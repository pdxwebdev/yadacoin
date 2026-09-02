"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import os
from hashlib import sha256

from coincurve import PublicKey
from coincurve.utils import GROUP_ORDER_INT

from yadacoin.core.locationrecovery import CURVE_N, verify_proof


def _hex_to_bytes(value: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError("hex value must be a string")
    if len(value) % 2 != 0:
        raise ValueError("hex value must have even length")
    return bytes.fromhex(value)


def _challenge(R_hex: str, commitment_hex: str, prev_key_hash) -> int:
    R_bytes = _hex_to_bytes(R_hex)
    C_bytes = _hex_to_bytes(commitment_hex)
    if prev_key_hash:
        prev_bytes = prev_key_hash.encode("utf-8")
    else:
        prev_bytes = b"\x00" * 32
    digest = sha256(R_bytes + C_bytes + prev_bytes).digest()
    return int.from_bytes(digest, "big") % CURVE_N


def generate_proof(witness_hex: str, prev_key_hash: str = None) -> dict:
    """Issuer-held Schnorr proof of knowledge of *witness*, bound to prev_key_hash."""
    raw = _hex_to_bytes(witness_hex)
    x = int.from_bytes(raw, "big") % GROUP_ORDER_INT
    if x == 0:
        raise ValueError("witness must be a non-zero scalar")
    x_bytes = x.to_bytes(32, "big")
    C = PublicKey.from_secret(x_bytes)
    commitment_hex = C.format(compressed=True).hex()

    r = int.from_bytes(os.urandom(32), "big") % GROUP_ORDER_INT
    if r == 0:
        r = 1
    r_bytes = r.to_bytes(32, "big")
    R = PublicKey.from_secret(r_bytes)
    R_hex = R.format(compressed=True).hex()

    e = _challenge(R_hex, commitment_hex, prev_key_hash)
    if e == 0:
        raise ValueError("Fiat-Shamir challenge was zero")
    s = (r - e * x) % GROUP_ORDER_INT
    if s == 0:
        raise ValueError("proof scalar s was zero")
    s_hex = s.to_bytes(32, "big").hex()
    proof = {"commitment": commitment_hex, "R": R_hex, "s": s_hex}
    if not verify_proof(commitment_hex, R_hex, s_hex, prev_key_hash=prev_key_hash):
        raise ValueError("generated proof failed verification")
    return proof
