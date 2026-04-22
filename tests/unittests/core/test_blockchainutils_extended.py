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

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor
        mock_db.miner_transactions.find_one = AsyncMock(return_value={"id": "m1"})

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
        """Covers lines 800-810: extra_blocks branch in is_input_spent."""
        input_id = "test_input_id"

        class FakeInput:
            def __init__(self, id):
                self.id = id

        class FakeTxn:
            def __init__(self, inputs):
                self.inputs = [FakeInput(i) for i in inputs]

        class FakeBlock:
            def __init__(self, index, input_ids):
                self.index = index
                self.transactions = [FakeTxn(input_ids)]

        block_doc = {"index": 1}

        async def agg_iter(*args, **kwargs):
            yield block_doc

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: agg_iter()
        mock_db.blocks.aggregate.return_value = mock_cursor

        extra_blocks = [FakeBlock(1, [input_id])]

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent(
                input_id, "pk1", extra_blocks=extra_blocks
            )
        self.assertTrue(result)

    async def test_with_extra_blocks_no_match_returns_false(self):
        """Covers line 810: extra_blocks branch returns False when no match."""
        block_doc = {"index": 99}  # index doesn't match extra_blocks

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

        extra_blocks = [FakeBlock(1)]  # index 1 != 99, so no match

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.is_input_spent(
                "any_id", "pk1", extra_blocks=extra_blocks
            )
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# get_mempool_transactions
# ---------------------------------------------------------------------------


class TestGetMempoolTransactions(BUTestCase):
    async def test_returns_found_transaction(self):
        mock_db = MagicMock()
        mock_db.miner_transactions.find_one = AsyncMock(return_value={"id": "txn1"})
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_mempool_transactions("pk1", ["inp1"])
        self.assertEqual(result["id"], "txn1")

    async def test_returns_none_when_not_found(self):
        mock_db = MagicMock()
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await self.bu.get_mempool_transactions("pk1", ["inp1"])
        self.assertIsNone(result)


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
# generate_signature
# ---------------------------------------------------------------------------


class TestGenerateSignature(BUTestCase):
    async def test_returns_base64_string(self):
        sig = self.bu.generate_signature("test message", self.config.private_key)
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


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
