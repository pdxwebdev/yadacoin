"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

# ── Location-recovery announcement / proof classes ────────────────────────────
#
# These mirror the AgentAnnouncement / NodeAnnouncement pattern: a structured
# Python object stored verbatim under `transaction.relationship`, hashed via
# `to_string()` for the relationship_hash, and detected by Transaction.__init__
# when the wire-format relationship dict carries the matching top-level key.
#
# Two complementary on-chain artefacts exist:
#
#   • RecoveryAnnouncement  — relationship = {"recovery": <witness_hash_hex>}
#       Embedded in a KEL rotation signed by the user's CURRENT active key.
#       Publishes the *commitment-of-commitment* H = sha256(commitment) so
#       any future recovers-inception can be matched back to this KEL.
#
#       The wire format is either the legacy flat string (witness hash only)
#       or the extended dict shape:
#         {"recovery": {
#             "witness_hash": "<hex>",
#             "lookup_id":     "<hex sha256 of normalised Recovery Code>",
#             "hints_iv":      "<hex IV>",
#             "hints_ct":      "<base64 AES-GCM ciphertext of hint labels>"
#         }}
#       The encrypted hints are decryptable only by holders of the user's
#       Recovery Code; the chain itself stores no plaintext.  This removes
#       the previous server-side `location_recovery_hints` collection.
#
#   • RecoveryProof         — relationship = {"recovers": {commitment, R, s}}
#       Embedded in a recovers-inception (an inception-shaped KEL transaction
#       whose prev_public_key_hash points at the lost KEL's tip pkh).  The
#       Schnorr proof is verified by yadacoin.core.locationrecovery.verify_proof
#       against the witnessHash announced earlier.
#
# Keeping the JSON-decoded dict shape in sync with the bytes the client signed
# is critical: the relationship_hash on the transaction is sha256(to_string()),
# and consensus recomputes it inside Transaction.generate_hash.


class RecoveryAnnouncement:
    """Witness-hash announcement embedded in a KEL rotation.

    Wire format (legacy):   {"recovery": "<witness_hash_hex>"}
    Wire format (extended): {"recovery": {"witness_hash": "<hex>",
                                          "lookup_id":   "<hex>",
                                          "hints_iv":    "<hex>",
                                          "hints_ct":    "<base64>"}}
    """

    def __init__(
        self,
        witness_hash,
        lookup_id="",
        hints_iv="",
        hints_ct="",
        **kwargs,
    ):
        if not witness_hash or not isinstance(witness_hash, str):
            raise ValueError("witness_hash is required and must be a hex string")
        for name, val in (
            ("lookup_id", lookup_id),
            ("hints_iv", hints_iv),
            ("hints_ct", hints_ct),
        ):
            if val is None:
                val = ""
            if not isinstance(val, str):
                raise ValueError(f"{name} must be a string")
        self.witness_hash = witness_hash.lower()
        # lookup_id / hints_iv are hex; normalise to lowercase so the
        # to_string() preimage is deterministic across clients.
        self.lookup_id = (lookup_id or "").lower()
        self.hints_iv = (hints_iv or "").lower()
        # hints_ct is base64; keep verbatim — base64 is case-sensitive.
        self.hints_ct = hints_ct or ""
        # forward-compatible passthrough for any future fields
        self.extra_fields = {k: v for k, v in kwargs.items()}

    @staticmethod
    def from_dict(data):
        """Build from the inner dict (i.e. the value of relationship["recovery"]
        already unwrapped).  When the caller has the full
        {"recovery": "<hash>"} envelope they should call
        `RecoveryAnnouncement.from_relationship` instead.

        Accepts both the legacy flat string and the extended dict shape.
        """
        if isinstance(data, str):
            return RecoveryAnnouncement(witness_hash=data)
        if not isinstance(data, dict):
            raise ValueError("data must be a dict or hex string")
        return RecoveryAnnouncement(**data)

    @staticmethod
    def from_relationship(relationship):
        """Build from the top-level relationship dict {"recovery": ...}."""
        if not isinstance(relationship, dict) or "recovery" not in relationship:
            raise ValueError("relationship must contain a 'recovery' key")
        return RecoveryAnnouncement.from_dict(relationship["recovery"])

    def has_hints(self):
        return bool(self.hints_ct and self.hints_iv)

    def to_dict(self):
        # Preserve the legacy flat string form when no extras are present so
        # already-published announcements round-trip byte-for-byte.
        if not (self.lookup_id or self.hints_iv or self.hints_ct or self.extra_fields):
            return {"recovery": self.witness_hash}
        inner = {"witness_hash": self.witness_hash}
        if self.lookup_id:
            inner["lookup_id"] = self.lookup_id
        if self.hints_iv:
            inner["hints_iv"] = self.hints_iv
        if self.hints_ct:
            inner["hints_ct"] = self.hints_ct
        if self.extra_fields:
            inner.update(self.extra_fields)
        return {"recovery": inner}

    def to_string(self):
        """Deterministic preimage for the relationship_hash.

        Concatenates witness_hash + lookup_id + hints_iv + hints_ct (each
        empty string when absent).  Empty extras collapse to the legacy
        preimage of just the witness_hash, so old announcements still
        produce the same relationship_hash.  The JS client must compute
        the same concatenation when broadcasting an extended announcement.
        """
        return self.witness_hash + self.lookup_id + self.hints_iv + self.hints_ct

    def __repr__(self):
        return (
            f"RecoveryAnnouncement(witness_hash={self.witness_hash!r}, "
            f"lookup_id={self.lookup_id!r}, has_hints={self.has_hints()})"
        )


