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
        Nodes.eligible_nodes_by_address.clear()
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
                            # Verify eligible_nodes_by_address was populated regardless of connectivity
                            self.assertIn(
                                "1TestCollateralAddress",
                                Nodes.eligible_nodes_by_address,
                            )
                            self.assertEqual(
                                Nodes.eligible_nodes_by_address[
                                    "1TestCollateralAddress"
                                ],
                                mock_node,
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
        # Verify eligible_nodes_by_address was NOT populated for a rejected node
        self.assertEqual(len(Nodes.eligible_nodes_by_address), 0)

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
        Nodes.eligible_nodes_by_address["test_addr_for_evict"] = mock_node

        initial_static_count = (
            len(self.seeds_instance._NODES) - 1
        )  # exclude the one we just added

        Nodes._evict_all_dynamic_nodes()

        self.assertEqual(len(self.seeds_instance._NODES), initial_static_count)
        self.assertNotIn("test_dynamic_pubkey", Nodes.dynamic_node_public_keys)
        self.assertNotIn("test_dynamic_pubkey", Nodes.dynamic_node_collateral_txns)
        self.assertEqual(len(Nodes.eligible_nodes_by_address), 0)

    async def test_evict_spent_dynamic_nodes_clears_eligible_nodes(self):
        """Test that _evict_spent_dynamic_nodes removes the entry from eligible_nodes_by_address."""
        pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a"
        mock_node = Mock()
        mock_node.identity = Mock()
        mock_node.identity.public_key = pub

        # Register the node as a tracked dynamic node
        self.seeds_instance._NODES.append(
            {"ranges": [(CHAIN.DYNAMIC_NODES_FORK, None)], "node": mock_node}
        )
        Nodes.dynamic_node_public_keys.add(pub)
        Nodes.dynamic_node_collateral_txns[pub] = "spent_txn_id"
        Nodes.dynamic_node_collateral_addresses[pub] = "1SpentCollateralAddress"
        Nodes.eligible_nodes_by_address["1SpentCollateralAddress"] = mock_node

        # Simulate the collateral UTXO being spent
        with mock.patch.object(
            Nodes,
            "_collateral_utxo_is_unspent",
            new=AsyncMock(return_value=False),
        ):
            with mock.patch(
                "yadacoin.core.nodes.P2PKHBitcoinAddress.from_pubkey",
                return_value="1SpentCollateralAddress",
            ):
                await Nodes._evict_spent_dynamic_nodes(self.config)

        self.assertNotIn(pub, Nodes.dynamic_node_public_keys)
        self.assertNotIn(pub, Nodes.dynamic_node_collateral_txns)
        self.assertNotIn("1SpentCollateralAddress", Nodes.eligible_nodes_by_address)

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


class TestNodeTypeSelfDetermination(AsyncTestCase):
    """Tests for startup node-type self-determination and its propagation through
    the announcement and load pipeline."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.seeds_instance = Seeds()
        self.gateways_instance = SeedGateways()
        self.providers_instance = ServiceProviders()
        self.config.LatestBlock = MagicMock()
        self.config.LatestBlock.block = MagicMock()
        self.config.LatestBlock.block.index = CHAIN.DYNAMIC_NODES_FORK + 100
        self.config.mongo = Mongo()
        self.config.mongo.async_db = MagicMock()
        self.config.mongo.async_db.blocks = MagicMock()
        yadacoin.core.config.CONFIG = self.config
        self.original_public_key = self.config.public_key
        self.original_seeds = self.seeds_instance._NODES.copy()
        self.original_gateways = self.gateways_instance._NODES.copy()
        self.original_providers = self.providers_instance._NODES.copy()

    async def asyncTearDown(self):
        self.config.public_key = self.original_public_key
        self.seeds_instance._NODES = self.original_seeds
        self.gateways_instance._NODES = self.original_gateways
        self.providers_instance._NODES = self.original_providers
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
        Nodes.eligible_nodes_by_address.clear()
        Nodes._last_scanned_height = 0

    # ------------------------------------------------------------------
    # _assign_node_type load-balancing logic
    # ------------------------------------------------------------------

    async def test_assign_type_seed_when_no_seeds(self):
        """When there are no seeds at all, the first node must become a seed."""
        self.seeds_instance._NODES = []
        self.gateways_instance._NODES = []
        self.providers_instance._NODES = []
        result = Nodes._assign_node_type()
        self.assertEqual(result, "seed")

    async def test_assign_type_seed_gateway_when_no_gateways(self):
        """When seeds exist but zero gateways exist, assign seed_gateway."""
        # Keep the hardcoded seed(s) but clear gateways and providers
        self.gateways_instance._NODES = []
        self.providers_instance._NODES = []
        result = Nodes._assign_node_type()
        self.assertEqual(result, "seed_gateway")

    async def test_assign_type_seed_gateway_when_gateways_lt_seeds(self):
        """When the number of gateways is less than seeds, assign seed_gateway."""
        seed_node = Mock()
        seed_node2 = Mock()
        self.seeds_instance._NODES = [
            {"ranges": [(0, None)], "node": seed_node},
            {"ranges": [(0, None)], "node": seed_node2},
        ]
        # Only one gateway for two seeds → need another gateway
        self.gateways_instance._NODES = [
            {"ranges": [(0, None)], "node": Mock()},
        ]
        self.providers_instance._NODES = []
        result = Nodes._assign_node_type()
        self.assertEqual(result, "seed_gateway")

    async def test_assign_type_service_provider_normally(self):
        """When seeds and gateways are balanced and not saturated, assign service_provider."""
        seed_node = Mock()
        gateway_node = Mock()
        self.seeds_instance._NODES = [{"ranges": [(0, None)], "node": seed_node}]
        self.gateways_instance._NODES = [{"ranges": [(0, None)], "node": gateway_node}]
        self.providers_instance._NODES = []
        result = Nodes._assign_node_type()
        self.assertEqual(result, "service_provider")

    async def test_assign_type_seed_when_all_gateways_saturated(self):
        """When all gateways are at max capacity, scale out by assigning a seed."""
        seed_node = Mock()
        gateway_node = Mock()
        provider_node = Mock()
        self.seeds_instance._NODES = [{"ranges": [(0, None)], "node": seed_node}]
        self.gateways_instance._NODES = [{"ranges": [(0, None)], "node": gateway_node}]
        # Fill providers to exactly max_providers_per_gateway
        max_peers = self.config.max_peers or 10000
        self.providers_instance._NODES = [
            {"ranges": [(0, None)], "node": provider_node}
        ] * max_peers
        result = Nodes._assign_node_type()
        self.assertEqual(result, "seed")

    # ------------------------------------------------------------------
    # self_determine_peer_type: runtime startup type determination
    # ------------------------------------------------------------------

    def _make_mock_node(self, public_key):
        """Create a mock dynamic node with the given public key."""
        node = Mock()
        node.identity = Mock()
        node.identity.public_key = public_key
        return node

    async def test_self_determine_returns_seed_for_seed_list(self):
        """When this node's public key is in the Seeds list, returns SEED peer type."""
        from yadacoin.enums.peertypes import PEER_TYPES

        pub = "03aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899"
        self.config.public_key = pub
        mock_node = self._make_mock_node(pub)
        self.seeds_instance._NODES.append(
            {"ranges": [(CHAIN.DYNAMIC_NODES_FORK, None)], "node": mock_node}
        )
        Nodes.dynamic_node_public_keys.add(pub)

        result = Nodes.self_determine_peer_type(self.config)
        self.assertEqual(result, PEER_TYPES.SEED.value)

    async def test_self_determine_returns_seed_gateway_for_gateway_list(self):
        """When this node's public key is in the SeedGateways list, returns SEED_GATEWAY peer type."""
        from yadacoin.enums.peertypes import PEER_TYPES

        pub = "03bbccddeeff00112233445566778899aabbccddeeff00112233445566778899aa"
        self.config.public_key = pub
        mock_node = self._make_mock_node(pub)
        self.gateways_instance._NODES.append(
            {"ranges": [(CHAIN.DYNAMIC_NODES_FORK, None)], "node": mock_node}
        )
        Nodes.dynamic_node_public_keys.add(pub)

        result = Nodes.self_determine_peer_type(self.config)
        self.assertEqual(result, PEER_TYPES.SEED_GATEWAY.value)

    async def test_self_determine_returns_service_provider_for_provider_list(self):
        """When this node's public key is in the ServiceProviders list, returns SERVICE_PROVIDER peer type."""
        from yadacoin.enums.peertypes import PEER_TYPES

        pub = "03ccddeeff00112233445566778899aabbccddeeff00112233445566778899aabb"
        self.config.public_key = pub
        mock_node = self._make_mock_node(pub)
        self.providers_instance._NODES.append(
            {"ranges": [(CHAIN.DYNAMIC_NODES_FORK, None)], "node": mock_node}
        )
        Nodes.dynamic_node_public_keys.add(pub)

        result = Nodes.self_determine_peer_type(self.config)
        self.assertEqual(result, PEER_TYPES.SERVICE_PROVIDER.value)

    async def test_self_determine_returns_none_when_not_a_dynamic_node(self):
        """Returns None when this node's public key is not in dynamic_node_public_keys."""
        pub = "03ddeeff00112233445566778899aabbccddeeff00112233445566778899aabbcc"
        self.config.public_key = pub
        # Do NOT add pub to dynamic_node_public_keys

        result = Nodes.self_determine_peer_type(self.config)
        self.assertIsNone(result)

    async def test_self_determine_returns_none_when_not_in_any_list(self):
        """Returns None when public key is in dynamic_node_public_keys but absent from all node lists."""
        pub = "03eeff00112233445566778899aabbccddeeff00112233445566778899aabbccdd"
        self.config.public_key = pub
        Nodes.dynamic_node_public_keys.add(pub)
        # Ensure all lists contain no entries with this key
        self.seeds_instance._NODES = []
        self.gateways_instance._NODES = []
        self.providers_instance._NODES = []

        result = Nodes.self_determine_peer_type(self.config)
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # Additional coverage tests
    # ------------------------------------------------------------------

    async def test_get_all_nodes_indexed_by_address_for_block_height(self):
        """Test get_all_nodes_indexed_by_address_for_block_height returns empty dict when no nodes."""
        self.seeds_instance._NODES = []
        self.gateways_instance._NODES = []
        self.providers_instance._NODES = []
        Seeds.set_fork_points()
        Seeds.set_nodes()
        SeedGateways.set_fork_points()
        SeedGateways.set_nodes()
        ServiceProviders.set_fork_points()
        ServiceProviders.set_nodes()
        result = Nodes.get_all_nodes_indexed_by_address_for_block_height(0)
        self.assertEqual(result, {})

    async def test_count_providers_per_gateway_zero_gateways(self):
        """Returns 0 when gateways_count == 0."""
        self.gateways_instance._NODES = []
        result = Nodes._count_providers_per_gateway()
        self.assertEqual(result, 0)

    async def test_evict_all_dynamic_nodes_empty_set(self):
        """_evict_all_dynamic_nodes returns early when dynamic_node_public_keys is empty."""
        Nodes.dynamic_node_public_keys.clear()
        initial_count = len(self.seeds_instance._NODES)
        Nodes._evict_all_dynamic_nodes()
        self.assertEqual(len(self.seeds_instance._NODES), initial_count)

    async def test_load_dynamic_nodes_no_activation_height(self):
        """load_dynamic_nodes_from_chain uses default fork when activation_height is None."""
        from yadacoin.core.chain import CHAIN

        self.config.LatestBlock.block.index = CHAIN.DYNAMIC_NODES_FORK - 1

        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([])
        self.config.mongo.async_db.blocks.find.return_value.sort.return_value = (
            async_iter
        )

        initial = len(self.seeds_instance._NODES)
        await Nodes.load_dynamic_nodes_from_chain()  # no activation_height argument
        self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_latest_block_raises(self):
        """load_dynamic_nodes_from_chain returns early when LatestBlock access raises."""
        self.config.LatestBlock = MagicMock(side_effect=Exception("no block"))
        initial = len(self.seeds_instance._NODES)
        await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_scan_from_exceeds_current_height(self):
        """Returns early when scan_from > current_height (all data cached)."""
        from yadacoin.core.chain import CHAIN

        self.config.LatestBlock.block.index = CHAIN.DYNAMIC_NODES_FORK + 10
        Nodes._last_scanned_height = CHAIN.DYNAMIC_NODES_FORK + 10  # already up-to-date

        self.config.mongo.async_db.blocks.find.call_count
        initial = len(self.seeds_instance._NODES)
        await Nodes.load_dynamic_nodes_from_chain()
        # Should not call find since scan_from > current_height
        self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_cursor_creation_raises(self):
        """Returns early when mongo cursor creation raises."""
        from yadacoin.core.chain import CHAIN

        self.config.LatestBlock.block.index = CHAIN.DYNAMIC_NODES_FORK + 5
        self.config.mongo.async_db.blocks.find.side_effect = Exception("db error")

        initial = len(self.seeds_instance._NODES)
        await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(self.seeds_instance._NODES), initial)
        # Reset side_effect for teardown
        self.config.mongo.async_db.blocks.find.side_effect = None

    async def test_load_dynamic_nodes_node_blob_not_dict(self):
        """Skips transaction when relationship.node is not a dict (e.g., integer)."""
        from yadacoin.core.chain import CHAIN

        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [{"public_key": "03test", "relationship": {"node": 42}}],
        }
        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])
        self.config.mongo.async_db.blocks.find.return_value.sort.return_value = (
            async_iter
        )

        initial = len(self.seeds_instance._NODES)
        await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_node_def_from_nested_node(self):
        """Uses node_blob directly when node_blob['node'] is not a dict."""
        from yadacoin.core.chain import CHAIN

        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": "03test",
                    "relationship": {
                        "node": {
                            # No nested "node" key, so node_def = node_blob
                            "identity": None,  # will trigger identity-not-dict path
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

        initial = len(self.seeds_instance._NODES)
        await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_identity_not_dict(self):
        """Skips transaction when identity is not a dict."""
        from yadacoin.core.chain import CHAIN

        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": "03test",
                    "relationship": {
                        "node": {
                            "identity": "not_a_dict",
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

        initial = len(self.seeds_instance._NODES)
        await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_collateral_missing(self):
        """Skips transaction when collateral_address is missing."""
        from yadacoin.core.chain import CHAIN

        node_def = {
            "identity": {
                "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
                "username_signature": base64.b64encode(b"valid_sig").decode(),
                "username": "testuser_col",
            },
            # No collateral_address
        }
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": node_def["identity"]["public_key"],
                    "id": "txn_col",
                    "relationship": {"node": node_def},
                }
            ],
        }
        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])
        self.config.mongo.async_db.blocks.find.return_value.sort.return_value = (
            async_iter
        )

        with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
            initial = len(self.seeds_instance._NODES)
            await Nodes.load_dynamic_nodes_from_chain()
            self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_assigns_seed_gateway_type(self):
        """Tests the seed_gateway assignment branch in load_dynamic_nodes_from_chain."""
        from yadacoin.core.chain import CHAIN

        valid_pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3b"
        node_def = {
            "host": "1.2.3.4",
            "port": 8000,
            "identity": {
                "public_key": valid_pub,
                "username_signature": base64.b64encode(b"valid_sig").decode(),
                "username": "testuser_sgw",
            },
            "collateral_address": "1TestAddress",
        }
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": valid_pub,
                    "id": "txn_sgw",
                    "relationship": {"node": node_def},
                }
            ],
        }
        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])

        empty_collateral_iter = AsyncMock()
        empty_collateral_iter.__aiter__.return_value = iter([])

        def find_side_effect(query, *args, **kwargs):
            if "inputs.id" in query.get("transactions", {}).get("$elemMatch", {}):
                return empty_collateral_iter
            cursor = MagicMock()
            cursor.sort.return_value = async_iter
            return cursor

        self.config.mongo.async_db.blocks.find.side_effect = find_side_effect

        mock_node = Mock()
        mock_node.identity = Mock()
        mock_node.identity.public_key = valid_pub

        with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
            with mock.patch.object(self.config, "address_is_valid", return_value=True):
                with mock.patch.object(
                    Nodes, "_assign_node_type", return_value="seed_gateway"
                ):
                    with mock.patch(
                        "yadacoin.core.nodes.P2PKHBitcoinAddress.from_pubkey",
                        return_value="1TestPaymentAddress",
                    ):
                        from yadacoin.core.peer import SeedGateway as SeedGatewayPeer

                        with mock.patch.object(
                            SeedGatewayPeer, "from_dict", return_value=mock_node
                        ):
                            before_gw = len(self.gateways_instance._NODES)
                            await Nodes.load_dynamic_nodes_from_chain()
                            self.assertGreater(
                                len(self.gateways_instance._NODES), before_gw
                            )

        self.config.mongo.async_db.blocks.find.side_effect = None

    async def test_load_dynamic_nodes_unknown_type_skipped(self):
        """Tests that an unknown assigned_type causes the node to be skipped."""
        from yadacoin.core.chain import CHAIN

        valid_pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3c"
        node_def = {
            "identity": {
                "public_key": valid_pub,
                "username_signature": base64.b64encode(b"valid_sig").decode(),
                "username": "testuser_unk",
            },
            "collateral_address": "1TestAddress",
        }
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": valid_pub,
                    "id": "txn_unk",
                    "relationship": {"node": node_def},
                }
            ],
        }
        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])

        empty_collateral_iter = AsyncMock()
        empty_collateral_iter.__aiter__.return_value = iter([])

        def find_side_effect(query, *args, **kwargs):
            if "inputs.id" in query.get("transactions", {}).get("$elemMatch", {}):
                return empty_collateral_iter
            cursor = MagicMock()
            cursor.sort.return_value = async_iter
            return cursor

        self.config.mongo.async_db.blocks.find.side_effect = find_side_effect

        with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
            with mock.patch.object(self.config, "address_is_valid", return_value=True):
                with mock.patch.object(
                    Nodes, "_assign_node_type", return_value="unknown_type"
                ):
                    initial = len(self.seeds_instance._NODES)
                    await Nodes.load_dynamic_nodes_from_chain()
                    self.assertEqual(len(self.seeds_instance._NODES), initial)

        self.config.mongo.async_db.blocks.find.side_effect = None

    async def test_load_dynamic_nodes_pub_key_already_registered(self):
        """Skips node registration when pub key is already in dynamic_node_public_keys."""
        from yadacoin.core.chain import CHAIN

        valid_pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3d"
        Nodes.dynamic_node_public_keys.add(valid_pub)

        node_def = {
            "identity": {
                "public_key": valid_pub,
                "username_signature": base64.b64encode(b"valid_sig").decode(),
                "username": "testuser_dup",
            },
            "collateral_address": "1TestAddress",
        }
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": valid_pub,
                    "id": "txn_dup",
                    "relationship": {"node": node_def},
                }
            ],
        }
        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])

        empty_collateral_iter = AsyncMock()
        empty_collateral_iter.__aiter__.return_value = iter([])

        def find_side_effect(query, *args, **kwargs):
            if "inputs.id" in query.get("transactions", {}).get("$elemMatch", {}):
                return empty_collateral_iter
            cursor = MagicMock()
            cursor.sort.return_value = async_iter
            return cursor

        self.config.mongo.async_db.blocks.find.side_effect = find_side_effect

        with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
            with mock.patch.object(self.config, "address_is_valid", return_value=True):
                initial = len(self.seeds_instance._NODES)
                await Nodes.load_dynamic_nodes_from_chain()
                self.assertEqual(len(self.seeds_instance._NODES), initial)

        self.config.mongo.async_db.blocks.find.side_effect = None

    async def test_load_dynamic_nodes_txn_pub_mismatch_skipped(self):
        """Skips node when txn public_key differs from identity public_key."""
        from yadacoin.core.chain import CHAIN

        identity_pub = (
            "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3e"
        )
        txn_pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b00"

        node_def = {
            "identity": {
                "public_key": identity_pub,
                "username_signature": base64.b64encode(b"valid_sig").decode(),
                "username": "testuser_mismatch",
            },
            "collateral_address": "1TestAddress",
        }
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": txn_pub,  # Different from identity pub
                    "id": "txn_mismatch",
                    "relationship": {"node": node_def},
                }
            ],
        }
        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])
        self.config.mongo.async_db.blocks.find.return_value.sort.return_value = (
            async_iter
        )

        with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
            initial = len(self.seeds_instance._NODES)
            await Nodes.load_dynamic_nodes_from_chain()
            self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_empty_username_sig_skipped(self):
        """Line 318: covers when pub present but username_sig is falsy (empty string)."""
        from yadacoin.core.chain import CHAIN

        pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3f"
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": pub,
                    "id": "txn_nosig",
                    "relationship": {
                        "node": {
                            "identity": {
                                "public_key": pub,
                                "username_signature": "",  # Empty = falsy → line 318 hit
                                "username": "testuser",
                            },
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

        initial = len(self.seeds_instance._NODES)
        await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_invalid_collateral_address_skipped(self):
        """Line 339: covers when collateral present but config.address_is_valid returns False."""
        from yadacoin.core.chain import CHAIN

        pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b40"
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": pub,
                    "id": "txn_invalidcol",
                    "relationship": {
                        "node": {
                            "identity": {
                                "public_key": pub,
                                "username_signature": base64.b64encode(
                                    b"valid_sig"
                                ).decode(),
                                "username": "testuser_inv_col",
                            },
                            "collateral_address": "invalid_addr",
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

        with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
            with mock.patch.object(self.config, "address_is_valid", return_value=False):
                initial = len(self.seeds_instance._NODES)
                await Nodes.load_dynamic_nodes_from_chain()
                self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_missing_txn_id_skipped(self):
        """Line 347: covers when txn has no id (or id is falsy)."""
        from yadacoin.core.chain import CHAIN

        pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b41"
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": pub,
                    # No "id" key → txn_id = None → falsy
                    "relationship": {
                        "node": {
                            "identity": {
                                "public_key": pub,
                                "username_signature": base64.b64encode(
                                    b"valid_sig"
                                ).decode(),
                                "username": "testuser_noid",
                            },
                            "collateral_address": "1ValidAddress",
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

        with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
            with mock.patch.object(self.config, "address_is_valid", return_value=True):
                initial = len(self.seeds_instance._NODES)
                await Nodes.load_dynamic_nodes_from_chain()
                self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_utxo_is_spent_skipped(self):
        """Line 352: covers when _collateral_utxo_is_unspent returns False (UTXO spent)."""
        from yadacoin.core.chain import CHAIN

        pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b42"
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": pub,
                    "id": "txn_spent",
                    "relationship": {
                        "node": {
                            "identity": {
                                "public_key": pub,
                                "username_signature": base64.b64encode(
                                    b"valid_sig"
                                ).decode(),
                                "username": "testuser_spent",
                            },
                            "collateral_address": "1ValidAddress",
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

        with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
            with mock.patch.object(self.config, "address_is_valid", return_value=True):
                with mock.patch.object(
                    Nodes,
                    "_collateral_utxo_is_unspent",
                    new=AsyncMock(return_value=False),
                ):
                    initial = len(self.seeds_instance._NODES)
                    await Nodes.load_dynamic_nodes_from_chain()
                    self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_utxo_check_raises_skipped(self):
        """Lines 353-354: covers except block when _collateral_utxo_is_unspent raises."""
        from yadacoin.core.chain import CHAIN

        pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b43"
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": pub,
                    "id": "txn_raises",
                    "relationship": {
                        "node": {
                            "identity": {
                                "public_key": pub,
                                "username_signature": base64.b64encode(
                                    b"valid_sig"
                                ).decode(),
                                "username": "testuser_raises",
                            },
                            "collateral_address": "1ValidAddress",
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

        with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
            with mock.patch.object(self.config, "address_is_valid", return_value=True):
                with mock.patch.object(
                    Nodes,
                    "_collateral_utxo_is_unspent",
                    new=AsyncMock(side_effect=RuntimeError("DB error")),
                ):
                    initial = len(self.seeds_instance._NODES)
                    await Nodes.load_dynamic_nodes_from_chain()
                    self.assertEqual(len(self.seeds_instance._NODES), initial)

    async def test_load_dynamic_nodes_assigns_service_provider_type(self):
        """Lines 373-374: covers the service_provider branch in load_dynamic_nodes_from_chain."""
        from yadacoin.core.chain import CHAIN

        valid_pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b44"
        node_def = {
            "host": "10.0.0.1",
            "port": 8001,
            "identity": {
                "public_key": valid_pub,
                "username_signature": base64.b64encode(b"valid_sig").decode(),
                "username": "testuser_sp",
            },
            "collateral_address": "1SPTestAddress",
        }
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": valid_pub,
                    "id": "txn_sp",
                    "relationship": {"node": node_def},
                }
            ],
        }
        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])

        empty_collateral_iter = AsyncMock()
        empty_collateral_iter.__aiter__.return_value = iter([])

        def find_side_effect(query, *args, **kwargs):
            if "inputs.id" in query.get("transactions", {}).get("$elemMatch", {}):
                return empty_collateral_iter
            cursor = MagicMock()
            cursor.sort.return_value = async_iter
            return cursor

        self.config.mongo.async_db.blocks.find.side_effect = find_side_effect

        mock_node = Mock()
        mock_node.identity = Mock()
        mock_node.identity.public_key = valid_pub

        from yadacoin.core.peer import ServiceProvider as ServiceProviderPeer

        with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
            with mock.patch.object(self.config, "address_is_valid", return_value=True):
                with mock.patch.object(
                    Nodes, "_assign_node_type", return_value="service_provider"
                ):
                    with mock.patch(
                        "yadacoin.core.nodes.P2PKHBitcoinAddress.from_pubkey",
                        return_value="1TestPaymentAddressSP",
                    ):
                        with mock.patch.object(
                            ServiceProviderPeer, "from_dict", return_value=mock_node
                        ):
                            before_sp = len(self.providers_instance._NODES)
                            await Nodes.load_dynamic_nodes_from_chain()
                            self.assertGreater(
                                len(self.providers_instance._NODES), before_sp
                            )

        self.config.mongo.async_db.blocks.find.side_effect = None

    async def test_load_dynamic_nodes_skips_duplicate_existing_node(self):
        """Lines 391-392, 396: covers when pub key matches existing hardcoded node."""
        from yadacoin.core.chain import CHAIN

        valid_pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b45"
        node_def = {
            "host": "10.0.0.2",
            "port": 8002,
            "identity": {
                "public_key": valid_pub,
                "username_signature": base64.b64encode(b"valid_sig").decode(),
                "username": "testuser_dup2",
            },
            "collateral_address": "1DupTestAddress",
        }
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": valid_pub,
                    "id": "txn_dup2",
                    "relationship": {"node": node_def},
                }
            ],
        }
        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])

        empty_collateral_iter = AsyncMock()
        empty_collateral_iter.__aiter__.return_value = iter([])

        def find_side_effect(query, *args, **kwargs):
            if "inputs.id" in query.get("transactions", {}).get("$elemMatch", {}):
                return empty_collateral_iter
            cursor = MagicMock()
            cursor.sort.return_value = async_iter
            return cursor

        self.config.mongo.async_db.blocks.find.side_effect = find_side_effect

        # Pre-populate Seeds with a node having the same pub key
        mock_existing = Mock()
        mock_existing.identity = Mock()
        mock_existing.identity.public_key = valid_pub
        self.seeds_instance._NODES.append(
            {"ranges": [(CHAIN.DYNAMIC_NODES_FORK, None)], "node": mock_existing}
        )

        mock_new_node = Mock()
        mock_new_node.identity = Mock()
        mock_new_node.identity.public_key = valid_pub

        from yadacoin.core.peer import Seed as SeedPeer

        with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
            with mock.patch.object(self.config, "address_is_valid", return_value=True):
                with mock.patch.object(Nodes, "_assign_node_type", return_value="seed"):
                    with mock.patch.object(
                        SeedPeer, "from_dict", return_value=mock_new_node
                    ):
                        initial = len(self.seeds_instance._NODES)
                        await Nodes.load_dynamic_nodes_from_chain()
                        # Node should NOT be re-added since it already exists
                        self.assertEqual(len(self.seeds_instance._NODES), initial)

        self.config.mongo.async_db.blocks.find.side_effect = None


