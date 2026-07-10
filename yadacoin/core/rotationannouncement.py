"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Rotation announcements — embedded in KEL rotation transactions.

For secp256k1 nodes the rotation announcement is omitted entirely — the
transaction's own ``prerotated_key_hash`` / ``twice_prerotated_key_hash``
fields carry the rotation pre-commitment.

For secp256r1 (P-256) nodes the rotation announcement must be present and
carries the current P-256 public key, its Bitcoin-style key hash, and the
DTLS fingerprint of the self-signed certificate derived from that key.
This enables WebRTC data-channel connections with blockchain-rooted trust.
"""

import datetime

# ---------------------------------------------------------------------------
# RotationAnnouncement
# ---------------------------------------------------------------------------


class RotationAnnouncement:
    """Rotation key announcement for secp256r1 (P-256) nodes.

    For secp256k1 nodes the rotation announcement is omitted entirely — the
    transaction's own ``prerotated_key_hash`` / ``twice_prerotated_key_hash``
    fields carry the rotation pre-commitment.

    For secp256r1 (P-256) nodes the rotation announcement must be present and
    carries the current P-256 public key, its Bitcoin-style key hash, and the
    DTLS fingerprint of the self-signed certificate derived from that key.
    This enables WebRTC data-channel connections with blockchain-rooted trust.
    """

    RELATIONSHIP_KEY = "rotation"
    SUPPORTED_CURVES = ("secp256k1", "secp256r1")

    def __init__(
        self,
        curve: str = "secp256k1",
        public_key: str = "",
        key_hash: str = "",
        dtls_fingerprint: str = "",
        **kwargs,
    ):
        if curve not in self.SUPPORTED_CURVES:
            raise ValueError(
                f"unsupported curve '{curve}'; must be one of {self.SUPPORTED_CURVES}"
            )
        self.curve = curve
        self.public_key = public_key  # uncompressed P-256 hex (secp256r1 only)
        self.key_hash = key_hash  # Bitcoin-style P2PKH of public_key
        self.dtls_fingerprint = dtls_fingerprint  # "sha-256:AB:CD:..." (WebRTC)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        d: dict = {"curve": self.curve}
        if self.public_key:
            d["public_key"] = self.public_key
        if self.key_hash:
            d["key_hash"] = self.key_hash
        if self.dtls_fingerprint:
            d["dtls_fingerprint"] = self.dtls_fingerprint
        return d

    @staticmethod
    def get_string(value) -> str:
        """Helper to safely convert value to string for concatenation."""
        if value is None:
            return ""
        return str(value)

    def to_string(self) -> str:
        """Hard-coded deterministic string for hashing/signing.
        Fields are concatenated in this exact order:
        curve + public_key + key_hash + dtls_fingerprint
        """
        return (
            self.get_string(self.curve)
            + self.get_string(self.public_key)
            + self.get_string(self.key_hash)
            + self.get_string(self.dtls_fingerprint)
        )

    @staticmethod
    def from_dict(data: dict) -> "RotationAnnouncement":
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        return RotationAnnouncement(**data)

    @staticmethod
    def from_relationship(rel: dict) -> "RotationAnnouncement":
        if RotationAnnouncement.RELATIONSHIP_KEY not in rel:
            raise ValueError("relationship does not contain a 'rotation' key")
        return RotationAnnouncement.from_dict(
            rel[RotationAnnouncement.RELATIONSHIP_KEY]
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_p256(self) -> bool:
        """Return True if the P-256 key, key_hash, and dtls_fingerprint are
        mutually consistent.  Raises ValueError on failure."""
        if self.curve != "secp256r1":
            return True  # secp256k1 has no inline key material to validate

        if not self.public_key:
            raise ValueError(
                "RotationAnnouncement: secp256r1 rotation requires public_key"
            )

        # Verify key_hash = P2PKH(public_key)
        try:
            pub_bytes = bytes.fromhex(self.public_key)
        except ValueError:
            raise ValueError("RotationAnnouncement: public_key is not valid hex")

        import hashlib as _hl

        from bitcoin.base58 import encode as _b58encode

        from yadacoin.core.crypt import RIPEMD160

        ripemd_digest = RIPEMD160.ripemd160(pub_bytes)
        versioned = b"\x00" + ripemd_digest
        checksum = _hl.sha256(_hl.sha256(versioned).digest()).digest()[:4]
        expected_hash = _b58encode(versioned + checksum)

        if self.key_hash and self.key_hash != expected_hash:
            raise ValueError(
                f"RotationAnnouncement: key_hash {self.key_hash!r} does not match "
                f"P2PKH of public_key ({expected_hash})"
            )
        return True

    # ------------------------------------------------------------------
    # P-256 key derivation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def derive_p256_from_k0(k0_private_bytes: bytes) -> "RotationAnnouncement":
        """Deterministically derive a secp256r1 key from K0 via HKDF and
        return a RotationAnnouncement populated with the public key, key hash,
        and self-signed DTLS fingerprint."""
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.x509.oid import NameOID

        # Derive a P-256 private scalar via HKDF so it's independent of K0
        seed = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"yadacoin-p256-identity",
            info=b"",
        ).derive(k0_private_bytes)

        scalar = int.from_bytes(seed, "big")
        if scalar == 0:
            scalar = 1  # astronomically unlikely but guard anyway  # pragma: no cover
        p256_priv = ec.derive_private_key(scalar, SECP256R1())
        p256_pub = p256_priv.public_key()

        # Uncompressed public key hex (04 || x || y, 65 bytes)
        pub_bytes = p256_pub.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        pub_hex = pub_bytes.hex()

        # Bitcoin-style address (P2PKH) of the uncompressed key
        import hashlib as _hl

        from bitcoin.base58 import encode as _b58encode

        from yadacoin.core.crypt import RIPEMD160

        ripemd_digest = RIPEMD160.ripemd160(pub_bytes)
        versioned = b"\x00" + ripemd_digest
        checksum = _hl.sha256(_hl.sha256(versioned).digest()).digest()[:4]
        key_hash = _b58encode(versioned + checksum)

        # Self-signed DTLS certificate and its SHA-256 fingerprint
        cert = (
            x509.CertificateBuilder()
            .subject_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "yadacoin-node")])
            )
            .issuer_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "yadacoin-node")])
            )
            .public_key(p256_pub)
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=36500)
            )
            .sign(p256_priv, hashes.SHA256())
        )
        fp = cert.fingerprint(hashes.SHA256())
        dtls_fingerprint = "sha-256:" + ":".join(f"{b:02X}" for b in fp)

        return RotationAnnouncement(
            curve="secp256r1",
            public_key=pub_hex,
            key_hash=key_hash,
            dtls_fingerprint=dtls_fingerprint,
        )
