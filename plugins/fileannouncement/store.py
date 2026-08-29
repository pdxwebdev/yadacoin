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


async def search_chain(config, query: str, limit: int = 50) -> list:
    """Search confirmed + mempool file announcements by title/description/keywords/file_id."""
    q = (query or "").strip()
    escaped = re.escape(q) if q else None
    regex = {"$regex": escaped, "$options": "i"} if escaped else {"$exists": True}
    match = {
        "$or": [
            {"transactions.relationship.file.title": regex},
            {"transactions.relationship.file.description": regex},
            {"transactions.relationship.file.keywords": regex},
            {"transactions.relationship.file.file_id": regex},
            {"transactions.relationship.file.filename": regex},
        ]
    }
    results = []
    pipeline = [
        {"$match": match},
        {"$unwind": "$transactions"},
        {
            "$match": {
                "$or": [
                    {"transactions.relationship.file.title": regex},
                    {"transactions.relationship.file.description": regex},
                    {"transactions.relationship.file.keywords": regex},
                    {"transactions.relationship.file.file_id": regex},
                    {"transactions.relationship.file.filename": regex},
                ]
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

    mem_filt = {
        "$or": [
            {"relationship.file.title": regex},
            {"relationship.file.description": regex},
            {"relationship.file.keywords": regex},
            {"relationship.file.file_id": regex},
            {"relationship.file.filename": regex},
        ]
    }
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
