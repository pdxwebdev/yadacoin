"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import re
import time
import uuid
from typing import Optional

from yadacoin.core.fileannouncement import FileAnnouncement

FILES_COLLECTION = "file_announcements"
HISTORY_COLLECTION = "file_upload_history"
SETTINGS_COLLECTION = "file_announcement_settings"
SETTINGS_ID = "default"


def _db(config):
    return config.mongo.async_db


def _now():
    return int(time.time())


def new_record_id() -> str:
    return uuid.uuid4().hex


def record_from_announcement(
    ann: FileAnnouncement,
    record_id: str = "",
    transaction_id: str = "",
    status: str = "announced",
) -> dict:
    return {
        "record_id": record_id or new_record_id(),
        "backend": ann.backend,
        "file_id": ann.file_id,
        "title": ann.title,
        "description": ann.description,
        "keywords": list(ann.keywords),
        "filename": ann.filename,
        "mime_type": ann.mime_type,
        "size": ann.size,
        "supersedes": ann.supersedes,
        "transaction_id": transaction_id,
        "status": status,
        "created_at": _now(),
        "updated_at": _now(),
    }


def public_record(doc: dict) -> dict:
    if not doc:
        return {}
    out = dict(doc)
    out.pop("_id", None)
    return out


async def get_settings(config) -> dict:
    doc = await _db(config)[SETTINGS_COLLECTION].find_one({"_id": SETTINGS_ID})
    if not doc:
        return {
            "backend": "sia",
            "sia_app_key": getattr(config, "sia_app_key", "") or "",
            "sia_indexer_url": "https://sia.storage",
        }
    doc.pop("_id", None)
    if not doc.get("sia_app_key"):
        doc["sia_app_key"] = getattr(config, "sia_app_key", "") or ""
    return doc


async def save_settings(config, data: dict) -> dict:
    current = await get_settings(config)
    if "backend" in data and data["backend"]:
        current["backend"] = str(data["backend"]).strip().lower()
    if "sia_app_key" in data:
        current["sia_app_key"] = str(data["sia_app_key"] or "").strip()
    if "sia_indexer_url" in data and data["sia_indexer_url"]:
        current["sia_indexer_url"] = str(data["sia_indexer_url"]).strip()
    await _db(config)[SETTINGS_COLLECTION].update_one(
        {"_id": SETTINGS_ID},
        {"$set": current},
        upsert=True,
    )
    return current


async def insert_file(config, record: dict) -> dict:
    record = dict(record)
    record.setdefault("record_id", new_record_id())
    record.setdefault("created_at", _now())
    record["updated_at"] = _now()
    await _db(config)[FILES_COLLECTION].insert_one(record)
    return public_record(record)


async def update_file(config, record_id: str, fields: dict) -> Optional[dict]:
    fields = dict(fields)
    fields["updated_at"] = _now()
    await _db(config)[FILES_COLLECTION].update_one(
        {"record_id": record_id}, {"$set": fields}
    )
    return await get_file(config, record_id)


async def get_file(config, record_id: str) -> Optional[dict]:
    doc = await _db(config)[FILES_COLLECTION].find_one(
        {"record_id": record_id}, {"_id": 0}
    )
    return doc


async def get_file_by_file_id(config, file_id: str) -> Optional[dict]:
    doc = await _db(config)[FILES_COLLECTION].find_one({"file_id": file_id}, {"_id": 0})
    return doc


async def get_file_by_transaction_id(config, transaction_id: str) -> Optional[dict]:
    tid = (transaction_id or "").strip()
    if not tid:
        return None
    doc = await _db(config)[FILES_COLLECTION].find_one(
        {"transaction_id": tid}, {"_id": 0}
    )
    return doc


async def delete_file(config, record_id: str) -> bool:
    result = await _db(config)[FILES_COLLECTION].delete_one({"record_id": record_id})
    return bool(getattr(result, "deleted_count", 0))


