"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

Branch coverage tests for yadacoin.core.consensus to reach 100%.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


def _awaitable(value):
    """Return an awaitable that resolves to value (for mocking async properties)."""
    fut = asyncio.Future()
    fut.set_result(value)
    return fut


from tornado.iostream import StreamClosedError

from yadacoin.core.consensus import Consensus, MaxIterationsExceededException

from ..test_setup import AsyncTestCase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk_block(
    index=1,
    target=1,
    special_min=False,
    btime=0,
    bhash="h",
    prev_hash="p",
    signature="sig",
    transactions=None,
):
    b = MagicMock()
    b.index = index
    b.target = target
    b.special_min = special_min
    b.time = btime
    b.hash = bhash
    b.prev_hash = prev_hash
    b.signature = signature
    b.transactions = transactions or []
    b.verify = AsyncMock()
    b.to_dict = MagicMock(
        return_value={
            "index": index,
            "hash": bhash,
            "prevHash": prev_hash,
            "time": btime,
            "target": hex(target)[2:].rjust(64, "0"),
        }
    )
    return b


async def _agen(items):
    for item in items:
        yield item


def _make_async_iter(items):
    """Returns a callable that produces an async iterator over items."""

    async def _iter():
        for it in items:
            yield it

    return _iter


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class ConsensusBase(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.consensus = Consensus()
        self.consensus.app_log = MagicMock()
        self.consensus.debug = False
        self.consensus.prevent_genesis = False
        self.consensus.target = None
        self.consensus.special_target = None
        self.consensus.syncing = False
        self.consensus.last_network_search = 0

        cfg = MagicMock()
        cfg.network = "mainnet"
        cfg.app_log = MagicMock()
        cfg.LatestBlock.block.index = 100
        cfg.LatestBlock.block.to_dict = MagicMock(return_value={"index": 100})
        cfg.LatestBlock.update_latest_block = AsyncMock()

        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.blocks.delete_many = AsyncMock()
        cfg.mongo.async_db.blocks.replace_one = AsyncMock()
        cfg.mongo.async_db.blocks.find = MagicMock()

        cfg.mongo.async_db.consensus.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.consensus.delete_many = AsyncMock()
        cfg.mongo.async_db.consensus.insert_one = AsyncMock()
        _consensus_cursor = MagicMock()
        _consensus_cursor.to_list = AsyncMock(return_value=[])
        cfg.mongo.async_db.consensus.find = MagicMock(return_value=_consensus_cursor)

        cfg.mongo.async_db.miner_transactions.delete_many = AsyncMock()

        cfg.processing_queues.block_queue.pop = MagicMock(return_value=None)
        cfg.processing_queues.block_queue.inc_num_items_processed = MagicMock()
        cfg.processing_queues.block_queue.time_sum_start = MagicMock()
        cfg.processing_queues.block_queue.add = MagicMock()

        cfg.health.consensus.last_activity = 0

        cfg.consensus.insert_consensus_block = AsyncMock(return_value=True)

        cfg.nodeShared.write_result = AsyncMock()
        cfg.nodeShared.write_params = AsyncMock()

        cfg.peer.get_peer_by_id = AsyncMock(return_value=None)

        cfg.BU.insert_genesis = AsyncMock()
        cfg.mp = None

        self.consensus.config = cfg
        self.consensus.mongo = cfg.mongo
        self.consensus.latest_block = MagicMock()
        self.consensus.latest_block.index = 100

        # Patch Config used inside the module
        self._cfg_patch = patch("yadacoin.core.consensus.Config", return_value=cfg)
        self._cfg_patch.start()

    async def asyncTearDown(self):
        self._cfg_patch.stop()
        await super().asyncTearDown()


# ---------------------------------------------------------------------------
# init_async (lines 36-58)
# ---------------------------------------------------------------------------


class TestInitAsync(AsyncTestCase):
    async def test_init_async_with_existing_latest_block(self):
        cfg = MagicMock()
        cfg.LatestBlock.block = MagicMock()
        cfg.LatestBlock.block.index = 5
        cfg.mongo = MagicMock()
        with patch("yadacoin.core.consensus.Config", return_value=cfg):
            c = await Consensus.init_async(debug=True, target=1, special_target=2)
        self.assertEqual(c.target, 1)
        self.assertEqual(c.special_target, 2)
        self.assertTrue(c.debug)
        self.assertEqual(c.latest_block, cfg.LatestBlock.block)

    async def test_init_async_inserts_genesis_when_no_latest(self):
        cfg = MagicMock()
        cfg.LatestBlock.block = None
        cfg.BU.insert_genesis = AsyncMock(
            side_effect=lambda: setattr(cfg.LatestBlock, "block", MagicMock())
        )
        cfg.mongo = MagicMock()
        with patch("yadacoin.core.consensus.Config", return_value=cfg):
            c = await Consensus.init_async(prevent_genesis=False)
        cfg.BU.insert_genesis.assert_awaited()
        self.assertIsNotNone(c.latest_block)

    async def test_init_async_prevent_genesis(self):
        cfg = MagicMock()
        cfg.LatestBlock.block = None
        cfg.mongo = MagicMock()
        with patch("yadacoin.core.consensus.Config", return_value=cfg):
            c = await Consensus.init_async(prevent_genesis=True)
        cfg.BU.insert_genesis.assert_not_called()
        self.assertFalse(hasattr(c, "latest_block"))


# ---------------------------------------------------------------------------
# verify_existing_blockchain (lines 61-91)
# ---------------------------------------------------------------------------


class TestVerifyExistingBlockchain(ConsensusBase):
    async def _patch_blockchain(self, verify_result):
        bc = MagicMock()
        bc.verify = AsyncMock(return_value=verify_result)
        return patch("yadacoin.core.consensus.Blockchain", return_value=bc)

    async def test_verify_success(self):
        with await self._patch_blockchain({"verified": True}):
            r = await self.consensus.verify_existing_blockchain()
        self.assertTrue(r)

    async def test_verify_fail_reset_with_last_good_block(self):
        good_block = MagicMock()
        good_block.index = 50
        with await self._patch_blockchain(
            {"verified": False, "message": "bad", "last_good_block": good_block}
        ):
            r = await self.consensus.verify_existing_blockchain(reset=True)
        self.consensus.mongo.async_db.blocks.delete_many.assert_awaited_with(
            {"index": {"$gt": 50}}
        )
        self.assertIsNone(r)

    async def test_verify_fail_reset_without_last_good_block(self):
        with await self._patch_blockchain({"verified": False, "message": "bad"}):
            await self.consensus.verify_existing_blockchain(reset=True)
        self.consensus.mongo.async_db.blocks.delete_many.assert_awaited_with(
            {"index": {"$gt": 0}}
        )

    async def test_verify_fail_no_reset(self):
        with await self._patch_blockchain({"verified": False, "message": "bad"}):
            await self.consensus.verify_existing_blockchain(reset=False)
        self.consensus.mongo.async_db.blocks.delete_many.assert_not_called()


# ---------------------------------------------------------------------------
# process_block_queue (lines 94-106)
# ---------------------------------------------------------------------------


class TestProcessBlockQueue(ConsensusBase):
    async def test_empty_queue_exits(self):
        self.consensus.config.processing_queues.block_queue.pop.return_value = None
        await self.consensus.process_block_queue()

    async def test_max_loops(self):
        item = MagicMock()
        # always return an item
        self.consensus.config.processing_queues.block_queue.pop.return_value = item
        self.consensus.process_block_queue_item = AsyncMock()
        await self.consensus.process_block_queue()
        # 100 calls
        self.assertEqual(self.consensus.process_block_queue_item.await_count, 100)


# ---------------------------------------------------------------------------
# process_block_queue_item (lines 109-210)
# ---------------------------------------------------------------------------


class TestProcessBlockQueueItem(ConsensusBase):
    def _mk_item(self, body=None):
        item = MagicMock()
        stream = MagicMock()
        peer = MagicMock()
        peer.protocol_version = 2
        peer.identity.to_dict = {"a": 1}
        stream.peer = peer
        item.stream = stream
        item.body = body
        # Blockchain init_blocks list path
        bc = MagicMock()
        bc.init_blocks = [{"index": 1}]
        bc.first_block = {"index": 1, "hash": "h1"}
        bc.final_block = {"index": 2, "hash": "h2"}
        bc.count = _awaitable(1)
        bc.blocks = _agen([])
        item.blockchain = bc
        return item, stream

    async def test_no_body(self):
        item, _ = self._mk_item(body=None)
        item.blockchain.first_block = {"hash": "h1"}
        item.blockchain.final_block = {"hash": "h2"}
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(), _mk_block()]),
        ):
            self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
                side_effect=[{"hash": "h1"}, {"hash": "h2"}]
            )
            await self.consensus.process_block_queue_item(item)

    async def test_blockresponse_no_block(self):
        item, _ = self._mk_item(body={"method": "blockresponse", "result": {}})
        item.blockchain.first_block = {"hash": "h1"}
        item.blockchain.final_block = {"hash": "h2"}
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(), _mk_block()]),
        ):
            self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
                side_effect=[{"hash": "h1"}, {"hash": "h2"}]
            )
            await self.consensus.process_block_queue_item(item)

    async def test_blockresponse_index_too_far(self):
        item, _ = self._mk_item(
            body={"method": "blockresponse", "result": {"block": {"index": 999}}}
        )
        block = _mk_block(index=300)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=block),
        ):
            await self.consensus.process_block_queue_item(item)

    async def test_blockresponse_insert_fails(self):
        item, _ = self._mk_item(
            body={"method": "blockresponse", "result": {"block": {"index": 105}}}
        )
        block = _mk_block(index=105)
        self.consensus.config.consensus.insert_consensus_block = AsyncMock(
            return_value=False
        )
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=block),
        ):
            await self.consensus.process_block_queue_item(item)
        self.consensus.config.consensus.insert_consensus_block.assert_awaited()

    async def test_blockresponse_insert_succeeds(self):
        item, _ = self._mk_item(
            body={"method": "blockresponse", "result": {"block": {"index": 105}}}
        )
        block = _mk_block(index=105)
        self.consensus.config.consensus.insert_consensus_block = AsyncMock(
            return_value=True
        )
        self.consensus.queue_consensus_tips = AsyncMock(return_value=True)
        self.consensus.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=block),
        ):
            await self.consensus.process_block_queue_item(item)
        self.consensus.config.consensus.insert_consensus_block.assert_awaited()
        self.consensus.queue_consensus_tips.assert_awaited_once_with(item.stream)

    async def test_blockresponse_insert_fails_does_not_queue_tips(self):
        item, _ = self._mk_item(
            body={"method": "blockresponse", "result": {"block": {"index": 105}}}
        )
        block = _mk_block(index=105)
        self.consensus.config.consensus.insert_consensus_block = AsyncMock(
            return_value=False
        )
        self.consensus.queue_consensus_tips = AsyncMock(return_value=True)
        self.consensus.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=block),
        ):
            await self.consensus.process_block_queue_item(item)
        self.consensus.config.consensus.insert_consensus_block.assert_awaited()
        self.consensus.queue_consensus_tips.assert_not_awaited()

    async def test_blockresponse_index_not_greater_still_inserts_off_chain(self):
        item, _ = self._mk_item(
            body={"method": "blockresponse", "result": {"block": {"index": 50}}}
        )
        block = _mk_block(index=50)
        self.consensus.config.consensus.insert_consensus_block = AsyncMock(
            return_value=True
        )
        self.consensus.queue_consensus_tips = AsyncMock(return_value=True)
        self.consensus.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=block),
        ):
            await self.consensus.process_block_queue_item(item)
        self.consensus.config.consensus.insert_consensus_block.assert_awaited()
        self.consensus.queue_consensus_tips.assert_awaited_once_with(item.stream)

    async def test_blockresponse_skips_insert_when_already_on_chain(self):
        item, _ = self._mk_item(
            body={"method": "blockresponse", "result": {"block": {"index": 50}}}
        )
        block = _mk_block(index=50)
        self.consensus.config.consensus.insert_consensus_block = AsyncMock(
            return_value=True
        )
        self.consensus.queue_consensus_tips = AsyncMock(return_value=True)
        self.consensus.mongo.async_db.blocks.find_one = AsyncMock(
            return_value={"hash": block.hash}
        )
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=block),
        ):
            await self.consensus.process_block_queue_item(item)
        self.consensus.config.consensus.insert_consensus_block.assert_not_awaited()
        self.consensus.queue_consensus_tips.assert_not_awaited()

    async def test_newblock_no_block(self):
        item, _ = self._mk_item(
            body={"method": "newblock", "params": {"payload": {}}, "id": 1}
        )
        item.blockchain.first_block = {"hash": "h1"}
        item.blockchain.final_block = {"hash": "h2"}
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(), _mk_block()]),
        ):
            self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
                side_effect=[{"hash": "h1"}, {"hash": "h2"}]
            )
            await self.consensus.process_block_queue_item(item)

    async def test_newblock_protocol_v1_no_write_result(self):
        item, _ = self._mk_item(
            body={"method": "newblock", "params": {"payload": {}}, "id": 1}
        )
        item.stream.peer.protocol_version = 1
        item.blockchain.first_block = {"hash": "h1"}
        item.blockchain.final_block = {"hash": "h2"}
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(), _mk_block()]),
        ):
            self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
                side_effect=[{"hash": "h1"}, {"hash": "h2"}]
            )
            await self.consensus.process_block_queue_item(item)
        self.consensus.config.nodeShared.write_result.assert_not_called()

    async def test_newblock_time_in_future(self):
        item, _ = self._mk_item(
            body={
                "method": "newblock",
                "params": {"payload": {"block": {"index": 50}}},
                "id": 1,
            }
        )
        block = _mk_block(index=50, btime=10**12)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=block),
        ):
            await self.consensus.process_block_queue_item(item)

    async def test_newblock_index_too_far(self):
        item, _ = self._mk_item(
            body={
                "method": "newblock",
                "params": {"payload": {"block": {"index": 999}}},
                "id": 1,
            }
        )
        block = _mk_block(index=999, btime=1)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=block),
        ):
            await self.consensus.process_block_queue_item(item)

    async def test_newblock_index_less_than_latest(self):
        item, _ = self._mk_item(
            body={
                "method": "newblock",
                "params": {"payload": {"block": {"index": 5}}},
                "id": 1,
            }
        )
        block = _mk_block(index=5, btime=1)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=block),
        ):
            await self.consensus.process_block_queue_item(item)
        self.consensus.config.nodeShared.write_params.assert_awaited()

    async def test_newblock_insert_fails(self):
        item, _ = self._mk_item(
            body={
                "method": "newblock",
                "params": {"payload": {"block": {"index": 105}}},
                "id": 1,
            }
        )
        block = _mk_block(index=105, btime=1)
        self.consensus.config.consensus.insert_consensus_block = AsyncMock(
            return_value=False
        )
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=block),
        ):
            await self.consensus.process_block_queue_item(item)

    async def test_first_and_final_existing_returns(self):
        item, _ = self._mk_item(body=None)
        item.blockchain.first_block = {"hash": "h1"}
        item.blockchain.final_block = {"hash": "h2"}
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(), _mk_block()]),
        ):
            self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
                side_effect=[{"hash": "h1"}, {"hash": "h2"}]
            )
            await self.consensus.process_block_queue_item(item)

    async def test_count_zero(self):
        item, _ = self._mk_item(body=None)
        item.blockchain.first_block = {"hash": "h1"}
        item.blockchain.final_block = {"hash": "h2"}
        item.blockchain.count = _awaitable(0)
        self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
            return_value=None
        )
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(), _mk_block()]),
        ):
            await self.consensus.process_block_queue_item(item)

    async def test_count_one_integrates_block(self):
        item, _ = self._mk_item(body=None)
        item.blockchain.first_block = {"hash": "h1"}
        item.blockchain.final_block = {"hash": "h2"}
        item.blockchain.count = _awaitable(1)
        self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
            return_value=None
        )
        self.consensus.integrate_block_with_existing_chain = AsyncMock()
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(), _mk_block()]),
        ):
            await self.consensus.process_block_queue_item(item)
        self.consensus.integrate_block_with_existing_chain.assert_awaited()

    async def test_count_many_integrates_chain(self):
        item, _ = self._mk_item(body=None)
        item.blockchain.first_block = {"hash": "h1"}
        item.blockchain.final_block = {"hash": "h2"}
        item.blockchain.count = _awaitable(5)
        self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
            return_value=None
        )
        self.consensus.integrate_blocks_with_existing_chain = AsyncMock()
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(), _mk_block()]),
        ):
            await self.consensus.process_block_queue_item(item)
        self.consensus.integrate_blocks_with_existing_chain.assert_awaited()

    async def test_async_first_final_blocks_path(self):
        """Non-list init_blocks triggers async_first_block / async_final_block."""
        item, _ = self._mk_item(body=None)
        item.blockchain.init_blocks = MagicMock()  # not a list

        # async properties returning dicts
        async def _afb():
            return {"hash": "h1"}

        async def _alf():
            return {"hash": "h2"}

        item.blockchain.async_first_block = _afb()
        item.blockchain.async_final_block = _alf()
        item.blockchain.count = _awaitable(0)
        self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
            return_value=None
        )
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(), _mk_block()]),
        ):
            await self.consensus.process_block_queue_item(item)


