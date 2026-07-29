"""Coverage tests for template-only pool payout settlement."""

from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.miningpoolpayout import NonMatchingDifficultyException, PoolPayer

from ..test_setup import AsyncTestCase


class _AsyncIter:
    def __init__(self, items):
        self._items = items

    def sort(self, *a, **k):
        return self

    def __aiter__(self):
        async def gen():
            for it in self._items:
                yield it

        return gen()


INCEPTION_ADDR = "1InceptionAddr"


def _mk_config(debug=False):
    cfg = MagicMock()
    cfg.address = "addr1"
    cfg.debug = debug
    cfg.payout_frequency = 2
    cfg.pool_take = 0.1
    cfg.pool_payout = True
    cfg.LatestBlock = MagicMock()
    cfg.LatestBlock.block.index = 100
    cfg.address_is_valid = MagicMock(return_value=True)
    cfg.mongo = MagicMock()
    cfg.mongo.async_db = MagicMock()
    cfg.inception = MagicMock()
    cfg.inception.public_key = "aa" * 33
    cfg.BU = MagicMock()
    cfg.BU.is_input_spent = AsyncMock(return_value=False)
    cfg.BU.get_transaction_by_id = AsyncMock(return_value=None)
    return cfg


def _mk_payer(cfg=None, inception_addr=INCEPTION_ADDR):
    with patch(
        "yadacoin.core.miningpoolpayout.Config", return_value=cfg or _mk_config()
    ):
        p = PoolPayer()
    p.pool_inception_address = MagicMock(return_value=inception_addr)
    return p


def _mk_coinbase(sig="sig10", value=50.0, prerotated="1Pre", inception=INCEPTION_ADDR):
    cb = MagicMock()
    out = MagicMock()
    out.to = prerotated
    out.value = value
    cb.outputs = [out]
    cb.transaction_signature = sig
    cb.prerotated_key_hash = prerotated
    cb.inception_public_key_hash = inception
    return cb


def _mk_block(index=10, coinbase=None):
    block = MagicMock()
    block.index = index
    block.get_coinbase = MagicMock(return_value=coinbase or _mk_coinbase(f"sig{index}"))
    return block


class TestHelpers(AsyncTestCase):
    async def test_pool_reward_value(self):
        p = _mk_payer()
        cb = _mk_coinbase(value=40.0, prerotated="1Pre")
        self.assertEqual(p.pool_reward_value(cb), 40.0)

    async def test_pool_reward_value_no_prerotated(self):
        p = _mk_payer()
        cb = _mk_coinbase()
        cb.prerotated_key_hash = ""
        self.assertEqual(p.pool_reward_value(cb), 0.0)

    async def test_is_pool_won_coinbase(self):
        p = _mk_payer()
        self.assertTrue(p.is_pool_won_coinbase(_mk_coinbase()))
        bad = _mk_coinbase(inception="1Other")
        self.assertFalse(p.is_pool_won_coinbase(bad))

    async def test_already_used(self):
        p = _mk_payer()
        p.config.BU.is_input_spent = AsyncMock(return_value=True)
        self.assertTrue(await p.already_used(_mk_coinbase(), "kel_pub"))
        p.config.BU.is_input_spent = AsyncMock(return_value=False)
        self.assertFalse(await p.already_used(_mk_coinbase(), "kel_pub"))
        self.assertFalse(await p.already_used(_mk_coinbase(), None))


class TestGetShareList(AsyncTestCase):
    async def test_no_shares(self):
        p = _mk_payer()
        p.config.mongo.async_db.shares.find = MagicMock(return_value=_AsyncIter([]))
        self.assertFalse(await p.get_share_list_for_height(10))

    async def test_success(self):
        p = _mk_payer()
        shares = [
            {"address": "a1", "hash": "0" * 64},
            {"address": "a1", "hash": "1" * 64},
        ]
        p.config.mongo.async_db.shares.find = MagicMock(return_value=_AsyncIter(shares))
        result = await p.get_share_list_for_height(10)
        self.assertIn("a1", result)
        self.assertAlmostEqual(result["a1"]["payout_share"], 1.0)

    async def test_non_matching_difficulty(self):
        p = _mk_payer()
        # Force mismatch by patching get_difficulty
        p.config.mongo.async_db.shares.find = MagicMock(
            return_value=_AsyncIter([{"address": "a1", "hash": "0" * 64}])
        )
        p.get_difficulty = MagicMock(side_effect=[100, 50])
        with self.assertRaises(NonMatchingDifficultyException):
            await p.get_share_list_for_height(10)


