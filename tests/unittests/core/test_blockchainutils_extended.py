"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from logging import getLogger
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.blockchainutils import BU, BlockChainUtils, set_BU
from yadacoin.core.config import Config

from ..test_setup import AsyncTestCase


class BUTestCase(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        config = Config()
        if not hasattr(config, "app_log"):
            config.app_log = getLogger("tornado.application")
        self.config = config
        self.bu = BlockChainUtils()


# ---------------------------------------------------------------------------
# Module-level BU() / set_BU()
# ---------------------------------------------------------------------------


class TestBUGlobals(unittest.TestCase):
    def test_bu_returns_none_initially(self):
        import yadacoin.core.blockchainutils as bcu_module

        original = bcu_module.GLOBAL_BU
        bcu_module.GLOBAL_BU = None
        self.assertIsNone(BU())
        bcu_module.GLOBAL_BU = original

    def test_set_bu_changes_global(self):
        import yadacoin.core.blockchainutils as bcu_module

        original = bcu_module.GLOBAL_BU
        mock = MagicMock()
        set_BU(mock)
        self.assertIs(BU(), mock)
        bcu_module.GLOBAL_BU = original


# ---------------------------------------------------------------------------
# BlockChainUtils.__init__ and helpers
# ---------------------------------------------------------------------------


class TestBlockChainUtilsInit(BUTestCase):
    async def test_init_sets_config(self):
        self.assertIsInstance(self.bu, BlockChainUtils)
        self.assertIsNotNone(self.bu.config)

    async def test_invalidate_latest_block(self):
        self.bu.latest_block = {"index": 5}
        self.bu.invalidate_latest_block()
        self.assertIsNone(self.bu.latest_block)

    async def test_set_latest_block(self):
        block_dict = {"index": 10, "hash": "abc"}
        self.bu.set_latest_block(block_dict)
        self.assertEqual(self.bu.latest_block, block_dict)


# ---------------------------------------------------------------------------
# get_latest_block (caching behaviour)
# ---------------------------------------------------------------------------


class TestGetLatestBlock(BUTestCase):
    async def test_returns_cached_block_when_set(self):
        cached = {"index": 99, "hash": "cached_hash"}
        self.bu.latest_block = cached
        result = await self.bu.get_latest_block()
        self.assertEqual(result, cached)

    async def test_queries_db_when_cache_is_none(self):
        self.bu.latest_block = None
        mock_db = MagicMock()
        mock_db.blocks.find_one = AsyncMock(
            return_value={"index": 1, "hash": "db_hash"}
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_latest_block()
        self.assertEqual(result["index"], 1)
        mock_db.blocks.find_one.assert_called_once()

    async def test_caches_result_after_db_query(self):
        self.bu.latest_block = None
        mock_db = MagicMock()
        mock_db.blocks.find_one = AsyncMock(return_value={"index": 1, "hash": "x"})
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            await self.bu.get_latest_block()
        self.assertEqual(self.bu.latest_block["index"], 1)


class TestGetLatestBlockAsync(BUTestCase):
    async def test_uses_cache(self):
        cached = {"index": 5}
        self.bu.latest_block = cached
        result = await self.bu.get_latest_block_async()
        self.assertEqual(result, cached)

    async def test_bypasses_cache_with_use_cache_false(self):
        self.bu.latest_block = {"index": 5}
        mock_db = MagicMock()
        mock_db.blocks.find_one = AsyncMock(return_value={"index": 10})
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_latest_block_async(use_cache=False)
        self.assertEqual(result["index"], 10)


# ---------------------------------------------------------------------------
# get_blocks_async
# ---------------------------------------------------------------------------


class TestGetBlocksAsync(BUTestCase):
    async def test_returns_sorted_ascending(self):
        mock_cursor = MagicMock()
        mock_db = MagicMock()
        mock_db.blocks.find.return_value.sort.return_value = mock_cursor
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_blocks_async(reverse=False)
        self.assertIs(result, mock_cursor)

    async def test_returns_sorted_descending(self):
        mock_cursor = MagicMock()
        mock_db = MagicMock()
        mock_db.blocks.find.return_value.sort.return_value = mock_cursor
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_blocks_async(reverse=True)
        self.assertIs(result, mock_cursor)


# ---------------------------------------------------------------------------
# get_block_by_index
# ---------------------------------------------------------------------------


class TestGetBlockByIndex(BUTestCase):
    async def test_returns_block(self):
        mock_db = MagicMock()
        mock_db.blocks.find_one = AsyncMock(return_value={"index": 5})
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_block_by_index(5)
        self.assertEqual(result["index"], 5)

    async def test_returns_none_when_not_found(self):
        mock_db = MagicMock()
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_block_by_index(999)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# get_transaction_by_id
# ---------------------------------------------------------------------------


class TestGetTransactionById(BUTestCase):
    async def test_returns_txn_dict_when_found_in_blocks(self):
        txn = {"id": "sig1", "hash": "abc"}
        block = {"index": 1, "transactions": [txn]}

        async def find_iter(*args, **kwargs):
            yield block

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: find_iter()
        mock_db.blocks.find.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_transaction_by_id("sig1")
        self.assertEqual(result["id"], "sig1")

    async def test_returns_instance_when_instance_true(self):
        from yadacoin.core.transaction import Transaction

        txn = {
            "id": "sig1",
            "time": 1000,
            "rid": "",
            "relationship": "",
            "public_key": self.config.public_key,
            "dh_public_key": None,
            "fee": 0.0,
            "inputs": [],
            "outputs": [],
        }
        block = {"index": 1, "transactions": [txn]}

        async def find_iter(*args, **kwargs):
            yield block

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: find_iter()
        mock_db.blocks.find.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_transaction_by_id("sig1", instance=True)
        self.assertIsInstance(result, Transaction)

    async def test_returns_none_when_not_found(self):
        async def empty_iter(*args, **kwargs):
            return
            yield

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.find.return_value = mock_cursor
        mock_db.unspent_cache.delete_many = AsyncMock()

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_transaction_by_id("missing_id")
        self.assertIsNone(result)

    async def test_returns_block_when_give_block_true(self):
        txn = {"id": "sig1"}
        block_doc = {"index": 1, "transactions": [txn]}

        async def find_iter(*args, **kwargs):
            yield block_doc

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: find_iter()
        mock_db.blocks.find.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_transaction_by_id("sig1", give_block=True)
        self.assertEqual(result["index"], 1)

    async def test_checks_mempool_when_inc_mempool_true(self):
        async def empty_iter(*args, **kwargs):
            return
            yield

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.find.return_value = mock_cursor
        mock_db.miner_transactions.find_one = AsyncMock(return_value={"id": "m1"})

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_transaction_by_id("m1", inc_mempool=True)
        self.assertEqual(result["id"], "m1")


# ---------------------------------------------------------------------------
# is_input_spent
# ---------------------------------------------------------------------------


class TestIsInputSpent(BUTestCase):
    async def test_returns_true_when_found(self):
        block = {"index": 1, "transactions": {"id": "t1", "public_key": "pk1"}}

        async def agg_iter(*args, **kwargs):
            yield block

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: agg_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent("input_id_1", "pk1")
        self.assertTrue(result)

    async def test_returns_false_when_not_found(self):
        async def empty_iter(*args, **kwargs):
            return
            yield

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent("nonexistent", "pk1")
        self.assertFalse(result)

    async def test_accepts_list_of_input_ids(self):
        async def empty_iter(*args, **kwargs):
            return
            yield

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent(["id1", "id2"], "pk1")
        self.assertFalse(result)

    async def test_checks_mempool_when_inc_mempool_true(self):
        async def empty_iter(*args, **kwargs):
            return
            yield

        async def mp_iter():
            yield {"id": "m1", "public_key": "pk1"}

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor
        mp_cursor = MagicMock()
        mp_cursor.__aiter__ = lambda self: mp_iter()
        mock_db.miner_transactions.find.return_value = mp_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent("m1", "pk1", inc_mempool=True)
        self.assertTrue(result)

    async def test_with_from_index_adds_match_stage(self):
        """Covers lines 796-797: from_index branch in is_input_spent."""

        async def empty_iter(*args, **kwargs):
            return
            yield

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent("input_id", "pk1", from_index=5)
        self.assertFalse(result)
        # Verify that aggregate was called with a query starting with $match on index
        call_args = mock_db.blocks.aggregate.call_args[0][0]
        self.assertEqual(call_args[0], {"$match": {"index": {"$lt": 5}}})

    async def test_with_extra_blocks_matching(self):
        """extra_blocks: spend found on fork chain is spent."""
        input_id = "test_input_id"

        class FakeInput:
            def __init__(self, id):
                self.id = id

        class FakeTxn:
            def __init__(self, inputs, public_key="pk1"):
                self.inputs = [FakeInput(i) for i in inputs]
                self.public_key = public_key

        class FakeBlock:
            def __init__(self, index, input_ids, public_key="pk1"):
                self.index = index
                self.transactions = [FakeTxn(input_ids, public_key=public_key)]

        async def empty_iter(*args, **kwargs):
            return
            yield

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        # Spend lives only on the fork (not in mongo).
        extra_blocks = [FakeBlock(10, [input_id], public_key="pk1")]

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent(
                input_id, "pk1", from_index=11, extra_blocks=extra_blocks
            )
        self.assertTrue(result)

    async def test_extra_blocks_spend_at_different_height(self):
        """Fork spent the input at height 10; validating height 12 still sees it."""
        input_id = "test_input_id"

        class FakeInput:
            def __init__(self, id):
                self.id = id

        class FakeTxn:
            def __init__(self, inputs, public_key="pk1"):
                self.inputs = [FakeInput(i) for i in inputs]
                self.public_key = public_key

        class FakeBlock:
            def __init__(self, index, input_ids=None, public_key="pk1"):
                self.index = index
                self.transactions = (
                    [FakeTxn(input_ids, public_key=public_key)] if input_ids else []
                )

        async def empty_iter(*args, **kwargs):
            return
            yield

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        extra_blocks = [
            FakeBlock(10, [input_id], public_key="pk1"),
            FakeBlock(11),
            FakeBlock(12),
        ]

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent(
                input_id, "pk1", from_index=12, extra_blocks=extra_blocks
            )
        self.assertTrue(result)

    async def test_with_extra_blocks_different_pubkey_not_spent(self):
        """extra_blocks: same input_id by a different non-KEL key is not spent."""
        input_id = "test_input_id"

        class FakeInput:
            def __init__(self, id):
                self.id = id

        class FakeTxn:
            def __init__(self, inputs, public_key):
                self.inputs = [FakeInput(i) for i in inputs]
                self.public_key = public_key

        class FakeBlock:
            def __init__(self, index, input_ids, public_key):
                self.index = index
                self.transactions = [FakeTxn(input_ids, public_key=public_key)]

        async def empty_iter(*args, **kwargs):
            return
            yield

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        extra_blocks = [FakeBlock(1, [input_id], public_key="bob_pk")]

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.kel_spend_conflict",
                new=AsyncMock(return_value=False),
            ):
                result = await self.bu.is_input_spent(
                    input_id, "alice_pk", from_index=2, extra_blocks=extra_blocks
                )
        self.assertFalse(result)

    async def test_mongo_spend_ignored_when_height_on_fork(self):
        """Mongo spend at a height covered by extra_blocks does not count."""
        block_doc = {
            "index": 10,
            "transactions": {
                "id": "t1",
                "public_key": "pk1",
                "inputs": [{"id": "any_id"}],
            },
        }

        async def agg_iter(*args, **kwargs):
            yield block_doc

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: agg_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        class FakeBlock:
            def __init__(self, index):
                self.index = index
                self.transactions = []

        # Fork replaces height 10 with a block that does not spend the input.
        extra_blocks = [FakeBlock(10)]

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent(
                "any_id", "pk1", from_index=11, extra_blocks=extra_blocks
            )
        self.assertFalse(result)

    async def test_mongo_spend_outside_fork_still_counts(self):
        """Mongo spend below the fork tip still counts when height is not on fork."""
        block_doc = {
            "index": 5,
            "transactions": {
                "id": "t1",
                "public_key": "pk1",
                "inputs": [{"id": "any_id"}],
            },
        }

        async def agg_iter(*args, **kwargs):
            yield block_doc

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: agg_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        class FakeBlock:
            def __init__(self, index):
                self.index = index
                self.transactions = []

        extra_blocks = [FakeBlock(10), FakeBlock(11)]

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent(
                "any_id", "pk1", from_index=11, extra_blocks=extra_blocks
            )
        self.assertTrue(result)

    async def test_same_kel_spender_counts_as_spent(self):
        """A prior KEL key spending the input is spent for the tip key."""
        block = {
            "index": 1,
            "transactions": {
                "id": "t1",
                "public_key": "aa" * 33,
                "inputs": [{"id": "input_id"}],
            },
        }

        async def agg_iter(*args, **kwargs):
            yield block

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: agg_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.kel_spend_conflict",
                new=AsyncMock(return_value=True),
            ):
                result = await self.bu.is_input_spent("input_id", "bb" * 33)
        self.assertTrue(result)

    async def test_different_kel_spender_not_spent(self):
        """A different wallet spending the same parent input is not a double-spend."""
        block = {
            "index": 1,
            "transactions": {
                "id": "t1",
                "public_key": "aa" * 33,
                "inputs": [{"id": "input_id"}],
            },
        }

        async def agg_iter(*args, **kwargs):
            yield block

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: agg_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.kel_spend_conflict",
                new=AsyncMock(return_value=False),
            ):
                result = await self.bu.is_input_spent("input_id", "bb" * 33)
        self.assertFalse(result)

    async def test_same_inception_tag_counts_as_spent_without_onchain_kel(self):
        """Prior spend + tip spend sharing tags is spent when on-chain resolve fails."""
        block = {
            "index": 1,
            "transactions": {
                "id": "t1",
                "public_key": "aa" * 33,
                "inception_public_key_hash": "pool_inc",
                "inputs": [{"id": "coinbase_id"}],
            },
        }

        async def agg_iter(*args, **kwargs):
            yield block

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: agg_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(return_value=None),
            ):
                result = await self.bu.is_input_spent(
                    "coinbase_id",
                    "bb" * 33,
                    spender_inception="pool_inc",
                )
        self.assertTrue(result)

    async def test_different_inception_tag_not_spent(self):
        """Different inception tags on spenders of same parent input is not a conflict."""
        block = {
            "index": 1,
            "transactions": {
                "id": "t1",
                "public_key": "aa" * 33,
                "inception_public_key_hash": "kel_a",
                "inputs": [{"id": "parent_id"}],
            },
        }

        async def agg_iter(*args, **kwargs):
            yield block

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: agg_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(return_value=None),
            ):
                result = await self.bu.is_input_spent(
                    "parent_id",
                    "bb" * 33,
                    spender_inception="kel_b",
                )
        self.assertFalse(result)

    async def test_query_matches_input_id_only(self):
        """Aggregate pipeline no longer filters by public_key (KEL dual-path)."""

        async def empty_iter(*args, **kwargs):
            return
            yield

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            await self.bu.is_input_spent("input_id", "pk1")
        call_pipeline = mock_db.blocks.aggregate.call_args[0][0]
        first_match = call_pipeline[0]["$match"]
        self.assertIn("transactions", first_match)
        elem_match = first_match["transactions"]["$elemMatch"]
        self.assertEqual(elem_match, {"inputs.id": {"$in": ["input_id"]}})
        self.assertNotIn("public_key", elem_match)


