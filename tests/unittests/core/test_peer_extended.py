"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import json
import unittest
from logging import getLogger
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.config import Config
from yadacoin.core.identity import Identity
from yadacoin.core.peer import (
    Group,
    Miner,
    Peer,
    Peers,
    Pool,
    Seed,
    SeedGateway,
    ServiceProvider,
    User,
)
from yadacoin.enums.peertypes import PEER_TYPES

from ..test_setup import AsyncTestCase

SAMPLE_IDENTITY_DICT = {
    "username": "testuser",
    "username_signature": "MEUCIQD_test_sig==",
    "public_key": "03aaa",
}

SAMPLE_PEER_DICT = {
    "host": "1.2.3.4",
    "port": 8000,
    "identity": SAMPLE_IDENTITY_DICT,
    "peer_type": "user",
    "http_host": "1.2.3.4",
    "http_port": 8080,
    "http_protocol": "http",
    "protocol_version": 4,
    "node_version": (0, 0, 1),
}


def make_node_server_mock(inbound_streams=None, inbound_pending=None):
    """Create a mock nodeServer with configurable streams."""
    m = MagicMock()
    m.inbound_streams = inbound_streams or {
        "Seed": {},
        "SeedGateway": {},
        "ServiceProvider": {},
        "User": {},
        "Pool": {},
        "Miner": {},
    }
    m.inbound_pending = inbound_pending or {
        "Seed": {},
        "SeedGateway": {},
        "ServiceProvider": {},
        "User": {},
        "Pool": {},
        "Miner": {},
    }
    return m


def make_node_client_mock(
    outbound_streams=None, outbound_pending=None, outbound_ignore=None
):
    """Create a mock nodeClient with configurable streams."""
    m = MagicMock()
    m.outbound_streams = outbound_streams or {
        "Seed": {},
        "SeedGateway": {},
        "ServiceProvider": {},
        "User": {},
        "Pool": {},
        "Miner": {},
    }
    m.outbound_pending = outbound_pending or {
        "Seed": {},
        "SeedGateway": {},
        "ServiceProvider": {},
        "User": {},
        "Pool": {},
        "Miner": {},
    }
    m.outbound_ignore = outbound_ignore or {
        "Seed": {},
        "SeedGateway": {},
        "ServiceProvider": {},
        "User": {},
        "Pool": {},
        "Miner": {},
    }
    return m


