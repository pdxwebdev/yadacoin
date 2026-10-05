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
RETRACTIONS_COLLECTION = "file_announcement_retractions"
_BLOCKED_LOCAL_STATUSES = frozenset({"taken_down", "deleted"})
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
        "share_url": ann.share_url,
        "thumbnail_file_id": ann.thumbnail_file_id,
        "thumbnail_share_url": ann.thumbnail_share_url,
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


def _share_url_for_rel(rel: dict, file_id: str) -> str:
    if not rel:
        return ""
    if rel.get("file_id") == file_id:
        return str(rel.get("share_url") or "").strip()
    if rel.get("thumbnail_file_id") == file_id:
        return str(rel.get("thumbnail_share_url") or rel.get("share_url") or "").strip()
    return ""


async def share_url_for_file(config, file_id: str) -> str:
    """Public Sia share URL from the local index, then confirmed blocks."""
    file_id = (file_id or "").strip()
    if not file_id:
        return ""
    local = await get_file_by_file_id(config, file_id)
    url = ((local or {}).get("share_url") or "").strip()
    if url:
        return url
    try:
        thumb = await _db(config)[FILES_COLLECTION].find_one(
            {"thumbnail_file_id": file_id}, {"_id": 0}
        )
    except Exception:
        thumb = None
    url = _share_url_for_rel(thumb or {}, file_id)
    if url:
        return url
    try:
        cursor = (
            _db(config)
            .blocks.find(
                {
                    "$or": [
                        {"transactions.relationship.file.file_id": file_id},
                        {"transactions.relationship.file.thumbnail_file_id": file_id},
                    ]
                },
                {"transactions.relationship.file": 1, "index": 1},
            )
            .sort("index", -1)
            .limit(8)
        )
        async for block in cursor:
            for txn in block.get("transactions") or []:
                rel = (txn.get("relationship") or {}).get("file") or {}
                url = _share_url_for_rel(rel, file_id)
                if url:
                    return url
    except Exception:
        return ""
    try:
        cursor = (
            _db(config)
            .miner_transactions.find(
                {
                    "$or": [
                        {"relationship.file.file_id": file_id},
                        {"relationship.file.thumbnail_file_id": file_id},
                    ]
                },
                {"relationship.file": 1},
            )
            .sort([("time", -1)])
            .limit(8)
        )
        async for txn in cursor:
            rel = (txn.get("relationship") or {}).get("file") or {}
            url = _share_url_for_rel(rel, file_id)
            if url:
                return url
    except Exception:
        return ""
    return ""


def _file_payload(relationship):
    if not isinstance(relationship, dict):
        return None
    file_rel = relationship.get("file")
    if not isinstance(file_rel, dict):
        return None
    if not (file_rel.get("file_id") or "").strip():
        return None
    return file_rel


def _backend_matches(file_rel: dict, backend: str) -> bool:
    wanted = (backend or "").strip().lower()
    if not wanted:
        return True
    actual = ((file_rel or {}).get("backend") or "sia").strip().lower()
    return actual == wanted


async def find_file_announcements(config, file_id: str) -> list:
    """File announcements still stored in confirmed blocks or the mempool."""
    file_id = (file_id or "").strip()
    if not file_id:
        return []
    found = []
    try:
        cursor = (
            _db(config)
            .blocks.find(
                {
                    "$or": [
                        {"transactions.relationship.file.file_id": file_id},
                        {"transactions.relationship.file.thumbnail_file_id": file_id},
                    ]
                },
                {"transactions": 1, "index": 1},
            )
            .limit(20)
        )
        async for block in cursor:
            for txn in block.get("transactions") or []:
                rel = _file_payload(txn.get("relationship"))
                if not rel or (
                    rel.get("file_id") != file_id
                    and rel.get("thumbnail_file_id") != file_id
                ):
                    continue
                found.append(
                    {
                        "source": "chain",
                        "block_index": block.get("index"),
                        "transaction_id": txn.get("id") or "",
                        "owner": txn.get("inception_public_key_hash") or "",
                        "file": rel,
                    }
                )
    except Exception:
        pass
    found.sort(key=lambda item: int(item.get("block_index") or 0), reverse=True)
    try:
        cursor = (
            _db(config)
            .miner_transactions.find(
                {
                    "$or": [
                        {"relationship.file.file_id": file_id},
                        {"relationship.file.thumbnail_file_id": file_id},
                    ]
                },
                {"_id": 0},
            )
            .limit(20)
        )
        async for txn in cursor:
            rel = _file_payload(txn.get("relationship"))
            if not rel or (
                rel.get("file_id") != file_id
                and rel.get("thumbnail_file_id") != file_id
            ):
                continue
            found.append(
                {
                    "source": "mempool",
                    "block_index": None,
                    "transaction_id": txn.get("id") or "",
                    "owner": txn.get("inception_public_key_hash") or "",
                    "file": rel,
                }
            )
    except Exception:
        pass
    return found


