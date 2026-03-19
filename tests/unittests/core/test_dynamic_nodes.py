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
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, Mock

import yadacoin.core.config
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.mongo import Mongo
from yadacoin.core.nodes import Nodes, SeedGateways, Seeds, ServiceProviders
from yadacoin.core.peer import Seed

from ..test_setup import AsyncTestCase

# Sample node definition for testing
SAMPLE_NODE_DEFINITION = {
    "identity": {
        "public_key": "03abcdef1234567890abcdef1234567890abcdef1234567890abcdef12345678",
        "username": "test_node",
        "username_signature": base64.b64encode(b"test_signature").decode(),
    },
    "host": "192.168.1.100",
    "port": 8000,
}

# Duplicate node definition (same public key)
DUPLICATE_NODE_DEFINITION = {
    "identity": {
        "public_key": "03abcdef1234567890abcdef1234567890abcdef1234567890abcdef12345678",
        "username": "test_node_dup",
        "username_signature": base64.b64encode(b"test_signature").decode(),
    },
    "host": "192.168.1.101",
    "port": 8000,
}

# Different node definition
DIFFERENT_NODE_DEFINITION = {
    "identity": {
        "public_key": "02fedcba0987654321fedcba0987654321fedcba0987654321fedcba09876543",
        "username": "different_node",
        "username_signature": base64.b64encode(b"different_sig").decode(),
    },
    "host": "192.168.1.200",
    "port": 8000,
}


