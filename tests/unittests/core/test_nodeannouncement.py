"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import base64
import unittest

from yadacoin.core.nodeannouncement import NodeAnnouncement
from yadacoin.core.transaction import Transaction

from ..test_setup import AsyncTestCase


class TestNodeAnnouncement(AsyncTestCase):
    """Test suite for NodeAnnouncement class."""

    async def asyncSetUp(self):
        """Set up test environment."""
        await super().asyncSetUp()

        self.valid_node_data = {
            "identity": {
                "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
                "username": "test_node",
                "username_signature": base64.b64encode(b"signature").decode(),
            },
            "host": "192.168.1.100",
            "port": 8000,
        }

    async def test_create_valid_node_announcement(self):
        """Test creating a valid node announcement."""
        node = NodeAnnouncement.from_dict(self.valid_node_data)

        self.assertEqual(node.host, "192.168.1.100")
        self.assertEqual(node.port, 8000)
        self.assertEqual(
            node.identity.public_key,
            "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
        )
        self.assertEqual(node.identity.username, "test_node")

    async def test_node_announcement_missing_identity(self):
        """Test that missing identity raises error."""
        invalid_data = {
            "host": "192.168.1.100",
            "port": 8000,
        }

        with self.assertRaises(ValueError) as context:
            NodeAnnouncement.from_dict(invalid_data)

        self.assertIn("identity", str(context.exception).lower())

    async def test_node_announcement_missing_public_key(self):
        """Test that missing public key raises error."""
        invalid_data = {
            "identity": {
                "username": "test_node",
                "username_signature": base64.b64encode(b"signature").decode(),
            },
            "host": "192.168.1.100",
            "port": 8000,
        }

        with self.assertRaises(ValueError) as context:
            NodeAnnouncement.from_dict(invalid_data)

        self.assertIn("public_key", str(context.exception).lower())

    async def test_node_announcement_missing_username_signature(self):
        """Test that missing username_signature raises error."""
        invalid_data = {
            "identity": {
                "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
                "username": "test_node",
            },
            "host": "192.168.1.100",
            "port": 8000,
        }

        with self.assertRaises(ValueError) as context:
            NodeAnnouncement.from_dict(invalid_data)

        self.assertIn("username_signature", str(context.exception).lower())

    async def test_node_announcement_missing_host(self):
        """Test that missing host raises error."""
        invalid_data = {
            "identity": self.valid_node_data["identity"],
            "port": 8000,
        }

        with self.assertRaises(ValueError) as context:
            NodeAnnouncement.from_dict(invalid_data)

        self.assertIn("host", str(context.exception).lower())

    async def test_node_announcement_missing_port(self):
        """Test that missing port raises error."""
        invalid_data = {
            "identity": self.valid_node_data["identity"],
            "host": "192.168.1.100",
        }

        with self.assertRaises(ValueError) as context:
            NodeAnnouncement.from_dict(invalid_data)

        self.assertIn("port", str(context.exception).lower())

    async def test_node_announcement_to_dict(self):
        """Test converting node announcement to dict."""
        node = NodeAnnouncement.from_dict(self.valid_node_data)
        result = node.to_dict()

        self.assertIn("identity", result)
        self.assertIn("host", result)
        self.assertIn("port", result)
        self.assertEqual(result["host"], "192.168.1.100")
        self.assertEqual(result["port"], 8000)

    async def test_node_announcement_to_string(self):
        """Test converting node announcement to string."""
        node = NodeAnnouncement.from_dict(self.valid_node_data)
        result = node.to_string()

        # Should be a concatenated string containing the key field values
        self.assertIsInstance(result, str)
        self.assertIn(node.identity.username_signature, result)
        self.assertIn(node.host, result)
        self.assertIn(str(node.port), result)

    async def test_node_announcement_extra_fields(self):
        """Test that extra fields are preserved."""
        data_with_extras = {
            **self.valid_node_data,
            "extra_field": "extra_value",
            "another_field": 123,
        }

        node = NodeAnnouncement.from_dict(data_with_extras)
        result = node.to_dict()

        self.assertEqual(result["extra_field"], "extra_value")
        self.assertEqual(result["another_field"], 123)

    async def test_transaction_with_node_announcement(self):
        """Test that Transaction converts node dict to NodeAnnouncement."""
        txn_dict = {
            "time": 1234567890,
            "id": "test_signature",
            "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
            "hash": "test_hash",
            "relationship": {"node": self.valid_node_data},
            "inputs": [],
            "outputs": [],
        }

        txn = Transaction.from_dict(txn_dict)

        # relationship should be a NodeAnnouncement instance
        self.assertIsInstance(txn.relationship, NodeAnnouncement)
        self.assertEqual(txn.relationship.host, "192.168.1.100")
        self.assertEqual(txn.relationship.port, 8000)

    async def test_transaction_with_invalid_node_announcement(self):
        """Test that Transaction rejects invalid node announcements."""
        txn_dict = {
            "time": 1234567890,
            "id": "test_signature",
            "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
            "hash": "test_hash",
            "relationship": {
                "node": {
                    "identity": {
                        "username": "test_node",
                        # Missing public_key and username_signature
                    },
                    "host": "192.168.1.100",
                    "port": 8000,
                }
            },
            "inputs": [],
            "outputs": [],
        }

        with self.assertRaises(ValueError):
            Transaction.from_dict(txn_dict)

    async def test_transaction_to_dict_preserves_node_structure(self):
        """Test that Transaction.to_dict() properly wraps NodeAnnouncement."""
        txn_dict = {
            "time": 1234567890,
            "id": "test_signature",
            "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
            "hash": "test_hash",
            "relationship": {"node": self.valid_node_data},
            "inputs": [],
            "outputs": [],
        }

        txn = Transaction.from_dict(txn_dict)
        result = txn.to_dict()

        # Should have node key in relationship
        self.assertIn("node", result["relationship"])
        self.assertIn("identity", result["relationship"]["node"])
        self.assertEqual(result["relationship"]["node"]["host"], "192.168.1.100")