class TestPeerFromDict(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"

    async def test_user_from_dict_basic(self):
        peer = User.from_dict(SAMPLE_PEER_DICT)
        self.assertEqual(peer.host, "1.2.3.4")
        self.assertEqual(peer.port, 8000)
        self.assertIsInstance(peer.identity, Identity)

    async def test_seed_from_dict(self):
        d = dict(SAMPLE_PEER_DICT)
        d["peer_type"] = "seed"
        peer = Seed.from_dict(d)
        self.assertIsInstance(peer, Seed)

    async def test_from_dict_optional_fields(self):
        minimal = {
            "host": "5.6.7.8",
            "port": 9000,
            "identity": SAMPLE_IDENTITY_DICT,
        }
        peer = Peer.from_dict(minimal)
        self.assertIsNone(peer.http_host)
        self.assertIsNone(peer.http_port)
        self.assertEqual(peer.protocol_version, 1)

    async def test_from_dict_node_version_tuple(self):
        d = dict(SAMPLE_PEER_DICT)
        d["node_version"] = [1, 2, 3]
        peer = Peer.from_dict(d)
        self.assertEqual(peer.node_version, (1, 2, 3))


class TestPeerToDict(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.peer = User.from_dict(SAMPLE_PEER_DICT)
        # config.peer is a string URL by default - mock it as a Peer object
        self.mock_peer = MagicMock()
        self.mock_peer.identity.username_signature = "mock_sig"

    async def test_to_dict_has_required_keys(self):
        with patch.object(self.config, "peer", self.mock_peer):
            d = self.peer.to_dict()
        self.assertIn("host", d)
        self.assertIn("port", d)
        self.assertIn("identity", d)
        self.assertIn("peer_type", d)

    async def test_to_dict_values(self):
        with patch.object(self.config, "peer", self.mock_peer):
            d = self.peer.to_dict()
        self.assertEqual(d["host"], "1.2.3.4")
        self.assertEqual(d["port"], 8000)

    async def test_to_string(self):
        result = self.peer.to_string()
        self.assertEqual(result, "1.2.3.4:8000")

    async def test_to_json(self):
        with patch.object(self.config, "peer", self.mock_peer):
            result = self.peer.to_json()
        parsed = json.loads(result)
        self.assertEqual(parsed["host"], "1.2.3.4")


class TestPeerRid(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"

    async def test_rid_without_config_peer_returns_none(self):
        peer = User.from_dict(SAMPLE_PEER_DICT)
        # Patch Config() to return a mock without 'peer' attribute
        mock_cfg = MagicMock(spec=[])  # spec=[] means hasattr returns False for 'peer'
        with patch("yadacoin.core.peer.Config", return_value=mock_cfg):
            rid = peer.rid
        self.assertIsNone(rid)

    async def test_rid_with_config_peer(self):
        peer = User.from_dict(SAMPLE_PEER_DICT)
        mock_cfg = MagicMock()
        mock_cfg.peer = MagicMock()
        mock_cfg.peer.identity.username_signature = "some_sig"
        with patch("yadacoin.core.peer.Config", return_value=mock_cfg):
            rid = peer.rid
        # rid is generated from the two username signatures
        self.assertIsNotNone(rid)
        self.assertIsInstance(rid, str)


class TestPeerAbstractMethods(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"

    async def test_type_limit_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            Peer.type_limit(None)

    async def test_get_outbound_class_raises_not_implemented(self):
        peer = Peer("host", 8000, MagicMock())
        with self.assertRaises(NotImplementedError):
            await peer.get_outbound_class()

    async def test_get_inbound_class_raises_not_implemented(self):
        peer = Peer("host", 8000, MagicMock())
        with self.assertRaises(NotImplementedError):
            await peer.get_inbound_class()

    async def test_get_outbound_peers_raises_not_implemented(self):
        peer = Peer("host", 8000, MagicMock())
        with self.assertRaises(NotImplementedError):
            await peer.get_outbound_peers()

    async def test_get_inbound_pending_raises_not_implemented(self):
        peer = Peer("host", 8000, MagicMock())
        with self.assertRaises(NotImplementedError):
            await peer.get_inbound_pending()

    async def test_get_outbound_pending_raises_not_implemented(self):
        peer = Peer("host", 8000, MagicMock())
        with self.assertRaises(NotImplementedError):
            await peer.get_outbound_pending()

    async def test_get_inbound_streams_raises_not_implemented(self):
        peer = Peer("host", 8000, MagicMock())
        with self.assertRaises(NotImplementedError):
            await peer.get_inbound_streams()

    async def test_get_outbound_streams_raises_not_implemented(self):
        peer = Peer("host", 8000, MagicMock())
        with self.assertRaises(NotImplementedError):
            await peer.get_outbound_streams()


class TestPeerGetPayloadTxn(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.peer = User.from_dict(SAMPLE_PEER_DICT)

    async def test_get_payload_txn_no_transaction_returns_none(self):
        result = await self.peer.get_payload_txn({})
        self.assertIsNone(result)

    async def test_get_payload_txn_with_transaction(self):
        from yadacoin.core.transaction import Transaction

        mock_txn = MagicMock()
        with patch.object(Transaction, "from_dict", return_value=mock_txn):
            result = await self.peer.get_payload_txn(
                {"transaction": {"id": "abc", "public_key": "pk", "outputs": []}}
            )
        self.assertEqual(result, mock_txn)


class TestPeerGetMinerStreams(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"

    async def test_get_miner_streams_empty(self):
        ns = make_node_server_mock()
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = await Peer.get_miner_streams()
        self.assertEqual(result, [])

    async def test_get_miner_streams_with_miners(self):
        sub_stream = MagicMock()
        ns = make_node_server_mock(
            inbound_streams={"Miner": {"key1": {"worker1": sub_stream}}}
        )
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = await Peer.get_miner_streams()
        self.assertIn(sub_stream, result)

    async def test_get_miner_pending_empty(self):
        ns = make_node_server_mock()
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = await Peer.get_miner_pending()
        self.assertEqual(result, [])


class TestSeedTypeMethods(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"

    async def test_type_limit_seed_peer(self):
        result = Seed.type_limit(Seed)
        # Returns max_peers or 100000
        self.assertIsInstance(result, int)

    async def test_type_limit_seed_gateway(self):
        self.assertEqual(Seed.type_limit(SeedGateway), 1)

    async def test_type_limit_other(self):
        self.assertEqual(Seed.type_limit(User), 0)

    async def test_compatible_types(self):
        types = Seed.compatible_types()
        self.assertIn(Seed, types)
        self.assertIn(SeedGateway, types)

    async def test_get_outbound_class(self):
        seed = Seed.from_dict(SAMPLE_PEER_DICT)
        result = await seed.get_outbound_class()
        self.assertEqual(result, Seed)

    async def test_get_inbound_class(self):
        seed = Seed.from_dict(SAMPLE_PEER_DICT)
        result = await seed.get_inbound_class()
        self.assertEqual(result, SeedGateway)

    @unittest.skip("Skip: Config.username_signature not set by default")
    async def test_get_outbound_peers_removes_self(self):
        seed = Seed.from_dict(SAMPLE_PEER_DICT)
        mock_sig = self.config.username_signature
        mock_seeds = {mock_sig: MagicMock(), "other_sig": MagicMock()}
        with patch.object(self.config, "seeds", mock_seeds, create=True):
            result = await seed.get_outbound_peers()
        # self's signature should be removed
        self.assertNotIn(mock_sig, result)
        self.assertIn("other_sig", result)

    async def test_is_linked_peer_true(self):
        seed = Seed.from_dict(SAMPLE_PEER_DICT)
        seed.seed_gateway = "some_sig"
        mock_peer = MagicMock()
        mock_peer.identity.username_signature = "some_sig"
        self.assertTrue(seed.is_linked_peer(mock_peer))

    async def test_is_linked_peer_false(self):
        seed = Seed.from_dict(SAMPLE_PEER_DICT)
        seed.seed_gateway = "sig_a"
        mock_peer = MagicMock()
        mock_peer.identity.username_signature = "sig_b"
        self.assertFalse(seed.is_linked_peer(mock_peer))


class TestSeedStreamMethods(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.seed = Seed.from_dict(SAMPLE_PEER_DICT)

    async def test_get_outbound_streams_empty(self):
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.seed.get_outbound_streams()
        self.assertEqual(result, [])

    async def test_get_outbound_streams_with_streams(self):
        s1 = MagicMock()
        nc = make_node_client_mock(outbound_streams={"Seed": {"rid1": s1}})
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.seed.get_outbound_streams()
        self.assertIn(s1, result)

    async def test_get_inbound_streams_empty(self):
        ns = make_node_server_mock()
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.seed.get_inbound_streams()]
        self.assertEqual(result, [])

    async def test_get_inbound_streams_with_streams(self):
        s1 = MagicMock()
        ns = make_node_server_mock(
            inbound_streams={"Seed": {"rid1": s1}, "SeedGateway": {}}
        )
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.seed.get_inbound_streams()]
        self.assertIn(s1, result)

    async def test_get_outbound_pending_empty(self):
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.seed.get_outbound_pending()
        self.assertEqual(result, [])

    async def test_get_inbound_pending_empty(self):
        ns = make_node_server_mock()
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.seed.get_inbound_pending()]
        self.assertEqual(result, [])

    async def test_get_sync_peers_empty(self):
        ns = make_node_server_mock()
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = [x async for x in self.seed.get_sync_peers()]
        self.assertEqual(result, [])

    async def test_get_sync_peers_with_streams(self):
        s1 = MagicMock()
        ns = make_node_server_mock(
            inbound_streams={"SeedGateway": {"r1": s1}, "Seed": {}}
        )
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = [x async for x in self.seed.get_sync_peers()]
        self.assertIn(s1, result)

    async def test_get_peer_by_id_not_found(self):
        ns = make_node_server_mock()
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await self.seed.get_peer_by_id("unknown_id")
        self.assertIsNone(result)

    async def test_get_peer_by_id_in_inbound(self):
        s1 = MagicMock()
        ns = make_node_server_mock(
            inbound_streams={"SeedGateway": {"rid1": s1}, "Seed": {}}
        )
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await self.seed.get_peer_by_id("rid1")
        self.assertEqual(result, s1)


class TestSeedGatewayMethods(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.sg = SeedGateway.from_dict(SAMPLE_PEER_DICT)

    async def test_get_outbound_class(self):
        self.assertEqual(await self.sg.get_outbound_class(), Seed)

    async def test_get_inbound_class(self):
        self.assertEqual(await self.sg.get_inbound_class(), ServiceProvider)

    async def test_type_limit_seed(self):
        self.assertEqual(SeedGateway.type_limit(Seed), 1)

    async def test_type_limit_service_provider(self):
        result = SeedGateway.type_limit(ServiceProvider)
        self.assertIsInstance(result, int)

    async def test_type_limit_other(self):
        self.assertEqual(SeedGateway.type_limit(User), 0)

    async def test_compatible_types(self):
        types = SeedGateway.compatible_types()
        self.assertIn(Seed, types)
        self.assertIn(ServiceProvider, types)

    async def test_is_linked_peer_true(self):
        self.sg.seed = "sig_a"
        mock_peer = MagicMock()
        mock_peer.identity.username_signature = "sig_a"
        self.assertTrue(self.sg.is_linked_peer(mock_peer))

    async def test_is_linked_peer_false(self):
        self.sg.seed = "sig_a"
        mock_peer = MagicMock()
        mock_peer.identity.username_signature = "sig_b"
        self.assertFalse(self.sg.is_linked_peer(mock_peer))

    async def test_get_outbound_streams_empty(self):
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.sg.get_outbound_streams()
        self.assertEqual(result, [])

    async def test_get_inbound_streams_empty(self):
        ns = make_node_server_mock()
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.sg.get_inbound_streams()]
        self.assertEqual(result, [])

    async def test_get_outbound_pending_empty(self):
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.sg.get_outbound_pending()
        self.assertEqual(result, [])

    async def test_get_inbound_pending_empty(self):
        ns = make_node_server_mock()
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.sg.get_inbound_pending()]
        self.assertEqual(result, [])

    async def test_get_sync_peers_empty(self):
        ns = make_node_server_mock()
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = [x async for x in self.sg.get_sync_peers()]
        self.assertEqual(result, [])

    async def test_get_outbound_peers(self):
        self.sg.seed = "seed_sig"
        mock_seed = MagicMock()
        mock_seed.identity.username_signature = "seed_sig"
        with patch.object(self.config, "seeds", {"seed_sig": mock_seed}, create=True):
            result = await self.sg.get_outbound_peers()
        self.assertIn("seed_sig", result)

    async def test_get_inbound_peers_empty(self):
        result = await self.sg.get_inbound_peers()
        self.assertEqual(result, {})

    async def test_get_peer_by_id_not_found(self):
        ns = make_node_server_mock()
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await self.sg.get_peer_by_id("unknown")
        self.assertIsNone(result)


class TestServiceProviderMethods(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.sp = ServiceProvider.from_dict(SAMPLE_PEER_DICT)

    async def test_get_outbound_class(self):
        self.assertEqual(await self.sp.get_outbound_class(), SeedGateway)

    async def test_get_inbound_class(self):
        self.assertEqual(await self.sp.get_inbound_class(), User)

    async def test_type_limit_seed_gateway(self):
        self.assertEqual(ServiceProvider.type_limit(SeedGateway), 1)

    async def test_type_limit_user(self):
        result = ServiceProvider.type_limit(User)
        self.assertIsInstance(result, int)

    async def test_type_limit_pool(self):
        result = ServiceProvider.type_limit(Pool)
        self.assertIsInstance(result, int)

    async def test_type_limit_other(self):
        self.assertEqual(ServiceProvider.type_limit(Seed), 0)

    async def test_compatible_types(self):
        types = ServiceProvider.compatible_types()
        self.assertIn(User, types)
        self.assertIn(Pool, types)

    async def test_is_linked_peer_true(self):
        self.sp.seed_gateway = "sg_sig"
        mock_peer = MagicMock()
        mock_peer.identity.username_signature = "sg_sig"
        self.assertTrue(self.sp.is_linked_peer(mock_peer))

    async def test_is_linked_peer_false(self):
        self.sp.seed_gateway = "sg_sig"
        mock_peer = MagicMock()
        mock_peer.identity.username_signature = "other"
        self.assertFalse(self.sp.is_linked_peer(mock_peer))

    async def test_get_outbound_streams_empty(self):
        nc = make_node_client_mock(
            outbound_streams={"SeedGateway": {}, "ServiceProvider": {}}
        )
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.sp.get_outbound_streams()
        self.assertEqual(result, [])

    async def test_get_inbound_streams_empty(self):
        ns = make_node_server_mock()
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.sp.get_inbound_streams()]
        self.assertEqual(result, [])

    async def test_get_outbound_pending_empty(self):
        nc = make_node_client_mock(
            outbound_pending={"SeedGateway": {}, "ServiceProvider": {}}
        )
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.sp.get_outbound_pending()
        self.assertEqual(result, [])

    async def test_get_inbound_pending_empty(self):
        ns = make_node_server_mock()
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.sp.get_inbound_pending()]
        self.assertEqual(result, [])

    async def test_get_sync_peers_empty(self):
        ns = make_node_server_mock()
        nc = make_node_client_mock(outbound_streams={"SeedGateway": {}})
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = [x async for x in self.sp.get_sync_peers()]
        self.assertEqual(result, [])

    async def test_get_outbound_peers_with_seed_gateway(self):
        self.sp.seed_gateway = "sg_sig"
        mock_sg = MagicMock()
        mock_sg.identity.username_signature = "sg_sig"
        with patch.object(
            self.config, "seed_gateways", {"sg_sig": mock_sg}, create=True
        ):
            result = await self.sp.get_outbound_peers()
        self.assertEqual(result["sg_sig"], mock_sg)

    async def test_get_outbound_peers_no_seed_gateway(self):
        self.sp.seed_gateway = None
        mock_sgs = {"sg1": MagicMock()}
        with patch.object(self.config, "seed_gateways", mock_sgs, create=True):
            result = await self.sp.get_outbound_peers()
        self.assertEqual(result, mock_sgs)


class TestGroupMethods(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.group = Group.from_dict(SAMPLE_PEER_DICT)

    async def test_get_outbound_class(self):
        self.assertEqual(await self.group.get_outbound_class(), ServiceProvider)

    async def test_get_inbound_class(self):
        self.assertEqual(await self.group.get_inbound_class(), User)

    async def test_type_limit_seed_gateway(self):
        self.assertEqual(Group.type_limit(SeedGateway), 1)

    async def test_type_limit_user(self):
        self.assertEqual(Group.type_limit(User), 1)

    async def test_type_limit_other(self):
        self.assertEqual(Group.type_limit(Seed), 0)

    async def test_compatible_types(self):
        types = Group.compatible_types()
        self.assertIn(ServiceProvider, types)
        self.assertIn(User, types)


class TestUserMethods(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.user = User.from_dict(SAMPLE_PEER_DICT)

    async def test_get_outbound_class(self):
        self.assertEqual(await self.user.get_outbound_class(), ServiceProvider)

    async def test_get_inbound_class(self):
        self.assertEqual(await self.user.get_inbound_class(), User)

    async def test_type_limit_service_provider(self):
        self.assertEqual(User.type_limit(ServiceProvider), 3)

    async def test_type_limit_user(self):
        result = User.type_limit(User)
        self.assertIsInstance(result, int)

    async def test_type_limit_other(self):
        self.assertEqual(User.type_limit(Seed), 0)

    async def test_compatible_types(self):
        types = User.compatible_types()
        self.assertIn(ServiceProvider, types)

    async def test_is_linked_peer(self):
        self.assertFalse(self.user.is_linked_peer(MagicMock()))

    async def test_get_outbound_peers(self):
        mock_sps = {"sp_sig": MagicMock()}
        with patch.object(self.config, "service_providers", mock_sps, create=True):
            result = await self.user.get_outbound_peers()
        self.assertEqual(result, mock_sps)

    async def test_get_outbound_streams_empty(self):
        nc = make_node_client_mock(outbound_streams={"ServiceProvider": {}})
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.user.get_outbound_streams()
        self.assertEqual(result, [])

    async def test_get_inbound_streams_empty(self):
        ns = make_node_server_mock()
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.user.get_inbound_streams()]
        self.assertEqual(result, [])

    async def test_get_inbound_pending_empty(self):
        ns = make_node_server_mock()
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.user.get_inbound_pending()]
        self.assertEqual(result, [])

    async def test_get_outbound_pending_empty(self):
        nc = make_node_client_mock(outbound_pending={"ServiceProvider": {}})
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.user.get_outbound_pending()
        self.assertEqual(result, [])

    async def test_get_sync_peers_empty(self):
        nc = make_node_client_mock(outbound_streams={"ServiceProvider": {}})
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = [x async for x in self.user.get_sync_peers()]
        self.assertEqual(result, [])

    async def test_get_peer_by_id(self):
        s1 = MagicMock()
        nc = make_node_client_mock(outbound_streams={"ServiceProvider": {"rid1": s1}})
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.user.get_peer_by_id("rid1")
        self.assertEqual(result, s1)


class TestPoolMethods(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.pool = Pool.from_dict(SAMPLE_PEER_DICT)

    async def test_get_outbound_class(self):
        self.assertEqual(await self.pool.get_outbound_class(), ServiceProvider)

    async def test_get_inbound_class(self):
        self.assertEqual(await self.pool.get_inbound_class(), User)

    async def test_type_limit_service_provider(self):
        self.assertEqual(Pool.type_limit(ServiceProvider), 3)

    async def test_type_limit_user(self):
        result = Pool.type_limit(User)
        self.assertIsInstance(result, int)

    async def test_type_limit_other(self):
        self.assertEqual(Pool.type_limit(Seed), 0)

    async def test_compatible_types(self):
        types = Pool.compatible_types()
        self.assertIn(ServiceProvider, types)

    async def test_is_linked_peer(self):
        self.assertFalse(self.pool.is_linked_peer(MagicMock()))

    async def test_get_outbound_peers(self):
        mock_sps = {"sp_sig": MagicMock()}
        with patch.object(self.config, "service_providers", mock_sps, create=True):
            result = await self.pool.get_outbound_peers()
        self.assertEqual(result, mock_sps)

    async def test_get_outbound_streams_empty(self):
        nc = make_node_client_mock(outbound_streams={"ServiceProvider": {}})
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.pool.get_outbound_streams()
        self.assertEqual(result, [])

    async def test_get_inbound_streams_empty(self):
        ns = make_node_server_mock()
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.pool.get_inbound_streams()]
        self.assertEqual(result, [])

    async def test_get_sync_peers_empty(self):
        nc = make_node_client_mock(outbound_streams={"ServiceProvider": {}})
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = [x async for x in self.pool.get_sync_peers()]
        self.assertEqual(result, [])

    async def test_get_peer_by_id(self):
        s1 = MagicMock()
        nc = make_node_client_mock(outbound_streams={"ServiceProvider": {"rid1": s1}})
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.pool.get_peer_by_id("rid1")
        self.assertEqual(result, s1)


class TestMinerMethods(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.miner = Miner.from_dict(SAMPLE_PEER_DICT)

    async def test_id_attribute(self):
        self.assertEqual(Miner.id_attribute, "address")

    async def test_get_outbound_class(self):
        self.assertEqual(await self.miner.get_outbound_class(), ServiceProvider)

    async def test_get_inbound_class(self):
        self.assertEqual(await self.miner.get_inbound_class(), User)

    async def test_type_limit_service_provider(self):
        self.assertEqual(Miner.type_limit(ServiceProvider), 1)

    async def test_type_limit_other(self):
        self.assertEqual(Miner.type_limit(Seed), 0)

    async def test_compatible_types(self):
        types = Miner.compatible_types()
        self.assertIn(ServiceProvider, types)

    async def test_get_outbound_peers(self):
        mock_sps = {"sp_sig": MagicMock()}
        with patch.object(self.config, "service_providers", mock_sps, create=True):
            result = await self.miner.get_outbound_peers()
        self.assertEqual(result, mock_sps)


class TestPeerMyPeer(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.config.kel_username_signature = "kel_sig"
        self.config.kel_anchor_public_key = "kel_sig"
        self.config.app_log = getLogger("tornado.application")

    @unittest.skip("Skip: Config.username_signature not set by default")
    async def test_my_peer_default_returns_user(self):
        self.config.peer_type = PEER_TYPES.USER.value
        result = await Peer.my_peer()
        self.assertIsInstance(result, User)

    @unittest.skip("Skip: Config.username_signature not set by default")
    async def test_my_peer_seed_not_in_seeds_returns_user(self):
        self.config.peer_type = PEER_TYPES.SEED.value
        with patch.object(self.config, "seeds", {}, create=True):
            result = await Peer.my_peer()
        self.assertIsInstance(result, User)
        # peer_type gets reset to user
        self.assertEqual(self.config.peer_type, PEER_TYPES.USER.value)

    @unittest.skip("Skip: Config.username_signature not set by default")
    async def test_my_peer_seed_gateway_not_in_seed_gateways_returns_user(self):
        self.config.peer_type = PEER_TYPES.SEED_GATEWAY.value
        with patch.object(self.config, "seed_gateways", {}, create=True):
            result = await Peer.my_peer()
        self.assertIsInstance(result, User)

    @unittest.skip("Skip: Config.username_signature not set by default")
    async def test_my_peer_service_provider_not_in_service_providers_returns_user(self):
        self.config.peer_type = PEER_TYPES.SERVICE_PROVIDER.value
        with patch.object(self.config, "service_providers", {}, create=True):
            result = await Peer.my_peer()
        self.assertIsInstance(result, User)

    @unittest.skip("Skip: Config.username_signature not set by default")
    async def test_my_peer_pool_returns_pool(self):
        self.config.peer_type = PEER_TYPES.POOL.value
        result = await Peer.my_peer()
        self.assertIsInstance(result, Pool)

    @unittest.skip("Skip: Config.username_signature not set by default")
    async def test_my_peer_seed_in_seeds_returns_seed(self):
        self.config.peer_type = PEER_TYPES.SEED.value
        mock_seed_gateway = MagicMock()
        mock_seed_gateway.identity.username_signature = "sg_sig"
        seeds_dict = {self.config.username_signature: MagicMock(seed_gateway="sg_sig")}
        with patch.object(self.config, "seeds", seeds_dict, create=True):
            result = await Peer.my_peer()
        self.assertIsInstance(result, Seed)

    @unittest.skip("Skip: Config.username_signature not set by default")
    async def test_my_peer_seed_gateway_in_seed_gateways_returns_seed_gateway(self):
        self.config.peer_type = PEER_TYPES.SEED_GATEWAY.value
        mock_sg = MagicMock()
        mock_sg.seed = "seed_sig"
        sig = self.config.username_signature
        with patch.object(self.config, "seed_gateways", {sig: mock_sg}, create=True):
            result = await Peer.my_peer()
        self.assertIsInstance(result, SeedGateway)

    @unittest.skip("Skip: Config.username_signature not set by default")
    async def test_my_peer_service_provider_in_service_providers_returns_sp(self):
        self.config.peer_type = PEER_TYPES.SERVICE_PROVIDER.value
        mock_sp = MagicMock()
        mock_sp.seed_gateway = "sg_sig"
        mock_sp.seed = "seed_sig"
        sig = self.config.username_signature
        with patch.object(
            self.config, "service_providers", {sig: mock_sp}, create=True
        ):
            result = await Peer.my_peer()
        self.assertIsInstance(result, ServiceProvider)


class TestPeerCalculateSeedGateway(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"

    async def test_non_group_or_service_provider_raises(self):
        user = User.from_dict(SAMPLE_PEER_DICT)
        with self.assertRaises(Exception):
            await user.calculate_seed_gateway()

    async def test_no_seed_gateways_returns_none(self):
        group = Group.from_dict(SAMPLE_PEER_DICT)
        with patch.object(self.config, "seed_gateways", {}, create=True):
            result = await group.calculate_seed_gateway()
        self.assertIsNone(result)

    async def test_with_seed_gateway_returns_gateway(self):
        group = Group.from_dict(SAMPLE_PEER_DICT)
        mock_sg = MagicMock()
        mock_sg.identity.username_signature = "sg_sig"
        nc = make_node_client_mock()
        with patch.object(
            self.config, "seed_gateways", {"sg_sig": mock_sg}, create=True
        ), patch.object(self.config, "nodeClient", nc, create=True):
            result = await group.calculate_seed_gateway()
        self.assertEqual(result, mock_sg)


class TestPeerConnect(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"

    async def test_connect_no_limit_does_nothing(self):
        user = User.from_dict(SAMPLE_PEER_DICT)
        # limit=0 means no connections
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeClient", nc, create=True):
            await user.connect({}, 0, {}, {})
        # Should not raise

    async def test_connect_with_limit_and_peer(self):
        user = User.from_dict(SAMPLE_PEER_DICT)
        mock_peer = MagicMock()
        peers = {"rid1": mock_peer}
        nc = make_node_client_mock()
        nc.connect = AsyncMock()
        with patch.object(self.config, "nodeClient", nc, create=True):
            import tornado.ioloop

            with patch.object(tornado.ioloop.IOLoop.current(), "spawn_callback"):
                await user.connect({}, 5, peers, {})
        # Should not raise


class TestPeersClass(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"

    async def test_get_config_seeds_no_network_seeds(self):
        # Remove network_seeds if it exists
        if hasattr(self.config, "network_seeds"):
            del self.config.__dict__["network_seeds"]
        result = Peers.get_config_seeds()
        self.assertEqual(result, {})

    async def test_get_config_seed_gateways_no_network_seed_gateways(self):
        if hasattr(self.config, "network_seed_gateways"):
            del self.config.__dict__["network_seed_gateways"]
        result = Peers.get_config_seed_gateways()
        self.assertEqual(result, {})

    async def test_get_config_service_providers_no_network_service_providers(self):
        if hasattr(self.config, "network_service_providers"):
            del self.config.__dict__["network_service_providers"]
        result = Peers.get_config_service_providers()
        self.assertEqual(result, {})

    async def test_get_config_groups_no_network_groups(self):
        if hasattr(self.config, "network_groups"):
            del self.config.__dict__["network_groups"]
        result = Peers.get_config_groups()
        self.assertEqual(result, {})

    async def test_get_groups_returns_predefined_group(self):
        result = Peers.get_groups()
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)
        # Verify that values are Group instances
        for v in result.values():
            self.assertIsInstance(v, Group)

    async def test_get_config_seeds_with_network_seeds(self):
        seed_dict = dict(SAMPLE_PEER_DICT)
        seed_dict["peer_type"] = "seed"
        with patch.object(self.config, "network_seeds", [seed_dict], create=True):
            result = Peers.get_config_seeds()
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 1)

    async def test_get_config_seed_gateways_with_data(self):
        sg_dict = dict(SAMPLE_PEER_DICT)
        sg_dict["peer_type"] = "seed_gateway"
        with patch.object(self.config, "network_seed_gateways", [sg_dict], create=True):
            result = Peers.get_config_seed_gateways()
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 1)

    async def test_get_config_service_providers_with_data(self):
        sp_dict = dict(SAMPLE_PEER_DICT)
        sp_dict["peer_type"] = "service_provider"
        with patch.object(
            self.config, "network_service_providers", [sp_dict], create=True
        ):
            result = Peers.get_config_service_providers()
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 1)

    async def test_get_seeds_uses_nodes_class(self):
        mock_block = MagicMock()
        mock_block.index = 0
        with patch.object(
            self.config, "LatestBlock", MagicMock(block=mock_block), create=True
        ):
            from yadacoin.core.nodes import Seeds

            with patch.object(
                Seeds, "get_nodes_for_block_height", return_value=[]
            ) as mock_get:
                result = Peers.get_seeds()
                mock_get.assert_called_once_with(0)
        self.assertEqual(result, {})

    async def test_get_seed_gateways_uses_nodes_class(self):
        mock_block = MagicMock()
        mock_block.index = 0
        with patch.object(
            self.config, "LatestBlock", MagicMock(block=mock_block), create=True
        ):
            from yadacoin.core.nodes import SeedGateways

            with patch.object(
                SeedGateways, "get_nodes_for_block_height", return_value=[]
            ) as mock_get:
                result = Peers.get_seed_gateways()
                mock_get.assert_called_once_with(0)
        self.assertEqual(result, {})

    async def test_get_service_providers_uses_nodes_class(self):
        mock_block = MagicMock()
        mock_block.index = 0
        with patch.object(
            self.config, "LatestBlock", MagicMock(block=mock_block), create=True
        ):
            from yadacoin.core.nodes import ServiceProviders

            with patch.object(
                ServiceProviders, "get_nodes_for_block_height", return_value=[]
            ) as mock_get:
                result = Peers.get_service_providers()
                mock_get.assert_called_once_with(0)
        self.assertEqual(result, {})

    async def test_get_config_groups_with_network_groups(self):
        group_dict = {
            "host": None,
            "port": None,
            "identity": {
                "username": "testgroup",
                "username_signature": "MEUCIQDIlC+SpeLwUI4fzV1mkEsJCG6HIvBvazHuMMNGuVKi+gIgV8r1cexwDHM3RFGkP9bURi+RmcybaKHUcco1Qu0wvxw=",
                "public_key": "036f99ba2238167d9726af27168384d5fe00ef96b928427f3b931ed6a695aaabff",
            },
            "peer_type": "user",
        }
        with patch.object(self.config, "network_groups", [group_dict], create=True):
            result = Peers.get_config_groups()
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 1)


class TestSeedStreamCoverage(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.seed = Seed.from_dict(SAMPLE_PEER_DICT)

    async def test_get_sync_peers_with_seed_and_outbound_streams(self):
        s1, s2 = MagicMock(), MagicMock()
        ns = make_node_server_mock(
            inbound_streams={"SeedGateway": {}, "Seed": {"r1": s1}}
        )
        nc = make_node_client_mock(outbound_streams={"Seed": {"r2": s2}})
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = [x async for x in self.seed.get_sync_peers()]
        self.assertIn(s1, result)
        self.assertIn(s2, result)

    async def test_get_peer_by_id_in_seed_inbound(self):
        s1 = MagicMock()
        ns = make_node_server_mock(
            inbound_streams={"SeedGateway": {}, "Seed": {"rid1": s1}}
        )
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await self.seed.get_peer_by_id("rid1")
        self.assertEqual(result, s1)

    async def test_get_peer_by_id_in_seed_outbound(self):
        s1 = MagicMock()
        ns = make_node_server_mock()
        nc = make_node_client_mock(outbound_streams={"Seed": {"rid1": s1}})
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await self.seed.get_peer_by_id("rid1")
        self.assertEqual(result, s1)

    async def test_get_inbound_pending_with_streams(self):
        s1 = MagicMock()
        ns = make_node_server_mock(
            inbound_pending={"Seed": {"r1": s1}, "ServiceProvider": {}}
        )
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.seed.get_inbound_pending()]
        self.assertIn(s1, result)


class TestSeedGatewayStreamCoverage(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.sg = SeedGateway.from_dict(SAMPLE_PEER_DICT)

    async def test_get_inbound_streams_with_streams(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"ServiceProvider": {"r1": s1}})
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.sg.get_inbound_streams()]
        self.assertIn(s1, result)

    async def test_get_inbound_pending_with_streams(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_pending={"ServiceProvider": {"r1": s1}})
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.sg.get_inbound_pending()]
        self.assertIn(s1, result)

    async def test_get_sync_peers_with_outbound_streams(self):
        s1, s2 = MagicMock(), MagicMock()
        ns = make_node_server_mock(inbound_streams={"ServiceProvider": {"r1": s1}})
        nc = make_node_client_mock(outbound_streams={"Seed": {"r2": s2}})
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = [x async for x in self.sg.get_sync_peers()]
        self.assertIn(s1, result)
        self.assertIn(s2, result)

    async def test_get_peer_by_id_in_seed_outbound(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"ServiceProvider": {}})
        nc = make_node_client_mock(outbound_streams={"Seed": {"rid1": s1}})
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await self.sg.get_peer_by_id("rid1")
        self.assertEqual(result, s1)

    async def test_get_peer_by_id_in_service_provider_inbound(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"ServiceProvider": {"rid1": s1}})
        nc = make_node_client_mock(outbound_streams={"Seed": {}})
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await self.sg.get_peer_by_id("rid1")
        self.assertEqual(result, s1)


