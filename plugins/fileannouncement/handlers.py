"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import json
import os
import tempfile
import time
from urllib.parse import quote

import tornado.web
from tornado.iostream import StreamClosedError

from plugins.keyrotation.handlers import KelUnlockHandler
from yadacoin.core.contenttakedown import TakedownReasonCode
from yadacoin.http.base import BaseHandler

from . import store
from .backends import available_backends
from .service import (
    FileAnnouncementServiceError,
    announce_content_takedown,
    create_file,
    delete_file,
    download_by_backend_file_id,
    download_file,
    takedown_file,
    update_file,
)

_STREAM_CACHE: dict = {}
_STREAM_CACHE_TTL = 3600
_STREAM_CHUNK = 256 * 1024
_STREAM_TMP_DIR = os.path.join(tempfile.gettempdir(), "yada_fileannouncement_stream")
os.makedirs(_STREAM_TMP_DIR, exist_ok=True)
for _orphan in os.listdir(_STREAM_TMP_DIR):
    try:
        os.unlink(os.path.join(_STREAM_TMP_DIR, _orphan))
    except OSError:
        pass

DEMO_DIR = os.path.join(os.path.dirname(__file__), "demos", "yadascrollerdemo")


def _evict_stream_cache():
    now = time.monotonic()
    for key in list(_STREAM_CACHE):
        entry = _STREAM_CACHE[key]
        path, _total, exp = entry[0], entry[1], entry[2]
        if now > exp:
            try:
                os.unlink(path)
            except OSError:
                pass
            del _STREAM_CACHE[key]


def _video_public_item(item: dict) -> dict:
    f = item.get("file") or {}
    backend = (f.get("backend") or "sia").strip().lower()
    file_id = (f.get("file_id") or "").strip()
    return {
        "source": item.get("source") or "",
        "block_index": item.get("block_index"),
        "transaction_id": item.get("transaction_id") or "",
        "title": f.get("title") or "",
        "description": f.get("description") or "",
        "keywords": list(f.get("keywords") or []),
        "filename": f.get("filename") or "",
        "mime_type": f.get("mime_type") or "",
        "size": f.get("size") or 0,
        "backend": backend,
        "file_id": file_id,
        "stream_url": (
            f"/file-announcements/api/v1/public/stream/{quote(backend, safe='')}/"
            f"{quote(file_id, safe='')}"
            if file_id
            else ""
        ),
    }


def _json_body(handler):
    if not handler.request.body:
        return {}
    try:
        return json.loads(handler.request.body.decode("utf-8"))
    except Exception:
        raise ValueError("Invalid JSON body")