# ---------------------------------------------------------------------------
# get_mempool_transactions
# ---------------------------------------------------------------------------


class TestGetMempoolTransactions(BUTestCase):
    async def test_returns_found_transaction(self):
        async def mp_iter():
            yield {"id": "txn1", "public_key": "pk1"}

        mock_db = MagicMock()
        mp_cursor = MagicMock()
        mp_cursor.__aiter__ = lambda self: mp_iter()
        mock_db.miner_transactions.find.return_value = mp_cursor
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_mempool_transactions("pk1", ["inp1"])
        self.assertEqual(result["id"], "txn1")

    async def test_returns_none_when_not_found(self):
        async def mp_iter():
            if False:
                yield None

        mock_db = MagicMock()
        mp_cursor = MagicMock()
        mp_cursor.__aiter__ = lambda self: mp_iter()
        mock_db.miner_transactions.find.return_value = mp_cursor
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_mempool_transactions("pk1", ["inp1"])
        self.assertIsNone(result)

    async def test_same_kel_mempool_match(self):
        """Mempool spend by a same-KEL key counts as spent."""

        async def mp_iter():
            yield {"id": "txn1", "public_key": "aa" * 33}

        mock_db = MagicMock()
        mp_cursor = MagicMock()
        mp_cursor.__aiter__ = lambda self: mp_iter()
        mock_db.miner_transactions.find.return_value = mp_cursor
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.kel_spend_conflict",
                new=AsyncMock(return_value=True),
            ):
                result = await self.bu.get_mempool_transactions("bb" * 33, ["inp1"])
        self.assertEqual(result["id"], "txn1")

    async def test_mempool_same_inception_tag_match(self):
        async def mp_iter():
            yield {
                "id": "txn1",
                "public_key": "aa" * 33,
                "inception_public_key_hash": "pool_inc",
            }

        mock_db = MagicMock()
        mp_cursor = MagicMock()
        mp_cursor.__aiter__ = lambda self: mp_iter()
        mock_db.miner_transactions.find.return_value = mp_cursor
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(return_value=None),
            ):
                result = await self.bu.get_mempool_transactions(
                    "bb" * 33, ["inp1"], spender_inception="pool_inc"
                )
        self.assertEqual(result["id"], "txn1")


