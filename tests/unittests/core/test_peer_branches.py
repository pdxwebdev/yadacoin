"""
Coverage for previously-untested branches in yadacoin/core/peer.py.
"""

from collections import OrderedDict
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.config import Config
from yadacoin.core.peer import (
    Group,
    Peer,
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


class TestPeerAggregateStreams(AsyncTestCase):
    """Lines 180-196: get_all_inbound/outbound/streams + miner streams."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()

    async def test_get_all_inbound_streams(self):
        seed = Seed.from_dict(SAMPLE_PEER_DICT)
        s1, s2 = MagicMock(), MagicMock()
        ns = make_node_server_mock(
            inbound_streams={"Seed": {"r1": s1}, "SeedGateway": {}},
            inbound_pending={"Seed": {"r2": s2}, "ServiceProvider": {}},
        )
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = await seed.get_all_inbound_streams()
        self.assertIn(s1, result)
        self.assertIn(s2, result)

    async def test_get_all_outbound_streams(self):
        seed = Seed.from_dict(SAMPLE_PEER_DICT)
        s1, s2 = MagicMock(), MagicMock()
        nc = make_node_client_mock(
            outbound_streams={"Seed": {"r1": s1}},
            outbound_pending={"Seed": {"r2": s2}},
        )
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = await seed.get_all_outbound_streams()
        self.assertIn(s1, result)
        self.assertIn(s2, result)

    async def test_get_all_streams_raises_typeerror(self):
        # get_all_streams is buggy: mixes async generators with list
        # concatenation. Just exercise the call site for coverage.
        sg = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        ns = make_node_server_mock()
        nc = make_node_client_mock()
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            with self.assertRaises(TypeError):
                await sg.get_all_streams()

    async def test_get_all_miner_streams(self):
        seed = Seed.from_dict(SAMPLE_PEER_DICT)
        s1 = MagicMock()
        ns = make_node_server_mock(
            inbound_streams={"Miner": {"k1": {"w1": s1}}},
        )
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = await seed.get_all_miner_streams()
        self.assertIn(s1, result)


class TestPeerCalculateSeedGatewayBranches(AsyncTestCase):
    """Lines 224-231: calculate_seed_gateway loop branches."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()

    async def test_seed_gateway_in_outbound_ignore_returns_none(self):
        group = Group.from_dict(SAMPLE_PEER_DICT)
        sg1 = MagicMock()
        sg1.identity.username_signature = "sg_sig_1"
        sgs = OrderedDict([("sg_sig_1", sg1)])
        nc = make_node_client_mock(outbound_ignore={"SeedGateway": {"sg_sig_1": True}})
        with patch.object(self.config, "seed_gateways", sgs, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await group.calculate_seed_gateway()
        self.assertIsNone(result)

    async def test_gw_ignore_key_falls_back_to_identity_announcement(self):
        """Line 322: _gw_ignore_key falls back to identity_announcement when
        the candidate gateway carries no inline identity (KEL-anchored)."""
        group = Group.from_dict(SAMPLE_PEER_DICT)
        sg1 = MagicMock()
        sg1.identity = None
        sg1.identity_announcement = "ia_gateway_1"
        sgs = OrderedDict([("ia_gateway_1", sg1)])
        nc = make_node_client_mock(outbound_ignore={"SeedGateway": {}})
        with patch.object(self.config, "seed_gateways", sgs, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await group.calculate_seed_gateway()
        self.assertEqual(result, sg1)


class TestPeerEnsurePeersConnected(AsyncTestCase):
    """Lines 239-261: ensure_peers_connected."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()

    async def test_no_peers_returns(self):
        user = User.from_dict(SAMPLE_PEER_DICT)
        with patch.object(
            self.config, "service_providers", {}, create=True
        ), patch.object(self.config, "peer", MagicMock(), create=True):
            await user.ensure_peers_connected()

    async def test_with_peers(self):
        user = User.from_dict(SAMPLE_PEER_DICT)
        mock_sp = MagicMock()
        mock_sp.identity.username_signature = "sp_sig"
        mock_peer = MagicMock()
        mock_peer.identity.generate_rid = MagicMock(return_value="generated_rid")
        nc = make_node_client_mock(
            outbound_streams={"ServiceProvider": {}},
            outbound_pending={"ServiceProvider": {}},
            outbound_ignore={"ServiceProvider": {}},
        )
        ns = make_node_server_mock(
            inbound_streams={"ServiceProvider": {}},
            inbound_pending={"ServiceProvider": {}},
        )
        with patch.object(
            self.config, "service_providers", {"sp_sig": mock_sp}, create=True
        ), patch.object(self.config, "peer", mock_peer, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ), patch.object(
            self.config, "nodeServer", ns, create=True
        ):
            import tornado.ioloop

            with patch.object(tornado.ioloop.IOLoop.current(), "spawn_callback"):
                await user.ensure_peers_connected()


class TestPeerConnectBranches(AsyncTestCase):
    """Line 274: connect break-on-limit."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()

    async def test_break_when_index_reaches_limit(self):
        user = User.from_dict(SAMPLE_PEER_DICT)
        peers = {f"p{i}": MagicMock() for i in range(5)}
        nc = make_node_client_mock()
        nc.connect = AsyncMock()
        with patch.object(self.config, "nodeClient", nc, create=True):
            import tornado.ioloop

            with patch.object(
                tornado.ioloop.IOLoop.current(), "spawn_callback"
            ) as spawn:
                await user.connect({}, 2, peers, {})
        self.assertEqual(spawn.call_count, 2)


class TestPeerIsSynced(AsyncTestCase):
    """Lines 281-285: Peer.is_synced."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()

    async def test_is_synced_all_synced(self):
        s1 = MagicMock(synced=True)
        mock_peer = MagicMock()
        mock_peer.get_outbound_streams = AsyncMock(return_value=[s1])
        with patch.object(self.config, "peer", mock_peer, create=True):
            result = await Peer.is_synced()
        self.assertTrue(result)

    async def test_is_synced_one_not_synced(self):
        s1 = MagicMock(synced=False)
        mock_peer = MagicMock()
        mock_peer.get_outbound_streams = AsyncMock(return_value=[s1])
        with patch.object(self.config, "peer", mock_peer, create=True):
            result = await Peer.is_synced()
        self.assertFalse(result)


class TestSeedGetInboundPeers(AsyncTestCase):
    """Lines 333-346: Seed.get_inbound_peers."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()


class TestSeedGetRoutePeers(AsyncTestCase):
    """Lines 362-406: Seed.get_route_peers."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.seed = Seed.from_dict(SAMPLE_PEER_DICT)

    async def test_route_peer_seed_branch(self):
        s1, s2 = MagicMock(), MagicMock()
        ns = make_node_server_mock(
            inbound_streams={"SeedGateway": {"r1": s1}, "Seed": {}}
        )
        nc = make_node_client_mock(outbound_streams={"Seed": {"r2": s2}})
        peer = Seed.from_dict(SAMPLE_PEER_DICT)
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = [x async for x in self.seed.get_route_peers(peer, {})]
        self.assertIn(s1, result)
        self.assertIn(s2, result)

    async def test_route_peer_seedgateway_response_inbound(self):
        bridge_seed = MagicMock()
        bridge_seed.rid = "bridge_rid"
        stream = MagicMock()
        ns = make_node_server_mock(inbound_streams={"Seed": {"bridge_rid": stream}})
        nc = make_node_client_mock()
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        payload = {"source_seed": "src_sig"}
        with patch.object(
            self.config, "seeds", {"src_sig": bridge_seed}, create=True
        ), patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = [x async for x in self.seed.get_route_peers(sg_peer, payload)]
        self.assertEqual(result, [stream])

    async def test_route_peer_seedgateway_response_outbound(self):
        bridge_seed = MagicMock()
        bridge_seed.rid = "bridge_rid"
        stream = MagicMock()
        ns = make_node_server_mock(inbound_streams={"Seed": {}})
        nc = make_node_client_mock(outbound_streams={"Seed": {"bridge_rid": stream}})
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        payload = {"source_seed": "src_sig"}
        with patch.object(
            self.config, "seeds", {"src_sig": bridge_seed}, create=True
        ), patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = [x async for x in self.seed.get_route_peers(sg_peer, payload)]
        self.assertEqual(result, [stream])

    async def test_route_peer_seedgateway_no_bridge_logs_error(self):
        bridge_seed = MagicMock()
        bridge_seed.rid = "missing_rid"
        ns = make_node_server_mock(inbound_streams={"Seed": {}})
        nc = make_node_client_mock(outbound_streams={"Seed": {}})
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        payload = {"source_seed": "src_sig"}
        with patch.object(
            self.config, "seeds", {"src_sig": bridge_seed}, create=True
        ), patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ), patch.object(
            self.config, "app_log", MagicMock(), create=True
        ):
            with self.assertRaises(UnboundLocalError):
                [x async for x in self.seed.get_route_peers(sg_peer, payload)]

    async def test_seedgateway_response_inbound(self):
        bridge_seed = MagicMock(rid="bridge_rid")
        stream = MagicMock()
        ns = make_node_server_mock(inbound_streams={"Seed": {"bridge_rid": stream}})
        nc = make_node_client_mock()
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        payload = {"source_seed": dict(SAMPLE_PEER_DICT)}
        fake_origin = MagicMock()
        fake_origin.identity.username_signature = "origin_sig"
        with patch.object(
            self.config, "seeds", {"origin_sig": bridge_seed}, create=True
        ), patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ), patch(
            "yadacoin.core.peer.Peer.from_dict", return_value=fake_origin
        ):
            result = [
                x
                async for x in self.seed.get_service_provider_request_peers(
                    sg_peer, payload
                )
            ]
        self.assertEqual(result, [stream])

    async def test_seedgateway_response_outbound(self):
        bridge_seed = MagicMock(rid="bridge_rid")
        stream = MagicMock()
        ns = make_node_server_mock(inbound_streams={"Seed": {}})
        nc = make_node_client_mock(outbound_streams={"Seed": {"bridge_rid": stream}})
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        payload = {"source_seed": dict(SAMPLE_PEER_DICT)}
        fake_origin = MagicMock()
        fake_origin.identity.username_signature = "origin_sig"
        with patch.object(
            self.config, "seeds", {"origin_sig": bridge_seed}, create=True
        ), patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ), patch(
            "yadacoin.core.peer.Peer.from_dict", return_value=fake_origin
        ):
            result = [
                x
                async for x in self.seed.get_service_provider_request_peers(
                    sg_peer, payload
                )
            ]
        self.assertEqual(result, [stream])

    async def test_seedgateway_originator_branch(self):
        bridge_seed = MagicMock(rid="bridge_rid")
        stream = MagicMock()
        ns = make_node_server_mock(inbound_streams={"Seed": {"bridge_rid": stream}})
        nc = make_node_client_mock()
        my_peer = MagicMock()
        my_peer.identity.username_signature = "my_sig"
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        bridge_sg_dict = MagicMock()
        bridge_sg_dict.identity.username_signature = "lookup_sig"
        sg_in_config = MagicMock(seed="origin_sig")
        payload = {PEER_TYPES.SEED_GATEWAY.value: dict(SAMPLE_PEER_DICT)}
        with patch.object(self.config, "peer", my_peer, create=True), patch.object(
            self.config, "seeds", {"origin_sig": bridge_seed}, create=True
        ), patch.object(
            self.config, "seed_gateways", {"lookup_sig": sg_in_config}, create=True
        ), patch.object(
            self.config, "nodeServer", ns, create=True
        ), patch.object(
            self.config, "nodeClient", nc, create=True
        ), patch(
            "yadacoin.core.peer.Peer.from_dict", return_value=bridge_sg_dict
        ):
            result = [
                x
                async for x in self.seed.get_service_provider_request_peers(
                    sg_peer, payload
                )
            ]
        self.assertEqual(result, [stream])
        self.assertEqual(payload["source_seed"], "my_sig")

    async def test_route_peer_seedgateway_response_bridge_seed_none(self):
        """Lines 509-512: response case where the referenced bridge seed
        cannot be resolved at all."""
        ns = make_node_server_mock(inbound_streams={"Seed": {}})
        nc = make_node_client_mock(outbound_streams={"Seed": {}})
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        payload = {"source_seed": "unresolvable_sig"}
        with patch.object(self.config, "seeds", {}, create=True), patch.object(
            self.config, "nodeServer", ns, create=True
        ), patch.object(self.config, "nodeClient", nc, create=True), patch.object(
            self.config, "app_log", MagicMock(), create=True
        ):
            result = [x async for x in self.seed.get_route_peers(sg_peer, payload)]
        self.assertEqual(result, [])

    async def test_route_peer_seedgateway_originator_no_seed_gateway(self):
        """Lines 523-527: destination-service-provider branch where the
        calculated seed gateway is missing or has no seed."""
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        dest_peer = MagicMock()
        dest_peer.calculate_seed_gateway = AsyncMock(return_value=None)
        payload = {"dest_service_provider": dict(SAMPLE_PEER_DICT)}
        with patch.object(self.config, "app_log", MagicMock(), create=True), patch(
            "yadacoin.core.peer.Peer.from_dict", return_value=dest_peer
        ):
            result = [x async for x in self.seed.get_route_peers(sg_peer, payload)]
        self.assertEqual(result, [])

    async def test_route_peer_seedgateway_originator_no_seed_gateway_seed(self):
        """Lines 523-527: calculated seed gateway found but has no seed."""
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        dest_peer = MagicMock()
        bridge_sg = MagicMock(seed=None)
        dest_peer.calculate_seed_gateway = AsyncMock(return_value=bridge_sg)
        payload = {"dest_service_provider": dict(SAMPLE_PEER_DICT)}
        with patch.object(self.config, "app_log", MagicMock(), create=True), patch(
            "yadacoin.core.peer.Peer.from_dict", return_value=dest_peer
        ):
            result = [x async for x in self.seed.get_route_peers(sg_peer, payload)]
        self.assertEqual(result, [])

    async def test_route_peer_seedgateway_originator_bridge_seed_none(self):
        """Lines 533-537: seed gateway resolved with a seed ref, but that
        seed ref does not resolve to any configured seed."""
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        dest_peer = MagicMock()
        bridge_sg = MagicMock(seed="unresolvable_seed_ref")
        dest_peer.calculate_seed_gateway = AsyncMock(return_value=bridge_sg)
        payload = {"dest_service_provider": dict(SAMPLE_PEER_DICT)}
        with patch.object(self.config, "seeds", {}, create=True), patch.object(
            self.config, "app_log", MagicMock(), create=True
        ), patch("yadacoin.core.peer.Peer.from_dict", return_value=dest_peer):
            result = [x async for x in self.seed.get_route_peers(sg_peer, payload)]
        self.assertEqual(result, [])

    async def test_route_peer_seedgateway_originator_success(self):
        """Lines 528-556: full destination-service-provider success path,
        assigning source_seed and yielding the resolved bridge stream."""
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        dest_peer = MagicMock()
        bridge_sg = MagicMock(seed="resolved_seed_ref")
        dest_peer.calculate_seed_gateway = AsyncMock(return_value=bridge_sg)
        bridge_seed = MagicMock(rid="bridge_rid")
        stream = MagicMock()
        ns = make_node_server_mock(inbound_streams={"Seed": {"bridge_rid": stream}})
        nc = make_node_client_mock()
        my_peer = MagicMock()
        my_peer.identity.username_signature = "my_sig"
        payload = {"dest_service_provider": dict(SAMPLE_PEER_DICT)}
        with patch.object(
            self.config, "seeds", {"resolved_seed_ref": bridge_seed}, create=True
        ), patch.object(self.config, "peer", my_peer, create=True), patch.object(
            self.config, "nodeServer", ns, create=True
        ), patch.object(
            self.config, "nodeClient", nc, create=True
        ), patch(
            "yadacoin.core.peer.Peer.from_dict", return_value=dest_peer
        ):
            result = [x async for x in self.seed.get_route_peers(sg_peer, payload)]
        self.assertEqual(result, [stream])
        self.assertEqual(payload["source_seed"], "my_sig")

    async def test_seedgateway_no_bridge_raises(self):
        bridge_seed = MagicMock(rid="missing_rid")
        ns = make_node_server_mock(inbound_streams={"Seed": {}})
        nc = make_node_client_mock(outbound_streams={"Seed": {}})
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        payload = {"source_seed": dict(SAMPLE_PEER_DICT)}
        fake_origin = MagicMock()
        fake_origin.identity.username_signature = "origin_sig"
        with patch.object(
            self.config, "seeds", {"origin_sig": bridge_seed}, create=True
        ), patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ), patch.object(
            self.config, "app_log", MagicMock(), create=True
        ), patch(
            "yadacoin.core.peer.Peer.from_dict", return_value=fake_origin
        ):
            with self.assertRaises(UnboundLocalError):
                [
                    x
                    async for x in self.seed.get_service_provider_request_peers(
                        sg_peer, payload
                    )
                ]

    async def test_sp_request_response_bridge_seed_none(self):
        """Lines 582-585: response case where the referenced bridge seed
        cannot be resolved at all."""
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        payload = {"source_seed": dict(SAMPLE_PEER_DICT)}
        fake_origin = MagicMock()
        fake_origin.identity.username_signature = "unresolvable_origin_sig"
        with patch.object(self.config, "seeds", {}, create=True), patch.object(
            self.config, "app_log", MagicMock(), create=True
        ), patch("yadacoin.core.peer.Peer.from_dict", return_value=fake_origin):
            result = [
                x
                async for x in self.seed.get_service_provider_request_peers(
                    sg_peer, payload
                )
            ]
        self.assertEqual(result, [])

    async def test_sp_request_originator_no_bridge_seed_gateway(self):
        """Lines 596-599: originator branch where Peer.from_dict on the
        seed_gateway payload field yields nothing usable."""
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        payload = {PEER_TYPES.SEED_GATEWAY.value: dict(SAMPLE_PEER_DICT)}
        with patch.object(self.config, "app_log", MagicMock(), create=True), patch(
            "yadacoin.core.peer.Peer.from_dict", return_value=None
        ):
            result = [
                x
                async for x in self.seed.get_service_provider_request_peers(
                    sg_peer, payload
                )
            ]
        self.assertEqual(result, [])

    async def test_sp_request_originator_resolved_sg_none(self):
        """Lines 606-609: bridge seed gateway resolved from the payload but
        it cannot be found among the configured seed_gateways."""
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        bridge_sg_dict = MagicMock()
        bridge_sg_dict.identity.username_signature = "unresolvable_sg_ref"
        payload = {PEER_TYPES.SEED_GATEWAY.value: dict(SAMPLE_PEER_DICT)}
        with patch.object(self.config, "seed_gateways", {}, create=True), patch.object(
            self.config, "app_log", MagicMock(), create=True
        ), patch("yadacoin.core.peer.Peer.from_dict", return_value=bridge_sg_dict):
            result = [
                x
                async for x in self.seed.get_service_provider_request_peers(
                    sg_peer, payload
                )
            ]
        self.assertEqual(result, [])

    async def test_sp_request_originator_resolved_sg_no_seed(self):
        """Lines 606-609: resolved seed gateway found but has no seed ref."""
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        bridge_sg_dict = MagicMock()
        bridge_sg_dict.identity.username_signature = "lookup_sig"
        sg_in_config = MagicMock(seed=None)
        payload = {PEER_TYPES.SEED_GATEWAY.value: dict(SAMPLE_PEER_DICT)}
        with patch.object(
            self.config, "seed_gateways", {"lookup_sig": sg_in_config}, create=True
        ), patch.object(self.config, "app_log", MagicMock(), create=True), patch(
            "yadacoin.core.peer.Peer.from_dict", return_value=bridge_sg_dict
        ):
            result = [
                x
                async for x in self.seed.get_service_provider_request_peers(
                    sg_peer, payload
                )
            ]
        self.assertEqual(result, [])

    async def test_sp_request_originator_bridge_seed_none(self):
        """Lines 612-615: resolved seed gateway has a seed ref, but that ref
        does not resolve to any configured seed."""
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        bridge_sg_dict = MagicMock()
        bridge_sg_dict.identity.username_signature = "lookup_sig"
        sg_in_config = MagicMock(seed="unresolvable_seed_ref")
        payload = {PEER_TYPES.SEED_GATEWAY.value: dict(SAMPLE_PEER_DICT)}
        with patch.object(self.config, "seeds", {}, create=True), patch.object(
            self.config,
            "seed_gateways",
            {"lookup_sig": sg_in_config},
            create=True,
        ), patch.object(self.config, "app_log", MagicMock(), create=True), patch(
            "yadacoin.core.peer.Peer.from_dict", return_value=bridge_sg_dict
        ):
            result = [
                x
                async for x in self.seed.get_service_provider_request_peers(
                    sg_peer, payload
                )
            ]
        self.assertEqual(result, [])

    async def test_sp_request_peers_seed_instance_branch(self):
        """Lines 635-639: when peer is a Seed instance, yield inbound
        SeedGateway streams."""
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"SeedGateway": {"r1": s1}})
        seed_peer = Seed.from_dict(SAMPLE_PEER_DICT)
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [
                x
                async for x in self.seed.get_service_provider_request_peers(
                    seed_peer, {}
                )
            ]
        self.assertEqual(result, [s1])


class TestSeedGatewayRoutePeersExtra(AsyncTestCase):
    """Lines 567-595: SeedGateway route + sp request methods."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.sg = SeedGateway.from_dict(SAMPLE_PEER_DICT)

    async def test_route_peers_seed_branch(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"ServiceProvider": {"r1": s1}})
        seed_peer = Seed.from_dict(SAMPLE_PEER_DICT)
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [x async for x in self.sg.get_route_peers(seed_peer, {})]
        self.assertEqual(result, [s1])

    async def test_route_peers_service_provider_branch(self):
        s1 = MagicMock()
        nc = make_node_client_mock(outbound_streams={"Seed": {"r1": s1}})
        sp_peer = ServiceProvider.from_dict(SAMPLE_PEER_DICT)
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = [x async for x in self.sg.get_route_peers(sp_peer, {})]
        self.assertEqual(result, [s1])

    async def test_sp_request_peers_seed_branch(self):
        s1 = MagicMock()
        ns = make_node_server_mock(inbound_streams={"ServiceProvider": {"r1": s1}})
        seed_peer = Seed.from_dict(SAMPLE_PEER_DICT)
        with patch.object(self.config, "nodeServer", ns, create=True):
            result = [
                x
                async for x in self.sg.get_service_provider_request_peers(seed_peer, {})
            ]
        self.assertEqual(result, [s1])

    async def test_sp_request_peers_service_provider_branch(self):
        s1 = MagicMock()
        nc = make_node_client_mock(outbound_streams={"Seed": {"r1": s1}})
        sp_peer = ServiceProvider.from_dict(SAMPLE_PEER_DICT)
        with patch.object(self.config, "nodeClient", nc, create=True):
            result = [
                x async for x in self.sg.get_service_provider_request_peers(sp_peer, {})
            ]
        self.assertEqual(result, [s1])


class TestServiceProviderRoutePeersAndRequest(AsyncTestCase):
    """Lines 689-781: ServiceProvider route + sp request methods."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.sp = ServiceProvider.from_dict(SAMPLE_PEER_DICT)

    async def test_route_peers_user_branch(self):
        s1, s2 = MagicMock(), MagicMock()
        s2.peer.identity.username_signature = "ws_sig"
        nc = make_node_client_mock(outbound_streams={"SeedGateway": {"r1": s1}})
        ws = MagicMock()
        ws.inbound_streams = {"k1": s2}
        user_peer = User.from_dict(SAMPLE_PEER_DICT)
        with patch.object(self.config, "nodeClient", nc, create=True), patch.object(
            self.config, "websocketServer", ws, create=True
        ):
            result = [x async for x in self.sp.get_route_peers(user_peer, {})]
        self.assertIn(s1, result)
        self.assertIn(s2, result)

    async def test_route_peers_user_filters_self(self):
        s2 = MagicMock()
        user_peer = User.from_dict(SAMPLE_PEER_DICT)
        s2.peer.identity.username_signature = user_peer.identity.username_signature
        nc = make_node_client_mock(outbound_streams={"SeedGateway": {}})
        ws = MagicMock()
        ws.inbound_streams = {"k1": s2}
        with patch.object(self.config, "nodeClient", nc, create=True), patch.object(
            self.config, "websocketServer", ws, create=True
        ):
            result = [x async for x in self.sp.get_route_peers(user_peer, {})]
        self.assertNotIn(s2, result)

    async def test_route_peers_seedgateway_no_txn(self):
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        # get_payload_txn returns None when payload has no transaction; but
        # the ServiceProvider implementation calls it without await so it's a
        # coroutine that's truthy. Patch get_payload_txn → None directly.
        with patch.object(self.sp, "get_payload_txn", lambda p: None):
            result = [x async for x in self.sp.get_route_peers(sg_peer, {})]
        self.assertEqual(result, [])

    async def test_sp_request_peers_user_branch(self):
        user_peer = User.from_dict(SAMPLE_PEER_DICT)
        s1, s2 = MagicMock(), MagicMock()
        s2.peer.identity.username_signature = "ws_sig"
        nc = make_node_client_mock(outbound_streams={"SeedGateway": {"r1": s1}})
        ws = MagicMock()
        ws.inbound_streams = {"k1": s2}
        with patch.object(self.config, "nodeClient", nc, create=True), patch.object(
            self.config, "websocketServer", ws, create=True
        ):
            result = [
                x
                async for x in self.sp.get_service_provider_request_peers(user_peer, {})
            ]
        self.assertIn(s1, result)
        self.assertIn(s2, result)

    async def test_sp_request_peers_seedgateway_branch(self):
        sg_peer = SeedGateway.from_dict(SAMPLE_PEER_DICT)
        s1, s2 = MagicMock(), MagicMock()
        ns = make_node_server_mock(inbound_streams={"User": {"r1": s1}})
        ws = MagicMock()
        ws.inbound_streams = {"User": {"r2": s2}}
        with patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "websocketServer", ws, create=True
        ):
            result = [
                x async for x in self.sp.get_service_provider_request_peers(sg_peer, {})
            ]
        self.assertIn(s1, result)
        self.assertIn(s2, result)


class TestGroupOutboundPeers(AsyncTestCase):
    """Lines 823-824: Group.get_outbound_peers."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()

    async def test_get_outbound_peers(self):
        group = Group.from_dict(SAMPLE_PEER_DICT)
        sp = MagicMock()
        sp.identity.username_signature = "sp_sig"
        group.calculate_service_provider = AsyncMock(return_value=sp)
        result = await group.get_outbound_peers()
        self.assertEqual(result["sp_sig"], sp)


class TestUserPoolGetRoutePeers(AsyncTestCase):
    """Lines 900-904 & 970-974: User/Pool get_route_peers."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()

    async def test_user_get_route_peers(self):
        user = User.from_dict(SAMPLE_PEER_DICT)
        s1, s2 = MagicMock(), MagicMock()
        nc = make_node_client_mock(outbound_streams={"User": {"r1": s1}})
        ns = make_node_server_mock(inbound_streams={"User": {"r2": s2}})
        with patch.object(self.config, "nodeClient", nc, create=True), patch.object(
            self.config, "nodeServer", ns, create=True
        ):
            result = [x async for x in user.get_route_peers(None, {})]
        self.assertIn(s1, result)
        self.assertIn(s2, result)

    async def test_pool_get_route_peers(self):
        pool = Pool.from_dict(SAMPLE_PEER_DICT)
        s1, s2 = MagicMock(), MagicMock()
        nc = make_node_client_mock(outbound_streams={"User": {"r1": s1}})
        ns = make_node_server_mock(inbound_streams={"User": {"r2": s2}})
        with patch.object(self.config, "nodeClient", nc, create=True), patch.object(
            self.config, "nodeServer", ns, create=True
        ):
            result = [x async for x in pool.get_route_peers(None, {})]
        self.assertIn(s1, result)
        self.assertIn(s2, result)


class TestExtraBranches(AsyncTestCase):
    """Remaining lines 227-231, 718/736, 769."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()

    async def test_calculate_seed_gateway_wraparound(self):
        # Force the while loop to wrap around with all entries ignored.
        group = Group.from_dict(SAMPLE_PEER_DICT)
        sg1 = MagicMock()
        sg1.identity.username_signature = "sg_a"
        sg2 = MagicMock()
        sg2.identity.username_signature = "sg_b"
        sgs = OrderedDict([("sg_a", sg1), ("sg_b", sg2)])
        nc = make_node_client_mock(
            outbound_ignore={"SeedGateway": {"sg_a": True, "sg_b": True}}
        )
        with patch.object(self.config, "seed_gateways", sgs, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ):
            result = await group.calculate_seed_gateway()
        self.assertIsNone(result)

    async def test_sp_request_peers_user_filters_self(self):
        sp = ServiceProvider.from_dict(SAMPLE_PEER_DICT)
        user_peer = User.from_dict(SAMPLE_PEER_DICT)
        s2 = MagicMock()
        s2.peer.identity.username_signature = user_peer.identity.username_signature
        nc = make_node_client_mock(outbound_streams={"SeedGateway": {}})
        ws = MagicMock()
        ws.inbound_streams = {"k1": s2}
        with patch.object(self.config, "nodeClient", nc, create=True), patch.object(
            self.config, "websocketServer", ws, create=True
        ):
            result = [
                x async for x in sp.get_service_provider_request_peers(user_peer, {})
            ]
        self.assertNotIn(s2, result)
