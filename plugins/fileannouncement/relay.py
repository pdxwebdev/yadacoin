"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import base64
from uuid import uuid4

from yadacoin.core.peer import User
from yadacoin.tcpsocket.base import BaseRPC

from . import paidstore, purchase, store

CHUNK = 128 * 1024
_WAITERS = {}


def _identity(stream):
    peer = getattr(stream, "peer", None)
    return getattr(peer, "identity", None)


def _matches(stream, username: str, signature: str) -> bool:
    ident = _identity(stream)
    if ident is None:
        return False
    sig = str(getattr(ident, "username_signature", "") or "")
    name = str(getattr(ident, "username", "") or "").lstrip("@")
    if signature and sig == signature:
        return True
    if username and name and name.lower() == username.lower():
        return True
    return False


def connected_creator_streams(config, username: str, signature: str) -> list:
    found = []
    seen = set()
    server = getattr(config, "nodeServer", None)
    inbound = getattr(server, "inbound_streams", None) or {}
    for stream in (inbound.get(User.__name__) or {}).values():
        if id(stream) in seen or not _matches(stream, username, signature):
            continue
        seen.add(id(stream))
        found.append(stream)
    return found


async def handle_paid_media(rpc, body, stream):
    params = body.get("params") or {}
    transaction_id = str(params.get("transaction_id") or "").strip()
    payment_id = str(params.get("payment_id") or "").strip()
    try:
        start = int(params.get("start") or 0)
        length = int(params.get("length") or 0)
    except (TypeError, ValueError):
        start, length = 0, 0
    result = {"ok": False}
    live = await store.get_live_by_transaction_id(rpc.config, transaction_id)
    payment = await purchase.payment_by_id(rpc.config, payment_id)
    price = str((live or {}).get("price") or "")
    pay_to = str((live or {}).get("public_key_hash") or "")
    file_id = str((live or {}).get("file_id") or "")
    credential_ok = True
    from .credentials import (
        PresentationError,
        credential_requirements,
        presentation_from_parts,
        requirement_applies,
        verify_presentation,
    )

    if requirement_applies(live, file_id):
        names = {}
        try:
            from .credentials import looks_like_username

            for gate in credential_requirements(live):
                issuer = str((gate or {}).get("issuer") or "").strip().lstrip("@")
                if not issuer or not looks_like_username(issuer):
                    continue
                for sig in await store.signatures_for_username(rpc.config, issuer):
                    names[sig] = issuer
        except Exception:
            names = {}
        try:
            verify_presentation(
                presentation_from_parts(str(params.get("vp") or ""), ""),
                gates=credential_requirements(live),
                issuer_names=names if isinstance(names, dict) else {},
            )
        except PresentationError:
            credential_ok = False
            result = {"ok": False, "error": "credential required"}
    if (
        live
        and payment
        and file_id
        and purchase.output_pays(payment, pay_to, price)
        and paidstore.has(rpc.config, file_id)
        and credential_ok
        and start >= 0
        and 0 < length <= CHUNK
    ):
        fh = paidstore.open_file(rpc.config, file_id)
        try:
            fh.seek(start)
            raw = fh.read(length)
        finally:
            fh.close()
        info = paidstore.meta(rpc.config, file_id)
        result = {
            "ok": True,
            "data": base64.b64encode(raw).decode(),
            "size": int(info.get("size") or 0),
            "mime_type": info.get("mime_type") or live.get("mime_type") or "",
            "filename": info.get("filename") or live.get("filename") or "",
        }
    await rpc.write_result(stream, "paid_media_result", result, body.get("id"))


def handle_paid_media_result(body):
    fut = _WAITERS.get(body.get("id"))
    if fut is not None and not fut.done():
        fut.set_result(body.get("result") or {})


async def pull_chunk(
    config, username, signature, transaction_id, payment_id, start, length, vp=""
):
    streams = connected_creator_streams(config, username, signature)
    if not streams:
        return None
    req_id = str(uuid4())
    fut = asyncio.get_event_loop().create_future()
    _WAITERS[req_id] = fut
    try:
        await BaseRPC().write_as_json(
            streams[0],
            "paid_media",
            {
                "transaction_id": transaction_id,
                "payment_id": payment_id,
                "start": int(start),
                "length": int(length),
                "vp": vp or "",
            },
            "params",
            req_id,
        )
        result = await asyncio.wait_for(fut, timeout=20)
    except Exception:
        return None
    finally:
        _WAITERS.pop(req_id, None)
    if not isinstance(result, dict) or not result.get("ok"):
        return None
    try:
        return base64.b64decode(result.get("data") or "")
    except Exception:
        return None
