"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import time
import uuid

CHANNELS = "livestream_channels"
GRANTS = "livestream_grants"
BLOCKED = "livestream_blocked_branches"
CHALLENGES = "livestream_challenges"
SETTINGS = "livestream_settings"
SETTINGS_ID = "default"


def _db(config):
    return config.mongo.async_db


def _now():
    return int(time.time())


def new_channel_id() -> str:
    return uuid.uuid4().hex


def public_doc(doc: dict) -> dict:
    if not doc:
        return {}
    out = dict(doc)
    out.pop("_id", None)
    return out


async def get_settings(config) -> dict:
    doc = await _db(config)[SETTINGS].find_one({"_id": SETTINGS_ID})
    if not doc:
        return {
            "obs_websocket_host": getattr(config, "obs_websocket_host", "127.0.0.1"),
            "obs_websocket_port": getattr(config, "obs_websocket_port", 4455),
            "obs_websocket_password": getattr(config, "obs_websocket_password", "")
            or "",
            "preferred_sp_host": "",
        }
    doc.pop("_id", None)
    return doc


async def save_settings(config, data: dict) -> dict:
    current = await get_settings(config)
    current.update(
        {
            k: data[k]
            for k in data
            if k
            in (
                "obs_websocket_host",
                "obs_websocket_port",
                "obs_websocket_password",
                "preferred_sp_host",
            )
        }
    )
    current["_id"] = SETTINGS_ID
    await _db(config)[SETTINGS].replace_one({"_id": SETTINGS_ID}, current, upsert=True)
    current.pop("_id", None)
    return current


async def insert_channel(config, doc: dict) -> dict:
    doc = dict(doc)
    doc.setdefault("created_at", _now())
    doc.setdefault("updated_at", _now())
    await _db(config)[CHANNELS].insert_one(doc)
    return public_doc(doc)


async def get_channel(config, channel_id: str):
    doc = await _db(config)[CHANNELS].find_one({"channel_id": channel_id})
    return public_doc(doc) if doc else None


async def list_channels(config, limit=100, skip=0):
    cursor = (
        _db(config)[CHANNELS].find({}).sort("created_at", -1).skip(skip).limit(limit)
    )
    if hasattr(cursor, "to_list"):
        docs = await cursor.to_list(length=limit)
    else:
        docs = []
        async for d in cursor:
            docs.append(d)
    return [public_doc(d) for d in docs]


async def update_channel(config, channel_id: str, **fields):
    fields["updated_at"] = _now()
    await _db(config)[CHANNELS].update_one({"channel_id": channel_id}, {"$set": fields})
    return await get_channel(config, channel_id)


async def channel_id_for_announcement(config, transaction_id: str) -> str:
    doc = await _db(config)[CHANNELS].find_one({"announcement_txn_id": transaction_id})
    if not doc:
        return ""
    return doc.get("channel_id") or ""


async def upsert_blocked_branch(
    config,
    channel_id="",
    branch_commit="",
    transaction_id="",
    reason_code="",
):
    now = _now()
    filt = {}
    if transaction_id:
        filt["transaction_id"] = transaction_id
    elif channel_id:
        filt["channel_id"] = channel_id
    elif branch_commit:
        filt["branch_commit"] = branch_commit
    else:
        return None
    await _db(config)[BLOCKED].update_one(
        filt,
        {
            "$set": {
                "channel_id": channel_id,
                "branch_commit": branch_commit,
                "transaction_id": transaction_id,
                "reason_code": reason_code,
                "blocked_at": now,
                "whitelisted": False,
            }
        },
        upsert=True,
    )
    return await get_blocked(
        config, channel_id=channel_id, transaction_id=transaction_id
    )


async def get_blocked(config, channel_id="", transaction_id="", branch_commit=""):
    clauses = []
    if channel_id:
        clauses.append({"channel_id": channel_id})
    if transaction_id:
        clauses.append({"transaction_id": transaction_id})
    if branch_commit:
        clauses.append({"branch_commit": branch_commit})
    if not clauses:
        return None
    doc = await _db(config)[BLOCKED].find_one(
        {"$or": clauses} if len(clauses) > 1 else clauses[0]
    )
    return public_doc(doc) if doc else None


def is_effectively_blocked(doc) -> bool:
    if not doc:
        return False
    return not bool(doc.get("whitelisted"))


async def whitelist_blocked(config, channel_id: str):
    await _db(config)[BLOCKED].update_one(
        {"channel_id": channel_id}, {"$set": {"whitelisted": True}}
    )
    return await get_blocked(config, channel_id=channel_id)


async def insert_grant(config, doc: dict) -> dict:
    doc = dict(doc)
    doc.setdefault("created_at", _now())
    doc.setdefault("active", True)
    await _db(config)[GRANTS].insert_one(doc)
    return public_doc(doc)


async def get_active_grant(config, channel_id: str):
    doc = await _db(config)[GRANTS].find_one({"channel_id": channel_id, "active": True})
    return public_doc(doc) if doc else None


async def deactivate_grants(config, channel_id: str):
    await _db(config)[GRANTS].update_many(
        {"channel_id": channel_id, "active": True},
        {"$set": {"active": False, "revoked_at": _now()}},
    )


async def insert_challenge(config, doc: dict):
    await _db(config)[CHALLENGES].insert_one(doc)


async def consume_challenge(config, nonce: str):
    doc = await _db(config)[CHALLENGES].find_one({"nonce": nonce})
    if not doc:
        return None
    if int(doc.get("exp") or 0) < _now():
        await _db(config)[CHALLENGES].delete_one({"nonce": nonce})
        return None
    await _db(config)[CHALLENGES].delete_one({"nonce": nonce})
    return public_doc(doc)


async def list_live(config, limit=100):
    cursor = (
        _db(config)[CHANNELS]
        .find({"status": "live"})
        .sort("updated_at", -1)
        .limit(limit)
    )
    if hasattr(cursor, "to_list"):
        docs = await cursor.to_list(length=limit)
    else:
        docs = []
        async for d in cursor:
            docs.append(d)
    return [public_doc(d) for d in docs]
