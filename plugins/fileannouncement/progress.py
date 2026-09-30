"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import re
import threading
import time

_LOCK = threading.Lock()
_UPLOADS = {}
_TTL = 3600
_ID = re.compile(r"^[A-Za-z0-9_-]{8,80}$")


def valid_id(upload_id) -> bool:
    return bool(_ID.fullmatch(str(upload_id or "")))


def _evict(now):
    for key in list(_UPLOADS):
        if now - _UPLOADS[key]["updated"] > _TTL:
            del _UPLOADS[key]


def begin(upload_id, filename="", size=0) -> bool:
    if not valid_id(upload_id):
        return False
    now = time.monotonic()
    with _LOCK:
        _evict(now)
        _UPLOADS[upload_id] = {
            "upload_id": upload_id,
            "phase": "receiving",
            "filename": filename or "",
            "size": int(size or 0),
            "shards": 0,
            "shard_bytes": 0,
            "shard_index": 0,
            "slab_index": 0,
            "error": "",
            "ok": None,
            "updated": now,
        }
    return True


def apply(upload_id, event) -> None:
    if not valid_id(upload_id) or not isinstance(event, dict):
        return
    with _LOCK:
        row = _UPLOADS.get(upload_id)
        if not row:
            return
        phase = event.get("phase")
        if phase:
            row["phase"] = str(phase)
        if "shard_size" in event:
            row["shards"] += 1
            row["shard_bytes"] += int(event.get("shard_size") or 0)
            row["shard_index"] = int(event.get("shard_index") or 0)
            row["slab_index"] = int(event.get("slab_index") or 0)
            row["phase"] = "sia"
        row["updated"] = time.monotonic()


def finish(upload_id, ok=True, error="") -> None:
    if not valid_id(upload_id):
        return
    with _LOCK:
        row = _UPLOADS.get(upload_id)
        if not row:
            return
        row["ok"] = bool(ok)
        row["error"] = error or ""
        row["phase"] = "done" if ok else "error"
        row["updated"] = time.monotonic()


def snapshot(upload_id) -> dict:
    upload_id = str(upload_id or "")
    pending = {
        "upload_id": upload_id,
        "phase": "pending",
        "shards": 0,
        "shard_bytes": 0,
        "ok": None,
        "error": "",
    }
    if not valid_id(upload_id):
        return pending
    now = time.monotonic()
    with _LOCK:
        _evict(now)
        row = _UPLOADS.get(upload_id)
        if not row:
            return pending
        return {
            "upload_id": row["upload_id"],
            "phase": row["phase"],
            "filename": row["filename"],
            "size": row["size"],
            "shards": row["shards"],
            "shard_bytes": row["shard_bytes"],
            "shard_index": row["shard_index"],
            "slab_index": row["slab_index"],
            "error": row["error"],
            "ok": row["ok"],
        }
