"""sia/handlers.py — Public download proxy for Sia share tokens.

GET /ai-agent-auth/sia/download/<token>

Anyone who has the share URL can download the file directly in their browser.
No Sia software required.  The token is a random URL-safe string stored in
MongoDB by sia_share() along with the object_id, app_key_hex, and expiry.

The file is streamed chunk-by-chunk using the SDK's Download.read() method
run in a thread-pool executor so the Tornado event loop is never blocked.
"""
import datetime

from yadacoin.http.base import BaseHandler


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

        # Read metadata for headers before streaming
        meta: dict = {}
        try:
            import json

            meta_bytes = obj.metadata()
            if meta_bytes:
                meta = json.loads(meta_bytes.decode("utf-8", errors="replace"))
        except Exception:
            pass

        mime_type = meta.get("mime_type") or "application/octet-stream"
        filename = meta.get("filename") or object_id[:16]

        self.set_header("Content-Type", mime_type)
        self.set_header(
            "Content-Disposition",
            f'attachment; filename="{filename}"',
        )

        # Stream chunk-by-chunk using the SDK's async-wrapped read().
        try:
            async with sdk.download(obj, DownloadOptions()) as d:
                while True:
                    chunk = await d.read()
                    if not chunk:
                        break
                    self.write(chunk)
                    await self.flush()
        except Exception as exc:
            # Headers already sent — can't change status, just close
            self.config.app_log.error(f"SiaDownloadHandler stream error: {exc}")
        finally:
            self.finish()
