"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import os
import sys
import unittest

from ..test_setup import AsyncTestCase

parent_dir = os.path.abspath(
    os.path.join(
        os.path.dirname(os.path.realpath(__file__)), os.pardir, os.pardir, os.pardir
    )
)
sys.path.insert(0, parent_dir)
parent_dir = os.path.abspath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir, os.pardir)
)
sys.path.insert(0, parent_dir)
parent_dir = os.path.abspath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir)
)
sys.path.insert(0, parent_dir)


class TestNode(AsyncTestCase):
    async def test_scenerio_1(self):
        """One block ahead, no fork"""


class TestNodeTrackers(unittest.TestCase):
    """Tests for tracker to_dict() methods (coverage for lines 56, 63, 71, 78)."""

    def test_node_server_disconnect_tracker_to_dict(self):
        from yadacoin.tcpsocket.node import NodeServerDisconnectTracker

        tracker = NodeServerDisconnectTracker()
        result = tracker.to_dict()
        self.assertIn("by_host", result)
        self.assertIn("by_reason", result)

    def test_node_server_new_txn_tracker_to_dict(self):
        from yadacoin.tcpsocket.node import NodeServerNewTxnTracker

        tracker = NodeServerNewTxnTracker()
        result = tracker.to_dict()
        self.assertIn("by_host", result)

    def test_node_client_disconnect_tracker_to_dict(self):
        from yadacoin.tcpsocket.node import NodeClientDisconnectTracker

        tracker = NodeClientDisconnectTracker()
        result = tracker.to_dict()
        self.assertIn("by_host", result)
        self.assertIn("by_reason", result)

    def test_node_client_new_txn_tracker_to_dict(self):
        from yadacoin.tcpsocket.node import NodeClientNewTxnTracker

        tracker = NodeClientNewTxnTracker()
        result = tracker.to_dict()
        self.assertIn("by_host", result)


