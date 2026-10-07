"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import hashlib
import json
import time
import uuid
from logging import getLogger

from coincurve import PublicKey, verify_signature

from yadacoin.core.branchannouncement import BRANCH_TYPE_LIVESTREAM

from . import obs, store
from .vp import VPVerificationError, verify_age_vp

app_log = getLogger("tornado.application")


class LivestreamServiceError(Exception):
    pass


def branch_peer(channel_id: str) -> str:
    return f"livestream:{channel_id}"


def _now():
    return int(time.time())


async def _http_json(method, url, payload=None, timeout=10):
    import aiohttp

    async with aiohttp.ClientSession() as session:
        kw = {"timeout": aiohttp.ClientTimeout(total=timeout)}
        if payload is not None:
            kw["json"] = payload
        async with session.request(method, url, **kw) as resp:
            text = await resp.text()
            try:
                data = json.loads(text) if text else {}
            except Exception:
                data = {"raw": text}
            if resp.status >= 400:
                raise LivestreamServiceError(
                    data.get("error") or f"SP request failed ({resp.status})"
                )
            return data


def _result(data):
    if not isinstance(data, dict):
        return {}
    inner = data.get("result")
    if isinstance(inner, dict):
        return inner
    return data


async def create_channel(
    config,
    title,
    description="",
    age_restricted=False,
    sp_host="",
):
    title = (title or "").strip()
    if not title:
        raise LivestreamServiceError("title is required")
    channel_id = store.new_channel_id()
    peer = branch_peer(channel_id)
    mgr = getattr(config, "kel_manager", None)
    if mgr is None or not hasattr(mgr, "_ensure_peer_branch_ready"):
        raise LivestreamServiceError("KEL manager is not initialized")
    _state, _is_new = await mgr._ensure_peer_branch_ready(
        peer, branch_type=BRANCH_TYPE_LIVESTREAM
    )
    announcement_txn_id = ""
    branch_commit = ""
    try:
        bridge = await config.mongo.async_db.key_event_log.find_one(
            {"branch_peer": peer, "counter": 0}
        )
        if bridge:
            announcement_txn_id = (
                (bridge.get("announcement_txn") or {}).get("id")
            ) or ""
            branch_commit = bridge.get("branch_commit") or ""
    except Exception:
        pass
    doc = {
        "channel_id": channel_id,
        "title": title,
        "description": description or "",
        "age_restricted": bool(age_restricted),
        "sp_host": (sp_host or "").rstrip("/"),
        "branch_peer": peer,
        "announcement_txn_id": announcement_txn_id,
        "branch_commit": branch_commit,
        "status": "idle",
        "publisher_username_signature": getattr(config, "username_signature", "") or "",
    }
    return await store.insert_channel(config, doc)


async def assert_not_blocked(config, channel):
    blocked = await store.get_blocked(
        config,
        channel_id=channel.get("channel_id") or "",
        transaction_id=channel.get("announcement_txn_id") or "",
        branch_commit=channel.get("branch_commit") or "",
    )
    if store.is_effectively_blocked(blocked):
        raise LivestreamServiceError("channel is blocked")
    return blocked


async def issue_challenge(config, channel_id, action="grant"):
    nonce = uuid.uuid4().hex
    aud = getattr(config, "username_signature", "") or getattr(config, "peer_host", "")
    exp = _now() + 120
    doc = {
        "nonce": nonce,
        "aud": aud,
        "exp": exp,
        "action": action,
        "channel_id": channel_id,
    }
    await store.insert_challenge(config, doc)
    return {
        "nonce": nonce,
        "aud": aud,
        "exp": exp,
        "action": action,
        "channel_id": channel_id,
    }


def signing_address(ratchet_pub: str) -> str:
    from bitcoin.wallet import P2PKHBitcoinAddress

    return str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(ratchet_pub)))


def channel_id_from_path(path: str) -> str:
    parts = [part for part in (path or "").strip().split("/") if part]
    if parts and parts[-1] in ("whip", "whep"):
        parts = parts[:-1]
    return parts[-1] if parts else ""


async def _kel_authorizes(config, channel_id: str, address: str) -> bool:
    db = getattr(getattr(config, "mongo", None), "async_db", None)
    kel = getattr(db, "key_event_log", None) if db is not None else None
    if kel is None or not address:
        return False
    try:
        doc = await kel.find_one(
            {"branch_peer": branch_peer(channel_id), "public_key_hash": address}
        )
    except Exception:
        return False
    if not doc or doc.get("superseded"):
        return False
    return True


