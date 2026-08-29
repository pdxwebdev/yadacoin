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

from yadacoin.core.contenttakedown import TakedownReasonCode
from yadacoin.http.base import BaseHandler

from . import store
from .backends import available_backends
from .service import (
    FileAnnouncementServiceError,
    create_file,
    delete_file,
    download_file,
    takedown_file,
    update_file,
)


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


class BaseFileAnnouncementHandler(BaseHandler):
    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")

    def _error(self, status, message):
        self.set_status(status)
        return self.render_as_json({"status": False, "error": message})


class FileAnnouncementDashboardHandler(BaseFileAnnouncementHandler):
    async def get(self):
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
                    {"value": r.value, "name": r.name} for r in TakedownReasonCode
                ],
            }
        )


HANDLERS = [
    (r"/file-announcements", FileAnnouncementDashboardHandler),
    (r"/file-announcements/api/v1/files", FileListHandler),
    (r"/file-announcements/api/v1/files/search", FileSearchHandler),
    (r"/file-announcements/api/v1/files/([^/]+)/takedown", FileTakedownHandler),
    (r"/file-announcements/api/v1/files/([^/]+)/download", FileDownloadHandler),
    (r"/file-announcements/api/v1/files/([^/]+)", FileDetailHandler),
    (r"/file-announcements/api/v1/history", FileHistoryHandler),
    (r"/file-announcements/api/v1/settings", FileSettingsHandler),
    (r"/file-announcements/api/v1/backends", FileBackendsHandler),
    (r"/file-announcements/api/v1/takedown-reasons", FileTakedownReasonsHandler),
]
