"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import json
import os
import tempfile
import time
from urllib.parse import quote

import tornado.web
from tornado.iostream import StreamClosedError

from plugins.keyrotation.handlers import KelUnlockHandler
from plugins.yadapasswordsignin.handlers import redirect_to_signin
from yadacoin.core.contenttakedown import TakedownReasonCode
from yadacoin.http.base import BaseHandler

from . import paidstore, progress, purchase, store
from .backends import available_backends
from .service import (
    DuplicateFileAnnouncementError,
    FileAnnouncementServiceError,
    announce_content_takedown,
    assert_live,
    create_file,
    delete_file,
    download_file,
    forget_live,
    open_public_range,
    operator_inception_public_key_hash,
    prepare_public_stream,
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


def _drop_stream_cache_entry(key):
    entry = _STREAM_CACHE.pop(key, None)
    if not entry:
        return False
    try:
        os.unlink(entry[0])
    except OSError:
        pass
    return True


def list_stream_cache():
    _evict_stream_cache()
    now = time.monotonic()
    results = []
    for key, entry in _STREAM_CACHE.items():
        path, total, exp = entry[0], entry[1], entry[2]
        filename = entry[3] if len(entry) > 3 else ""
        mime_type = entry[4] if len(entry) > 4 else ""
        backend, _, file_id = key.partition(":")
        cached_at = None
        try:
            cached_at = os.path.getmtime(path)
        except OSError:
            pass
        results.append(
            {
                "key": key,
                "backend": backend,
                "file_id": file_id,
                "filename": filename,
                "mime_type": mime_type,
                "size": total,
                "path": path,
                "present": os.path.isfile(path),
                "cached_at": cached_at,
                "expires_in": max(0, int(exp - now)),
            }
        )
    results.sort(key=lambda row: row.get("cached_at") or 0, reverse=True)
    return {
        "count": len(results),
        "total_bytes": sum(row.get("size") or 0 for row in results),
        "ttl_seconds": _STREAM_CACHE_TTL,
        "directory": _STREAM_TMP_DIR,
        "results": results,
    }


def delete_stream_cache(key):
    _evict_stream_cache()
    return 1 if _drop_stream_cache_entry(key) else 0


def drop_stream_cache_for_file(backend, file_id):
    backend = (backend or "sia").strip().lower()
    file_id = (file_id or "").strip()
    if not file_id:
        return 0
    forget_live(backend, file_id)
    return 1 if _drop_stream_cache_entry(f"{backend}:{file_id}") else 0


def parse_byte_range(header, total):
    """Return (start, end) inclusive, or None for an unsatisfiable range."""
    total = int(total)
    if total <= 0:
        return None
    if not header:
        return 0, total - 1
    if not header.startswith("bytes="):
        raise ValueError("invalid range")
    spec = header[6:].split(",", 1)[0].strip()
    start_str, sep, end_str = spec.partition("-")
    if not sep:
        raise ValueError("invalid range")
    if start_str == "":
        suffix = int(end_str)
        if suffix <= 0:
            raise ValueError("invalid range")
        start = max(0, total - suffix)
        end = total - 1
    else:
        start = int(start_str)
        end = int(end_str) if end_str else total - 1
    end = min(end, total - 1)
    if start < 0 or start >= total or start > end:
        return None
    return start, end


async def prune_stream_cache(config):
    """Drop cached streams whose announcement is gone, retracted, or taken down."""
    for key in list(_STREAM_CACHE):
        backend, _, file_id = key.partition(":")
        live = await store.live_announcement(config, file_id, backend)
        if not live:
            _drop_stream_cache_entry(key)


def clear_stream_cache():
    _evict_stream_cache()
    deleted = 0
    for key in list(_STREAM_CACHE):
        if _drop_stream_cache_entry(key):
            deleted += 1
    return deleted


def _thumbnail_url(backend: str, thumbnail_file_id: str) -> str:
    thumb = (thumbnail_file_id or "").strip()
    if not thumb:
        return ""
    return (
        f"/file-announcements/api/v1/public/stream/{quote(backend, safe='')}/"
        f"{quote(thumb, safe='')}?mime_type=image%2Fjpeg&filename=thumb.jpg"
    )


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
        "owner": (item.get("owner") or "").strip(),
        "public_key_hash": (item.get("public_key_hash") or "").strip(),
        "username": (item.get("username") or "").strip(),
        "price": str(f.get("price") or "").strip(),
        "grant_seconds": str(f.get("grant_seconds") or "").strip(),
        "required_claim": str(f.get("required_claim") or "").strip(),
        "required_issuer": str(f.get("required_issuer") or "").strip(),
        "required_credentials": list(f.get("required_credentials") or []),
        "stream_url": (
            ""
            if str(f.get("price") or "").strip()
            else (
                f"/file-announcements/api/v1/public/stream/{quote(backend, safe='')}/"
                f"{quote(file_id, safe='')}"
                if file_id
                else ""
            )
        ),
        "thumbnail_url": _thumbnail_url(backend, f.get("thumbnail_file_id") or ""),
        "type": str(f.get("type") or "").strip().lower(),
    }


def _json_body(handler):
    if not handler.request.body:
        return {}
    try:
        return json.loads(handler.request.body.decode("utf-8"))
    except Exception:
        raise ValueError("Invalid JSON body")


async def _issuer_names(handler, gates=None) -> dict:
    """Map issuer signatures for these gates only. Does not scan every identity."""
    from .credentials import looks_like_username

    names = {}
    seen = set()
    for gate in gates or []:
        issuer = str((gate or {}).get("issuer") or "").strip().lstrip("@")
        key = issuer.lower()
        if not issuer or key in seen or not looks_like_username(issuer):
            continue
        seen.add(key)
        try:
            sigs = await store.signatures_for_username(handler.config, issuer)
        except Exception:
            sigs = []
        for sig in sigs:
            names[sig] = issuer
    return names


async def _operator_credential_badges(handler) -> list:
    if not await operator_session_unlocked(handler):
        return []
    username = _operator_username(handler.config)
    if not username:
        return []
    try:
        badges = []
        for signature in await store.signatures_for_username(handler.config, username):
            badges.extend(await store.received_credentials(handler.config, signature))
        return badges
    except Exception:
        return []


async def _credential_blocked(handler, live, file_id: str = "") -> bool:
    """Deny a download when the announcement requires a W3C presentation."""
    from .credentials import (
        PresentationError,
        credential_requirements,
        credentials_satisfy,
        presentation_from_parts,
        requirement_applies,
        verify_presentation,
    )

    if not requirement_applies(live, file_id):
        return False
    gates = credential_requirements(live)
    names = await _issuer_names(handler, gates)
    presented = _presented_vp(handler)
    if presented:
        try:
            verify_presentation(
                presentation_from_parts(presented, ""),
                gates=gates,
                issuer_names=names,
            )
            return False
        except PresentationError:
            pass
    if credentials_satisfy(
        await _operator_credential_badges(handler), gates, issuer_names=names
    ):
        return False
    handler.set_status(403)
    handler.finish("credential required")
    return True


def _presented_vp(handler) -> str:
    return (
        handler.request.headers.get("X-Yada-VP", "")
        or handler.get_query_argument("vp", "")
        or ""
    ).strip()


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


async def kel_session_unlocked(handler) -> bool:
    cookie = handler.get_secure_cookie(KEL_SESSION_COOKIE)
    if not cookie:
        return False
    try:
        ts = float(cookie.decode())
    except (ValueError, AttributeError, UnicodeDecodeError):
        return False
    return ts >= await handler.get_auth_cutoff()


async def operator_session_unlocked(handler) -> bool:
    """True when this request has a wallet or file-announcement KEL session."""
    if await handler.wallet_is_unlocked():
        return True
    return await kel_session_unlocked(handler)


