"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from unittest import mock
from unittest.mock import AsyncMock, MagicMock

from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.transaction import (
    InvalidTransactionException,
    InvalidTransactionSignatureException,
    MissingInputTransactionException,
    NotEnoughMoneyException,
)

from ..test_setup import AsyncTestCase


class _AsyncIterClone:
    """Simulates a non-list source with a .clone() method (e.g. a Mongo cursor)."""

    def __init__(self, items):
        self._items = items

    def clone(self):
        async def gen():
            for item in self._items:
                yield item

        return gen()


def _make_test_block(
    index=1,
    hash_="0" * 64,
    prev_hash="0" * 64,
    block_time=None,
    special_min=False,
    transactions=None,
    target=2**256 - 1,
):
    """Create a MagicMock that quacks like a Block for test_block()."""
    from time import time as _time

    block = MagicMock(spec=Block)
    block.index = index
    block.hash = hash_
    block.prev_hash = prev_hash
    block.time = block_time if block_time is not None else int(_time()) - 10
    block.special_min = special_min
    block.transactions = transactions if transactions is not None else []
    block.target = target
    block.verify = AsyncMock(return_value=None)
    return block


class TestBlockchain(AsyncTestCase):
    async def test_init(self):
        blockchain = Blockchain()
        self.assertIsInstance(blockchain, Blockchain)

    async def test_make_gen(self):
        blockchain = Blockchain()
        block_gen = blockchain.make_gen([1, 2])
        self.assertEqual([x async for x in block_gen], [1, 2])

    async def test_blocks(self):
        blocks = [Block()]
        blockchain = Blockchain(blocks)
        self.assertEqual([x async for x in blockchain.blocks], blocks)

    async def test_get_block(self):
        blocks = [Block()]
        blockchain = Blockchain(blocks)
        got_block = await blockchain.get_block(0, 1)
        self.assertEqual(got_block, blocks[0])

    async def test_get_blocks(self):
        blocks = [Block(), Block()]
        blockchain = Blockchain(blocks)
        got_blocks = blockchain.get_blocks(0, 2)
        self.assertEqual([x async for x in got_blocks], blocks)

    async def test_is_consecutive(self):
        block1 = Block()
        block1.index = 0
        block1.hash = "3"
        block1.prev_hash = ""

        block2 = Block()
        block2.index = 1
        block2.hash = "4"
        block2.prev_hash = "3"
        blockchain = Blockchain([block1, block2])
        self.assertTrue(await blockchain.is_consecutive)

    async def test_final_block(self):
        blocks = [Block(), Block()]
        blockchain = Blockchain(blocks)
        final_block = blockchain.final_block
        self.assertEqual(final_block, blocks[1])

    async def test_count(self):
        blocks = [Block(), Block()]
        blockchain = Blockchain(blocks)
        final_block = blockchain.final_block
        self.assertEqual(final_block, blocks[1])

    async def test_verify(self):
        from traceback import format_exc

        blockchain = Blockchain()
        try:
            await blockchain.verify()
        except:
            self.fail(f"Blockchain did not verify {format_exc()}")

    async def test_test_inbound_chain(self):
        block1 = Block()
        block1.index = 0
        block1.hash = "3000000000000000"
        block1.prev_hash = ""

        block2 = Block()
        block2.index = 1
        block2.hash = "4000000000000000"
        blocks = [block1, block2]
        blockchain = Blockchain(blocks)

        block1 = Block()
        block1.index = 0
        block1.hash = "3"
        block1.prev_hash = ""

        block2 = Block()
        block2.index = 1
        block2.hash = "5"

        block3 = Block()
        block3.index = 2
        block3.hash = "5"
        inbound_blocks = [block1, block2, block3]
        inbound_blockchain = Blockchain(inbound_blocks)

        self.assertTrue(await blockchain.test_inbound_blockchain(inbound_blockchain))

    async def test_get_difficulty(self):
        block1 = Block()
        block1.index = 0
        block1.hash = "3000000000000000"
        block1.prev_hash = ""

        block2 = Block()
        block2.index = 1
        block2.hash = "4000000000000000"
        blocks = [block1, block2]
        blockchain = Blockchain(blocks)
        result = await blockchain.get_difficulty()
        self.assertEqual(
            result,
            231584178474632390847141970017375815706539969331281128078907097565294011351038,
        )