def _keywords(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [k.strip() for k in str(value).split(",") if k.strip()]


KEL_SESSION_COOKIE = "file_announcement_kel"


class FileAnnouncementUnlockHandler(KelUnlockHandler):
    """POST /file-announcements/api/v1/unlock — KelUnlockHandler plus operator cookie."""

    def render_as_json(self, data, indent=None):
        if isinstance(data, dict) and data.get("status") is True:
            self.set_secure_cookie(KEL_SESSION_COOKIE, str(time.time()))
        return super().render_as_json(data, indent)


class BaseFileAnnouncementHandler(BaseHandler):
    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")

    async def kel_is_unlocked(self):
        cookie = self.get_secure_cookie(KEL_SESSION_COOKIE)
        if not cookie:
            return False
        try:
            ts = float(cookie.decode())
        except (ValueError, AttributeError, UnicodeDecodeError):
            return False
        return ts >= await self.get_auth_cutoff()

    async def prepare(self, exceptions=None):
        await super().prepare(exceptions=exceptions)
        if self._finished:
            return
        if self.request.method == "OPTIONS":
            return
        if await self.kel_is_unlocked() or await self.wallet_is_unlocked():
            return
        self.set_status(401)
        path = self.request.path or ""
        if path.startswith("/file-announcements/api/"):
            self.render_as_json({"status": False, "error": "not authorized"})
        else:
            self.render(
                "locked.html",
                yadacoin=self.yadacoin_vars,
                title="YadaCoin - File Announcements",
            )
            self.finish()

    def _error(self, status, message):
        self.set_status(status)
        return self.render_as_json({"status": False, "error": message})


class FileAnnouncementDashboardHandler(BaseFileAnnouncementHandler):
    async def get(self):
        if not (await self.kel_is_unlocked() or await self.wallet_is_unlocked()):
            return
        self.render(
            "dashboard.html",
            yadacoin=self.yadacoin_vars,
            title="YadaCoin - File Announcements",
        )


class FileListHandler(BaseFileAnnouncementHandler):
    async def get(self):
        query = self.get_query_argument("q", "")
        status = self.get_query_argument("status", "")
        try:
            limit = min(int(self.get_query_argument("limit", 100)), 500)
            skip = max(int(self.get_query_argument("skip", 0)), 0)
        except ValueError:
            return self._error(400, "limit and skip must be integers")
        files = await store.list_files(
            self.config, query=query, status=status, limit=limit, skip=skip
        )
        return self.render_as_json(
            {"status": True, "count": len(files), "results": files}
        )

    async def post(self):
        filename = ""
        mime_type = ""
        content = None
        ct = self.request.headers.get("Content-Type") or ""
        if self.request.files.get("file") or "multipart/form-data" in ct:
            if self.request.files.get("file"):
                upload = self.request.files["file"][0]
                content = upload["body"]
                filename = upload.get("filename") or ""
                mime_type = upload.get("content_type") or ""
            title = self.get_body_argument("title", "") or filename
            description = self.get_body_argument("description", "")
            keywords = _keywords(self.get_body_argument("keywords", ""))
            file_id = self.get_body_argument("file_id", "")
            backend = self.get_body_argument("backend", "")
        else:
            try:
                data = _json_body(self)
            except ValueError as exc:
                return self._error(400, str(exc))
            title = data.get("title") or ""
            description = data.get("description") or ""
            keywords = _keywords(data.get("keywords"))
            filename = data.get("filename") or ""
            mime_type = data.get("mime_type") or ""
            file_id = data.get("file_id") or ""
            backend = data.get("backend") or ""
            raw = data.get("content_b64") or ""
            if raw:
                import base64

                try:
                    content = base64.b64decode(raw)
                except Exception:
                    return self._error(400, "content_b64 is not valid base64")
        if not title:
            return self._error(400, "title is required")
        try:
            record = await create_file(
                self.config,
                title=title,
                description=description,
                keywords=keywords,
                content=content,
                filename=filename,
                mime_type=mime_type,
                file_id=file_id,
                backend_name=backend,
            )
        except (FileAnnouncementServiceError, ValueError) as exc:
            return self._error(400, str(exc))
        self.set_status(201)
        return self.render_as_json({"status": True, "result": record})


class FileDetailHandler(BaseFileAnnouncementHandler):
    async def get(self, record_id):
        doc = await store.get_file(self.config, record_id)
        if not doc:
            return self._error(404, "file not found")
        return self.render_as_json({"status": True, "result": doc})

    async def put(self, record_id):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        kwargs = {}
        if "title" in data:
            kwargs["title"] = data.get("title")
        if "description" in data:
            kwargs["description"] = data.get("description")
        if "keywords" in data:
            kwargs["keywords"] = _keywords(data.get("keywords"))
        try:
            record = await update_file(self.config, record_id, **kwargs)
        except FileAnnouncementServiceError as exc:
            code = 404 if "not found" in str(exc) else 400
            return self._error(code, str(exc))
        return self.render_as_json({"status": True, "result": record})

    async def delete(self, record_id):
        delete_backend = (
            self.get_query_argument("delete_backend", "true").lower() != "false"
        )
        try:
            result = await delete_file(
                self.config, record_id, delete_backend=delete_backend
            )
        except FileAnnouncementServiceError as exc:
            code = 404 if "not found" in str(exc) else 400
            return self._error(code, str(exc))
        return self.render_as_json({"status": True, "result": result})


class FileSearchHandler(BaseFileAnnouncementHandler):
    async def get(self):
        query = self.get_query_argument("q", "")
        try:
            limit = min(int(self.get_query_argument("limit", 50)), 200)
        except ValueError:
            return self._error(400, "limit must be an integer")
        local = await store.list_files(self.config, query=query, limit=limit)
        chain = await store.search_chain(self.config, query=query, limit=limit)
        return self.render_as_json(
            {
                "status": True,
                "query": query,
                "local": local,
                "network": chain,
            }
        )


class FileHistoryHandler(BaseFileAnnouncementHandler):
    async def get(self):
        query = self.get_query_argument("q", "")
        record_id = self.get_query_argument("record_id", "")
        try:
            limit = min(int(self.get_query_argument("limit", 200)), 500)
            skip = max(int(self.get_query_argument("skip", 0)), 0)
        except ValueError:
            return self._error(400, "limit and skip must be integers")
        items = await store.list_history(
            self.config,
            query=query,
            record_id=record_id,
            limit=limit,
            skip=skip,
        )
        return self.render_as_json(
            {"status": True, "count": len(items), "results": items}
        )


class FileTakedownHandler(BaseFileAnnouncementHandler):
    async def post(self, record_id):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        reason = (data.get("reason_code") or "").strip()
        if not reason:
            return self._error(400, "reason_code is required")
        delete_backend = bool(data.get("delete_backend"))
        try:
            result = await takedown_file(
                self.config,
                record_id,
                reason_code=reason,
                delete_backend=delete_backend,
            )
        except FileAnnouncementServiceError as exc:
            code = 404 if "not found" in str(exc) else 400
            return self._error(code, str(exc))
        return self.render_as_json({"status": True, "result": result})


class FileDownloadHandler(BaseFileAnnouncementHandler):
    async def get(self, record_id):
        try:
            result = await download_file(self.config, record_id)
        except FileAnnouncementServiceError as exc:
            code = 404 if "not found" in str(exc) else 400
            return self._error(code, str(exc))
        except Exception as exc:
            return self._error(502, str(exc))
        filename = result.get("filename") or "download"
        mime_type = result.get("mime_type") or "application/octet-stream"
        self.set_header("Content-Type", mime_type)
        self.set_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.write(result["content"])
        return self.finish()


class FileSettingsHandler(BaseFileAnnouncementHandler):
    async def get(self):
        settings = await store.get_settings(self.config)
        redacted = dict(settings)
        key = redacted.get("sia_app_key") or ""
        redacted["sia_app_key_configured"] = bool(key)
        if key:
            redacted["sia_app_key"] = key[:6] + "…" + key[-4:]
        return self.render_as_json({"status": True, "result": redacted})

    async def put(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        allowed = {
            k: data[k]
            for k in ("backend", "sia_app_key", "sia_indexer_url")
            if k in data
        }
        settings = await store.save_settings(self.config, allowed)
        redacted = dict(settings)
        key = redacted.get("sia_app_key") or ""
        redacted["sia_app_key_configured"] = bool(key)
        if key:
            redacted["sia_app_key"] = key[:6] + "…" + key[-4:]
        return self.render_as_json({"status": True, "result": redacted})


class FileBackendsHandler(BaseFileAnnouncementHandler):
    async def get(self):
        return self.render_as_json({"status": True, "results": available_backends()})


class FileTakedownReasonsHandler(BaseFileAnnouncementHandler):
    async def get(self):
        return self.render_as_json(
            {
                "status": True,
                "results": [
                    {"value": r.value, "name": r.name, "label": _reason_label(r)}
                    for r in TakedownReasonCode
                ],
            }
        )


def _reason_label(r: TakedownReasonCode) -> str:
    return r.name.replace("_", " ").title()


class PublicTakedownReasonsHandler(BaseHandler):
    """GET /file-announcements/api/v1/public/takedown-reasons"""

    async def get(self):
        return self.render_as_json(
            {
                "status": True,
                "results": [
                    {
                        "value": r.value,
                        "name": r.name,
                        "label": _reason_label(r),
                    }
                    for r in TakedownReasonCode
                ],
            }
        )


class PublicTakedownHandler(BaseHandler):
    """POST /file-announcements/api/v1/public/takedown

    Body: { "transaction_id": "<file announcement txn id>", "reason_code": "csam"|... }
    Mints an on-chain ContentTakedownAnnouncement via this node's KEL.
    """

    async def options(self):
        self.set_status(204)
        self.finish()

    async def post(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            self.set_status(400)
            return self.render_as_json({"status": False, "error": str(exc)})
        transaction_id = (data.get("transaction_id") or "").strip()
        reason_code = (data.get("reason_code") or "").strip()
        if not transaction_id:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "error": "transaction_id is required"}
            )
        if not reason_code:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "error": "reason_code is required"}
            )
        try:
            result = await announce_content_takedown(
                self.config,
                transaction_id=transaction_id,
                reason_code=reason_code,
                delete_backend=bool(data.get("delete_backend")),
            )
        except FileAnnouncementServiceError as exc:
            msg = str(exc)
            code = 400
            if "KEL" in msg or "key event" in msg.lower() or "not initialized" in msg:
                code = 503
            self.set_status(code)
            return self.render_as_json({"status": False, "error": msg})
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json({"status": False, "error": str(exc)})
        return self.render_as_json({"status": True, "result": result})