class TestDynamicNodes(AsyncTestCase):
    """Test suite for dynamic node loading and management."""

    async def asyncSetUp(self):
        """Set up test environment."""
        await super().asyncSetUp()
        self.config = Config()

        # Initialize node singletons
        self.seeds_instance = Seeds()
        self.gateways_instance = SeedGateways()
        self.providers_instance = ServiceProviders()

        # Mock the LatestBlock
        self.config.LatestBlock = MagicMock()
        self.config.LatestBlock.block = MagicMock()
        self.config.LatestBlock.block.index = CHAIN.DYNAMIC_NODES_FORK + 100

        # Mock mongo database
        self.config.mongo = Mongo()
        self.config.mongo.async_db = MagicMock()
        self.config.mongo.async_db.blocks = MagicMock()

        yadacoin.core.config.CONFIG = self.config

        # Store original _NODES for cleanup
        self.original_seeds = self.seeds_instance._NODES.copy()
        self.original_gateways = self.gateways_instance._NODES.copy()
        self.original_providers = self.providers_instance._NODES.copy()

    async def asyncTearDown(self):
        """Clean up after tests."""
        # Restore original node lists
        self.seeds_instance._NODES = self.original_seeds
        self.gateways_instance._NODES = self.original_gateways
        self.providers_instance._NODES = self.original_providers

        # Recompute fork points and node maps for restored state
        Seeds.set_fork_points()
        Seeds.set_nodes()
        SeedGateways.set_fork_points()
        SeedGateways.set_nodes()
        ServiceProviders.set_fork_points()
        ServiceProviders.set_nodes()

        Nodes._get_nodes_for_block_height_cache = {
            "Seeds": {},
            "SeedGateways": {},
            "ServiceProviders": {},
        }
        Nodes.dynamic_node_public_keys.clear()
        Nodes.dynamic_node_collateral_txns.clear()
        Nodes.dynamic_node_collateral_addresses.clear()
        Nodes._last_scanned_height = 0

    async def test_load_dynamic_nodes_before_fork(self):
        """Test that no dynamic nodes are loaded before activation fork."""
        # Set latest block before fork
        self.config.LatestBlock.block.index = CHAIN.DYNAMIC_NODES_FORK - 1

        # Clear any existing dynamic nodes (keep hardcoded ones)
        initial_count = len(self.seeds_instance._NODES)

        # Load dynamic nodes
        await Nodes.load_dynamic_nodes_from_chain(
            activation_height=CHAIN.DYNAMIC_NODES_FORK
        )

        # Should not add any nodes before fork
        self.assertEqual(len(self.seeds_instance._NODES), initial_count)

    async def test_load_dynamic_nodes_no_blocks(self):
        """Test loading dynamic nodes when no blocks exist."""
        # Mock empty cursor
        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([])

        self.config.mongo.async_db.blocks.find.return_value.sort.return_value = (
            async_iter
        )

        initial_seeds = len(self.seeds_instance._NODES)
        initial_gateways = len(self.gateways_instance._NODES)
        initial_providers = len(self.providers_instance._NODES)

        await Nodes.load_dynamic_nodes_from_chain(
            activation_height=CHAIN.DYNAMIC_NODES_FORK
        )

        # Node counts should not change
        self.assertEqual(len(self.seeds_instance._NODES), initial_seeds)
        self.assertEqual(len(self.gateways_instance._NODES), initial_gateways)
        self.assertEqual(len(self.providers_instance._NODES), initial_providers)

    async def test_load_dynamic_nodes_invalid_relationship(self):
        """Test that nodes with invalid relationship data are skipped."""
        # Block with invalid relationship (not a dict)
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": SAMPLE_NODE_DEFINITION["identity"]["public_key"],
                    "relationship": "invalid_string",  # Invalid: should be dict
                }
            ],
        }

        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])

        self.config.mongo.async_db.blocks.find.return_value.sort.return_value = (
            async_iter
        )

        initial_count = len(self.seeds_instance._NODES)

        await Nodes.load_dynamic_nodes_from_chain(
            activation_height=CHAIN.DYNAMIC_NODES_FORK
        )

        # Should not add nodes with invalid relationship
        self.assertEqual(len(self.seeds_instance._NODES), initial_count)

    async def test_load_dynamic_nodes_missing_identity(self):
        """Test that nodes without identity are skipped."""
        # Block with missing identity
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": "03test",
                    "relationship": {
                        "node": {
                            "host": "192.168.1.1",
                            "port": 8000,
                            # Missing identity field
                        }
                    },
                }
            ],
        }

        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])

        self.config.mongo.async_db.blocks.find.return_value.sort.return_value = (
            async_iter
        )

        initial_count = len(self.seeds_instance._NODES)

        await Nodes.load_dynamic_nodes_from_chain(
            activation_height=CHAIN.DYNAMIC_NODES_FORK
        )

        # Should not add nodes without identity
        self.assertEqual(len(self.seeds_instance._NODES), initial_count)

    async def test_load_dynamic_nodes_mismatched_public_key(self):
        """Test that nodes where transaction public_key doesn't match identity public_key are skipped."""
        # Block with mismatched public keys
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": "03different_key",  # Different from identity public key
                    "relationship": {"node": SAMPLE_NODE_DEFINITION.copy()},
                }
            ],
        }

        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])

        self.config.mongo.async_db.blocks.find.return_value.sort.return_value = (
            async_iter
        )

        initial_count = len(self.seeds_instance._NODES)

        await Nodes.load_dynamic_nodes_from_chain(
            activation_height=CHAIN.DYNAMIC_NODES_FORK
        )

        # Should not add nodes with mismatched keys
        self.assertEqual(len(self.seeds_instance._NODES), initial_count)

    async def test_load_dynamic_nodes_duplicate_prevention(self):
        """Test that duplicate nodes (same public key) are not added."""
        # Pre-populate with a node
        existing_node = Mock()
        existing_node.identity = Mock()
        existing_node.identity.public_key = SAMPLE_NODE_DEFINITION["identity"][
            "public_key"
        ]

        self.seeds_instance._NODES.append(
            {
                "ranges": [(CHAIN.DYNAMIC_NODES_FORK, None)],
                "node": existing_node,
            }
        )

        initial_count = len(self.seeds_instance._NODES)

        # Block with duplicate node
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK + 10,
            "transactions": [
                {
                    "public_key": SAMPLE_NODE_DEFINITION["identity"]["public_key"],
                    "relationship": {"node": SAMPLE_NODE_DEFINITION.copy()},
                }
            ],
        }

        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])

        self.config.mongo.async_db.blocks.find.return_value.sort.return_value = (
            async_iter
        )

        with mock.patch.object(Nodes, "_assign_node_type", return_value="seed"):
            await Nodes.load_dynamic_nodes_from_chain(
                activation_height=CHAIN.DYNAMIC_NODES_FORK
            )

        # Should not add duplicate
        self.assertEqual(len(self.seeds_instance._NODES), initial_count)

    async def test_load_dynamic_nodes_successful(self):
        """Test successful loading of a valid node announcement from blockchain."""
        # Create a valid node announcement
        valid_node_def = {
            "identity": {
                "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
                "username": "valid_test_node",
                "username_signature": base64.b64encode(b"valid_signature").decode(),
            },
            "host": "192.168.1.50",
            "port": 8000,
            "collateral_address": "1TestCollateralAddress",
        }

        # Block with valid node announcement
        # fee=200 ensures expiry_height = DYNAMIC_NODES_FORK + 200 > current_height (fork+100)
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "test_announcement_txn_id_abc123",
                    "public_key": valid_node_def["identity"]["public_key"],
                    "relationship": {"node": valid_node_def},
                    "fee": 200,
                }
            ],
        }

        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])

        empty_collateral_iter = AsyncMock()
        empty_collateral_iter.__aiter__.return_value = iter([])

        def find_side_effect_unspent(query, *args, **kwargs):
            elem_match = {}
            if isinstance(query, dict):
                elem_match = query.get("transactions", {}).get("$elemMatch", {})
            if "inputs.id" in elem_match:
                return empty_collateral_iter
            cursor = MagicMock()
            cursor.sort.return_value = async_iter
            return cursor

        self.config.mongo.async_db.blocks.find.side_effect = find_side_effect_unspent

        # Mock verify_signature to pass validation
        with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
            with mock.patch.object(self.config, "address_is_valid", return_value=True):
                with mock.patch(
                    "yadacoin.core.nodes.P2PKHBitcoinAddress.from_pubkey",
                    return_value="1TestCollateralAddress",
                ):
                    # Mock Seed.from_dict to return a valid node object
                    mock_node = Mock()
                    mock_node.identity = Mock()
                    mock_node.identity.public_key = valid_node_def["identity"][
                        "public_key"
                    ]
                    mock_node.host = valid_node_def["host"]
                    mock_node.port = valid_node_def["port"]

                    with mock.patch.object(Seed, "from_dict", return_value=mock_node):
                        with mock.patch.object(
                            Nodes, "_assign_node_type", return_value="seed"
                        ):
                            initial_count = len(self.seeds_instance._NODES)

                            # Load dynamic nodes
                            await Nodes.load_dynamic_nodes_from_chain(
                                activation_height=CHAIN.DYNAMIC_NODES_FORK
                            )

                            # Should have added one node
                            self.assertEqual(
                                len(self.seeds_instance._NODES), initial_count + 1
                            )

                            # Verify the node was added with correct structure
                            added_node = self.seeds_instance._NODES[-1]
                            self.assertEqual(
                                added_node["ranges"], [(CHAIN.DYNAMIC_NODES_FORK, None)]
                            )
                            self.assertEqual(added_node["node"], mock_node)
                            self.assertEqual(
                                added_node["node"].identity.public_key,
                                valid_node_def["identity"]["public_key"],
                            )
                            # Verify collateral txn id was recorded
                            self.assertIn(
                                valid_node_def["identity"]["public_key"],
                                Nodes.dynamic_node_collateral_txns,
                            )
                            self.assertEqual(
                                Nodes.dynamic_node_collateral_txns[
                                    valid_node_def["identity"]["public_key"]
                                ],
                                "test_announcement_txn_id_abc123",
                            )

    async def test_load_dynamic_nodes_spent_collateral_rejected(self):
        """Test that a node whose collateral UTXO has been spent is not registered."""
        valid_node_def = {
            "identity": {
                "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
                "username": "valid_test_node",
                "username_signature": base64.b64encode(b"valid_signature").decode(),
            },
            "host": "192.168.1.50",
            "port": 8000,
            "collateral_address": "1TestCollateralAddress",
        }

        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "spent_collateral_txn_id",
                    "public_key": valid_node_def["identity"]["public_key"],
                    "relationship": {"node": valid_node_def},
                    "fee": 200,
                }
            ],
        }

        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])

        spending_iter = AsyncMock()
        spending_iter.__aiter__.return_value = iter(
            [
                {
                    "transactions": [
                        {
                            "inputs": [{"id": "spent_collateral_txn_id"}],
                            "public_key": valid_node_def["identity"]["public_key"],
                        }
                    ]
                }
            ]
        )

        def find_side_effect_spent(query, *args, **kwargs):
            elem_match = {}
            if isinstance(query, dict):
                elem_match = query.get("transactions", {}).get("$elemMatch", {})
            if "inputs.id" in elem_match:
                return spending_iter
            cursor = MagicMock()
            cursor.sort.return_value = async_iter
            return cursor

        self.config.mongo.async_db.blocks.find.side_effect = find_side_effect_spent

        initial_count = len(self.seeds_instance._NODES)

        with mock.patch(
            "yadacoin.core.nodes.P2PKHBitcoinAddress.from_pubkey",
            return_value="1TestCollateralAddress",
        ):
            with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
                with mock.patch.object(
                    self.config, "address_is_valid", return_value=True
                ):
                    await Nodes.load_dynamic_nodes_from_chain(
                        activation_height=CHAIN.DYNAMIC_NODES_FORK
                    )

        # Node must NOT have been added because collateral is spent
        self.assertEqual(len(self.seeds_instance._NODES), initial_count)
        self.assertNotIn(
            valid_node_def["identity"]["public_key"],
            Nodes.dynamic_node_collateral_txns,
        )

    async def test_evict_all_dynamic_nodes(self):
        """Test that _evict_all_dynamic_nodes removes tracked dynamic nodes."""
        # Register a fake dynamic node
        mock_node = Mock()
        mock_node.identity = Mock()
        mock_node.identity.public_key = "test_dynamic_pubkey"
        self.seeds_instance._NODES.append(
            {"ranges": [(CHAIN.DYNAMIC_NODES_FORK, None)], "node": mock_node}
        )
        Nodes.dynamic_node_public_keys.add("test_dynamic_pubkey")
        Nodes.dynamic_node_collateral_txns["test_dynamic_pubkey"] = "txn_abc"

        initial_static_count = (
            len(self.seeds_instance._NODES) - 1
        )  # exclude the one we just added

        Nodes._evict_all_dynamic_nodes()

        self.assertEqual(len(self.seeds_instance._NODES), initial_static_count)
        self.assertNotIn("test_dynamic_pubkey", Nodes.dynamic_node_public_keys)
        self.assertNotIn("test_dynamic_pubkey", Nodes.dynamic_node_collateral_txns)

    async def test_count_nodes_by_type(self):
        """Test counting nodes by type."""
        # Add some mock nodes
        seed_node = Mock()
        gateway_node = Mock()
        provider_node = Mock()

        self.seeds_instance._NODES = [
            {"ranges": [(0, None)], "node": seed_node},
            {"ranges": [(0, None)], "node": seed_node},
        ]
        self.gateways_instance._NODES = [
            {"ranges": [(0, None)], "node": gateway_node},
        ]
        self.providers_instance._NODES = [
            {"ranges": [(0, None)], "node": provider_node},
            {"ranges": [(0, None)], "node": provider_node},
            {"ranges": [(0, None)], "node": provider_node},
        ]

        seeds_count, gateways_count, providers_count = Nodes._count_nodes_by_type()

        self.assertEqual(seeds_count, 2)
        self.assertEqual(gateways_count, 1)
        self.assertEqual(providers_count, 3)

    async def test_set_fork_points(self):
        """Test fork point calculation."""
        # Add nodes with different ranges
        node1 = Mock()
        node2 = Mock()
        node3 = Mock()

        self.seeds_instance._NODES = []
        self.gateways_instance._NODES = [
            {"ranges": [(1000, 2000)], "node": node1},
            {"ranges": [(2000, 3000)], "node": node2},
        ]
        self.providers_instance._NODES = [
            {"ranges": [(500, 1500)], "node": node3},
        ]

        # Call set_fork_points on each subclass separately
        Seeds.set_fork_points()
        SeedGateways.set_fork_points()
        ServiceProviders.set_fork_points()

        # Check fork points from each class
        Seeds().fork_points
        gateways_fork_points = SeedGateways().fork_points
        providers_fork_points = ServiceProviders().fork_points

        # SeedGateways should have the 1000, 2000 fork points
        self.assertIn(1000, gateways_fork_points)
        self.assertIn(2000, gateways_fork_points)

        # ServiceProviders should have the 500 fork point
        self.assertIn(500, providers_fork_points)

    async def test_set_nodes(self):
        """Test node mapping by fork point."""
        node1 = Mock()
        node1.identity = Mock()
        node1.identity.public_key = "key1"

        node2 = Mock()
        node2.identity = Mock()
        node2.identity.public_key = "key2"

        # Set up nodes with ranges
        self.seeds_instance._NODES = [
            {"ranges": [(0, None)], "node": node1},
        ]
        self.gateways_instance._NODES = [
            {"ranges": [(100, None)], "node": node2},
        ]
        self.providers_instance._NODES = []

        # Call set_fork_points and set_nodes on each subclass
        Seeds.set_fork_points()
        Seeds.set_nodes()
        SeedGateways.set_fork_points()
        SeedGateways.set_nodes()
        ServiceProviders.set_fork_points()
        ServiceProviders.set_nodes()

        # Check that nodes are in the correct fork point buckets
        self.assertIn(node1, [n for n in Seeds().NODES.get(0, [])])
        self.assertIn(node2, [n for n in SeedGateways().NODES.get(100, [])])

    async def test_apply_dynamic_nodes(self):
        """Test the full apply_dynamic_nodes workflow."""
        # Mock the load_dynamic_nodes_from_chain method
        with mock.patch.object(
            Nodes, "load_dynamic_nodes_from_chain", new_callable=AsyncMock
        ) as mock_load:
            mock_load.return_value = None

            # Call apply_dynamic_nodes
            await Nodes.apply_dynamic_nodes(activation_height=CHAIN.DYNAMIC_NODES_FORK)

            # Verify load was called
            mock_load.assert_called_once_with(
                activation_height=CHAIN.DYNAMIC_NODES_FORK
            )

    async def test_get_fork_for_block_height(self):
        """Test fork point lookup for block heights across all node types."""
        # Set up different fork points for each node type to ensure they maintain separate state
        self.seeds_instance.fork_points = [0, 100, 200, 300]
        self.gateways_instance.fork_points = [0, 150, 250]
        self.providers_instance.fork_points = [0, 50, 175, 400]

        # Test Seeds fork point lookups
        self.assertEqual(Seeds.get_fork_for_block_height(50), 0)
        self.assertEqual(Seeds.get_fork_for_block_height(100), 100)
        self.assertEqual(Seeds.get_fork_for_block_height(150), 100)
        self.assertEqual(Seeds.get_fork_for_block_height(250), 200)
        self.assertEqual(Seeds.get_fork_for_block_height(400), 300)

        # Test SeedGateways fork point lookups
        self.assertEqual(SeedGateways.get_fork_for_block_height(50), 0)
        self.assertEqual(SeedGateways.get_fork_for_block_height(150), 150)
        self.assertEqual(SeedGateways.get_fork_for_block_height(200), 150)
        self.assertEqual(SeedGateways.get_fork_for_block_height(300), 250)

        # Test ServiceProviders fork point lookups
        self.assertEqual(ServiceProviders.get_fork_for_block_height(25), 0)
        self.assertEqual(ServiceProviders.get_fork_for_block_height(50), 50)
        self.assertEqual(ServiceProviders.get_fork_for_block_height(100), 50)
        self.assertEqual(ServiceProviders.get_fork_for_block_height(175), 175)
        self.assertEqual(ServiceProviders.get_fork_for_block_height(300), 175)
        self.assertEqual(ServiceProviders.get_fork_for_block_height(500), 400)

    async def test_get_all_nodes_for_block_height(self):
        """Test retrieving all nodes for a specific block height."""
        seed_node = Mock()
        gateway_node = Mock()
        provider_node = Mock()

        self.seeds_instance._NODES = [{"ranges": [(0, None)], "node": seed_node}]
        self.gateways_instance._NODES = [{"ranges": [(0, None)], "node": gateway_node}]
        self.providers_instance._NODES = [
            {"ranges": [(0, None)], "node": provider_node}
        ]

        # Clear cache to avoid using stale results
        Nodes._get_nodes_for_block_height_cache = {
            "Seeds": {},
            "SeedGateways": {},
            "ServiceProviders": {},
        }

        Seeds.set_fork_points()
        Seeds.set_nodes()
        SeedGateways.set_fork_points()
        SeedGateways.set_nodes()
        ServiceProviders.set_fork_points()
        ServiceProviders.set_nodes()

        all_nodes = Nodes.get_all_nodes_for_block_height(50)

        # Should return seeds + gateways + providers
        self.assertEqual(len(all_nodes), 3)
        self.assertIn(seed_node, all_nodes)
        self.assertIn(gateway_node, all_nodes)
        self.assertIn(provider_node, all_nodes)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