class BaseFileAnnouncementHandler(BaseHandler):
    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")

    async def kel_is_unlocked(self):
        return await kel_session_unlocked(self)

    async def prepare(self, exceptions=None):
        await super().prepare(exceptions=exceptions)
        if self._finished:
            return
        if self.request.method == "OPTIONS":
            return
        if await self.kel_is_unlocked() or await self.wallet_is_unlocked():
            return
        path = self.request.path or ""
        if path.startswith("/file-announcements/api/"):
            self.set_status(401)
            self.render_as_json({"status": False, "error": "not authorized"})
        else:
            redirect_to_signin(self, "file-announcements")

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
    def initialize(self):
        super().initialize()
        self._upload_aborted = False

    def on_connection_close(self):
        self._upload_aborted = True
        super().on_connection_close()

    def _upload_cancelled(self):
        if self._upload_aborted:
            return True
        try:
            stream = self.request.connection.stream
            closed = stream is not None and stream.closed()
        except Exception:
            return False
        if closed:
            self._upload_aborted = True
        return bool(closed)

    async def get(self):
        query = self.get_query_argument("q", "")
        status = self.get_query_argument("status", "")
        try:
            limit = min(int(self.get_query_argument("limit", 100)), 500)
            skip = max(int(self.get_query_argument("skip", 0)), 0)
        except ValueError:
            return self._error(400, "limit and skip must be integers")
        files = await store.list_live_files(
            self.config, query=query, status=status, limit=limit, skip=skip
        )
        return self.render_as_json(
            {"status": True, "count": len(files), "results": files}
        )

    async def post(self):
        filename = ""
        mime_type = ""
        content = None
        upload_id = ""
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
            upload_id = self.get_body_argument("upload_id", "")
            file_type = self.get_body_argument("type", "")
            price = self.get_body_argument("price", "")
            grant_seconds = self.get_body_argument(
                "grant_duration", ""
            ) or self.get_body_argument("grant_seconds", "")
            required_claim = self.get_body_argument("required_claim", "")
            required_issuer = self.get_body_argument("required_issuer", "")
            required_credentials = self.get_body_argument("required_credentials", "")
            thumbnail = None
            if self.request.files.get("thumbnail"):
                thumbnail = self.request.files["thumbnail"][0].get("body") or None
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
            upload_id = data.get("upload_id") or ""
            file_type = data.get("type") or ""
            price = data.get("price") or ""
            grant_seconds = (
                data.get("grant_duration") or data.get("grant_seconds") or ""
            )
            required_claim = data.get("required_claim") or ""
            required_issuer = data.get("required_issuer") or ""
            required_credentials = data.get("required_credentials")
            thumbnail = None
            raw = data.get("content_b64") or ""
            if raw:
                import base64

                try:
                    content = base64.b64decode(raw)
                except Exception:
                    return self._error(400, "content_b64 is not valid base64")
        if thumbnail and len(thumbnail) > 512 * 1024:
            return self._error(400, "thumbnail exceeds 512KB")
        if not title:
            return self._error(400, "title is required")
        from yadacoin.core.fileannouncement import normalize_required_credentials

        from .credentials import canonical_issuer

        try:
            if isinstance(
                required_credentials, str
            ) and required_credentials.strip().startswith("["):
                required_credentials = json.loads(required_credentials)
            gates = normalize_required_credentials(
                required_credentials, required_claim, required_issuer
            )
            resolved_gates = []
            for gate in gates:
                resolved_gates.append(
                    {
                        "claim": gate["claim"],
                        "issuer": await canonical_issuer(gate["issuer"]),
                    }
                )
        except (ValueError, json.JSONDecodeError) as exc:
            return self._error(400, str(exc))
        upload_id = str(upload_id or "").strip()
        tracked = progress.begin(
            upload_id,
            filename=filename,
            size=len(content) if content else 0,
        )
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
                thumbnail=thumbnail,
                type=file_type,
                price=price,
                grant_seconds=grant_seconds,
                required_credentials=resolved_gates,
                on_progress=(
                    (lambda event, uid=upload_id: progress.apply(uid, event))
                    if tracked
                    else None
                ),
                cancelled=self._upload_cancelled,
            )
        except DuplicateFileAnnouncementError as exc:
            if tracked:
                progress.finish(upload_id, ok=False, error=str(exc))
            return self._error(409, str(exc))
        except (FileAnnouncementServiceError, ValueError) as exc:
            if tracked:
                progress.finish(upload_id, ok=False, error=str(exc))
            return self._error(400, str(exc))
        except Exception:
            if tracked:
                progress.finish(upload_id, ok=False, error="upload failed")
            raise
        if tracked:
            progress.finish(upload_id, ok=True)
        self.set_status(201)
        return self.render_as_json({"status": True, "result": record})


class FileUploadProgressHandler(BaseFileAnnouncementHandler):
    async def get(self, upload_id):
        return self.render_as_json(
            {"status": True, "result": progress.snapshot(upload_id)}
        )


class FileDetailHandler(BaseFileAnnouncementHandler):
    async def get(self, record_id):
        doc = await store.get_live_by_transaction_id(self.config, record_id)
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
        drop_stream_cache_for_file(result.get("backend"), result.get("file_id"))
        return self.render_as_json({"status": True, "result": result})


class FileSearchHandler(BaseFileAnnouncementHandler):
    async def get(self):
        query = self.get_query_argument("q", "")
        try:
            limit = min(int(self.get_query_argument("limit", 50)), 200)
        except ValueError:
            return self._error(400, "limit must be an integer")
        local = []
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
        local = result.get("local_record") if isinstance(result, dict) else None
        if isinstance(local, dict):
            drop_stream_cache_for_file(local.get("backend"), local.get("file_id"))
        elif isinstance(result, dict):
            drop_stream_cache_for_file(result.get("backend"), result.get("file_id"))
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


class StreamCacheHandler(BaseFileAnnouncementHandler):
    async def get(self):
        await prune_stream_cache(self.config)
        data = list_stream_cache()
        data["status"] = True
        return self.render_as_json(data)

    async def delete(self):
        clear_all = self.get_query_argument("all", "").lower() in ("1", "true", "yes")
        if clear_all:
            return self.render_as_json(
                {"status": True, "deleted": clear_stream_cache()}
            )
        key = self.get_query_argument("key", "")
        if not key:
            return self._error(400, "key is required")
        deleted = delete_stream_cache(key)
        if not deleted:
            return self._error(404, "cache entry not found")
        return self.render_as_json({"status": True, "deleted": deleted})


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
        local = result.get("local_record") if isinstance(result, dict) else None
        if isinstance(local, dict):
            drop_stream_cache_for_file(local.get("backend"), local.get("file_id"))
        return self.render_as_json({"status": True, "result": result})


async def _public_media_list(handler, match, search):
    query = handler.get_query_argument("q", "")
    transaction_id = (handler.get_query_argument("transaction_id", "") or "").strip()
    try:
        limit = min(int(handler.get_query_argument("limit", 30)), 100)
        skip = max(int(handler.get_query_argument("skip", 0)), 0)
    except ValueError:
        handler.set_status(400)
        return handler.render_as_json(
            {"status": False, "error": "limit and skip must be integers"}
        )
    tornado.ioloop.IOLoop.current().spawn_callback(prune_stream_cache, handler.config)
    if transaction_id:
        live = await store.get_live_by_transaction_id(handler.config, transaction_id)
        raw = [live] if live and match(live) else []
        results = [
            _public_file_item(row, keep_stream=not store.is_video_file(row))
            for row in raw
        ]
    else:
        raw = await search(handler.config, query=query, limit=limit, skip=skip)
        results = [_video_public_item(item) for item in raw]
    results = [
        r
        for r in results
        if r.get("file_id")
        and (r.get("stream_url") or r.get("price") or r.get("thumbnail_url"))
    ]
    from .credentials import badges_include_over18, is_adult_post

    if not badges_include_over18(await _operator_credential_badges(handler)):
        results = [r for r in results if not is_adult_post(r)]
    try:
        names = await store.identity_usernames(handler.config)
    except Exception:
        names = {}
    for item in results:
        item["username"] = names.get(item.get("owner") or "", "")
    return handler.render_as_json(
        {
            "status": True,
            "query": query,
            "count": len(results),
            "results": results,
        }
    )