class TestNodeAnnouncementDirectInit(unittest.TestCase):
    """Tests for NodeAnnouncement.__init__ validation branches."""

    VALID_IDENTITY = {
        "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
        "username": "test_node",
        "username_signature": "dGVzdA==",
    }

    def test_init_identity_none_raises(self):
        with self.assertRaises(ValueError) as ctx:
            NodeAnnouncement(identity=None, host="127.0.0.1", port=8080)
        self.assertIn("identity", str(ctx.exception))

    def test_init_identity_not_dict_raises(self):
        with self.assertRaises(ValueError) as ctx:
            NodeAnnouncement(identity="not a dict", host="127.0.0.1", port=8080)
        self.assertIn("dict", str(ctx.exception))

    def test_init_no_public_key_raises(self):
        with self.assertRaises(ValueError) as ctx:
            NodeAnnouncement(identity={}, host="127.0.0.1", port=8080)
        self.assertIn("public_key", str(ctx.exception))

    def test_init_no_username_signature_raises(self):
        with self.assertRaises(ValueError) as ctx:
            NodeAnnouncement(
                identity={"public_key": "abc"},
                host="127.0.0.1",
                port=8080,
            )
        self.assertIn("username_signature", str(ctx.exception))

    def test_init_host_none_raises(self):
        with self.assertRaises(ValueError) as ctx:
            NodeAnnouncement(identity=self.VALID_IDENTITY, host=None, port=8080)
        self.assertIn("host", str(ctx.exception))

    def test_init_port_none_raises(self):
        with self.assertRaises(ValueError) as ctx:
            NodeAnnouncement(identity=self.VALID_IDENTITY, host="127.0.0.1", port=None)
        self.assertIn("port", str(ctx.exception))

    def test_from_dict_not_dict_raises(self):
        with self.assertRaises(ValueError) as ctx:
            NodeAnnouncement.from_dict("not a dict")
        self.assertIn("dict", str(ctx.exception))

    def test_repr_returns_string(self):
        node = NodeAnnouncement.from_dict(
            {
                "identity": self.VALID_IDENTITY,
                "host": "127.0.0.1",
                "port": 8080,
            }
        )
        result = repr(node)
        self.assertIsInstance(result, str)
        self.assertIn("NodeAnnouncement", result)

    def test_init_invalid_identity_raises(self):
        """Lines 68-69: covers except in Identity.from_dict (missing username)."""
        with self.assertRaises(ValueError) as ctx:
            # Has pub_key and sig to pass pre-checks, but Identity.from_dict will fail
            NodeAnnouncement(
                identity={"public_key": "abc", "username_signature": "def"},
                host="127.0.0.1",
                port=8080,
            )
        self.assertIn("Invalid identity", str(ctx.exception))

    def test_init_non_integer_port_raises(self):
        """Lines 74-75: covers except in port validation."""
        with self.assertRaises(ValueError) as ctx:
            NodeAnnouncement(
                identity=self.VALID_IDENTITY, host="127.0.0.1", port="not_a_port"
            )
        self.assertIn("port", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
