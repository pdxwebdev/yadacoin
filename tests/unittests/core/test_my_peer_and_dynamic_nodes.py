"""
Coverage tests for Peer.my_peer() (lines 113-204) and
Nodes.load_dynamic_nodes_from_chain() (lines 359-574).
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import yadacoin.core.config
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.mongo import Mongo
from yadacoin.core.nodes import Nodes, SeedGateways, Seeds, ServiceProviders
from yadacoin.core.peer import Peer, Pool, Seed, SeedGateway, ServiceProvider, User
from yadacoin.enums.peertypes import PEER_TYPES

from ..test_setup import AsyncTestCase

# ==============================================================================
# Peer.my_peer() — all branches (lines 113-204)
# ==============================================================================


class TestMyPeerAllBranches(AsyncTestCase):
    """Covers Peer.my_peer (lines 113-204)."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.config.network = "regnet"
        self.config.username = "testuser"
        self.config.username_signature = "ab" * 32
        self.config.public_key = "02" + "00" * 32
        self.config.peer_host = "127.0.0.1"
        self.config.peer_port = 8000
        self.config.peer_type = PEER_TYPES.USER.value
        self.config.ssl = MagicMock()
        self.config.ssl.common_name = "test.example.com"
        self.config.ssl.port = 443
        self.config.serve_port = 8001
        self.config.node_version = (1, 0, 0)
        self.config.seeds = {}
        self.config.seed_gateways = {}
        self.config.service_providers = {}
        self.config.kel_manager = None
        self.config.pool_payout = False
        self.config.app_log = MagicMock()
        yadacoin.core.config.CONFIG = self.config

    async def test_default_returns_user(self):
        """Lines 203-204: default peer_type returns User."""
        result = await Peer.my_peer()
        self.assertIsInstance(result, User)

    async def test_pool_peer_type_returns_pool(self):
        """Lines 197-202: pool peer_type returns Pool."""
        self.config.peer_type = PEER_TYPES.POOL.value
        result = await Peer.my_peer()
        self.assertIsInstance(result, Pool)

    async def test_pool_payout_true_returns_pool(self):
        """Line 197: pool_payout=True routes to pool even with user type."""
        self.config.peer_type = PEER_TYPES.USER.value
        self.config.pool_payout = True
        result = await Peer.my_peer()
        self.assertIsInstance(result, Pool)

    async def test_seed_not_in_seeds_returns_user(self):
        """Lines 168-171: seed type but not in config.seeds -> User."""
        self.config.peer_type = PEER_TYPES.SEED.value
        self.config.seeds = {}
        result = await Peer.my_peer()
        self.assertIsInstance(result, User)

    async def test_seed_in_seeds_returns_seed(self):
        """Lines 172-173: seed found in config.seeds -> Seed."""
        self.config.peer_type = PEER_TYPES.SEED.value
        mock_entry = MagicMock()
        mock_entry.seed_gateway = "my_gateway_id"
        self.config.seeds = {"ab" * 32: mock_entry}
        result = await Peer.my_peer()
        self.assertIsInstance(result, Seed)

    async def test_seed_gateway_not_in_list_returns_user(self):
        """Lines 178-181: seed_gateway not found -> User."""
        self.config.peer_type = PEER_TYPES.SEED_GATEWAY.value
        self.config.seed_gateways = {}
        result = await Peer.my_peer()
        self.assertIsInstance(result, User)

    async def test_seed_gateway_in_list_returns_seed_gateway(self):
        """Lines 182-183: seed_gateway found -> SeedGateway."""
        self.config.peer_type = PEER_TYPES.SEED_GATEWAY.value
        mock_entry = MagicMock()
        mock_entry.seed = "my_seed_id"
        self.config.seed_gateways = {"ab" * 32: mock_entry}
        result = await Peer.my_peer()
        self.assertIsInstance(result, SeedGateway)

    async def test_service_provider_not_in_list_returns_user(self):
        """Lines 190-193: service_provider not found -> User."""
        self.config.peer_type = PEER_TYPES.SERVICE_PROVIDER.value
        self.config.service_providers = {}
        result = await Peer.my_peer()
        self.assertIsInstance(result, User)

    async def test_service_provider_in_list_returns_sp(self):
        """Lines 194-196: service_provider found -> ServiceProvider."""
        self.config.peer_type = PEER_TYPES.SERVICE_PROVIDER.value
        mock_entry = MagicMock()
        mock_entry.seed_gateway = "sg_id"
        mock_entry.seed = "seed_id"
        self.config.service_providers = {"ab" * 32: mock_entry}
        result = await Peer.my_peer()
        self.assertIsInstance(result, ServiceProvider)

    async def test_kel_manager_resolves_identity(self):
        """Lines 125-137: kel_manager._inception_txn_id resolves on-chain."""
        self.config.peer_type = PEER_TYPES.USER.value
        mock_kel = MagicMock()
        mock_kel._inception_txn_id = "ia_txn_inception_001"
        self.config.kel_manager = mock_kel

        ia_mock = AsyncMock(
            return_value={
                "public_key": "03" + "00" * 32,
                "identity": {
                    "username": "onchain_user",
                    "username_signature": "cd" * 32,
                },
            }
        )
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=ia_mock,
        ):
            result = await Peer.my_peer()
        self.assertIsInstance(result, User)
        self.assertTrue(hasattr(result, "identity_announcement"))