class PublicVideoListHandler(BaseHandler):
    """GET /file-announcements/api/v1/public/videos — no auth; video announcements only."""

    async def get(self):
        query = self.get_query_argument("q", "")
        try:
            limit = min(int(self.get_query_argument("limit", 30)), 100)
            skip = max(int(self.get_query_argument("skip", 0)), 0)
        except ValueError:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "error": "limit and skip must be integers"}
            )
        raw = await store.search_videos(
            self.config, query=query, limit=limit, skip=skip
        )
        results = [_video_public_item(item) for item in raw]
        results = [r for r in results if r.get("file_id") and r.get("stream_url")]
        return self.render_as_json(
            {
                "status": True,
                "query": query,
                "count": len(results),
                "results": results,
            }
        )


class PublicStreamHandler(BaseHandler):
    """GET /file-announcements/api/v1/public/stream/{backend}/{file_id} — Range streaming."""

    async def options(self, backend=None, file_id=None):
        self.set_status(204)
        self.finish()

    async def head(self, backend, file_id):
        """Browsers / media stacks sometimes probe with HEAD before Range GET."""
        await self._prepare_cache(backend, file_id)
        if self._finished:
            return
        cache_key = f"{(backend or '').strip().lower()}:{(file_id or '').strip()}"
        entry = _STREAM_CACHE.get(cache_key)
        if not entry:
            self.set_status(404)
            return self.finish()
        tmp_path, total, _, filename, mime_type = entry
        is_av = mime_type.startswith("video/") or mime_type.startswith("audio/")
        self.set_header("Content-Type", mime_type)
        self.set_header("Accept-Ranges", "bytes")
        self.set_header("Content-Length", str(total))
        safe_name = filename.replace('"', "")
        self.set_header(
            "Content-Disposition",
            f'inline; filename="{safe_name}"'
            if is_av
            else f'attachment; filename="{safe_name}"',
        )
        self.set_status(200)
        return self.finish()

    async def _prepare_cache(self, backend, file_id):
        backend = (backend or "").strip().lower()
        file_id = (file_id or "").strip()
        if not backend or not file_id:
            self.set_status(400)
            self.finish("backend and file_id are required")
            return None

        filename = self.get_query_argument("filename", "") or ""
        mime_type = self.get_query_argument("mime_type", "") or ""

        _evict_stream_cache()
        cache_key = f"{backend}:{file_id}"

        if cache_key not in _STREAM_CACHE:
            try:
                result = await download_by_backend_file_id(
                    self.config,
                    backend,
                    file_id,
                    filename=filename,
                    mime_type=mime_type,
                )
            except FileAnnouncementServiceError as exc:
                self.set_status(404 if "not found" in str(exc).lower() else 502)
                self.finish(str(exc))
                return None
            except Exception as exc:
                self.set_status(502)
                self.finish(str(exc))
                return None

            content = result.get("content") or b""
            filename = result.get("filename") or filename or file_id[:16]
            mime_type = (
                result.get("mime_type") or mime_type or "application/octet-stream"
            )
            fd, tmp_path = tempfile.mkstemp(prefix="fa_stream_", dir=_STREAM_TMP_DIR)
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(content)
                total = len(content)
            except Exception:
                try:
                    os.close(fd)
                except OSError:
                    pass
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                self.set_status(500)
                self.finish("failed to cache stream")
                return None
            _STREAM_CACHE[cache_key] = (
                tmp_path,
                total,
                time.monotonic() + _STREAM_CACHE_TTL,
                filename,
                mime_type,
            )
        else:
            tmp_path, total, _, filename, mime_type = _STREAM_CACHE[cache_key]
            _STREAM_CACHE[cache_key] = (
                tmp_path,
                total,
                time.monotonic() + _STREAM_CACHE_TTL,
                filename,
                mime_type,
            )
        return cache_key, tmp_path, total, filename, mime_type

    async def get(self, backend, file_id):
        prepared = await self._prepare_cache(backend, file_id)
        if self._finished or not prepared:
            return
        _cache_key, tmp_path, total, filename, mime_type = prepared

        is_av = mime_type.startswith("video/") or mime_type.startswith("audio/")
        self.set_header("Content-Type", mime_type)
        self.set_header("Accept-Ranges", "bytes")
        self.set_header(
            "Access-Control-Expose-Headers",
            "Content-Type, Content-Length, Content-Range, Accept-Ranges",
        )
        safe_name = filename.replace('"', "")
        self.set_header(
            "Content-Disposition",
            f'inline; filename="{safe_name}"'
            if is_av
            else f'attachment; filename="{safe_name}"',
        )

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
                            chunk = fh.read(min(_STREAM_CHUNK, remaining))
                            if not chunk:
                                break
                            self.write(chunk)
                            await self.flush()
                            remaining -= len(chunk)
                except (ValueError, IndexError):
                    self.set_status(400)
                    return self.finish("Invalid Range header")
            else:
                self.set_header("Content-Length", str(total))
                with open(tmp_path, "rb") as fh:
                    while True:
                        chunk = fh.read(_STREAM_CHUNK)
                        if not chunk:
                            break
                        self.write(chunk)
                        await self.flush()
        except StreamClosedError:
            return
        self.finish()


