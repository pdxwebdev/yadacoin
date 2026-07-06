"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from yadacoin.core.identity import Identity


class AgentAnnouncement:
    """Represents an AI agent registration in a transaction relationship field.

    Similar to NodeAnnouncement, this class provides structure and validation
    for agent registrations stored on-chain, enabling agent discovery.

    On-chain format: {"agent": <to_dict()>}

    Fields
    ------
    identity       : registrant identity (public_key, username, username_signature)
    agent_id       : deterministic unique ID — sha256(public_key + label)[:16]
    label          : human-readable agent name
    description    : what the agent does
    capabilities   : list of intent keywords (e.g. ["travel", "flight", "hotel"])
    endpoint_url   : base URL where the agent API is accessible
    agent_type     : agent type id matching the AGENT_TYPES registry
    icon           : emoji/icon string (optional, default "🤖")
    version        : semver string (optional, default "1.0")
    """

    RELATIONSHIP_KEY = "agent"

    def __init__(
        self,
        identity,
        agent_id,
        label,
        description,
        capabilities,
        endpoint_url,
        agent_type="general",
        icon="🤖",
        version="1.0",
        **kwargs,
    ):
        if identity is None:
            raise ValueError("identity is required")
        if not isinstance(identity, dict):
            raise ValueError("identity must be a dict")
        if not identity.get("public_key"):
            raise ValueError("identity.public_key is required")
        if not identity.get("username_signature"):
            raise ValueError("identity.username_signature is required")
        if not agent_id:
            raise ValueError("agent_id is required")
        if not label:
            raise ValueError("label is required")
        if not endpoint_url:
            raise ValueError("endpoint_url is required")

        try:
            self.identity = Identity.from_dict(identity)
        except Exception as e:
            raise ValueError(f"Invalid identity structure: {e}")

        self.agent_id = str(agent_id)
        self.label = str(label)
        self.description = str(description) if description else ""
        self.capabilities = sorted(list(capabilities)) if capabilities else []
        self.endpoint_url = str(endpoint_url).rstrip("/")
        self.agent_type = str(agent_type) if agent_type else "general"
        self.icon = str(icon) if icon else "🤖"
        self.version = str(version) if version else "1.0"

        # Store unrecognised fields for forward compatibility
        self.extra_fields = {k: v for k, v in kwargs.items()}

    @staticmethod
    def from_dict(data):
        """Create an AgentAnnouncement from a dictionary.

        Args:
            data: Dict containing agent announcement data

        Returns:
            AgentAnnouncement instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        for field in ("identity", "agent_id", "label", "endpoint_url"):
            if field not in data:
                raise ValueError(f"{field} field is required")
        return AgentAnnouncement(**data)

    def to_dict(self):
        """Convert to dictionary representation for on-chain storage."""
        result = {
            "identity": self.identity.to_dict,  # to_dict is a property on Identity
            "agent_id": self.agent_id,
            "label": self.label,
            "description": self.description,
            "capabilities": self.capabilities,
            "endpoint_url": self.endpoint_url,
            "agent_type": self.agent_type,
            "icon": self.icon,
            "version": self.version,
        }
        if self.extra_fields:
            result.update(self.extra_fields)
        return result

    def get_string(self, p):
        return "" if p is None else str(p)

    def to_string(self):
        """Deterministic string for relationship hashing."""
        return (
            self.get_string(self.identity.username_signature)
            + self.get_string(self.agent_id)
            + self.get_string(self.label)
            + ",".join(self.capabilities)
            + self.get_string(self.endpoint_url)
        )

    def __repr__(self):
        return (
            f"AgentAnnouncement(agent_id={self.agent_id!r}, "
            f"label={self.label!r}, "
            f"public_key={self.identity.public_key[:8]}...)"
        )