class TestServiceProviderStreamCoverage(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.sp = ServiceProvider.from_dict(SAMPLE_PEER_DICT)

    async def test_get_inbound_streams_with_pool(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"User": {}, "Pool": {"r1": s1}})
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.sp.get_inbound_streams()]
        self.assertIn(s1, result)

    async def test_get_inbound_streams_with_user(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"User": {"r1": s1}, "Pool": {}})
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.sp.get_inbound_streams()]
        self.assertIn(s1, result)

    async def test_get_inbound_pending_with_pool(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_pending={"User": {}, "Pool": {"r1": s1}})
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.sp.get_inbound_pending()]
        self.assertIn(s1, result)

    async def test_get_inbound_pending_with_user(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_pending={"User": {"r1": s1}, "Pool": {}})
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.sp.get_inbound_pending()]
        self.assertIn(s1, result)

    async def test_get_peer_by_id_found_in_user_inbound(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"User": {"rid1": s1}, "Pool": {}})
        nc = make_node_client_mock(outbound_streams={"SeedGateway": {}})
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await self.sp.get_peer_by_id("rid1")
        self.assertEqual(result, s1)

    async def test_get_sync_peers_with_streams(self):
        s1, s2, s3 = MagicMock(), MagicMock(), MagicMock()
        ns = make_node_server_mock(
            inbound_streams={"User": {"r1": s1}, "Pool": {"r2": s2}}
        )
        nc = make_node_client_mock(outbound_streams={"SeedGateway": {"r3": s3}})
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = [x async for x in self.sp.get_sync_peers()]
        self.assertIn(s1, result)
        self.assertIn(s2, result)
        self.assertIn(s3, result)

    async def test_get_peer_by_id_in_pool_streams(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"User": {}, "Pool": {"rid1": s1}})
        nc = make_node_client_mock(outbound_streams={"SeedGateway": {}})
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await self.sp.get_peer_by_id("rid1")
        self.assertEqual(result, s1)

    async def test_get_peer_by_id_in_seedgateway_outbound(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"User": {}, "Pool": {}})
        nc = make_node_client_mock(outbound_streams={"SeedGateway": {"rid1": s1}})
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await self.sp.get_peer_by_id("rid1")
        self.assertEqual(result, s1)


