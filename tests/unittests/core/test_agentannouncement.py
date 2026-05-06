"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import base64

from yadacoin.core.agentannouncement import AgentAnnouncement
from yadacoin.core.transaction import Transaction

from ..test_setup import AsyncTestCase


class TestAgentAnnouncement(AsyncTestCase):
    """Test suite for AgentAnnouncement class."""

    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.valid_identity = {
            "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
            "username": "test_agent_owner",
            "username_signature": base64.b64encode(b"signature").decode(),
        }

        self.valid_data = {
            "identity": self.valid_identity,
            "agent_id": "abc123def456",
            "label": "Test Agent",
            "description": "A test agent",
            "capabilities": ["travel", "hotel"],
            "endpoint_url": "https://agent.example.com/",
            "agent_type": "travel",
            "icon": "✈️",
            "version": "1.0",
        }

    # ------------------------------------------------------------------ #
    # __init__ validation (lines 51-81)                                   #
    # ------------------------------------------------------------------ #

    async def test_init_identity_none_raises(self):
        """Line 52: identity is None"""
        with self.assertRaises(ValueError) as ctx:
            AgentAnnouncement(
                identity=None,
                agent_id="abc",
                label="L",
                description="D",
                capabilities=[],
                endpoint_url="https://x.com",
            )
        self.assertIn("identity", str(ctx.exception).lower())

    async def test_init_identity_not_dict_raises(self):
        """Line 54: identity not a dict"""
        with self.assertRaises(ValueError) as ctx:
            AgentAnnouncement(
                identity="notadict",
                agent_id="abc",
                label="L",
                description="D",
                capabilities=[],
                endpoint_url="https://x.com",
            )
        self.assertIn("dict", str(ctx.exception).lower())

    async def test_init_identity_missing_public_key_raises(self):
        """Line 56: identity.public_key missing"""
        identity = {
            "username_signature": base64.b64encode(b"sig").decode(),
        }
        with self.assertRaises(ValueError) as ctx:
            AgentAnnouncement(
                identity=identity,
                agent_id="abc",
                label="L",
                description="D",
                capabilities=[],
                endpoint_url="https://x.com",
            )
        self.assertIn("public_key", str(ctx.exception).lower())

    async def test_init_identity_missing_username_signature_raises(self):
        """Line 58: identity.username_signature missing"""
        identity = {
            "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
        }
        with self.assertRaises(ValueError) as ctx:
            AgentAnnouncement(
                identity=identity,
                agent_id="abc",
                label="L",
                description="D",
                capabilities=[],
                endpoint_url="https://x.com",
            )
        self.assertIn("username_signature", str(ctx.exception).lower())

    async def test_init_agent_id_empty_raises(self):
        """Line 60: agent_id empty"""
        with self.assertRaises(ValueError) as ctx:
            AgentAnnouncement(
                identity=self.valid_identity,
                agent_id="",
                label="L",
                description="D",
                capabilities=[],
                endpoint_url="https://x.com",
            )
        self.assertIn("agent_id", str(ctx.exception).lower())

    async def test_init_label_empty_raises(self):
        """Line 62: label empty"""
        with self.assertRaises(ValueError) as ctx:
            AgentAnnouncement(
                identity=self.valid_identity,
                agent_id="abc",
                label="",
                description="D",
                capabilities=[],
                endpoint_url="https://x.com",
            )
        self.assertIn("label", str(ctx.exception).lower())

    async def test_init_endpoint_url_empty_raises(self):
        """Line 64: endpoint_url empty"""
        with self.assertRaises(ValueError) as ctx:
            AgentAnnouncement(
                identity=self.valid_identity,
                agent_id="abc",
                label="L",
                description="D",
                capabilities=[],
                endpoint_url="",
            )
        self.assertIn("endpoint_url", str(ctx.exception).lower())

    async def test_init_invalid_identity_structure_raises(self):
        """Line 68-69: Identity.from_dict raises"""
        identity = {
            "public_key": "not_a_valid_key!!!",
            "username_signature": base64.b64encode(b"sig").decode(),
        }
        with self.assertRaises(ValueError) as ctx:
            AgentAnnouncement(
                identity=identity,
                agent_id="abc",
                label="L",
                description="D",
                capabilities=[],
                endpoint_url="https://x.com",
            )
        self.assertIn("identity", str(ctx.exception).lower())

    async def test_init_valid_stores_fields(self):
        """Lines 71-81: valid construction stores all fields correctly"""
        agent = AgentAnnouncement(**self.valid_data)

        self.assertEqual(agent.agent_id, "abc123def456")
        self.assertEqual(agent.label, "Test Agent")
        self.assertEqual(agent.description, "A test agent")
        self.assertEqual(agent.capabilities, ["hotel", "travel"])  # sorted
        self.assertEqual(
            agent.endpoint_url, "https://agent.example.com"
        )  # trailing slash stripped
        self.assertEqual(agent.agent_type, "travel")
        self.assertEqual(agent.icon, "✈️")
        self.assertEqual(agent.version, "1.0")

    async def test_init_none_optionals_use_defaults(self):
        """Lines 74-79: None optionals fall back to defaults"""
        agent = AgentAnnouncement(
            identity=self.valid_identity,
            agent_id="abc",
            label="L",
            description=None,
            capabilities=None,
            endpoint_url="https://x.com",
            agent_type=None,
            icon=None,
            version=None,
        )
        self.assertEqual(agent.description, "")
        self.assertEqual(agent.capabilities, [])
        self.assertEqual(agent.agent_type, "general")
        self.assertEqual(agent.icon, "🤖")
        self.assertEqual(agent.version, "1.0")

    async def test_init_extra_fields_stored(self):
        """Line 81: extra kwargs stored in extra_fields"""
        agent = AgentAnnouncement(
            **self.valid_data,
            future_field="future_value",
        )
        self.assertEqual(agent.extra_fields["future_field"], "future_value")

    # ------------------------------------------------------------------ #
    # from_dict (lines 96-101)                                            #
    # ------------------------------------------------------------------ #

    async def test_from_dict_not_dict_raises(self):
        """Line 96: data not a dict"""
        with self.assertRaises(ValueError):
            AgentAnnouncement.from_dict("notadict")

    async def test_from_dict_missing_required_field_raises(self):
        """Lines 97-100: missing required field raises ValueError"""
        for field in ("identity", "agent_id", "label", "endpoint_url"):
            data = {**self.valid_data}
            del data[field]
            with self.assertRaises(ValueError) as ctx:
                AgentAnnouncement.from_dict(data)
            self.assertIn(field, str(ctx.exception).lower())

    async def test_from_dict_valid(self):
        """Line 101: valid from_dict returns AgentAnnouncement"""
        agent = AgentAnnouncement.from_dict(self.valid_data)
        self.assertIsInstance(agent, AgentAnnouncement)
        self.assertEqual(agent.agent_id, "abc123def456")

    # ------------------------------------------------------------------ #
    # to_dict (lines 105-118)                                             #
    # ------------------------------------------------------------------ #

    async def test_to_dict_contains_all_fields(self):
        """Lines 105-113: to_dict returns all standard fields"""
        agent = AgentAnnouncement.from_dict(self.valid_data)
        result = agent.to_dict()

        for key in (
            "identity",
            "agent_id",
            "label",
            "description",
            "capabilities",
            "endpoint_url",
            "agent_type",
            "icon",
            "version",
        ):
            self.assertIn(key, result)

        self.assertEqual(result["agent_id"], "abc123def456")
        self.assertEqual(result["label"], "Test Agent")

    async def test_to_dict_includes_extra_fields(self):
        """Lines 115-117: extra_fields merged into to_dict output"""
        agent = AgentAnnouncement.from_dict({**self.valid_data, "bonus": "yes"})
        result = agent.to_dict()
        self.assertEqual(result["bonus"], "yes")

    async def test_to_dict_no_extra_fields(self):
        """Line 114 branch: no extra_fields skips update"""
        agent = AgentAnnouncement.from_dict(self.valid_data)
        self.assertEqual(agent.extra_fields, {})
        result = agent.to_dict()
        self.assertNotIn("bonus", result)

    # ------------------------------------------------------------------ #
    # get_string / to_string (lines 121, 125, 134)                        #
    # ------------------------------------------------------------------ #

    async def test_get_string_none_returns_empty(self):
        """Line 121: get_string(None) returns ''"""
        agent = AgentAnnouncement.from_dict(self.valid_data)
        self.assertEqual(agent.get_string(None), "")

    async def test_get_string_value_returns_str(self):
        """Line 121: get_string(value) returns str(value)"""
        agent = AgentAnnouncement.from_dict(self.valid_data)
        self.assertEqual(agent.get_string(42), "42")

    async def test_to_string_is_deterministic(self):
        """Lines 125-134: to_string returns consistent concatenated string"""
        agent = AgentAnnouncement.from_dict(self.valid_data)
        result = agent.to_string()

        self.assertIsInstance(result, str)
        self.assertIn(agent.agent_id, result)
        self.assertIn(agent.label, result)
        self.assertIn(agent.endpoint_url, result)
        self.assertIn(agent.identity.username_signature, result)
        # capabilities joined with comma
        self.assertIn(",".join(agent.capabilities), result)

    async def test_to_string_empty_capabilities(self):
        """to_string works when capabilities is empty"""
        data = {**self.valid_data, "capabilities": []}
        agent = AgentAnnouncement.from_dict(data)
        result = agent.to_string()
        self.assertIsInstance(result, str)

    async def test_repr(self):
        """Line 134: __repr__ returns expected string"""
        agent = AgentAnnouncement.from_dict(self.valid_data)
        result = repr(agent)
        self.assertIn("AgentAnnouncement", result)
        self.assertIn(agent.agent_id, result)
        self.assertIn(agent.label, result)

    # ------------------------------------------------------------------ #
    # Transaction integration                                             #
    # ------------------------------------------------------------------ #

    async def test_transaction_with_agent_announcement(self):
        """Transaction converts agent dict to AgentAnnouncement instance."""
        txn_dict = {
            "time": 1234567890,
            "id": "test_signature",
            "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
            "hash": "test_hash",
            "relationship": {"agent": self.valid_data},
            "inputs": [],
            "outputs": [],
        }
        txn = Transaction.from_dict(txn_dict)
        self.assertIsInstance(txn.relationship, AgentAnnouncement)
        self.assertEqual(txn.relationship.agent_id, "abc123def456")

    async def test_transaction_to_dict_wraps_agent(self):
        """Transaction.to_dict() wraps AgentAnnouncement under 'agent' key."""
        txn_dict = {
            "time": 1234567890,
            "id": "test_signature",
            "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
            "hash": "test_hash",
            "relationship": {"agent": self.valid_data},
            "inputs": [],
            "outputs": [],
        }
        txn = Transaction.from_dict(txn_dict)
        result = txn.to_dict()
        self.assertIn("agent", result["relationship"])
