"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import os
import time
from logging import getLogger

from yadacoin.core.credentialannouncement import (
    CLAIM_AGE_OVER_18,
    CredentialAnnouncement,
    did_for,
    expiration_iso,
)
from yadacoin.core.locationrecovery import verify_proof

from . import store
from .zkp import generate_proof

app_log = getLogger("tornado.application")


class CredentialIssuerError(Exception):
    pass


def _issuer_identity_announcement(config) -> str:
    inc = getattr(config, "inception", None)
    if inc is not None:
        for attr in ("transaction_signature", "id"):
            val = getattr(inc, attr, None)
            if val:
                return val
        if isinstance(inc, dict):
            return inc.get("id") or inc.get("transaction_signature") or ""
    return ""


def build_vc(
    subject_username_signature,
    issuer_username_signature,
    claim,
    expires,
    proof,
    issuer_identity_announcement="",
):
    vc_type = (
        "AgeOver18Credential" if claim == CLAIM_AGE_OVER_18 else f"{claim}Credential"
    )
    subject = {"id": did_for(subject_username_signature)}
    if claim == CLAIM_AGE_OVER_18:
        subject["ageOver18"] = True
    else:
        subject[claim] = True
    return {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "type": ["VerifiableCredential", vc_type],
        "issuer": did_for(issuer_username_signature),
        "credentialSubject": subject,
        "expirationDate": expiration_iso(expires),
        "expires": int(expires),
        "issuer_identity_announcement": issuer_identity_announcement,
        "proof": proof,
    }


async def resolve_subject_username(username: str):
    """Map a unique on-chain username to its identity announcement."""
    from yadacoin.core.identityannouncement import IdentityAnnouncement

    username = (username or "").strip().lower()
    if not username:
        raise CredentialIssuerError("username is required")
    found = await IdentityAnnouncement.get_by_username(username)
    if not found:
        raise CredentialIssuerError(
            f"no identity announcement for username {username!r}"
        )
    identity = found.get("identity") or {}
    sig = (identity.get("username_signature") or "").strip()
    if not sig:
        raise CredentialIssuerError(
            f"identity for {username!r} is missing username_signature"
        )
    return username, sig, identity


def _unique_forward_chain(base_tip, candidates):
    from yadacoin.core.keyeventlog import (
        classify_key_event_flag,
        kel_successor_flag_allowed,
        verify_kel_step,
    )

    if base_tip is None:
        return []
    children_of = {}
    for txn in candidates or []:
        prev = getattr(txn, "prev_public_key_hash", None) or ""
        if not isinstance(prev, str) or not prev:
            continue
        populated = getattr(txn, "are_kel_fields_populated", None)
        if populated is not None and not populated():
            continue
        children_of.setdefault(prev, []).append(txn)

    prev = base_tip
    chain = []
    seen = set()
    previous_onchain = True
    while len(chain) < 64:
        prev_pkh = getattr(prev, "public_key_hash", None) or ""
        if not isinstance(prev_pkh, str) or not prev_pkh:
            break
        try:
            prev_flag = classify_key_event_flag(prev)
        except Exception:
            break
        kids = []
        for kid in children_of.get(prev_pkh, []):
            sig = getattr(kid, "transaction_signature", None)
            if not sig or sig in seen:
                continue
            try:
                kid_flag = classify_key_event_flag(kid)
            except Exception:
                continue
            if not kel_successor_flag_allowed(prev_flag, kid_flag):
                continue
            try:
                verify_kel_step(
                    prev,
                    kid,
                    previous_onchain=previous_onchain,
                    latest_entry=prev,
                )
            except Exception:
                continue
            kids.append(kid)
        if len(kids) != 1:
            break
        nxt = kids[0]
        seen.add(nxt.transaction_signature)
        chain.append(nxt)
        prev = nxt
        previous_onchain = False
    return chain


def partition_issue_kel(onchain, mempool_txns):
    """Parent like file announcements: complete mempool extension, or on-chain tip.

    A stuck UNCONFIRMED child of that tip is kept so its confirming sibling can
    be synthesized. Orphan confirmings (parent already discarded) are dropped.
    """
    from yadacoin.core.keyeventlog import (
        KeyEventFlag,
        classify_key_event_flag,
        is_kel_chain_complete,
    )

    chain = _unique_forward_chain(onchain, mempool_txns)
    prefix = []
    for end in range(len(chain), 0, -1):
        if is_kel_chain_complete(chain[:end]):
            prefix = chain[:end]
            break
    rest = chain[len(prefix) :]
    keep = list(prefix)
    if len(rest) == 1 and classify_key_event_flag(rest[0]) == KeyEventFlag.UNCONFIRMED:
        keep.append(rest[0])
    keep_sigs = {getattr(txn, "transaction_signature", None) for txn in keep}
    drop = [
        txn
        for txn in mempool_txns or []
        if getattr(txn, "transaction_signature", None) not in keep_sigs
    ]
    return keep, drop


