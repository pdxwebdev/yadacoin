"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.tcpsocket.base import (
    REQUEST_ONLY,
    REQUEST_RESPONSE_MAP,
    BaseRPC,
    DummyStream,
    RPCSocketClient,
    RPCSocketServer,
)


class TestRequestResponseMap(unittest.TestCase):
    def test_is_dict(self):
        self.assertIsInstance(REQUEST_RESPONSE_MAP, dict)

    def test_blockresponse_maps_to_getblock(self):
        self.assertEqual(REQUEST_RESPONSE_MAP["blockresponse"], "getblock")

    def test_blocksresponse_maps_to_getblocks(self):
        self.assertEqual(REQUEST_RESPONSE_MAP["blocksresponse"], "getblocks")

    def test_keepalive_maps_to_keepalive(self):
        self.assertEqual(REQUEST_RESPONSE_MAP["keepalive"], "keepalive")

    def test_all_keys_are_strings(self):
        for k, v in REQUEST_RESPONSE_MAP.items():
            self.assertIsInstance(k, str)
            self.assertIsInstance(v, str)


class TestRequestOnly(unittest.TestCase):
    def test_is_list(self):
        self.assertIsInstance(REQUEST_ONLY, list)

    def test_contains_connect(self):
        self.assertIn("connect", REQUEST_ONLY)

    def test_contains_challenge(self):
        self.assertIn("challenge", REQUEST_ONLY)

    def test_contains_authenticate(self):
        self.assertIn("authenticate", REQUEST_ONLY)

    def test_contains_newblock(self):
        self.assertIn("newblock", REQUEST_ONLY)

    def test_contains_disconnect(self):
        self.assertIn("disconnect", REQUEST_ONLY)

    def test_all_elements_are_strings(self):
        for item in REQUEST_ONLY:
            self.assertIsInstance(item, str)


class TestDummyStream(unittest.TestCase):
    def test_init_stores_peer(self):
        peer = MagicMock()
        ds = DummyStream(peer)
        self.assertIs(ds.peer, peer)

    def test_close_does_not_raise(self):
        peer = MagicMock()
        ds = DummyStream(peer)
        ds.close()  # should return None without raising

    def test_close_returns_none(self):
        peer = MagicMock()
        ds = DummyStream(peer)
        result = ds.close()
        self.assertIsNone(result)

    def test_class_attr_peer_is_none(self):
        self.assertIsNone(DummyStream.peer)

    def test_instance_peer_overrides_class_attr(self):
        peer = MagicMock()
        ds = DummyStream(peer)
        self.assertIsNotNone(ds.peer)


class TestBaseRPC(unittest.TestCase):
    @patch("yadacoin.tcpsocket.base.Config")
    def test_init_sets_config(self, mock_config_cls):
        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        rpc = BaseRPC()
        self.assertIs(rpc.config, mock_cfg)

    @patch("yadacoin.tcpsocket.base.Config")
    def test_write_result_calls_write_as_json(self, mock_config_cls):
        mock_config_cls.return_value = MagicMock()
        rpc = BaseRPC()
        rpc.write_as_json = AsyncMock()
        import asyncio

        asyncio.run(rpc.write_result("stream", "method", "data", "req_id"))
        rpc.write_as_json.assert_called_once_with(
            "stream", "method", "data", "result", "req_id"
        )

    @patch("yadacoin.tcpsocket.base.Config")
    def test_write_params_calls_write_as_json(self, mock_config_cls):
        mock_config_cls.return_value = MagicMock()
        rpc = BaseRPC()
        rpc.write_as_json = AsyncMock()
        import asyncio

        asyncio.run(rpc.write_params("stream", "method", "data"))
        rpc.write_as_json.assert_called_once_with("stream", "method", "data", "params")

    @patch("yadacoin.tcpsocket.base.Config")
    def test_write_as_json_with_dummy_stream_returns_early(self, mock_config_cls):
        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        rpc = BaseRPC()
        peer = MagicMock()
        ds = DummyStream(peer)
        import asyncio

        asyncio.run(rpc.write_as_json(ds, "method", {}, "params"))
        mock_cfg.app_log.warning.assert_called()

    @patch("yadacoin.tcpsocket.base.Config")
    def test_write_as_json_stream_without_peer_closes(self, mock_config_cls):
        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        rpc = BaseRPC()
        stream = MagicMock()  # no 'peer' attribute
        del stream.peer  # ensure peer is absent
        import asyncio

        asyncio.run(rpc.write_as_json(stream, "method", {}, "params"))
        mock_cfg.app_log.warning.assert_called()
        stream.close.assert_called()


class TestRPCSocketServerKeepalive(unittest.TestCase):
    """Tests for the keepalive handler on RPCSocketServer."""

    def _make_server(self, mock_config_cls):
        mock_cfg = MagicMock()
        mock_cfg.health.tcp_server.last_activity = 0.0
        mock_config_cls.return_value = mock_cfg
        server = RPCSocketServer.__new__(RPCSocketServer)
        server.config = mock_cfg
        server.write_result = AsyncMock()
        server.remove_peer = AsyncMock()
        return server, mock_cfg

    @patch("yadacoin.tcpsocket.base.Config")
    def test_keepalive_calls_write_result(self, mock_config_cls):
        server, mock_cfg = self._make_server(mock_config_cls)
        mock_stream = MagicMock()
        mock_stream.peer = MagicMock()
        mock_stream.peer.host = "127.0.0.1"
        body = {"id": "test-id"}
        import asyncio

        asyncio.run(server.keepalive(body, mock_stream))
        server.write_result.assert_called_once_with(
            mock_stream, "keepalive", {"ok": True}, "test-id"
        )

    @patch("yadacoin.tcpsocket.base.Config")
    def test_keepalive_updates_last_activity(self, mock_config_cls):
        import time

        server, mock_cfg = self._make_server(mock_config_cls)
        mock_stream = MagicMock()
        mock_stream.peer = MagicMock()
        mock_stream.peer.host = "127.0.0.1"
        body = {"id": "test-id"}
        import asyncio

        before = int(time.time())
        asyncio.run(server.keepalive(body, mock_stream))
        self.assertGreaterEqual(mock_stream.last_activity, before)


class TestRPCSocketClientSendKeepalive(unittest.TestCase):
    """Tests for send_keepalive on RPCSocketClient."""

    @patch("yadacoin.tcpsocket.base.Config")
    def test_send_keepalive_stops_when_stream_closed(self, mock_config_cls):
        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        client = RPCSocketClient.__new__(RPCSocketClient)
        client.config = mock_cfg
        client.write_params = AsyncMock()

        mock_stream = MagicMock()
        mock_stream.closed.return_value = True
        mock_stream.peer = MagicMock()
        mock_stream.peer.host = "127.0.0.1"

        import asyncio

        # Patch sleep to return immediately so the loop runs once
        async def fast_sleep(_):
            return

        with patch("yadacoin.tcpsocket.base.asyncio.sleep", fast_sleep):
            asyncio.run(client.send_keepalive(mock_stream))

        client.write_params.assert_not_called()


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