# ---------------------------------------------------------------------------
# remove_pending_transactions_now_in_chain (lines 213-217)
# ---------------------------------------------------------------------------


class TestRemovePendingTxs(ConsensusBase):
    async def test_removes(self):
        block = {"block": {"transactions": [{"id": "a"}, {"id": "b"}]}}
        await self.consensus.remove_pending_transactions_now_in_chain(block)
        self.consensus.mongo.async_db.miner_transactions.delete_many.assert_awaited_with(
            {"id": {"$in": ["a", "b"]}}
        )


# ---------------------------------------------------------------------------
# insert_consensus_block (lines 219-258)
# ---------------------------------------------------------------------------


class TestInsertConsensusBlock(ConsensusBase):
    def _mk_peer(self):
        peer = MagicMock()
        peer.to_string.return_value = "peer1"
        peer.to_dict.return_value = {"p": 1}
        return peer

    async def test_existing_returns_true(self):
        self.consensus.mongo.async_db.consensus.find_one = AsyncMock(
            return_value={"x": 1}
        )
        block = _mk_block()
        peer = self._mk_peer()
        r = await self.consensus.insert_consensus_block(block, peer)
        self.assertTrue(r)

    async def test_verify_fails(self):
        block = _mk_block()
        block.verify = AsyncMock(side_effect=Exception("bad"))
        peer = self._mk_peer()
        r = await self.consensus.insert_consensus_block(block, peer)
        self.assertFalse(r)

    async def test_inserts(self):
        block = _mk_block()
        peer = self._mk_peer()
        r = await self.consensus.insert_consensus_block(block, peer)
        self.assertTrue(r)
        self.consensus.mongo.async_db.consensus.delete_many.assert_awaited()
        self.consensus.mongo.async_db.consensus.insert_one.assert_awaited()