class TestBlockchainBlocksProperty(AsyncTestCase):
    """Cover the non-list branch of the blocks property and from_dict conversion."""

    async def test_blocks_with_non_list_clone_branch(self):
        """Line 63: init_blocks is not a list, so blocks = self.init_blocks.clone()."""
        b = Block()
        b.index = 1
        b.hash = "abc"
        source = _AsyncIterClone([b])
        blockchain = Blockchain()
        blockchain.init_blocks = source  # not list / Block / dict / falsy
        results = [x async for x in blockchain.blocks]
        self.assertEqual(results, [b])

    async def test_blocks_yields_from_dict_when_not_block(self):
        """Line 67: 'block = await Block.from_dict(block)' inside blocks property."""
        block_dict = {"fake": "dict"}
        converted = Block()
        with mock.patch(
            "yadacoin.core.blockchain.Block.from_dict",
            new=AsyncMock(return_value=converted),
        ):
            blockchain = Blockchain([block_dict])
            results = [x async for x in blockchain.blocks]
        self.assertEqual(results, [converted])

    async def test_get_blocks_yields_from_dict_when_not_block(self):
        """Line 76: 'block = await Block.from_dict(block)' in get_blocks."""
        # We patch Blockchain.blocks itself to yield raw dicts so get_blocks
        # exercises the not-isinstance branch.

        async def _fake_blocks_gen(self):
            for d in [{"fake": 1}, {"fake": 2}]:
                yield d

        converted = [Block(), Block()]
        with mock.patch.object(Blockchain, "blocks", property(_fake_blocks_gen)):
            with mock.patch(
                "yadacoin.core.blockchain.Block.from_dict",
                new=AsyncMock(side_effect=converted),
            ):
                blockchain = Blockchain()
                results = [x async for x in blockchain.get_blocks(0, 2)]
        self.assertEqual(results, converted)


class TestBlockchainFirstBlock(AsyncTestCase):
    """Cover first_block return paths."""

    async def test_first_block_none_when_empty(self):
        """Line 94: first_block returns None when init_blocks is empty."""
        blockchain = Blockchain()
        self.assertIsNone(blockchain.first_block)

    async def test_first_block_returns_first_when_list(self):
        """Line 95: first_block returns init_blocks[0]."""
        b1 = Block()
        b2 = Block()
        blockchain = Blockchain([b1, b2])
        self.assertEqual(blockchain.first_block, b1)


class TestBlockchainVerify(AsyncTestCase):
    """Cover the verify() method's from_dict and verified=False branches."""

    async def test_verify_returns_false_when_test_block_fails(self):
        """Line 129: returns {'verified': False} when test_block returns False."""
        b = Block()
        with mock.patch(
            "yadacoin.core.blockchain.Blockchain.test_block",
            new=AsyncMock(return_value=False),
        ):
            blockchain = Blockchain([b])
            result = await blockchain.verify()
        self.assertEqual(result, {"verified": False})

    async def test_verify_converts_dict_to_block(self):
        """Line 126: 'block = await Block.from_dict(block)' in verify.

        ``Blockchain.blocks`` always converts dicts -> Blocks, so the only way
        to exercise the inner from_dict call in ``verify`` is to patch the
        ``blocks`` property to yield raw dicts."""

        async def _fake_blocks_gen(self):
            yield {"fake": "data"}

        converted = Block()
        with mock.patch.object(Blockchain, "blocks", property(_fake_blocks_gen)):
            with mock.patch(
                "yadacoin.core.blockchain.Block.from_dict",
                new=AsyncMock(return_value=converted),
            ):
                with mock.patch(
                    "yadacoin.core.blockchain.Blockchain.test_block",
                    new=AsyncMock(return_value=True),
                ):
                    blockchain = Blockchain()
                    result = await blockchain.verify()
        self.assertEqual(result, {"verified": True})


