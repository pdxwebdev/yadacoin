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
# get_chain_spent_inputs (batch pagination)
# ---------------------------------------------------------------------------


class TestGetChainSpentInputs(BUTestCase):
    async def test_returns_inputs_from_single_batch(self):
        mock_db = MagicMock()
        # First call returns data, second call returns empty (stops loop)
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(
            side_effect=[
                [{"spent_inputs": ["inp1", "inp2"]}],
                [],
            ]
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_chain_spent_inputs("pk1")
        self.assertIn("inp1", result)
        self.assertIn("inp2", result)

    async def test_returns_empty_when_no_results(self):
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(return_value=[])
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_chain_spent_inputs("pk1")
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
            return_value=[{"total_balance": result_value}]
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
        facet_result = {
            "total_spent_outputs": 3.0,
            "total_fee": 0.1,
            "total_mn_fee": 0.05,
        }
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(
            return_value=[facet_result]
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
    async def test_zero_amount_needed_returns_balance_only(self):
        mock_db = MagicMock()
        # reversed_public_keys cache hit
        mock_db.reversed_public_keys.find_one = AsyncMock(
            return_value={"public_key": self.config.public_key}
        )
        # blocks aggregate returns two outputs
        outputs = [
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
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(return_value=outputs)
        # chain and mempool spent inputs both empty
        mock_db.miner_transactions.aggregate.return_value.to_list = AsyncMock(
            return_value=[]
        )

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(
                self.bu,
                "get_chain_spent_inputs",
                new=AsyncMock(return_value=set()),
            ):
                with patch.object(
                    self.bu,
                    "get_mempool_spent_inputs",
                    new=AsyncMock(return_value=[]),
                ):
                    result = await self.bu.get_unspent_outputs(
                        self.config.address, amount_needed=0
                    )

        self.assertIn("balance", result)
        self.assertEqual(result["unspent_utxos"], [])
        self.assertAlmostEqual(result["balance"], 8.0)

    async def test_with_amount_needed_returns_utxos(self):
        mock_db = MagicMock()
        mock_db.reversed_public_keys.find_one = AsyncMock(
            return_value={"public_key": self.config.public_key}
        )
        outputs = [
            {
                "id": "txn1",
                "outputs": [{"to": self.config.address, "value": 5.0}],
                "time": 100,
            },
        ]
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(return_value=outputs)

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(
                self.bu,
                "get_chain_spent_inputs",
                new=AsyncMock(return_value=set()),
            ):
                with patch.object(
                    self.bu,
                    "get_mempool_spent_inputs",
                    new=AsyncMock(return_value=[]),
                ):
                    result = await self.bu.get_unspent_outputs(
                        self.config.address, amount_needed=3.0
                    )

        self.assertIn("unspent_utxos", result)
        self.assertEqual(len(result["unspent_utxos"]), 1)

    async def test_spent_outputs_excluded(self):
        mock_db = MagicMock()
        mock_db.reversed_public_keys.find_one = AsyncMock(
            return_value={"public_key": self.config.public_key}
        )
        outputs = [
            {
                "id": "spent_txn",
                "outputs": [{"to": self.config.address, "value": 5.0}],
                "time": 100,
            },
        ]
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(return_value=outputs)

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(
                self.bu,
                "get_chain_spent_inputs",
                new=AsyncMock(return_value={"spent_txn"}),
            ):
                with patch.object(
                    self.bu,
                    "get_mempool_spent_inputs",
                    new=AsyncMock(return_value=[]),
                ):
                    result = await self.bu.get_unspent_outputs(
                        self.config.address, amount_needed=0
                    )

        self.assertAlmostEqual(result["balance"], 0.0)


class TestGetUnspentOutputsZeroProcessingTime(BUTestCase):
    async def test_zero_processing_time_else_branch(self):
        """Line 979: processing_time <= 0 hits the else pass."""
        mock_db = MagicMock()
        mock_db.reversed_public_keys.find_one = AsyncMock(
            return_value={"public_key": self.config.public_key}
        )
        outputs = [
            {
                "id": "txn1",
                "outputs": [{"to": self.config.address, "value": 5.0}],
                "time": 100,
            },
        ]
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(return_value=outputs)
        mock_db.miner_transactions.aggregate.return_value.to_list = AsyncMock(
            return_value=[]
        )

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(
                self.bu,
                "get_chain_spent_inputs",
                new=AsyncMock(return_value=set()),
            ):
                with patch.object(
                    self.bu,
                    "get_mempool_spent_inputs",
                    new=AsyncMock(return_value=[]),
                ):
                    # Constant clock → processing_time == 0 → else pass
                    with patch(
                        "yadacoin.core.blockchainutils.precise_time",
                        return_value=1000.0,
                    ):
                        result = await self.bu.get_unspent_outputs(
                            self.config.address, amount_needed=1.0
                        )
        self.assertIn("unspent_utxos", result)


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