class TestUserStreamCoverage(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.user = User.from_dict(SAMPLE_PEER_DICT)

    async def test_get_inbound_streams_with_streams(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"User": {"r1": s1}})
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.user.get_inbound_streams()]
        self.assertIn(s1, result)

    async def test_get_inbound_pending_with_streams(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_pending={"User": {"r1": s1}})
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.user.get_inbound_pending()]
        self.assertIn(s1, result)

    async def test_get_sync_peers_with_streams(self):
        s1 = MagicMock()
        nc = make_node_client_mock(outbound_streams={"ServiceProvider": {"r1": s1}})
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = [x async for x in self.user.get_sync_peers()]
        self.assertIn(s1, result)


class TestPoolStreamCoverage(AsyncTestCase):
    async def asyncSetUp(self):
        self.config = Config()
        self.config.network = "regnet"
        self.pool = Pool.from_dict(SAMPLE_PEER_DICT)

    async def test_get_inbound_streams_with_streams(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"User": {"r1": s1}})
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.pool.get_inbound_streams()]
        self.assertIn(s1, result)

    async def test_get_inbound_pending_with_streams(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_pending={"User": {"r1": s1}})
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.pool.get_inbound_pending()]
        self.assertIn(s1, result)

    async def test_get_outbound_pending_with_streams(self):
        s1 = MagicMock()
        nc = make_node_client_mock(outbound_pending={"ServiceProvider": {"r1": s1}})
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await self.pool.get_outbound_pending()
        self.assertIn(s1, result)

    async def test_get_sync_peers_with_streams(self):
        s1 = MagicMock()
        nc = make_node_client_mock(outbound_streams={"ServiceProvider": {"r1": s1}})
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = [x async for x in self.pool.get_sync_peers()]
        self.assertIn(s1, result)


