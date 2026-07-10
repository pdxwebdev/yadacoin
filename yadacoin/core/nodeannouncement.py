"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from yadacoin.core.identity import Identity


class NodeAnnouncement:
    """Represents a node announcement in a transaction relationship field.

    Similar to Contract, this class provides structure and validation for node
    announcements that are stored on-chain.

    A node announcement carries either an inline ``identity`` dict (legacy) or an
    ``identity_announcement`` — the transaction id of the on-chain identity
    announcement (KEL inception) that anchors the node's identity.  When only
    ``identity_announcement`` is present the concrete ``identity`` is resolved
    lazily via :meth:`resolve_identity_announcement` (the same mechanism used for
    bootstrap nodes configured in ``nodes.py``).
    """

    RELATIONSHIP_KEY = "node"

    def __init__(
        self,
        identity=None,
        host=None,
        port=None,
        identity_announcement=None,
        http_host="",
        http_port=None,
        http_protocol="https",
        collateral_address="",
        **kwargs,
    ):
        """Initialize a node announcement.

        Args:
            identity: Dict containing public_key, username, username_signature
                (legacy).  Optional when ``identity_announcement`` is supplied.
            host: IP address or hostname of the node
            port: Port number the node listens on
            identity_announcement: Transaction id of the on-chain identity
                announcement that anchors this node's identity.
            http_host: HTTP hostname for the node
            http_port: HTTP port for the node
            http_protocol: 'http' or 'https'
            collateral_address: Collateral address for the node
            **kwargs: Additional fields (for forward compatibility)
        """
        if identity is None and not identity_announcement:
            raise ValueError("either identity or identity_announcement is required")

        # Validate required arguments before processing
        if host is None:
            raise ValueError("host is required")

        if port is None:
            raise ValueError("port is required")

        self.identity = None
        if identity is not None:
            if not isinstance(identity, dict):
                raise ValueError("identity must be a dict")

            if not identity.get("public_key"):
                raise ValueError("identity.public_key is required")

            if not identity.get("username_signature"):
                raise ValueError("identity.username_signature is required")

            try:
                self.identity = Identity.from_dict(identity)
            except Exception as e:
                raise ValueError(f"Invalid identity structure: {e}")

        self.identity_announcement = identity_announcement

        self.host = str(host)
        try:
            self.port = int(port)
        except (ValueError, TypeError):
            raise ValueError("port must be a valid integer")

        self.http_host = str(http_host) if http_host else ""
        self.http_port = int(http_port) if http_port is not None else None
        self.http_protocol = (
            str(http_protocol).strip().lower() if http_protocol else "https"
        )
        self.collateral_address = str(collateral_address) if collateral_address else ""

        # Store any unrecognised fields for forward compatibility
        self.extra_fields = {k: v for k, v in kwargs.items()}

    @staticmethod
    def from_dict(data):
        """Create a NodeAnnouncement from a dictionary.

        Args:
            data: Dict containing node announcement data

        Returns:
            NodeAnnouncement instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")

        # Validate required fields before attempting instantiation
        if "identity" not in data and "identity_announcement" not in data:
            raise ValueError("identity or identity_announcement field is required")
        if "host" not in data:
            raise ValueError("host field is required")
        if "port" not in data:
            raise ValueError("port field is required")

        return NodeAnnouncement(**data)

    async def resolve_identity_announcement(self) -> bool:
        """Populate ``self.identity`` (and ``self.anchor_public_key``) from the
        on-chain identity announcement referenced by ``identity_announcement``.

        Returns True if no resolution was needed or it succeeded; False if a
        configured ``identity_announcement`` could not be found on-chain.
        """
        if self.identity is not None:
            return True
        ia_id = getattr(self, "identity_announcement", None)
        if not ia_id:
            return True
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        result = await IdentityAnnouncement.get_by_transaction_id(ia_id)
        if not result:
            return False
        identity_data = result.get("identity") or {}
        self.identity = Identity(
            public_key=result.get("public_key", ""),
            username=identity_data.get("username", "") or "",
            username_signature=identity_data.get("username_signature", "") or "",
        )
        self.anchor_public_key = result.get("public_key") or None
        return True

    def to_dict(self):
        """Convert to dictionary representation.

        Returns:
            Dict containing node announcement data
        """
        result = {
            "host": self.host,
            "port": self.port,
            "http_host": self.http_host,
            "http_port": self.http_port,
            "http_protocol": self.http_protocol,
            "collateral_address": self.collateral_address,
        }
        # New-format announcements reference the on-chain identity announcement;
        # legacy announcements carry the inline identity dict.
        if self.identity_announcement:
            result["identity_announcement"] = self.identity_announcement
        if self.identity is not None:
            result["identity"] = self.identity.to_dict

        # Include any unrecognised extra fields
        if self.extra_fields:
            result.update(self.extra_fields)

        return result

    def get_string(self, p):
        return "" if p is None else str(p)

    def to_string(self):
        return (
            self.get_string(self.identity.username_signature if self.identity else "")
            + self.get_string(self.host)
            + self.get_string(self.port)
            + self.get_string(self.http_host)
            + self.get_string(self.http_port)
            + self.get_string(self.http_protocol)
            + self.get_string(self.collateral_address)
        )

    def __repr__(self):
        pub = (
            self.identity.public_key[:8]
            if self.identity
            else (self.identity_announcement or "")[:8]
        )
        return (
            f"NodeAnnouncement(host={self.host}, port={self.port}, public_key={pub}...)"
        )
