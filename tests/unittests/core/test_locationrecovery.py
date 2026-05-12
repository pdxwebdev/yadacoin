"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 - for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.
"""

"""
Unit tests for the consensus-side Schnorr verifier in
``yadacoin.core.locationrecovery``.

These tests construct proofs in pure Python (mirroring the JS prover in
``plugins/yadacoinwallet/ui/src/composables/useLocationRecovery.js``) and
exercise the verifier's positive, negative, and malformed-input paths.
"""

import os
import unittest
from hashlib import sha256

from coincurve import PublicKey

from yadacoin.core.locationrecovery import CURVE_N, verify_proof


def _make_proof(x: int, prev_key_hash: str = None, r: int = None):
    """Return ``(commitment_hex, R_hex, s_hex)`` for witness scalar ``x``.

    Mirrors the JS prover step for step:
      C = x.G,  R = r.G,  e = SHA-256(R || C || prev_key_hash_or_zeros) mod N,
      s = (r - e*x) mod N
    """
    if r is None:
        # Sample uniformly in [1, N-1]
        while True:
            r = int.from_bytes(os.urandom(32), "big") % CURVE_N
            if r != 0:
                break

    x_bytes = x.to_bytes(32, "big")
    r_bytes = r.to_bytes(32, "big")

    C = PublicKey.from_secret(x_bytes)
    R = PublicKey.from_secret(r_bytes)
    C_hex = C.format(compressed=True).hex()
    R_hex = R.format(compressed=True).hex()

    if prev_key_hash:
        prev_bytes = prev_key_hash.encode("utf-8")
    else:
        prev_bytes = b"\x00" * 32

    e = (
        int.from_bytes(
            sha256(bytes.fromhex(R_hex) + bytes.fromhex(C_hex) + prev_bytes).digest(),
            "big",
        )
        % CURVE_N
    )
    s = (r - e * x) % CURVE_N
    return C_hex, R_hex, s.to_bytes(32, "big").hex()


def _random_scalar() -> int:
    while True:
        n = int.from_bytes(os.urandom(32), "big") % CURVE_N
        if n != 0:
            return n


class TestVerifyProof(unittest.TestCase):
    """Pure unit tests for ``verify_proof``."""

    # ── happy paths ──────────────────────────────────────────────────────

    def test_valid_proof_no_prev_key_hash(self):
        x = _random_scalar()
        C, R, s = _make_proof(x, prev_key_hash=None)
        self.assertTrue(verify_proof(C, R, s, prev_key_hash=None))

    def test_valid_proof_with_prev_key_hash(self):
        x = _random_scalar()
        prev = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        C, R, s = _make_proof(x, prev_key_hash=prev)
        self.assertTrue(verify_proof(C, R, s, prev_key_hash=prev))

    def test_empty_string_prev_key_hash_treated_as_none(self):
        """The verifier hashes 32 zero bytes when prev_key_hash is falsy."""
        x = _random_scalar()
        C, R, s = _make_proof(x, prev_key_hash=None)
        # Empty string should hash the same zero block as None.
        self.assertTrue(verify_proof(C, R, s, prev_key_hash=""))

    # ── prev_key_hash binding (replay protection) ────────────────────────

    def test_proof_bound_to_prev_key_hash_rejects_other_kel(self):
        """A proof generated for KEL A must NOT verify against KEL B."""
        x = _random_scalar()
        prev_a = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        prev_b = "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar"
        C, R, s = _make_proof(x, prev_key_hash=prev_a)
        self.assertFalse(verify_proof(C, R, s, prev_key_hash=prev_b))

    def test_proof_with_prev_key_hash_rejected_when_verifier_passes_none(self):
        x = _random_scalar()
        prev = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        C, R, s = _make_proof(x, prev_key_hash=prev)
        self.assertFalse(verify_proof(C, R, s, prev_key_hash=None))

    # ── tampering ───────────────────────────────────────────────────────

    def test_tampered_s_rejected(self):
        x = _random_scalar()
        C, R, s = _make_proof(x)
        tampered = ((int(s, 16) + 1) % CURVE_N).to_bytes(32, "big").hex()
        self.assertFalse(verify_proof(C, R, tampered, prev_key_hash=None))

    def test_tampered_R_rejected(self):
        x = _random_scalar()
        C, R, s = _make_proof(x)
        # Replace R with a fresh random point.
        bad_R = PublicKey.from_secret(_random_scalar().to_bytes(32, "big"))
        bad_R_hex = bad_R.format(compressed=True).hex()
        self.assertFalse(verify_proof(C, bad_R_hex, s, prev_key_hash=None))

    def test_tampered_commitment_rejected(self):
        x = _random_scalar()
        C, R, s = _make_proof(x)
        bad_C = PublicKey.from_secret(_random_scalar().to_bytes(32, "big"))
        bad_C_hex = bad_C.format(compressed=True).hex()
        self.assertFalse(verify_proof(bad_C_hex, R, s, prev_key_hash=None))

    # ── malformed inputs ────────────────────────────────────────────────

    def test_s_zero_rejected(self):
        x = _random_scalar()
        C, R, _ = _make_proof(x)
        self.assertFalse(verify_proof(C, R, "00" * 32, prev_key_hash=None))

    def test_s_equal_to_curve_order_rejected(self):
        x = _random_scalar()
        C, R, _ = _make_proof(x)
        s_n = CURVE_N.to_bytes(32, "big").hex()
        self.assertFalse(verify_proof(C, R, s_n, prev_key_hash=None))

    def test_s_wrong_length_rejected(self):
        x = _random_scalar()
        C, R, _ = _make_proof(x)
        # 31-byte scalar
        self.assertFalse(verify_proof(C, R, "ab" * 31, prev_key_hash=None))

    def test_malformed_commitment_hex_rejected(self):
        x = _random_scalar()
        _, R, s = _make_proof(x)
        self.assertFalse(verify_proof("not-hex-data!!", R, s, prev_key_hash=None))

    def test_odd_length_hex_rejected(self):
        x = _random_scalar()
        C, R, s = _make_proof(x)
        self.assertFalse(verify_proof(C, R, s[:-1], prev_key_hash=None))

    def test_non_string_inputs_rejected(self):
        self.assertFalse(verify_proof(None, None, None, prev_key_hash=None))

    def test_zero_challenge_rejected(self):
        """Line 116: when Fiat-Shamir challenge `e == 0`, verification rejects."""
        from unittest.mock import patch

        x = _random_scalar()
        C, R, s = _make_proof(x)
        with patch("yadacoin.core.locationrecovery._challenge", return_value=0):
            self.assertFalse(verify_proof(C, R, s, prev_key_hash=None))


if __name__ == "__main__":
    unittest.main()
