"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRCPWebSocketServerWriteAsJson(unittest.TestCase):
    """Tests for RCPWebSocketServer.write_as_json and related write helpers."""

    def _make_server(self, mock_config_cls):
        from yadacoin.websocket.base import RCPWebSocketServer

        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        server = RCPWebSocketServer.__new__(RCPWebSocketServer)
        server.config = mock_cfg
        server.peer = MagicMock()
        server.peer.identity = MagicMock()
        server.peer.identity.username = "test_user"
        server.write_message = AsyncMock()
        return server, mock_cfg

    @patch("yadacoin.websocket.base.Config")
    def test_write_as_json_calls_write_message(self, mock_config_cls):
        server, _ = self._make_server(mock_config_cls)
        asyncio.run(server.write_as_json("method", {"key": "val"}, "result"))
        server.write_message.assert_called_once()
        call_arg = server.write_message.call_args[0][0]
        data = json.loads(call_arg)
        self.assertEqual(data["method"], "method")
        self.assertEqual(data["result"], {"key": "val"})
        self.assertEqual(data["jsonrpc"], 2.0)

    @patch("yadacoin.websocket.base.Config")
    def test_write_as_json_uses_body_id(self, mock_config_cls):
        server, _ = self._make_server(mock_config_cls)
        body = {"id": 42}
        asyncio.run(server.write_as_json("method", {}, "result", body=body))
        call_arg = server.write_message.call_args[0][0]
        data = json.loads(call_arg)
        self.assertEqual(data["id"], 42)

    @patch("yadacoin.websocket.base.Config")
    def test_write_as_json_uses_default_id_when_no_body(self, mock_config_cls):
        server, _ = self._make_server(mock_config_cls)
        asyncio.run(server.write_as_json("method", {}, "params"))
        call_arg = server.write_message.call_args[0][0]
        data = json.loads(call_arg)
        self.assertEqual(data["id"], 1)

    @patch("yadacoin.websocket.base.Config")
    def test_write_result_calls_write_as_json_with_result_type(self, mock_config_cls):
        server, _ = self._make_server(mock_config_cls)
        server.write_as_json = AsyncMock()
        body = {"id": 10}
        asyncio.run(server.write_result("my_method", {"data": 1}, body=body))
        server.write_as_json.assert_called_once_with(
            "my_method", {"data": 1}, "result", body
        )

    @patch("yadacoin.websocket.base.Config")
    def test_write_params_calls_write_as_json_with_params_type(self, mock_config_cls):
        server, _ = self._make_server(mock_config_cls)
        server.write_as_json = AsyncMock()
        asyncio.run(server.write_params("my_method", {"param": "val"}))
        server.write_as_json.assert_called_once_with(
            "my_method", {"param": "val"}, "params", None
        )

    @patch("yadacoin.websocket.base.Config")
    def test_write_as_json_handles_websocket_closed_error(self, mock_config_cls):
        from tornado.websocket import WebSocketClosedError

        server, mock_cfg = self._make_server(mock_config_cls)
        server.write_message = AsyncMock(side_effect=WebSocketClosedError())
        server.remove_peer = MagicMock()
        asyncio.run(server.write_as_json("method", {}, "result"))
        server.remove_peer.assert_called_once_with(server.peer)

    @patch("yadacoin.websocket.base.Config")
    def test_write_as_json_handles_generic_exception(self, mock_config_cls):
        server, mock_cfg = self._make_server(mock_config_cls)
        server.write_message = AsyncMock(side_effect=Exception("something went wrong"))
        server.remove_peer = MagicMock()
        asyncio.run(server.write_as_json("method", {}, "result"))
        server.remove_peer.assert_called_once_with(server.peer)


class TestRCPWebSocketServerRemovePeer(unittest.TestCase):
    def _make_server(self, mock_config_cls):
        from yadacoin.websocket.base import RCPWebSocketServer

        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        server = RCPWebSocketServer.__new__(RCPWebSocketServer)
        server.config = mock_cfg
        server.inbound_streams = {
            "User": {},
            "Group": {},
        }
        return server, mock_cfg

    @patch("yadacoin.websocket.base.Config")
    def test_remove_peer_none_logs_warning(self, mock_config_cls):
        server, mock_cfg = self._make_server(mock_config_cls)
        server.remove_peer(None)
        mock_cfg.app_log.warning.assert_called()

    @patch("yadacoin.websocket.base.Config")
    def test_remove_peer_removes_from_inbound_streams(self, mock_config_cls):
        import asyncio

        server, mock_cfg = self._make_server(mock_config_cls)
        peer = MagicMock()
        peer.__class__.__name__ = "User"
        peer.id_attribute = "rid"
        peer.rid = "test_rid"
        peer.groups = {}
        server.inbound_streams["User"]["test_rid"] = MagicMock()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            server.remove_peer(peer)
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        self.assertNotIn("test_rid", server.inbound_streams["User"])