async def takedown_targets(config, txn_ids) -> set:
    """Announcement ids targeted by a takedown in blocks or the mempool."""
    ids = []
    seen = set()
    for raw in txn_ids or []:
        tid = (raw or "").strip()
        if tid and tid not in seen:
            seen.add(tid)
            ids.append(tid)
    if not ids:
        return set()
    hit = set()
    try:
        cursor = _db(config).blocks.find(
            {"transactions.relationship.content_takedown.transaction_id": {"$in": ids}},
            {"transactions.relationship": 1},
        )
        async for block in cursor:
            for txn in block.get("transactions") or []:
                rel = txn.get("relationship")
                if not isinstance(rel, dict):
                    continue
                target = (
                    (rel.get("content_takedown") or {}).get("transaction_id") or ""
                ).strip()
                if target in seen:
                    hit.add(target)
    except Exception:
        pass
    try:
        cursor = _db(config).miner_transactions.find(
            {"relationship.content_takedown.transaction_id": {"$in": ids}},
            {"relationship": 1, "_id": 0},
        )
        async for txn in cursor:
            rel = txn.get("relationship")
            if not isinstance(rel, dict):
                continue
            target = (
                (rel.get("content_takedown") or {}).get("transaction_id") or ""
            ).strip()
            if target in seen:
                hit.add(target)
    except Exception:
        pass
    return hit


async def is_retracted(config, file_id: str = "", transaction_id: str = "") -> bool:
    file_id = (file_id or "").strip()
    transaction_id = (transaction_id or "").strip()
    clauses = []
    if file_id:
        clauses.append({"file_id": file_id})
    if transaction_id:
        clauses.append({"transaction_id": transaction_id})
    if not clauses:
        return False
    try:
        doc = await _db(config)[RETRACTIONS_COLLECTION].find_one(
            {"$or": clauses}, {"_id": 1}
        )
    except Exception:
        return False
    return bool(doc)


async def retract_file(config, file_id: str = "", transaction_id: str = "") -> None:
    file_id = (file_id or "").strip()
    transaction_id = (transaction_id or "").strip()
    if not file_id and not transaction_id:
        return
    await _db(config)[RETRACTIONS_COLLECTION].update_one(
        {"file_id": file_id, "transaction_id": transaction_id},
        {
            "$set": {
                "file_id": file_id,
                "transaction_id": transaction_id,
                "updated_at": _now(),
            }
        },
        upsert=True,
    )


async def clear_retraction(config, file_id: str = "") -> None:
    file_id = (file_id or "").strip()
    if not file_id:
        return
    try:
        await _db(config)[RETRACTIONS_COLLECTION].delete_many({"file_id": file_id})
    except Exception:
        pass


async def clear_local_file_relationship(config, transaction_id: str) -> None:
    """Drop a file relationship from this node's stored blocks.

    Same local effect as takedown compliance: the announcement is no longer
    on chain for playback, without changing relationship_hash.
    """
    tid = (transaction_id or "").strip()
    if not tid:
        return
    try:
        await _db(config).blocks.update_many(
            {"transactions.id": tid},
            {"$set": {"transactions.$.relationship": ""}},
        )
    except Exception:
        pass


async def remove_mempool_announcement(
    config, file_id: str = "", transaction_ids=None
) -> None:
    ids = [i for i in (transaction_ids or []) if i]
    try:
        if ids:
            await _db(config).miner_transactions.delete_many({"id": {"$in": ids}})
        file_id = (file_id or "").strip()
        if file_id:
            await _db(config).miner_transactions.delete_many(
                {"relationship.file.file_id": file_id}
            )
    except Exception:
        pass