async def assert_branch_signer(config, channel_id, ratchet_pub, announcement_txn_id=""):
    try:
        address = signing_address(ratchet_pub)
    except Exception as exc:
        raise LivestreamServiceError(
            "ratchet key is not authorized for this livestream branch"
        ) from exc
    if await _kel_authorizes(config, channel_id, address):
        return address
    announcement = await _announcement_txn(
        config,
        {
            "announcement_txn_id": announcement_txn_id,
            "branch_peer": branch_peer(channel_id),
        },
    )
    branch = _branch_payload(announcement)
    if (branch.get("type") or "").strip().lower() != BRANCH_TYPE_LIVESTREAM:
        raise LivestreamServiceError(
            "ratchet key is not authorized for this livestream branch"
        )
    allowed = {
        (branch.get("prerotated_key_hash") or "").strip(),
        (branch.get("twice_prerotated_key_hash") or "").strip(),
    }
    allowed.discard("")
    if address not in allowed:
        raise LivestreamServiceError(
            "ratchet key is not authorized for this livestream branch"
        )
    channel = await store.get_channel(config, channel_id)
    pinned = (channel or {}).get("announcement_txn_id") or ""
    if pinned and announcement_txn_id and pinned != announcement_txn_id:
        raise LivestreamServiceError("announcement does not match this channel")
    return address


def verify_ratchet_signature(ratchet_pub: str, nonce: str, signature: str) -> bool:
    if not ratchet_pub or not nonce or not signature:
        return False
    try:
        msg = hashlib.sha256(nonce.encode("utf-8")).digest()
        pub = PublicKey(bytes.fromhex(ratchet_pub))
        return bool(verify_signature(bytes.fromhex(signature), msg, pub.format()))
    except Exception:
        return False


def sign_ratchet_nonce(private_key_hex: str, nonce: str) -> str:
    from coincurve import PrivateKey

    key = PrivateKey.from_hex(private_key_hex)
    msg = hashlib.sha256(nonce.encode("utf-8")).digest()
    return key.sign(msg).hex()


async def accept_grant(config, body: dict):
    channel_id = (body.get("channel_id") or "").strip()
    if not channel_id:
        raise LivestreamServiceError("channel_id is required")
    channel = await store.get_channel(config, channel_id)
    if not channel:
        # SP may not have the local channel record; still enforce grant/block.
        channel = {
            "channel_id": channel_id,
            "age_restricted": bool(body.get("age_restricted")),
            "announcement_txn_id": body.get("announcement_txn_id") or "",
            "branch_commit": body.get("branch_commit") or "",
        }
    await assert_not_blocked(config, channel)
    nonce = body.get("nonce") or ""
    challenge = await store.consume_challenge(config, nonce)
    if not challenge:
        raise LivestreamServiceError("challenge nonce is invalid or expired")
    if challenge.get("channel_id") != channel_id:
        raise LivestreamServiceError("challenge channel mismatch")
    ratchet_pub = body.get("ratchet_pub") or ""
    signature = body.get("signature") or ""
    if not verify_ratchet_signature(ratchet_pub, nonce, signature):
        raise LivestreamServiceError("ratchet signature is invalid")
    await assert_branch_signer(
        config,
        channel_id,
        ratchet_pub,
        announcement_txn_id=body.get("announcement_txn_id")
        or channel.get("announcement_txn_id")
        or "",
    )
    age_restricted = bool(channel.get("age_restricted") or body.get("age_restricted"))
    vp = body.get("vp")
    vp_verified = False
    if age_restricted:
        if not vp:
            raise LivestreamServiceError("VP is required for age-restricted channels")
        try:
            verify_age_vp(config, vp, nonce)
        except VPVerificationError as exc:
            raise LivestreamServiceError(str(exc)) from exc
        vp_verified = True
    await store.deactivate_grants(config, channel_id)
    grant = await store.insert_grant(
        config,
        {
            "channel_id": channel_id,
            "publisher_username_signature": body.get("publisher_username_signature")
            or "",
            "expires": int(body.get("expires") or (_now() + 12 * 3600)),
            "active": True,
            "publishing": False,
            "ratchet_pub": ratchet_pub,
            "next_address": (body.get("next_address") or "").strip(),
            "age_restricted": age_restricted,
            "vp_verified": vp_verified,
        },
    )
    if channel.get("title") or True:
        try:
            await store.update_channel(
                config,
                channel_id,
                status="granted",
                age_restricted=age_restricted,
            )
        except Exception:
            pass
    return grant


