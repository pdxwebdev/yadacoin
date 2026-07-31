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

    async def test_iter_blocks_aggregate_hint_fallback(self):
        """Hinted aggregate fails mid-iteration; retry without hint."""

        class FailingCursor:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise Exception("bad hint")

        class OkCursor:
            def __init__(self, items):
                self._items = list(items)
                self._i = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._i >= len(self._items):
                    raise StopAsyncIteration
                item = self._items[self._i]
                self._i += 1
                return item

        n = {"c": 0}

        def aggregate(*args, **kwargs):
            n["c"] += 1
            if "hint" in kwargs:
                return FailingCursor()
            return OkCursor([{"id": "recovered"}])

        mock_db = MagicMock()
        mock_db.blocks.aggregate.side_effect = aggregate
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_chain_spent_inputs("pk1")
        self.assertEqual(result, {"recovered"})
        self.assertGreaterEqual(n["c"], 2)

    async def test_get_spent_among_candidates_empty_and_from_index(self):
        empty = await self.bu.get_spent_among_candidates(None, ["a"])
        self.assertEqual(empty, set())
        empty2 = await self.bu.get_spent_among_candidates("pk", [])
        self.assertEqual(empty2, set())

        class OkCursor:
            def __init__(self, items):
                self._items = list(items)
                self._i = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._i >= len(self._items):
                    raise StopAsyncIteration
                item = self._items[self._i]
                self._i += 1
                return item

        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value = OkCursor([{"_id": "spent1"}])
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            spent = await self.bu.get_spent_among_candidates(
                "pk", ["spent1", "free"], from_index=10
            )
        self.assertEqual(spent, {"spent1"})
        # from_index => no compound-index hint
        self.assertNotIn("hint", mock_db.blocks.aggregate.call_args.kwargs)


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
    def _agg_db(self, rows, public_key=None):
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(return_value=rows)
        pk = self.config.public_key if public_key is None else public_key
        mock_db.reversed_public_keys.find_one = AsyncMock(
            return_value={"public_key": pk} if pk else None
        )
        return mock_db

    async def _make_mock_db_with_aggregate_result(self, result_value):
        return self._agg_db([{"total_balance": result_value}])

    async def test_get_total_received_balance_returns_value(self):
        mock_db = await self._make_mock_db_with_aggregate_result(10.5)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_total_received_balance(self.config.address)
        self.assertAlmostEqual(result, 10.5)

    async def test_get_total_received_balance_returns_zero_when_empty(self):
        mock_db = self._agg_db([])
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_total_received_balance(self.config.address)
        self.assertEqual(result, 0.0)

    async def test_get_spent_balance_returns_sum(self):
        facet_result = {
            "total_spent_outputs": 3.0,
            "total_fee": 0.1,
            "total_mn_fee": 0.05,
        }
        mock_db = self._agg_db([facet_result])
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_spent_balance(self.config.address)
            # Historical API maps from_index -> to_index on get_total_spent_balance
            result2 = await self.bu.get_spent_balance(
                self.config.address, from_index=100
            )
        self.assertAlmostEqual(result, 3.15)
        self.assertAlmostEqual(result2, 3.15)

    async def test_get_spent_balance_returns_zero_when_empty(self):
        mock_db = self._agg_db([])
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_spent_balance(self.config.address)
        self.assertEqual(result, 0.0)

    async def test_get_total_spent_no_public_key_returns_zero(self):
        mock_db = self._agg_db([], public_key=False)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_total_spent_balance(self.config.address)
        self.assertEqual(result, 0.0)

    async def test_get_total_spent_with_from_index_and_total_spent(self):
        mock_db = self._agg_db([{"totalSpent": 4.25}])
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_total_spent_balance(
                self.config.address, from_index=5
            )
        self.assertAlmostEqual(result, 4.25)
        # from_index set => no index hint on aggregate
        kwargs = mock_db.blocks.aggregate.call_args.kwargs
        self.assertNotIn("hint", kwargs)

    async def test_aggregate_blocks_hint_fallback_on_error(self):
        mock_db = MagicMock()
        call_n = {"n": 0}

        class Agg:
            def __init__(self, fail_hint):
                self.fail_hint = fail_hint

            def to_list(self, length=1):
                call_n["n"] += 1
                if self.fail_hint:
                    raise Exception("no hint index")
                return [{"totalSpent": 1.5}]

            async def __aiter__(self):
                if False:
                    yield {}

        def aggregate(*args, **kwargs):
            return Agg(fail_hint="hint" in kwargs)

        # Async to_list
        async def to_list_ok(length=1):
            return [{"totalSpent": 1.5}]

        async def to_list_fail(length=1):
            raise Exception("no hint index")

        n = {"c": 0}

        def aggregate2(*args, **kwargs):
            cur = MagicMock()
            n["c"] += 1
            if "hint" in kwargs:
                cur.to_list = to_list_fail
            else:
                cur.to_list = to_list_ok
            return cur

        mock_db.blocks.aggregate.side_effect = aggregate2
        mock_db.reversed_public_keys.find_one = AsyncMock(
            return_value={"public_key": self.config.public_key}
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_total_spent_balance(self.config.address)
        self.assertAlmostEqual(result, 1.5)
        self.assertGreaterEqual(n["c"], 2)

    async def test_received_from_others_no_pk_and_from_index(self):
        mock_db = self._agg_db([{"totalReceived": 2.0}], public_key=False)
        # reverse lookup returns None so txn_cond uses no-public_key branch
        self.bu.get_reverse_public_key = AsyncMock(return_value=None)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_received_from_others_balance(
                self.config.address, public_key=None, from_index=3
            )
        self.assertAlmostEqual(result, 2.0)

    async def test_received_solo_no_pk_returns_zero(self):
        mock_db = self._agg_db([], public_key=False)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_received_solo_mining_balance(self.config.address)
        self.assertEqual(result, 0.0)

    async def test_received_solo_index_filters_and_legacy_total_balance(self):
        mock_db = self._agg_db([{"total_balance": 9.0}])
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_received_solo_mining_balance(
                self.config.address, from_index=1, to_index=99
            )
        self.assertAlmostEqual(result, 9.0)

    async def test_masternode_coinbase_index_filters_and_legacy(self):
        mock_db = self._agg_db([{"total_balance": 1.25}])
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_masternode_coinbase_balance(
                self.config.address, from_index=2, to_index=50
            )
        self.assertAlmostEqual(result, 1.25)
        mock_db2 = self._agg_db([{"totalReceived": 0.75}])
        with patch.object(self.config.mongo, "async_db", new=mock_db2):
            result2 = await self.bu.get_masternode_coinbase_balance(self.config.address)
        self.assertAlmostEqual(result2, 0.75)

    async def test_coinbase_alias_and_compute_components_without_pk_arg(self):
        mock_db = self._agg_db([{"totalReceived": 0.0}])
        # spent facet empty; received paths return 0
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(return_value=[])
        mock_db.reversed_public_keys.find_one = AsyncMock(
            return_value={"public_key": self.config.public_key}
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            alias = await self.bu.get_coinbase_total_output_balance(self.config.address)
            comps = await self.bu._compute_balance_components(self.config.address)
        self.assertEqual(alias, 0.0)
        self.assertEqual(comps["public_key"], self.config.public_key)
        self.assertIn("total_spent", comps)

    async def test_save_wallet_balance_cache_writes_doc(self):
        mock_db = MagicMock()
        mock_db.wallet_balance_cache.update_one = AsyncMock()
        mock_db.wallet_balance_cache.find_one = AsyncMock(
            return_value={"balance": 1.0, "address": self.config.address}
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            bal = await self.bu._save_wallet_balance_cache(
                self.config.address,
                self.config.public_key,
                1.0,
                4.0,
                5.0,
                {"hash": "h", "index": 7},
            )
            cached = await self.bu._get_wallet_balance_cache(self.config.address)
        self.assertAlmostEqual(bal, 8.0)
        self.assertEqual(cached["balance"], 1.0)
        mock_db.wallet_balance_cache.update_one.assert_awaited_once()


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
            "max_transferable_value": 4.0,
            "last_block_hash": "tip",
            "last_block_index": 10,
        }
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=cache_doc)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu._select_spendable_utxos = AsyncMock()
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        result = await self.bu.get_unspent_outputs(self.config.address, amount_needed=0)
        self.assertAlmostEqual(result["balance"], 4.0)
        self.assertAlmostEqual(result["max_transferable_value"], 4.0)
        self.bu._select_spendable_utxos.assert_not_awaited()

    async def test_unspent_cache_hit_legacy_max_transferable(self):
        """DISPLAY path sums UTXOs when max_transferable_value is absent."""
        self.bu.get_reverse_public_key = AsyncMock(return_value=self.config.public_key)
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "tip", "index": 10}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=7.0)
        cache_doc = {
            "unspent_utxos": [
                {"id": "a", "outputs": [{"value": 3.0}], "time": 1},
                {"id": "b", "outputs": [{"value": 4.0}], "time": 2},
            ],
            "last_block_hash": "tip",
            "last_block_index": 10,
        }
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=cache_doc)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        result = await self.bu.get_unspent_outputs(self.config.address, amount_needed=0)
        self.assertAlmostEqual(result["max_transferable_value"], 7.0)

    async def test_unspent_cache_invalid_triggers_invalidate(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value=self.config.public_key)
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "tip", "index": 10}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=1.0)
        self.bu._get_wallet_unspent_cache = AsyncMock(
            return_value={"last_block_hash": "stale", "last_block_index": 1}
        )
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=False)
        self.bu._invalidate_wallet_unspent_cache = AsyncMock()
        self.bu._select_spendable_utxos = AsyncMock(
            return_value=(
                [{"id": "u1", "outputs": [{"value": 1.0}], "time": 1}],
                1.0,
            )
        )
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=1.0)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        result = await self.bu.get_unspent_outputs(
            self.config.address, amount_needed=0.5
        )
        self.bu._invalidate_wallet_unspent_cache.assert_awaited()
        self.assertEqual(len(result["unspent_utxos"]), 1)

    async def test_unspent_cache_reselect_when_amount_not_covered(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value=self.config.public_key)
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "tip", "index": 10}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=1.0)
        cache_doc = {
            "unspent_utxos": [
                {"id": "small", "outputs": [{"value": 1.0}], "time": 1},
            ],
            "max_transferable_value": 1.0,
            "selection_complete": False,
            "last_block_hash": "tip",
            "last_block_index": 10,
        }
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=cache_doc)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu._select_spendable_utxos = AsyncMock(
            return_value=(
                [
                    {"id": "small", "outputs": [{"value": 1.0}], "time": 1},
                    {"id": "big", "outputs": [{"value": 9.0}], "time": 2},
                ],
                10.0,
            )
        )
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=10.0)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        result = await self.bu.get_unspent_outputs(
            self.config.address, amount_needed=5.0
        )
        self.bu._select_spendable_utxos.assert_awaited()
        ids = [u["id"] for u in result["unspent_utxos"]]
        self.assertIn("big", ids)

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
        # Exercise real _filter_unspent_outputs + empty-cache _async_empty_set path
        # by only mocking lower-level spent lookup and fetch.
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
        self.bu._select_spendable_utxos = AsyncMock(
            return_value=(
                [
                    {
                        "id": "extra",
                        "outputs": [{"to": self.config.address, "value": 1.0}],
                        "time": 4,
                    }
                ],
                1.0,
            )
        )
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=8.0)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        # force sparse max_utxos so extra select merge runs
        result = await self.bu.get_unspent_outputs(
            self.config.address, amount_needed=0, max_utxos=5
        )
        self.assertAlmostEqual(result["balance"], 8.0)
        self.bu._save_wallet_unspent_cache.assert_awaited()

    async def test_incremental_falls_through_when_amount_short(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value=self.config.public_key)
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "newtip", "index": 12}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=2.0)
        cache_doc = {
            "unspent_utxos": [
                {"id": "old1", "outputs": [{"value": 1.0}], "time": 1},
            ],
            "last_block_hash": "oldtip",
            "last_block_index": 10,
        }
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=cache_doc)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu._fetch_received_outputs = AsyncMock(return_value=[])
        self.bu.get_spent_among_candidates = AsyncMock(return_value=set())
        # After incremental merge still short of amount with room under max_utxos
        # => selectable=None fallthrough; FULL select then provides enough.
        select_calls = {"n": 0}

        async def select(*args, **kwargs):
            select_calls["n"] += 1
            if select_calls["n"] == 1:
                # sparse extra during incremental merge
                return ([{"id": "extra", "outputs": [{"value": 0.5}], "time": 2}], 0.5)
            # full select after fallthrough
            return (
                [
                    {"id": "old1", "outputs": [{"value": 1.0}], "time": 1},
                    {"id": "more", "outputs": [{"value": 10.0}], "time": 2},
                ],
                11.0,
            )

        self.bu._select_spendable_utxos = AsyncMock(side_effect=select)
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=11.0)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        result = await self.bu.get_unspent_outputs(
            self.config.address, amount_needed=5.0, max_utxos=10
        )
        ids = [u["id"] for u in result["unspent_utxos"]]
        self.assertIn("more", ids)
        self.assertGreaterEqual(select_calls["n"], 2)

    async def test_incremental_extra_merge_hits_max_utxos(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value=self.config.public_key)
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "newtip", "index": 12}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=3.0)
        cache_doc = {
            "unspent_utxos": [
                {"id": "old1", "outputs": [{"value": 1.0}], "time": 1},
            ],
            "last_block_hash": "oldtip",
            "last_block_index": 10,
        }
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=cache_doc)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu._fetch_received_outputs = AsyncMock(return_value=[])
        self.bu.get_spent_among_candidates = AsyncMock(return_value=set())
        self.bu._select_spendable_utxos = AsyncMock(
            return_value=(
                [
                    {"id": "e1", "outputs": [{"value": 1.0}], "time": 2},
                    {"id": "e2", "outputs": [{"value": 1.0}], "time": 3},
                    {"id": "e3", "outputs": [{"value": 1.0}], "time": 4},
                ],
                3.0,
            )
        )
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=2.0)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        result = await self.bu.get_unspent_outputs(
            self.config.address, amount_needed=0, max_utxos=2
        )
        self.assertAlmostEqual(result["balance"], 3.0)
        self.bu._save_wallet_unspent_cache.assert_awaited()

    async def test_select_spendable_and_fetch_received_real(self):
        """Drive real _select_spendable_utxos / _fetch_received_outputs / filter."""
        self.config.balance_min_utxo = 0.5
        outputs = [
            {"id": "big", "outputs": [{"value": 5.0}], "time": 3},
            {"id": "med", "outputs": [{"value": 2.0}], "time": 2},
            {"id": "dust", "outputs": [{"value": 0.1}], "time": 1},
            {"id": "spent", "outputs": [{"value": 4.0}], "time": 4},
        ]

        async def fetch(*args, **kwargs):
            # honor min_value roughly like mongo would
            mv = kwargs.get("min_value") or 0
            return [o for o in outputs if self.bu._utxo_value(o) >= float(mv or 0)]

        self.bu._fetch_received_outputs = AsyncMock(side_effect=fetch)
        self.bu.get_spent_among_candidates = AsyncMock(return_value={"spent"})
        selected, total = await self.bu._select_spendable_utxos(
            self.config.address,
            self.config.public_key,
            max_utxos=2,
            amount_needed=6.0,
        )
        ids = [u["id"] for u in selected]
        self.assertNotIn("spent", ids)
        self.assertGreaterEqual(total, 6.0)

    async def test_fetch_received_outputs_pipeline_and_hint_fallback(self):
        mock_db = MagicMock()
        n = {"c": 0}

        async def to_list(length=None):
            n["c"] += 1
            if n["c"] == 1:
                raise Exception("missing index")
            return [{"id": "t1", "outputs": [{"to": "a", "value": 1.0}], "time": 1}]

        cur = MagicMock()
        cur.to_list = to_list
        mock_db.blocks.aggregate.return_value = cur
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            rows = await self.bu._fetch_received_outputs(
                self.config.address,
                min_value=0.01,
                max_blocks=10,
                sort_by_value=True,
                limit=5,
            )
        self.assertEqual(len(rows), 1)
        # first attempt used hint, second without
        self.assertGreaterEqual(mock_db.blocks.aggregate.call_count, 2)

    async def test_fetch_received_with_index_bounds_no_hint(self):
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(return_value=[])
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            await self.bu._fetch_received_outputs(
                self.config.address,
                from_index=1,
                to_index=9,
                sort_time=1,
                sort_by_value=False,
            )
        kwargs = mock_db.blocks.aggregate.call_args.kwargs
        self.assertNotIn("hint", kwargs)

    async def test_fetch_received_default_uses_to_hint(self):
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value.to_list = AsyncMock(return_value=[])
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            await self.bu._fetch_received_outputs(self.config.address)
        self.assertEqual(mock_db.blocks.aggregate.call_args.kwargs.get("hint"), "__to")

    async def test_filter_unspent_empty_and_batch_stop(self):
        empty, tot = await self.bu._filter_unspent_outputs("pk", [])
        self.assertEqual(empty, [])
        self.assertEqual(tot, 0.0)

        outs = [{"id": f"i{i}", "outputs": [{"value": 1.0}]} for i in range(5)]
        self.bu.get_spent_among_candidates = AsyncMock(return_value=set())
        # stop on max_unspent inside batch
        got, total = await self.bu._filter_unspent_outputs(
            "pk", outs, batch_size=2, max_unspent=2
        )
        self.assertEqual(len(got), 2)
        # stop on amount_needed
        got2, total2 = await self.bu._filter_unspent_outputs(
            "pk", outs, batch_size=10, amount_needed=2.5
        )
        self.assertGreaterEqual(total2, 2.5)
        self.assertLessEqual(len(got2), 3)
        # exact multiple of batch_size => final flush() sees empty pending
        outs4 = [{"id": f"j{i}", "outputs": [{"value": 1.0}]} for i in range(4)]
        got3, _ = await self.bu._filter_unspent_outputs(
            "pk", outs4, batch_size=2, max_unspent=100
        )
        self.assertEqual(len(got3), 4)

    async def test_save_wallet_unspent_cache_and_cached_max(self):
        mock_db = MagicMock()
        mock_db.wallet_unspent_cache.update_one = AsyncMock()
        mock_db.wallet_unspent_cache.find_one = AsyncMock(
            return_value={
                "max_transferable_value": 3.33,
                "last_block_hash": "h",
                "last_block_index": 5,
                "unspent_utxos": [],
            }
        )
        mock_db.wallet_unspent_cache.delete_one = AsyncMock()
        mock_db.blocks.find_one = AsyncMock(
            side_effect=lambda q, *a, **k: (
                {"hash": "h", "index": 5}
                if q.get("hash") == "h" or q.get("index") == 5
                else None
            )
        )
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "tip", "index": 8}
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            bal = await self.bu._save_wallet_unspent_cache(
                self.config.address,
                self.config.public_key,
                [{"id": "u", "time": 1, "outputs": [{"value": 2.5}]}],
                {"hash": "h", "index": 5},
                selection_complete=True,
            )
            self.assertAlmostEqual(bal, 2.5)
            # exception path
            mock_db.wallet_unspent_cache.update_one = AsyncMock(
                side_effect=Exception("bson too large")
            )
            bal2 = await self.bu._save_wallet_unspent_cache(
                self.config.address,
                self.config.public_key,
                [{"id": "u2", "outputs": [{"value": 1.0}]}],
                {"hash": "h", "index": 5},
            )
            self.assertAlmostEqual(bal2, 1.0)
            mx = await self.bu.get_cached_max_transferable_value(self.config.address)
            self.assertAlmostEqual(mx, 3.33)
            await self.bu._invalidate_wallet_unspent_cache(
                self.config.address, reason="test"
            )
            mock_db.wallet_unspent_cache.delete_one.assert_awaited()

    async def test_cached_max_transferable_legacy_and_miss(self):
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "tip", "index": 3}
        )
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=None)
        self.assertEqual(
            await self.bu.get_cached_max_transferable_value(self.config.address), 0.0
        )
        self.bu._get_wallet_unspent_cache = AsyncMock(
            return_value={"last_block_hash": "x", "last_block_index": 1}
        )
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=False)
        self.assertEqual(
            await self.bu.get_cached_max_transferable_value(self.config.address), 0.0
        )
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu._get_wallet_unspent_cache = AsyncMock(
            return_value={
                "unspent_utxos": [
                    {"outputs": [{"value": 1.5}, {"value": None}]},
                    {"outputs": None},
                ]
            }
        )
        mx = await self.bu.get_cached_max_transferable_value(self.config.address)
        self.assertAlmostEqual(mx, 1.5)

    async def test_select_dust_fallback_and_async_empty_set(self):
        self.config.balance_min_utxo = 10.0

        # first pass with high min_value returns nothing; dust fallback min_value=0
        async def fetch(*args, **kwargs):
            mv = float(kwargs.get("min_value") or 0)
            if mv > 0:
                return []
            # many small coins; target high so amount stop does not fire first
            return [
                {"id": f"tiny{i}", "outputs": [{"value": 0.5}], "time": i}
                for i in range(5)
            ]

        self.bu._fetch_received_outputs = AsyncMock(side_effect=fetch)
        self.bu.get_spent_among_candidates = AsyncMock(return_value=set())
        selected, total = await self.bu._select_spendable_utxos(
            self.config.address,
            self.config.public_key,
            max_utxos=2,
            amount_needed=100.0,  # never met -> max_utxos break in dust merge
        )
        self.assertEqual(len(selected), 2)
        # amount_needed falsy => min_value = cfg_min (line 1575)
        self.config.balance_min_utxo = 1.0
        self.bu._fetch_received_outputs = AsyncMock(
            return_value=[{"id": "a", "outputs": [{"value": 11.0}], "time": 1}]
        )
        selected0, _ = await self.bu._select_spendable_utxos(
            self.config.address,
            self.config.public_key,
            max_utxos=3,
            amount_needed=None,
            min_value=None,
        )
        self.assertEqual([u["id"] for u in selected0], ["a"])
        empty = await self.bu._async_empty_set()
        self.assertEqual(empty, set())

    async def test_from_index_historical_fork_select(self):
        """from_index path fetches to_index-bounded candidates then filters."""
        self.bu.get_reverse_public_key = AsyncMock(return_value=self.config.public_key)
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "tip", "index": 20}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=5.0)
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=None)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=False)
        self.bu._fetch_received_outputs = AsyncMock(
            return_value=[
                {"id": "h1", "outputs": [{"value": 5.0}], "time": 1},
                {"id": "h2", "outputs": [{"value": 3.0}], "time": 2},
            ]
        )
        self.bu.get_spent_among_candidates = AsyncMock(return_value=set())
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        result = await self.bu.get_unspent_outputs(
            self.config.address, amount_needed=4.0, from_index=15
        )
        self.bu._fetch_received_outputs.assert_awaited()
        kwargs = self.bu._fetch_received_outputs.await_args.kwargs
        self.assertEqual(kwargs.get("to_index"), 15)
        self.assertEqual(len(result["unspent_utxos"]), 1)

    async def test_select_meets_target_stops_windows_and_dust(self):
        """Cover window loop target break and dust-fallback target break."""
        self.config.balance_min_utxo = 0.0
        # Window 1 returns enough to meet target; window 2 hits total>=target break.
        calls = {"n": 0}

        async def fetch_windows(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return [{"id": "big", "outputs": [{"value": 10.0}], "time": 1}]
            return [{"id": "more", "outputs": [{"value": 10.0}], "time": 2}]

        self.bu._fetch_received_outputs = AsyncMock(side_effect=fetch_windows)
        self.bu.get_spent_among_candidates = AsyncMock(return_value=set())
        selected, total = await self.bu._select_spendable_utxos(
            self.config.address,
            self.config.public_key,
            max_utxos=50,
            amount_needed=5.0,
            min_value=0,
        )
        self.assertGreaterEqual(total, 5.0)
        self.assertEqual([u["id"] for u in selected], ["big"])

        # Dust fallback: first pass empty under high min_value; dust adds until target
        async def fetch_dust(*args, **kwargs):
            mv = float(kwargs.get("min_value") or 0)
            if mv > 0:
                return []
            return [
                {"id": "d1", "outputs": [{"value": 0.3}], "time": 1},
                {"id": "d2", "outputs": [{"value": 0.3}], "time": 2},
                {"id": "d3", "outputs": [{"value": 0.3}], "time": 3},
            ]

        self.config.balance_min_utxo = 5.0
        self.bu._fetch_received_outputs = AsyncMock(side_effect=fetch_dust)
        selected2, total2 = await self.bu._select_spendable_utxos(
            self.config.address,
            self.config.public_key,
            max_utxos=50,
            amount_needed=0.5,
            min_value=None,
        )
        self.assertGreaterEqual(total2, 0.5)
        self.assertLessEqual(len(selected2), 2)

    async def test_incremental_empty_cache_uses_async_empty_set(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value=self.config.public_key)
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "newtip", "index": 12}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=0.0)
        cache_doc = {
            "unspent_utxos": [],
            "last_block_hash": "old",
            "last_block_index": 10,
        }
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=cache_doc)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=True)
        self.bu._fetch_received_outputs = AsyncMock(return_value=[])
        self.bu.get_spent_among_candidates = AsyncMock()
        self.bu._select_spendable_utxos = AsyncMock(return_value=([], 0.0))
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=0.0)
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        await self.bu.get_unspent_outputs(self.config.address, amount_needed=0)
        # empty by_id => get_spent_among_candidates not used
        self.bu.get_spent_among_candidates.assert_not_awaited()


class TestGetUnspentOutputsMempoolOverlay(BUTestCase):
    async def test_mempool_spend_filters_cached_utxo(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value=self.config.public_key)
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "tip", "index": 10}
        )
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
        self.assertAlmostEqual(result["balance"], 2.0)


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