class PublicVideoListHandler(BaseHandler):
    """GET /file-announcements/api/v1/public/videos — no auth; video announcements only."""

    async def get(self):
        return await _public_media_list(self, store.is_video_file, store.search_videos)


class PublicPhotoListHandler(BaseHandler):
    """GET /file-announcements/api/v1/public/photos — no auth; image announcements only."""

    async def get(self):
        return await _public_media_list(self, store.is_image_file, store.search_photos)


def _public_file_item(row: dict, username: str = "", keep_stream: bool = False) -> dict:
    shaped = {
        "source": row.get("source") or "",
        "block_index": row.get("block_index"),
        "transaction_id": row.get("transaction_id") or "",
        "owner": row.get("owner") or "",
        "public_key_hash": row.get("public_key_hash") or "",
        "username": username,
        "file": {
            "title": row.get("title") or "",
            "description": row.get("description") or "",
            "keywords": list(row.get("keywords") or []),
            "filename": row.get("filename") or "",
            "mime_type": row.get("mime_type") or "",
            "size": row.get("size") or 0,
            "backend": row.get("backend") or "sia",
            "file_id": row.get("file_id") or "",
            "thumbnail_file_id": row.get("thumbnail_file_id") or "",
            "type": str(row.get("type") or "").strip().lower(),
            "price": str(row.get("price") or "").strip(),
            "grant_seconds": str(row.get("grant_seconds") or "").strip(),
            "required_claim": str(row.get("required_claim") or "").strip(),
            "required_issuer": str(row.get("required_issuer") or "").strip(),
            "required_credentials": list(row.get("required_credentials") or []),
        },
    }
    item = _video_public_item(shaped)
    if not keep_stream and not store.is_video_file(row):
        item["stream_url"] = ""
    return item


async def _kel_gift_balance(config, inception: str) -> float:
    address = (inception or "").strip()
    bu = getattr(config, "BU", None)
    if not address or bu is None:
        return 0.0
    try:
        return float(await bu.get_wallet_balance(address) or 0.0)
    except Exception:
        return 0.0


def _is_follow_branch(relationship) -> bool:
    if not isinstance(relationship, dict):
        return False
    branch = relationship.get("branch")
    if not isinstance(branch, dict):
        return False
    if not (branch.get("prerotated_key_hash") or "").strip():
        return False
    return (branch.get("type") or "").strip().lower() != "livestream"


async def _following_count(config, inception: str) -> int:
    """Branch announcements from this identity."""
    inception = (inception or "").strip()
    if not inception:
        return 0
    db = config.mongo.async_db
    seen = set()

    def _take(txn):
        if not isinstance(txn, dict):
            return
        if (txn.get("inception_public_key_hash") or "").strip() != inception:
            return
        if not _is_follow_branch(txn.get("relationship")):
            return
        tid = (txn.get("id") or "").strip()
        if tid:
            seen.add(tid)

    try:
        cursor = db.blocks.aggregate(
            [
                {
                    "$match": {
                        "transactions.inception_public_key_hash": inception,
                        "transactions.relationship.branch.prerotated_key_hash": {
                            "$gt": ""
                        },
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        "transactions.inception_public_key_hash": inception,
                        "transactions.relationship.branch.prerotated_key_hash": {
                            "$gt": ""
                        },
                    }
                },
                {"$project": {"transactions": 1}},
            ]
        )
        async for doc in cursor:
            _take(doc.get("transactions"))
    except Exception:
        pass
    try:
        async for txn in db.miner_transactions.find(
            {
                "inception_public_key_hash": inception,
                "relationship.branch.prerotated_key_hash": {"$gt": ""},
            },
            {"_id": 0, "id": 1, "inception_public_key_hash": 1, "relationship": 1},
        ):
            _take(txn)
    except Exception:
        pass
    return len(seen)


async def _identity_announcement_txn_id(config, inception: str) -> str:
    """Txn id of the identity announcement for this inception hash."""
    inception = (inception or "").strip()
    if not inception:
        return ""
    db = config.mongo.async_db
    match = {
        "$or": [
            {"transactions.inception_public_key_hash": inception},
            {"transactions.public_key_hash": inception},
        ],
        "transactions.relationship.identity.username": {"$gt": ""},
    }

    def _id(txn):
        if not isinstance(txn, dict):
            return ""
        rel = txn.get("relationship") or {}
        ident = rel.get("identity") if isinstance(rel, dict) else None
        if not isinstance(ident, dict) or not (ident.get("username") or "").strip():
            return ""
        owner = (
            txn.get("inception_public_key_hash") or txn.get("public_key_hash") or ""
        ).strip()
        if owner != inception:
            return ""
        return (txn.get("id") or "").strip()

    try:
        cursor = db.blocks.aggregate(
            [
                {"$match": match},
                {"$unwind": "$transactions"},
                {"$match": match},
                {"$limit": 1},
            ]
        )
        async for doc in cursor:
            found = _id(doc.get("transactions"))
            if found:
                return found
    except Exception:
        pass
    try:
        txn = await db.miner_transactions.find_one(
            {
                "$or": [
                    {"inception_public_key_hash": inception},
                    {"public_key_hash": inception},
                ],
                "relationship.identity.username": {"$gt": ""},
            },
            {
                "_id": 0,
                "id": 1,
                "inception_public_key_hash": 1,
                "public_key_hash": 1,
                "relationship": 1,
            },
        )
    except Exception:
        txn = None
    return _id(txn)


async def _follower_count(config, identity_txn_id: str) -> int:
    """Distinct announcers whose branch points at this identity announcement."""
    identity_txn_id = (identity_txn_id or "").strip()
    if not identity_txn_id:
        return 0
    db = config.mongo.async_db
    announcers = set()

    def _take(txn):
        if not isinstance(txn, dict):
            return
        rel = txn.get("relationship") or {}
        branch = rel.get("branch") if isinstance(rel, dict) else None
        if not isinstance(branch, dict):
            return
        if (branch.get("identity_announcement") or "").strip() != identity_txn_id:
            return
        if (branch.get("type") or "").strip().lower() == "livestream":
            return
        who = (
            txn.get("inception_public_key_hash")
            or txn.get("public_key_hash")
            or txn.get("id")
            or ""
        ).strip()
        if who:
            announcers.add(who)

    chain_match = {
        "transactions.relationship.branch.identity_announcement": identity_txn_id
    }
    try:
        cursor = db.blocks.aggregate(
            [
                {"$match": chain_match},
                {"$unwind": "$transactions"},
                {"$match": chain_match},
                {"$project": {"transactions": 1}},
            ]
        )
        async for doc in cursor:
            _take(doc.get("transactions"))
    except Exception:
        pass
    try:
        async for txn in db.miner_transactions.find(
            {"relationship.branch.identity_announcement": identity_txn_id},
            {
                "_id": 0,
                "id": 1,
                "inception_public_key_hash": 1,
                "public_key_hash": 1,
                "relationship": 1,
            },
        ):
            _take(txn)
    except Exception:
        pass
    return len(announcers)