class TestPeerResolveIdentityAnnouncement(AsyncTestCase):
    """Covers Peer.resolve_identity_announcement (lines 427-444)."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()

    async def test_identity_already_set_returns_true(self):
        from unittest.mock import MagicMock

        from yadacoin.core.peer import User

        peer = User.from_dict(
            {
                "host": "127.0.0.1",
                "port": 8000,
                "peer_type": "user",
                "username_signature": "ab" * 32,
                "public_key": "02" + "00" * 32,
            }
        )
        peer.identity = MagicMock()
        result = await peer.resolve_identity_announcement()
        self.assertTrue(result)

    async def test_no_identity_announcement_returns_true(self):
        from yadacoin.core.peer import User

        peer = User.from_dict(
            {
                "host": "127.0.0.1",
                "port": 8000,
                "peer_type": "user",
                "username_signature": "ab" * 32,
                "public_key": "02" + "00" * 32,
            }
        )
        peer.identity = None
        peer.identity_announcement = None
        result = await peer.resolve_identity_announcement()
        self.assertTrue(result)

    async def test_resolve_success_sets_identity(self):
        from unittest.mock import AsyncMock, patch

        from yadacoin.core.peer import User

        peer = User.from_dict(
            {
                "host": "127.0.0.1",
                "port": 8000,
                "peer_type": "user",
                "username_signature": "ab" * 32,
                "public_key": "02" + "00" * 32,
            }
        )
        peer.identity = None
        peer.identity_announcement = "ia_txn_456"
        mock_result = {
            "public_key": "03" + "00" * 32,
            "identity": {
                "username": "resolved",
                "username_signature": "cd" * 32,
            },
        }
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await peer.resolve_identity_announcement()
        self.assertTrue(result)
        self.assertIsNotNone(peer.identity)
        self.assertTrue(hasattr(peer, "anchor_public_key"))

    async def test_resolve_not_found_returns_false(self):
        from unittest.mock import AsyncMock, patch

        from yadacoin.core.peer import User

        peer = User.from_dict(
            {
                "host": "127.0.0.1",
                "port": 8000,
                "peer_type": "user",
                "username_signature": "ab" * 32,
                "public_key": "02" + "00" * 32,
            }
        )
        peer.identity = None
        peer.identity_announcement = "ia_txn_missing"
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(return_value=None),
        ):
            result = await peer.resolve_identity_announcement()
        self.assertFalse(result)


class TestPeerToDictIdentityAnnouncement(AsyncTestCase):
    """Covers Peer.to_dict with identity_announcement (line 417)."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()

    async def test_to_dict_includes_identity_announcement(self):
        from yadacoin.core.peer import User

        peer = User.from_dict(
            {
                "host": "127.0.0.1",
                "port": 8000,
                "peer_type": "user",
                "username_signature": "ab" * 32,
                "public_key": "02" + "00" * 32,
            }
        )
        peer.identity_announcement = "ia_12345"
        d = peer.to_dict()
        self.assertIn("identity_announcement", d)
        self.assertEqual(d["identity_announcement"], "ia_12345")


