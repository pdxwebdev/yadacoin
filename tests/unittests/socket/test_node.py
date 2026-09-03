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
        server.config.consensus.insert_consensus_block = AsyncMock(return_value=True)
        server.config.processing_queues = MagicMock()
        server.config.processing_queues.block_queue = MagicMock()
        server.fill_gap = AsyncMock()
        server.write_result = AsyncMock()

        stream = MagicMock()
        stream.peer.protocol_version = 1
        stream.peer.host = "127.0.0.1"
        stream.peer = MagicMock()
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
        server.fill_gap.assert_awaited_once_with(20, stream, first_block=tip)
        server.config.consensus.insert_consensus_block.assert_awaited()
        server.config.processing_queues.block_queue.add.assert_not_called()

    async def test_blocksresponse_no_blocks(self):
        from unittest.mock import AsyncMock, MagicMock

        from yadacoin.tcpsocket.node import NodeSocketServer

        server = NodeSocketServer.__new__(NodeSocketServer)
        server.config = MagicMock()
        server.config.app_log = MagicMock()
        server.config.consensus = MagicMock()
        server.config.consensus.syncing = True
        server.config.LatestBlock.block.index = 100
        server.write_result = AsyncMock()
        server.send_mempool_to_sync_peers = AsyncMock()

        stream = MagicMock()
        stream.peer.protocol_version = 1
        stream.peer.host = "127.0.0.1"
        stream.peer.block = None
        stream.synced = False

        body = {"id": "req3", "result": {"blocks": []}}
        await server.blocksresponse(body, stream)

        self.assertFalse(server.config.consensus.syncing)
        self.assertTrue(stream.synced)
        server.send_mempool_to_sync_peers.assert_awaited_once()

    async def test_blocksresponse_no_blocks_keeps_unsynced_when_peer_ahead(self):
        from unittest.mock import AsyncMock, MagicMock

        from yadacoin.tcpsocket.node import NodeSocketServer

        server = NodeSocketServer.__new__(NodeSocketServer)
        server.config = MagicMock()
        server.config.app_log = MagicMock()
        server.config.consensus = MagicMock()
        server.config.consensus.syncing = True
        server.config.LatestBlock.block.index = 100
        server.write_result = AsyncMock()
        server.send_mempool_to_sync_peers = AsyncMock()

        stream = MagicMock()
        stream.peer.protocol_version = 1
        stream.peer.host = "127.0.0.1"
        stream.peer.block = MagicMock()
        stream.peer.block.index = 250
        stream.synced = True

        body = {"id": "req3", "result": {"blocks": []}}
        await server.blocksresponse(body, stream)

        self.assertFalse(stream.synced)
        server.send_mempool_to_sync_peers.assert_not_awaited()

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


class TestFillGapHashFork(AsyncTestCase):
    async def test_fill_gap_requests_overlap_on_hash_fork(self):
        """Index-contiguous but hash-divergent tips must still pull history."""
        from unittest.mock import AsyncMock, MagicMock

        from yadacoin.core.chain import CHAIN
        from yadacoin.tcpsocket.node import NodeSocketServer

        server = NodeSocketServer.__new__(NodeSocketServer)
        server.config = MagicMock()
        server.config.LatestBlock.block.index = 605120
        server.config.nodeShared = MagicMock()
        server.config.nodeShared.write_params = AsyncMock()

        stream = MagicMock()
        first = MagicMock()
        first.index = 605121
        first.prev_hash = "alt605120"

        await server.fill_gap(605121, stream, first_block=first)

        calls = server.config.nodeShared.write_params.await_args_list
        methods = [c.args[1] for c in calls]
        self.assertIn("getblock", methods)
        self.assertIn("getblocks", methods)
        getblocks = [c for c in calls if c.args[1] == "getblocks"][0]
        params = getblocks.args[2]
        self.assertLessEqual(params["start_index"], 605120)
        self.assertGreaterEqual(params["end_index"], 605120)
        self.assertLessEqual(
            params["end_index"] - params["start_index"] + 1,
            CHAIN.MAX_BLOCKS_PER_MESSAGE,
        )
        getblock = [c for c in calls if c.args[1] == "getblock"][0]
        self.assertEqual(getblock.args[2]["hash"], "alt605120")
        self.assertEqual(getblock.args[2]["index"], 605120)

    async def test_fill_gap_classic_index_hole(self):
        from unittest.mock import AsyncMock, MagicMock

        from yadacoin.tcpsocket.node import NodeSocketServer

        server = NodeSocketServer.__new__(NodeSocketServer)
        server.config = MagicMock()
        server.config.LatestBlock.block.index = 100
        server.config.nodeShared = MagicMock()
        server.config.nodeShared.write_params = AsyncMock()

        stream = MagicMock()
        await server.fill_gap(150, stream)

        server.config.nodeShared.write_params.assert_awaited()
        args = server.config.nodeShared.write_params.await_args[0]
        self.assertEqual(args[1], "getblocks")
        self.assertEqual(args[2]["end_index"], 149)
        self.assertLessEqual(args[2]["start_index"], 149)