# ---------------------------------------------------------------------------
# get_mempool_spent_inputs
# ---------------------------------------------------------------------------


class TestGetMempoolSpentInputs(BUTestCase):
    async def test_returns_spent_inputs(self):
        mock_db = MagicMock()
        mock_db.miner_transactions.aggregate.return_value.to_list = AsyncMock(
            return_value=[{"spent_inputs": ["inp1", "inp2"]}]
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_mempool_spent_inputs("pk1")
        self.assertEqual(sorted(result), ["inp1", "inp2"])

    async def test_returns_empty_when_no_transactions(self):
        mock_db = MagicMock()
        mock_db.miner_transactions.aggregate.return_value.to_list = AsyncMock(
            return_value=[]
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_mempool_spent_inputs("pk1")
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# get_chain_spent_inputs
# ---------------------------------------------------------------------------


class TestGetChainSpentInputs(BUTestCase):
    async def test_returns_inputs_from_single_batch(self):
        async def gen():
            for x in [{"id": "inp1"}, {"id": "inp2"}]:
                yield x

        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value = gen()
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_chain_spent_inputs("pk1")
        self.assertIn("inp1", result)
        self.assertIn("inp2", result)
        mock_db.blocks.aggregate.assert_called_once()

    async def test_returns_empty_when_no_results(self):
        async def gen():
            if False:
                yield {}

        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value = gen()
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_chain_spent_inputs("pk1")
        self.assertEqual(result, set())

    async def test_returns_empty_when_no_public_key(self):
        result = await self.bu.get_chain_spent_inputs(None)
        self.assertEqual(result, set())


# ---------------------------------------------------------------------------
# floor_to_two_decimal_places
# ---------------------------------------------------------------------------


class TestFloorToTwoDecimalPlaces(unittest.TestCase):
    def test_rounds_down(self):
        bu = BlockChainUtils.__new__(BlockChainUtils)
        self.assertAlmostEqual(bu.floor_to_two_decimal_places(3.456), 3.45)

    def test_exact_value(self):
        bu = BlockChainUtils.__new__(BlockChainUtils)
        self.assertAlmostEqual(bu.floor_to_two_decimal_places(3.50), 3.50)

    def test_zero(self):
        bu = BlockChainUtils.__new__(BlockChainUtils)
        self.assertAlmostEqual(bu.floor_to_two_decimal_places(0.0), 0.0)


# ---------------------------------------------------------------------------
# NodeKeyRotationManager._sign
# ---------------------------------------------------------------------------


class TestGenerateSignature(BUTestCase):
    async def test_returns_base64_string(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        sig = NodeKeyRotationManager._sign(self.config.private_key, "test message")
        import base64

        decoded = base64.b64decode(sig)
        self.assertGreater(len(decoded), 0)


# ---------------------------------------------------------------------------
# get_hash_rate
# ---------------------------------------------------------------------------


class TestGetHashRate(BUTestCase):
    async def test_single_block_returns_zero(self):
        block = MagicMock()
        block.target = 2**208
        block.time = "1000"
        result = self.bu.get_hash_rate([block])
        self.assertEqual(result, 0)

    async def test_multiple_blocks_returns_integer(self):
        b1 = MagicMock()
        b1.target = 2**208
        b1.time = "2000"
        b2 = MagicMock()
        b2.target = 2**207
        b2.time = "1000"
        result = self.bu.get_hash_rate([b1, b2])
        self.assertIsInstance(result, int)


# ---------------------------------------------------------------------------
# get_total_received_balance / get_spent_balance (mocked aggregation)
# ---------------------------------------------------------------------------


class TestBalanceMethods(BUTestCase):
    async def _make_mock_db_with_aggregate_result(self, result_value):
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(
            return_value=[{"totalReceived": result_value}]
        )
        mock_db.reversed_public_keys.find_one = AsyncMock(
            return_value={"public_key": self.config.public_key}
        )
        return mock_db

    async def test_get_total_received_balance_returns_value(self):
        mock_db = await self._make_mock_db_with_aggregate_result(10.5)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_total_received_balance(self.config.address)
        self.assertAlmostEqual(result, 10.5)

    async def test_get_total_received_balance_returns_zero_when_empty(self):
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(return_value=[])
        mock_db.reversed_public_keys.find_one = AsyncMock(
            return_value={"public_key": self.config.public_key}
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_total_received_balance(self.config.address)
        self.assertEqual(result, 0.0)

    async def test_get_spent_balance_returns_sum(self):
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(
            return_value=[{"totalSpent": 3.15}]
        )
        mock_db.reversed_public_keys.find_one = AsyncMock(
            return_value={"public_key": self.config.public_key}
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_spent_balance(self.config.address)
        self.assertAlmostEqual(result, 3.15)

    async def test_get_spent_balance_returns_zero_when_empty(self):
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(return_value=[])
        mock_db.reversed_public_keys.find_one = AsyncMock(
            return_value={"public_key": self.config.public_key}
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_spent_balance(self.config.address)
        self.assertEqual(result, 0.0)


# ---------------------------------------------------------------------------
# get_reverse_public_key
# ---------------------------------------------------------------------------


class TestGetReversePublicKey(BUTestCase):
    async def test_returns_cached_public_key(self):
        mock_db = MagicMock()
        mock_db.reversed_public_keys.find_one = AsyncMock(
            return_value={"public_key": self.config.public_key}
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_reverse_public_key(self.config.address)
        self.assertEqual(result, self.config.public_key)

    async def test_returns_none_when_no_pairs(self):
        mock_db = MagicMock()
        mock_db.reversed_public_keys.find_one = AsyncMock(return_value=None)
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(return_value=[])
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_reverse_public_key(self.config.address)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# get_unspent_outputs (zero amount_needed path)
# ---------------------------------------------------------------------------


class TestGetUnspentOutputs(BUTestCase):
    def _patch_unspent_common(self, selectable=None, balance=8.0):
        selectable = selectable or []
        self.bu.get_reverse_public_key = AsyncMock(return_value=self.config.public_key)
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "tip", "index": 10}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=balance)
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=None)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=False)
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=0.0)
        self.bu._select_spendable_utxos = AsyncMock(return_value=(selectable, balance))
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        self.bu.floor_to_two_decimal_places = (
            lambda v: __import__("math").floor(v * 100) / 100
        )

    async def test_zero_amount_needed_returns_balance_only(self):
        selectable = [
            {
                "id": "txn1",
                "outputs": [{"to": self.config.address, "value": 5.0}],
                "time": 100,
            },
            {
                "id": "txn2",
                "outputs": [{"to": self.config.address, "value": 3.0}],
                "time": 200,
            },
        ]
        self._patch_unspent_common(selectable, balance=8.0)
        result = await self.bu.get_unspent_outputs(self.config.address, amount_needed=0)
        self.assertIn("balance", result)
        self.assertEqual(result["unspent_utxos"], [])
        self.assertAlmostEqual(result["balance"], 8.0)

    async def test_with_amount_needed_returns_utxos(self):
        selectable = [
            {
                "id": "txn1",
                "outputs": [{"to": self.config.address, "value": 5.0}],
                "time": 100,
            },
        ]
        self._patch_unspent_common(selectable, balance=5.0)
        result = await self.bu.get_unspent_outputs(
            self.config.address, amount_needed=3.0
        )
        self.assertIn("unspent_utxos", result)
        self.assertEqual(len(result["unspent_utxos"]), 1)

    async def test_unspent_cache_hit(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value=self.config.public_key)
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "tip", "index": 10}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=4.0)
        cache_doc = {
            "address": self.config.address,
            "public_key": self.config.public_key,
            "unspent_utxos": [
                {
                    "id": "txn1",
                    "outputs": [{"to": self.config.address, "value": 4.0}],
                    "time": 1,
                }
            ],
            "balance": 4.0,
            "last_block_hash": "tip",
            "last_block_index": 10,
        }
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=cache_doc)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu._select_spendable_utxos = AsyncMock()
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        result = await self.bu.get_unspent_outputs(self.config.address, amount_needed=0)
        self.assertAlmostEqual(result["balance"], 4.0)
        self.bu._select_spendable_utxos.assert_not_awaited()

    async def test_unspent_cache_incremental(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value=self.config.public_key)
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "newtip", "index": 12}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=8.0)
        cache_doc = {
            "address": self.config.address,
            "public_key": self.config.public_key,
            "unspent_utxos": [
                {
                    "id": "old1",
                    "outputs": [{"to": self.config.address, "value": 5.0}],
                    "time": 1,
                },
                {
                    "id": "spent_later",
                    "outputs": [{"to": self.config.address, "value": 2.0}],
                    "time": 2,
                },
            ],
            "balance": 7.0,
            "last_block_hash": "oldtip",
            "last_block_index": 10,
        }
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=cache_doc)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu._fetch_received_outputs = AsyncMock(
            return_value=[
                {
                    "id": "new1",
                    "outputs": [{"to": self.config.address, "value": 3.0}],
                    "time": 3,
                }
            ]
        )
        self.bu.get_spent_among_candidates = AsyncMock(return_value={"spent_later"})
        self.bu._filter_unspent_outputs = AsyncMock(
            return_value=(
                [
                    {
                        "id": "old1",
                        "outputs": [{"to": self.config.address, "value": 5.0}],
                        "time": 1,
                    },
                    {
                        "id": "new1",
                        "outputs": [{"to": self.config.address, "value": 3.0}],
                        "time": 3,
                    },
                ],
                8.0,
            )
        )
        self.bu._select_spendable_utxos = AsyncMock(return_value=([], 0.0))
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=None)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        # amount_needed > 0 skips the display-only fast path and runs incremental.
        result = await self.bu.get_unspent_outputs(
            self.config.address, amount_needed=1.0
        )
        self.assertAlmostEqual(result["balance"], 8.0)
        # Selection stops once amount_needed is covered (largest first).
        ids = [u["id"] for u in result["unspent_utxos"]]
        self.assertTrue(ids)
        self.assertIn(ids[0], {"old1", "new1"})
        self.bu._save_wallet_unspent_cache.assert_awaited()
        # Also verify max_transferable reflects the full selectable set.
        self.assertAlmostEqual(result["max_transferable_value"], 8.0)


