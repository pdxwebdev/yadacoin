"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

# ── Credential receipt class ──────────────────────────────────────────────────
#
# A CredentialReceipt is a data-only on-chain transaction that the wallet
# broadcasts after receiving a verifiable credential (VC) from a vendor.  It
# carries an AES-256-GCM-encrypted copy of the full VC JSON, keyed by a
# symmetric key derived from the user's mnemonic (stable across KEL rotations),
# alongside a lookup_key (sha256-derived wallet fingerprint) that lets the
# server surface all receipts for a given wallet on resync without revealing
# the mnemonic.
#
# Wire format:
#   {"credential_receipt": {
#       "lookup_key": "<hex sha256-HKDF of mnemonic>",
#       "iv":         "<hex 12-byte AES-GCM nonce>",
#       "ct":         "<base64 AES-GCM ciphertext of the full VC JSON>"
#   }}
#
# Because the transaction carries no inputs, no value-bearing outputs, and no
# KEL rotation fields, it is NOT treated as a key event — Transaction.verify()
# skips the full KEL pipeline for CredentialReceipt relationships and only
# enforces the "no funds" invariant.
#
# Resync flow (fresh device):
#   1. Restore mnemonic (location recovery or mnemonic import).
#   2. Re-derive lookup_key and AES enc key from mnemonic (client-side).
#   3. GET /ai-agent-auth/api/resync-credentials?lookup_key=<hex>
#   4. Decrypt each receipt's ct with the enc key → VC JSON.
#   5. saveBookingCredential(vc) in localStorage.


class CredentialReceipt:
    """AES-GCM-encrypted VC receipt embedded in a data-only transaction.

    Wire format:
        {"credential_receipt": {
            "lookup_key": "<hex>",
            "iv":         "<hex>",
            "ct":         "<base64>"
        }}
    """

    _REQUIRED = ("lookup_key", "iv", "ct")

    def __init__(self, lookup_key, iv, ct, **kwargs):
        for name, val in (
            ("lookup_key", lookup_key),
            ("iv", iv),
            ("ct", ct),
        ):
            if not val or not isinstance(val, str):
                raise ValueError(f"{name} is required and must be a non-empty string")
        # lookup_key and iv are hex — normalise to lowercase for determinism.
        self.lookup_key = lookup_key.lower()
        self.iv = iv.lower()
        # ct is base64 — case-sensitive, keep verbatim.
        self.ct = ct
        # Forward-compatible passthrough for any future fields.
        self.extra_fields = {k: v for k, v in kwargs.items()}

    @staticmethod
    def from_dict(data):
        """Build from the inner dict (value of relationship["credential_receipt"])."""
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        for f in CredentialReceipt._REQUIRED:
            if f not in data:
                raise ValueError(f"'{f}' field is required in credential_receipt")
        return CredentialReceipt(**data)

    @staticmethod
    def from_relationship(relationship):
        """Build from the top-level relationship dict {"credential_receipt": ...}."""
        if (
            not isinstance(relationship, dict)
            or "credential_receipt" not in relationship
        ):
            raise ValueError("relationship must contain a 'credential_receipt' key")
        return CredentialReceipt.from_dict(relationship["credential_receipt"])

    def to_dict(self):
        inner = {
            "lookup_key": self.lookup_key,
            "iv": self.iv,
            "ct": self.ct,
        }
        if self.extra_fields:
            inner.update(self.extra_fields)
        return {"credential_receipt": inner}

    def to_string(self):
        """Deterministic preimage for the relationship_hash.

        Concatenates lookup_key + iv + ct (no separators).  The JS client
        must compute the same concatenation when signing.
        """
        return self.lookup_key + self.iv + self.ct

    def __repr__(self):
        return (
            f"CredentialReceipt(lookup_key={self.lookup_key[:8]}…, "
            f"iv={self.iv[:8]}…)"
        )