async def revoke_grant(config, channel_id: str):
    await store.deactivate_grants(config, channel_id)
    try:
        await store.update_channel(config, channel_id, status="idle")
    except Exception:
        pass
    return {"channel_id": channel_id, "active": False}


async def assert_publish_allowed(config, channel_id: str):
    channel_id = channel_id_from_path(channel_id) or (channel_id or "").strip()
    if not channel_id:
        raise LivestreamServiceError("channel_id is required")
    channel = await store.get_channel(config, channel_id) or {"channel_id": channel_id}
    await assert_not_blocked(config, channel)
    grant = await store.get_active_grant(config, channel_id)
    if not grant:
        raise LivestreamServiceError("no active grant")
    if int(grant.get("expires") or 0) < _now():
        await store.deactivate_grants(config, channel_id)
        raise LivestreamServiceError("grant expired")
    if grant.get("age_restricted") and not grant.get("vp_verified"):
        raise LivestreamServiceError("18+ publish requires a verified VP on the grant")
    return {"ok": True, "channel_id": channel_id}


async def on_publish(config, channel_id: str):
    channel = await store.get_channel(config, channel_id) or {"channel_id": channel_id}
    await assert_not_blocked(config, channel)
    grant = await store.get_active_grant(config, channel_id)
    if not grant:
        raise LivestreamServiceError("no active grant")
    if int(grant.get("expires") or 0) < _now():
        await store.deactivate_grants(config, channel_id)
        raise LivestreamServiceError("grant expired")
    if grant.get("age_restricted") and not grant.get("vp_verified"):
        raise LivestreamServiceError("18+ publish requires a verified VP on the grant")
    await store.mark_grant_publishing(config, channel_id)
    await store.ensure_channel(
        config,
        channel_id,
        status="live",
        age_restricted=bool(grant.get("age_restricted")),
        publisher_username_signature=grant.get("publisher_username_signature") or "",
        announcement_txn_id=channel.get("announcement_txn_id") or "",
        branch_commit=channel.get("branch_commit") or "",
        branch_peer=channel.get("branch_peer") or branch_peer(channel_id),
        title=channel.get("title") or "",
        description=channel.get("description") or "",
    )
    return {"ok": True, "channel_id": channel_id}


async def on_unpublish(config, channel_id: str):
    await store.deactivate_grants(config, channel_id)
    try:
        await store.update_channel(config, channel_id, status="idle")
    except Exception:
        pass
    return {"ok": True, "channel_id": channel_id}


def _identity_username(txn):
    if not isinstance(txn, dict):
        return ""
    relationship = txn.get("relationship")
    if not isinstance(relationship, dict):
        return ""
    identity = relationship.get("identity")
    if not isinstance(identity, dict):
        return ""
    return (identity.get("username") or "").strip()


def _branch_payload(txn):
    if not isinstance(txn, dict):
        return {}
    relationship = txn.get("relationship")
    if not isinstance(relationship, dict):
        return {}
    branch = relationship.get("branch")
    if not isinstance(branch, dict):
        return {}
    return branch


def _txn_identity(txn):
    if not isinstance(txn, dict):
        return {}
    branch = _branch_payload(txn)
    branch_type = (branch.get("type") or "").strip().lower()
    owner = (txn.get("inception_public_key_hash") or "").strip()
    public_key_hash = (txn.get("public_key_hash") or "").strip()
    return {
        "branch_type": branch_type,
        "owner": owner,
        "public_key_hash": public_key_hash or owner,
        "transaction_id": (txn.get("id") or "").strip(),
        "protocol_livestream": branch_type == BRANCH_TYPE_LIVESTREAM,
    }


async def _find_txn(config, transaction_id):
    transaction_id = (transaction_id or "").strip()
    if not transaction_id:
        return None
    db = getattr(getattr(config, "mongo", None), "async_db", None)
    if db is None:
        return None
    mem = getattr(db, "miner_transactions", None)
    if mem is not None:
        try:
            txn = await mem.find_one({"id": transaction_id})
        except Exception:
            txn = None
        if txn:
            return txn
    blocks = getattr(db, "blocks", None)
    if blocks is None or not hasattr(blocks, "aggregate"):
        return None
    match = {"transactions.id": transaction_id}
    try:
        cursor = blocks.aggregate(
            [
                {"$match": match},
                {"$unwind": "$transactions"},
                {"$match": match},
                {"$limit": 1},
            ]
        )
        async for doc in cursor:
            txn = doc.get("transactions")
            if isinstance(txn, dict):
                return txn
    except Exception:
        return None
    return None


