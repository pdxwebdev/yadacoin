"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import hashlib
import time
from logging import getLogger

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey as CoincurvePrivateKey

from yadacoin.core.contenttakedown import (
    ContentTakedownAnnouncement,
    TakedownReasonCode,
)
from yadacoin.core.fileannouncement import FileAnnouncement
from yadacoin.core.keyeventlog import KeyEventFlag, KeyEventLog, classify_key_event_flag
from yadacoin.core.keyrotation import NodeKeyRotationManager, derive_secure_path
from yadacoin.core.transaction import NotEnoughMoneyException, Transaction

from . import store
from .backends import StorageBackendError, get_backend

app_log = getLogger("tornado.application")


class FileAnnouncementServiceError(Exception):
    pass


async def _backend_from_settings(config, backend_name=None):
    settings = await store.get_settings(config)
    name = backend_name or settings.get("backend") or "sia"
    return (
        get_backend(
            name,
            app_key_hex=settings.get("sia_app_key") or "",
            indexer_url=settings.get("sia_indexer_url") or "",
        ),
        name,
        settings,
    )


async def _broadcast(config, txn: Transaction):
    await config.mongo.async_db.miner_transactions.replace_one(
        {"id": txn.transaction_signature}, txn.to_dict(), upsert=True
    )
    confirming = getattr(txn, "confirming_txn", None)
    if confirming is not None:
        await config.mongo.async_db.miner_transactions.replace_one(
            {"id": confirming.transaction_signature},
            confirming.to_dict(),
            upsert=True,
        )
    peer = getattr(config, "peer", None)
    node_shared = getattr(config, "nodeShared", None)
    node_client = getattr(config, "nodeClient", None)
    if not peer or not node_shared:
        return
    try:
        async for peer_stream in peer.get_sync_peers():
            payload = {"transaction": txn.to_dict()}
            await node_shared.write_params(peer_stream, "newtxn", payload)
            confirming = getattr(txn, "confirming_txn", None)
            if confirming is not None:
                await node_shared.write_params(
                    peer_stream, "newtxn", {"transaction": confirming.to_dict()}
                )
            if node_client and getattr(peer_stream.peer, "protocol_version", 1) > 1:
                node_client.retry_messages[
                    (
                        peer_stream.peer.rid,
                        "newtxn",
                        txn.transaction_signature,
                    )
                ] = payload
                if confirming is not None:
                    node_client.retry_messages[
                        (
                            peer_stream.peer.rid,
                            "newtxn",
                            confirming.transaction_signature,
                        )
                    ] = {"transaction": confirming.to_dict()}
    except Exception as exc:
        app_log.warning("file announcement broadcast failed: %s", exc)


def _key_pub_addr(key):
    pub = CoincurvePrivateKey(key["private_key"]).public_key.format(compressed=True)
    return pub.hex(), str(P2PKHBitcoinAddress.from_pubkey(pub))


def _rel_hash(relationship):
    if not relationship:
        return ""
    if hasattr(relationship, "to_string") and callable(relationship.to_string):
        preimage = relationship.to_string()
    else:
        preimage = relationship
    return hashlib.sha256(preimage.encode()).digest().hex()


def _as_str(value):
    return value if isinstance(value, str) else ""


def _kel_material(config):
    mgr = getattr(config, "kel_manager", None)
    k0 = getattr(mgr, "_k0", None) if mgr is not None else None
    second_factor = _as_str(
        getattr(mgr, "_second_factor", None) if mgr is not None else ""
    )
    if k0 and second_factor:
        return k0, second_factor
    raise FileAnnouncementServiceError(
        "node KEL is not initialized; file announcements require key rotation continuity"
    )


def _k0_from_seed(config, second_factor):
    """Re-derive K0 the same way NodeKeyRotationManager and keyrotation handlers do."""
    seed = _as_str(getattr(config, "seed", ""))
    if not seed or not second_factor:
        return None
    from bip32utils import BIP32Key
    from mnemonic import Mnemonic

    entropy = Mnemonic("english").to_entropy(seed)
    root = BIP32Key.fromEntropy(entropy)
    return derive_secure_path(root.PrivateKey(), root.ChainCode(), second_factor)


