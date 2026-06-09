"""sia/handlers.py — Public download proxy for Sia share tokens.

GET /ai-agent-auth/sia/download/<token>

Anyone who has the share URL can download the file directly in their browser.
No Sia software required.  The token is a random URL-safe string stored in
MongoDB by sia_share() along with the object_id, app_key_hex, and expiry.

Files are streamed from Sia chunk-by-chunk into a per-object temp file on
disk (keyed by object_id, auto-cleaned when expired).  Serving from disk
with Range support keeps RAM usage bounded to ~one Sia slab (~4 MB) regardless
of file size.
"""
import asyncio
import datetime
import mimetypes
import os
import tempfile
import time

from yadacoin.http.base import BaseHandler

# In-process disk cache: object_id → (tmp_path, total_bytes, expires_monotonic)
_FILE_CACHE: dict = {}
_CACHE_TTL = 3600  # seconds — evict temp files after 1 hour
_CHUNK_SEND = 256 * 1024  # 256 KB chunks when serving to browser

# All temp files live in a single directory so orphans from a previous
# server run are wiped clean on the next startup.
_SIA_TMP_DIR = os.path.join(tempfile.gettempdir(), "sia_dl_cache")
os.makedirs(_SIA_TMP_DIR, exist_ok=True)
# Remove any leftover files from a previous process
for _f in os.listdir(_SIA_TMP_DIR):
    try:
        os.unlink(os.path.join(_SIA_TMP_DIR, _f))
    except OSError:
        pass


def _evict_expired_cache():
    now = time.monotonic()
    for oid in list(_FILE_CACHE):
        path, _, exp = _FILE_CACHE[oid]
        if now > exp:
            try:
                os.unlink(path)
            except OSError:
                pass
            del _FILE_CACHE[oid]


class SiaDownloadHandler(BaseHandler):
    """Stream a Sia file to the requester using a pre-issued share token."""

    async def get(self, token: str):
        token = (token or "").strip()
        if not token:
            self.set_status(400)
            return self.finish("Missing token")

        doc = await self.config.mongo.async_db.sia_share_tokens.find_one(
            {"token": token}
        )
        if not doc:
            self.set_status(404)
            return self.finish("Share link not found or already expired")

        expires_at = doc.get("expires_at")
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            if datetime.datetime.now(datetime.timezone.utc) > expires_at:
                await self.config.mongo.async_db.sia_share_tokens.delete_one(
                    {"token": token}
                )
                self.set_status(410)
                return self.finish("Share link has expired")

        object_id = doc.get("object_id", "")
        app_key_hex = doc.get("app_key_hex", "")

        try:
            from sia_storage import DownloadOptions  # type: ignore[import]

            from .api import _get_sdk
        except ImportError as exc:
            self.set_status(502)
            return self.finish(f"sia-storage SDK not available: {exc}")

        try:
            sdk = await _get_sdk(app_key_hex)
            obj = await sdk.object(object_id.strip())
        except Exception as exc:
            self.set_status(502)
            return self.finish(f"Object lookup failed: {exc}")

        # Read metadata for Content-Type / filename
        meta: dict = {}
        try:
            import json

            meta_bytes = obj.metadata()
            if meta_bytes:
                meta = json.loads(meta_bytes.decode("utf-8", errors="replace"))
        except Exception:
            pass

        filename = meta.get("filename") or object_id[:16]
        mime_type = meta.get("mime_type") or ""
        if not mime_type:
            guessed, _ = mimetypes.guess_type(filename)
            mime_type = guessed or "application/octet-stream"

        # ── Disk cache ────────────────────────────────────────────────────────
        _evict_expired_cache()
        cache_key = object_id.strip()

        if cache_key not in _FILE_CACHE:
            # Stream Sia → temp file chunk-by-chunk (bounded RAM usage)
            tmp_fd, tmp_path = tempfile.mkstemp(prefix="sia_dl_", dir=_SIA_TMP_DIR)
            try:
                async with sdk.download(obj, DownloadOptions()) as d:
                    try:
                        with os.fdopen(tmp_fd, "wb") as fh:
                            tmp_fd = None  # ownership transferred
                            async for chunk in d:
                                fh.write(chunk)
                                # yield to event loop so other requests aren't starved
                                await asyncio.sleep(0)
                    except Exception as exc:
                        self.config.app_log.error(
                            f"SiaDownloadHandler write error: {exc}"
                        )
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass
                        self.set_status(503)
                        self.finish(f"File unavailable from Sia network: {exc}")
                        return
            except Exception as exc:
                if tmp_fd is not None:
                    os.close(tmp_fd)
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                self.config.app_log.error(f"SiaDownloadHandler error: {exc}")
                self.set_status(503)
                self.finish(f"Download failed: {exc}")
                return

            total = os.path.getsize(tmp_path)
            _FILE_CACHE[cache_key] = (tmp_path, total, time.monotonic() + _CACHE_TTL)
        else:
            tmp_path, total, _ = _FILE_CACHE[cache_key]
            # Refresh TTL on access
            _FILE_CACHE[cache_key] = (tmp_path, total, time.monotonic() + _CACHE_TTL)

        # ── Serve with Range support ──────────────────────────────────────────
        is_av = mime_type.startswith("video/") or mime_type.startswith("audio/")
        self.set_header("Content-Type", mime_type)
        self.set_header("Accept-Ranges", "bytes")
        self.set_header(
            "Content-Disposition",
            f'inline; filename="{filename}"'
            if is_av
            else f'attachment; filename="{filename}"',
        )

        from tornado.iostream import StreamClosedError

        range_header = self.request.headers.get("Range", "")
        try:
            if range_header and range_header.startswith("bytes="):
                try:
                    range_spec = range_header[6:]
                    start_str, _, end_str = range_spec.partition("-")
                    start = int(start_str) if start_str else 0
                    end = int(end_str) if end_str else total - 1
                    end = min(end, total - 1)
                    if start > end or start >= total:
                        self.set_status(416)
                        self.set_header("Content-Range", f"bytes */{total}")
                        self.finish()
                        return
                    self.set_status(206)
                    self.set_header("Content-Range", f"bytes {start}-{end}/{total}")
                    self.set_header("Content-Length", str(end - start + 1))
                    with open(tmp_path, "rb") as fh:
                        fh.seek(start)
                        remaining = end - start + 1
                        while remaining > 0:
                            chunk = fh.read(min(_CHUNK_SEND, remaining))
                            if not chunk:
                                break
                            self.write(chunk)
                            await self.flush()
                            remaining -= len(chunk)
                except (ValueError, IndexError):
                    self.set_status(400)
                    self.finish("Invalid Range header")
                    return
            else:
                self.set_header("Content-Length", str(total))
                with open(tmp_path, "rb") as fh:
                    while True:
                        chunk = fh.read(_CHUNK_SEND)
                        if not chunk:
                            break
                        self.write(chunk)
                        await self.flush()
        except StreamClosedError:
            # Browser cancelled the request (e.g. seeking skipped to a new
            # position) — this is normal, not an error worth logging.
            return

        self.finish()