async def _resolve_public_inception(config, username="", transaction_id="", owner=""):
    inception = ""
    if username:
        inception = await store.inception_for_username(config, username)
    elif transaction_id:
        live = await store.get_live_by_transaction_id(config, transaction_id)
        if live:
            inception = (live.get("owner") or "").strip()
    if not inception:
        inception = (owner or "").strip()
    return inception


async def _profile_payload(config, inception: str, is_me: bool) -> dict:
    ident = await store.identity_for_inception(config, inception)
    username = ident.get("username") or ""
    rows = await store.files_for_inception(config, inception)
    videos = []
    photos = []
    for row in rows:
        if store.is_video_file(row):
            videos.append(_public_file_item(row, username))
        elif store.is_image_file(row):
            photos.append(_public_file_item(row, username, keep_stream=True))
    gifts = await _kel_gift_balance(config, inception)
    following = await _following_count(config, inception)
    identity_txn_id = await _identity_announcement_txn_id(config, inception)
    followers = await _follower_count(config, identity_txn_id)
    signature = await store.username_signature_for_inception(config, inception)
    badges = await store.received_credentials(config, signature)
    return {
        "inception_public_key_hash": inception,
        "username": username,
        "is_me": bool(is_me),
        "gifts": gifts,
        "following": following,
        "followers": followers,
        "badges": len(badges),
        "identity_announcement": identity_txn_id,
        "videos": videos,
        "photos": photos,
    }


class PublicProfileHandler(BaseHandler):
    """GET /file-announcements/api/v1/public/profile — identity plus uploads."""

    async def get(self):
        transaction_id = (self.get_query_argument("transaction_id", "") or "").strip()
        owner = (self.get_query_argument("owner", "") or "").strip()
        username = (self.get_query_argument("username", "") or "").strip()
        inception = await _resolve_public_inception(
            self.config, username, transaction_id, owner
        )
        if not inception:
            self.set_status(404)
            return self.render_as_json(
                {
                    "status": False,
                    "error": (
                        "file announcement not found"
                        if transaction_id
                        else "user not found"
                    ),
                }
            )
        try:
            me = await operator_inception_public_key_hash(self.config)
        except Exception:
            me = ""
        profile = await _profile_payload(
            self.config, inception, bool(me and me == inception)
        )
        return self.render_as_json({"status": True, "profile": profile})


class PublicBadgesHandler(BaseHandler):
    """GET /file-announcements/api/v1/public/badges — received credentials."""

    async def get(self):
        transaction_id = (self.get_query_argument("transaction_id", "") or "").strip()
        owner = (self.get_query_argument("owner", "") or "").strip()
        username = (self.get_query_argument("username", "") or "").strip()
        inception = await _resolve_public_inception(
            self.config, username, transaction_id, owner
        )
        if not inception:
            self.set_status(404)
            return self.render_as_json(
                {
                    "status": False,
                    "error": (
                        "file announcement not found"
                        if transaction_id
                        else "user not found"
                    ),
                }
            )
        ident = await store.identity_for_inception(self.config, inception)
        signature = await store.username_signature_for_inception(self.config, inception)
        badges = await store.received_credentials(self.config, signature)
        return self.render_as_json(
            {
                "status": True,
                "username": ident.get("username") or "",
                "count": len(badges),
                "badges": badges,
            }
        )


def _operator_username(config, profile=None) -> str:
    name = ""
    if isinstance(profile, dict):
        name = (profile.get("username") or "").strip().lstrip("@")
    if not name:
        name = (getattr(config, "username", None) or "").strip().lstrip("@")
    return name


class PublicMeHandler(BaseHandler):
    """GET /file-announcements/api/v1/public/me — operator identity when signed in."""

    async def get(self):
        if not await operator_session_unlocked(self):
            return self.render_as_json(
                {"status": True, "authenticated": False, "profile": None}
            )
        try:
            inception = await operator_inception_public_key_hash(self.config)
        except Exception:
            inception = ""
        profile = None
        if inception:
            profile = await _profile_payload(self.config, inception, True)
        username = _operator_username(self.config, profile)
        return self.render_as_json(
            {
                "status": True,
                "authenticated": True,
                "username": username,
                "profile": profile,
            }
        )


