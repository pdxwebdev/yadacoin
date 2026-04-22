"""
Coverage tests for yadacoin.core.miningpoolpayout.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.miningpoolpayout import (
    NonMatchingDifficultyException,
    PartialPayoutException,
    PoolPayer,
)
from yadacoin.core.transaction import NotEnoughMoneyException

from ..test_setup import AsyncTestCase


class _AsyncIter:
    """Async iterable supporting chainable .sort()."""

    def __init__(self, items):
        self._items = items

    def sort(self, *a, **k):
        return self

    def __aiter__(self):
        async def gen():
            for it in self._items:
                yield it

        return gen()


def _mk_config(address="addr1", debug=False):
    cfg = MagicMock()
    cfg.address = address
    cfg.public_key = "pk"
    cfg.private_key = "priv"
    cfg.debug = debug
    cfg.payout_frequency = 2
    cfg.pool_take = 0.1
    cfg.LatestBlock = MagicMock()
    cfg.LatestBlock.block.index = 100
    cfg.address_is_valid = MagicMock(return_value=True)
    cfg.peer = MagicMock()
    cfg.nodeShared = MagicMock()
    cfg.nodeShared.write_params = AsyncMock()
    cfg.nodeClient = MagicMock()
    cfg.nodeClient.retry_messages = {}
    cfg.mongo = MagicMock()
    cfg.mongo.async_db = MagicMock()
    return cfg


def _mk_payer(cfg=None):
    with patch(
        "yadacoin.core.miningpoolpayout.Config", return_value=cfg or _mk_config()
    ):
        return PoolPayer()


def _mk_block(index=10, address="addr1", coinbase_value=50):
    block = MagicMock()
    block.index = index
    coinbase = MagicMock()
    out = MagicMock()
    out.to = address
    out.value = coinbase_value
    coinbase.outputs = [out]
    coinbase.transaction_signature = f"sig{index}"
    block.get_coinbase = MagicMock(return_value=coinbase)
    return block


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit(AsyncTestCase):
    async def test_init(self):
        cfg = _mk_config()
        with patch("yadacoin.core.miningpoolpayout.Config", return_value=cfg):
            p = PoolPayer()
        self.assertIs(p.config, cfg)


# ---------------------------------------------------------------------------
# get_difficulty
# ---------------------------------------------------------------------------


class TestGetDifficulty(AsyncTestCase):
    async def test_get_difficulty(self):
        from yadacoin.core.chain import CHAIN

        p = _mk_payer()
        blocks = [{"hash": "00" + "f" * 62}, {"hash": "01" + "f" * 62}]
        d = p.get_difficulty(blocks)
        expected = sum(CHAIN.MAX_TARGET - int(b["hash"], 16) for b in blocks)
        self.assertEqual(d, expected)


# ---------------------------------------------------------------------------
# already_used
# ---------------------------------------------------------------------------


class TestAlreadyUsed(AsyncTestCase):
    async def test_already_used_returns_list(self):
        p = _mk_payer()
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter([{"x": 1}, {"x": 2}])
        )
        txn = MagicMock(transaction_signature="sig")
        r = await p.already_used(txn)
        self.assertEqual(r, [{"x": 1}, {"x": 2}])

    async def test_already_used_empty(self):
        p = _mk_payer()
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter([])
        )
        r = await p.already_used(MagicMock(transaction_signature="s"))
        self.assertEqual(r, [])


# ---------------------------------------------------------------------------
# broadcast_transaction
# ---------------------------------------------------------------------------


class TestBroadcastTransaction(AsyncTestCase):
    async def test_broadcast_with_protocol_v2(self):
        p = _mk_payer()
        peer = MagicMock()
        peer.peer.protocol_version = 2
        peer.peer.rid = "rid"

        async def _gen():
            yield peer

        p.config.peer.get_sync_peers = MagicMock(return_value=_gen())
        txn = MagicMock(transaction_signature="ts")
        txn.to_dict = MagicMock(return_value={"a": 1})
        await p.broadcast_transaction(txn)
        p.config.nodeShared.write_params.assert_awaited()
        self.assertIn(("rid", "newtxn", "ts"), p.config.nodeClient.retry_messages)

    async def test_broadcast_with_protocol_v1(self):
        p = _mk_payer()
        peer = MagicMock()
        peer.peer.protocol_version = 1

        async def _gen():
            yield peer

        p.config.peer.get_sync_peers = MagicMock(return_value=_gen())
        txn = MagicMock(transaction_signature="ts")
        txn.to_dict = MagicMock(return_value={})
        await p.broadcast_transaction(txn)
        self.assertEqual(p.config.nodeClient.retry_messages, {})


# ---------------------------------------------------------------------------
# get_share_list_for_height
# ---------------------------------------------------------------------------


class TestGetShareListForHeight(AsyncTestCase):
    async def test_no_shares_returns_false(self):
        p = _mk_payer()
        p.config.mongo.async_db.shares.find = MagicMock(return_value=_AsyncIter([]))
        r = await p.get_share_list_for_height(10)
        self.assertFalse(r)

    async def test_invalid_address_raises(self):
        p = _mk_payer()
        p.config.address_is_valid = MagicMock(return_value=False)
        p.config.mongo.async_db.shares.find = MagicMock(
            return_value=_AsyncIter([{"address": "bad", "hash": "00ff"}])
        )
        p.config.mongo.async_db.shares.delete_many = AsyncMock()
        with self.assertRaises(Exception):
            await p.get_share_list_for_height(10)
        p.config.mongo.async_db.shares.delete_many.assert_awaited()

    async def test_success_returns_shares(self):
        p = _mk_payer()
        shares_in = [
            {"address": "addrA.worker", "hash": "00ff" + "0" * 60},
            {"address": "addrB", "hash": "01ff" + "0" * 60},
        ]
        p.config.mongo.async_db.shares.find = MagicMock(
            return_value=_AsyncIter(shares_in)
        )
        r = await p.get_share_list_for_height(10)
        self.assertIn("addrA", r)
        self.assertIn("addrB", r)
        self.assertAlmostEqual(sum(v["payout_share"] for v in r.values()), 1.0)

    async def test_non_matching_difficulty_raises(self):
        """Force the add_up != total branch by making get_difficulty return inconsistent values."""
        p = _mk_payer()
        shares_in = [{"address": "addrA", "hash": "00ff" + "0" * 60}]
        p.config.mongo.async_db.shares.find = MagicMock(
            return_value=_AsyncIter(shares_in)
        )
        # First call is for total, second for per-address
        call = {"n": 0}
        p.get_difficulty

        def _diff(blocks):
            call["n"] += 1
            return 100 if call["n"] == 1 else 50

        p.get_difficulty = _diff
        with self.assertRaises(NonMatchingDifficultyException):
            await p.get_share_list_for_height(10)


# ---------------------------------------------------------------------------
# do_payout
# ---------------------------------------------------------------------------


class TestDoPayout(AsyncTestCase):
    async def _setup_basic(self, cfg=None, debug=False):
        cfg = cfg or _mk_config(debug=debug)
        p = _mk_payer(cfg)
        return p, cfg

    async def test_no_blocks_returns(self):
        p, cfg = await self._setup_basic()
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.blocks.aggregate = MagicMock(return_value=_AsyncIter([]))
        await p.do_payout()

    async def test_already_paid_height_passed(self):
        p, cfg = await self._setup_basic()
        cfg.mongo.async_db.blocks.aggregate = MagicMock(return_value=_AsyncIter([]))
        await p.do_payout(already_paid_height={"index": 5})

    async def test_skip_block_with_wrong_address(self):
        """Coinbase outputs[0].to mismatch -> continue."""
        p, cfg = await self._setup_basic(debug=True)
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter([{"index": 10, "id": "i", "hash": "h"}])
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        block = _mk_block(index=10, address="other")
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(return_value=block),
        ):
            await p.do_payout()

    async def test_breaks_when_enough_ready_blocks(self):
        """ready_blocks length >= payout_frequency triggers break -> do_payout=True."""
        p, cfg = await self._setup_basic(debug=True)
        cfg.payout_frequency = 1
        cfg.LatestBlock.block.index = 100
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.share_payout.insert_one = AsyncMock()
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(side_effect=[{"x": 1}, {"x": 2}])
        b1 = _mk_block(index=10)
        b2 = _mk_block(index=11)
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=[b1, b2]),
        ):
            # already_used returns truthy -> deletes and continues
            p.already_used = AsyncMock(return_value=[1])
            cfg.mongo.async_db.shares.delete_many = AsyncMock()
            await p.do_payout()
        cfg.mongo.async_db.shares.delete_many.assert_awaited()

    async def test_existing_with_pending_returns(self):
        p, cfg = await self._setup_basic()
        cfg.payout_frequency = 1
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(
            side_effect=[
                None,  # initial check
                {"txn": {"a": 1}},  # for existing per-block
            ]
        )
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        b1 = _mk_block(index=10)
        b2 = _mk_block(index=11)
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=[b1, b2]),
        ):
            p.already_used = AsyncMock(return_value=[])
            cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(
                return_value={"pending": True}
            )
            await p.do_payout()

    async def test_existing_rebroadcasts(self):
        p, cfg = await self._setup_basic(debug=True)
        cfg.payout_frequency = 1
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(
            side_effect=[
                None,
                {"txn": {"a": 1}},
            ]
        )
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        b1 = _mk_block(index=10)
        b2 = _mk_block(index=11)
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=[b1, b2]),
        ), patch(
            "yadacoin.core.miningpoolpayout.Transaction.from_dict",
            return_value=MagicMock(to_dict=MagicMock(return_value={})),
        ):
            p.already_used = AsyncMock(return_value=[])
            cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(
                return_value=None
            )
            cfg.mongo.async_db.miner_transactions.insert_one = AsyncMock()
            p.broadcast_transaction = AsyncMock()
            await p.do_payout()
        p.broadcast_transaction.assert_awaited()

    async def test_get_share_list_keyerror(self):
        p, cfg = await self._setup_basic()
        cfg.payout_frequency = 1
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(10), _mk_block(11)]),
        ):
            p.already_used = AsyncMock(return_value=[])
            p.get_share_list_for_height = AsyncMock(side_effect=KeyError("k"))
            await p.do_payout()

    async def test_get_share_list_generic_exception(self):
        p, cfg = await self._setup_basic()
        cfg.payout_frequency = 1
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(10), _mk_block(11)]),
        ):
            p.already_used = AsyncMock(return_value=[])
            p.get_share_list_for_height = AsyncMock(side_effect=Exception("bad"))
            await p.do_payout()

    async def test_no_shares_continues(self):
        p, cfg = await self._setup_basic()
        cfg.payout_frequency = 1
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.share_payout.insert_one = AsyncMock()
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(10), _mk_block(11)]),
        ):
            p.already_used = AsyncMock(return_value=[])
            p.get_share_list_for_height = AsyncMock(return_value=False)
            await p.do_payout()
        # ready_blocks present but outputs empty -> share_payout.insert_one called
        cfg.mongo.async_db.share_payout.insert_one.assert_awaited()

    async def test_address_changed_returns(self):
        """Second coinbase address check (line 166) returns when mismatch."""
        p, cfg = await self._setup_basic()
        cfg.payout_frequency = 1
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})

        # First (won) block: ready_blocks gets it (initial loop call must show good)
        # In payout loop: 4 get_coinbase() calls; the 4th (line 162) returns bad
        block = MagicMock()
        block.index = 10
        good = MagicMock()
        gout = MagicMock()
        gout.to = cfg.address
        gout.value = 50
        good.outputs = [gout]
        good.transaction_signature = "sig10"
        bad = MagicMock()
        bout = MagicMock()
        bout.to = "different"
        bad.outputs = [bout]
        bad.transaction_signature = "sig10"
        block.get_coinbase = MagicMock(side_effect=[good, good, bad])
        block2 = _mk_block(index=11)

        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=[block, block2]),
        ):
            p.already_used = AsyncMock(return_value=[])
            p.get_share_list_for_height = AsyncMock(
                return_value={"a": {"payout_share": 1.0}}
            )
            await p.do_payout()

    async def test_partial_payout_exception(self):
        p, cfg = await self._setup_basic(debug=True)
        cfg.payout_frequency = 1
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(
            side_effect=[
                None,  # initial
                None,  # existing per-block (no rebroadcast)
                {"already": True},  # in shares loop -> raises PartialPayoutException
            ]
        )
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(10), _mk_block(11)]),
        ):
            p.already_used = AsyncMock(return_value=[])
            p.get_share_list_for_height = AsyncMock(
                return_value={"addr1": {"payout_share": 1.0}}
            )
            with self.assertRaises(PartialPayoutException):
                await p.do_payout()

    async def test_full_payout_success(self):
        p, cfg = await self._setup_basic(debug=True)
        cfg.payout_frequency = 1
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.share_payout.insert_one = AsyncMock()
        cfg.mongo.async_db.miner_transactions.insert_one = AsyncMock()
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        gen_txn = MagicMock(transaction_signature="payout_sig")
        gen_txn.to_dict = MagicMock(return_value={"t": 1})
        gen_txn.verify = AsyncMock()
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(10), _mk_block(11)]),
        ), patch(
            "yadacoin.core.miningpoolpayout.Transaction.generate",
            new=AsyncMock(return_value=gen_txn),
        ):
            p.already_used = AsyncMock(return_value=[])
            p.get_share_list_for_height = AsyncMock(
                return_value={"a1": {"payout_share": 1.0}}
            )
            p.broadcast_transaction = AsyncMock()
            await p.do_payout()
        p.broadcast_transaction.assert_awaited()
        gen_txn.verify.assert_awaited()

    async def test_not_enough_money_exception(self):
        p, cfg = await self._setup_basic(debug=True)
        cfg.payout_frequency = 1
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(10), _mk_block(11)]),
        ), patch(
            "yadacoin.core.miningpoolpayout.Transaction.generate",
            new=AsyncMock(side_effect=NotEnoughMoneyException("nope")),
        ):
            p.already_used = AsyncMock(return_value=[])
            p.get_share_list_for_height = AsyncMock(
                return_value={"a1": {"payout_share": 1.0}}
            )
            await p.do_payout()

    async def test_generate_generic_exception_then_verify_raises(self):
        """Transaction.generate raises generic Exception (debug branch),
        then `transaction` is undefined, so verify call NameErrors which is re-raised.
        """
        p, cfg = await self._setup_basic(debug=True)
        cfg.payout_frequency = 1
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(10), _mk_block(11)]),
        ), patch(
            "yadacoin.core.miningpoolpayout.Transaction.generate",
            new=AsyncMock(side_effect=Exception("oops")),
        ):
            p.already_used = AsyncMock(return_value=[])
            p.get_share_list_for_height = AsyncMock(
                return_value={"a1": {"payout_share": 1.0}}
            )
            with self.assertRaises(Exception):
                await p.do_payout()

    async def test_verify_raises(self):
        p, cfg = await self._setup_basic(debug=True)
        cfg.payout_frequency = 1
        cfg.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        gen_txn = MagicMock(transaction_signature="ps")
        gen_txn.verify = AsyncMock(side_effect=Exception("verifybad"))
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=[_mk_block(10), _mk_block(11)]),
        ), patch(
            "yadacoin.core.miningpoolpayout.Transaction.generate",
            new=AsyncMock(return_value=gen_txn),
        ):
            p.already_used = AsyncMock(return_value=[])
            p.get_share_list_for_height = AsyncMock(
                return_value={"a1": {"payout_share": 1.0}}
            )
            with self.assertRaises(Exception):
                await p.do_payout()