async def _anchor_issue_kel(config):
    from plugins.fileannouncement.service import (
        _k0_from_seed,
        _kel_material,
        _key_pub_addr,
    )
    from yadacoin.core.keyeventlog import KeyEventLog
    from yadacoin.core.transaction import Transaction

    k0, second_factor = _kel_material(config)
    seeded = _k0_from_seed(config, second_factor)
    if seeded is not None:
        k0 = seeded
    k0_pub, _addr = _key_pub_addr(k0)
    onchain = None
    try:
        onchain = await KeyEventLog.get_onchain_hashlink_tip(k0_pub)
    except Exception as exc:
        app_log.warning("credentialissuer: on-chain hashlink tip failed: %s", exc)
    if onchain is None:
        onchain = await KeyEventLog.get_latest(k0_pub, onchain_only=True)
    if onchain is None:
        raise CredentialIssuerError(
            "no on-chain KEL tip; credential issuance would be discarded"
        )
    inception = getattr(onchain, "inception_public_key_hash", None) or ""
    if not inception:
        return
    mempool = []
    cursor = config.mongo.async_db.miner_transactions.find(
        {"inception_public_key_hash": inception}
    )
    async for doc in cursor:
        if not isinstance(doc, dict):
            continue
        try:
            mempool.append(Transaction.from_dict(doc))
        except Exception:
            continue
    _keep, drop = partition_issue_kel(onchain, mempool)
    for txn in drop:
        sig = getattr(txn, "transaction_signature", None) or ""
        if not sig:
            continue
        await config.mongo.async_db.miner_transactions.delete_one({"id": sig})
        app_log.info(
            "credentialissuer: dropped orphan KEL %s; issuance extends the on-chain tip",
            sig[:24],
        )


async def issue_credential(
    config,
    username="",
    subject_username_signature="",
    claim=CLAIM_AGE_OVER_18,
    expires=None,
    witness_hex="",
):
    username = (username or "").strip()
    subject_username_signature = (subject_username_signature or "").strip()
    if username:
        (
            username,
            subject_username_signature,
            _identity,
        ) = await resolve_subject_username(username)
    elif subject_username_signature:
        username = ""
    else:
        raise CredentialIssuerError("username is required")
    claim = (claim or CLAIM_AGE_OVER_18).strip() or CLAIM_AGE_OVER_18
    if expires is None:
        expires = int(time.time()) + 365 * 24 * 3600
    expires = int(expires)
    issuer_sig = getattr(config, "username_signature", "") or ""
    if not issuer_sig:
        raise CredentialIssuerError("node username_signature is not configured")
    issuer_id = _issuer_identity_announcement(config)
    if not issuer_id:
        raise CredentialIssuerError(
            "node inception identity announcement transaction id is required"
        )
    if not witness_hex:
        witness_hex = os.urandom(32).hex()
    proof = generate_proof(witness_hex, prev_key_hash=subject_username_signature)
    if not verify_proof(
        proof["commitment"],
        proof["R"],
        proof["s"],
        prev_key_hash=subject_username_signature,
    ):
        raise CredentialIssuerError("ZKP failed verification")
    vc = build_vc(
        subject_username_signature,
        issuer_sig,
        claim,
        expires,
        proof,
        issuer_identity_announcement=issuer_id,
    )
    ann = CredentialAnnouncement(
        subject_username_signature=subject_username_signature,
        issuer_username_signature=issuer_sig,
        issuer_identity_announcement=issuer_id,
        claim=claim,
        expires=expires,
        vc=vc,
    )
    from plugins.fileannouncement.service import (
        FileAnnouncementServiceError,
        _broadcast,
        _generate_txn,
    )

    try:
        await _anchor_issue_kel(config)
        txn = await _generate_txn(config, ann)
        await _broadcast(config, txn)
    except FileAnnouncementServiceError as exc:
        raise CredentialIssuerError(str(exc)) from exc
    record = await store.insert_issued(
        config,
        {
            "transaction_id": txn.transaction_signature,
            "username": username,
            "subject_username_signature": subject_username_signature,
            "issuer_username_signature": issuer_sig,
            "issuer_identity_announcement": issuer_id,
            "claim": claim,
            "expires": expires,
            "vc": vc,
        },
    )
    return record
