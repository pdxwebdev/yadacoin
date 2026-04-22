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
from pathlib import Path
from unittest.mock import MagicMock


class TestPeerjsHandlers(unittest.TestCase):
    def test_peerjs_handlers_is_list(self):
        from yadacoin.websocket.peerjs import PEERJS_HANDLERS

        self.assertIsInstance(PEERJS_HANDLERS, list)

    def test_peerjs_handlers_has_entries(self):
        from yadacoin.websocket.peerjs import PEERJS_HANDLERS

        self.assertGreater(len(PEERJS_HANDLERS), 0)

    def test_peerjsclient_route_exists(self):
        from yadacoin.websocket.peerjs import PEERJS_HANDLERS

        routes = [h[0] for h in PEERJS_HANDLERS]
        self.assertIn(r"/peerjsclient", routes)

    def test_peerjs_websocket_route_exists(self):
        from yadacoin.websocket.peerjs import PEERJS_HANDLERS

        routes = [h[0] for h in PEERJS_HANDLERS]
        self.assertIn(r"/peerjs", routes)

    def test_peerjs_handler_class(self):
        from yadacoin.websocket.peerjs import PEERJS_HANDLERS, PeerWebSocketHandler

        handler_map = {h[0]: h[1] for h in PEERJS_HANDLERS}
        self.assertIs(handler_map[r"/peerjs"], PeerWebSocketHandler)

    def test_main_handler_class(self):
        from yadacoin.websocket.peerjs import PEERJS_HANDLERS, MainHandler

        handler_map = {h[0]: h[1] for h in PEERJS_HANDLERS}
        self.assertIs(handler_map[r"/peerjsclient"], MainHandler)

    def test_static_file_handler_route(self):
        from yadacoin.websocket.peerjs import PEERJS_HANDLERS

        # The static handler route pattern for peerjsclient
        routes = [h[0] for h in PEERJS_HANDLERS]
        self.assertIn(r"/peerjsclient/(.*)", routes)

    def test_static_handler_path_is_valid(self):
        import tornado.web

        from yadacoin.websocket.peerjs import PEERJS_HANDLERS

        static_entry = None
        for entry in PEERJS_HANDLERS:
            if (
                entry[0] == r"/peerjsclient/(.*)"
                and entry[1] is tornado.web.StaticFileHandler
            ):
                static_entry = entry
                break
        self.assertIsNotNone(static_entry)
        # path kwarg should be a Path pointing to static/peerjsclient
        path = static_entry[2]["path"]
        self.assertIsInstance(path, Path)
        self.assertTrue(str(path).endswith("peerjsclient"))


class TestConnectionsAndGroups(unittest.TestCase):
    def test_connections_dict_exists(self):
        from yadacoin.websocket.peerjs import connections

        self.assertIsInstance(connections, dict)

    def test_groups_dict_exists(self):
        from yadacoin.websocket.peerjs import groups

        self.assertIsInstance(groups, dict)


class TestPeerWebSocketHandlerOnMessage(unittest.TestCase):
    """Tests for PeerWebSocketHandler.on_message logic."""

    def _make_handler(self):
        from yadacoin.websocket.peerjs import PeerWebSocketHandler

        handler = PeerWebSocketHandler.__new__(PeerWebSocketHandler)
        handler.peer_id = "test_peer_id"
        handler.write_message = MagicMock()
        return handler

    def test_on_message_invalid_json_sends_error(self):
        handler = self._make_handler()
        handler.on_message("not_valid_json")
        handler.write_message.assert_called_once()
        call_arg = json.loads(handler.write_message.call_args[0][0])
        self.assertEqual(call_arg["type"], "ERROR")

    def test_on_message_join_group_adds_to_groups(self):
        from yadacoin.websocket import peerjs as peerjs_module

        handler = self._make_handler()
        # Clear groups state
        peerjs_module.groups.clear()
        msg = json.dumps({"type": "JOIN_GROUP", "group": "test_group"})
        handler.on_message(msg)
        self.assertIn("test_group", peerjs_module.groups)
        self.assertIn(handler, peerjs_module.groups["test_group"])

    def test_on_message_offer_forwards_to_peer(self):
        from yadacoin.websocket import peerjs as peerjs_module

        sender = self._make_handler()
        sender.peer_id = "sender_peer"

        receiver = MagicMock()
        receiver.write_message = MagicMock()

        peerjs_module.connections["receiver_peer"] = receiver

        msg = json.dumps({"type": "OFFER", "dst": "receiver_peer", "data": "sdp"})
        sender.on_message(msg)
        receiver.write_message.assert_called_once()
        forwarded = json.loads(receiver.write_message.call_args[0][0])
        self.assertEqual(forwarded["src"], "sender_peer")

        # Cleanup
        del peerjs_module.connections["receiver_peer"]

    def test_on_message_answer_forwards_to_peer(self):
        from yadacoin.websocket import peerjs as peerjs_module

        sender = self._make_handler()
        sender.peer_id = "answer_sender"

        receiver = MagicMock()
        peerjs_module.connections["answer_receiver"] = receiver

        msg = json.dumps({"type": "ANSWER", "dst": "answer_receiver"})
        sender.on_message(msg)
        receiver.write_message.assert_called_once()

        del peerjs_module.connections["answer_receiver"]

    def test_on_message_candidate_forwards_to_peer(self):
        from yadacoin.websocket import peerjs as peerjs_module

        sender = self._make_handler()
        sender.peer_id = "cand_sender"

        receiver = MagicMock()
        peerjs_module.connections["cand_receiver"] = receiver

        msg = json.dumps({"type": "CANDIDATE", "dst": "cand_receiver"})
        sender.on_message(msg)
        receiver.write_message.assert_called_once()

        del peerjs_module.connections["cand_receiver"]

    def test_on_message_offer_unknown_peer_no_error(self):
        """Forwarding to an unknown peer should not raise."""
        handler = self._make_handler()
        msg = json.dumps({"type": "OFFER", "dst": "nonexistent_peer"})
        # Should swallow gracefully (no target in connections)
        handler.on_message(msg)
        # No exception means pass


class TestPeerWebSocketHandlerCheckOrigin(unittest.TestCase):
    def test_check_origin_returns_true(self):
        from yadacoin.websocket.peerjs import PeerWebSocketHandler

        handler = PeerWebSocketHandler.__new__(PeerWebSocketHandler)
        self.assertTrue(handler.check_origin("http://any.origin.com"))
        self.assertTrue(handler.check_origin("https://other.origin.net"))


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