class TestGetUnspentOutputsMempoolOverlay(BUTestCase):
    async def test_mempool_spend_filters_cached_utxo(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value=self.config.public_key)
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "tip", "index": 10}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=7.0)
        cache_doc = {
            "address": self.config.address,
            "public_key": self.config.public_key,
            "unspent_utxos": [
                {
                    "id": "mempool_spent",
                    "outputs": [{"to": self.config.address, "value": 5.0}],
                    "time": 1,
                },
                {
                    "id": "still_good",
                    "outputs": [{"to": self.config.address, "value": 2.0}],
                    "time": 2,
                },
            ],
            "balance": 7.0,
            "last_block_hash": "tip",
            "last_block_index": 10,
        }
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=cache_doc)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=["mempool_spent"])
        result = await self.bu.get_unspent_outputs(
            self.config.address, amount_needed=1.0
        )
        ids = [u["id"] for u in result["unspent_utxos"]]
        self.assertEqual(ids, ["still_good"])
        # Chain balance comes from wallet_balance_cache, not filtered UTXO sum.
        self.assertAlmostEqual(result["balance"], 7.0)
        self.assertAlmostEqual(result.get("max_transferable_value", 2.0), 2.0)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)


class TestIsInputSpentExceptionPaths(BUTestCase):
    async def test_conflicts_invalid_other_pubkey(self):
        block = {
            "index": 1,
            "transactions": {
                "id": "t1",
                "public_key": "not-hex",
                "inputs": [{"id": "input_id"}],
            },
        }

        async def agg_iter(*args, **kwargs):
            yield block

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: agg_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch(
                "yadacoin.core.blockchainutils.P2PKHBitcoinAddress.from_pubkey",
                side_effect=lambda b: type("A", (), {"__str__": lambda s: "addr"})(),
            ):
                # spender ok, other fails decode in conflicts
                result = await self.bu.is_input_spent("input_id", "bb" * 33)
        self.assertFalse(result)

    async def test_mempool_invalid_other_pk(self):
        async def empty_iter(*args, **kwargs):
            return
            yield

        async def mp_iter():
            yield {"id": "m1", "public_key": "zz"}  # invalid hex

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor
        mp_cursor = MagicMock()
        mp_cursor.__aiter__ = lambda self: mp_iter()
        mock_db.miner_transactions.find.return_value = mp_cursor
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch(
                "yadacoin.core.blockchainutils.P2PKHBitcoinAddress.from_pubkey",
                side_effect=[
                    type("A", (), {"__str__": lambda s: "addr"})(),  # spender
                    Exception("bad"),  # other
                ],
            ):
                result = await self.bu.is_input_spent(
                    "input_id", "bb" * 33, inc_mempool=True
                )
        self.assertFalse(result)

    async def test_from_index_in_query(self):
        async def empty_iter(*args, **kwargs):
            return
            yield

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            await self.bu.is_input_spent("input_id", "pk1", from_index=50)
        pipeline = mock_db.blocks.aggregate.call_args[0][0]
        self.assertEqual(pipeline[0], {"$match": {"index": {"$lt": 50}}})


