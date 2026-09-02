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
