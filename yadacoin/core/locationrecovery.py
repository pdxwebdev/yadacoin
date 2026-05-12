"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 - for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.
"""

"""
Location-recovery zero-knowledge proof verifier (Python / consensus side).

The wallet UI generates a non-interactive Schnorr proof of knowledge of the
witness scalar derived from the user's three secret locations.  This module
mirrors the verifier in ``plugins/yadacoinwallet/ui/src/composables/useLocationRecovery.js``
so blockchain nodes can verify a ``{"recovers": ...}`` proof embedded in a
transaction's ``relationship`` field.

Schnorr proof (no trusted setup):

    Public:   C = x.G   (commitment)
              prev_key_hash  (binds proof to a specific key log entry)
    Prove:    r <- random
              R = r.G
              e = SHA-256(R || C || prev_key_hash_or_zeros)   [Fiat-Shamir]
              s = r - e*x  mod N
    Verify:   e' = SHA-256(R || C || prev_key_hash_or_zeros)
              s.G + e'.C == R

Implementation notes
--------------------
* All point arithmetic is delegated to ``coincurve`` (libsecp256k1).
* The proof points (``commitment`` and ``R``) MUST be supplied as 33-byte
  compressed secp256k1 points hex-encoded.  The verifier rejects malformed
  encodings, the point at infinity, and out-of-range scalars.
* ``prev_key_hash`` is the previous KEL tip's ``public_key_hash`` (a
  P2PKHBitcoinAddress base58 string).  It is hashed in raw UTF-8 form so the
  verifier never has to know the address codec.
"""

from hashlib import sha256

from coincurve import PublicKey
from coincurve.utils import GROUP_ORDER_INT

# Public secp256k1 group order, exposed for callers that want to validate
# scalars before constructing a proof.
CURVE_N: int = GROUP_ORDER_INT


def _hex_to_bytes(value: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError("hex value must be a string")
    if len(value) % 2 != 0:
        raise ValueError("hex value must have even length")
    return bytes.fromhex(value)


def _scalar_to_bytes32(scalar: int) -> bytes:
    return scalar.to_bytes(32, "big")


def _challenge(R_hex: str, commitment_hex: str, prev_key_hash) -> int:
    """Fiat-Shamir challenge ``e = SHA-256(R || C || prev_key_hash_or_zeros) mod N``.

    ``prev_key_hash`` is treated as raw UTF-8 bytes so the same hash can be
    reproduced trivially on both sides without parsing the address.  When
    ``None`` or empty a 32-byte zero block is used (matches the JS verifier).
    """
    R_bytes = _hex_to_bytes(R_hex)
    C_bytes = _hex_to_bytes(commitment_hex)
    if prev_key_hash:
        prev_bytes = prev_key_hash.encode("utf-8")
    else:
        prev_bytes = b"\x00" * 32
    digest = sha256(R_bytes + C_bytes + prev_bytes).digest()
    return int.from_bytes(digest, "big") % CURVE_N


def verify_proof(
    commitment_hex: str,
    R_hex: str,
    s_hex: str,
    prev_key_hash: str = None,
) -> bool:
    """Verify a Schnorr proof of knowledge of the location-derived witness.

    Parameters
    ----------
    commitment_hex : 33-byte compressed point ``C = x.G`` as hex
    R_hex          : 33-byte compressed point ``R = r.G`` as hex
    s_hex          : 32-byte scalar ``s`` as hex
    prev_key_hash  : previous KEL tip's ``public_key_hash`` (or None)

    Returns
    -------
    bool : True when the proof is valid, False otherwise.

    Any malformed input or curve-arithmetic failure returns False rather than
    raising, so callers can treat verification as a simple boolean predicate.
    """
    try:
        s_bytes = _hex_to_bytes(s_hex)
        if len(s_bytes) != 32:
            return False
        s = int.from_bytes(s_bytes, "big")
        if s == 0 or s >= CURVE_N:
            return False

        C = PublicKey(_hex_to_bytes(commitment_hex))
        R = PublicKey(_hex_to_bytes(R_hex))

        e = _challenge(R_hex, commitment_hex, prev_key_hash)
        if e == 0:
            return False

        # s.G  via PublicKey.from_secret (rejects 0)
        sG = PublicKey.from_secret(s_bytes)
        # e.C
        eC = C.multiply(_scalar_to_bytes32(e))
        # s.G + e.C
        lhs = PublicKey.combine_keys([sG, eC])

        return lhs.format(compressed=True) == R.format(compressed=True)
    except Exception:
        return False