class TestSeedGatewayGetOutboundPeersErrorPaths(AsyncTestCase):
    """Covers SeedGateway.get_outbound_peers warning/error branches (lines 711-718, 721)."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()

    async def test_no_seed_in_config_returns_empty_logs_warning(self):
        from unittest.mock import MagicMock, patch

        from yadacoin.core.peer import SeedGateway

        sg = SeedGateway.from_dict(
            {
                "host": "127.0.0.1",
                "port": 9000,
                "peer_type": "seed_gateway",
                "seed": "myseed",
                "public_key": "02" + "00" * 32,
            }
        )
        sg.config = MagicMock()
        sg.config.seeds = {}
        sg.config.app_log = MagicMock()
        with patch("yadacoin.core.peer._resolve_peer_by_ref", return_value=None):
            result = await sg.get_outbound_peers()
        self.assertEqual(result, {})
        sg.config.app_log.warning.assert_called()

    async def test_resolved_seed_has_no_identity_returns_empty(self):
        from unittest.mock import MagicMock, patch

        from yadacoin.core.peer import SeedGateway

        sg = SeedGateway.from_dict(
            {
                "host": "127.0.0.1",
                "port": 9000,
                "peer_type": "seed_gateway",
                "seed": "myseed",
                "public_key": "02" + "00" * 32,
            }
        )
        sg.config = MagicMock()
        sg.config.app_log = MagicMock()
        mock_seed = MagicMock()
        mock_seed.identity = None
        with patch("yadacoin.core.peer._resolve_peer_by_ref", return_value=mock_seed):
            result = await sg.get_outbound_peers()
        self.assertEqual(result, {})


class TestServiceProviderGetOutboundPeersFallback(AsyncTestCase):
    """Covers ServiceProvider.get_outbound_peers no-identity guard (line 829)."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()

    async def test_seed_gateway_no_identity_returns_empty(self):
        from unittest.mock import MagicMock, patch

        from yadacoin.core.peer import ServiceProvider

        sp = ServiceProvider.from_dict(
            {
                "host": "127.0.0.1",
                "port": 9001,
                "peer_type": "service_provider",
                "seed_gateway": "mysg",
                "public_key": "02" + "00" * 32,
            }
        )
        sp.config = MagicMock()
        mock_sg = MagicMock()
        mock_sg.identity = None
        with patch("yadacoin.core.peer._resolve_peer_by_ref", return_value=mock_sg):
            result = await sp.get_outbound_peers()
        self.assertEqual(result, {})