class TestBlocksResponseForkAssembly(AsyncTestCase):
    """Multi-block sync must prepend fork ancestors before queueing."""

    async def test_blocksresponse_includes_backward_blocks(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.blockchain import Blockchain
        from yadacoin.core.processingqueue import BlockProcessingQueueItem
        from yadacoin.tcpsocket.node import NodeSocketServer

        def _mk_block(index, prev_hash, block_hash):
            b = MagicMock()
            b.index = index
            b.prev_hash = prev_hash
            b.hash = block_hash
            b.to_dict.return_value = {
                "index": index,
                "prevHash": prev_hash,
                "hash": block_hash,
            }
            return b

        fork_parent = _mk_block(10, "h9", "hfork10")
        tip_a = _mk_block(11, "hfork10", "htip11")
        tip_b = _mk_block(12, "htip11", "htip12")

        server = NodeSocketServer.__new__(NodeSocketServer)
        server.config = MagicMock()
        server.config.app_log = MagicMock()
        server.config.consensus = MagicMock()
        server.config.consensus.syncing = False
        server.config.consensus.build_remote_chain = AsyncMock(
            return_value=Blockchain([], partial=True)
        )
        server.config.consensus.build_backward_from_block_to_fork = AsyncMock(
            return_value=([fork_parent], True)
        )
        server.config.processing_queues = MagicMock()
        server.config.processing_queues.block_queue = MagicMock()
        server.fill_gap = AsyncMock()
        server.write_result = AsyncMock()

        stream = MagicMock()
        stream.peer.protocol_version = 1
        stream.peer.host = "127.0.0.1"

        body = {
            "id": "req1",
            "result": {
                "start_index": 11,
                "blocks": [tip_a.to_dict(), tip_b.to_dict()],
            },
        }

        with patch(
            "yadacoin.tcpsocket.node.Block.from_dict",
            AsyncMock(side_effect=[tip_a, tip_b]),
        ):
            await server.blocksresponse(body, stream)

        server.fill_gap.assert_not_awaited()
        server.config.processing_queues.block_queue.add.assert_called_once()
        item = server.config.processing_queues.block_queue.add.call_args[0][0]
        self.assertIsInstance(item, BlockProcessingQueueItem)
        queued = item.blockchain.init_blocks
        self.assertEqual([b.hash for b in queued], ["hfork10", "htip11", "htip12"])
        self.assertEqual([b.index for b in queued], [10, 11, 12])

    async def test_blocksresponse_fill_gap_when_fork_incomplete(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.blockchain import Blockchain
        from yadacoin.tcpsocket.node import NodeSocketServer

        tip = MagicMock()
        tip.index = 20
        tip.prev_hash = "missing"
        tip.hash = "h20"
        tip.to_dict.return_value = {
            "index": 20,
            "prevHash": "missing",
            "hash": "h20",
        }

        server = NodeSocketServer.__new__(NodeSocketServer)
        server.config = MagicMock()
        server.config.app_log = MagicMock()
        server.config.consensus = MagicMock()
        server.config.consensus.syncing = False
        server.config.consensus.build_remote_chain = AsyncMock(
            return_value=Blockchain([], partial=True)
        )
        server.config.consensus.build_backward_from_block_to_fork = AsyncMock(
            return_value=([], False)
        )
        server.config.processing_queues = MagicMock()
        server.config.processing_queues.block_queue = MagicMock()
        server.fill_gap = AsyncMock()
        server.write_result = AsyncMock()

        stream = MagicMock()
        stream.peer.protocol_version = 1
        stream.peer.host = "127.0.0.1"

        body = {
            "id": "req2",
            "result": {"start_index": 20, "blocks": [tip.to_dict()]},
        }

        with patch(
            "yadacoin.tcpsocket.node.Block.from_dict",
            AsyncMock(return_value=tip),
        ):
            result = await server.blocksresponse(body, stream)

        self.assertFalse(result)
        server.fill_gap.assert_awaited_once_with(20, stream)
        server.config.processing_queues.block_queue.add.assert_not_called()

    async def test_blocksresponse_no_blocks(self):
        from unittest.mock import AsyncMock, MagicMock

        from yadacoin.tcpsocket.node import NodeSocketServer

        server = NodeSocketServer.__new__(NodeSocketServer)
        server.config = MagicMock()
        server.config.app_log = MagicMock()
        server.config.consensus = MagicMock()
        server.config.consensus.syncing = True
        server.write_result = AsyncMock()

        stream = MagicMock()
        stream.peer.protocol_version = 1
        stream.peer.host = "127.0.0.1"
        stream.synced = False

        body = {"id": "req3", "result": {"blocks": []}}
        await server.blocksresponse(body, stream)

        self.assertFalse(server.config.consensus.syncing)
        self.assertTrue(stream.synced)

    async def test_blocksresponse_protocol_v2_confirms(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.blockchain import Blockchain
        from yadacoin.tcpsocket.node import NodeSocketServer

        tip = MagicMock()
        tip.index = 11
        tip.prev_hash = "h10"
        tip.hash = "h11"
        tip.to_dict.return_value = {"index": 11, "prevHash": "h10", "hash": "h11"}

        server = NodeSocketServer.__new__(NodeSocketServer)
        server.config = MagicMock()
        server.config.app_log = MagicMock()
        server.config.consensus = MagicMock()
        server.config.consensus.syncing = False
        server.config.consensus.build_remote_chain = AsyncMock(
            return_value=Blockchain([], partial=True)
        )
        server.config.consensus.build_backward_from_block_to_fork = AsyncMock(
            return_value=([], True)
        )
        server.config.processing_queues = MagicMock()
        server.config.processing_queues.block_queue = MagicMock()
        server.fill_gap = AsyncMock()
        server.write_result = AsyncMock()

        stream = MagicMock()
        stream.peer.protocol_version = 2
        stream.peer.host = "127.0.0.1"

        body = {
            "id": "req4",
            "result": {"start_index": 11, "blocks": [tip.to_dict()]},
        }

        with patch(
            "yadacoin.tcpsocket.node.Block.from_dict",
            AsyncMock(return_value=tip),
        ):
            await server.blocksresponse(body, stream)

        server.write_result.assert_awaited()
        args = server.write_result.await_args[0]
        self.assertEqual(args[1], "blocksresponse_confirmed")
        server.config.processing_queues.block_queue.add.assert_called_once()