def _search_filter(query: str, extra: Optional[dict] = None) -> dict:
    filt = dict(extra or {})
    q = (query or "").strip()
    if not q:
        return filt
    escaped = re.escape(q)
    regex = {"$regex": escaped, "$options": "i"}
    filt["$or"] = [
        {"title": regex},
        {"description": regex},
        {"keywords": regex},
        {"file_id": regex},
        {"filename": regex},
        {"transaction_id": regex},
    ]
    return filt


async def list_files(
    config,
    query: str = "",
    status: str = "",
    limit: int = 100,
    skip: int = 0,
) -> list:
    extra = {}
    if status:
        extra["status"] = status
    filt = _search_filter(query, extra)
    cursor = (
        _db(config)[FILES_COLLECTION]
        .find(filt, {"_id": 0})
        .sort([("updated_at", -1)])
        .skip(int(skip))
        .limit(int(limit))
    )
    return await cursor.to_list(length=int(limit))


async def add_history(config, entry: dict) -> dict:
    entry = dict(entry)
    entry.setdefault("timestamp", _now())
    entry.setdefault("history_id", new_record_id())
    await _db(config)[HISTORY_COLLECTION].insert_one(entry)
    return public_record(entry)


async def list_history(
    config,
    query: str = "",
    record_id: str = "",
    limit: int = 200,
    skip: int = 0,
) -> list:
    extra = {}
    if record_id:
        extra["record_id"] = record_id
    filt = _search_filter(query, extra)
    cursor = (
        _db(config)[HISTORY_COLLECTION]
        .find(filt, {"_id": 0})
        .sort([("timestamp", -1)])
        .skip(int(skip))
        .limit(int(limit))
    )
    return await cursor.to_list(length=int(limit))


VIDEO_EXT_RE = re.compile(r"\.(mp4|webm|mov|m4v|mkv|ogv)$", re.I)
VIDEO_MIME_RE = re.compile(r"^video/", re.I)


def is_video_file(file_doc: dict) -> bool:
    """True when announcement metadata indicates video content."""
    if not file_doc:
        return False
    mime = (file_doc.get("mime_type") or "").strip()
    if VIDEO_MIME_RE.match(mime):
        return True
    filename = file_doc.get("filename") or ""
    if VIDEO_EXT_RE.search(filename):
        return True
    return False


def _text_match_clauses(prefix: str, regex):
    return [
        {f"{prefix}.title": regex},
        {f"{prefix}.description": regex},
        {f"{prefix}.keywords": regex},
        {f"{prefix}.file_id": regex},
        {f"{prefix}.filename": regex},
    ]


def _video_match_clauses(prefix: str):
    return [
        {f"{prefix}.mime_type": {"$regex": r"^video/", "$options": "i"}},
        {
            f"{prefix}.filename": {
                "$regex": r"\.(mp4|webm|mov|m4v|mkv|ogv)$",
                "$options": "i",
            }
        },
    ]


async def search_chain(config, query: str, limit: int = 50) -> list:
    """Search confirmed + mempool file announcements by title/description/keywords/file_id."""
    q = (query or "").strip()
    escaped = re.escape(q) if q else None
    regex = {"$regex": escaped, "$options": "i"} if escaped else {"$exists": True}
    match = {"$or": _text_match_clauses("transactions.relationship.file", regex)}
    results = []
    pipeline = [
        {"$match": match},
        {"$unwind": "$transactions"},
        {
            "$match": {
                "$or": _text_match_clauses("transactions.relationship.file", regex)
            }
        },
        {"$sort": {"index": -1}},
        {"$limit": int(limit)},
        {
            "$project": {
                "_id": 0,
                "block_index": "$index",
                "transaction": "$transactions",
            }
        },
    ]
    try:
        async for doc in _db(config).blocks.aggregate(pipeline):
            txn = doc.get("transaction") or {}
            rel = (txn.get("relationship") or {}).get("file") or {}
            results.append(
                {
                    "source": "chain",
                    "block_index": doc.get("block_index"),
                    "transaction_id": txn.get("id"),
                    "file": rel,
                }
            )
    except Exception:
        pass

    mem_filt = {"$or": _text_match_clauses("relationship.file", regex)}
    try:
        async for txn in (
            _db(config)
            .miner_transactions.find(mem_filt, {"_id": 0})
            .sort([("time", -1)])
            .limit(int(limit))
        ):
            rel = (txn.get("relationship") or {}).get("file") or {}
            results.append(
                {
                    "source": "mempool",
                    "block_index": None,
                    "transaction_id": txn.get("id"),
                    "file": rel,
                }
            )
    except Exception:
        pass
    return results