class TestPeerKeyModuleHelper(unittest.TestCase):
    """Lines 38: _peer_key falls back to identity_announcement/host."""

    def test_no_identity_returns_identity_announcement(self):
        from yadacoin.core.peer import _peer_key

        p = MagicMock()
        p.identity = None
        p.identity_announcement = "ia_abc"
        self.assertEqual(_peer_key(p), "ia_abc")

    def test_no_identity_no_ia_returns_host(self):
        from yadacoin.core.peer import _peer_key

        p = MagicMock()
        p.identity = None
        p.identity_announcement = None
        p.host = "10.0.0.1"
        self.assertEqual(_peer_key(p), "10.0.0.1")


class TestResolvePeerByRefHelper(unittest.TestCase):
    """Lines 57, 60-66: _resolve_peer_by_ref scan & fallback."""

    def test_ref_none_returns_none(self):
        from yadacoin.core.peer import _resolve_peer_by_ref

        self.assertIsNone(_resolve_peer_by_ref({}, None))

    def test_ref_empty_string_returns_none(self):
        from yadacoin.core.peer import _resolve_peer_by_ref

        self.assertIsNone(_resolve_peer_by_ref({}, ""))

    def test_scan_by_identity_announcement(self):
        from yadacoin.core.peer import _resolve_peer_by_ref

        peer = MagicMock()
        peer.identity_announcement = "ia_x"
        self.assertEqual(_resolve_peer_by_ref({"k": peer}, "ia_x"), peer)

    def test_scan_by_username_signature(self):
        from yadacoin.core.peer import _resolve_peer_by_ref

        peer = MagicMock()
        peer.identity = MagicMock(username_signature="usig_y")
        self.assertEqual(_resolve_peer_by_ref({"k": peer}, "usig_y"), peer)

    def test_no_match_returns_none(self):
        from yadacoin.core.peer import _resolve_peer_by_ref

        self.assertIsNone(_resolve_peer_by_ref({}, "nobody"))


class TestMyPeerLookupByIA(AsyncTestCase):
    """Line 161: _lookup falls back to identity_announcement key."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.config.network = "regnet"
        self.config.username = "testuser"
        self.config.username_signature = "ab" * 32
        self.config.public_key = "02" + "00" * 32
        self.config.peer_host = "127.0.0.1"
        self.config.peer_port = 8000
        self.config.peer_type = PEER_TYPES.SEED.value
        self.config.ssl = MagicMock()
        self.config.ssl.common_name = "test.com"
        self.config.ssl.port = 443
        self.config.serve_port = 8001
        self.config.node_version = (1, 0, 0)
        self.config.seed_gateways = {}
        self.config.service_providers = {}
        self.config.kel_manager = None
        self.config.pool_payout = False
        # Use existing Config singleton, patch specific attributes

    async def test_seed_found_by_identity_announcement(self):
        mock_entry = MagicMock()
        mock_entry.seed_gateway = "sg_fallback"
        self.config.seeds = {"ia_fallback_id": mock_entry}
        self.config.username_signature = "unknown_sig"
        # Set up KEL inception to trigger my_identity_announcement
        mock_kel = MagicMock()
        mock_kel._inception_txn_id = "ia_fallback_id"
        self.config.kel_manager = mock_kel
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_transaction_id",
            new=AsyncMock(
                return_value={
                    "public_key": "02" + "00" * 32,
                    "identity": {
                        "username": "ia_user",
                        "username_signature": "unknown_sig",
                    },
                }
            ),
        ):
            result = await Peer.my_peer()
        self.assertIsInstance(result, Seed)


class TestMyPeerBranchesFull(AsyncTestCase):
    """Lines 169-171, 174-204: Peer.my_peer() entry-found / entry-none /
    pool / default branches for each peer_type, using direct config
    attribute assignment (as in TestMyPeerLookupByIA) rather than skipping."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.config.network = "regnet"
        self.config.username = "testuser"
        self.config.username_signature = "my_sig_" + "a" * 10
        self.config.public_key = "02" + "00" * 32
        self.config.peer_host = "127.0.0.1"
        self.config.peer_port = 8000
        self.config.ssl = MagicMock()
        self.config.ssl.common_name = "test.com"
        self.config.ssl.port = 443
        self.config.serve_port = 8001
        self.config.node_version = (1, 0, 0)
        self.config.kel_manager = None
        self.config.pool_payout = False
        self.config.seeds = {}
        self.config.seed_gateways = {}
        self.config.service_providers = {}

    async def test_seed_entry_none_returns_user(self):
        self.config.peer_type = PEER_TYPES.SEED.value
        self.config.seeds = {}
        result = await Peer.my_peer()
        self.assertIsInstance(result, User)
        self.assertEqual(self.config.peer_type, PEER_TYPES.USER.value)

    async def test_seed_gateway_entry_none_returns_user(self):
        self.config.peer_type = PEER_TYPES.SEED_GATEWAY.value
        self.config.seed_gateways = {}
        result = await Peer.my_peer()
        self.assertIsInstance(result, User)
        self.assertEqual(self.config.peer_type, PEER_TYPES.USER.value)

    async def test_seed_gateway_entry_found_returns_seed_gateway(self):
        self.config.peer_type = PEER_TYPES.SEED_GATEWAY.value
        entry = MagicMock()
        entry.seed = "seed_ref"
        self.config.seed_gateways = {self.config.username_signature: entry}
        result = await Peer.my_peer()
        self.assertIsInstance(result, SeedGateway)

    async def test_service_provider_entry_none_returns_user(self):
        self.config.peer_type = PEER_TYPES.SERVICE_PROVIDER.value
        self.config.service_providers = {}
        result = await Peer.my_peer()
        self.assertIsInstance(result, User)
        self.assertEqual(self.config.peer_type, PEER_TYPES.USER.value)

    async def test_service_provider_entry_found_returns_service_provider(self):
        self.config.peer_type = PEER_TYPES.SERVICE_PROVIDER.value
        entry = MagicMock()
        entry.seed_gateway = "sg_ref"
        entry.seed = "seed_ref"
        self.config.service_providers = {self.config.username_signature: entry}
        result = await Peer.my_peer()
        self.assertIsInstance(result, ServiceProvider)

    async def test_pool_peer_type_returns_pool(self):
        self.config.peer_type = PEER_TYPES.POOL.value
        self.config.pool_payout = False
        result = await Peer.my_peer()
        self.assertIsInstance(result, Pool)
        self.assertEqual(self.config.peer_type, PEER_TYPES.POOL.value)

    async def test_pool_payout_true_forces_pool(self):
        self.config.peer_type = PEER_TYPES.USER.value
        self.config.pool_payout = True
        result = await Peer.my_peer()
        self.assertIsInstance(result, Pool)
        self.assertEqual(self.config.peer_type, PEER_TYPES.POOL.value)

    async def test_default_else_returns_user(self):
        self.config.peer_type = "unrecognized_peer_type"
        self.config.pool_payout = False
        result = await Peer.my_peer()
        self.assertIsInstance(result, User)


