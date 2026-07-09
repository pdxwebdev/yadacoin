"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Identity and rotation announcements — embedded in KEL inception / rotation transactions.

Relationship field layout
--------------------------

Inception (secp256k1 — default):
    {"identity": {"username": "...", "host": "...", ...}}
    Key rotation is tracked via the transaction's own prerotated_key_hash /
    twice_prerotated_key_hash fields.  No "rotation" sibling needed.

Inception (secp256r1 — enterprise / WebRTC):
    {
      "identity": {"username": "...", "host": "...", ...},
      "rotation": {
          "curve": "secp256r1",
          "public_key": "04...",          ← uncompressed P-256 hex
          "key_hash": "1abc...",          ← Bitcoin-style P2PKH of public_key
          "dtls_fingerprint": "sha-256:AB:CD:..."   ← WebRTC DTLS fingerprint
      }
    }
    ``identity`` is recorded exactly once (inception).
    ``rotation`` is present for secp256r1 nodes; for secp256k1 it is omitted.

Subsequent rotation (secp256r1 only):
    {"rotation": {"curve": "secp256r1", "public_key": "04new...", ...}}
    Identity is not repeated — look it up from the inception transaction.

Uniqueness contract
-------------------
``username`` MUST be unique across the entire chain and the mempool.
``Transaction.verify()`` enforces this.  Blank usernames are rejected at
startup and during validation.
"""

import base64
import datetime
import json
from typing import Optional

from coincurve import verify_signature

# ---------------------------------------------------------------------------
# RotationAnnouncement
# ---------------------------------------------------------------------------


class RotationAnnouncement:
    """Optional rotation key announcement embedded alongside (or instead of)
    an IdentityAnnouncement in the transaction relationship field.

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
        self.extra_fields = {k: v for k, v in kwargs.items()}

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
        d.update(self.extra_fields)
        return d

    def to_string(self) -> str:
        return json.dumps({self.RELATIONSHIP_KEY: self.to_dict()}, sort_keys=True)

    def to_relationship(self) -> dict:
        return {self.RELATIONSHIP_KEY: self.to_dict()}

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
        # Verify key_hash = HASH160(public_key) — computed without secp256k1 validation
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
        # Bitcoin-style address (P2PKH) using raw HASH160 to avoid secp256k1 validation
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


