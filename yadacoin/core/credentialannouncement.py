"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Credential announcements — on-chain W3C VCs with recovery-style Schnorr proofs.

Wire format::

    {"credential": {
      "subject_username_signature": "...",
      "issuer_username_signature": "...",
      "issuer_identity_announcement": "<inception txn id>",
      "claim": "ageOver18",
      "expires": <unix int>,
      "vc": { /* W3C VC */ }
    }}

Must not collide with ``credential_receipt``.
"""

from datetime import datetime, timezone

from yadacoin.core.locationrecovery import verify_proof

DID_PREFIX = "did:yadacoin:"
CLAIM_AGE_OVER_18 = "ageOver18"


def did_for(username_signature: str) -> str:
    return f"{DID_PREFIX}{username_signature}"


def parse_did(did: str) -> str:
    if not isinstance(did, str) or not did.startswith(DID_PREFIX):
        raise ValueError("DID must be did:yadacoin:<username_signature>")
    sig = did[len(DID_PREFIX) :].strip()
    if not sig:
        raise ValueError("DID username_signature is empty")
    return sig


def expiration_iso(expires: int) -> str:
    return datetime.fromtimestamp(int(expires), tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


class CredentialAnnouncement:
    """On-chain verifiable credential embedded in a transaction relationship."""

    RELATIONSHIP_KEY = "credential"

    def __init__(
        self,
        subject_username_signature,
        issuer_username_signature,
        issuer_identity_announcement,
        claim,
        expires,
        vc,
        **kwargs,
    ):
        for name, val in (
            ("subject_username_signature", subject_username_signature),
            ("issuer_username_signature", issuer_username_signature),
            ("issuer_identity_announcement", issuer_identity_announcement),
            ("claim", claim),
        ):
            if not val or not isinstance(val, str):
                raise ValueError(f"{name} is required and must be a non-empty string")
        try:
            expires = int(expires)
        except (TypeError, ValueError):
            raise ValueError("expires must be a unix timestamp int")
        if expires <= 0:
            raise ValueError("expires must be a positive unix timestamp")
        if not isinstance(vc, dict) or not vc:
            raise ValueError("vc is required and must be a dict")
        self.subject_username_signature = subject_username_signature
        self.issuer_username_signature = issuer_username_signature
        self.issuer_identity_announcement = issuer_identity_announcement
        self.claim = str(claim).strip()
        self.expires = expires
        self.vc = vc
        self.extra_fields = {k: v for k, v in kwargs.items()}

    @staticmethod
    def get_string(value) -> str:
        if value is None:
            return ""
        return str(value)

    def proof_parts(self):
        proof = self.vc.get("proof") or {}
        if not isinstance(proof, dict):
            raise ValueError("vc.proof must be an object")
        commitment = proof.get("commitment")
        R = proof.get("R")
        s = proof.get("s")
        if not commitment or not R or not s:
            raise ValueError("vc.proof must include commitment, R, and s")
        return str(commitment), str(R), str(s)

    def verify_zkp(self) -> bool:
        commitment, R, s = self.proof_parts()
        return verify_proof(
            commitment,
            R,
            s,
            prev_key_hash=self.subject_username_signature,
        )

    def to_dict(self) -> dict:
        d = {
            "subject_username_signature": self.subject_username_signature,
            "issuer_username_signature": self.issuer_username_signature,
            "issuer_identity_announcement": self.issuer_identity_announcement,
            "claim": self.claim,
            "expires": self.expires,
            "vc": self.vc,
        }
        if self.extra_fields:
            d.update(self.extra_fields)
        return d

    def to_string(self) -> str:
        commitment, R, s = self.proof_parts()
        return (
            self.get_string(self.subject_username_signature)
            + self.get_string(self.issuer_username_signature)
            + self.get_string(self.issuer_identity_announcement)
            + self.get_string(self.claim)
            + str(self.expires)
            + commitment
            + R
            + s
        )

    @staticmethod
    def from_dict(data: dict) -> "CredentialAnnouncement":
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        for field in (
            "subject_username_signature",
            "issuer_username_signature",
            "issuer_identity_announcement",
            "claim",
            "expires",
            "vc",
        ):
            if field not in data:
                raise ValueError(f"{field} field is required")
        return CredentialAnnouncement(**data)

    @staticmethod
    def from_relationship(rel: dict) -> "CredentialAnnouncement":
        if (
            not isinstance(rel, dict)
            or CredentialAnnouncement.RELATIONSHIP_KEY not in rel
        ):
            raise ValueError("relationship does not contain a 'credential' key")
        return CredentialAnnouncement.from_dict(
            rel[CredentialAnnouncement.RELATIONSHIP_KEY]
        )

    def __repr__(self):
        return (
            f"CredentialAnnouncement(claim={self.claim!r}, "
            f"subject={self.subject_username_signature[:12]!r}…)"
        )