class TestRCPWebSocketServerOnlineMethod(unittest.TestCase):
    def _make_server(self, mock_config_cls):
        from yadacoin.websocket.base import RCPWebSocketServer

        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        server = RCPWebSocketServer.__new__(RCPWebSocketServer)
        server.config = mock_cfg
        server.peer = MagicMock()
        server.write_result = AsyncMock()
        server.config.websocketServer = MagicMock()
        server.config.websocketServer.inbound_streams = {
            "User": {"rid_a": MagicMock(), "rid_b": MagicMock()},
        }
        return server, mock_cfg

    @patch("yadacoin.websocket.base.Config")
    def test_online_returns_matching_rids(self, mock_config_cls):
        server, mock_cfg = self._make_server(mock_config_cls)
        body = {"params": {"rids": ["rid_a", "rid_c"]}}
        asyncio.run(server.online(body))
        call_kwargs = server.write_result.call_args
        online_rids = call_kwargs[0][1]["online_rids"]
        self.assertIn("rid_a", online_rids)
        self.assertNotIn("rid_c", online_rids)

    @patch("yadacoin.websocket.base.Config")
    def test_online_returns_empty_when_no_match(self, mock_config_cls):
        server, mock_cfg = self._make_server(mock_config_cls)
        body = {"params": {"rids": ["rid_x", "rid_y"]}}
        asyncio.run(server.online(body))
        call_kwargs = server.write_result.call_args
        online_rids = call_kwargs[0][1]["online_rids"]
        self.assertEqual(online_rids, [])


class TestRCPWebSocketServerAppendToGroup(unittest.TestCase):
    def _make_server(self, mock_config_cls):
        from yadacoin.websocket.base import RCPWebSocketServer

        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg
        server = RCPWebSocketServer.__new__(RCPWebSocketServer)
        server.config = mock_cfg
        server.peer = MagicMock()
        server.peer.identity = MagicMock()
        server.peer.groups = {}
        server.inbound_streams = {"User": {}, "Group": {}}
        RCPWebSocketServer.inbound_streams = {"User": {}, "Group": {}}
        return server, mock_cfg

    @patch("yadacoin.websocket.base.Config")
    def test_append_to_group_adds_entry(self, mock_config_cls):
        from yadacoin.core.collections import Collections

        server, mock_cfg = self._make_server(mock_config_cls)
        group = MagicMock()
        group.generate_rid = MagicMock(return_value="group_rid_123")
        group.username_signature = "sig123"
        server.peer.identity.generate_rid = MagicMock(return_value="peer_rid_456")
        server.peer.identity.to_dict = {"public_key": "pk"}
        result = server.append_to_group(group, Collections.GROUP_CHAT.value)
        self.assertIn("group_rid_123", result)

    @patch("yadacoin.websocket.base.Config")
    def test_append_to_group_adds_peer_to_groups(self, mock_config_cls):
        from yadacoin.core.collections import Collections

        server, mock_cfg = self._make_server(mock_config_cls)
        group = MagicMock()
        group.generate_rid = MagicMock(return_value="group_rid_abc")
        group.username_signature = "sig_abc"
        server.peer.identity.generate_rid = MagicMock(return_value="peer_rid_abc")
        server.peer.identity.to_dict = {"public_key": "pk2"}
        server.append_to_group(group, Collections.GROUP_CHAT.value)
        self.assertIn("group_rid_abc", server.peer.groups)


class TestWebSocketHandlers(unittest.TestCase):
    def test_websocket_handlers_list(self):
        from yadacoin.websocket.base import WEBSOCKET_HANDLERS

        self.assertIsInstance(WEBSOCKET_HANDLERS, list)
        self.assertGreater(len(WEBSOCKET_HANDLERS), 0)

    def test_websocket_handler_route(self):
        from yadacoin.websocket.base import WEBSOCKET_HANDLERS

        routes = [h[0] for h in WEBSOCKET_HANDLERS]
        self.assertIn("/websocket", routes)

    def test_websocket_handler_class(self):
        from yadacoin.websocket.base import WEBSOCKET_HANDLERS, RCPWebSocketServer

        handler_map = {h[0]: h[1] for h in WEBSOCKET_HANDLERS}
        self.assertIs(handler_map["/websocket"], RCPWebSocketServer)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
