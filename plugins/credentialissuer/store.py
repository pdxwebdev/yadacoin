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

COLLECTION = "issued_credentials"


def _db(config):
    return config.mongo.async_db


def _now():
    return int(time.time())


def public_doc(doc):
    if not doc:
        return {}
    out = dict(doc)
    out.pop("_id", None)
    return out


async def insert_issued(config, doc: dict) -> dict:
    doc = dict(doc)
    doc.setdefault("record_id", uuid.uuid4().hex)
    doc.setdefault("created_at", _now())
    await _db(config)[COLLECTION].insert_one(doc)
    return public_doc(doc)


async def _ids_in(config, collection, query, field="id"):
    found = set()
    try:
        cursor = _db(config)[collection].find(query, {field: 1, "transactions.id": 1})
    except Exception:
        return found
    try:
        async for doc in cursor:
            if field == "transactions.id":
                for txn in doc.get("transactions") or []:
                    tid = txn.get("id")
                    if tid:
                        found.add(tid)
                continue
            tid = doc.get(field)
            if tid:
                found.add(tid)
    except Exception:
        return found
    return found


async def live_transaction_ids(config, transaction_ids):
    """Transaction ids still in the mempool or on chain. Failed txns are ignored."""
    ids = [tid for tid in transaction_ids if tid]
    if not ids:
        return set()
    mempool = await _ids_in(config, "miner_transactions", {"id": {"$in": ids}})
    chain = await _ids_in(
        config,
        "blocks",
        {"transactions.id": {"$in": ids}},
        field="transactions.id",
    )
    return mempool | chain


async def list_issued(config, limit=100, skip=0):
    limit = max(1, min(int(limit), 500))
    skip = max(0, int(skip))
    cursor = _db(config)[COLLECTION].find({}).sort("created_at", -1)
    docs = []
    if hasattr(cursor, "to_list"):
        docs = await cursor.to_list(length=None)
    else:
        async for d in cursor:
            docs.append(d)
    live = await live_transaction_ids(config, [d.get("transaction_id") for d in docs])
    kept = [public_doc(d) for d in docs if d.get("transaction_id") in live]
    return kept[skip : skip + limit]