class TestNewBlockPeerTracking(AsyncTestCase):
    async def test_newblock_tracks_peer_height_and_clears_synced(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.tcpsocket.node import NodeSocketServer

        block = MagicMock()
        block.index = 200
        block.hash = "h200"

        server = NodeSocketServer.__new__(NodeSocketServer)
        server.config = MagicMock()
        server.config.app_log = MagicMock()
        server.config.LatestBlock.block.index = 100
        server.config.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        server.config.nodeShared.write_result = AsyncMock()
        server.config.processing_queues = MagicMock()
        server.config.processing_queues.block_queue = MagicMock()

        stream = MagicMock()
        stream.peer.protocol_version = 2
        stream.peer.block = None
        stream.synced = True

        body = {
            "id": "nb1",
            "params": {
                "payload": {
                    "block": {"index": 200, "hash": "h200"},
                }
            },
        }

        with patch(
            "yadacoin.tcpsocket.node.Block.from_dict",
            AsyncMock(return_value=block),
        ):
            await server.newblock(body, stream)

        self.assertIs(stream.peer.block, block)
        self.assertFalse(stream.synced)
        server.config.processing_queues.block_queue.add.assert_called_once()

    async def test_newblock_no_payload(self):
        from unittest.mock import AsyncMock, MagicMock

        from yadacoin.tcpsocket.node import NodeSocketServer

        server = NodeSocketServer.__new__(NodeSocketServer)
        server.config = MagicMock()
        server.config.app_log = MagicMock()
        server.config.nodeShared.write_result = AsyncMock()

        stream = MagicMock()
        stream.peer.protocol_version = 1
        body = {"id": "nb2", "params": {"payload": {}}}
        await server.newblock(body, stream)
        server.config.nodeShared.write_result.assert_not_awaited()

    async def test_blocksresponse_no_blocks_bad_peer_index(self):
        from unittest.mock import AsyncMock, MagicMock

        from yadacoin.tcpsocket.node import NodeSocketServer

        server = NodeSocketServer.__new__(NodeSocketServer)
        server.config = MagicMock()
        server.config.app_log = MagicMock()
        server.config.consensus = MagicMock()
        server.config.consensus.syncing = True
        server.config.LatestBlock.block.index = 100
        server.write_result = AsyncMock()
        server.send_mempool_to_sync_peers = AsyncMock()

        stream = MagicMock()
        stream.peer.protocol_version = 1
        stream.peer.host = "127.0.0.1"
        stream.peer.block = MagicMock()
        stream.peer.block.index = object()  # int() fails
        stream.synced = False

        body = {"id": "req5", "result": {"blocks": []}}
        await server.blocksresponse(body, stream)
        self.assertTrue(stream.synced)
        server.send_mempool_to_sync_peers.assert_awaited_once()


class TestNewTxnRelay(AsyncTestCase):
    def _server(self):
        from unittest.mock import AsyncMock, MagicMock

        from yadacoin.tcpsocket.node import NodeSocketServer

        server = NodeSocketServer.__new__(NodeSocketServer)
        server.config = MagicMock()
        server.config.app_log = MagicMock()
        server.config.LatestBlock.block.index = 0
        server.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value=None
        )
        server.config.mongo.async_db.txn_tracking.update_one = AsyncMock()
        server.config.mongo.async_db.txn_tracking.find = MagicMock()
        server.config.processing_queues = MagicMock()
        server.config.processing_queues.transaction_queue = MagicMock()
        server.config.notifier.notify_new_transaction = AsyncMock()
        server.config.modes = []
        server.write_result = AsyncMock()
        server.newtxn_tracker = MagicMock()
        server.newtxn_tracker.by_host = {}
        server.retry_messages = {}
        return server

    async def test_newtxn_confirms_only_after_queue(self):
        from unittest.mock import MagicMock, patch

        from yadacoin.core.processingqueue import TransactionProcessingQueueItem

        server = self._server()
        txn = MagicMock()
        txn.transaction_signature = "sig1"
        txn.inputs = []
        txn.outputs = []
        txn.public_key = "pk"
        txn.are_kel_fields_populated.return_value = False
        txn.to_dict.return_value = {"id": "sig1"}

        stream = MagicMock()
        stream.peer.protocol_version = 4
        stream.peer.rid = "sender"
        stream.peer.host = "10.0.0.1"

        body = {"id": "req", "params": {"transaction": {"id": "sig1"}}}
        with patch("yadacoin.tcpsocket.node.Transaction.from_dict", return_value=txn):
            await server.newtxn(body, stream)

        server.write_result.assert_awaited()
        self.assertEqual(server.write_result.await_args[0][1], "newtxn_confirmed")
        server.config.processing_queues.transaction_queue.add.assert_called_once()
        queued = server.config.processing_queues.transaction_queue.add.call_args[0][0]
        self.assertIsInstance(queued, TransactionProcessingQueueItem)

    async def test_newtxn_kel_null_fields_do_not_false_match(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        server = self._server()
        txn = MagicMock()
        txn.transaction_signature = "sig-kel"
        txn.inputs = []
        txn.outputs = []
        txn.public_key = "wallet-pk"
        txn.are_kel_fields_populated.return_value = True
        txn.is_already_in_mempool = AsyncMock(return_value=False)
        txn.to_dict.return_value = {"id": "sig-kel"}

        stream = MagicMock()
        stream.peer.protocol_version = 4
        stream.peer.rid = "sender"
        stream.peer.host = "10.0.0.1"
        body = {"id": "req", "params": {"transaction": {"id": "sig-kel"}}}
        with patch("yadacoin.tcpsocket.node.Transaction.from_dict", return_value=txn):
            await server.newtxn(body, stream)

        txn.is_already_in_mempool.assert_awaited()
        server.config.mongo.async_db.miner_transactions.find_one.assert_awaited()
        # Must not query mempool with null KEL hashes / public_key $or.
        for (
            call
        ) in server.config.mongo.async_db.miner_transactions.find_one.await_args_list:
            args = call.args
            if args and isinstance(args[0], dict) and "$or" in args[0]:
                self.fail("KEL duplicate used raw $or including possibly-null fields")
        server.config.processing_queues.transaction_queue.add.assert_called_once()

    async def test_newtxn_does_not_confirm_when_kel_duplicate(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        server = self._server()
        txn = MagicMock()
        txn.transaction_signature = "sig-dup"
        txn.inputs = []
        txn.outputs = []
        txn.are_kel_fields_populated.return_value = True
        txn.is_already_in_mempool = AsyncMock(return_value=True)

        stream = MagicMock()
        stream.peer.protocol_version = 4
        stream.peer.rid = "sender"
        stream.peer.host = "10.0.0.1"
        body = {"id": "req", "params": {"transaction": {"id": "sig-dup"}}}
        with patch("yadacoin.tcpsocket.node.Transaction.from_dict", return_value=txn):
            await server.newtxn(body, stream)

        server.write_result.assert_not_awaited()
        server.config.processing_queues.transaction_queue.add.assert_not_called()

    async def test_transient_hold_still_broadcasts(self):
        from unittest.mock import AsyncMock, MagicMock

        from yadacoin.core.transaction import MissingInputTransactionException

        server = self._server()
        server.config.LatestBlock.block.index = 0
        server.config.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        server._broadcast_newtxn = AsyncMock()

        txn = MagicMock()
        txn.coinbase = False
        txn.transaction_signature = "sig-hold"
        txn.to_dict.return_value = {"id": "sig-hold"}
        txn.verify = AsyncMock(side_effect=MissingInputTransactionException("missing"))

        item = MagicMock()
        item.transaction = txn
        await server.process_transaction_queue_item(item)
        server.config.mongo.async_db.miner_transactions.replace_one.assert_awaited()
        server._broadcast_newtxn.assert_awaited_with(txn)

    async def test_send_mempool_skips_invalid_without_deleting(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        server = self._server()
        server.config.LatestBlock.block.index = 0
        bad = {"id": "bad"}

        async def gen():
            yield bad

        server.config.mongo.async_db.miner_transactions.find = MagicMock(
            return_value=gen()
        )
        server.config.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        server.write_params = AsyncMock()
        txn = MagicMock()
        txn.transaction_signature = "bad"
        txn.inputs = [MagicMock()]
        txn.are_kel_fields_populated = MagicMock(return_value=False)
        txn.to_dict.return_value = bad
        txn.verify = AsyncMock(side_effect=Exception("invalid"))
        peer_stream = MagicMock()
        peer_stream.peer.protocol_version = 1
        peer_stream.peer.rid = "pool1"

        with patch(
            "yadacoin.tcpsocket.node.Transaction.from_dict", return_value=txn
        ), patch(
            "yadacoin.tcpsocket.node.Transaction.handle_exception",
            new_callable=AsyncMock,
        ) as handle, patch(
            "yadacoin.tcpsocket.node.Peer.is_synced",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await server.send_mempool(peer_stream)

        handle.assert_not_awaited()
        server.write_params.assert_not_awaited()

    async def test_send_mempool_drops_onchain_and_coinbase(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        server = self._server()
        server.config.LatestBlock.block.index = 0
        doc = {"id": "coinbase_id"}

        async def gen():
            yield doc

        server.config.mongo.async_db.miner_transactions.find = MagicMock(
            return_value=gen()
        )
        server.config.mongo.async_db.miner_transactions.delete_one = AsyncMock()
        server.write_params = AsyncMock()
        txn = MagicMock()
        txn.transaction_signature = "coinbase_id"
        txn.inputs = []
        txn.outputs = [MagicMock(value=12.5)]
        txn.coinbase = False
        txn.verify = AsyncMock()
        peer_stream = MagicMock()
        peer_stream.peer.protocol_version = 1

        fake_block = MagicMock()
        with patch(
            "yadacoin.tcpsocket.node.Transaction.from_dict", return_value=txn
        ), patch.object(
            server,
            "_resolve_block_for_txn",
            new_callable=AsyncMock,
            return_value=fake_block,
        ), patch(
            "yadacoin.tcpsocket.node.Block.is_coinbase", return_value=True
        ), patch(
            "yadacoin.tcpsocket.node.Peer.is_synced",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await server.send_mempool(peer_stream)

        server.config.mongo.async_db.miner_transactions.delete_one.assert_awaited()
        txn.verify.assert_not_awaited()
        server.write_params.assert_not_awaited()

    async def test_send_mempool_skips_when_not_synced(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        server = self._server()
        server.config.mongo.async_db.miner_transactions.find = MagicMock()
        server.write_params = AsyncMock()
        peer_stream = MagicMock()

        with patch(
            "yadacoin.tcpsocket.node.Peer.is_synced",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await server.send_mempool(peer_stream)

        server.config.mongo.async_db.miner_transactions.find.assert_not_called()
        server.write_params.assert_not_awaited()