class PublicStreamHandler(BaseHandler):
    """GET /file-announcements/api/v1/public/stream/{backend}/{file_id} — Range streaming."""

    async def options(self, backend=None, file_id=None):
        self.set_status(204)
        self.finish()

    def _media_headers(self, filename, mime_type, total, start, end, partial):
        inline = (
            mime_type.startswith("video/")
            or mime_type.startswith("audio/")
            or mime_type.startswith("image/")
        )
        safe_name = (filename or "file").replace('"', "")
        self.set_header("Content-Type", mime_type)
        self.set_header("Accept-Ranges", "bytes")
        self.set_header("X-Content-Type-Options", "nosniff")
        self.set_header("Cache-Control", "private, max-age=3600")
        self.set_header(
            "Access-Control-Expose-Headers",
            "Content-Type, Content-Length, Content-Range, Accept-Ranges",
        )
        self.set_header(
            "Content-Disposition",
            (
                f'inline; filename="{safe_name}"'
                if inline
                else f'attachment; filename="{safe_name}"'
            ),
        )
        length = end - start + 1
        if partial:
            self.set_status(206)
            self.set_header("Content-Range", f"bytes {start}-{end}/{total}")
        else:
            self.set_status(200)
        self.set_header("Content-Length", str(length))

    async def _write_span(self, read_chunk, start, end):
        remaining = end - start + 1
        try:
            while remaining > 0:
                chunk = await read_chunk(remaining)
                if not chunk:
                    break
                if len(chunk) > remaining:
                    chunk = chunk[:remaining]
                self.write(chunk)
                await self.flush()
                remaining -= len(chunk)
        except StreamClosedError:
            return
        except OSError:
            if not self._finished:
                self.set_status(404)
                self.finish("cache entry unavailable")
            return
        if not self._finished:
            self.finish()

    async def head(self, backend, file_id):
        """Browsers / media stacks sometimes probe with HEAD before Range GET."""
        backend = (backend or "").strip().lower()
        file_id = (file_id or "").strip()
        try:
            live = await assert_live(self.config, backend, file_id)
        except FileAnnouncementServiceError:
            live = None
        if live and await _credential_blocked(self, live, file_id):
            return
        cache_key = f"{backend}:{file_id}"
        _evict_stream_cache()
        entry = _STREAM_CACHE.get(cache_key)
        if entry:
            try:
                live = await assert_live(self.config, backend, file_id)
            except FileAnnouncementServiceError:
                _drop_stream_cache_entry(cache_key)
                self.set_status(404)
                return self.finish("file not found")
            from .service import is_priced_media

            if is_priced_media(live, file_id):
                _drop_stream_cache_entry(cache_key)
                self.set_status(404)
                return self.finish("file not found")
            _tmp, total, _, filename, mime_type = entry
            self._media_headers(filename, mime_type, total, 0, total - 1, False)
            return self.finish()
        filename = self.get_query_argument("filename", "") or ""
        mime_type = self.get_query_argument("mime_type", "") or ""
        try:
            stat = await prepare_public_stream(
                self.config, backend, file_id, filename, mime_type
            )
        except FileAnnouncementServiceError as exc:
            self.set_status(404 if "not found" in str(exc).lower() else 502)
            return self.finish(str(exc))
        total = int(stat["size"])
        if total <= 0:
            self.set_status(404)
            return self.finish("empty")
        self._media_headers(
            stat["filename"], stat["mime_type"], total, 0, total - 1, False
        )
        return self.finish()

    async def get(self, backend, file_id):
        backend = (backend or "").strip().lower()
        file_id = (file_id or "").strip()
        if not backend or not file_id:
            self.set_status(400)
            self.finish("backend and file_id are required")
            return
        try:
            gated = await assert_live(self.config, backend, file_id)
        except FileAnnouncementServiceError:
            gated = None
        if gated and await _credential_blocked(self, gated, file_id):
            return
        cache_key = f"{backend}:{file_id}"
        _evict_stream_cache()
        entry = _STREAM_CACHE.get(cache_key)
        filename = self.get_query_argument("filename", "") or ""
        mime_type = self.get_query_argument("mime_type", "") or ""
        range_header = self.request.headers.get("Range", "")

        if entry and os.path.isfile(entry[0]):
            try:
                live = await assert_live(self.config, backend, file_id)
            except FileAnnouncementServiceError:
                _drop_stream_cache_entry(cache_key)
                self.set_status(404)
                return self.finish("file not found")
            from .service import is_priced_media

            if is_priced_media(live, file_id):
                _drop_stream_cache_entry(cache_key)
                self.set_status(404)
                return self.finish("file not found")
            try:
                await assert_live(self.config, backend, file_id)
            except FileAnnouncementServiceError:
                _drop_stream_cache_entry(cache_key)
                self.set_status(404)
                return self.finish("file not found")
            tmp_path, total, _exp, cached_name, cached_mime = entry
            _STREAM_CACHE[cache_key] = (
                tmp_path,
                total,
                time.monotonic() + _STREAM_CACHE_TTL,
                cached_name,
                cached_mime,
            )
            filename = filename or cached_name
            mime_type = mime_type or cached_mime
            try:
                span = parse_byte_range(range_header, total)
            except ValueError:
                self.set_status(400)
                return self.finish("Invalid Range header")
            if span is None:
                self.set_status(416)
                self.set_header("Content-Range", f"bytes */{total}")
                return self.finish()
            start, end = span
            partial = bool(range_header)
            self._media_headers(filename, mime_type, total, start, end, partial)
            fh = open(tmp_path, "rb")
            fh.seek(start)

            async def read_chunk(remaining, handle=fh):
                return handle.read(min(_STREAM_CHUNK, remaining))

            try:
                await self._write_span(read_chunk, start, end)
            finally:
                fh.close()
            return

        try:
            stat = await prepare_public_stream(
                self.config, backend, file_id, filename, mime_type
            )
        except FileAnnouncementServiceError as exc:
            msg = str(exc)
            self.set_status(404 if "not found" in msg.lower() else 502)
            return self.finish(msg)
        total = int(stat["size"])
        if total <= 0:
            self.set_status(404)
            return self.finish("empty")
        try:
            span = parse_byte_range(range_header, total)
        except ValueError:
            self.set_status(400)
            return self.finish("Invalid Range header")
        if span is None:
            self.set_status(416)
            self.set_header("Content-Range", f"bytes */{total}")
            return self.finish()
        start, end = span
        length = end - start + 1
        try:
            chunks = await open_public_range(
                self.config,
                backend,
                file_id,
                offset=start,
                length=length,
                share_url=stat.get("share_url") or "",
                backend=stat.get("backend"),
            )
        except FileAnnouncementServiceError as exc:
            msg = str(exc)
            self.set_status(404 if "not found" in msg.lower() else 502)
            return self.finish(msg)
        partial = bool(range_header)
        self._media_headers(
            stat["filename"], stat["mime_type"], total, start, end, partial
        )
        agen = chunks.__aiter__()

        async def read_chunk(_remaining, iterator=agen):
            try:
                return await iterator.__anext__()
            except StopAsyncIteration:
                return b""

        try:
            await self._write_span(read_chunk, start, end)
        finally:
            try:
                await chunks.aclose()
            except Exception:
                pass


def write_scroller_index(handler):
    full = os.path.join(DEMO_DIR, "index.html")
    css_path = os.path.join(DEMO_DIR, "styles.css")
    if not os.path.isfile(full):
        handler.set_status(404)
        handler.finish("not found")
        return
    with open(full, encoding="utf-8") as fh:
        html = fh.read()
    if os.path.isfile(css_path):
        with open(css_path, encoding="utf-8") as fh:
            css = fh.read().replace("</style", "<\\/style")
        html = html.replace(
            '<link rel="stylesheet" href="/file-announcements/demo/yadascroller/styles.css" />',
            "<style>\n" + css + "\n</style>",
        )
    handler.set_header("Cache-Control", "no-store")
    handler.set_header("Content-Type", "text/html; charset=UTF-8")
    handler.write(html.encode("utf-8"))
    handler.finish()


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


PPV_INVOICE_COOKIE = "yada_ppv_invoice"


def _invoice_tokens(handler) -> list:
    raw = handler.get_secure_cookie(PPV_INVOICE_COOKIE)
    if not raw:
        return []
    try:
        text = raw.decode()
    except AttributeError:
        text = str(raw)
    return [part for part in text.split(",") if part][-8:]


def _remember_invoice(handler, token: str) -> None:
    tokens = [part for part in _invoice_tokens(handler) if part != token]
    tokens.append(token)
    handler.set_secure_cookie(PPV_INVOICE_COOKIE, ",".join(tokens[-8:]), expires_days=7)


async def _creator_username_signature(handler, live) -> str:
    username = str((live or {}).get("username") or "").strip().lstrip("@")
    if not username:
        owner = str((live or {}).get("owner") or "").strip()
        if owner:
            try:
                names = await store.identity_usernames(handler.config)
            except Exception:
                names = {}
            username = str(names.get(owner) or "").strip().lstrip("@")
    if not username:
        return ""
    try:
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        found = await IdentityAnnouncement.get_by_username(username)
    except Exception:
        return ""
    return str(((found or {}).get("identity") or {}).get("username_signature") or "")


_STREAM_HOME = {}
_STREAM_HOME_TTL = 600.0


def _stream_home_get(transaction_id: str) -> str:
    hit = _STREAM_HOME.get(transaction_id or "")
    if not hit or hit[1] <= time.time():
        _STREAM_HOME.pop(transaction_id or "", None)
        return ""
    return hit[0]


def _stream_home_put(transaction_id: str, base: str) -> None:
    base = (base or "").rstrip("/")
    if transaction_id and base:
        _STREAM_HOME[transaction_id] = (base, time.time() + _STREAM_HOME_TTL)


def _stream_home_drop(transaction_id: str) -> None:
    _STREAM_HOME.pop(transaction_id or "", None)