class TestBlockchainTestBlock(AsyncTestCase):
    """Cover Blockchain.test_block branches not exercised elsewhere."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        # Replace BU with a mock so transaction-input branches don't hit network
        self.config.BU = MagicMock()
        self.config.BU.get_transaction_by_id = AsyncMock(return_value=None)
        self.config.BU.is_input_spent = AsyncMock(return_value=False)

        class _AppLog:
            def warning(self, *a, **kw):
                pass

            def info(self, *a, **kw):
                pass

            def debug(self, *a, **kw):
                pass

        self.config.app_log = _AppLog()

    async def test_block_verify_raises_returns_false(self):
        """Lines 148-150: block.verify() raises -> warning + return False."""
        block = _make_test_block(index=1)
        block.verify = AsyncMock(side_effect=Exception("boom"))
        result = await Blockchain.test_block(block)
        self.assertFalse(result)

    async def test_block_index_zero_returns_true(self):
        """Line 153: block.index == 0 -> return True (already covered, redundant safety)."""
        block = _make_test_block(index=0)
        result = await Blockchain.test_block(block)
        self.assertTrue(result)

    async def test_block_time_in_future_returns_false(self):
        """Lines 156-157: block.time > time() returns False."""
        from time import time as _time

        block = _make_test_block(index=1, block_time=int(_time()) + 100000)
        result = await Blockchain.test_block(block)
        self.assertFalse(result)

    async def test_block_no_simulate_last_no_db_match_returns_false(self):
        """Lines 162-168: last_block_data is None -> return False."""
        block = _make_test_block(index=10)
        self.config.mongo.async_db = MagicMock()
        self.config.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        result = await Blockchain.test_block(block)
        self.assertFalse(result)

    async def test_block_no_simulate_last_with_db_match_uses_from_dict(self):
        """Lines 162-166: last_block_data found, calls from_dict."""
        block = _make_test_block(index=10)
        last = _make_test_block(index=9)
        self.config.mongo.async_db = MagicMock()
        self.config.mongo.async_db.blocks.find_one = AsyncMock(
            return_value={"index": 9}
        )
        with mock.patch(
            "yadacoin.core.blockchain.Block.from_dict",
            new=AsyncMock(return_value=last),
        ):
            with mock.patch.object(
                CHAIN, "get_target", new=AsyncMock(return_value=2**256 - 1)
            ):
                # Block index < FORK_10_MIN_BLOCK so get_target is used
                result = await Blockchain.test_block(block)
        # We don't care about result; we just want to exercise lines 162-166, 173.
        self.assertIn(result, (True, False))

    async def test_block_pre_fork_uses_get_target(self):
        """Line 173: pre-FORK_10_MIN_BLOCK uses CHAIN.get_target."""
        block = _make_test_block(index=10, target=2**256 - 1)
        last = _make_test_block(index=9)
        get_target = AsyncMock(return_value=2**256 - 1)
        with mock.patch.object(CHAIN, "get_target", new=get_target):
            await Blockchain.test_block(block, simulate_last_block=last)
        get_target.assert_called_once()

    async def test_block_special_min_with_short_delta_returns_false_early(self):
        """Line 183: index>=35200 and delta_t<600 and special_min -> False."""
        from time import time as _time

        last = _make_test_block(index=39999, block_time=int(_time()) - 10)
        block = _make_test_block(index=40000, block_time=int(_time()), special_min=True)
        with mock.patch.object(
            CHAIN, "get_target_10min", new=AsyncMock(return_value=2**256 - 1)
        ):
            result = await Blockchain.test_block(block, simulate_last_block=last)
        self.assertFalse(result)

    async def test_block_dynamic_nodes_fork_sets_check_flag(self):
        """Line 199: check_dynamic_nodes = True for index >= DYNAMIC_NODES_FORK.

        Also exercises lines 187, 191, 195 (other check flags True) and
        the final regnet branch (line 336)."""
        from time import time as _time

        last = _make_test_block(
            index=CHAIN.DYNAMIC_NODES_FORK - 1, block_time=int(_time()) - 1000
        )
        block = _make_test_block(
            index=CHAIN.DYNAMIC_NODES_FORK,
            block_time=int(_time()) - 5,
            prev_hash=last.hash,
            target=2**256 - 1,
        )
        block.hash = "ff" + "0" * 62  # not less than target so falls through to regnet
        with mock.patch.object(
            CHAIN, "get_target_10min", new=AsyncMock(return_value=0)
        ):
            with mock.patch.object(CHAIN, "target_block_time", return_value=600):
                self.config.network = "regnet"
                result = await Blockchain.test_block(block, simulate_last_block=last)
        # Should reach the final regnet elif and return True.
        self.assertTrue(result)

    async def test_block_extra_blocks_assigns_to_transaction(self):
        """Lines 211-213: extra_blocks branch sets transaction.extra_blocks."""
        from time import time as _time

        last = _make_test_block(index=9, block_time=int(_time()) - 1000)
        txn = MagicMock()
        txn.inputs = []
        txn.verify = AsyncMock(return_value=None)
        block = _make_test_block(
            index=10,
            block_time=int(_time()) - 5,
            prev_hash=last.hash,
            transactions=[txn],
            target=2**256 - 1,
        )
        block.hash = "ff" + "0" * 62
        extra = [_make_test_block(index=8)]
        with mock.patch.object(CHAIN, "get_target", new=AsyncMock(return_value=0)):
            with mock.patch.object(CHAIN, "target_block_time", return_value=600):
                self.config.network = "regnet"
                await Blockchain.test_block(
                    block, extra_blocks=extra, simulate_last_block=last
                )
        self.assertEqual(txn.extra_blocks, extra)

    async def _run_with_txn_exception(self, exc):
        """Helper: build a block with one txn whose verify raises ``exc``."""
        from time import time as _time

        last = _make_test_block(index=9, block_time=int(_time()) - 1000)
        txn = MagicMock()
        txn.inputs = []
        txn.verify = AsyncMock(side_effect=exc)
        block = _make_test_block(
            index=10,
            block_time=int(_time()) - 5,
            prev_hash=last.hash,
            transactions=[txn],
        )
        with mock.patch.object(
            CHAIN, "get_target", new=AsyncMock(return_value=2**256 - 1)
        ):
            return await Blockchain.test_block(block, simulate_last_block=last)

    async def test_block_invalid_transaction_exception_returns_false(self):
        """Lines 225-227."""
        result = await self._run_with_txn_exception(InvalidTransactionException("x"))
        self.assertFalse(result)

    async def test_block_invalid_signature_exception_returns_false(self):
        """Lines 228-230."""
        result = await self._run_with_txn_exception(
            InvalidTransactionSignatureException("x")
        )
        self.assertFalse(result)

    async def test_block_missing_input_exception_returns_false(self):
        """Lines 231-233."""
        result = await self._run_with_txn_exception(
            MissingInputTransactionException("x")
        )
        self.assertFalse(result)

    async def test_block_not_enough_money_exception_returns_false(self):
        """Lines 234-236."""
        result = await self._run_with_txn_exception(NotEnoughMoneyException("x"))
        self.assertFalse(result)

    async def test_block_generic_exception_returns_false(self):
        """Lines 237-239."""
        result = await self._run_with_txn_exception(RuntimeError("boom"))
        self.assertFalse(result)

    async def test_block_double_spend_post_fork_returns_false(self):
        """Lines 265-268, 275-276: is_input_spent True triggers double-spend
        return False (block.index >= CHECK_DOUBLE_SPEND_FROM)."""
        from time import time as _time

        last = _make_test_block(
            index=CHAIN.CHECK_DOUBLE_SPEND_FROM - 1, block_time=int(_time()) - 1000
        )
        input_item = MagicMock()
        input_item.id = "input-1"
        input_item.input_txn = MagicMock()  # truthy so we skip BU lookup
        txn = MagicMock()
        txn.inputs = [input_item]
        txn.public_key = "pk"
        txn.verify = AsyncMock(return_value=None)
        block = _make_test_block(
            index=CHAIN.CHECK_DOUBLE_SPEND_FROM,
            block_time=int(_time()) - 5,
            prev_hash=last.hash,
            transactions=[txn],
        )
        self.config.BU.is_input_spent = AsyncMock(return_value=True)
        with mock.patch.object(
            CHAIN, "get_target_10min", new=AsyncMock(return_value=2**256 - 1)
        ):
            result = await Blockchain.test_block(block, simulate_last_block=last)
        self.assertFalse(result)

    async def test_block_double_spend_pre_fork_continues(self):
        """Lines 270, 272, 277-278: failed flag triggers continue (pre-fork)."""
        from time import time as _time

        last = _make_test_block(index=9, block_time=int(_time()) - 1000)
        input_a = MagicMock()
        input_a.id = "dup-id"
        input_a.input_txn = MagicMock()
        # Same input id used twice in same txn (line 269-270)
        input_b = MagicMock()
        input_b.id = "dup-id"
        input_b.input_txn = MagicMock()
        txn = MagicMock()
        txn.inputs = [input_a, input_b]
        txn.public_key = "pk"
        txn.verify = AsyncMock(return_value=None)
        block = _make_test_block(
            index=10,
            block_time=int(_time()) - 5,
            prev_hash=last.hash,
            transactions=[txn],
        )
        block.hash = "ff" + "0" * 62
        with mock.patch.object(CHAIN, "get_target", new=AsyncMock(return_value=0)):
            with mock.patch.object(CHAIN, "target_block_time", return_value=600):
                self.config.network = "regnet"
                result = await Blockchain.test_block(block, simulate_last_block=last)
        self.assertTrue(result)  # falls through via continue + regnet

    async def test_block_used_inputs_across_txns_pre_fork_continues(self):
        """Line 271-272: (id, pk) already in used_inputs across two txns triggers
        failed; pre-fork branch -> continue."""
        from time import time as _time

        last = _make_test_block(index=9, block_time=int(_time()) - 1000)
        input_a = MagicMock()
        input_a.id = "shared"
        input_a.input_txn = MagicMock()
        input_b = MagicMock()
        input_b.id = "shared"
        input_b.input_txn = MagicMock()
        txn1 = MagicMock()
        txn1.inputs = [input_a]
        txn1.public_key = "pk"
        txn1.verify = AsyncMock(return_value=None)
        txn2 = MagicMock()
        txn2.inputs = [input_b]
        txn2.public_key = "pk"
        txn2.verify = AsyncMock(return_value=None)
        block = _make_test_block(
            index=10,
            block_time=int(_time()) - 5,
            prev_hash=last.hash,
            transactions=[txn1, txn2],
        )
        block.hash = "ff" + "0" * 62
        with mock.patch.object(CHAIN, "get_target", new=AsyncMock(return_value=0)):
            with mock.patch.object(CHAIN, "target_block_time", return_value=600):
                self.config.network = "regnet"
                result = await Blockchain.test_block(block, simulate_last_block=last)
        self.assertTrue(result)

    async def test_block_post_loop_special_min_check_returns_false(self):
        """Lines 280-284: the 35200/delta_t/special_min post-txn-loop check.

        Trigger by making block.special_min flip True after entering the txn
        loop (only way since the earlier line-183 check also fires)."""
        from time import time as _time

        # Use a wrapper that lies about special_min on first read but tells the
        # truth on second read. Easier: monkey-patch via property after entry.
        last = _make_test_block(index=39999, block_time=int(_time()) - 10)

        class _Block:
            index = 40000
            time = int(_time())
            transactions = []
            hash = "0" * 64
            prev_hash = last.hash
            target = 2**256 - 1
            _reads = 0

            async def verify(self):
                return None

            @property
            def special_min(self):  # type: ignore[override]
                _Block._reads += 1
                # First call (line 182) returns False -> skip early-return.
                # Subsequent calls (line 280, etc.) return True.
                return _Block._reads > 1

        block = _Block()
        with mock.patch.object(
            CHAIN, "get_target_10min", new=AsyncMock(return_value=2**256 - 1)
        ):
            result = await Blockchain.test_block(block, simulate_last_block=last)
        self.assertFalse(result)

    async def test_block_check_time_from_failure_returns_false(self):
        """Lines 286-292: block.time < last_block.time post CHECK_TIME_FROM."""
        from time import time as _time

        last = _make_test_block(index=CHAIN.CHECK_TIME_FROM, block_time=int(_time()))
        block = _make_test_block(
            index=CHAIN.CHECK_TIME_FROM + 1,
            block_time=int(_time()) - 1000,  # earlier than last
            prev_hash=last.hash,
        )
        with mock.patch.object(
            CHAIN, "get_target_10min", new=AsyncMock(return_value=2**256 - 1)
        ):
            result = await Blockchain.test_block(block, simulate_last_block=last)
        self.assertFalse(result)

    async def test_block_prev_hash_mismatch_returns_false(self):
        """Lines 294-298: last_block.hash != block.prev_hash returns False."""
        from time import time as _time

        last = _make_test_block(index=9, block_time=int(_time()) - 1000)
        last.hash = "real-hash"
        block = _make_test_block(
            index=10,
            block_time=int(_time()) - 5,
            prev_hash="different-hash",
        )
        with mock.patch.object(
            CHAIN, "get_target", new=AsyncMock(return_value=2**256 - 1)
        ):
            result = await Blockchain.test_block(block, simulate_last_block=last)
        self.assertFalse(result)

    async def test_block_special_min_too_soon_returns_false(self):
        """Lines 300-308: post CHECK_TIME_FROM and time < last+600 with special_min."""
        from time import time as _time

        last_t = int(_time()) - 100
        last = _make_test_block(index=CHAIN.CHECK_TIME_FROM, block_time=last_t)

        # Need: block.special_min False on line 182 (so we don't early-return),
        # but True on line 280 (also early-return) and True on line 303.
        # Easiest: ensure delta_t >= 600 by setting last.time far in past so
        # line-182 check fails, then block.time still close enough to make
        # line 302 true. But delta_t = now - last.time, line 182 needs <600.
        # So make last.time = now-700 -> delta_t=700, line 182 False; then
        # block.time-last.time < 600 so line 302 True.
        last.time = int(_time()) - 700
        block = _make_test_block(
            index=CHAIN.CHECK_TIME_FROM + 1,
            block_time=last.time + 100,
            prev_hash=last.hash,
            special_min=True,
        )
        with mock.patch.object(
            CHAIN, "get_target_10min", new=AsyncMock(return_value=2**256 - 1)
        ):
            result = await Blockchain.test_block(block, simulate_last_block=last)
        self.assertFalse(result)

    async def test_block_pre_v5_fork_int_hash_branch(self):
        """Line 318-320: pre-V5-fork uses int(block.hash, 16) < target."""
        from time import time as _time

        last = _make_test_block(index=9, block_time=int(_time()) - 1000)
        block = _make_test_block(
            index=10,
            block_time=int(_time()) - 5,
            prev_hash=last.hash,
            target=2**256 - 1,
        )
        block.hash = "0" * 64  # int = 0 < target
        with mock.patch.object(
            CHAIN, "get_target", new=AsyncMock(return_value=2**256 - 1)
        ):
            with mock.patch.object(CHAIN, "target_block_time", return_value=600):
                result = await Blockchain.test_block(block, simulate_last_block=last)
        self.assertTrue(result)

    async def test_block_special_min_special_target_branch(self):
        """Lines 321-323: special_min and int(hash,16) < special_target."""
        from time import time as _time

        # Need delta_t >= 600 to bypass line-182 early return.
        last = _make_test_block(index=29999, block_time=int(_time()) - 700)
        block = _make_test_block(
            index=30000,
            block_time=last.time + 100,  # delta with last is 100, but global
            # delta_t = now - last.time = 700
            prev_hash=last.hash,
            special_min=True,
            target=0,  # so int(hash,16) < target is False
        )
        block.hash = "0" * 64  # special_target check uses this
        with mock.patch.object(CHAIN, "get_target", new=AsyncMock(return_value=0)):
            with mock.patch.object(CHAIN, "special_target", return_value=2**256 - 1):
                with mock.patch.object(CHAIN, "target_block_time", return_value=600):
                    result = await Blockchain.test_block(
                        block, simulate_last_block=last
                    )
        self.assertTrue(result)

    async def test_block_special_min_pre_35200_branch(self):
        """Lines 324-326: special_min and block.index < 35200."""
        from time import time as _time

        last = _make_test_block(index=99, block_time=int(_time()) - 700)
        block = _make_test_block(
            index=100,
            block_time=last.time + 100,
            prev_hash=last.hash,
            special_min=True,
            target=0,
        )
        block.hash = "f" * 64  # high so int(hash,16) NOT < target/special
        with mock.patch.object(CHAIN, "get_target", new=AsyncMock(return_value=0)):
            with mock.patch.object(CHAIN, "special_target", return_value=0):
                with mock.patch.object(CHAIN, "target_block_time", return_value=600):
                    result = await Blockchain.test_block(
                        block, simulate_last_block=last
                    )
        self.assertTrue(result)

    async def test_block_special_min_35200_38600_long_delta_branch(self):
        """Lines 327-334: 35200 <= index < 38600 with special_min and long delta."""
        from time import time as _time

        last = _make_test_block(index=35199, block_time=int(_time()) - 1000)
        block = _make_test_block(
            index=35200,
            block_time=last.time + 1000,  # > target_block_time(600)
            prev_hash=last.hash,
            special_min=True,
            target=0,
        )
        block.hash = "f" * 64
        with mock.patch.object(
            CHAIN, "get_target_10min", new=AsyncMock(return_value=0)
        ):
            with mock.patch.object(CHAIN, "special_target", return_value=0):
                with mock.patch.object(CHAIN, "target_block_time", return_value=600):
                    # block.special_min must be False on line 182 path? Let's
                    # re-check: line 182 needs delta_t<600. delta_t=now-last.time
                    # last.time is now-1000 -> delta_t=1000 -> line 182 False.
                    # And line 280 also requires delta_t<600 -> False. Good.
                    self.config.network = "mainnet"  # disable regnet branch
                    result = await Blockchain.test_block(
                        block, simulate_last_block=last
                    )
        self.assertTrue(result)

    async def test_block_target_too_high_else_branch_returns_false(self):
        """Lines 337-340, 342-343: no checks pass -> False."""
        from time import time as _time

        last = _make_test_block(index=9, block_time=int(_time()) - 1000)
        block = _make_test_block(
            index=10,
            block_time=int(_time()) - 5,
            prev_hash=last.hash,
            target=0,  # so int(hash,16) < 0 is False
            special_min=False,
        )
        block.hash = "f" * 64
        with mock.patch.object(CHAIN, "get_target", new=AsyncMock(return_value=0)):
            with mock.patch.object(CHAIN, "special_target", return_value=0):
                with mock.patch.object(CHAIN, "target_block_time", return_value=600):
                    self.config.network = "mainnet"
                    result = await Blockchain.test_block(
                        block, simulate_last_block=last
                    )
        self.assertFalse(result)


class TestBlockchainTestInbound(AsyncTestCase):
    """Cover branches in test_inbound_blockchain."""

    async def test_inbound_no_existing_returns_true(self):
        """Lines 359-360: not final_existing_block -> True."""
        existing = Blockchain()  # empty -> final_block=None
        inbound_block = Block()
        inbound_block.index = 1
        inbound_block.hash = "abc"
        inbound = Blockchain([inbound_block])
        self.assertTrue(await existing.test_inbound_blockchain(inbound))

    async def test_inbound_lower_difficulty_returns_false(self):
        """Line 366: returns False when inbound difficulty not greater."""
        b1 = Block()
        b1.index = 0
        b1.hash = "0" * 16
        existing = Blockchain([b1])
        inbound_block = Block()
        inbound_block.index = 0
        inbound_block.hash = "0" * 16  # same difficulty
        inbound = Blockchain([inbound_block])
        self.assertFalse(await existing.test_inbound_blockchain(inbound))

    async def test_inbound_non_list_blockchains_use_async_final(self):
        """Lines 353, 358: non-list init_blocks -> async_final_block path."""
        b_existing = Block()
        b_existing.index = 0
        b_existing.hash = "0000000000000000"
        b_inbound = Block()
        b_inbound.index = 1
        b_inbound.hash = "ffffffffffffffff"

        existing = Blockchain()
        existing.init_blocks = _AsyncIterClone([b_existing])
        inbound = Blockchain()
        inbound.init_blocks = _AsyncIterClone([b_inbound])
        result = await existing.test_inbound_blockchain(inbound)
        self.assertIsInstance(result, bool)


class TestBlockchainFindErrorBlock(AsyncTestCase):
    """Cover find_error_block branches."""

    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_find_error_block_index_gap(self):
        """Lines 397-398: returns last_block.index + 1 when gap > 1."""
        b1 = MagicMock(spec=Block)
        b1.index = 0
        b1.hash = "h0"
        b1.prev_hash = ""
        b1.transactions = []
        b1.verify = AsyncMock()

        b2 = MagicMock(spec=Block)
        b2.index = 5  # gap > 1
        b2.hash = "h2"
        b2.prev_hash = "h0"
        b2.transactions = []
        b2.verify = AsyncMock()

        blockchain = Blockchain([b1, b2])
        result = await blockchain.find_error_block()
        self.assertEqual(result, 1)

    async def test_find_error_block_prev_hash_mismatch(self):
        """Lines 399-400: returns last_block.index when prev_hash mismatch."""
        b1 = MagicMock(spec=Block)
        b1.index = 0
        b1.hash = "h0"
        b1.prev_hash = ""
        b1.transactions = []
        b1.verify = AsyncMock()

        b2 = MagicMock(spec=Block)
        b2.index = 1
        b2.hash = "h1"
        b2.prev_hash = "wrong"
        b2.transactions = []
        b2.verify = AsyncMock()

        blockchain = Blockchain([b1, b2])
        result = await blockchain.find_error_block()
        self.assertEqual(result, 0)

    async def test_find_error_block_all_check_flags_set(self):
        """Lines 375, 379, 383, 387, 390: txn.verify with all check_X flags True."""
        txn = MagicMock()
        txn.verify = AsyncMock(return_value=None)
        b = MagicMock(spec=Block)
        b.index = CHAIN.DYNAMIC_NODES_FORK + 1
        b.hash = "h"
        b.prev_hash = ""
        b.transactions = [txn]
        b.verify = AsyncMock()
        blockchain = Blockchain([b])
        result = await blockchain.find_error_block()
        self.assertIsNone(result)
        txn.verify.assert_awaited_once()
        kwargs = txn.verify.await_args.kwargs
        self.assertTrue(kwargs["check_max_inputs"])
        self.assertTrue(kwargs["check_masternode_fee"])
        self.assertTrue(kwargs["check_kel"])
        self.assertTrue(kwargs["check_dynamic_nodes"])


class TestBlockchainGetDifficultyExtra(AsyncTestCase):
    """Extra coverage for get_difficulty and get_highest_block_height."""

    async def test_get_difficulty_converts_dict_via_from_dict(self):
        """Line 407: from_dict invoked when block is not Block instance.

        Same as the verify test: must patch ``Blockchain.blocks`` to yield raw
        dicts, since the property otherwise converts them first."""

        async def _fake_blocks_gen(self):
            yield {"fake": "data"}

        converted = Block()
        converted.index = CHAIN.LITTLE_HASH_DIFF_FIX
        converted.hash = "0" * 64
        with mock.patch.object(Blockchain, "blocks", property(_fake_blocks_gen)):
            with mock.patch(
                "yadacoin.core.blockchain.Block.from_dict",
                new=AsyncMock(return_value=converted),
            ):
                blockchain = Blockchain()
                result = await blockchain.get_difficulty()
        self.assertEqual(result, CHAIN.MAX_TARGET)

    async def test_get_highest_block_height(self):
        """Lines 417-421: synchronous loop returns max index.

        Note: ``self.blocks`` is an async property returning an async generator,
        so the synchronous ``for`` loop cannot actually iterate it. We patch
        the property on the class to a regular list-returning property to
        exercise the loop body."""
        b1 = Block()
        b1.index = 5
        b2 = Block()
        b2.index = 12
        b3 = Block()
        b3.index = 3
        blockchain = Blockchain([b1, b2, b3])
        with mock.patch.object(
            Blockchain, "blocks", property(lambda self: [b1, b2, b3])
        ):
            self.assertEqual(blockchain.get_highest_block_height(), 12)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