async def search_videos(
    config, query: str = "", limit: int = 50, skip: int = 0
) -> list:
    """Discover video file announcements from local index, chain, and mempool."""
    limit = max(1, min(int(limit), 200))
    skip = max(0, int(skip))
    fetch_n = limit + skip + 50
    q = (query or "").strip()
    escaped = re.escape(q) if q else None
    text_regex = {"$regex": escaped, "$options": "i"} if escaped else {"$exists": True}

    seen = set()
    results = []

    def _add(item: dict):
        f = item.get("file") or {}
        if not f or not f.get("file_id"):
            return
        if not is_video_file(f):
            return
        key = f"{f.get('backend') or 'sia'}:{f.get('file_id')}"
        if key in seen:
            return
        seen.add(key)
        results.append(item)

    local = await list_files(
        config, query=query, status="announced", limit=fetch_n, skip=0
    )
    for doc in local:
        if not is_video_file(doc):
            continue
        _add(
            {
                "source": "local",
                "block_index": None,
                "transaction_id": doc.get("transaction_id") or "",
                "file": {
                    "backend": doc.get("backend") or "sia",
                    "file_id": doc.get("file_id") or "",
                    "title": doc.get("title") or "",
                    "description": doc.get("description") or "",
                    "keywords": list(doc.get("keywords") or []),
                    "filename": doc.get("filename") or "",
                    "mime_type": doc.get("mime_type") or "",
                    "size": doc.get("size") or 0,
                },
            }
        )

    text_or = _text_match_clauses("transactions.relationship.file", text_regex)
    video_or = _video_match_clauses("transactions.relationship.file")
    if q:
        txn_match = {"$and": [{"$or": text_or}, {"$or": video_or}]}
        block_match = {
            "$and": [
                {
                    "$or": _text_match_clauses(
                        "transactions.relationship.file", text_regex
                    )
                },
                {"$or": video_or},
            ]
        }
    else:
        txn_match = {"$or": video_or}
        block_match = {"$or": video_or}

    pipeline = [
        {"$match": block_match},
        {"$unwind": "$transactions"},
        {"$match": txn_match},
        {"$sort": {"index": -1}},
        {"$limit": int(fetch_n)},
        {
            "$project": {
                "_id": 0,
                "block_index": "$index",
                "transaction": "$transactions",
            }
        },
    ]
    try:
        async for doc in _db(config).blocks.aggregate(pipeline):
            txn = doc.get("transaction") or {}
            rel = (txn.get("relationship") or {}).get("file") or {}
            _add(
                {
                    "source": "chain",
                    "block_index": doc.get("block_index"),
                    "transaction_id": txn.get("id") or "",
                    "file": rel,
                }
            )
    except Exception:
        pass

    mem_text = _text_match_clauses("relationship.file", text_regex)
    mem_video = _video_match_clauses("relationship.file")
    if q:
        mem_filt = {"$and": [{"$or": mem_text}, {"$or": mem_video}]}
    else:
        mem_filt = {"$or": mem_video}
    try:
        async for txn in (
            _db(config)
            .miner_transactions.find(mem_filt, {"_id": 0})
            .sort([("time", -1)])
            .limit(int(fetch_n))
        ):
            rel = (txn.get("relationship") or {}).get("file") or {}
            _add(
                {
                    "source": "mempool",
                    "block_index": None,
                    "transaction_id": txn.get("id") or "",
                    "file": rel,
                }
            )
    except Exception:
        pass

    return results[skip : skip + limit]