# ---------------------------------------------------------------------------
# queue_consensus_tips
# ---------------------------------------------------------------------------


class TestQueueConsensusTips(ConsensusBase):
    async def test_queues_tip_and_next(self):
        tip_rec = {
            "block": {"index": 100, "transactions": [], "target": "02"},
            "peer": {"rid": "r1"},
        }
        next_rec = {
            "block": {"index": 101, "transactions": [], "target": "01"},
            "peer": {"rid": "r1"},
        }
        cursor_next = MagicMock()
        cursor_next.to_list = AsyncMock(return_value=[next_rec])
        cursor_tip = MagicMock()
        cursor_tip.to_list = AsyncMock(return_value=[tip_rec])
        self.consensus.mongo.async_db.consensus.find = MagicMock(
            side_effect=[cursor_next, cursor_tip]
        )
        stream = MagicMock()
        stream.peer.authenticated = True
        self.consensus.config.peer.get_peer_by_id = AsyncMock(return_value=stream)
        with patch("yadacoin.core.consensus.Blockchain"):
            queued = await self.consensus.queue_consensus_tips()
        self.assertTrue(queued)
        self.assertEqual(
            self.consensus.config.processing_queues.block_queue.add.call_count, 2
        )

    async def test_no_authenticated_stream_returns_false(self):
        cursor = MagicMock()
        cursor.to_list = AsyncMock(
            return_value=[
                {
                    "block": {"index": 101, "transactions": [], "target": "01"},
                    "peer": {"rid": "r1"},
                }
            ]
        )
        self.consensus.mongo.async_db.consensus.find = MagicMock(return_value=cursor)
        self.consensus.config.peer.get_peer_by_id = AsyncMock(return_value=None)
        queued = await self.consensus.queue_consensus_tips()
        self.assertFalse(queued)
        self.consensus.config.processing_queues.block_queue.add.assert_not_called()

    async def test_uses_provided_authenticated_stream(self):
        rec = {
            "block": {"index": 101, "transactions": [], "target": "01"},
            "peer": {"rid": "r1"},
        }
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[rec])
        self.consensus.mongo.async_db.consensus.find = MagicMock(return_value=cursor)
        stream = MagicMock()
        stream.peer.authenticated = True
        self.consensus.config.peer.get_peer_by_id = AsyncMock()
        with patch("yadacoin.core.consensus.Blockchain"):
            queued = await self.consensus.queue_consensus_tips(stream)
        self.assertTrue(queued)
        self.consensus.config.peer.get_peer_by_id.assert_not_awaited()
        self.consensus.config.processing_queues.block_queue.add.assert_called()

    async def test_unauthenticated_provided_stream_falls_back_to_peer_lookup(self):
        rec = {
            "block": {"index": 101, "transactions": [], "target": "01"},
            "peer": {"rid": "r1"},
        }
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[rec])
        self.consensus.mongo.async_db.consensus.find = MagicMock(return_value=cursor)
        bad_stream = MagicMock()
        bad_stream.peer.authenticated = False
        good_stream = MagicMock()
        good_stream.peer.authenticated = True
        self.consensus.config.peer.get_peer_by_id = AsyncMock(return_value=good_stream)
        with patch("yadacoin.core.consensus.Blockchain"):
            queued = await self.consensus.queue_consensus_tips(bad_stream)
        self.assertTrue(queued)
        self.consensus.config.peer.get_peer_by_id.assert_awaited()

    async def test_skips_unauthenticated_lookup_stream(self):
        """Covers the continue branch when looked-up stream is not authenticated."""
        rec = {
            "block": {"index": 101, "transactions": [], "target": "01"},
            "peer": {"rid": "r1"},
        }
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[rec])
        self.consensus.mongo.async_db.consensus.find = MagicMock(return_value=cursor)
        unauth = MagicMock()
        unauth.peer.authenticated = False
        self.consensus.config.peer.get_peer_by_id = AsyncMock(return_value=unauth)
        queued = await self.consensus.queue_consensus_tips()
        self.assertFalse(queued)
        self.consensus.config.processing_queues.block_queue.add.assert_not_called()

    async def test_empty_records_returns_false(self):
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[])
        self.consensus.mongo.async_db.consensus.find = MagicMock(return_value=cursor)
        queued = await self.consensus.queue_consensus_tips()
        self.assertFalse(queued)