class TestIsInputSpentSpenderNone(BUTestCase):
    async def test_invalid_spender_pubkey(self):
        block = {
            "index": 1,
            "transactions": {
                "public_key": "aa" * 33,
                "inputs": [{"id": "inp"}],
            },
        }

        async def agg():
            yield block

        mock_db = MagicMock()
        cur = MagicMock()
        cur.__aiter__ = lambda s: agg()
        mock_db.blocks.aggregate.return_value = cur
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent("inp", "not-hex-key")
        self.assertFalse(result)

    async def test_mempool_spender_none(self):
        async def empty():
            return
            yield

        async def mp():
            yield {"public_key": "aa" * 33, "id": "x"}

        mock_db = MagicMock()
        cur = MagicMock()
        cur.__aiter__ = lambda s: empty()
        mock_db.blocks.aggregate.return_value = cur
        mp_cur = MagicMock()
        mp_cur.__aiter__ = lambda s: mp()
        mock_db.miner_transactions.find.return_value = mp_cur
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent(
                "inp", "bad-spender", inc_mempool=True
            )
        self.assertFalse(result)

    async def test_mempool_empty_other_pk(self):
        async def empty():
            return
            yield

        async def mp():
            yield {"public_key": "", "id": "x"}
            yield {"public_key": None, "id": "y"}

        mock_db = MagicMock()
        cur = MagicMock()
        cur.__aiter__ = lambda s: empty()
        mock_db.blocks.aggregate.return_value = cur
        mp_cur = MagicMock()
        mp_cur.__aiter__ = lambda s: mp()
        mock_db.miner_transactions.find.return_value = mp_cur
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent("inp", "pk1", inc_mempool=True)
        self.assertFalse(result)


class TestIsInputSpentFinalGaps(BUTestCase):
    async def test_conflicts_empty_other_public_key(self):
        """Line 757: other_public_key falsy → return False."""
        block = {
            "index": 1,
            "transactions": {
                "public_key": None,
                "inputs": [{"id": "inp"}],
            },
        }

        async def agg():
            yield block

        mock_db = MagicMock()
        cur = MagicMock()
        cur.__aiter__ = lambda s: agg()
        mock_db.blocks.aggregate.return_value = cur
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent("inp", "bb" * 33)
        self.assertFalse(result)

    async def test_mempool_other_from_pubkey_exception(self):
        """Lines 848-849: from_pubkey raises on other → continue."""

        async def mp():
            yield {"public_key": "02" + "cd" * 32, "id": "x"}
            # second doc so we continue after exception
            yield {"public_key": "02" + "cd" * 32, "id": "y"}

        mock_db = MagicMock()
        mp_cursor = MagicMock()
        mp_cursor.__aiter__ = lambda s: mp()
        mock_db.miner_transactions.find.return_value = mp_cursor

        n = {"c": 0}

        def from_pub(b):
            n["c"] += 1
            # 1st = spender in get_mempool_transactions; rest = others (raise)
            if n["c"] == 1:
                return type("A", (), {"__str__": lambda s: "spender"})()
            raise ValueError("bad other pubkey")

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch(
                "yadacoin.core.blockchainutils.P2PKHBitcoinAddress.from_pubkey",
                side_effect=from_pub,
            ):
                # Call get_mempool_transactions directly so only one spender resolve
                result = await self.bu.get_mempool_transactions("bb" * 33, ["inp"])
        self.assertIsNone(result)
        self.assertGreaterEqual(n["c"], 2)


# ---------------------------------------------------------------------------
# Coverage pass for wallet cache / UTXO selection / balance edge paths
# ---------------------------------------------------------------------------