# ==============================================================================
# Nodes.load_dynamic_nodes_from_chain — happy path (lines 359-574)
# ==============================================================================


class TestLoadDynamicNodesCoverage(AsyncTestCase):
    """Covers Nodes.load_dynamic_nodes_from_chain happy path and edge guards."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        yadacoin.core.config.CONFIG = self.config

        self.seeds_instance = Seeds()
        self.gateways_instance = SeedGateways()
        self.providers_instance = ServiceProviders()

        self.config.LatestBlock = MagicMock()
        self.config.LatestBlock.block = MagicMock()
        self.config.LatestBlock.block.index = CHAIN.DYNAMIC_NODES_FORK + 100

        self.config.mongo = Mongo()
        self.config.mongo.async_db = MagicMock()
        self.config.mongo.async_db.blocks = MagicMock()

        # Save originals for cleanup
        self._orig_seeds = self.seeds_instance._NODES.copy()
        self._orig_gateways = self.gateways_instance._NODES.copy()
        self._orig_providers = self.providers_instance._NODES.copy()

    async def asyncTearDown(self):
        self.seeds_instance._NODES = self._orig_seeds
        self.gateways_instance._NODES = self._orig_gateways
        self.providers_instance._NODES = self._orig_providers
        Nodes.dynamic_node_public_keys.clear()
        Nodes.eligible_nodes_by_address.clear()
        Nodes._last_scanned_height = 0

    async def test_happy_path_adds_dynamic_node(self):
        pub = "02" + "00" * 32
        ia_id = "ia_happy_001"
        txn_id = "txn_happy_001"

        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": txn_id,
                    "public_key": pub,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.1",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
                            "identity_announcement": ia_id,
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

        mock_node = MagicMock()
        mock_node.identity = None

        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": pub,
                    "identity": {"username": "dyn", "username_signature": "ab" * 32},
                }
            ),
        ), patch(
            "yadacoin.core.nodes.verify_signature", return_value=True
        ), patch.object(
            self.config, "address_is_valid", return_value=True
        ), patch.object(
            Nodes, "_collateral_utxo_is_unspent", new=AsyncMock(return_value=True)
        ), patch.object(
            Nodes, "_assign_node_type", return_value="seed"
        ), patch(
            "yadacoin.core.nodes.Seed.from_dict", return_value=mock_node
        ), patch(
            "yadacoin.core.nodes.P2PKHBitcoinAddress"
        ) as mock_p2pkh:
            mock_addr = MagicMock()
            mock_addr.__str__.return_value = "1PaymentAddr1234567890123456"
            mock_p2pkh.from_pubkey.return_value = mock_addr

            await Nodes.load_dynamic_nodes_from_chain()

        self.assertIn(pub, Nodes.dynamic_node_public_keys)

    async def test_no_identity_announcement_skipped(self):
        """Cover line 427: continue when identity_announcement is missing."""
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "txn_no_ia",
                    "public_key": "02" + "00" * 32,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.2",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
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
        with patch.object(self.config, "address_is_valid", return_value=True):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)

    async def test_ia_doc_not_found_skipped(self):
        """Cover line 438: continue when IdentityAnnouncement not found."""
        pub = "02" + "00" * 32
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "txn_bad_ia",
                    "public_key": pub,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.3",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
                            "identity_announcement": "ia_missing",
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
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(return_value=None),
        ), patch.object(self.config, "address_is_valid", return_value=True):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)

    async def test_no_pub_or_sig_skipped(self):
        """Cover line 445: continue when pub or username_sig missing."""
        pub = "02" + "00" * 32
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "txn_no_sig",
                    "public_key": pub,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.4",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
                            "identity_announcement": "ia_no_sig",
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
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": None,
                    "identity": {"username": "x", "username_signature": None},
                }
            ),
        ), patch.object(self.config, "address_is_valid", return_value=True):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)

    async def test_signature_exception_skipped(self):
        """Cover lines 453-454: exception during signature verify."""
        pub = "02" + "00" * 32
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "txn_bad_sig",
                    "public_key": pub,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.5",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
                            "identity_announcement": "ia_bad_sig",
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
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": pub,
                    "identity": {
                        "username": "x",
                        "username_signature": "!!NOT_BASE64!!",
                    },
                }
            ),
        ), patch.object(self.config, "address_is_valid", return_value=True):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)

    async def test_verification_failed_skipped(self):
        """Cover line 456: continue when signature verification fails."""
        pub = "02" + "00" * 32
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "txn_verify_fail",
                    "public_key": pub,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.6",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
                            "identity_announcement": "ia_verify_fail",
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
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": pub,
                    "identity": {"username": "x", "username_signature": "ab" * 32},
                }
            ),
        ), patch(
            "yadacoin.core.nodes.verify_signature", return_value=False
        ), patch.object(
            self.config, "address_is_valid", return_value=True
        ):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)

    async def test_txn_pub_mismatch_skipped(self):
        """Cover line 461: continue when txn public_key != identity pub."""
        pub_ia = "02" + "00" * 32
        pub_txn = "03" + "00" * 32
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "txn_mismatch",
                    "public_key": pub_txn,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.7",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
                            "identity_announcement": "ia_mismatch",
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
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": pub_ia,
                    "identity": {"username": "x", "username_signature": "ab" * 32},
                }
            ),
        ), patch(
            "yadacoin.core.nodes.verify_signature", return_value=True
        ), patch.object(
            self.config, "address_is_valid", return_value=True
        ):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)

    async def test_bad_collateral_address_skipped(self):
        """Cover line 472: continue when collateral_address missing/invalid."""
        pub = "02" + "00" * 32
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "txn_bad_collat",
                    "public_key": pub,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.8",
                            "port": 8000,
                            "collateral_address": "",
                            "identity_announcement": "ia_bad_collat",
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
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": pub,
                    "identity": {"username": "x", "username_signature": "ab" * 32},
                }
            ),
        ), patch(
            "yadacoin.core.nodes.verify_signature", return_value=True
        ), patch.object(
            self.config, "address_is_valid", return_value=False
        ):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)

    async def test_no_txn_id_skipped(self):
        """Cover line 480: continue when txn has no id field."""
        pub = "02" + "00" * 32
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "public_key": pub,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.9",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
                            "identity_announcement": "ia_no_txnid",
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
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": pub,
                    "identity": {"username": "x", "username_signature": "ab" * 32},
                }
            ),
        ), patch(
            "yadacoin.core.nodes.verify_signature", return_value=True
        ), patch.object(
            self.config, "address_is_valid", return_value=True
        ):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)

    async def test_collateral_spent_skipped(self):
        """Cover line 485: continue when _collateral_utxo_is_unspent returns False."""
        pub = "02" + "00" * 32
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "txn_spent",
                    "public_key": pub,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.10",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
                            "identity_announcement": "ia_spent",
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
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": pub,
                    "identity": {"username": "x", "username_signature": "ab" * 32},
                }
            ),
        ), patch(
            "yadacoin.core.nodes.verify_signature", return_value=True
        ), patch.object(
            self.config, "address_is_valid", return_value=True
        ), patch.object(
            Nodes, "_collateral_utxo_is_unspent", new=AsyncMock(return_value=False)
        ):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)

    async def test_collateral_exception_skipped(self):
        """Cover line 487: continue when _collateral_utxo_is_unspent raises."""
        pub = "02" + "00" * 32
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "txn_exc",
                    "public_key": pub,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.11",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
                            "identity_announcement": "ia_exc",
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
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": pub,
                    "identity": {"username": "x", "username_signature": "ab" * 32},
                }
            ),
        ), patch(
            "yadacoin.core.nodes.verify_signature", return_value=True
        ), patch.object(
            self.config, "address_is_valid", return_value=True
        ), patch.object(
            Nodes,
            "_collateral_utxo_is_unspent",
            new=AsyncMock(side_effect=Exception("db error")),
        ):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)

    async def test_duplicate_pubkey_skipped(self):
        """Cover line 495: continue when pub already in dynamic_node_public_keys."""
        pub = "02" + "00" * 32
        Nodes.dynamic_node_public_keys.add(pub)
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "txn_dup",
                    "public_key": pub,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.12",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
                            "identity_announcement": "ia_dup",
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
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": pub,
                    "identity": {"username": "x", "username_signature": "ab" * 32},
                }
            ),
        ), patch(
            "yadacoin.core.nodes.verify_signature", return_value=True
        ), patch.object(
            self.config, "address_is_valid", return_value=True
        ), patch.object(
            Nodes, "_collateral_utxo_is_unspent", new=AsyncMock(return_value=True)
        ):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 1)  # still 1

    async def test_bad_assigned_type_skipped(self):
        """Cover line 504: continue when _assign_node_type returns invalid type."""
        pub = "02" + "00" * 32
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "txn_bad_type",
                    "public_key": pub,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.13",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
                            "identity_announcement": "ia_bad_type",
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
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": pub,
                    "identity": {"username": "x", "username_signature": "ab" * 32},
                }
            ),
        ), patch(
            "yadacoin.core.nodes.verify_signature", return_value=True
        ), patch.object(
            self.config, "address_is_valid", return_value=True
        ), patch.object(
            Nodes, "_collateral_utxo_is_unspent", new=AsyncMock(return_value=True)
        ), patch.object(
            Nodes, "_assign_node_type", return_value="invalid_type"
        ):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)

    async def test_from_dict_exception_skipped(self):
        """Cover line 518: continue when creator.from_dict raises."""
        pub = "02" + "00" * 32
        block = {
            "index": CHAIN.DYNAMIC_NODES_FORK,
            "transactions": [
                {
                    "id": "txn_bad_fd",
                    "public_key": pub,
                    "relationship": {
                        "node": {
                            "host": "10.0.0.14",
                            "port": 8000,
                            "collateral_address": "1" + "C" * 33,
                            "identity_announcement": "ia_bad_fd",
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
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": pub,
                    "identity": {"username": "x", "username_signature": "ab" * 32},
                }
            ),
        ), patch(
            "yadacoin.core.nodes.verify_signature", return_value=True
        ), patch.object(
            self.config, "address_is_valid", return_value=True
        ), patch.object(
            Nodes, "_collateral_utxo_is_unspent", new=AsyncMock(return_value=True)
        ), patch.object(
            Nodes, "_assign_node_type", return_value="seed"
        ), patch(
            "yadacoin.core.nodes.Seed.from_dict", side_effect=ValueError("bad node_def")
        ):
            await Nodes.load_dynamic_nodes_from_chain()
        self.assertEqual(len(Nodes.dynamic_node_public_keys), 0)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
