"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import time
import unittest
from logging import getLogger
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.config import Config
from yadacoin.core.health import (
    BlockCheckerHealth,
    BlockInserterHealth,
    CacheValidatorHealth,
    ConsenusHealth,
    Health,
    HealthItem,
    MempoolCleanerHealth,
    MessageSenderHealth,
    NodeTesterHealth,
    NonceProcessorHealth,
    PeerHealth,
    PoolPayerHealth,
    TCPClientHealth,
    TCPServerHealth,
    TransactionProcessorHealth,
)

from ..test_setup import AsyncTestCase


class HealthTestCase(AsyncTestCase):
    """Base class for health tests: ensures app_log is set on Config singleton."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        config = Config()
        if not hasattr(config, "app_log"):
            config.app_log = getLogger("tornado.application")


class TestHealthItem(HealthTestCase):
    async def test_init(self):
        item = HealthItem()
        self.assertIsNotNone(item)

    async def test_report_status_true(self):
        item = HealthItem()
        result = item.report_status(True)
        self.assertTrue(result)
        self.assertTrue(item.status)

    async def test_report_status_false(self):
        item = HealthItem()
        result = item.report_status(False)
        self.assertFalse(result)
        self.assertFalse(item.status)

    async def test_report_status_ignore(self):
        item = HealthItem()
        item.report_status(True, ignore=True)
        self.assertTrue(item.ignore)

    async def test_to_dict(self):
        item = HealthItem()
        d = item.to_dict()
        self.assertIn("status         ", d)
        self.assertIn("last_activity  ", d)

    async def test_reset(self):
        item = HealthItem()
        # reset is a no-op
        await item.reset()


class TestConsenusHealth(HealthTestCase):
    async def test_check_health_within_timeout(self):
        h = ConsenusHealth()
        h.last_activity = time.time()
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_past_timeout(self):
        h = ConsenusHealth()
        h.last_activity = time.time() - 9999
        result = await h.check_health()
        self.assertFalse(result)

    async def test_reset_clears_block_queue(self):
        h = ConsenusHealth()
        mock_queues = MagicMock()
        mock_queues.block_queue.queue = {"item": "value"}
        h.config.processing_queues = mock_queues
        await h.reset()
        self.assertEqual(mock_queues.block_queue.queue, {})


class TestBlockCheckerHealth(HealthTestCase):
    async def test_check_health_within_timeout(self):
        h = BlockCheckerHealth()
        h.last_activity = time.time()
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_past_timeout(self):
        h = BlockCheckerHealth()
        h.last_activity = time.time() - 9999
        result = await h.check_health()
        self.assertFalse(result)


class TestBlockInserterHealth(HealthTestCase):
    async def test_check_health_within_timeout(self):
        h = BlockInserterHealth()
        h.last_activity = time.time()
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_past_timeout(self):
        h = BlockInserterHealth()
        h.last_activity = time.time() - 9999
        result = await h.check_health()
        self.assertFalse(result)


class TestTransactionProcessorHealth(HealthTestCase):
    async def test_check_health_within_timeout(self):
        h = TransactionProcessorHealth()
        h.last_activity = time.time()
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_past_timeout(self):
        h = TransactionProcessorHealth()
        h.last_activity = time.time() - 9999
        result = await h.check_health()
        self.assertFalse(result)


class TestNonceProcessorHealth(HealthTestCase):
    async def test_check_health_within_timeout(self):
        h = NonceProcessorHealth()
        h.last_activity = time.time()
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_past_timeout(self):
        h = NonceProcessorHealth()
        h.last_activity = time.time() - 9999
        result = await h.check_health()
        self.assertFalse(result)


class TestPoolPayerHealth(HealthTestCase):
    async def test_check_health_no_pp(self):
        h = PoolPayerHealth()
        h.config.pp = None
        result = await h.check_health()
        self.assertTrue(result)
        self.assertTrue(h.ignore)

    async def test_check_health_with_pp_within_timeout(self):
        h = PoolPayerHealth()
        h.config.pp = MagicMock()
        h.last_activity = time.time()
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_with_pp_past_timeout(self):
        h = PoolPayerHealth()
        h.config.pp = MagicMock()
        h.last_activity = time.time() - 9999
        result = await h.check_health()
        self.assertFalse(result)


class TestCacheValidatorHealth(HealthTestCase):
    async def test_check_health_within_timeout(self):
        h = CacheValidatorHealth()
        h.last_activity = time.time()
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_past_timeout(self):
        h = CacheValidatorHealth()
        h.last_activity = time.time() - 9999999
        result = await h.check_health()
        self.assertFalse(result)


class TestMempoolCleanerHealth(HealthTestCase):
    async def test_check_health_within_timeout(self):
        h = MempoolCleanerHealth()
        h.last_activity = time.time()
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_past_timeout(self):
        h = MempoolCleanerHealth()
        h.last_activity = time.time() - 9999999
        result = await h.check_health()
        self.assertFalse(result)


class TestNodeTesterHealth(HealthTestCase):
    async def test_check_health_within_timeout(self):
        h = NodeTesterHealth()
        h.last_activity = time.time()
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_past_timeout(self):
        h = NodeTesterHealth()
        h.last_activity = time.time() - 9999999
        result = await h.check_health()
        self.assertFalse(result)


class TestHealth(HealthTestCase):
    async def test_init(self):
        h = Health()
        self.assertIsNotNone(h)

    async def test_to_dict_has_status(self):
        h = Health()
        d = h.to_dict()
        self.assertIn("status", d)

    async def test_to_dict_has_health_items(self):
        h = Health()
        d = h.to_dict()
        self.assertIn("ConsenusHealth", d)
        self.assertIn("BlockCheckerHealth", d)

    async def test_check_health_all_good(self):
        h = Health()
        for item in h.health_items:
            item.last_activity = time.time()
        # TCPServerHealth and TCPClientHealth access config.peer as object with stream methods
        # Patch these to ignore streams (returns empty list → reports True/ignore)
        with patch.object(
            h.tcp_server, "check_health", new=AsyncMock(return_value=True)
        ), patch.object(h.tcp_client, "check_health", new=AsyncMock(return_value=True)):
            result = await h.check_health()
            self.assertTrue(result)


class TestTCPServerHealth(HealthTestCase):
    async def test_check_health_no_streams(self):
        h = TCPServerHealth()
        mock_peer = MagicMock()
        mock_peer.get_all_inbound_streams = AsyncMock(return_value=[])
        mock_peer.get_all_miner_streams = AsyncMock(return_value=[])
        h.config.peer = mock_peer
        result = await h.check_health()
        self.assertTrue(result)
        self.assertTrue(h.ignore)

    async def test_check_health_with_streams_within_timeout(self):
        h = TCPServerHealth()
        h.last_activity = time.time()
        mock_stream = MagicMock()
        mock_stream.last_activity = time.time()
        mock_peer = MagicMock()
        mock_peer.get_all_inbound_streams = AsyncMock(return_value=[mock_stream])
        mock_peer.get_all_miner_streams = AsyncMock(return_value=[])
        h.config.peer = mock_peer
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_with_streams_past_timeout(self):
        h = TCPServerHealth()
        h.last_activity = time.time() - 9999
        mock_stream = MagicMock()
        mock_stream.last_activity = time.time()
        mock_peer = MagicMock()
        mock_peer.get_all_inbound_streams = AsyncMock(return_value=[mock_stream])
        mock_peer.get_all_miner_streams = AsyncMock(return_value=[])
        h.config.peer = mock_peer
        result = await h.check_health()
        self.assertFalse(result)

    async def test_check_health_stale_stream_calls_remove_peer(self):
        h = TCPServerHealth()
        h.last_activity = time.time()
        mock_stream = MagicMock()
        mock_stream.last_activity = time.time() - 9999  # stale
        mock_peer = MagicMock()
        mock_peer.get_all_inbound_streams = AsyncMock(return_value=[mock_stream])
        mock_peer.get_all_miner_streams = AsyncMock(return_value=[])
        mock_server = MagicMock()
        mock_server.remove_peer = AsyncMock()
        h.config.peer = mock_peer
        h.config.node_server_instance = mock_server
        result = await h.check_health()
        mock_server.remove_peer.assert_called_once()
        self.assertTrue(result)

    async def test_reset(self):
        h = TCPServerHealth()
        mock_server = MagicMock()
        mock_server.stop = MagicMock()
        mock_server.bind = MagicMock()
        mock_server.start = MagicMock()
        mock_new_server = MagicMock()
        mock_new_server.bind = MagicMock()
        mock_new_server.start = MagicMock()
        h.config.node_server_instance = mock_server
        h.config.nodeServer = MagicMock(return_value=mock_new_server)
        h.config.peer_port = 8000
        result = await h.reset()
        mock_server.stop.assert_called_once()
        mock_new_server.bind.assert_called_once_with(8000)
        mock_new_server.start.assert_called_once_with(1)
        self.assertTrue(result)


class TestTCPClientHealth(HealthTestCase):
    async def test_check_health_no_streams(self):
        h = TCPClientHealth()
        mock_peer = MagicMock()
        mock_peer.get_all_outbound_streams = AsyncMock(return_value=[])
        h.config.peer = mock_peer
        result = await h.check_health()
        self.assertTrue(result)
        self.assertTrue(h.ignore)

    async def test_check_health_with_streams_within_timeout(self):
        h = TCPClientHealth()
        h.last_activity = time.time()
        mock_stream = MagicMock()
        mock_peer = MagicMock()
        mock_peer.get_all_outbound_streams = AsyncMock(return_value=[mock_stream])
        h.config.peer = mock_peer
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_with_streams_past_timeout(self):
        h = TCPClientHealth()
        h.last_activity = time.time() - 9999
        mock_stream = MagicMock()
        mock_stream.last_activity = time.time() - 9999
        mock_peer = MagicMock()
        mock_peer.get_all_outbound_streams = AsyncMock(return_value=[mock_stream])
        mock_client = MagicMock()
        mock_client.remove_peer = AsyncMock()
        h.config.peer = mock_peer
        h.config.nodeClient = mock_client
        result = await h.check_health()
        self.assertFalse(result)

    async def test_reset(self):
        h = TCPClientHealth()
        mock_stream = MagicMock()
        mock_peer = MagicMock()
        mock_peer.get_all_outbound_streams = AsyncMock(return_value=[mock_stream])
        mock_client = MagicMock()
        mock_client.remove_peer = AsyncMock()
        h.config.peer = mock_peer
        h.config.nodeClient = mock_client
        await h.reset()
        mock_client.remove_peer.assert_called_once_with(
            mock_stream, reason="TCPClientHealth: reset"
        )


class TestPeerHealth(HealthTestCase):
    async def test_check_health_within_timeout(self):
        h = PeerHealth()
        h.last_activity = time.time()
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_past_timeout(self):
        h = PeerHealth()
        h.last_activity = time.time() - 9999
        mock_app = MagicMock()
        mock_app.background_peers = MagicMock()
        h.config.application = mock_app
        mock_ioloop = MagicMock()
        with patch("tornado.ioloop.IOLoop.current", return_value=mock_ioloop):
            result = await h.check_health()
        self.assertFalse(result)
        mock_ioloop.spawn_callback.assert_called_once_with(mock_app.background_peers)


class TestMessageSenderHealth(HealthTestCase):
    async def test_check_health_within_timeout(self):
        h = MessageSenderHealth()
        h.last_activity = time.time()
        result = await h.check_health()
        self.assertTrue(result)

    async def test_check_health_past_timeout(self):
        h = MessageSenderHealth()
        h.last_activity = time.time() - 9999
        mock_app = MagicMock()
        mock_app.background_message_sender = MagicMock()
        h.config.application = mock_app
        mock_ioloop = MagicMock()
        with patch("tornado.ioloop.IOLoop.current", return_value=mock_ioloop):
            result = await h.check_health()
        self.assertFalse(result)
        mock_ioloop.spawn_callback.assert_called_once_with(
            mock_app.background_message_sender
        )


class TestHealthCheckFailurePath(HealthTestCase):
    async def test_check_health_item_fails_triggers_reset(self):
        h = Health()
        # Replace all health items with a single mock that returns False with ignore=False
        mock_item = MagicMock()
        mock_item.check_health = AsyncMock(return_value=False)
        mock_item.ignore = False
        mock_item.reset = AsyncMock()
        h.health_items = [mock_item]
        result = await h.check_health()
        self.assertFalse(result)
        mock_item.reset.assert_called_once()

    async def test_check_health_item_fails_but_ignored(self):
        h = Health()
        mock_item = MagicMock()
        mock_item.check_health = AsyncMock(return_value=False)
        mock_item.ignore = True
        mock_item.reset = AsyncMock()
        h.health_items = [mock_item]
        result = await h.check_health()
        self.assertTrue(result)
        mock_item.reset.assert_not_called()


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
