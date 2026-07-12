"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Identity announcements — embedded in KEL inception transactions.

Relationship field layout
--------------------------

Inception:
    {"identity": {"username": "...", ...}}

Uniqueness contract
-------------------
``username`` MUST be unique across the entire chain and the mempool.
``Transaction.verify()`` enforces this.  Blank usernames are rejected at
startup and during validation.
"""

import base64
from enum import Enum
from typing import Optional

from coincurve import verify_signature


def is_valid_dns_username(username: str) -> bool:
    """Return True if ``username`` is a valid lower-case DNS domain name.

    Delegates the domain-format check to the ``validators`` library (already a
    project dependency).  ``validators.domain`` does not restrict the TLD, but
    it is case-insensitive, so an explicit lower-case check is added here.
    """
    if not username or username != username.lower():
        return False
    import validators

    return bool(validators.domain(username))


class IdentityType(str, Enum):
    """Type of identity announced at inception."""

    DNS = "dns"
    IPFS = "ipfs"
    TOR = "tor"
    EMAIL = "email"
    DID = "did"
    SOCIAL = "social"


class IdentityAnnouncement:
    """Node identity announcement stored once at inception under the ``"identity"`` key."""

    RELATIONSHIP_KEY = "identity"

    def __init__(
        self,
        username: str,
        username_signature: str,
        identity_type: str = IdentityType.DNS.value,
    ):
        if not username or not username.strip():
            raise ValueError("username is required and must not be blank")
        if not username_signature:
            raise ValueError("username_signature is required")
        if identity_type not in {t.value for t in IdentityType}:
            raise ValueError(
                f"identity_type must be one of {[t.value for t in IdentityType]}"
            )

        # A DNS identity must be a valid lower-case domain name.  If the
        # username does not satisfy that, downgrade the announcement to a
        # social identity instead of rejecting outright.
        if identity_type == IdentityType.DNS.value and not is_valid_dns_username(
            username
        ):
            identity_type = IdentityType.SOCIAL.value

        self.username = username.strip()
        self.username_signature = username_signature
        self.identity_type = identity_type

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        d = {
            "username": self.username,
            "username_signature": self.username_signature,
            "identity_type": self.identity_type,
        }
        return d

    def to_string(self) -> str:
        """String used for hashing / signing purposes (minimal fields only)."""
        return (
            self.get_string(self.username)
            + self.get_string(self.username_signature)
            + self.get_string(self.identity_type)
        )

    @staticmethod
    def get_string(value) -> str:
        """Helper to safely convert value to string (add if not already present)."""
        if isinstance(value, (int, float)):
            return str(value)
        return str(value) if value is not None else ""

    @staticmethod
    def from_dict(data: dict) -> "IdentityAnnouncement":
        """Create from the inner dict (the value of the ``"identity"`` key)."""
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        required = {"username", "username_signature"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
        return IdentityAnnouncement(
            username=data["username"],
            username_signature=data["username_signature"],
            identity_type=data.get("identity_type", IdentityType.DNS.value),
        )

    @staticmethod
    def from_relationship(rel: dict) -> "IdentityAnnouncement":
        """Create from the full relationship dict (must have an ``"identity"`` key)."""
        if IdentityAnnouncement.RELATIONSHIP_KEY not in rel:
            raise ValueError("relationship does not contain an 'identity' key")
        ia = IdentityAnnouncement.from_dict(rel[IdentityAnnouncement.RELATIONSHIP_KEY])
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

    async def verify(self, public_key: str, exclude_txn_sig: str = "") -> None:
        """Validate this identity announcement during transaction verification.

        Performs, in order: username-signature check against ``public_key``,
        blank-username rejection, DNS-domain enforcement for ``dns`` identities,
        and chain/mempool username-uniqueness.  Raises
        ``InvalidTransactionException`` on the first failure.
        """
        from yadacoin.core.transaction import InvalidTransactionException

        if not self.verify_username_signature(public_key):
            raise InvalidTransactionException(
                "Identity announcement: username_signature does not match public_key"
            )
        if not self.username:
            raise InvalidTransactionException(
                "Identity announcement: username must not be blank"
            )
        if self.identity_type == IdentityType.DNS.value and not is_valid_dns_username(
            self.username
        ):
            raise InvalidTransactionException(
                f"Identity announcement: username '{self.username}' is not a "
                f"valid DNS domain for a 'dns' identity type"
            )
        already_claimed = await IdentityAnnouncement.exists_username(
            self.username,
            exclude_txn_sig=exclude_txn_sig,
        )
        if already_claimed:
            raise InvalidTransactionException(
                f"Identity announcement: username '{self.username}' is already claimed"
            )

    # ------------------------------------------------------------------
    # Chain / mempool lookup
    # ------------------------------------------------------------------

    @staticmethod
    async def get_by_transaction_id(
        txn_id: str, include_mempool: bool = True, config=None
    ) -> Optional[dict]:
        """Return the inception transaction dict for the given transaction id
        (``transaction_signature``), or None.

        Searches confirmed blocks first, then the mempool if
        ``include_mempool`` is True.  The result mirrors ``get_by_username``::

            {
                "public_key": <K0 public key of the inception txn>,
                "identity": {username, username_signature, identity_type, ...},
                "source": "blockchain" | "mempool",
                "txn": <full txn dict>,
            }
        """
        from yadacoin.core.config import Config

        if config is None:
            config = Config()

        doc = await config.mongo.async_db.miner_transactions.find_one(
            {"id": txn_id}, {"_id": 0}
        )
        if doc:
            identity_data = (doc.get("relationship") or {}).get("identity") or {}
            return {
                "public_key": doc.get("public_key", ""),
                "identity": identity_data,
                "source": "mempool",
                "txn": doc,
            }

        if not include_mempool:
            return None

        pipeline = [
            {"$match": {"transactions.id": txn_id}},
            {"$unwind": "$transactions"},
            {"$match": {"transactions.id": txn_id}},
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

        return None

    @staticmethod
    async def get_by_username(
        username: str, include_mempool: bool = True
    ) -> Optional[dict]:
        """Return the inception transaction dict for a given username, or None.

        Searches confirmed blocks first, then the mempool if
        ``include_mempool`` is True.
        """
        from yadacoin.core.config import Config

        config = Config()

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