async def _announcement_txn(config, doc):
    txn = await _find_txn(config, doc.get("announcement_txn_id") or "")
    if txn:
        return txn
    peer = (doc.get("branch_peer") or "").strip()
    if not peer:
        return None
    db = getattr(getattr(config, "mongo", None), "async_db", None)
    kel = getattr(db, "key_event_log", None) if db is not None else None
    if kel is None:
        return None
    try:
        bridge = await kel.find_one({"branch_peer": peer, "counter": 0})
    except Exception:
        bridge = None
    if not bridge:
        return None
    announcement = bridge.get("announcement_txn")
    return announcement if isinstance(announcement, dict) else None


async def _username_for(config, owner="", public_key_hash="", signature=""):
    db = getattr(getattr(config, "mongo", None), "async_db", None)
    if db is None:
        return ""
    mem = getattr(db, "miner_transactions", None)
    signature = (signature or "").strip()
    if mem is not None and signature:
        try:
            txn = await mem.find_one(
                {"relationship.identity.username_signature": signature}
            )
        except Exception:
            txn = None
        name = _identity_username(txn)
        if name:
            return name
    keys = [k for k in ((owner or "").strip(), (public_key_hash or "").strip()) if k]
    if mem is not None and keys:
        try:
            txn = await mem.find_one(
                {
                    "$or": [
                        {"inception_public_key_hash": {"$in": keys}},
                        {"public_key_hash": {"$in": keys}},
                    ],
                    "relationship.identity.username": {"$gt": ""},
                }
            )
        except Exception:
            txn = None
        name = _identity_username(txn)
        if name:
            return name
    blocks = getattr(db, "blocks", None)
    if not keys or blocks is None or not hasattr(blocks, "aggregate"):
        return ""
    chain_query = {
        "$or": [
            {"transactions.inception_public_key_hash": {"$in": keys}},
            {"transactions.public_key_hash": {"$in": keys}},
        ],
        "transactions.relationship.identity.username": {"$gt": ""},
    }
    try:
        cursor = blocks.aggregate(
            [
                {"$match": chain_query},
                {"$unwind": "$transactions"},
                {"$match": chain_query},
                {"$limit": 1},
            ]
        )
        async for doc in cursor:
            name = _identity_username(doc.get("transactions"))
            if name:
                return name
    except Exception:
        return ""
    return ""


async def _identity_for_channel(config, doc):
    peer = (doc.get("branch_peer") or "").strip()
    txn = await _announcement_txn(config, doc)
    shaped = _txn_identity(txn) if txn else {}
    if txn and shaped.get("branch_type") not in ("", BRANCH_TYPE_LIVESTREAM):
        return {"skip": True}
    if txn and not shaped.get("protocol_livestream"):
        return {"skip": True}
    if not txn and not peer.startswith("livestream:"):
        return {"skip": True}
    signature = (doc.get("publisher_username_signature") or "").strip()
    username = await _username_for(
        config,
        owner=shaped.get("owner") or "",
        public_key_hash=shaped.get("public_key_hash") or "",
        signature=signature,
    )
    owner = shaped.get("owner") or ""
    public_key_hash = shaped.get("public_key_hash") or owner
    return {
        "skip": False,
        "branch_type": BRANCH_TYPE_LIVESTREAM,
        "protocol_livestream": bool(shaped.get("protocol_livestream")),
        "owner": owner,
        "public_key_hash": public_key_hash,
        "username": username,
        "transaction_id": shaped.get("transaction_id")
        or (doc.get("announcement_txn_id") or ""),
        "publisher_username_signature": signature,
    }