def _walk_to_address(start_key, second_factor, target_addr, max_steps=512):
    """Derive forward from *start_key* until P2PKH matches *target_addr*."""
    cur = start_key
    pub, addr = _key_pub_addr(cur)
    if addr == target_addr:
        return cur, pub, addr
    for _ in range(max_steps):
        cur = derive_secure_path(cur["private_key"], cur["chain_code"], second_factor)
        pub, addr = _key_pub_addr(cur)
        if addr == target_addr:
            return cur, pub, addr
    return None, None, None


async def _next_kel_signer(config):
    """Return K_{n+1} material that must sign the next UNCONFIRMED KEL event."""
    k0, second_factor = _kel_material(config)
    seeded = _k0_from_seed(config, second_factor)
    if seeded is not None:
        k0 = seeded
    k0_pub, _k0_addr = _key_pub_addr(k0)
    kel = await KeyEventLog.build_from_public_key(k0_pub)
    if not kel:
        raise FileAnnouncementServiceError(
            "no key event log found for this node; cannot rotate for continuity"
        )
    latest = kel[-1]
    if classify_key_event_flag(latest) == KeyEventFlag.UNCONFIRMED:
        raise FileAnnouncementServiceError(
            "KEL tip is UNCONFIRMED; wait for the confirming rotation before announcing"
        )
    target = latest.prerotated_key_hash
    signer, signer_pub, signer_addr = None, None, None

    # Prefer the live kel_anchor when it already is the pre-committed next signer.
    anchor_addr = _as_str(getattr(config, "kel_anchor_address", ""))
    anchor_priv = _as_str(getattr(config, "kel_anchor_private_key", ""))
    anchor_cc = _as_str(getattr(config, "kel_anchor_chain_code", ""))
    if target and anchor_addr == target and anchor_priv and anchor_cc:
        try:
            signer = {
                "private_key": bytes.fromhex(anchor_priv),
                "chain_code": bytes.fromhex(anchor_cc),
            }
            signer_pub, signer_addr = _key_pub_addr(signer)
        except Exception:
            signer = None

    if signer is None:
        signer, signer_pub, signer_addr = _walk_to_address(k0, second_factor, target)
    if signer is None or signer_addr != target:
        raise FileAnnouncementServiceError(
            "derived next signer does not match KEL prerotated_key_hash"
        )
    child = derive_secure_path(
        signer["private_key"], signer["chain_code"], second_factor
    )
    grandchild = derive_secure_path(
        child["private_key"], child["chain_code"], second_factor
    )
    great_grandchild = derive_secure_path(
        grandchild["private_key"], grandchild["chain_code"], second_factor
    )
    inception_pkh = (
        getattr(latest, "inception_public_key_hash", None) or kel[0].public_key_hash
    )
    next_counter = int(getattr(latest, "counter", 0) or 0) + 1
    return {
        "signer": signer,
        "signer_pub": signer_pub,
        "signer_addr": signer_addr,
        "child": child,
        "grandchild": grandchild,
        "great_grandchild": great_grandchild,
        "prev_public_key_hash": latest.public_key_hash,
        "inception_public_key_hash": inception_pkh,
        "counter": next_counter,
        "second_factor": second_factor,
    }


def _drop_zero_self_change(txn, prerotated_addr):
    txn.outputs = [
        o
        for o in txn.outputs
        if not (float(o.value) == 0.0 and o.to != prerotated_addr)
    ]


async def _sign_kel_txn(txn, priv_bytes, fee=0.0):
    if fee and float(fee) > 0:
        txn.fee = float(fee)
        try:
            await txn.do_money()
        except NotEnoughMoneyException as exc:
            raise FileAnnouncementServiceError(
                "not enough money to pay transaction fee"
            ) from exc
        _drop_zero_self_change(txn, txn.prerotated_key_hash)
    txn.hash = await txn.generate_hash()
    txn.transaction_signature = NodeKeyRotationManager._sign(priv_bytes.hex(), txn.hash)
    return txn