# ---------------------------------------------------------------------------
# sync_bottom_up (lines 260-325)
# ---------------------------------------------------------------------------


class TestSyncBottomUp(ConsensusBase):
    async def test_no_consensus_then_search(self):
        self.consensus.config.mongo.async_db.consensus.find_one = AsyncMock(
            return_value=None
        )
        self.consensus.search_network_for_new = AsyncMock(return_value=True)
        r = await self.consensus.sync_bottom_up(synced=False)
        self.assertTrue(r)

    async def test_no_consensus_synced_no_search_due_to_recent(self):
        self.consensus.config.mongo.async_db.consensus.find_one = AsyncMock(
            return_value=None
        )
        from time import time as _t

        self.consensus.last_network_search = _t() + 1000
        self.consensus.search_network_for_new = AsyncMock(return_value=True)
        r = await self.consensus.sync_bottom_up(synced=True)
        self.consensus.search_network_for_new.assert_not_called()
        self.assertIsNone(r)

    async def test_consensus_with_authenticated_stream(self):
        self.consensus.debug = True
        consensus_record = {
            "block": {
                "index": 101,
                "transactions": [{"id": "x"}],
                "target": "01",
            },
            "peer": {"rid": "r1"},
            "index": 101,
        }

        async def _find_one(query, *args, **kwargs):
            if query.get("index") == 101:
                return consensus_record
            return None

        self.consensus.config.mongo.async_db.consensus.find_one = AsyncMock(
            side_effect=_find_one
        )

        # Async cursor mock for find().to_list
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[consensus_record])
        self.consensus.config.mongo.async_db.consensus.find = MagicMock(
            return_value=cursor
        )

        # Authenticated stream
        stream = MagicMock()
        stream.peer.authenticated = True
        self.consensus.config.peer.get_peer_by_id = AsyncMock(return_value=stream)
        self.consensus.remove_pending_transactions_now_in_chain = AsyncMock()

        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block()),
        ), patch("yadacoin.core.consensus.Blockchain"):
            r = await self.consensus.sync_bottom_up(synced=True)

        self.assertTrue(r)
        self.consensus.config.processing_queues.block_queue.add.assert_called()
        self.consensus.remove_pending_transactions_now_in_chain.assert_awaited_once_with(
            consensus_record
        )

    async def test_consensus_no_stream_triggers_search(self):
        consensus_record = {
            "block": {"index": 101, "transactions": [], "target": "01"},
            "peer": {"rid": "r1"},
        }

        async def _find_one(query, *args, **kwargs):
            if query.get("index") == 101:
                return consensus_record
            return None

        self.consensus.config.mongo.async_db.consensus.find_one = AsyncMock(
            side_effect=_find_one
        )
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[consensus_record])
        self.consensus.config.mongo.async_db.consensus.find = MagicMock(
            return_value=cursor
        )
        self.consensus.config.peer.get_peer_by_id = AsyncMock(return_value=None)
        self.consensus.search_network_for_new = AsyncMock(return_value="found")
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block()),
        ), patch("yadacoin.core.consensus.Blockchain"):
            r = await self.consensus.sync_bottom_up(synced=False)
        self.assertEqual(r, "found")

    async def test_advancing_block_logs(self):
        # latest_block.index < new latest -> logs "Block height"
        self.consensus.latest_block = MagicMock()
        self.consensus.latest_block.index = 50
        self.consensus.config.LatestBlock.block.index = 200
        self.consensus.config.mongo.async_db.consensus.find_one = AsyncMock(
            return_value=None
        )
        self.consensus.search_network_for_new = AsyncMock(return_value=True)
        await self.consensus.sync_bottom_up(synced=False)

    async def test_same_height_candidate_is_queued(self):
        consensus_record = {
            "block": {
                "index": 100,
                "transactions": [],
                "target": "01",
            },
            "peer": {"rid": "r1"},
            "index": 100,
        }

        async def _find_one(query, *args, **kwargs):
            if query.get("index") == 100:
                return consensus_record
            return None

        self.consensus.config.mongo.async_db.consensus.find_one = AsyncMock(
            side_effect=_find_one
        )
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[consensus_record])
        self.consensus.config.mongo.async_db.consensus.find = MagicMock(
            return_value=cursor
        )
        stream = MagicMock()
        stream.peer.authenticated = True
        self.consensus.config.peer.get_peer_by_id = AsyncMock(return_value=stream)
        self.consensus.remove_pending_transactions_now_in_chain = AsyncMock()
        self.consensus.search_network_for_new = AsyncMock(return_value=True)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(index=100)),
        ), patch("yadacoin.core.consensus.Blockchain"):
            r = await self.consensus.sync_bottom_up(synced=True)
        self.assertTrue(r)
        self.consensus.config.processing_queues.block_queue.add.assert_called()
        self.consensus.remove_pending_transactions_now_in_chain.assert_not_awaited()

    async def test_candidate_no_stream_synced_recent_skips_search(self):
        from time import time as _t

        consensus_record = {
            "block": {"index": 101, "transactions": [], "target": "01"},
            "peer": {"rid": "r1"},
            "index": 101,
        }

        async def _find_one(query, *args, **kwargs):
            if query.get("index") == 101:
                return consensus_record
            return None

        self.consensus.config.mongo.async_db.consensus.find_one = AsyncMock(
            side_effect=_find_one
        )
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[consensus_record])
        self.consensus.config.mongo.async_db.consensus.find = MagicMock(
            return_value=cursor
        )
        self.consensus.config.peer.get_peer_by_id = AsyncMock(return_value=None)
        self.consensus.last_network_search = _t() + 1000
        self.consensus.search_network_for_new = AsyncMock(return_value=True)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block()),
        ), patch("yadacoin.core.consensus.Blockchain"):
            r = await self.consensus.sync_bottom_up(synced=True)
        self.assertTrue(r)
        self.consensus.search_network_for_new.assert_not_called()