class TestWalletCacheAndSelectionCoverage(BUTestCase):
    async def test_async_empty_set(self):
        self.assertEqual(await self.bu._async_empty_set(), set())

    async def test_iter_blocks_aggregate_hint_fallback(self):
        calls = {"n": 0}

        class Cursor:
            def __init__(self, docs):
                self._docs = docs

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self._docs:
                    raise StopAsyncIteration
                return self._docs.pop(0)

        def aggregate(pipeline, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1 and "hint" in kwargs:
                raise Exception("no hint")
            return Cursor([{"_id": 1}])

        mock_db = MagicMock()
        mock_db.blocks.aggregate.side_effect = aggregate
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            docs = []
            async for d in self.bu._iter_blocks_aggregate([{"$match": {}}], hint="h"):
                docs.append(d)
        self.assertEqual(docs, [{"_id": 1}])
        self.assertGreaterEqual(calls["n"], 2)

    async def test_aggregate_blocks_hint_fallback(self):
        class Agg:
            def __init__(self, fail_hint=False):
                self.fail_hint = fail_hint

            def to_list(self, length=None):
                async def _():
                    if self.fail_hint:
                        raise Exception("bad hint")
                    return [{"ok": 1}]

                return _()

        calls = {"n": 0}

        def aggregate(pipeline, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1 and "hint" in kwargs:
                return Agg(fail_hint=True)
            return Agg(fail_hint=False)

        mock_db = MagicMock()
        mock_db.blocks.aggregate.side_effect = aggregate

        # _aggregate_blocks uses to_list on cursor; first call raises via await
        # Make first to_list raise, second succeed
        class C1:
            async def to_list(self, length=None):
                raise Exception("hint fail")

        class C2:
            async def to_list(self, length=None):
                return [{"ok": 1}]

        seq = [C1(), C2()]

        def agg2(pipeline, **kwargs):
            return seq.pop(0)

        mock_db.blocks.aggregate.side_effect = agg2
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu._aggregate_blocks([{"$match": {}}], hint="h")
        self.assertEqual(result, [{"ok": 1}])

    async def test_total_spent_no_public_key(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value=None)
        self.assertEqual(await self.bu.get_total_spent_balance("addr"), 0.0)

    async def test_total_spent_with_from_index(self):
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(
            return_value=[{"totalSpent": 1.5}]
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_total_spent_balance(
                "addr", public_key="pk", from_index=10
            )
        self.assertEqual(result, 1.5)
        pipeline = mock_db.blocks.aggregate.call_args[0][0]
        self.assertEqual(pipeline[0]["$match"]["index"], {"$gt": 10})

    async def test_received_from_others_no_public_key_and_from_index(self):
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(
            return_value=[{"totalReceived": 4.0}]
        )
        self.bu.get_reverse_public_key = AsyncMock(return_value=None)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_received_from_others_balance(
                "addr", public_key=None, from_index=3
            )
        self.assertEqual(result, 4.0)

    async def test_solo_mining_no_public_key_and_from_index(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value=None)
        self.assertEqual(await self.bu.get_received_solo_mining_balance("a"), 0.0)
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(
            return_value=[{"totalReceived": 2.0}]
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_received_solo_mining_balance(
                "addr", public_key="pk", from_index=5
            )
        self.assertEqual(result, 2.0)

    async def test_masternode_coinbase_branches(self):
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(
            return_value=[{"totalReceived": 2.5}]
        )
        self.bu.get_reverse_public_key = AsyncMock(return_value=None)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            r1 = await self.bu.get_masternode_coinbase_balance(
                "addr", public_key="pk", from_index=1
            )
            r2 = await self.bu.get_masternode_coinbase_balance("addr", public_key=None)
        self.assertEqual(r1, 2.5)
        self.assertEqual(r2, 2.5)

    async def test_spent_balance_upper_bound_and_no_pk(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value=None)
        self.assertEqual(await self.bu.get_spent_balance("a", from_index=10), 0.0)
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(
            return_value=[{"totalSpent": 9.0}]
        )
        self.bu.get_reverse_public_key = AsyncMock(return_value="pk")
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_spent_balance("addr", from_index=500)
        self.assertEqual(result, 9.0)
        pipeline = mock_db.blocks.aggregate.call_args[0][0]
        self.assertEqual(pipeline[0]["$match"]["index"], {"$lt": 500})

    async def test_compute_balance_components_resolves_pk(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value="pk")
        self.bu.get_total_spent_balance = AsyncMock(return_value=1.0)
        self.bu.get_received_from_others_balance = AsyncMock(return_value=2.0)
        self.bu.get_received_solo_mining_balance = AsyncMock(return_value=3.0)
        self.bu.get_masternode_coinbase_balance = AsyncMock(return_value=4.0)
        result = await self.bu._compute_balance_components("addr")
        self.assertEqual(result["public_key"], "pk")
        self.assertEqual(result["received_solo_mining"], 7.0)
        self.assertEqual(result["total_spent"], 1.0)

    async def test_chain_marker_validation_branches(self):
        self.assertFalse(await self.bu._chain_marker_is_valid(None))
        self.assertFalse(
            await self.bu._chain_marker_is_valid({"last_block_hash": None})
        )
        mock_db = MagicMock()
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            self.assertFalse(
                await self.bu._chain_marker_is_valid(
                    {"last_block_hash": "h", "last_block_index": 1}
                )
            )

        async def find_one(q, *a, **k):
            if "hash" in q:
                return {"hash": "h", "index": 2}  # index mismatch
            return None

        mock_db.blocks.find_one = AsyncMock(side_effect=find_one)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            self.assertFalse(
                await self.bu._chain_marker_is_valid(
                    {"last_block_hash": "h", "last_block_index": 1},
                    latest_block={"index": 5},
                )
            )

        async def find_one2(q, *a, **k):
            if "hash" in q:
                return {"hash": "h", "index": 1}
            return None

        mock_db.blocks.find_one = AsyncMock(side_effect=find_one2)
        self.bu.get_latest_block_async = AsyncMock(return_value=None)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            self.assertFalse(
                await self.bu._chain_marker_is_valid(
                    {"last_block_hash": "h", "last_block_index": 1}
                )
            )

        self.bu.get_latest_block_async = AsyncMock(
            return_value={"index": 0, "hash": "t"}
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            self.assertFalse(
                await self.bu._chain_marker_is_valid(
                    {"last_block_hash": "h", "last_block_index": 1}
                )
            )

    async def test_invalidate_wallet_balance_cache(self):
        mock_db = MagicMock()
        mock_db.wallet_balance_cache.delete_one = AsyncMock()
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            await self.bu._invalidate_wallet_balance_cache("a", reason="reorg")
        mock_db.wallet_balance_cache.delete_one.assert_awaited()

    async def test_get_cached_max_transferable_value_paths(self):
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "t", "index": 1}
        )
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=None)
        self.assertEqual(await self.bu.get_cached_max_transferable_value("a"), 0.0)

        self.bu._get_wallet_unspent_cache = AsyncMock(return_value={"x": 1})
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=False)
        self.assertEqual(await self.bu.get_cached_max_transferable_value("a"), 0.0)

        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu._get_wallet_unspent_cache = AsyncMock(
            return_value={"max_transferable_value": 12.34}
        )
        self.assertEqual(await self.bu.get_cached_max_transferable_value("a"), 12.34)

        self.bu._get_wallet_unspent_cache = AsyncMock(
            return_value={
                "unspent_utxos": [
                    {"outputs": [{"value": 1.5}, {"value": 2.5}]},
                    {"outputs": None},
                ]
            }
        )
        self.assertEqual(await self.bu.get_cached_max_transferable_value("a"), 4.0)

    async def test_save_wallet_unspent_cache_success_and_fail(self):
        mock_db = MagicMock()
        mock_db.wallet_unspent_cache.update_one = AsyncMock()
        latest = {"hash": "h", "index": 9}
        utxos = [
            {"id": "a", "time": 1, "outputs": [{"value": 3.0}]},
            {"id": "b", "time": 2, "outputs": [{"value": 1.0}]},
        ]
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            bal = await self.bu._save_wallet_unspent_cache(
                "addr", "pk", utxos, latest, selection_complete=True
            )
        self.assertEqual(bal, 4.0)
        mock_db.wallet_unspent_cache.update_one.assert_awaited()

        mock_db.wallet_unspent_cache.update_one = AsyncMock(
            side_effect=Exception("bson too big")
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            bal = await self.bu._save_wallet_unspent_cache(
                "addr", "pk", utxos, latest, max_utxos=1
            )
        self.assertEqual(bal, 4.0)

    async def test_invalidate_wallet_unspent_cache(self):
        mock_db = MagicMock()
        mock_db.wallet_unspent_cache.delete_one = AsyncMock()
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            await self.bu._invalidate_wallet_unspent_cache("a", reason="x")
        mock_db.wallet_unspent_cache.delete_one.assert_awaited()

    async def test_fetch_received_outputs_branches(self):
        class Agg:
            def __init__(self, docs, fail=False):
                self.docs = docs
                self.fail = fail

            async def to_list(self, length=None):
                if self.fail:
                    raise Exception("hint")
                return self.docs

        calls = {"n": 0}

        def aggregate(q, **kwargs):
            calls["n"] += 1
            if kwargs.get("hint") and calls["n"] == 1:
                return Agg([], fail=True)
            return Agg([{"id": "x", "outputs": [{"to": "a", "value": 1}]}])

        mock_db = MagicMock()
        mock_db.blocks.aggregate.side_effect = aggregate
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            docs = await self.bu._fetch_received_outputs(
                "a",
                from_index=1,
                to_index=10,
                max_blocks=5,
                min_value=0.1,
                sort_by_value=False,
            )
        self.assertEqual(len(docs), 1)

        calls["n"] = 0
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            docs = await self.bu._fetch_received_outputs(
                "a", max_blocks=5, sort_by_value=True, limit=10
            )
        self.assertEqual(len(docs), 1)

        calls["n"] = 0

        def aggregate2(q, **kwargs):
            return Agg([{"id": "y"}])

        mock_db.blocks.aggregate.side_effect = aggregate2
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            docs = await self.bu._fetch_received_outputs("a")
        self.assertEqual(docs[0]["id"], "y")

    async def test_filter_unspent_outputs_branches(self):
        empty, total = await self.bu._filter_unspent_outputs("pk", [])
        self.assertEqual(empty, [])
        self.assertEqual(total, 0.0)

        outputs = [
            {"id": "s1", "outputs": [{"value": 1.0}]},
            {"id": "u1", "outputs": [{"value": 2.0}]},
            {"id": None, "outputs": [{"value": 9.0}]},
            {"id": "u2", "outputs": [{"value": 3.0}]},
            {"id": "u3", "outputs": [{"value": 4.0}]},
        ]
        self.bu.get_spent_among_candidates = AsyncMock(return_value={"s1"})
        unspent, total = await self.bu._filter_unspent_outputs(
            "pk", outputs, batch_size=2, max_unspent=2
        )
        self.assertEqual(len(unspent), 2)
        self.assertEqual(total, 5.0)

        self.bu.get_spent_among_candidates = AsyncMock(return_value=set())
        unspent, total = await self.bu._filter_unspent_outputs(
            "pk",
            [
                {"id": "a", "outputs": [{"value": 5.0}]},
                {"id": "b", "outputs": [{"value": 5.0}]},
            ],
            batch_size=10,
            amount_needed=5.0,
        )
        self.assertEqual(len(unspent), 1)
        self.assertEqual(total, 5.0)

        # batch flush early return
        many = [{"id": f"i{i}", "outputs": [{"value": 1.0}]} for i in range(5)]
        self.bu.get_spent_among_candidates = AsyncMock(return_value=set())
        unspent, total = await self.bu._filter_unspent_outputs(
            "pk", many, batch_size=2, max_unspent=1
        )
        self.assertEqual(len(unspent), 1)

    async def test_select_spendable_utxos_windows_and_dust(self):
        self.config.balance_min_utxo = 1.0
        outs = [
            {"id": "big", "time": 2, "outputs": [{"value": 10.0}]},
            {"id": "mid", "time": 1, "outputs": [{"value": 5.0}]},
        ]
        self.bu._fetch_received_outputs = AsyncMock(return_value=outs)
        self.bu._filter_unspent_outputs = AsyncMock(
            side_effect=lambda pk, fresh, **kw: (
                fresh[: kw.get("max_unspent", 10)],
                sum(self.bu._utxo_value(x) for x in fresh[: kw.get("max_unspent", 10)]),
            )
        )
        unspent, total = await self.bu._select_spendable_utxos(
            "addr", "pk", max_utxos=2, amount_needed=12.0
        )
        self.assertTrue(unspent)
        self.assertGreaterEqual(total, 10.0)

        # dust fallback path: first pass short with min_value, second without
        self.config.balance_min_utxo = 5.0
        call = {"n": 0}

        async def fetch(*a, **k):
            call["n"] += 1
            if k.get("min_value", 0) > 0:
                return []  # no large coins
            return [{"id": "dust", "time": 1, "outputs": [{"value": 0.5}]}]

        self.bu._fetch_received_outputs = AsyncMock(side_effect=fetch)

        async def filt(pk, fresh, **kw):
            return list(fresh), sum(self.bu._utxo_value(x) for x in fresh)

        self.bu._filter_unspent_outputs = AsyncMock(side_effect=filt)
        unspent, total = await self.bu._select_spendable_utxos(
            "addr", "pk", max_utxos=5, amount_needed=0.5
        )
        self.assertEqual(unspent[0]["id"], "dust")

        # amount_needed=0 uses cfg min
        self.bu._fetch_received_outputs = AsyncMock(return_value=outs)
        self.bu._filter_unspent_outputs = AsyncMock(
            side_effect=lambda pk, fresh, **kw: (fresh, 15.0)
        )
        unspent, total = await self.bu._select_spendable_utxos(
            "addr", "pk", max_utxos=2, amount_needed=0
        )
        self.assertEqual(len(unspent), 2)

    async def test_get_unspent_outputs_reorg_and_reselect(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value="pk")
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "tip", "index": 10}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=9.0)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        # invalid cache → invalidate
        self.bu._get_wallet_unspent_cache = AsyncMock(
            return_value={"last_block_hash": "old", "unspent_utxos": []}
        )
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=False)
        self.bu._invalidate_wallet_unspent_cache = AsyncMock()
        self.bu._select_spendable_utxos = AsyncMock(
            return_value=(
                [{"id": "a", "time": 1, "outputs": [{"value": 9.0}]}],
                9.0,
            )
        )
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=9.0)
        result = await self.bu.get_unspent_outputs("addr", amount_needed=1.0)
        self.bu._invalidate_wallet_unspent_cache.assert_awaited()
        self.assertEqual(result["unspent_utxos"][0]["id"], "a")

        # cache hit but incomplete → RESELECT
        cache = {
            "unspent_utxos": [{"id": "small", "time": 1, "outputs": [{"value": 1.0}]}],
            "max_transferable_value": 1.0,
            "last_block_hash": "tip",
            "last_block_index": 10,
            "selection_complete": False,
        }
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=cache)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu._select_spendable_utxos = AsyncMock(
            return_value=(
                [
                    {"id": "big", "time": 2, "outputs": [{"value": 20.0}]},
                    {"id": "small", "time": 1, "outputs": [{"value": 1.0}]},
                ],
                21.0,
            )
        )
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=21.0)
        result = await self.bu.get_unspent_outputs("addr", amount_needed=15.0)
        self.assertEqual(result["unspent_utxos"][0]["id"], "big")

    async def test_get_unspent_outputs_incremental_extra_and_reselect(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value="pk")
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "new", "index": 20}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=30.0)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        cache = {
            "unspent_utxos": [{"id": "old", "time": 1, "outputs": [{"value": 1.0}]}],
            "last_block_hash": "old",
            "last_block_index": 10,
        }
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=cache)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu._fetch_received_outputs = AsyncMock(
            return_value=[{"id": "n1", "time": 2, "outputs": [{"value": 2.0}]}]
        )
        self.bu.get_spent_among_candidates = AsyncMock(return_value=set())
        # filter returns sparse set to force extra select
        self.bu._filter_unspent_outputs = AsyncMock(
            return_value=(
                [{"id": "old", "time": 1, "outputs": [{"value": 1.0}]}],
                1.0,
            )
        )
        self.bu._select_spendable_utxos = AsyncMock(
            return_value=(
                [
                    {"id": "extra", "time": 3, "outputs": [{"value": 50.0}]},
                    {"id": "old", "time": 1, "outputs": [{"value": 1.0}]},
                ],
                51.0,
            )
        )
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=51.0)
        # short amount triggers fallthrough to full select after incremental short
        result = await self.bu.get_unspent_outputs(
            "addr", amount_needed=40.0, max_utxos=2
        )
        ids = [u["id"] for u in result["unspent_utxos"]]
        self.assertIn("extra", ids)

    async def test_get_unspent_outputs_from_index_path(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value="pk")
        self.bu.get_latest_block_async = AsyncMock(return_value=None)
        self.bu.get_wallet_balance = AsyncMock(return_value=5.0)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=["mp"])
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=None)
        self.bu._fetch_received_outputs = AsyncMock(
            return_value=[
                {"id": "mp", "time": 1, "outputs": [{"value": 9.0}]},
                {"id": "ok", "time": 2, "outputs": [{"value": 5.0}]},
            ]
        )
        self.bu._filter_unspent_outputs = AsyncMock(
            return_value=(
                [{"id": "ok", "time": 2, "outputs": [{"value": 5.0}]}],
                5.0,
            )
        )
        result = await self.bu.get_unspent_outputs(
            "addr", amount_needed=1.0, from_index=100
        )
        self.assertEqual(result["unspent_utxos"][0]["id"], "ok")

    async def test_get_unspent_outputs_mempool_filter_on_full_select(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value="pk")
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "t", "index": 1}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=3.0)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=["spent"])
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=None)
        self.bu._select_spendable_utxos = AsyncMock(
            return_value=(
                [
                    {"id": "spent", "time": 1, "outputs": [{"value": 9.0}]},
                    {"id": "keep", "time": 2, "outputs": [{"value": 3.0}]},
                ],
                12.0,
            )
        )
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=3.0)
        result = await self.bu.get_unspent_outputs("addr", amount_needed=1.0)
        self.assertEqual([u["id"] for u in result["unspent_utxos"]], ["keep"])

    async def test_spent_among_candidates_empty_and_from_index(self):
        self.assertEqual(await self.bu.get_spent_among_candidates(None, ["a"]), set())
        self.assertEqual(await self.bu.get_spent_among_candidates("pk", []), set())

        async def gen(*a, **k):
            yield {"_id": "a"}
            if False:
                yield None

        self.bu._iter_blocks_aggregate = gen
        spent = await self.bu.get_spent_among_candidates("pk", ["a", "b"], from_index=5)
        self.assertEqual(spent, {"a"})


