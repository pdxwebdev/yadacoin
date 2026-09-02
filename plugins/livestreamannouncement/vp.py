"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import hashlib
import time

from coincurve import PrivateKey, PublicKey, verify_signature

from yadacoin.core.credentialannouncement import CLAIM_AGE_OVER_18, did_for, parse_did
from yadacoin.core.locationrecovery import verify_proof


class VPVerificationError(Exception):
    pass


def _sha256(data: str) -> bytes:
    return hashlib.sha256(data.encode("utf-8")).digest()


def sign_vp_proof(private_key_hex: str, challenge: str, holder: str) -> str:
    key = PrivateKey.from_hex(private_key_hex)
    return key.sign(_sha256(challenge + holder)).hex()


def verify_holder_proof(proof: dict, holder: str, nonce: str) -> str:
    if not isinstance(proof, dict):
        raise VPVerificationError("VP proof is required")
    challenge = proof.get("challenge") or proof.get("nonce") or ""
    if challenge != nonce:
        raise VPVerificationError("VP proof challenge does not match nonce")
    pub_hex = proof.get("publicKey") or proof.get("verificationMethod") or ""
    if pub_hex.startswith("did:"):
        raise VPVerificationError("verificationMethod must be a secp256k1 public key")
    sig_hex = proof.get("signature") or ""
    proof_value = proof.get("proofValue") or ""
    if proof_value and proof_value.startswith("z") and not sig_hex:
        raise VPVerificationError("Data Integrity proofValue is not supported here")
    if not pub_hex or not sig_hex:
        raise VPVerificationError("VP proof publicKey and signature are required")
    try:
        pub = PublicKey(bytes.fromhex(pub_hex))
        ok = verify_signature(
            bytes.fromhex(sig_hex), _sha256(nonce + holder), pub.format()
        )
    except Exception as exc:
        raise VPVerificationError(f"VP proof is malformed: {exc}") from exc
    if not ok:
        raise VPVerificationError("VP proof signature is invalid")
    return pub_hex


def extract_vc(vp: dict) -> dict:
    creds = vp.get("verifiableCredential")
    if isinstance(creds, list) and creds:
        vc = creds[0]
    else:
        vc = vp.get("verifiableCredential") or vp.get("vc")
    if not isinstance(vc, dict):
        raise VPVerificationError("VP is missing verifiableCredential")
    return vc


def verify_age_vp(config, vp, nonce: str) -> dict:
    """Verify a holder VP wrapping an ageOver18 credential.

    Order: nonce (caller), holder proof, DID match, Schnorr ZKP, expiry,
    issuer allowlist.
    """
    if not isinstance(vp, dict):
        raise VPVerificationError("VP must be an object")
    holder = vp.get("holder") or ""
    try:
        holder_sig = parse_did(holder)
    except ValueError as exc:
        raise VPVerificationError(str(exc)) from exc
    pub_hex = verify_holder_proof(vp.get("proof") or {}, holder, nonce)
    vc = extract_vc(vp)
    subject = (vc.get("credentialSubject") or {}).get("id") or ""
    try:
        subject_sig = parse_did(subject)
    except ValueError as exc:
        raise VPVerificationError(str(exc)) from exc
    if subject_sig != holder_sig:
        raise VPVerificationError("VP holder does not match credential subject")
    if vc.get("credentialSubject", {}).get("ageOver18") is not True:
        raise VPVerificationError("credentialSubject.ageOver18 must be true")
    proof = vc.get("proof") or {}
    if not verify_proof(
        proof.get("commitment") or "",
        proof.get("R") or "",
        proof.get("s") or "",
        prev_key_hash=subject_sig,
    ):
        raise VPVerificationError("VC Schnorr proof is invalid")
    expires = vc.get("expires")
    if expires is None:
        # ISO expirationDate fallback
        expires = 0
    try:
        expires_i = int(expires)
    except (TypeError, ValueError):
        expires_i = 0
    if expires_i and expires_i < int(time.time()):
        raise VPVerificationError("credential is expired")
    expiration_date = vc.get("expirationDate") or ""
    if expiration_date:
        try:
            from datetime import datetime, timezone

            parsed = datetime.strptime(expiration_date, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            if parsed.timestamp() < time.time():
                raise VPVerificationError("credential is expired")
        except VPVerificationError:
            raise
        except Exception:
            pass
    issuer_id = (
        vp.get("issuer_identity_announcement")
        or vc.get("issuer_identity_announcement")
        or ""
    )
    allow = list(getattr(config, "age_credential_issuers", None) or [])
    if not allow:
        raise VPVerificationError("age_credential_issuers is empty")
    if issuer_id not in allow:
        raise VPVerificationError("issuer is not in age_credential_issuers")
    return {
        "holder": holder_sig,
        "public_key": pub_hex,
        "issuer_identity_announcement": issuer_id,
        "claim": CLAIM_AGE_OVER_18,
    }


def build_vp(
    private_key_hex, username_signature, vc, nonce, issuer_identity_announcement=""
):
    holder = did_for(username_signature)
    proof = {
        "type": "EcdsaSecp256k1Signature2019",
        "challenge": nonce,
        "publicKey": PrivateKey.from_hex(private_key_hex)
        .public_key.format(compressed=True)
        .hex(),
        "signature": sign_vp_proof(private_key_hex, nonce, holder),
    }
    return {
        "type": ["VerifiablePresentation"],
        "holder": holder,
        "verifiableCredential": [vc],
        "issuer_identity_announcement": issuer_identity_announcement,
        "proof": proof,
    }