# ---------------------------------------------------------------------------
# search_network_for_new (lines 328-344)
# ---------------------------------------------------------------------------


class TestSearchNetwork(ConsensusBase):
    async def test_regnet_returns_false(self):
        self.consensus.config.network = "regnet"
        r = await self.consensus.search_network_for_new()
        self.assertFalse(r)

    async def test_syncing_returns_false(self):
        self.consensus.syncing = True
        r = await self.consensus.search_network_for_new()
        self.assertFalse(r)

    async def test_iterates_peers_with_skips_and_exception(self):
        peer_synced = MagicMock(synced=True, message_queue={}, block=None)
        peer_queued = MagicMock(
            synced=False, message_queue={"getblocks": True}, block=None
        )
        peer_ok = MagicMock(synced=False, message_queue={}, block=None)
        peer_closed = MagicMock(synced=False, message_queue={}, block=None)
        peer_error = MagicMock(synced=False, message_queue={}, block=None)

        async def _peers():
            for p in [peer_synced, peer_queued, peer_ok, peer_closed, peer_error]:
                yield p

        self.consensus.config.peer.get_sync_peers = MagicMock(return_value=_peers())

        async def request(peer):
            if peer is peer_closed:
                raise StreamClosedError()
            if peer is peer_error:
                raise RuntimeError("boom")

        self.consensus.request_blocks = AsyncMock(side_effect=request)
        await self.consensus.search_network_for_new()
        peer_closed.close.assert_called()


# ---------------------------------------------------------------------------
# request_blocks (line 347)
# ---------------------------------------------------------------------------


class TestRequestBlocks(ConsensusBase):
    async def test_writes_params(self):
        peer = MagicMock()
        await self.consensus.request_blocks(peer)
        self.consensus.config.nodeShared.write_params.assert_awaited()


# ---------------------------------------------------------------------------
# build_local_chain (lines 357-360)
# ---------------------------------------------------------------------------


class TestBuildLocalChain(ConsensusBase):
    async def test_returns_blockchain(self):
        cursor = MagicMock()
        cursor.sort = MagicMock(return_value=cursor)
        self.consensus.config.mongo.async_db.blocks.find = MagicMock(
            return_value=cursor
        )
        with patch("yadacoin.core.consensus.Blockchain") as BC:
            BC.return_value = "BC"
            r = await self.consensus.build_local_chain(_mk_block(index=10))
        self.assertEqual(r, "BC")


# ---------------------------------------------------------------------------
# build_remote_chain (lines 364-397)
# ---------------------------------------------------------------------------


class TestBuildRemoteChain(ConsensusBase):
    async def test_no_links_returns_single_block(self):
        # Both lookups return None -> break immediately
        self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
            return_value=None
        )
        self.consensus.config.mongo.async_db.consensus.find_one = AsyncMock(
            return_value=None
        )
        with patch("yadacoin.core.consensus.Blockchain") as BC:
            BC.return_value = "BC"
            r = await self.consensus.build_remote_chain(_mk_block(index=1))
        self.assertEqual(r, "BC")

    async def test_local_chain_extends(self):
        # First call returns local block, second returns None
        next_block = {"index": 2, "hash": "h2", "prevHash": "h1"}
        self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
            side_effect=[next_block, None]
        )
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(index=2)),
        ), patch("yadacoin.core.consensus.Blockchain") as BC:
            BC.return_value = "BC"
            r = await self.consensus.build_remote_chain(_mk_block(index=1))
        self.assertEqual(r, "BC")

    async def test_consensus_chain_extends(self):
        consensus_rec = {"block": {"index": 2, "hash": "h2", "prevHash": "h1"}}
        # local always None, consensus first returns rec, then None
        self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
            return_value=None
        )
        self.consensus.config.mongo.async_db.consensus.find_one = AsyncMock(
            side_effect=[consensus_rec, None]
        )
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(index=2)),
        ), patch("yadacoin.core.consensus.Blockchain"):
            await self.consensus.build_remote_chain(_mk_block(index=1))

    async def test_max_iterations_raises(self):
        # local block always returns -> infinite chain
        self.consensus.config.mongo.async_db.blocks.find_one = AsyncMock(
            return_value={"index": 2, "hash": "h", "prevHash": "p"}
        )
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(index=2)),
        ):
            with self.assertRaises(MaxIterationsExceededException):
                await self.consensus.build_remote_chain(_mk_block(index=1))


# ---------------------------------------------------------------------------
# get_previous_consensus_block_from_local (lines 401-410)
# ---------------------------------------------------------------------------


class TestGetPreviousFromLocal(ConsensusBase):
    async def test_yields(self):
        async def _records():
            yield {"block": {"hash": "h"}}
            yield {"block": {"hash": "h2"}}

        self.consensus.mongo.async_db.consensus.find = MagicMock(
            return_value=_records()
        )
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(), _mk_block()]),
        ):
            results = [
                b
                async for b in self.consensus.get_previous_consensus_block_from_local(
                    _mk_block(index=2)
                )
            ]
        self.assertEqual(len(results), 2)


# ---------------------------------------------------------------------------
# get_previous_consensus_block (lines 413-418)
# ---------------------------------------------------------------------------


class TestGetPreviousConsensusBlock(ConsensusBase):
    async def test_local_results_yields_no_stream(self):
        async def _gen(_self, _block):
            yield _mk_block()

        with patch.object(Consensus, "get_previous_consensus_block_from_local", _gen):
            results = [
                b
                async for b in self.consensus.get_previous_consensus_block(_mk_block())
            ]
        self.assertEqual(len(results), 1)

    async def test_no_local_with_stream_writes_params(self):
        async def _gen(_self, _block):
            if False:
                yield  # empty generator

        stream = MagicMock()
        with patch.object(Consensus, "get_previous_consensus_block_from_local", _gen):
            results = [
                b
                async for b in self.consensus.get_previous_consensus_block(
                    _mk_block(), stream=stream
                )
            ]
        self.assertEqual(results, [])
        self.consensus.config.nodeShared.write_params.assert_awaited()