def config_http_bases(username: str, config_dir: str) -> list:
    """Loopback web ports of local configs whose username is the announcer."""
    wanted = str(username or "").strip().lstrip("@").lower()
    if not wanted or not config_dir:
        return []
    found = []
    try:
        names = os.listdir(config_dir)
    except OSError:
        return []
    for name in names:
        if not name.endswith(".json"):
            continue
        path = os.path.join(config_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        got = str(data.get("username") or "").strip().lstrip("@").lower()
        if got != wanted:
            continue
        try:
            port = int(data.get("web_server_port") or 0)
        except (TypeError, ValueError):
            continue
        if not 1 <= port <= 65535:
            continue
        host = str(data.get("peer_host") or "127.0.0.1").strip()
        if host in ("", "0.0.0.0", "::"):
            host = "127.0.0.1"
        found.append(f"http://{host}:{port}")
    return found


async def _creator_username(handler, live) -> str:
    username = str((live or {}).get("username") or "").strip().lstrip("@")
    if username:
        return username
    owner = str((live or {}).get("owner") or "").strip()
    if not owner:
        return ""
    try:
        names = await store.identity_usernames(handler.config)
    except Exception:
        return ""
    return str((names or {}).get(owner) or "").strip().lstrip("@")


async def _purchase_homes(handler, live) -> list:
    homes = []
    seen = set()
    this = ""
    try:
        this = (
            (
                (handler.request.protocol or "http")
                + "://"
                + (handler.request.host or "")
            )
            .rstrip("/")
            .lower()
        )
    except Exception:
        this = ""

    def add(base: str) -> None:
        base = (base or "").rstrip("/")
        if not base or base.lower() == this:
            return
        key = base.lower()
        if key in seen:
            return
        seen.add(key)
        homes.append(base)

    username = await _creator_username(handler, live)
    try:
        from plugins.passwordrotation.auth_session import password_home_bases

        sig = await _creator_username_signature(handler, live)
        for base in await password_home_bases(sig, handler, tested_limit=6):
            add(base)
        from .relay import connected_creator_streams

        for stream in connected_creator_streams(handler.config, username, sig):
            peer = getattr(stream, "peer", None)
            host = getattr(peer, "http_host", None) or getattr(peer, "host", None)
            port = getattr(peer, "http_port", None)
            if host and port:
                add(f"http://{host}:{port}")
    except Exception:
        pass
    return homes


def _paid_body(handler, live, redeemed) -> dict:
    return {
        "status": True,
        "paid": True,
        "access": (redeemed or {}).get("access") or "",
        "payment_id": (redeemed or {}).get("payment_id") or "",
        "holds_media": True,
    }


def _grant_seconds(live) -> str:
    return str((live or {}).get("grant_seconds") or "").strip()


def _expired_body() -> dict:
    return {
        "status": True,
        "paid": False,
        "expired": True,
        "error": purchase.EXPIRED_ERROR,
    }


async def _access_for_amount(
    handler, announcement_id: str, pay_to: str, amount: str, grant_seconds=""
):
    payment = await purchase.find_exact_payment(handler.config, pay_to, amount)
    if not payment:
        return None
    return purchase.issue_access(
        handler.config,
        announcement_id,
        payment.get("id") or "",
        grant_seconds,
    )


async def _paid_invoice(handler, transaction_id: str, grant_seconds=""):
    """A browser invoice is paid when its exact amount is in the mempool or on chain."""
    for token in _invoice_tokens(handler):
        try:
            redeemed = await purchase.redeem_invoice(
                handler.config, token, transaction_id, grant_seconds
            )
        except purchase.AccessExpired:
            raise
        except Exception:
            redeemed = None
        if redeemed:
            return redeemed
    return None


async def _session_payer_ids(handler) -> set:
    if not await operator_session_unlocked(handler):
        return set()
    ids = set()
    addr = str(getattr(handler.config, "address", "") or "").strip()
    if addr:
        ids.add(addr)
    try:
        inception = await operator_inception_public_key_hash(handler.config)
    except Exception:
        inception = ""
    if inception:
        ids.add(inception)
    return ids


class PublicPurchaseInvoiceHandler(BaseHandler):
    """POST /file-announcements/api/v1/public/purchase/invoice"""

    async def post(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            self.set_status(400)
            return self.render_as_json({"status": False, "error": str(exc)})
        transaction_id = (data.get("transaction_id") or "").strip()
        if not transaction_id:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "error": "transaction_id is required"}
            )
        live = await store.get_live_by_transaction_id(self.config, transaction_id)
        if not live:
            self.set_status(404)
            return self.render_as_json({"status": False, "error": "file not found"})
        price = str(live.get("price") or "").strip()
        pay_to = str(live.get("public_key_hash") or "").strip()
        if not price or not pay_to:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "error": "post is not for sale"}
            )
        direct = self.request.headers.get("X-Yada-Ppv-Direct") == "1"
        try:
            doc = await purchase.create_invoice(
                self.config, transaction_id, pay_to, price
            )
        except ValueError as exc:
            self.set_status(400)
            return self.render_as_json({"status": False, "error": str(exc)})
        if not direct:
            _remember_invoice(self, doc["token"])
        body = {
            "status": True,
            "amount": doc["amount"],
            "pay_to": pay_to,
            "price": price,
            "expires_at": doc["expires_at"],
        }
        if direct:
            body["token"] = doc["token"]
        return self.render_as_json(body)


class PublicPurchaseRedeemHandler(BaseHandler):
    """POST /file-announcements/api/v1/public/purchase/redeem"""

    async def post(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            self.set_status(400)
            return self.render_as_json({"status": False, "error": str(exc)})
        transaction_id = (data.get("transaction_id") or "").strip()
        if not transaction_id:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "error": "transaction_id is required"}
            )
        live = await store.get_live_by_transaction_id(self.config, transaction_id)
        if not live:
            self.set_status(404)
            return self.render_as_json({"status": False, "error": "file not found"})
        direct = self.request.headers.get("X-Yada-Ppv-Direct") == "1"
        tokens = [data.get("token") or ""] if direct else _invoice_tokens(self)
        tokens = [token for token in tokens if token]
        pay_to = str(live.get("public_key_hash") or "").strip()
        grant_seconds = _grant_seconds(live)
        redeemed = None
        echoed = ""
        expired = False
        for token in tokens:
            try:
                redeemed = await purchase.redeem_invoice(
                    self.config, token, transaction_id, grant_seconds
                )
            except purchase.AccessExpired:
                expired = True
                redeemed = None
                continue
            if redeemed:
                break
            doc = await purchase.invoice_for_token(self.config, token)
            if (
                doc
                and doc.get("announcement_id") == transaction_id
                and not doc.get("redeemed_at")
            ):
                echoed = doc.get("amount") or echoed
        if redeemed:
            return self.render_as_json(_paid_body(self, live, redeemed))
        if not redeemed and echoed:
            issued = await _access_for_amount(
                self, transaction_id, pay_to, echoed, grant_seconds
            )
            if issued:
                return self.render_as_json(_paid_body(self, live, issued))
        if tokens and not direct:
            try:
                claimed = await purchase.claim_unique_invoice_payment(
                    self.config,
                    transaction_id,
                    pay_to,
                    str(live.get("price") or ""),
                    grant_seconds,
                )
            except purchase.AccessExpired:
                expired = True
                claimed = None
            if claimed:
                return self.render_as_json(_paid_body(self, live, claimed))
        if expired:
            return self.render_as_json(_expired_body())
        body = {
            "status": True,
            "paid": False,
            "error": "no payment in the mempool or on chain for this checkout yet",
        }
        if echoed:
            body["amount"] = echoed
            body["pay_to"] = pay_to
        return self.render_as_json(body)


class PublicPurchaseHandler(BaseHandler):
    """GET /file-announcements/api/v1/public/purchase?transaction_id="""

    async def get(self):
        transaction_id = (self.get_query_argument("transaction_id", "") or "").strip()
        if not transaction_id:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "error": "transaction_id is required"}
            )
        live = await store.get_live_by_transaction_id(self.config, transaction_id)
        if not live:
            self.set_status(404)
            return self.render_as_json(
                {"status": False, "error": "file not found", "paid": False}
            )
        price = str(live.get("price") or "").strip()
        pay_to = str(live.get("public_key_hash") or "").strip()
        try:
            redeemed = await _paid_invoice(self, transaction_id, _grant_seconds(live))
        except purchase.AccessExpired:
            return self.render_as_json(_expired_body())
        if redeemed:
            return self.render_as_json(
                {
                    "status": True,
                    "paid": True,
                    "payment_id": redeemed.get("payment_id") or "",
                    "access": redeemed.get("access") or "",
                    "price": price,
                    "pay_to": pay_to,
                    "holds_media": paidstore.has(
                        self.config, live.get("file_id") or ""
                    ),
                }
            )
        payers = await _session_payer_ids(self)
        if not payers:
            self.set_status(401)
            return self.render_as_json(
                {"status": False, "error": "not authorized", "paid": False}
            )
        if not price:
            return self.render_as_json(
                {
                    "status": True,
                    "paid": True,
                    "price": "",
                    "pay_to": pay_to,
                    "holds_media": True,
                }
            )
        payment = await purchase.find_confirmed_payment(
            self.config, pay_to, price, payers
        )
        return self.render_as_json(
            {
                "status": True,
                "paid": bool(payment),
                "payment_id": (payment or {}).get("id") or "",
                "price": price,
                "pay_to": pay_to,
                "holds_media": paidstore.has(self.config, live.get("file_id") or ""),
            }
        )


