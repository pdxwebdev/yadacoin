"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import json

from yadacoin.core.identity import Identity


class NodeAnnouncement:
    """Represents a node announcement in a transaction relationship field.

    Similar to Contract, this class provides structure and validation for node
    announcements that are stored on-chain.
    """

    def __init__(self, identity, host, port, **kwargs):
        """Initialize a node announcement.

        Args:
            identity: Dict containing public_key, username, username_signature
            host: IP address or hostname of the node
            port: Port number the node listens on
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

        # Store any additional fields for forward compatibility
        self.extra_fields = {
            k: v for k, v in kwargs.items() if k not in ["identity", "host", "port"]
        }

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
        }

        # Include any extra fields
        if self.extra_fields:
            result.update(self.extra_fields)

        return result

    def to_string(self):
        """Convert to JSON string for hashing.

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def __repr__(self):
        return f"NodeAnnouncement(host={self.host}, port={self.port}, public_key={self.identity.public_key[:8]}...)"