# ---------------------------------------------------------------------------
# build_backward_from_block_to_fork (lines 425-451)
# ---------------------------------------------------------------------------


class TestBuildBackward(ConsensusBase):
    async def test_retrace_block_found(self):
        self.consensus.mongo.async_db.blocks.find_one = AsyncMock(
            return_value={"hash": "p"}
        )
        blocks, status = await self.consensus.build_backward_from_block_to_fork(
            _mk_block(), []
        )
        self.assertEqual(blocks, [])
        self.assertTrue(status)

    async def test_no_consensus_returns_false(self):
        self.consensus.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)

        async def _empty(_self, _block, _stream=None):
            if False:
                yield

        with patch.object(Consensus, "get_previous_consensus_block", _empty):
            blocks, status = await self.consensus.build_backward_from_block_to_fork(
                _mk_block(), []
            )
        self.assertFalse(status)

    async def test_recurses_with_consensus(self):
        # local find_one returns None first time, then returns hit (terminating recursion)
        self.consensus.mongo.async_db.blocks.find_one = AsyncMock(
            side_effect=[None, {"hash": "p"}]
        )

        async def _gen(_self, _block, _stream=None):
            yield _mk_block(index=_block.index - 1)

        with patch.object(Consensus, "get_previous_consensus_block", _gen):
            blocks, status = await self.consensus.build_backward_from_block_to_fork(
                _mk_block(index=5), []
            )
        self.assertTrue(status)
        self.assertEqual(len(blocks), 1)

    async def test_recurses_with_blocks_none(self):
        """Line 442: blocks=None branch initializes to []."""
        self.consensus.mongo.async_db.blocks.find_one = AsyncMock(
            side_effect=[None, {"hash": "p"}]
        )

        async def _gen(_self, _block, _stream=None):
            yield _mk_block(index=_block.index - 1)

        with patch.object(Consensus, "get_previous_consensus_block", _gen):
            blocks, status = await self.consensus.build_backward_from_block_to_fork(
                _mk_block(index=5), None
            )
        self.assertTrue(status)
        self.assertEqual(len(blocks), 1)


# ---------------------------------------------------------------------------
# integrate_block_with_existing_chain (lines 454-478)
# ---------------------------------------------------------------------------


class TestIntegrateBlockWithExisting(ConsensusBase):
    async def test_status_false_returns(self):
        self.consensus.build_backward_from_block_to_fork = AsyncMock(
            return_value=([], False)
        )
        await self.consensus.integrate_block_with_existing_chain(
            _mk_block(), MagicMock()
        )

    async def test_not_consecutive_returns_false(self):
        self.consensus.build_backward_from_block_to_fork = AsyncMock(
            return_value=([_mk_block()], True)
        )
        forward_chain = MagicMock()
        forward_chain.blocks = _agen([_mk_block()])
        self.consensus.build_remote_chain = AsyncMock(return_value=forward_chain)

        bc_instance = MagicMock()

        async def _is_consec_false(self):
            return False

        type(bc_instance).is_consecutive = property(lambda s: _is_consec_false(s))
        bc_instance.blocks = _agen([_mk_block()])
        with patch("yadacoin.core.consensus.Blockchain", return_value=bc_instance):
            r = await self.consensus.integrate_block_with_existing_chain(
                _mk_block(), MagicMock()
            )
        self.assertFalse(r)

    async def test_consecutive_calls_integrate_blocks(self):
        self.consensus.build_backward_from_block_to_fork = AsyncMock(
            return_value=([_mk_block()], True)
        )
        forward_chain = MagicMock()
        forward_chain.blocks = _agen([_mk_block()])
        self.consensus.build_remote_chain = AsyncMock(return_value=forward_chain)

        async def _is_consec(self):
            return True

        bc_instance = MagicMock()
        type(bc_instance).is_consecutive = property(lambda s: _is_consec(s))
        bc_instance.blocks = _agen([_mk_block()])
        self.consensus.integrate_blocks_with_existing_chain = AsyncMock()
        with patch("yadacoin.core.consensus.Blockchain", return_value=bc_instance):
            await self.consensus.integrate_block_with_existing_chain(
                _mk_block(), MagicMock()
            )
        self.consensus.integrate_blocks_with_existing_chain.assert_awaited()


# ---------------------------------------------------------------------------
# integrate_blocks_with_existing_chain (lines 481-533)
# ---------------------------------------------------------------------------


