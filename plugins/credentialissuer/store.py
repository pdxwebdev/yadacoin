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


async def list_issued(config, limit=100, skip=0):
    cursor = (
        _db(config)[COLLECTION].find({}).sort("created_at", -1).skip(skip).limit(limit)
    )
    if hasattr(cursor, "to_list"):
        docs = await cursor.to_list(length=limit)
    else:
        docs = []
        async for d in cursor:
            docs.append(d)
    return [public_doc(d) for d in docs]