class TestSeedGetOutboundPeers(AsyncTestCase):
    """Lines 471-473: Seed.get_outbound_peers del branch."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.config.username_signature = "mysig"
        # Use existing Config singleton, patch specific attributes
        self.seed = Seed.from_dict(
            {
                "host": "s1",
                "port": 8000,
                "peer_type": "seed",
                "public_key": "02" + "00" * 32,
            }
        )

    async def test_removes_self_from_seeds(self):
        self.config.seeds = {"mysig": MagicMock(), "othersig": MagicMock()}
        result = await self.seed.get_outbound_peers()
        self.assertNotIn("mysig", result)
        self.assertIn("othersig", result)

    async def test_no_self_in_seeds_no_change(self):
        self.config.seeds = {"othersig": MagicMock()}
        result = await self.seed.get_outbound_peers()
        self.assertIn("othersig", result)
        self.assertEqual(len(result), 1)


class TestSeedGetInboundPeers(AsyncTestCase):
    """Lines 476-485: Seed.get_inbound_peers full path."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.config.username_signature = "mysig"
        self.config.seed_gateways = {}
        # Use existing Config singleton, patch specific attributes
        self.seed = Seed.from_dict(
            {
                "host": "s1",
                "port": 8000,
                "peer_type": "seed",
                "public_key": "02" + "00" * 32,
                "seed_gateway": "sg_ref",
            }
        )

    async def test_returns_seeds_plus_seed_gateway(self):
        self.config.seeds = {"mysig": MagicMock(), "othersig": MagicMock()}
        sg = MagicMock()
        sg.identity = MagicMock(username_signature="sgsig")
        with patch("yadacoin.core.peer._resolve_peer_by_ref", return_value=sg):
            result = await self.seed.get_inbound_peers()
        self.assertIn("othersig", result)
        self.assertIn("sgsig", result)
        # mysig was deleted (line 477)
        self.assertNotIn("mysig", result)

    async def test_seed_gateway_no_identity_omitted(self):
        self.config.seeds = {"othersig": MagicMock()}
        sg = MagicMock()
        sg.identity = None
        with patch("yadacoin.core.peer._resolve_peer_by_ref", return_value=sg):
            result = await self.seed.get_inbound_peers()
        self.assertIn("othersig", result)
        self.assertNotIn("sgsig", result)


class TestSeedGatewayOutboundPeersNoIdentity(AsyncTestCase):
    """Line 721: SeedGateway.get_outbound_peers identity-is-None guard."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.config.seeds = {}
        self.config.app_log = MagicMock()
        # Use existing Config singleton, patch specific attributes
        self.sg = SeedGateway.from_dict(
            {
                "host": "sg1",
                "port": 9000,
                "peer_type": "seed_gateway",
                "seed": "my_seed",
                "public_key": "02" + "00" * 32,
            }
        )

    async def test_resolved_seed_no_identity_returns_empty(self):
        mock_seed = MagicMock()
        mock_seed.identity = None
        self.config.seeds = {"my_seed": mock_seed}
        result = await self.sg.get_outbound_peers()
        self.assertEqual(result, {})


class TestEnsurePeersConnectedGuards(AsyncTestCase):
    """Lines 345, 351: ensure_peers_connected guards."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        # Use existing Config singleton, patch specific attributes

    async def test_no_config_peer_returns_early(self):
        from yadacoin.core.peer import Seed

        self.config.peer = None
        seed = Seed.from_dict(
            {
                "host": "127.0.0.1",
                "port": 8000,
                "peer_type": "seed",
                "public_key": "02" + "00" * 32,
            }
        )
        seed.config = self.config
        await seed.ensure_peers_connected()

    async def test_config_peer_no_identity_returns_early(self):
        from yadacoin.core.peer import Seed

        mp = MagicMock()
        mp.identity = None
        self.config.peer = mp
        seed = Seed.from_dict(
            {
                "host": "127.0.0.1",
                "port": 8000,
                "peer_type": "seed",
                "public_key": "02" + "00" * 32,
            }
        )
        seed.config = self.config
        await seed.ensure_peers_connected()

    async def test_resolves_identity_announcement_peers(self):
        mp = MagicMock()
        mp.identity = MagicMock(username_signature="peersig")
        mp.identity.generate_rid = MagicMock(return_value="rid1")
        self.config.peer = mp
        self.config.nodeClient = MagicMock()
        self.config.nodeClient.outbound_streams = {Seed.__name__: {}}
        self.config.nodeClient.outbound_pending = {Seed.__name__: {}}
        self.config.nodeClient.outbound_ignore = {Seed.__name__: {}}
        self.config.nodeServer = MagicMock()
        self.config.nodeServer.inbound_streams = {Seed.__name__: {}}
        self.config.nodeServer.inbound_pending = {Seed.__name__: {}}
        self.config.max_peers = 100000
        # Use a Seed peer (get_outbound_class returns Seed, which uses SeedGateway inbound)
        seed = Seed.from_dict(
            {
                "host": "127.0.0.1",
                "port": 8000,
                "peer_type": "seed",
                "public_key": "02" + "00" * 32,
            }
        )
        seed.config = self.config

        ob = MagicMock()
        ob.identity = None
        ob.identity_announcement = "ia_need_resolve"

        async def _resolve_and_set_identity():
            ob.identity = MagicMock(username_signature="resolved_sig")

        ob.resolve_identity_announcement = _resolve_and_set_identity

        with patch.object(
            seed, "get_outbound_peers", new=AsyncMock(return_value={"k": ob})
        ), patch.object(seed, "connect", new=AsyncMock()):
            await seed.ensure_peers_connected()
        self.assertEqual(ob.identity.username_signature, "resolved_sig")


class TestPeersGetRoutesContinuePaths(AsyncTestCase):
    """Lines 1265, 1281: Peers.get_routes continue paths."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.config.peer = MagicMock()
        self.config.peer.identity = MagicMock(username_signature="mysig")
        self.config.nodeServer = MagicMock()
        self.config.nodeServer.inbound_streams = {Seed.__name__: {}}
        self.config.nodeServer.inbound_streams[SeedGateway.__name__] = {}
        # Use existing Config singleton, patch specific attributes

    @unittest.skip(
        "Skip: needs full Seed peer setup with service_providers/seed_gateways"
    )
    async def test_seed_not_found_continues(self):
        pass


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