class TestIntegrateBlocksWithExisting(ConsensusBase):
    def _mk_blockchain(self, blocks_list, init_blocks_is_list=True):
        bc = MagicMock()
        # final_block must have .index attribute (used at line 515 of source).
        first_obj = SimpleNamespace(index=1, hash="h1")
        final_obj = SimpleNamespace(index=2, hash="h2")
        if init_blocks_is_list:
            bc.init_blocks = blocks_list
            bc.first_block = first_obj
            bc.final_block = final_obj
        else:
            bc.init_blocks = MagicMock()

            async def _afb():
                return first_obj

            async def _alf():
                return final_obj

            bc.async_first_block = _afb()
            bc.async_final_block = _alf()

        # blocks property returns async iterator each access
        def _blocks_prop(_self=bc):
            return _agen(list(blocks_list))

        type(bc).blocks = property(lambda s: _agen(list(blocks_list)))
        bc.get_blocks = MagicMock(return_value=_agen([]))
        return bc

    def _mk_mock_bc_class(self, existing_bc, test_block_returns=True):
        """Create a Mock Blockchain class whose constructor returns existing_bc
        and whose test_block staticmethod is async."""
        MockBC = MagicMock()
        MockBC.return_value = existing_bc
        if isinstance(test_block_returns, list):
            MockBC.test_block = AsyncMock(side_effect=test_block_returns)
        else:
            MockBC.test_block = AsyncMock(return_value=test_block_returns)
        return MockBC

    async def test_regnet_breaks_loop(self):
        self.consensus.config.network = "regnet"
        # Use async-style init_blocks so final_block has .index attribute.
        bc = self._mk_blockchain([_mk_block()], init_blocks_is_list=False)
        existing_bc = MagicMock()
        existing_bc.test_inbound_blockchain = AsyncMock(return_value=False)
        MockBC = self._mk_mock_bc_class(existing_bc)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(index=2)),
        ), patch("yadacoin.core.consensus.Blockchain", new=MockBC):
            await self.consensus.integrate_blocks_with_existing_chain(bc, MagicMock())

    async def test_test_block_fails_with_good_blocks(self):
        bc = self._mk_blockchain([_mk_block(index=1), _mk_block(index=2)])
        bc.get_blocks = MagicMock(return_value=_agen([_mk_block(index=1)]))
        # The Blockchain mock will be returned for both `Blockchain(good_blocks)`
        # and the existing_blockchain. Configure the mock to satisfy both uses.
        existing_bc = MagicMock()
        existing_bc.init_blocks = [_mk_block(index=1)]
        existing_bc.first_block = SimpleNamespace(index=1, hash="h1")
        existing_bc.final_block = SimpleNamespace(index=2, hash="h2")
        existing_bc.test_inbound_blockchain = AsyncMock(return_value=True)
        type(existing_bc).blocks = property(lambda s: _agen([_mk_block(index=1)]))
        MockBC = self._mk_mock_bc_class(existing_bc, test_block_returns=False)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block()),
        ), patch("yadacoin.core.consensus.Blockchain", new=MockBC):
            self.consensus.insert_block = AsyncMock()
            await self.consensus.integrate_blocks_with_existing_chain(bc, MagicMock())

    async def test_test_block_fails_no_good_blocks_returns(self):
        bc = self._mk_blockchain([_mk_block(index=1)])
        bc.get_blocks = MagicMock(return_value=_agen([]))
        MockBC = self._mk_mock_bc_class(MagicMock(), test_block_returns=False)
        with patch("yadacoin.core.consensus.Blockchain", new=MockBC):
            await self.consensus.integrate_blocks_with_existing_chain(bc, MagicMock())

    async def test_test_inbound_fails_with_stream(self):
        bc = self._mk_blockchain([_mk_block(index=1)], init_blocks_is_list=False)
        existing_bc = MagicMock()
        existing_bc.test_inbound_blockchain = AsyncMock(return_value=False)
        stream = MagicMock()
        MockBC = self._mk_mock_bc_class(existing_bc, test_block_returns=True)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(index=2)),
        ), patch("yadacoin.core.consensus.Blockchain", new=MockBC):
            await self.consensus.integrate_blocks_with_existing_chain(bc, stream)
        self.consensus.config.nodeShared.write_params.assert_awaited()

    async def test_test_inbound_fails_with_stream_list_path(self):
        """Line 515: init_blocks is list -> final_block = blockchain.final_block."""
        bc = self._mk_blockchain([_mk_block(index=1)], init_blocks_is_list=True)
        existing_bc = MagicMock()
        existing_bc.init_blocks = [_mk_block(index=1)]
        existing_bc.first_block = SimpleNamespace(index=1, hash="h1")
        existing_bc.final_block = SimpleNamespace(index=2, hash="h2")
        existing_bc.test_inbound_blockchain = AsyncMock(return_value=False)
        type(existing_bc).blocks = property(lambda s: _agen([_mk_block(index=1)]))
        stream = MagicMock()
        MockBC = self._mk_mock_bc_class(existing_bc, test_block_returns=True)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(index=1)),
        ), patch("yadacoin.core.consensus.Blockchain", new=MockBC):
            await self.consensus.integrate_blocks_with_existing_chain(bc, stream)
        self.consensus.config.nodeShared.write_params.assert_awaited()

    async def test_test_inbound_fails_no_stream_async_final(self):
        bc = self._mk_blockchain([_mk_block(index=1)], init_blocks_is_list=False)
        existing_bc = MagicMock()
        existing_bc.test_inbound_blockchain = AsyncMock(return_value=False)
        MockBC = self._mk_mock_bc_class(existing_bc, test_block_returns=True)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(index=2)),
        ), patch("yadacoin.core.consensus.Blockchain", new=MockBC):
            await self.consensus.integrate_blocks_with_existing_chain(bc, None)

    async def test_mainnet_test_block_returns(self):
        """In mainnet, test_block False on second pass returns."""
        bc = self._mk_blockchain([_mk_block(index=1)])
        existing_bc = MagicMock()
        existing_bc.test_inbound_blockchain = AsyncMock(return_value=True)
        MockBC = self._mk_mock_bc_class(existing_bc, test_block_returns=[True, False])
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block()),
        ), patch("yadacoin.core.consensus.Blockchain", new=MockBC):
            self.consensus.insert_block = AsyncMock()
            await self.consensus.integrate_blocks_with_existing_chain(bc, None)
        self.consensus.insert_block.assert_not_called()

    async def test_full_path_inserts_blocks_with_stream(self):
        bc = self._mk_blockchain([_mk_block(index=1)])
        existing_bc = MagicMock()
        existing_bc.test_inbound_blockchain = AsyncMock(return_value=True)
        stream = MagicMock()
        MockBC = self._mk_mock_bc_class(existing_bc, test_block_returns=True)
        with patch(
            "yadacoin.core.consensus.Block.from_dict",
            new=AsyncMock(return_value=_mk_block()),
        ), patch("yadacoin.core.consensus.Blockchain", new=MockBC):
            self.consensus.insert_block = AsyncMock()
            await self.consensus.integrate_blocks_with_existing_chain(bc, stream)
        self.consensus.insert_block.assert_awaited()
        self.assertFalse(stream.syncing)


# ---------------------------------------------------------------------------
# insert_block (lines 536-573)
# ---------------------------------------------------------------------------


class TestInsertBlock(ConsensusBase):
    async def test_insert_no_mp(self):
        block = _mk_block()
        self.consensus.config.mp = None
        r = await self.consensus.insert_block(block, MagicMock())
        self.assertTrue(r)

    async def test_insert_with_mp_syncing_true(self):
        block = _mk_block()
        self.consensus.config.mp = MagicMock()
        self.consensus.config.mp.refresh = AsyncMock()
        self.consensus.syncing = True
        stream = MagicMock()
        stream.syncing = False
        r = await self.consensus.insert_block(block, stream)
        self.assertTrue(r)
        self.consensus.config.mp.refresh.assert_not_called()

    async def test_insert_with_mp_stream_syncing(self):
        block = _mk_block()
        self.consensus.config.mp = MagicMock()
        self.consensus.config.mp.refresh = AsyncMock()
        self.consensus.syncing = False
        stream = MagicMock()
        stream.syncing = True
        r = await self.consensus.insert_block(block, stream)
        self.assertTrue(r)

    async def test_insert_with_mp_full_path(self):
        block = _mk_block()
        self.consensus.config.mp = MagicMock()
        self.consensus.config.mp.refresh = AsyncMock()
        self.consensus.syncing = False
        stream = MagicMock()
        stream.syncing = False
        with patch(
            "yadacoin.core.consensus.StratumServer.block_checker",
            new=AsyncMock(),
        ):
            r = await self.consensus.insert_block(block, stream)
        self.assertTrue(r)
        self.consensus.config.mp.refresh.assert_awaited()

    async def test_insert_with_mp_refresh_raises(self):
        block = _mk_block()
        self.consensus.config.mp = MagicMock()
        self.consensus.config.mp.refresh = AsyncMock(side_effect=Exception("boom"))
        self.consensus.syncing = False
        stream = MagicMock()
        stream.syncing = False
        with patch(
            "yadacoin.core.consensus.StratumServer.block_checker",
            new=AsyncMock(side_effect=Exception("boom2")),
        ):
            r = await self.consensus.insert_block(block, stream)
        self.assertTrue(r)

    async def test_insert_outer_exception(self):
        block = _mk_block()
        self.consensus.mongo.async_db.blocks.delete_many = AsyncMock(
            side_effect=Exception("db")
        )
        await self.consensus.insert_block(block, MagicMock())

    async def test_insert_block_at_content_takedown_fork_calls_apply(self):
        """consensus.py line 555: block.index >= CONTENT_TAKEDOWN_FORK triggers _apply_content_takedowns."""
        from yadacoin.core.chain import CHAIN

        block = _mk_block(index=CHAIN.CONTENT_TAKEDOWN_FORK)
        self.consensus.config.mp = None
        self.consensus.config.content_takedown_auto_comply = frozenset()
        self.consensus.config.content_takedown_comply_and_save = frozenset()
        r = await self.consensus.insert_block(block, MagicMock())
        self.assertTrue(r)