class RecoveryProof:
    """Schnorr proof embedded in a recovers-inception transaction.

    On-chain wire format:
        {"recovers": {"commitment": "<hex>", "R": "<hex>", "s": "<hex>"}}
    """

    _REQUIRED = ("commitment", "R", "s")

    def __init__(self, commitment, R, s, **kwargs):
        for name, val in (("commitment", commitment), ("R", R), ("s", s)):
            if not val or not isinstance(val, str):
                raise ValueError(f"{name} is required and must be a hex string")
        self.commitment = commitment
        self.R = R
        self.s = s
        self.extra_fields = {k: v for k, v in kwargs.items()}

    @staticmethod
    def from_dict(data):
        """Build from the inner dict (the value of relationship["recovers"])."""
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        for f in RecoveryProof._REQUIRED:
            if f not in data:
                raise ValueError(f"{f} field is required")
        return RecoveryProof(**data)

    @staticmethod
    def from_relationship(relationship):
        """Build from the top-level relationship dict {"recovers": ...}."""
        if not isinstance(relationship, dict) or "recovers" not in relationship:
            raise ValueError("relationship must contain a 'recovers' key")
        return RecoveryProof.from_dict(relationship["recovers"])

    def to_dict(self):
        out = {
            "recovers": {
                "commitment": self.commitment,
                "R": self.R,
                "s": self.s,
            }
        }
        if self.extra_fields:
            out["recovers"].update(self.extra_fields)
        return out

    def to_string(self):
        """Deterministic preimage for the relationship_hash.

        Matches what the JS client signs: commitment || R || s, all
        lowercase hex with no separators.  Order matters and must stay in
        sync with the JS `buildRecoversRelationship` helper.
        """
        return self.commitment + self.R + self.s

    def __repr__(self):
        return (
            f"RecoveryProof(commitment={self.commitment[:8]}..., "
            f"R={self.R[:8]}..., s={self.s[:8]}...)"
        )


class RecoveryTransition:
    """Combined recovers-inception proof + new recovery announcement.

    Carried by a recovers-inception whose relationship contains BOTH a
    ``recovers`` Schnorr proof and a ``recovery`` announcement for the
    newly recovered KEL.  This atomically proves recovery eligibility and
    re-establishes the location-recovery vault commitment in a single
    transaction so the new KEL is immediately recoverable.

    Wire format:
        {
            "recovers": {"commitment": "<hex>", "R": "<hex>", "s": "<hex>"},
            "recovery": {"witness_hash": "<hex>",
                         "lookup_id":    "<hex>",
                         "hints_iv":     "<hex>",
                         "hints_ct":     "<base64>"}
        }
    """

    def __init__(self, proof: RecoveryProof, announcement: RecoveryAnnouncement):
        self.proof = proof
        self.announcement = announcement

    @staticmethod
    def from_relationship(relationship):
        """Build from a dict that has both 'recovers' and 'recovery' keys."""
        if not isinstance(relationship, dict):
            raise ValueError("relationship must be a dict")
        if "recovers" not in relationship or "recovery" not in relationship:
            raise ValueError(
                "relationship must contain both 'recovers' and 'recovery' keys"
            )
        proof = RecoveryProof.from_dict(relationship["recovers"])
        announcement = RecoveryAnnouncement.from_relationship(
            {"recovery": relationship["recovery"]}
        )
        return RecoveryTransition(proof, announcement)

    def to_dict(self):
        d = self.proof.to_dict()  # {"recovers": {...}}
        d.update(self.announcement.to_dict())  # {"recovery": ...}
        return d

    def to_string(self):
        """Deterministic preimage for the relationship_hash.

        Concatenates the proof preimage with the announcement preimage:
            commitment + R + s + witness_hash + lookup_id + hints_iv + hints_ct

        The JS ``buildRecoveryTransitionRelationship`` must compute the same
        concatenation.
        """
        return self.proof.to_string() + self.announcement.to_string()

    def __repr__(self):
        return (
            f"RecoveryTransition(proof={self.proof!r}, "
            f"announcement={self.announcement!r})"
        )