def _redact_live(doc, include_playback=False, playback_url="", identity=None):
    identity = identity or {}
    out = {
        "kind": "livestream",
        "branch_type": identity.get("branch_type") or BRANCH_TYPE_LIVESTREAM,
        "protocol_livestream": bool(identity.get("protocol_livestream")),
        "channel_id": doc.get("channel_id"),
        "title": doc.get("title"),
        "description": doc.get("description"),
        "age_restricted": bool(doc.get("age_restricted")),
        "status": doc.get("status"),
        "announcement_txn_id": doc.get("announcement_txn_id") or "",
        "transaction_id": identity.get("transaction_id")
        or doc.get("announcement_txn_id")
        or "",
        "username": identity.get("username") or "",
        "owner": identity.get("owner") or "",
        "public_key_hash": identity.get("public_key_hash") or "",
        "publisher_username_signature": identity.get("publisher_username_signature")
        or doc.get("publisher_username_signature")
        or "",
    }
    if include_playback:
        base = playback_url.rstrip("/")
        out["playback_url"] = f"{base}/{doc.get('channel_id')}" if base else ""
    return out


async def _confirmed_live_docs(config):
    """A channel is live only after the ingest sidecar calls on_publish.

    That sets ``publishing`` on an active, unexpired livestream-branch grant.
    Go Live and the branch announcement do not.
    """
    grants = await store.list_publishing_grants(config)
    docs = []
    for grant in grants:
        channel_id = (grant.get("channel_id") or "").strip()
        if not channel_id:
            continue
        if int(grant.get("expires") or 0) < _now():
            await store.deactivate_grants(config, channel_id)
            try:
                await store.update_channel(config, channel_id, status="idle")
            except Exception:
                pass
            continue
        channel = await store.get_channel(config, channel_id) or {}
        doc = dict(channel)
        doc["channel_id"] = channel_id
        doc["status"] = "live"
        doc.setdefault(
            "publisher_username_signature",
            grant.get("publisher_username_signature") or "",
        )
        doc.setdefault("age_restricted", bool(grant.get("age_restricted")))
        doc.setdefault("branch_peer", branch_peer(channel_id))
        docs.append(doc)
    return docs


async def _sp_hosts(config):
    hosts = []
    try:
        settings = await store.get_settings(config)
    except Exception:
        settings = {}
    preferred = (settings.get("preferred_sp_host") or "").rstrip("/")
    if preferred:
        hosts.append(preferred)
    try:
        channels = await store.list_channels(config)
    except Exception:
        channels = []
    for channel in channels:
        host = (channel.get("sp_host") or "").rstrip("/")
        if host and host not in hosts:
            hosts.append(host)
    return hosts


async def _remote_live(config):
    results = []
    seen = set()
    for host in await _sp_hosts(config):
        try:
            data = await _http_json(
                "GET",
                f"{host}/livestream-announcements/api/v1/live?local=1",
            )
        except Exception:
            continue
        for row in data.get("results") or []:
            channel_id = row.get("channel_id")
            if not channel_id or channel_id in seen:
                continue
            seen.add(channel_id)
            results.append(row)
    return results


async def public_live_list(config, include_remote=True):
    playback = getattr(config, "livestream_playback_url", "") or ""
    results = []
    seen = set()
    for doc in await _confirmed_live_docs(config):
        identity = await _identity_for_channel(config, doc)
        if identity.get("skip"):
            continue
        include = not bool(doc.get("age_restricted"))
        row = _redact_live(
            doc,
            include_playback=include,
            playback_url=playback,
            identity=identity,
        )
        seen.add(row.get("channel_id"))
        results.append(row)
    if include_remote and getattr(config, "peer_type", "") != "service_provider":
        for row in await _remote_live(config):
            if row.get("channel_id") in seen:
                continue
            seen.add(row.get("channel_id"))
            results.append(row)
    return results


async def watch(config, channel_id: str, vp=None):
    channel = await store.get_channel(config, channel_id)
    grant = await store.get_active_grant(config, channel_id)
    if (
        not channel
        or channel.get("status") != "live"
        or not grant
        or not grant.get("publishing")
        or int(grant.get("expires") or 0) < _now()
    ):
        raise LivestreamServiceError("channel is not live")
    await assert_not_blocked(config, channel)
    playback = getattr(config, "livestream_playback_url", "") or ""
    if channel.get("age_restricted"):
        if not vp:
            raise LivestreamServiceError(
                "VP is required to watch age-restricted streams"
            )
        nonce = (
            ((vp.get("proof") or {}).get("challenge")) if isinstance(vp, dict) else ""
        )
        if not nonce:
            raise LivestreamServiceError("VP proof challenge is required")
        consumed = await store.consume_challenge(config, nonce)
        if not consumed:
            raise LivestreamServiceError("challenge nonce is invalid or expired")
        try:
            verify_age_vp(config, vp, nonce)
        except VPVerificationError as exc:
            raise LivestreamServiceError(str(exc)) from exc
    return {
        "channel_id": channel_id,
        "playback_url": f"{playback.rstrip('/')}/{channel_id}" if playback else "",
    }