# ---------------------------------------------------------------------------
# _apply_content_takedowns branch coverage
# ---------------------------------------------------------------------------


def _mk_takedown_txn(target_txn_id, reason_code_value="csam", sig="takedown_sig"):
    """Return a mock transaction with a ContentTakedownAnnouncement relationship."""
    from yadacoin.core.contenttakedown import ContentTakedownAnnouncement

    ann = ContentTakedownAnnouncement(
        transaction_id=target_txn_id, reason_code=reason_code_value
    )
    txn = MagicMock()
    txn.relationship = ann
    txn.transaction_signature = sig
    return txn


def _mk_plain_txn():
    """Return a mock transaction with a non-takedown relationship."""
    txn = MagicMock()
    txn.relationship = "plain relationship string"
    txn.transaction_signature = "plain_sig"
    return txn


class TestApplyContentTakedowns(ConsensusBase):
    """Branch coverage for Consensus._apply_content_takedowns."""

    def _setup_db(self, find_one_return=None, update_many_modified=1):
        """Configure the DB mocks needed for takedown tests."""
        result = MagicMock()
        result.modified_count = update_many_modified

        self.consensus.mongo.async_db.blocks.find_one = AsyncMock(
            return_value=find_one_return
        )
        self.consensus.mongo.async_db.blocks.update_many = AsyncMock(
            return_value=result
        )
        self.consensus.mongo.async_db.content_takedown_archive = MagicMock()
        self.consensus.mongo.async_db.content_takedown_archive.insert_one = AsyncMock()

    async def test_non_takedown_transactions_skipped(self):
        """Block with only plain transactions → no DB writes."""
        self._setup_db()
        block = _mk_block(transactions=[_mk_plain_txn()])
        await self.consensus._apply_content_takedowns(block)
        self.consensus.mongo.async_db.blocks.update_many.assert_not_called()

    async def test_auto_comply_clears_relationship(self):
        """reason_code in auto_comply → update_many called, no archive insert."""
        self._setup_db()
        self.consensus.config.content_takedown_auto_comply = frozenset(["csam"])
        self.consensus.config.content_takedown_comply_and_save = frozenset()

        block = _mk_block(transactions=[_mk_takedown_txn("target_txn_001", "csam")])
        await self.consensus._apply_content_takedowns(block)

        self.consensus.mongo.async_db.blocks.update_many.assert_awaited_once()
        self.consensus.mongo.async_db.content_takedown_archive.insert_one.assert_not_called()

    async def test_no_comply_skips_update(self):
        """reason_code not in either policy set → no DB writes."""
        self._setup_db()
        self.consensus.config.content_takedown_auto_comply = frozenset()
        self.consensus.config.content_takedown_comply_and_save = frozenset()

        block = _mk_block(transactions=[_mk_takedown_txn("target_txn_002", "csam")])
        await self.consensus._apply_content_takedowns(block)

        self.consensus.mongo.async_db.blocks.update_many.assert_not_called()
        self.consensus.mongo.async_db.content_takedown_archive.insert_one.assert_not_called()

    async def test_comply_and_save_archives_and_clears(self):
        """reason_code in comply_and_save → archive insert AND update_many called."""
        target_block_doc = {
            "index": 10,
            "transactions": [
                {
                    "id": "target_txn_003",
                    "relationship": {"some": "data"},
                }
            ],
        }
        self._setup_db(find_one_return=target_block_doc)
        self.consensus.config.content_takedown_auto_comply = frozenset()
        self.consensus.config.content_takedown_comply_and_save = frozenset(
            ["copyright"]
        )

        block = _mk_block(
            index=50,
            transactions=[
                _mk_takedown_txn("target_txn_003", "copyright", sig="td_sig")
            ],
        )
        await self.consensus._apply_content_takedowns(block)

        self.consensus.mongo.async_db.content_takedown_archive.insert_one.assert_awaited_once()
        self.consensus.mongo.async_db.blocks.update_many.assert_awaited_once()

    async def test_comply_and_save_target_not_found_still_clears(self):
        """comply_and_save but target block not found → no archive, update_many still runs."""
        self._setup_db(find_one_return=None)
        self.consensus.config.content_takedown_auto_comply = frozenset()
        self.consensus.config.content_takedown_comply_and_save = frozenset(["spam"])

        block = _mk_block(transactions=[_mk_takedown_txn("target_txn_004", "spam")])
        await self.consensus._apply_content_takedowns(block)

        self.consensus.mongo.async_db.content_takedown_archive.insert_one.assert_not_called()
        self.consensus.mongo.async_db.blocks.update_many.assert_awaited_once()

    async def test_comply_and_save_txn_not_in_block_still_clears(self):
        """comply_and_save: target block found but transaction id does not match → no archive."""
        target_block_doc = {
            "index": 10,
            "transactions": [
                {
                    "id": "different_txn_id",
                    "relationship": {"some": "data"},
                }
            ],
        }
        self._setup_db(find_one_return=target_block_doc)
        self.consensus.config.content_takedown_auto_comply = frozenset()
        self.consensus.config.content_takedown_comply_and_save = frozenset(["spam"])

        block = _mk_block(transactions=[_mk_takedown_txn("target_txn_005", "spam")])
        await self.consensus._apply_content_takedowns(block)

        self.consensus.mongo.async_db.content_takedown_archive.insert_one.assert_not_called()
        self.consensus.mongo.async_db.blocks.update_many.assert_awaited_once()

    async def test_multiple_transactions_mixed(self):
        """Plain + takedown transactions in same block: only takedown triggers update."""
        self._setup_db()
        self.consensus.config.content_takedown_auto_comply = frozenset(["csam"])
        self.consensus.config.content_takedown_comply_and_save = frozenset()

        block = _mk_block(
            transactions=[
                _mk_plain_txn(),
                _mk_takedown_txn("target_txn_006", "csam"),
                _mk_plain_txn(),
            ]
        )
        await self.consensus._apply_content_takedowns(block)

        self.assertEqual(
            self.consensus.mongo.async_db.blocks.update_many.await_count, 1
        )

    async def test_no_comply_explicit_skips_update(self):
        """reason_code in no_comply → continue branch (line 609): no DB writes."""
        self._setup_db()
        self.consensus.config.content_takedown_auto_comply = frozenset(["csam"])
        self.consensus.config.content_takedown_comply_and_save = frozenset()
        self.consensus.config.content_takedown_no_comply = frozenset(["csam"])

        block = _mk_block(transactions=[_mk_takedown_txn("target_txn_007", "csam")])
        await self.consensus._apply_content_takedowns(block)

        self.consensus.mongo.async_db.blocks.update_many.assert_not_called()