class TestRemainingCoverageGaps(BUTestCase):
    async def test_filter_flush_empty_pending(self):
        """Covers flush() early return when pending is empty (line 1584)."""
        # Force a final flush with empty pending: only None-id outputs after batch.
        # batch_size larger than list so loop never mid-flushes; final await flush()
        # runs with pending that has items. Instead call flush via empty batch edge:
        # provide outputs that fill pending then get cleared, then empty trailing flush.
        # Direct approach: monkeypatch loop to call flush when pending empty.
        outputs = [{"id": "a", "outputs": [{"value": 1.0}]}]
        self.bu.get_spent_among_candidates = AsyncMock(return_value=set())
        # Normal path covers non-empty. Call _filter with empty after internal:
        # Use batch_size=1 with one output - flush runs with pending.
        # To hit empty pending return: call flush after clear via custom path.
        unspent, total = await self.bu._filter_unspent_outputs("pk", outputs)
        self.assertEqual(len(unspent), 1)

        # Invoke the nested flush with empty pending by replaying method logic
        # through a tiny subclass hook.
        seen = {}

        async def tracking_filter(
            public_key, outputs, batch_size=100, max_unspent=None, amount_needed=None
        ):
            if not outputs:
                return [], 0.0
            unspent = []
            total = 0.0
            pending = []

            async def flush():
                nonlocal total
                if not pending:
                    seen["empty"] = True
                    return False
                ids = [o["id"] for o in pending if o.get("id")]
                spent = await self.bu.get_spent_among_candidates(public_key, ids)
                for output in pending:
                    oid = output.get("id")
                    if not oid or oid in spent:
                        continue
                    unspent.append(output)
                    total += self.bu._utxo_value(output)
                pending.clear()
                return False

            for output in outputs:
                pending.append(output)
                if len(pending) >= batch_size:
                    await flush()
            await flush()  # second call after clear -> empty pending
            return unspent, total

        self.bu._filter_unspent_outputs = tracking_filter
        await self.bu._filter_unspent_outputs(
            "pk", [{"id": "x", "outputs": [{"value": 1}]}], batch_size=1
        )
        # Direct empty flush via real method: empty outputs already returns early.
        # Call real implementation's flush by using outputs=[] after restoring.
        from yadacoin.core.blockchainutils import BlockChainUtils

        real = BlockChainUtils._filter_unspent_outputs
        # Restore and hit empty pending by batch that clears then final flush:
        # batch_size=1, one spent-filtered? Actually after processing one item
        # pending is cleared in flush, then final await flush() hits empty.
        self.bu.get_spent_among_candidates = AsyncMock(return_value=set())
        result = await real(
            self.bu, "pk", [{"id": "z", "outputs": [{"value": 1.0}]}], batch_size=1
        )
        self.assertEqual(result[0][0]["id"], "z")

    async def test_select_dust_fallback_max_utxos_break(self):
        """Covers dust-fallback break when max_utxos reached (line 1729)."""
        self.config.balance_min_utxo = 10.0
        call = {"n": 0}

        async def fetch(*a, **k):
            call["n"] += 1
            if k.get("min_value", 0) > 0:
                return []
            # return more dust than max_utxos
            return [
                {"id": f"d{i}", "time": i, "outputs": [{"value": 0.1}]}
                for i in range(5)
            ]

        self.bu._fetch_received_outputs = AsyncMock(side_effect=fetch)

        async def filt(pk, fresh, **kw):
            need = kw.get("max_unspent") or len(fresh)
            take = list(fresh)[:need]
            return take, sum(self.bu._utxo_value(x) for x in take)

        self.bu._filter_unspent_outputs = AsyncMock(side_effect=filt)
        unspent, total = await self.bu._select_spendable_utxos(
            "addr", "pk", max_utxos=2, amount_needed=1.0
        )
        self.assertEqual(len(unspent), 2)

    async def test_incremental_short_falls_through_to_full(self):
        """Covers selectable = None fallthrough when incremental still short (1907)."""
        self.bu.get_reverse_public_key = AsyncMock(return_value="pk")
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "new", "index": 20}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=100.0)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        cache = {
            "unspent_utxos": [{"id": "tiny", "time": 1, "outputs": [{"value": 1.0}]}],
            "last_block_hash": "old",
            "last_block_index": 10,
        }
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=cache)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu._fetch_received_outputs = AsyncMock(return_value=[])
        self.bu.get_spent_among_candidates = AsyncMock(return_value=set())
        # Incremental keeps only the tiny utxo — short of amount_needed and
        # under max_utxos so selectable is cleared for full reselect.
        self.bu._filter_unspent_outputs = AsyncMock(
            return_value=(
                [{"id": "tiny", "time": 1, "outputs": [{"value": 1.0}]}],
                1.0,
            )
        )
        # extra select also returns sparse (len < max) so still short
        self.bu._select_spendable_utxos = AsyncMock(
            side_effect=[
                ([{"id": "tiny", "time": 1, "outputs": [{"value": 1.0}]}], 1.0),
                # full select after fallthrough
                (
                    [{"id": "big", "time": 2, "outputs": [{"value": 50.0}]}],
                    50.0,
                ),
            ]
        )
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=50.0)
        result = await self.bu.get_unspent_outputs(
            "addr", amount_needed=40.0, max_utxos=10
        )
        self.assertEqual(result["unspent_utxos"][0]["id"], "big")
        # full select path was used (second call)
        self.assertEqual(self.bu._select_spendable_utxos.await_count, 2)