def _managed_view(
    txn: dict, file_rel: dict, source: str, block_index=None, block_time=None
) -> dict:
    when = txn.get("time") or block_time or 0
    tid = txn.get("id") or ""
    return {
        "transaction_id": tid,
        "record_id": tid,
        "file_id": file_rel.get("file_id") or "",
        "title": file_rel.get("title") or "",
        "description": file_rel.get("description") or "",
        "keywords": list(file_rel.get("keywords") or []),
        "filename": file_rel.get("filename") or "",
        "mime_type": file_rel.get("mime_type") or "",
        "size": file_rel.get("size"),
        "backend": file_rel.get("backend") or "sia",
        "share_url": file_rel.get("share_url") or "",
        "thumbnail_file_id": file_rel.get("thumbnail_file_id") or "",
        "thumbnail_share_url": file_rel.get("thumbnail_share_url") or "",
        "supersedes": file_rel.get("supersedes") or "",
        "owner": txn.get("inception_public_key_hash") or "",
        "status": "mempool" if source == "mempool" else "confirmed",
        "source": source,
        "block_index": block_index,
        "updated_at": when,
        "created_at": when,
    }


def _text_matches(view: dict, query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return True
    keywords = view.get("keywords") or []
    if not isinstance(keywords, (list, tuple)):
        keywords = [keywords]
    haystacks = [
        view.get("title") or "",
        view.get("description") or "",
        view.get("file_id") or "",
        view.get("filename") or "",
        view.get("transaction_id") or "",
        " ".join(str(k) for k in keywords),
    ]
    return any(q in str(h).lower() for h in haystacks)


async def iter_live_file_txns(config) -> list:
    """File announcements currently in confirmed blocks or the mempool."""
    found = []
    try:
        cursor = _db(config).blocks.find(
            {"transactions.relationship.file.file_id": {"$gt": ""}},
            {"transactions": 1, "index": 1, "time": 1},
        )
        async for block in cursor:
            for txn in block.get("transactions") or []:
                rel = _file_payload(txn.get("relationship"))
                if not rel:
                    continue
                found.append(
                    _managed_view(
                        txn,
                        rel,
                        "chain",
                        block.get("index"),
                        block.get("time"),
                    )
                )
    except Exception:
        pass
    found.sort(key=lambda item: int(item.get("block_index") or 0), reverse=True)
    try:
        cursor = _db(config).miner_transactions.find(
            {"relationship.file.file_id": {"$gt": ""}},
            {"_id": 0},
        )
        async for txn in cursor:
            rel = _file_payload(txn.get("relationship"))
            if not rel:
                continue
            found.append(_managed_view(txn, rel, "mempool"))
    except Exception:
        pass
    return found


async def list_live_files(
    config,
    query: str = "",
    status: str = "",
    limit: int = 100,
    skip: int = 0,
) -> list:
    """Managed-file rows sourced only from the mempool and chain."""
    limit = max(1, min(int(limit), 500))
    skip = max(0, int(skip))
    wanted = (status or "").strip().lower()
    if wanted in ("chain", "onchain", "announced"):
        wanted = "confirmed"
    items = await iter_live_file_txns(config)
    ids = [item.get("transaction_id") for item in items]
    taken = await takedown_targets(config, ids)
    live = []
    for item in items:
        tid = (item.get("transaction_id") or "").strip()
        file_id = (item.get("file_id") or "").strip()
        if tid and tid in taken:
            continue
        if await is_retracted(config, file_id=file_id, transaction_id=tid):
            continue
        if wanted == "mempool" and item.get("status") != "mempool":
            continue
        if wanted == "confirmed" and item.get("status") != "confirmed":
            continue
        if not _text_matches(item, query):
            continue
        live.append(item)
    live.sort(key=lambda row: int(row.get("updated_at") or 0), reverse=True)
    return live[skip : skip + limit]


async def get_live_by_transaction_id(config, transaction_id: str) -> Optional[dict]:
    tid = (transaction_id or "").strip()
    if not tid:
        return None
    if await is_retracted(config, transaction_id=tid):
        return None
    if tid in await takedown_targets(config, [tid]):
        return None
    try:
        txn = await _db(config).miner_transactions.find_one({"id": tid}, {"_id": 0})
    except Exception:
        txn = None
    if txn:
        rel = _file_payload(txn.get("relationship"))
        if rel:
            return _managed_view(txn, rel, "mempool")
    try:
        block = await _db(config).blocks.find_one(
            {"transactions.id": tid},
            {"transactions": 1, "index": 1, "time": 1},
        )
    except Exception:
        block = None
    if not block:
        return None
    for txn in block.get("transactions") or []:
        if txn.get("id") != tid:
            continue
        rel = _file_payload(txn.get("relationship"))
        if rel:
            return _managed_view(
                txn, rel, "chain", block.get("index"), block.get("time")
            )
    return None


async def live_announcement(config, file_id: str, backend: str = "") -> Optional[dict]:
    """Return a playable announcement, or None if it must not be served.

    Playable means the file relationship is still in the mempool or on chain,
    it is not the target of a takedown in either place, and this node has not
    recorded an owner deletion or takedown for it.
    """
    file_id = (file_id or "").strip()
    if not file_id:
        return None
    if await is_retracted(config, file_id=file_id):
        return None
    candidates = [
        item
        for item in await find_file_announcements(config, file_id)
        if _backend_matches(item.get("file") or {}, backend)
    ]
    if not candidates:
        return None
    taken = await takedown_targets(
        config, [item.get("transaction_id") for item in candidates]
    )
    for item in candidates:
        tid = (item.get("transaction_id") or "").strip()
        if tid and tid in taken:
            continue
        if tid and await is_retracted(config, transaction_id=tid):
            continue
        return item
    return None


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


def _identity_username(txn: dict) -> str:
    if not isinstance(txn, dict):
        return ""
    relationship = txn.get("relationship")
    if not isinstance(relationship, dict):
        return ""
    identity = relationship.get("identity")
    if not isinstance(identity, dict):
        return ""
    return (identity.get("username") or "").strip()


def _identity_keys(txn: dict) -> list:
    keys = []
    for raw in (
        txn.get("inception_public_key_hash"),
        txn.get("public_key_hash"),
    ):
        key = (raw or "").strip()
        if key and key not in keys:
            keys.append(key)
    return keys


async def identity_usernames(config) -> dict:
    """Map inception / public-key hash to the identity-announcement username."""
    index = {}

    def _absorb(txn):
        if not isinstance(txn, dict):
            return
        username = _identity_username(txn)
        if not username:
            return
        for key in _identity_keys(txn):
            index[key] = username

    try:
        async for txn in _db(config).miner_transactions.find(
            {"relationship.identity.username": {"$gt": ""}},
            {"_id": 0},
        ):
            _absorb(txn)
    except Exception:
        pass
    try:
        cursor = _db(config).blocks.find(
            {"transactions.relationship.identity.username": {"$gt": ""}},
            {"transactions": 1},
        )
        async for block in cursor:
            for txn in block.get("transactions") or []:
                try:
                    _absorb(txn)
                except Exception:
                    continue
    except Exception:
        pass
    return index


async def inception_for_username(config, username: str) -> str:
    """Inception hash for an identity-announcement username."""
    wanted = (username or "").strip().lstrip("@").lower()
    if not wanted:
        return ""
    found = {}

    def _absorb(txn):
        if not isinstance(txn, dict):
            return
        name = _identity_username(txn)
        if not name or name.lower() != wanted:
            return
        key = (
            txn.get("inception_public_key_hash") or txn.get("public_key_hash") or ""
        ).strip()
        if key:
            found["inception"] = key

    try:
        async for txn in _db(config).miner_transactions.find(
            {"relationship.identity.username": {"$gt": ""}},
            {"_id": 0},
        ):
            _absorb(txn)
    except Exception:
        pass
    try:
        cursor = _db(config).blocks.find(
            {"transactions.relationship.identity.username": {"$gt": ""}},
            {"transactions": 1},
        )
        async for block in cursor:
            for txn in block.get("transactions") or []:
                try:
                    _absorb(txn)
                except Exception:
                    continue
    except Exception:
        pass
    return found.get("inception") or ""


async def identity_for_inception(config, inception_public_key_hash: str) -> dict:
    """Username from the identity announcement behind an inception hash."""
    pkh = (inception_public_key_hash or "").strip()
    if not pkh:
        return {"inception_public_key_hash": "", "username": ""}
    names = await identity_usernames(config)
    return {
        "inception_public_key_hash": pkh,
        "username": names.get(pkh) or "",
    }


async def files_for_inception(
    config, inception_public_key_hash: str, limit: int = 200
) -> list:
    """Live file announcements whose announcer inception hash matches."""
    owner = (inception_public_key_hash or "").strip()
    if not owner:
        return []
    limit = max(1, min(int(limit), 500))
    items = await iter_live_file_txns(config)
    owned = [item for item in items if (item.get("owner") or "").strip() == owner]
    taken = await takedown_targets(
        config, [item.get("transaction_id") for item in owned]
    )
    owned.sort(key=lambda row: int(row.get("updated_at") or 0), reverse=True)
    seen = set()
    matched = []
    for item in owned:
        tid = (item.get("transaction_id") or "").strip()
        file_id = (item.get("file_id") or "").strip()
        if tid and tid in taken:
            continue
        if await is_retracted(config, file_id=file_id, transaction_id=tid):
            continue
        backend = (item.get("backend") or "sia").strip().lower()
        key = f"{backend}:{file_id}" if file_id else tid
        if not key or key in seen:
            continue
        seen.add(key)
        matched.append(item)
        if len(matched) >= limit:
            break
    return matched


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


def video_feed_keys(file_doc: dict, owner: str = "") -> list:
    """Identity keys so one user is not listed twice for the same upload.

    The same object id always collapses. Filename plus size collapses only
    within one announcer, so a different user can publish the same name.
    """
    if not file_doc:
        return []
    keys = []
    file_id = (file_doc.get("file_id") or "").strip()
    if file_id:
        backend = (file_doc.get("backend") or "sia").strip().lower()
        keys.append(f"id:{backend}:{file_id}")
    owner = (owner or file_doc.get("owner") or "").strip().lower()
    name = (file_doc.get("filename") or "").strip().lower()
    try:
        size = int(file_doc.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    if owner and name and size > 0:
        keys.append(f"content:{owner}:{name}:{size}")
    return keys


def same_user_duplicate_filter(
    owner: str = "",
    file_id: str = "",
    filename: str = "",
    size=None,
    content_hash: str = "",
) -> Optional[dict]:
    """Match a still-active announcement of the same bytes by this user."""
    clauses = []
    file_id = (file_id or "").strip()
    if file_id:
        clauses.append({"file_id": file_id})
    content_hash = (content_hash or "").strip().lower()
    if content_hash:
        clauses.append({"content_hash": content_hash})
    name = (filename or "").strip()
    try:
        size_i = int(size or 0)
    except (TypeError, ValueError):
        size_i = 0
    if name and size_i > 0:
        clauses.append(
            {
                "filename": {"$regex": f"^{re.escape(name)}$", "$options": "i"},
                "size": size_i,
            }
        )
    if not clauses:
        return None
    filt = {"status": {"$nin": ["taken_down"]}, "$or": clauses}
    owner = (owner or "").strip()
    if owner:
        filt = {
            "status": {"$nin": ["taken_down"]},
            "$and": [
                {"$or": clauses},
                {
                    "$or": [
                        {"owner": owner},
                        {"owner": ""},
                        {"owner": {"$exists": False}},
                    ]
                },
            ],
        }
    return filt


async def find_same_user_duplicate(
    config,
    owner: str = "",
    file_id: str = "",
    filename: str = "",
    size=None,
    content_hash: str = "",
) -> Optional[dict]:
    """Match a live mempool or chain announcement of the same file."""
    file_id = (file_id or "").strip()
    if file_id:
        live = await live_announcement(config, file_id)
        if live:
            view = (live.get("file") or {}).copy()
            view["transaction_id"] = live.get("transaction_id") or ""
            view["title"] = view.get("title") or ""
            return view
    name = (filename or "").strip().lower()
    try:
        size_i = int(size or 0)
    except (TypeError, ValueError):
        size_i = 0
    if not name or size_i <= 0:
        return None
    owner = (owner or "").strip().lower()
    for item in await iter_live_file_txns(config):
        if owner and (item.get("owner") or "").strip().lower() not in ("", owner):
            continue
        if (item.get("filename") or "").strip().lower() != name:
            continue
        try:
            if int(item.get("size") or 0) != size_i:
                continue
        except (TypeError, ValueError):
            continue
        if await is_retracted(
            config,
            file_id=item.get("file_id") or "",
            transaction_id=item.get("transaction_id") or "",
        ):
            continue
        return item
    return None


def _file_text_matches(file_doc: dict, query: str, transaction_id: str = "") -> bool:
    view = dict(file_doc or {})
    view["transaction_id"] = transaction_id or view.get("transaction_id") or ""
    return _text_matches(view, query)


async def search_chain(config, query: str, limit: int = 50) -> list:
    """Search confirmed + mempool file announcements by title/description/keywords/file_id."""
    q = (query or "").strip()
    limit = max(1, int(limit))
    results = []
    pipeline = [
        {"$match": {"transactions.relationship.file.file_id": {"$gt": ""}}},
        {"$unwind": "$transactions"},
        {"$match": {"transactions.relationship.file.file_id": {"$gt": ""}}},
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
            if not rel.get("file_id"):
                continue
            if not _file_text_matches(rel, q, txn.get("id") or ""):
                continue
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
    results.sort(key=lambda item: int(item.get("block_index") or 0), reverse=True)

    try:
        async for txn in _db(config).miner_transactions.find(
            {"relationship.file.file_id": {"$gt": ""}},
            {"_id": 0},
        ):
            rel = (txn.get("relationship") or {}).get("file") or {}
            if not rel.get("file_id"):
                continue
            if not _file_text_matches(rel, q, txn.get("id") or ""):
                continue
            results.append(
                {
                    "source": "mempool",
                    "block_index": None,
                    "transaction_id": txn.get("id"),
                    "file": rel,
                }
            )
            if len(results) >= limit * 2:
                break
    except Exception:
        pass
    return results[:limit]


async def search_videos(
    config, query: str = "", limit: int = 50, skip: int = 0
) -> list:
    """Discover video announcements that are still in the mempool or on chain."""
    limit = max(1, min(int(limit), 200))
    skip = max(0, int(skip))
    fetch_n = limit + skip + 50
    q = (query or "").strip()

    seen = set()
    results = []

    def _add(item: dict):
        f = item.get("file") or {}
        if not f or not f.get("file_id"):
            return
        if not is_video_file(f):
            return
        owner = (item.get("owner") or f.get("owner") or "").strip()
        if not owner and item.get("source") == "local":
            owner = "local"
        keys = video_feed_keys(f, owner)
        if not keys or any(key in seen for key in keys):
            return
        seen.update(keys)
        item["owner"] = owner
        results.append(item)

    async def _add_live(item: dict):
        f = item.get("file") or {}
        live = await live_announcement(
            config, f.get("file_id") or "", f.get("backend") or ""
        )
        if not live:
            return
        merged = dict(item)
        merged["source"] = live.get("source") or item.get("source")
        merged["block_index"] = live.get("block_index")
        merged["transaction_id"] = live.get("transaction_id") or item.get(
            "transaction_id"
        )
        merged["owner"] = live.get("owner") or item.get("owner")
        merged["file"] = live.get("file") or f
        _add(merged)

    pipeline = [
        {"$match": {"transactions.relationship.file.file_id": {"$gt": ""}}},
        {"$unwind": "$transactions"},
        {"$match": {"transactions.relationship.file.file_id": {"$gt": ""}}},
        {
            "$project": {
                "_id": 0,
                "block_index": "$index",
                "transaction": "$transactions",
            }
        },
    ]
    chain_hits = []
    try:
        async for doc in _db(config).blocks.aggregate(pipeline):
            txn = doc.get("transaction") or {}
            rel = (txn.get("relationship") or {}).get("file") or {}
            if not is_video_file(rel):
                continue
            if not _file_text_matches(rel, q, txn.get("id") or ""):
                continue
            chain_hits.append(
                {
                    "source": "chain",
                    "block_index": doc.get("block_index"),
                    "transaction_id": txn.get("id") or "",
                    "owner": txn.get("inception_public_key_hash") or "",
                    "file": rel,
                }
            )
    except Exception:
        pass
    chain_hits.sort(key=lambda item: int(item.get("block_index") or 0), reverse=True)
    for item in chain_hits:
        if len(results) >= fetch_n:
            break
        await _add_live(item)

    try:
        async for txn in _db(config).miner_transactions.find(
            {"relationship.file.file_id": {"$gt": ""}},
            {"_id": 0},
        ):
            if len(results) >= fetch_n:
                break
            rel = (txn.get("relationship") or {}).get("file") or {}
            if not is_video_file(rel):
                continue
            if not _file_text_matches(rel, q, txn.get("id") or ""):
                continue
            await _add_live(
                {
                    "source": "mempool",
                    "block_index": None,
                    "transaction_id": txn.get("id") or "",
                    "owner": txn.get("inception_public_key_hash") or "",
                    "file": rel,
                }
            )
    except Exception:
        pass

    return results[skip : skip + limit]