class PublicPurchaseStreamHandler(BaseHandler):
    """GET /file-announcements/api/v1/public/purchase/stream/{transaction_id}"""

    async def get(self, transaction_id):
        transaction_id = (transaction_id or "").strip()
        access = (self.get_query_argument("access", "") or "").strip()
        live = await store.get_live_by_transaction_id(self.config, transaction_id)
        if not live:
            self.set_status(404)
            return self.finish("file not found")
        price = str(live.get("price") or "").strip()
        pay_to = str(live.get("public_key_hash") or "").strip()
        file_id = str(live.get("file_id") or "").strip()
        if not price or not pay_to:
            self.set_status(404)
            return self.finish("file not found")
        holds = paidstore.has(self.config, file_id)
        payment_id = (
            (self.get_query_argument("payment_id", "") or "").split("?")[0].strip()
        )
        payment = None
        local_access = purchase.access_token_ok(self.config, transaction_id, access)
        if access:
            try:
                saved = await self.config.mongo.async_db[purchase.INVOICES].find_one(
                    {"access": access, "announcement_id": transaction_id},
                    {"payment_id": 1},
                )
            except Exception:
                saved = None
            if saved and saved.get("payment_id"):
                payment_id = str(saved.get("payment_id") or "")
        if payment_id:
            named = await purchase.payment_by_id(self.config, payment_id)
            if (
                named
                and purchase.output_pays(named, pay_to, price)
                and not await purchase.payment_grant_elapsed(
                    self.config, transaction_id, payment_id, _grant_seconds(live)
                )
            ):
                local_access = True
                payment = named
        payers = await _session_payer_ids(self)
        grant_pub = (self.get_query_argument("grant_pub", "") or "").strip()
        if grant_pub:
            payment = await purchase.find_payment_from_key(
                self.config, pay_to, price, grant_pub
            )
            grant = {
                "message": f"yada-ppv|{transaction_id}|{self.get_query_argument('grant_exp', '')}",
                "signature": self.get_query_argument("grant_sig", "") or "",
                "public_key": grant_pub,
                "exp": self.get_query_argument("grant_exp", "") or "",
            }
            if payment and purchase.view_grant_ok(transaction_id, grant, payment):
                local_access = True
        if not local_access and payers:
            payment = await purchase.find_confirmed_payment(
                self.config, pay_to, price, payers
            )
            local_access = bool(payment)
        if not local_access:
            try:
                redeemed = await _paid_invoice(
                    self, transaction_id, _grant_seconds(live)
                )
            except purchase.AccessExpired:
                self.set_status(402)
                return self.finish(purchase.EXPIRED_ERROR)
            if redeemed:
                local_access = True
                if not payment_id:
                    payment_id = str(redeemed.get("payment_id") or "")
                if payment_id and not payment:
                    payment = await purchase.payment_by_id(self.config, payment_id)
        if not holds:
            if not local_access:
                self.set_status(402)
                if purchase.access_token_expired(
                    access
                ) or await purchase.payment_grant_elapsed(
                    self.config, transaction_id, payment_id, _grant_seconds(live)
                ):
                    return self.finish(purchase.EXPIRED_ERROR)
                return self.finish("payment required")
            if await _credential_blocked(self, live, file_id):
                return
            if await self._serve_connected(live, transaction_id, payment_id):
                return
            direct = self.request.headers.get("X-Yada-Ppv-Direct") == "1"
            if direct or not payment_id:
                self.set_status(404)
                return self.finish("file not found")
            return await self._proxy_homes(transaction_id, payment_id)
        if not local_access:
            self.set_status(402)
            if purchase.access_token_expired(
                access
            ) or await purchase.payment_grant_elapsed(
                self.config, transaction_id, payment_id, _grant_seconds(live)
            ):
                return self.finish(purchase.EXPIRED_ERROR)
            return self.finish("payment required")
        if await _credential_blocked(self, live, file_id):
            return
        info = paidstore.meta(self.config, file_id)
        total = int(info.get("size") or 0)
        if total <= 0:
            self.set_status(404)
            return self.finish("empty")
        try:
            span = parse_byte_range(self.request.headers.get("Range", ""), total)
        except ValueError:
            span = None
        if not span:
            self.set_status(416)
            self.set_header("Content-Range", f"bytes */{total}")
            return self.finish()
        start, end = span
        mime = (
            info.get("mime_type") or live.get("mime_type") or "application/octet-stream"
        )
        filename = info.get("filename") or live.get("filename") or "video"
        length = end - start + 1
        partial = not (start == 0 and end == total - 1)
        self.set_header("Accept-Ranges", "bytes")
        self.set_header("Cache-Control", "private, no-store")
        self.set_header("Content-Type", mime)
        self.set_header("Content-Length", str(length))
        self.set_header("Content-Disposition", f'inline; filename="{filename}"')
        if partial:
            self.set_status(206)
            self.set_header("Content-Range", f"bytes {start}-{end}/{total}")
        fh = paidstore.open_file(self.config, file_id)
        if fh is None:
            self.set_status(404)
            return self.finish("file not found")
        try:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                self.write(chunk)
                await self.flush()
        except StreamClosedError:
            return
        finally:
            fh.close()
        return self.finish()

    async def _serve_connected(self, live, transaction_id, payment_id):
        from .relay import CHUNK, pull_chunk

        if not payment_id:
            return False
        sig = await _creator_username_signature(self, live)
        username = str((live or {}).get("username") or "").strip().lstrip("@")
        if not username:
            owner = str((live or {}).get("owner") or "").strip()
            if owner:
                try:
                    names = await store.identity_usernames(self.config)
                except Exception:
                    names = {}
                username = str(names.get(owner) or "").strip().lstrip("@")
        total = int((live or {}).get("size") or 0)
        vp = _presented_vp(self)
        probe = await pull_chunk(
            self.config, username, sig, transaction_id, payment_id, 0, 1, vp=vp
        )
        if probe is None:
            return False
        if total <= 0:
            info_size = await pull_chunk(
                self.config, username, sig, transaction_id, payment_id, 0, 1, vp=vp
            )
            total = 0
        str((live or {}).get("file_id") or "")
        try:
            span = parse_byte_range(self.request.headers.get("Range", ""), total or 1)
        except ValueError:
            span = None
        if total <= 0:
            self.set_status(404)
            self.finish("empty")
            return True
        if not span:
            self.set_status(416)
            self.set_header("Content-Range", f"bytes */{total}")
            self.finish()
            return True
        start, end = span
        mime = (live or {}).get("mime_type") or "application/octet-stream"
        filename = (live or {}).get("filename") or "video"
        length = end - start + 1
        partial = not (start == 0 and end == total - 1)
        self.set_header("Accept-Ranges", "bytes")
        self.set_header("Cache-Control", "private, no-store")
        self.set_header("Content-Type", mime)
        self.set_header("Content-Length", str(length))
        self.set_header("Content-Disposition", f'inline; filename="{filename}"')
        if partial:
            self.set_status(206)
            self.set_header("Content-Range", f"bytes {start}-{end}/{total}")
        pos = start
        try:
            while pos <= end:
                raw = await pull_chunk(
                    self.config,
                    username,
                    sig,
                    transaction_id,
                    payment_id,
                    pos,
                    min(CHUNK, end - pos + 1),
                    vp=vp,
                )
                if not raw:
                    break
                self.write(raw)
                await self.flush()
                pos += len(raw)
        except StreamClosedError:
            return True
        self.finish()
        return True

    def _write_proxied(self, resp):
        self.set_status(resp.code)
        self.set_header("Cache-Control", "private, no-store")
        for name in (
            "Content-Type",
            "Content-Length",
            "Content-Range",
            "Accept-Ranges",
        ):
            value = resp.headers.get(name)
            if value:
                self.set_header(name, value)
        self.write(resp.body)
        self.finish()

    async def _fetch_purchase_stream(
        self, home, transaction_id, payment_id, probe=False, vp=""
    ):
        from tornado.httpclient import AsyncHTTPClient, HTTPClientError, HTTPRequest

        url = (
            home.rstrip("/")
            + "/file-announcements/api/v1/public/purchase/stream/"
            + quote(transaction_id, safe="")
            + "?payment_id="
            + quote(payment_id, safe="")
        )
        headers = {"X-Yada-Ppv-Direct": "1"}
        if vp:
            headers["X-Yada-VP"] = vp
        if probe:
            headers["Range"] = "bytes=0-0"
            request_timeout = 4
        else:
            range_header = self.request.headers.get("Range", "")
            if range_header:
                headers["Range"] = range_header
            request_timeout = 25
        try:
            return await AsyncHTTPClient().fetch(
                HTTPRequest(
                    url,
                    headers=headers,
                    connect_timeout=2,
                    request_timeout=request_timeout,
                )
            )
        except HTTPClientError as exc:
            response = getattr(exc, "response", None)
            if getattr(exc, "code", 0) == 403 and response is not None:
                return response
            return None
        except Exception:
            return None

    async def _first_stream_home(self, homes, transaction_id, payment_id, vp=""):
        tasks = [
            asyncio.create_task(
                self._fetch_purchase_stream(
                    home, transaction_id, payment_id, probe=True, vp=vp
                )
            )
            for home in homes
        ]
        pending = set(tasks)
        found = ""
        try:
            while pending and not found:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    resp = task.result()
                    if resp is None or (resp.code >= 400 and resp.code != 403):
                        continue
                    found = homes[tasks.index(task)]
                    break
        finally:
            if found:

                async def _drop():
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

                asyncio.get_running_loop().create_task(_drop())
            else:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        return found

    async def _proxy_homes(self, transaction_id, payment_id):
        live = await store.get_live_by_transaction_id(self.config, transaction_id)
        vp = _presented_vp(self)
        cached = _stream_home_get(transaction_id)
        if cached:
            resp = await self._fetch_purchase_stream(
                cached, transaction_id, payment_id, vp=vp
            )
            if resp is not None and resp.code == 403:
                self.set_status(403)
                return self.finish("credential required")
            if resp is not None and resp.code < 400:
                _stream_home_put(transaction_id, cached)
                return self._write_proxied(resp)
            _stream_home_drop(transaction_id)

        homes = [
            home
            for home in await _purchase_homes(self, live)
            if home.rstrip("/") != (cached or "").rstrip("/")
        ][:8]
        home = await self._first_stream_home(homes, transaction_id, payment_id, vp)
        if not home:
            self.set_status(404)
            return self.finish("file not found")
        resp = await self._fetch_purchase_stream(
            home, transaction_id, payment_id, vp=vp
        )
        if resp is not None and resp.code == 403:
            self.set_status(403)
            return self.finish("credential required")
        if resp is None or resp.code >= 400:
            self.set_status(404)
            return self.finish("file not found")
        _stream_home_put(transaction_id, home)
        return self._write_proxied(resp)

    async def _proxy_creator(
        self, home, transaction_id, access, payment, payment_id=""
    ):
        from tornado.httpclient import AsyncHTTPClient, HTTPClientError

        query = ""
        if payment_id:
            query = "?payment_id=" + quote(payment_id, safe="")
        elif access:
            query = "?access=" + quote(access, safe="")
        elif payment:
            exp = int(time.time()) + 300
            grant = purchase.view_grant(self.config, transaction_id, exp)
            if not purchase.view_grant_ok(transaction_id, grant, payment):
                self.set_status(401)
                return self.finish("not authorized")
            query = (
                "?grant_exp="
                + quote(str(grant["exp"]), safe="")
                + "&grant_sig="
                + quote(grant["signature"], safe="")
                + "&grant_pub="
                + quote(grant["public_key"], safe="")
            )
        url = (
            home.rstrip("/")
            + "/file-announcements/api/v1/public/purchase/stream/"
            + quote(transaction_id, safe="")
            + query
        )
        headers = {"X-Yada-Ppv-Direct": "1"}
        vp = _presented_vp(self)
        if vp:
            headers["X-Yada-VP"] = vp
        range_header = self.request.headers.get("Range", "")
        if range_header:
            headers["Range"] = range_header
        try:
            resp = await AsyncHTTPClient().fetch(
                url, headers=headers, request_timeout=120
            )
        except HTTPClientError:
            return False
        except Exception:
            return False
        self.set_status(resp.code)
        self.set_header("Cache-Control", "private, no-store")
        for name in (
            "Content-Type",
            "Content-Length",
            "Content-Range",
            "Accept-Ranges",
        ):
            value = resp.headers.get(name)
            if value:
                self.set_header(name, value)
        self.write(resp.body)
        self.finish()
        return True