async def _generate_txn(config, relationship, fee=0.0):
    """Build an UNCONFIRMED+CONFIRMING KEL pair so the announcement rotates the key."""
    keys = await _next_kel_signer(config)
    child_pub, child_addr = _key_pub_addr(keys["child"])
    _gc_pub, gc_addr = _key_pub_addr(keys["grandchild"])
    _ggc_pub, ggc_addr = _key_pub_addr(keys["great_grandchild"])
    now = int(time.time())

    unconfirmed = Transaction(
        txn_time=now,
        public_key=keys["signer_pub"],
        outputs=[{"to": child_addr, "value": 0.0}],
        inputs=[],
        fee=float(fee or 0.0),
        masternode_fee=0.0,
        version=7,
        prerotated_key_hash=child_addr,
        twice_prerotated_key_hash=gc_addr,
        public_key_hash=keys["signer_addr"],
        prev_public_key_hash=keys["prev_public_key_hash"],
        relationship=relationship,
        relationship_hash=_rel_hash(relationship),
        rid="",
        dh_public_key="",
        counter=keys["counter"],
        inception_public_key_hash=keys["inception_public_key_hash"],
    )
    await _sign_kel_txn(unconfirmed, keys["signer"]["private_key"], fee=fee)

    confirming = Transaction(
        txn_time=now,
        public_key=child_pub,
        outputs=[{"to": gc_addr, "value": 0.0}],
        inputs=[],
        fee=0.0,
        masternode_fee=0.0,
        version=7,
        prerotated_key_hash=gc_addr,
        twice_prerotated_key_hash=ggc_addr,
        public_key_hash=child_addr,
        prev_public_key_hash=keys["signer_addr"],
        relationship="",
        relationship_hash="",
        rid="",
        dh_public_key="",
        counter=keys["counter"] + 1,
        inception_public_key_hash=keys["inception_public_key_hash"],
    )
    await _sign_kel_txn(confirming, keys["child"]["private_key"], fee=0.0)

    unconfirmed.confirming_txn = confirming
    return unconfirmed


async def create_file(
    config,
    title: str,
    description: str = "",
    keywords=None,
    content: bytes = None,
    filename: str = "",
    mime_type: str = "",
    file_id: str = "",
    backend_name: str = "",
    size=None,
):
    backend, name, _settings = await _backend_from_settings(config, backend_name)
    record_id = store.new_record_id()
    uploaded = None
    try:
        if content:
            uploaded = await backend.upload(
                content,
                filename=filename,
                mime_type=mime_type,
                metadata={"title": title, "description": description},
            )
            file_id = uploaded["file_id"]
            size = uploaded.get("size", len(content))
        elif not file_id:
            raise FileAnnouncementServiceError(
                "either file content or an existing file_id is required"
            )

        ann = FileAnnouncement(
            file_id=file_id,
            title=title,
            backend=name,
            description=description,
            keywords=keywords,
            filename=filename,
            mime_type=mime_type,
            size=size,
        )
        txn = await _generate_txn(config, ann, fee=0.0)
        await _broadcast(config, txn)
        record = store.record_from_announcement(
            ann,
            record_id=record_id,
            transaction_id=txn.transaction_signature,
            status="announced",
        )
        confirming = getattr(txn, "confirming_txn", None)
        if confirming is not None:
            record["confirming_transaction_id"] = confirming.transaction_signature
        saved = await store.insert_file(config, record)
        await store.add_history(
            config,
            {
                "record_id": record_id,
                "action": "upload" if content else "announce",
                "status": "success",
                "file_id": file_id,
                "filename": filename,
                "backend": name,
                "title": title,
                "transaction_id": txn.transaction_signature,
                "size": size,
            },
        )
        saved["transaction"] = txn.to_dict()
        return saved
    except Exception as exc:
        await store.add_history(
            config,
            {
                "record_id": record_id,
                "action": "upload" if content else "announce",
                "status": "error",
                "error": str(exc),
                "file_id": file_id or "",
                "filename": filename,
                "backend": name,
                "title": title,
            },
        )
        if isinstance(
            exc, (FileAnnouncementServiceError, StorageBackendError, ValueError)
        ):
            raise
        raise FileAnnouncementServiceError(str(exc)) from exc


