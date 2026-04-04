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
    """

    def __init__(
        self,
        identity,
        host,
        port,
        http_host="",
        http_port=None,
        http_protocol="https",
        collateral_address="",
        **kwargs,
    ):
        """Initialize a node announcement.

        Args:
            identity: Dict containing public_key, username, username_signature
            host: IP address or hostname of the node
            port: Port number the node listens on
            http_host: HTTP hostname for the node
            http_port: HTTP port for the node
            http_protocol: 'http' or 'https'
            collateral_address: Collateral address for the node
            **kwargs: Additional fields (for forward compatibility)
        """
        # Validate required arguments before processing
        if identity is None:
            raise ValueError("identity is required")

        if not isinstance(identity, dict):
            raise ValueError("identity must be a dict")

        if not identity.get("public_key"):
            raise ValueError("identity.public_key is required")

        if not identity.get("username_signature"):
            raise ValueError("identity.username_signature is required")

        if host is None:
            raise ValueError("host is required")

        if port is None:
            raise ValueError("port is required")

        try:
            self.identity = Identity.from_dict(identity)
        except Exception as e:
            raise ValueError(f"Invalid identity structure: {e}")

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
        if "identity" not in data:
            raise ValueError("identity field is required")
        if "host" not in data:
            raise ValueError("host field is required")
        if "port" not in data:
            raise ValueError("port field is required")

        return NodeAnnouncement(**data)

    def to_dict(self):
        """Convert to dictionary representation.

        Returns:
            Dict containing node announcement data
        """
        result = {
            "identity": self.identity.to_dict,  # to_dict is a property, not a method
            "host": self.host,
            "port": self.port,
            "http_host": self.http_host,
            "http_port": self.http_port,
            "http_protocol": self.http_protocol,
            "collateral_address": self.collateral_address,
        }

        # Include any unrecognised extra fields
        if self.extra_fields:
            result.update(self.extra_fields)

        return result

    def get_string(self, p):
        return "" if p is None else str(p)

    def to_string(self):
        return (
            self.get_string(self.identity.username_signature)
            + self.get_string(self.host)
            + self.get_string(self.port)
            + self.get_string(self.http_host)
            + self.get_string(self.http_port)
            + self.get_string(self.http_protocol)
            + self.get_string(self.collateral_address)
        )

    def __repr__(self):
        return f"NodeAnnouncement(host={self.host}, port={self.port}, public_key={self.identity.public_key[:8]}...)"