async def go_live(config, channel_id: str, vp=None):
    channel = await store.get_channel(config, channel_id)
    if not channel:
        raise LivestreamServiceError("channel not found")
    await assert_not_blocked(config, channel)
    settings = await store.get_settings(config)
    sp_host = channel.get("sp_host") or settings.get("preferred_sp_host") or ""
    if not sp_host:
        raise LivestreamServiceError("sp_host is required")
    mgr = getattr(config, "kel_manager", None)
    if mgr is None:
        raise LivestreamServiceError("KEL manager is not initialized")
    challenge = await _http_json(
        "POST",
        f"{sp_host.rstrip('/')}/livestream-announcements/api/v1/challenge",
        {"channel_id": channel_id, "action": "grant"},
    )
    nonce = _result(challenge).get("nonce")
    if not nonce:
        raise LivestreamServiceError("SP challenge did not return a nonce")
    (
        cur_priv,
        cur_pub,
        _next_priv,
        next_pub,
        *_rest,
    ) = await mgr.advance_peer_auth_ratchet(
        branch_peer(channel_id), branch_type=BRANCH_TYPE_LIVESTREAM
    )
    signature = sign_ratchet_nonce(cur_priv, nonce)
    next_address = signing_address(next_pub) if next_pub else ""
    if channel.get("age_restricted") and not vp:
        raise LivestreamServiceError("VP is required for age-restricted channels")
    body = {
        "channel_id": channel_id,
        "publisher_username_signature": getattr(config, "username_signature", "") or "",
        "ratchet_pub": cur_pub,
        "next_address": next_address,
        "signature": signature,
        "nonce": nonce,
        "age_restricted": bool(channel.get("age_restricted")),
        "announcement_txn_id": channel.get("announcement_txn_id") or "",
        "branch_commit": channel.get("branch_commit") or "",
        "vp": vp,
    }
    grant = _result(
        await _http_json(
            "POST",
            f"{sp_host.rstrip('/')}/livestream-announcements/api/v1/grants",
            body,
        )
    )
    ingest_url = ""
    try:
        status = await _http_json("GET", f"{sp_host.rstrip('/')}/get-status")
        ingest_url = ((status.get("capabilities") or {}).get("livestream") or {}).get(
            "url"
        ) or ""
    except Exception:
        ingest_url = getattr(config, "livestream_ingest_url", "") or ""
    obs_ok, obs_err = await obs.try_start(
        settings.get("obs_websocket_host") or "127.0.0.1",
        settings.get("obs_websocket_port") or 4455,
        settings.get("obs_websocket_password") or "",
        ingest_url,
        channel_id,
    )
    await store.update_channel(config, channel_id, status="starting", sp_host=sp_host)
    return {
        "channel": await store.get_channel(config, channel_id),
        "grant": grant,
        "obs_started": obs_ok,
        "obs_error": obs_err,
        "ingest_url": ingest_url,
        "stream_key": channel_id,
    }


async def stop_live(config, channel_id: str):
    channel = await store.get_channel(config, channel_id)
    if not channel:
        raise LivestreamServiceError("channel not found")
    settings = await store.get_settings(config)
    sp_host = channel.get("sp_host") or settings.get("preferred_sp_host") or ""
    if sp_host:
        try:
            await _http_json(
                "POST",
                f"{sp_host.rstrip('/')}/livestream-announcements/api/v1/grants/revoke",
                {"channel_id": channel_id},
            )
        except Exception as exc:
            app_log.warning("livestream grant revoke failed: %s", exc)
    obs_ok, obs_err = await obs.try_stop(
        settings.get("obs_websocket_host") or "127.0.0.1",
        settings.get("obs_websocket_port") or 4455,
        settings.get("obs_websocket_password") or "",
    )
    await store.update_channel(config, channel_id, status="idle")
    return {
        "channel": await store.get_channel(config, channel_id),
        "obs_stopped": obs_ok,
        "obs_error": obs_err,
    }


async def whitelist_channel(config, channel_id: str):
    doc = await store.whitelist_blocked(config, channel_id)
    if not doc:
        raise LivestreamServiceError("blocked channel not found")
    return doc