class TestNodesExceptionPaths(AsyncTestCase):
    """Covers exception-handler and rare-branch paths in nodes.py."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        # Use a standalone mock config rather than touching the global Config singleton.
        self.mock_cfg = MagicMock()
        self.mock_cfg.LatestBlock.block.index = CHAIN.DYNAMIC_NODES_FORK + 100
        self.mock_cfg.address_is_valid.return_value = True
        self.seeds_instance = Seeds()
        self.gateways_instance = SeedGateways()
        self.providers_instance = ServiceProviders()
        self.original_seeds = self.seeds_instance._NODES.copy()
        self.original_gateways = self.gateways_instance._NODES.copy()
        self.original_providers = self.providers_instance._NODES.copy()

    async def asyncTearDown(self):
        self.seeds_instance._NODES = self.original_seeds
        self.gateways_instance._NODES = self.original_gateways
        self.providers_instance._NODES = self.original_providers
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
        Nodes.eligible_nodes_by_address.clear()
        Nodes._last_scanned_height = 0
        await super().asyncTearDown()

    # ------------------------------------------------------------------
    # Line 72: get_nodes_for_block_height retries when first call returns None
    # ------------------------------------------------------------------

    def test_get_nodes_for_block_height_retries_on_none_fork(self):
        """Line 72: retries get_fork_for_block_height when first call returns None."""
        Seeds.set_fork_points()
        Seeds.set_nodes()
        valid_fork = Seeds().fork_points[0] if Seeds().fork_points else 0
        Nodes._get_nodes_for_block_height_cache["Seeds"] = {}

        with mock.patch.object(
            Seeds, "get_fork_for_block_height", side_effect=[None, valid_fork]
        ):
            result = Seeds.get_nodes_for_block_height(valid_fork)

        self.assertIsNotNone(result)

    # ------------------------------------------------------------------
    # Lines 128, 135-136: _collateral_utxo_is_unspent edge cases
    # ------------------------------------------------------------------

    async def test_collateral_utxo_is_unspent_skips_non_matching_inputs(self):
        """Line 128: continues when transaction inputs don't reference txn_id."""
        block = {
            "transactions": [
                {
                    "inputs": [{"id": "DIFFERENT_TXN_ID"}],
                    "public_key": "03abcdef1234567890abcdef1234567890abcdef1234567890abcdef12345678",
                }
            ]
        }

        async def aiter_blocks():
            yield block

        self.mock_cfg.mongo.async_db.blocks.find.return_value = aiter_blocks()

        result = await Nodes._collateral_utxo_is_unspent(
            self.mock_cfg, "TARGET_TXN_ID", "1SomeAddress"
        )
        self.assertTrue(result)

    async def test_collateral_utxo_is_unspent_invalid_pubkey_continues(self):
        """Lines 135-136: continues on exception computing spending_address."""
        block = {
            "transactions": [
                {
                    "inputs": [{"id": "TARGET_TXN_ID"}],
                    "public_key": "INVALID_HEX_NOT_PUBKEY",
                }
            ]
        }

        async def aiter_blocks():
            yield block

        self.mock_cfg.mongo.async_db.blocks.find.return_value = aiter_blocks()

        result = await Nodes._collateral_utxo_is_unspent(
            self.mock_cfg, "TARGET_TXN_ID", "1SomeAddress"
        )
        self.assertTrue(result)

    # ------------------------------------------------------------------
    # Lines 156-157: _evict_all_dynamic_nodes handles broken node entry
    # ------------------------------------------------------------------

    def test_evict_all_dynamic_nodes_broken_node_entry(self):
        """Lines 156-157: catches exception accessing entry node's public_key."""
        Nodes.dynamic_node_public_keys.add("some_key")
        # Entry whose .identity.public_key access raises
        broken_entry = {"node": object()}  # plain object, no 'identity' attribute
        self.seeds_instance._NODES.append(broken_entry)

        # Should not raise
        Nodes._evict_all_dynamic_nodes()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)
        # broken entry is retained (pk is None, not in dynamic_node_public_keys)
        self.seeds_instance._NODES = [
            e for e in self.seeds_instance._NODES if e is not broken_entry
        ]

    # ------------------------------------------------------------------
    # Lines 182-183: _evict_spent_dynamic_nodes - no collateral address
    # ------------------------------------------------------------------

    async def test_evict_spent_nodes_no_collateral_address_evicts(self):
        """Lines 182-183: pub with no collateral_address is treated as spent."""
        pub = "03aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899"
        Nodes.dynamic_node_collateral_txns[pub] = "some_txn"
        # Intentionally do NOT set dynamic_node_collateral_addresses[pub]
        mock_node = Mock()
        mock_node.identity = Mock()
        mock_node.identity.public_key = pub
        self.seeds_instance._NODES.append(
            {"ranges": [(CHAIN.DYNAMIC_NODES_FORK, None)], "node": mock_node}
        )
        Nodes.dynamic_node_public_keys.add(pub)

        with mock.patch(
            "yadacoin.core.nodes.P2PKHBitcoinAddress.from_pubkey",
            return_value="1SomeAddr",
        ):
            await Nodes._evict_spent_dynamic_nodes(self.mock_cfg)

        self.assertNotIn(pub, Nodes.dynamic_node_collateral_txns)

    # ------------------------------------------------------------------
    # Lines 188-189: _evict_spent_dynamic_nodes - _collateral_utxo_is_unspent raises
    # ------------------------------------------------------------------

    async def test_evict_spent_nodes_collateral_check_exception_continues(self):
        """Lines 188-189: exception from _collateral_utxo_is_unspent is swallowed."""
        pub = "03bbccddeeff00112233445566778899aabbccddeeff00112233445566778899aa"
        Nodes.dynamic_node_collateral_txns[pub] = "txn_raises"
        Nodes.dynamic_node_collateral_addresses[pub] = "1CollateralAddr"

        with mock.patch.object(
            Nodes,
            "_collateral_utxo_is_unspent",
            new=AsyncMock(side_effect=Exception("db error")),
        ):
            await Nodes._evict_spent_dynamic_nodes(self.mock_cfg)

        # pub is still tracked (exception → continue, not evicted)
        self.assertIn(pub, Nodes.dynamic_node_collateral_txns)

    # ------------------------------------------------------------------
    # Line 193: _evict_spent_dynamic_nodes - early return when spent_keys empty
    # ------------------------------------------------------------------

    async def test_evict_spent_nodes_early_return_when_none_spent(self):
        """Line 193: returns early when all nodes are unspent."""
        pub = "03ccddeeff00112233445566778899aabbccddeeff00112233445566778899aabb"
        Nodes.dynamic_node_collateral_txns[pub] = "unspent_txn"
        Nodes.dynamic_node_collateral_addresses[pub] = "1UnspentAddr"

        initial_count = len(self.seeds_instance._NODES)

        with mock.patch.object(
            Nodes,
            "_collateral_utxo_is_unspent",
            new=AsyncMock(return_value=True),
        ):
            await Nodes._evict_spent_dynamic_nodes(self.mock_cfg)

        # No nodes evicted
        self.assertEqual(len(self.seeds_instance._NODES), initial_count)
        self.assertIn(pub, Nodes.dynamic_node_collateral_txns)

    # ------------------------------------------------------------------
    # Lines 200-201: _evict_spent_dynamic_nodes - broken entry in second loop
    # ------------------------------------------------------------------

    async def test_evict_spent_nodes_broken_entry_in_eviction_loop(self):
        """Lines 200-201: catches exception accessing node pk during eviction loop."""
        pub = "03ddeeff00112233445566778899aabbccddeeff00112233445566778899aabbcc"
        Nodes.dynamic_node_collateral_txns[pub] = "spent_txn"
        Nodes.dynamic_node_collateral_addresses[pub] = "1SpentAddr"
        Nodes.dynamic_node_public_keys.add(pub)

        # Add a broken entry alongside a valid one
        broken_entry = {"node": object()}  # accessing .identity.public_key raises
        self.seeds_instance._NODES.append(broken_entry)

        with mock.patch.object(
            Nodes,
            "_collateral_utxo_is_unspent",
            new=AsyncMock(return_value=False),
        ):
            with mock.patch(
                "yadacoin.core.nodes.P2PKHBitcoinAddress.from_pubkey",
                return_value="1SpentAddr",
            ):
                await Nodes._evict_spent_dynamic_nodes(self.mock_cfg)

        self.assertNotIn(pub, Nodes.dynamic_node_collateral_txns)
        # Clean up broken entry
        self.seeds_instance._NODES = [
            e for e in self.seeds_instance._NODES if e is not broken_entry
        ]

    # ------------------------------------------------------------------
    # Lines 213-214: _evict_spent_dynamic_nodes - invalid hex pub key
    # ------------------------------------------------------------------

    async def test_evict_spent_nodes_invalid_hex_pub_key(self):
        """Lines 213-214: catches exception when pub is not valid hex for address computation."""
        pub = "NOT_VALID_HEX"
        Nodes.dynamic_node_collateral_txns[pub] = "spent_txn2"
        Nodes.dynamic_node_collateral_addresses[pub] = "1AnotherAddr"
        Nodes.dynamic_node_public_keys.add(pub)

        with mock.patch.object(
            Nodes,
            "_collateral_utxo_is_unspent",
            new=AsyncMock(return_value=False),
        ):
            # Should not raise despite bad hex pub key
            await Nodes._evict_spent_dynamic_nodes(self.mock_cfg)

        self.assertNotIn(pub, Nodes.dynamic_node_collateral_txns)

    # ------------------------------------------------------------------
    # Line 378: load_dynamic_nodes_from_chain - unknown node type skipped
    # ------------------------------------------------------------------

    async def test_load_dynamic_nodes_unknown_assign_type_skipped(self):
        """Line 378: skips node when _assign_node_type returns an unknown value."""
        valid_pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3c"
        node_def = {
            "host": "1.2.3.4",
            "port": 8000,
            "collateral_address": "1TestAddr",
            "identity": {
                "public_key": valid_pub,
                "username_signature": base64.b64encode(b"sig").decode(),
                "username": "testuser",
            },
        }
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": valid_pub,
                    "id": "txn_unknown",
                    "relationship": {"node": node_def},
                }
            ],
        }
        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])
        empty_iter = AsyncMock()
        empty_iter.__aiter__.return_value = iter([])

        def find_side_effect(query, *args, **kwargs):
            if "inputs.id" in query.get("transactions", {}).get("$elemMatch", {}):
                return empty_iter
            cursor = MagicMock()
            cursor.sort.return_value = async_iter
            return cursor

        self.mock_cfg.mongo.async_db.blocks.find.side_effect = find_side_effect

        initial = len(self.seeds_instance._NODES)
        with mock.patch("yadacoin.core.nodes.Config", return_value=self.mock_cfg):
            with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
                with mock.patch.object(
                    Nodes, "_assign_node_type", return_value="unknown_type"
                ):
                    await Nodes.load_dynamic_nodes_from_chain()

        self.assertEqual(len(self.seeds_instance._NODES), initial)
        self.mock_cfg.mongo.async_db.blocks.find.side_effect = None

    # ------------------------------------------------------------------
    # Lines 382-383: load_dynamic_nodes_from_chain - from_dict raises
    # ------------------------------------------------------------------

    async def test_load_dynamic_nodes_from_dict_raises_skipped(self):
        """Lines 382-383: skips node when creator.from_dict raises."""
        from yadacoin.core.peer import Seed as SeedPeer

        valid_pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3d"
        node_def = {
            "host": "1.2.3.4",
            "port": 8000,
            "collateral_address": "1TestAddr",
            "identity": {
                "public_key": valid_pub,
                "username_signature": base64.b64encode(b"sig").decode(),
                "username": "testuser2",
            },
        }
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": valid_pub,
                    "id": "txn_fromdict",
                    "relationship": {"node": node_def},
                }
            ],
        }
        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])
        empty_iter = AsyncMock()
        empty_iter.__aiter__.return_value = iter([])

        def find_side_effect(query, *args, **kwargs):
            if "inputs.id" in query.get("transactions", {}).get("$elemMatch", {}):
                return empty_iter
            cursor = MagicMock()
            cursor.sort.return_value = async_iter
            return cursor

        self.mock_cfg.mongo.async_db.blocks.find.side_effect = find_side_effect

        initial = len(self.seeds_instance._NODES)
        with mock.patch("yadacoin.core.nodes.Config", return_value=self.mock_cfg):
            with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
                with mock.patch.object(Nodes, "_assign_node_type", return_value="seed"):
                    with mock.patch.object(
                        SeedPeer, "from_dict", side_effect=Exception("bad node data")
                    ):
                        await Nodes.load_dynamic_nodes_from_chain()

        self.assertEqual(len(self.seeds_instance._NODES), initial)
        self.mock_cfg.mongo.async_db.blocks.find.side_effect = None

    # ------------------------------------------------------------------
    # Lines 395-396: load_dynamic_nodes_from_chain - exception in dup check loop
    # ------------------------------------------------------------------

    async def test_load_dynamic_nodes_exception_in_duplicate_check(self):
        """Lines 395-396: continues when exception raised iterating existing nodes."""
        from yadacoin.core.peer import Seed as SeedPeer

        valid_pub = "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3e"
        node_def = {
            "host": "1.2.3.5",
            "port": 8000,
            "collateral_address": "1TestAddr2",
            "identity": {
                "public_key": valid_pub,
                "username_signature": base64.b64encode(b"sig").decode(),
                "username": "testuser3",
            },
        }
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": valid_pub,
                    "id": "txn_dupcheck",
                    "relationship": {"node": node_def},
                }
            ],
        }
        async_iter = AsyncMock()
        async_iter.__aiter__.return_value = iter([block])
        empty_iter = AsyncMock()
        empty_iter.__aiter__.return_value = iter([])

        def find_side_effect(query, *args, **kwargs):
            if "inputs.id" in query.get("transactions", {}).get("$elemMatch", {}):
                return empty_iter
            cursor = MagicMock()
            cursor.sort.return_value = async_iter
            return cursor

        self.mock_cfg.mongo.async_db.blocks.find.side_effect = find_side_effect

        # Insert a broken entry into seeds that will raise on .identity.public_key
        broken_entry = {"node": object()}
        self.seeds_instance._NODES.insert(0, broken_entry)

        mock_node = Mock()
        mock_node.identity = Mock()
        mock_node.identity.public_key = valid_pub

        with mock.patch("yadacoin.core.nodes.Config", return_value=self.mock_cfg):
            with mock.patch("yadacoin.core.nodes.verify_signature", return_value=True):
                with mock.patch.object(Nodes, "_assign_node_type", return_value="seed"):
                    with mock.patch.object(
                        SeedPeer, "from_dict", return_value=mock_node
                    ):
                        with mock.patch(
                            "yadacoin.core.nodes.P2PKHBitcoinAddress.from_pubkey",
                            return_value="1TestAddr2",
                        ):
                            await Nodes.load_dynamic_nodes_from_chain()

        # broken entry should have been iterated over without crashing
        self.seeds_instance._NODES = [
            e for e in self.seeds_instance._NODES if e is not broken_entry
        ]
        self.mock_cfg.mongo.async_db.blocks.find.side_effect = None

    # ------------------------------------------------------------------
    # Lines 466-467: self_determine_peer_type - exception in node list iteration
    # ------------------------------------------------------------------

    def test_self_determine_peer_type_exception_in_entry_continues(self):
        """Lines 466-467: continues when accessing entry node's public_key raises."""
        from yadacoin.enums.peertypes import PEER_TYPES

        pub = "03ff00112233445566778899aabbccddeeff00112233445566778899aabbccddee"
        self.mock_cfg.public_key = pub
        Nodes.dynamic_node_public_keys.add(pub)

        # First entry raises on .identity.public_key
        broken_entry = {"node": object()}
        # Second entry has the matching key
        match_node = Mock()
        match_node.identity = Mock()
        match_node.identity.public_key = pub
        self.seeds_instance._NODES.insert(0, broken_entry)
        self.seeds_instance._NODES.insert(
            1, {"ranges": [(0, None)], "node": match_node}
        )

        result = Nodes.self_determine_peer_type(self.mock_cfg)
        self.assertEqual(result, PEER_TYPES.SEED.value)

        # Clean up
        self.seeds_instance._NODES = [
            e
            for e in self.seeds_instance._NODES
            if e is not broken_entry and e.get("node") is not match_node
        ]


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
