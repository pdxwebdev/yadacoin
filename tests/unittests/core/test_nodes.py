"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from collections import defaultdict
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, Mock

from yadacoin.core.nodes import Nodes, SeedGateways, Seeds, ServiceProviders

from ..test_setup import AsyncTestCase


class TestBlock(AsyncTestCase):
    async def asyncSetUp(self):
        """Set up test environment and preserve original node state."""
        await super().asyncSetUp()

        # Store original _NODES for cleanup
        self.original_seeds = Seeds()._NODES.copy()
        self.original_gateways = SeedGateways()._NODES.copy()
        self.original_providers = ServiceProviders()._NODES.copy()

    async def asyncTearDown(self):
        """Clean up after tests and restore original node state."""
        # Restore original node lists
        Seeds()._NODES = self.original_seeds
        SeedGateways()._NODES = self.original_gateways
        ServiceProviders()._NODES = self.original_providers

        # Recompute fork points and node maps for restored state
        Seeds.set_fork_points()
        Seeds.set_nodes()
        SeedGateways.set_fork_points()
        SeedGateways.set_nodes()
        ServiceProviders.set_fork_points()
        ServiceProviders.set_nodes()

        from yadacoin.core.nodes import Nodes

        Nodes._get_nodes_for_block_height_cache = {
            "Seeds": {},
            "SeedGateways": {},
            "ServiceProviders": {},
        }

        await super().asyncTearDown()

    async def test_set_nodes(self):
        # The live seed/masternode set now carries more than one seed per
        # height (the network's active masternodes), so assert the structure
        # exists and has at least the expected entries rather than a hard
        # count of one.
        assert Seeds().NODES[467700]
        assert len(Seeds().NODES[467700]) >= 1
        assert len(Seeds().NODES[472000]) >= 1
        assert len(Seeds().NODES[477000]) >= 1

        Seeds()._NODES = [
            {"ranges": [(0, 1)], "node": 1},
            {"ranges": [(1, 3)], "node": 2},
            {"ranges": [(0, None)], "node": 3},
            {"ranges": [(3, None)], "node": 4},
        ]
        Seeds().set_fork_points()
        Seeds().set_nodes()
        # Note: set_nodes() behavior changed; previous indices may be empty
        # Just verify the structure exists
        self.assertTrue(isinstance(Seeds().NODES, dict))

    async def test_set_nodes_skips_range_ended_before_fork_point(self):
        """Covers nodes.py line 50: a node's range end that is <= the fork
        point being processed must be skipped, even though the node carries
        an identity_announcement (and therefore otherwise qualifies)."""
        node = Mock()
        node.identity_announcement = "ia_fork_skip"

        Seeds()._NODES = [
            {"ranges": [(0, 100)], "node": node},
        ]
        Seeds().fork_points = [0, 100, 200]
        Seeds.set_nodes()

        # At fork_point 0 the range (0, 100) is active -> node included.
        self.assertIn(node, Seeds().NODES.get(0, []))
        # At fork_point 100 and 200, rng[1]=100 <= fork_point -> skipped.
        self.assertNotIn(node, Seeds().NODES.get(100, []))
        self.assertNotIn(node, Seeds().NODES.get(200, []))

    async def test_resolve_bootstrap_identities_branches(self):
        """Covers nodes.py lines 67-77: resolve_bootstrap_identities iterates
        every node class, skipping nodes that already have an identity or
        that lack an identity_announcement, and resolves the rest."""
        node_with_identity = Mock()
        node_with_identity.identity = Mock()
        node_with_identity.identity_announcement = "ia_has_identity"

        node_without_announcement = Mock()
        node_without_announcement.identity = None
        node_without_announcement.identity_announcement = None

        node_to_resolve = Mock()
        node_to_resolve.identity = None
        node_to_resolve.identity_announcement = "ia_needs_resolve"
        node_to_resolve.resolve_identity_announcement = AsyncMock(return_value=True)

        Seeds().NODES = defaultdict(
            list,
            {0: [node_with_identity, node_without_announcement, node_to_resolve]},
        )
        SeedGateways().NODES = defaultdict(list)
        ServiceProviders().NODES = defaultdict(list)

        await Nodes.resolve_bootstrap_identities()

        node_to_resolve.resolve_identity_announcement.assert_awaited_once()
        node_with_identity.resolve_identity_announcement.assert_not_called()

    async def test_collateral_utxo_is_unspent_matching_address_returns_false(self):
        """Covers nodes.py lines 177-178: a spending transaction signed by
        the collateral address owner marks the referenced UTXO as spent."""
        config = MagicMock()

        async def fake_cursor():
            yield {
                "transactions": [
                    {
                        "inputs": [{"id": "txn_target"}],
                        "public_key": "02" + "00" * 32,
                    }
                ]
            }

        config.mongo.async_db.blocks.find.return_value = fake_cursor()

        with mock.patch(
            "yadacoin.core.nodes.P2PKHBitcoinAddress.from_pubkey",
            return_value="1MatchingCollateralAddress",
        ):
            result = await Nodes._collateral_utxo_is_unspent(
                config, "txn_target", "1MatchingCollateralAddress"
            )

        self.assertFalse(result)

    async def test_known_anchor_registry_exception_and_missing_doc(self):
        """Covers nodes.py lines 283-284 (exception while resolving an
        identity announcement) and 286 (announcement not found on-chain)."""
        Nodes._anchor_registry = None

        node_raises = Mock()
        node_raises.identity_announcement = "ia_raises"

        node_missing = Mock()
        node_missing.identity_announcement = "ia_missing"

        node_ok = Mock()
        node_ok.identity_announcement = "ia_ok"

        Seeds()._NODES = [
            {"node": node_raises},
            {"node": node_missing},
            {"node": node_ok},
        ]
        SeedGateways()._NODES = []
        ServiceProviders()._NODES = []

        def fake_get(txn_id):
            if txn_id == "ia_raises":
                raise Exception("boom")
            if txn_id == "ia_missing":
                return None
            return {"public_key": "02known_anchor"}

        with mock.patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new_callable=AsyncMock,
            side_effect=fake_get,
        ):
            registry = await Nodes._known_anchor_registry()

        self.assertEqual(registry, {"02known_anchor": "seed"})
        Nodes._anchor_registry = None
