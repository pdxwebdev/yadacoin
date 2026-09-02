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
            "ratchet_pub": ratchet_pub,
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
    await store.update_channel(config, channel_id, status="live")
    return {"ok": True, "channel_id": channel_id}


async def on_unpublish(config, channel_id: str):
    await store.deactivate_grants(config, channel_id)
    try:
        await store.update_channel(config, channel_id, status="idle")
    except Exception:
        pass
    return {"ok": True, "channel_id": channel_id}


def _redact_live(doc, include_playback=False, playback_url=""):
    out = {
        "channel_id": doc.get("channel_id"),
        "title": doc.get("title"),
        "description": doc.get("description"),
        "age_restricted": bool(doc.get("age_restricted")),
        "status": doc.get("status"),
    }
    if include_playback:
        base = playback_url.rstrip("/")
        out["playback_url"] = f"{base}/{doc.get('channel_id')}" if base else ""
    return out


async def public_live_list(config):
    playback = getattr(config, "livestream_playback_url", "") or ""
    docs = await store.list_live(config)
    results = []
    for doc in docs:
        include = not bool(doc.get("age_restricted"))
        results.append(
            _redact_live(doc, include_playback=include, playback_url=playback)
        )
    return results


async def watch(config, channel_id: str, vp=None):
    channel = await store.get_channel(config, channel_id)
    if not channel or channel.get("status") != "live":
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
    nonce = challenge.get("nonce")
    cur_priv, cur_pub, *_rest = await mgr.advance_peer_auth_ratchet(
        branch_peer(channel_id), branch_type=BRANCH_TYPE_LIVESTREAM
    )
    signature = sign_ratchet_nonce(cur_priv, nonce)
    if channel.get("age_restricted") and not vp:
        raise LivestreamServiceError("VP is required for age-restricted channels")
    body = {
        "channel_id": channel_id,
        "publisher_username_signature": getattr(config, "username_signature", "") or "",
        "ratchet_pub": cur_pub,
        "signature": signature,
        "nonce": nonce,
        "age_restricted": bool(channel.get("age_restricted")),
        "announcement_txn_id": channel.get("announcement_txn_id") or "",
        "branch_commit": channel.get("branch_commit") or "",
        "vp": vp,
    }
    grant = await _http_json(
        "POST",
        f"{sp_host.rstrip('/')}/livestream-announcements/api/v1/grants",
        body,
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
    await store.update_channel(config, channel_id, status="live", sp_host=sp_host)
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