class TestCollectSettlement(AsyncTestCase):
    async def test_no_inception(self):
        p = _mk_payer(inception_addr=None)
        p.pool_inception_address = MagicMock(return_value=None)
        c, o, i = await p.collect_settlement("pk")
        self.assertEqual(c, [])

    async def test_not_enough_ready_blocks(self):
        p = _mk_payer()
        p.config.payout_frequency = 2
        p.config.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter([{"index": 10, "id": "i", "hash": "h"}])
        )
        p.config.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(10)),
        ):
            c, o, i = await p.collect_settlement("pk")
        self.assertEqual(c, [])

    async def test_collects_ready(self):
        p = _mk_payer()
        p.config.payout_frequency = 1
        p.config.LatestBlock.block.index = 100
        p.config.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(
                [
                    {"index": 10, "id": "i1", "hash": "h1"},
                    {"index": 11, "id": "i2", "hash": "h2"},
                ]
            )
        )
        p.config.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        b10 = _mk_block(10, _mk_coinbase("sig10", 50.0))
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(return_value=b10),
        ):
            p.already_used = AsyncMock(return_value=False)
            p.get_share_list_for_height = AsyncMock(
                return_value={"miner1": {"payout_share": 1.0}}
            )
            coinbases, outputs, indexes = await p.collect_settlement("pk")
        self.assertEqual(len(coinbases), 1)
        self.assertIn("miner1", outputs)
        self.assertEqual(indexes, [10])
        # pool_take 0.1 → 45 to miners
        self.assertAlmostEqual(outputs["miner1"], 45.0)


class TestDoPayoutDeprecated(AsyncTestCase):
    async def test_do_payout_is_noop(self):
        p = _mk_payer()
        result = await p.do_payout()
        self.assertIsNone(result)


class TestAttachTemplateSettlement(AsyncTestCase):
    async def test_disabled_when_pool_payout_false(self):
        p = _mk_payer()
        p.config.pool_payout = False
        result = await p.attach_template_settlement([], MagicMock(), MagicMock())
        self.assertIsNone(result)

    async def test_no_coinbases_returns_none(self):
        p = _mk_payer()
        p.collect_settlement = AsyncMock(return_value=([], {}, []))
        triplet = MagicMock()
        cb = _mk_coinbase()
        result = await p.attach_template_settlement([], triplet, cb)
        self.assertIsNone(result)

    async def test_attaches_pair(self):
        p = _mk_payer()
        cb = _mk_coinbase("sig_cb")
        u = MagicMock(transaction_signature="u_sig", inputs=[])
        c = MagicMock(transaction_signature="c_sig")
        p.collect_settlement = AsyncMock(
            return_value=([_mk_coinbase("sig10")], {"m1": 1.0}, [10])
        )
        p.build_template_payout_pair = AsyncMock(return_value=(u, c))
        pending = []
        meta = await p.attach_template_settlement(pending, MagicMock(), cb)
        self.assertEqual(meta["settled_indexes"], [10])
        self.assertEqual(len(pending), 2)
        self.assertIs(pending[0], u)
        self.assertIs(pending[1], c)


class TestRecordTemplateSettlement(AsyncTestCase):
    async def test_records_indexes(self):
        p = _mk_payer()
        p.config.mongo.async_db.share_payout.update_one = AsyncMock()
        p.config.mongo.async_db.shares.delete_many = AsyncMock()
        block = MagicMock(index=50, hash="bh")
        txn = MagicMock(transaction_signature="u_sig")
        txn.to_dict = MagicMock(return_value={"id": "u_sig"})
        block.transactions = [txn]
        meta = {"settled_indexes": [10, 11], "payout_txn_id": "u_sig"}
        await p.record_template_settlement(meta, block)
        self.assertEqual(p.config.mongo.async_db.share_payout.update_one.await_count, 2)
        self.assertEqual(p.config.mongo.async_db.shares.delete_many.await_count, 2)

    async def test_empty_meta(self):
        p = _mk_payer()
        p.config.mongo.async_db.share_payout.update_one = AsyncMock()
        await p.record_template_settlement(None, MagicMock())
        p.config.mongo.async_db.share_payout.update_one.assert_not_awaited()


class TestBuildTemplatePayoutPair(AsyncTestCase):
    async def test_missing_triplet_material(self):
        p = _mk_payer()
        triplet = MagicMock(
            kn2_private_key="",
            kn3_address="",
            coinbase_confirming=MagicMock(),
        )
        u, c = await p.build_template_payout_pair(
            triplet, _mk_coinbase(), [_mk_coinbase()], {"m": 1.0}
        )
        self.assertIsNone(u)
        self.assertIsNone(c)

    async def test_no_miner_outputs(self):
        p = _mk_payer()
        triplet = MagicMock(
            kn2_private_key="priv",
            kn2_public_key="aa" * 33,
            kn3_address="1Kn3",
            kn3_public_key="bb" * 33,
            kn3_private_key="priv3",
            kn4_address="1Kn4",
            kn5_address="1Kn5",
            coinbase_twice_prerotated="1Kn2",
            coinbase_prerotated="1Kn1",
            coinbase_confirming=MagicMock(counter=5),
            coinbase_inception_public_key_hash=INCEPTION_ADDR,
        )
        with patch(
            "yadacoin.core.miningpoolpayout.P2PKHBitcoinAddress.from_pubkey",
            return_value=type("A", (), {"__str__": lambda s: "1Kn2"})(),
        ):
            u, c = await p.build_template_payout_pair(
                triplet, _mk_coinbase(), [_mk_coinbase()], {}
            )
        self.assertIsNone(u)