class YadaScrollerDemoHandler(BaseHandler):
    """GET /file-announcements/demo/yadascroller — serve demo index."""

    async def get(self, path=None):
        path = (path or "").lstrip("/")
        if not path or path.endswith("/"):
            path = "index.html"
        full = os.path.normpath(os.path.join(DEMO_DIR, path))
        if not full.startswith(
            os.path.normpath(DEMO_DIR) + os.sep
        ) and full != os.path.normpath(DEMO_DIR):
            self.set_status(403)
            return self.finish("forbidden")
        if not os.path.isfile(full):
            self.set_status(404)
            return self.finish("not found")
        self.set_header("Cache-Control", "no-cache")
        return await self._serve_file(full)

    async def _serve_file(self, full):
        # Delegate content-type via StaticFileHandler helpers
        content_type = self._guess_type(full)
        self.set_header("Content-Type", content_type)
        with open(full, "rb") as fh:
            self.write(fh.read())
        return self.finish()

    def _guess_type(self, path):
        import mimetypes

        guessed, _ = mimetypes.guess_type(path)
        return guessed or "application/octet-stream"


HANDLERS = [
    (r"/file-announcements", FileAnnouncementDashboardHandler),
    (r"/file-announcements/api/v1/unlock", FileAnnouncementUnlockHandler),
    (r"/file-announcements/api/v1/files", FileListHandler),
    (r"/file-announcements/api/v1/files/search", FileSearchHandler),
    (r"/file-announcements/api/v1/files/([^/]+)/takedown", FileTakedownHandler),
    (r"/file-announcements/api/v1/files/([^/]+)/download", FileDownloadHandler),
    (r"/file-announcements/api/v1/files/([^/]+)", FileDetailHandler),
    (r"/file-announcements/api/v1/history", FileHistoryHandler),
    (r"/file-announcements/api/v1/settings", FileSettingsHandler),
    (r"/file-announcements/api/v1/backends", FileBackendsHandler),
    (r"/file-announcements/api/v1/takedown-reasons", FileTakedownReasonsHandler),
    (r"/file-announcements/api/v1/public/videos", PublicVideoListHandler),
    (
        r"/file-announcements/api/v1/public/takedown-reasons",
        PublicTakedownReasonsHandler,
    ),
    (r"/file-announcements/api/v1/public/takedown", PublicTakedownHandler),
    (
        r"/file-announcements/api/v1/public/stream/([^/]+)/([^/]+)",
        PublicStreamHandler,
    ),
    (r"/file-announcements/demo/yadascroller/?", YadaScrollerDemoHandler),
    (
        r"/file-announcements/demo/yadascroller/(.*)",
        tornado.web.StaticFileHandler,
        {"path": DEMO_DIR},
    ),
]