class SiaUploadHandler(BaseHandler):
    """
    POST /ai-agent-auth/sia/upload

    Accepts a multipart/form-data upload with fields:
      - file  : the binary file (required)
      - app_key_hex : the user's Sia App Key hex (required)

    Returns JSON: {ok, object_id, size, filename, mime_type}
    """

    # Raise Tornado's body-size limit to 4 GB for this handler so large video
    # files don't cause a connection reset before the body is fully read.
    _MAX_UPLOAD_BYTES = 4 * 1024 * 1024 * 1024  # 4 GB

    def prepare(self):
        self.request.connection.set_max_body_size(self._MAX_UPLOAD_BYTES)
        # Must call super so BaseHandler sets up timeout_handle etc.
        return super().prepare()

    async def post(self):
        app_key_hex = (self.get_argument("app_key_hex", "") or "").strip()
        if not app_key_hex:
            self.set_status(400)
            return self.render_as_json(
                {"ok": False, "error": "app_key_hex is required"}
            )

        files = self.request.files.get("file")
        if not files:
            self.set_status(400)
            return self.render_as_json({"ok": False, "error": "file is required"})

        file_info = files[0]
        filename = file_info.get("filename") or "upload"
        body = file_info["body"]
        content_type = file_info.get("content_type") or ""
        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
            content_type = content_type or "application/octet-stream"

        # .sia extension is always a Sia manifest — never raw content
        if filename.lower().endswith(".sia"):
            self.set_status(400)
            return self.render_as_json(
                {
                    "ok": False,
                    "error": (
                        "This is a .sia reference file. "
                        "To access the file, use sia_storage/download with the object_id "
                        "stored inside it, or open it with a Sia-compatible client."
                    ),
                }
            )

        try:
            from .api import sia_upload

            result = await sia_upload(
                app_key_hex,
                body,
                filename=filename,
                mime_type=content_type,
            )
        except Exception as exc:
            self.set_status(502)
            return self.render_as_json({"ok": False, "error": str(exc)[:400]})

        result["filename"] = filename
        result["mime_type"] = content_type
        return self.render_as_json(result)