async def update_file(
    config, record_id: str, title=None, description=None, keywords=None
):
    existing = await store.get_file(config, record_id)
    if not existing:
        raise FileAnnouncementServiceError("file not found")
    if existing.get("status") == "taken_down":
        raise FileAnnouncementServiceError("cannot update a taken-down file")
    new_title = existing["title"] if title is None else title
    new_description = existing["description"] if description is None else description
    new_keywords = existing.get("keywords") if keywords is None else keywords
    ann = FileAnnouncement(
        file_id=existing["file_id"],
        title=new_title,
        backend=existing.get("backend") or "sia",
        description=new_description,
        keywords=new_keywords,
        filename=existing.get("filename") or "",
        mime_type=existing.get("mime_type") or "",
        size=existing.get("size"),
        supersedes=existing.get("transaction_id") or "",
    )
    txn = await _generate_txn(config, ann, fee=0.0)
    await _broadcast(config, txn)
    updated = await store.update_file(
        config,
        record_id,
        {
            "title": ann.title,
            "description": ann.description,
            "keywords": list(ann.keywords),
            "supersedes": existing.get("transaction_id") or "",
            "transaction_id": txn.transaction_signature,
            "status": "announced",
            **(
                {"confirming_transaction_id": txn.confirming_txn.transaction_signature}
                if getattr(txn, "confirming_txn", None) is not None
                else {}
            ),
        },
    )
    await store.add_history(
        config,
        {
            "record_id": record_id,
            "action": "update",
            "status": "success",
            "file_id": existing["file_id"],
            "filename": existing.get("filename") or "",
            "backend": existing.get("backend") or "",
            "title": ann.title,
            "transaction_id": txn.transaction_signature,
        },
    )
    updated["transaction"] = txn.to_dict()
    return updated


async def takedown_file(
    config, record_id: str, reason_code: str, delete_backend: bool = False
):
    existing = await store.get_file(config, record_id)
    if not existing:
        raise FileAnnouncementServiceError("file not found")
    txn_id = existing.get("transaction_id")
    if not txn_id:
        raise FileAnnouncementServiceError(
            "file has no announcement transaction to take down"
        )
    try:
        reason = TakedownReasonCode(reason_code)
    except ValueError:
        valid = [r.value for r in TakedownReasonCode]
        raise FileAnnouncementServiceError(
            f"invalid reason_code {reason_code!r}. Must be one of: {valid}"
        )
    ann = ContentTakedownAnnouncement(transaction_id=txn_id, reason_code=reason)
    txn = await _generate_txn(config, ann, fee=0.0)
    await _broadcast(config, txn)
    if delete_backend:
        try:
            backend, _name, _s = await _backend_from_settings(
                config, existing.get("backend")
            )
            await backend.delete(existing["file_id"])
        except Exception as exc:
            app_log.warning("backend delete during takedown failed: %s", exc)
    updated = await store.update_file(
        config,
        record_id,
        {
            "status": "taken_down",
            "takedown_transaction_id": txn.transaction_signature,
            "takedown_reason_code": reason.value,
            **(
                {
                    "takedown_confirming_transaction_id": txn.confirming_txn.transaction_signature
                }
                if getattr(txn, "confirming_txn", None) is not None
                else {}
            ),
        },
    )
    await store.add_history(
        config,
        {
            "record_id": record_id,
            "action": "takedown",
            "status": "success",
            "file_id": existing["file_id"],
            "filename": existing.get("filename") or "",
            "backend": existing.get("backend") or "",
            "title": existing.get("title") or "",
            "transaction_id": txn.transaction_signature,
            "reason_code": reason.value,
        },
    )
    updated["takedown_transaction"] = txn.to_dict()
    return updated


async def delete_file(config, record_id: str, delete_backend: bool = True):
    existing = await store.get_file(config, record_id)
    if not existing:
        raise FileAnnouncementServiceError("file not found")
    if delete_backend and existing.get("file_id"):
        try:
            backend, _name, _s = await _backend_from_settings(
                config, existing.get("backend")
            )
            await backend.delete(existing["file_id"])
        except Exception as exc:
            app_log.warning("backend delete failed: %s", exc)
    await store.delete_file(config, record_id)
    await store.add_history(
        config,
        {
            "record_id": record_id,
            "action": "delete",
            "status": "success",
            "file_id": existing.get("file_id") or "",
            "filename": existing.get("filename") or "",
            "backend": existing.get("backend") or "",
            "title": existing.get("title") or "",
        },
    )
    return {"ok": True, "record_id": record_id}


async def download_file(config, record_id: str) -> dict:
    existing = await store.get_file(config, record_id)
    if not existing:
        raise FileAnnouncementServiceError("file not found")
    backend, _name, _s = await _backend_from_settings(config, existing.get("backend"))
    result = await backend.download(existing["file_id"])
    result["filename"] = existing.get("filename") or existing.get("title") or "download"
    result["mime_type"] = existing.get("mime_type") or "application/octet-stream"
    return result