class IdentityAnnouncement:
    """Node identity announcement stored once at inception under the ``"identity"`` key.
    Optionally accompanied by a ``RotationAnnouncement`` sibling for secp256r1 nodes.
    """

    RELATIONSHIP_KEY = "identity"

    def __init__(
        self,
        username: str,
        username_signature: str,
        host: str,
        port: int,
        http_protocol: str = "https",
        http_port: int = 443,
        peer_type: str = "service_provider",
        rotation: "Optional[RotationAnnouncement]" = None,
        **kwargs,
    ):
        if not username or not username.strip():
            raise ValueError("username is required and must not be blank")
        if not username_signature:
            raise ValueError("username_signature is required")
        if not host:
            raise ValueError("host is required")
        if port is None:
            raise ValueError("port is required")

        self.username = username.strip()
        self.username_signature = username_signature
        self.host = str(host)
        self.port = int(port)
        self.http_protocol = str(http_protocol).strip().lower() or "https"
        self.http_port = int(http_port) if http_port is not None else 443
        self.peer_type = str(peer_type) if peer_type else "service_provider"
        self.rotation: Optional[RotationAnnouncement] = rotation  # secp256r1 only
        self.extra_fields = {k: v for k, v in kwargs.items()}

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        d = {
            "username": self.username,
            "username_signature": self.username_signature,
            "host": self.host,
            "port": self.port,
            "http_protocol": self.http_protocol,
            "http_port": self.http_port,
            "peer_type": self.peer_type,
        }
        d.update(self.extra_fields)
        return d

    def to_string(self) -> str:
        return json.dumps(self.to_relationship(), sort_keys=True)

    def to_relationship(self) -> dict:
        """Return the full relationship dict ready to set on a Transaction."""
        d = {self.RELATIONSHIP_KEY: self.to_dict()}
        if self.rotation:
            d[RotationAnnouncement.RELATIONSHIP_KEY] = self.rotation.to_dict()
        return d

    @staticmethod
    def from_dict(data: dict) -> "IdentityAnnouncement":
        """Create from the inner dict (the value of the ``"identity"`` key)."""
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        required = {"username", "username_signature", "host", "port"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
        return IdentityAnnouncement(**data)

    @staticmethod
    def from_relationship(rel: dict) -> "IdentityAnnouncement":
        """Create from the full relationship dict (must have an ``"identity"`` key).
        Also parses the optional ``"rotation"`` sibling for secp256r1 nodes."""
        if IdentityAnnouncement.RELATIONSHIP_KEY not in rel:
            raise ValueError("relationship does not contain an 'identity' key")
        ia = IdentityAnnouncement.from_dict(rel[IdentityAnnouncement.RELATIONSHIP_KEY])
        if RotationAnnouncement.RELATIONSHIP_KEY in rel:
            try:
                ia.rotation = RotationAnnouncement.from_dict(
                    rel[RotationAnnouncement.RELATIONSHIP_KEY]
                )
            except (ValueError, TypeError):
                pass
        return ia

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def verify_username_signature(self, public_key_hex: str) -> bool:
        """Return True if ``username_signature`` is a valid signature of
        ``username`` by the private key corresponding to ``public_key_hex``."""
        try:
            return verify_signature(
                base64.b64decode(self.username_signature),
                self.username.encode("utf-8"),
                bytes.fromhex(public_key_hex),
            )
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Chain / mempool lookup
    # ------------------------------------------------------------------

    @staticmethod
    async def get_by_username(
        username: str, include_mempool: bool = True
    ) -> Optional[dict]:
        """Return the inception transaction dict for a given username, or None.

        Searches confirmed blocks first, then the mempool if
        ``include_mempool`` is True.

        The returned dict has at minimum:
            ``public_key``   — the K0 public key (inception signer)
            ``identity``     — the IdentityAnnouncement inner dict
            ``source``       — ``"blockchain"`` or ``"mempool"``
        """
        from yadacoin.core.config import Config

        config = Config()

        # Build the query: relationship.identity.username == username
        query = {
            "transactions.relationship.identity.username": username,
        }

        # Check blockchain first
        pipeline = [
            {"$match": query},
            {"$unwind": "$transactions"},
            {"$match": {"transactions.relationship.identity.username": username}},
            {"$replaceRoot": {"newRoot": "$transactions"}},
            {"$limit": 1},
        ]
        async for doc in config.mongo.async_db.blocks.aggregate(pipeline):
            identity_data = (doc.get("relationship") or {}).get("identity") or {}
            return {
                "public_key": doc.get("public_key", ""),
                "identity": identity_data,
                "source": "blockchain",
                "txn": doc,
            }

        if not include_mempool:
            return None

        # Fall back to mempool
        doc = await config.mongo.async_db.miner_transactions.find_one(
            {"relationship.identity.username": username}, {"_id": 0}
        )
        if doc:
            identity_data = (doc.get("relationship") or {}).get("identity") or {}
            return {
                "public_key": doc.get("public_key", ""),
                "identity": identity_data,
                "source": "mempool",
                "txn": doc,
            }

        return None

    @staticmethod
    async def exists_username(
        username: str,
        exclude_txn_sig: str = "",
        config=None,
    ) -> bool:
        """Return True if ``username`` is already claimed on-chain or in the
        mempool (optionally excluding the transaction with
        ``exclude_txn_sig``).
        """
        from yadacoin.core.config import Config

        if config is None:
            config = Config()

        base_query = {"relationship.identity.username": username}

        # Check blockchain
        chain_query = {"transactions.relationship.identity.username": username}
        if exclude_txn_sig:
            chain_query["transactions.id"] = {"$ne": exclude_txn_sig}
        result = await config.mongo.async_db.blocks.find_one(chain_query)
        if result:
            return True

        # Check mempool
        mempool_query = dict(base_query)
        if exclude_txn_sig:
            mempool_query["id"] = {"$ne": exclude_txn_sig}
        result = await config.mongo.async_db.miner_transactions.find_one(mempool_query)
        return bool(result)