HANDLERS = [
    (r"/file-announcements", FileAnnouncementDashboardHandler),
    (r"/file-announcements/api/v1/unlock", FileAnnouncementUnlockHandler),
    (r"/file-announcements/api/v1/files", FileListHandler),
    (r"/file-announcements/api/v1/uploads/([^/]+)", FileUploadProgressHandler),
    (r"/file-announcements/api/v1/files/search", FileSearchHandler),
    (r"/file-announcements/api/v1/files/(.+)/takedown", FileTakedownHandler),
    (r"/file-announcements/api/v1/files/(.+)/download", FileDownloadHandler),
    (r"/file-announcements/api/v1/files/(.+)", FileDetailHandler),
    (r"/file-announcements/api/v1/history", FileHistoryHandler),
    (r"/file-announcements/api/v1/settings", FileSettingsHandler),
    (r"/file-announcements/api/v1/backends", FileBackendsHandler),
    (r"/file-announcements/api/v1/stream-cache", StreamCacheHandler),
    (r"/file-announcements/api/v1/takedown-reasons", FileTakedownReasonsHandler),
    (
        r"/file-announcements/api/v1/public/purchase/invoice",
        PublicPurchaseInvoiceHandler,
    ),
    (
        r"/file-announcements/api/v1/public/purchase/redeem",
        PublicPurchaseRedeemHandler,
    ),
    (r"/file-announcements/api/v1/public/purchase", PublicPurchaseHandler),
    (
        r"/file-announcements/api/v1/public/purchase/stream/([^/]+)",
        PublicPurchaseStreamHandler,
    ),
    (r"/file-announcements/api/v1/public/videos", PublicVideoListHandler),
    (r"/file-announcements/api/v1/public/photos", PublicPhotoListHandler),
    (r"/file-announcements/api/v1/public/profile", PublicProfileHandler),
    (r"/file-announcements/api/v1/public/badges", PublicBadgesHandler),
    (r"/file-announcements/api/v1/public/me", PublicMeHandler),
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
