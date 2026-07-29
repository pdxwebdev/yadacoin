"""Coverage tests for template-only multi-batch pool payout settlement."""

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
    cfg.max_payout_batches_per_block = 20
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

    async def test_is_pool_won_coinbase(self):
        p = _mk_payer()
        self.assertTrue(p.is_pool_won_coinbase(_mk_coinbase()))
        self.assertFalse(p.is_pool_won_coinbase(_mk_coinbase(inception="1Other")))

    async def test_already_used(self):
        p = _mk_payer()
        p.config.BU.is_input_spent = AsyncMock(return_value=True)
        self.assertTrue(await p.already_used(_mk_coinbase(), "kel_pub"))
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
        p.config.mongo.async_db.shares.find = MagicMock(
            return_value=_AsyncIter([{"address": "a1", "hash": "0" * 64}])
        )
        p.get_difficulty = MagicMock(side_effect=[100, 50])
        with self.assertRaises(NonMatchingDifficultyException):
            await p.get_share_list_for_height(10)


class TestCollectSettlementBatches(AsyncTestCase):
    async def test_no_inception(self):
        p = _mk_payer()
        p.pool_inception_address = MagicMock(return_value=None)
        self.assertEqual(await p.collect_settlement_batches("pk"), [])

    async def test_not_enough_for_one_batch(self):
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
            p.already_used = AsyncMock(return_value=False)
            p.get_share_list_for_height = AsyncMock(
                return_value={"m": {"payout_share": 1.0}}
            )
            batches = await p.collect_settlement_batches("pk")
        self.assertEqual(batches, [])

    async def test_multiple_batches_when_behind(self):
        """12 ready wins + freq=2 → 6 batches (catch-up)."""
        p = _mk_payer()
        p.config.payout_frequency = 2
        p.config.max_payout_batches_per_block = 20
        p.config.LatestBlock.block.index = 200
        p.config.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        docs = [{"index": i, "id": f"i{i}", "hash": f"h{i}"} for i in range(10, 22)]
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(docs)
        )
        p.config.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})

        async def from_dict(d):
            # index comes from the find_one path — use side_effect on block
            return MagicMock()  # overridden below

        # Build distinct blocks per find_one call order
        blocks = [_mk_block(i, _mk_coinbase(f"sig{i}", 50.0)) for i in range(10, 22)]
        call_i = {"n": 0}

        async def from_dict_side(doc):
            b = blocks[call_i["n"]]
            call_i["n"] += 1
            return b

        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=from_dict_side),
        ):
            p.already_used = AsyncMock(return_value=False)
            p.get_share_list_for_height = AsyncMock(
                return_value={"miner1": {"payout_share": 1.0}}
            )
            batches = await p.collect_settlement_batches("pk")

        self.assertEqual(len(batches), 6)
        for coinbases, outputs, indexes in batches:
            self.assertEqual(len(coinbases), 2)
            self.assertEqual(len(indexes), 2)
            self.assertIn("miner1", outputs)
            # 2 * 50 * 0.9 = 90
            self.assertAlmostEqual(outputs["miner1"], 90.0)

    async def test_max_batches_cap(self):
        p = _mk_payer()
        p.config.payout_frequency = 2
        p.config.max_payout_batches_per_block = 2  # cap at 2 batches = 4 blocks
        p.config.LatestBlock.block.index = 200
        p.config.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        docs = [{"index": i, "id": f"i{i}", "hash": f"h{i}"} for i in range(10, 30)]
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter(docs)
        )
        p.config.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        blocks = [_mk_block(i, _mk_coinbase(f"sig{i}")) for i in range(10, 14)]
        call_i = {"n": 0}

        async def from_dict_side(doc):
            b = blocks[call_i["n"] % len(blocks)]
            call_i["n"] += 1
            return b

        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(side_effect=from_dict_side),
        ):
            p.already_used = AsyncMock(return_value=False)
            p.get_share_list_for_height = AsyncMock(
                return_value={"m": {"payout_share": 1.0}}
            )
            batches = await p.collect_settlement_batches("pk")
        self.assertEqual(len(batches), 2)

    async def test_collect_settlement_first_batch_only(self):
        p = _mk_payer()
        p.collect_settlement_batches = AsyncMock(
            return_value=[
                ([_mk_coinbase("a")], {"m": 1.0}, [10]),
                ([_mk_coinbase("b")], {"m": 2.0}, [11, 12]),
            ]
        )
        c, o, i = await p.collect_settlement("pk")
        self.assertEqual(i, [10])


class TestAttachTemplateSettlement(AsyncTestCase):
    async def test_disabled(self):
        p = _mk_payer()
        p.config.pool_payout = False
        self.assertIsNone(
            await p.attach_template_settlement([], MagicMock(), MagicMock())
        )

    async def test_multiple_batches_chained(self):
        p = _mk_payer()
        cb = _mk_coinbase("sig_cb")
        batch0 = ([_mk_coinbase("s1"), _mk_coinbase("s2")], {"m": 10.0}, [10, 11])
        batch1 = ([_mk_coinbase("s3"), _mk_coinbase("s4")], {"m": 20.0}, [12, 13])
        p.collect_settlement_batches = AsyncMock(return_value=[batch0, batch1])

        u0 = MagicMock(transaction_signature="u0", inputs=[], counter=3)
        c0 = MagicMock(transaction_signature="c0", counter=4)
        u1 = MagicMock(transaction_signature="u1", inputs=[], counter=5)
        c1 = MagicMock(transaction_signature="c1", counter=6)
        p.build_template_payout_pair = AsyncMock(side_effect=[(u0, c0), (u1, c1)])
        p._derive_key_material = MagicMock(
            side_effect=lambda *a, **k: {
                "private_key": "p",
                "chain_code": "c",
                "public_key": "aa" * 33,
                "address": f"addr{p._derive_key_material.call_count}",
            }
        )

        triplet = MagicMock(
            kn2_private_key="k2",
            kn2_public_key="pk2",
            kn2_chain_code="cc2",
            kn2_address="1Kn2",
            coinbase_twice_prerotated="1Kn2",
            coinbase_prerotated="1Kn1",
            coinbase_confirming=MagicMock(
                counter=2, inception_public_key_hash=INCEPTION_ADDR
            ),
            coinbase_inception_public_key_hash=INCEPTION_ADDR,
            signer_public_key="spk",
        )
        with patch("yadacoin.core.keyrotation._read_second_factor", return_value="sf"):
            pending = []
            meta = await p.attach_template_settlement(pending, triplet, cb)

        self.assertIsNotNone(meta)
        self.assertEqual(meta["settled_indexes"], [10, 11, 12, 13])
        self.assertEqual(meta["payout_txn_ids"], ["u0", "u1"])
        self.assertEqual(len(pending), 4)
        self.assertEqual(p.build_template_payout_pair.await_count, 2)
        # First batch may spend template coinbase; second must not.
        calls = p.build_template_payout_pair.await_args_list
        self.assertTrue(calls[0].kwargs.get("spend_template_coinbase"))
        self.assertFalse(calls[1].kwargs.get("spend_template_coinbase"))


class TestRecordTemplateSettlement(AsyncTestCase):
    async def test_records_all_indexes(self):
        p = _mk_payer()
        p.config.mongo.async_db.share_payout.update_one = AsyncMock()
        p.config.mongo.async_db.shares.delete_many = AsyncMock()
        block = MagicMock(index=50, hash="bh")
        txn = MagicMock(transaction_signature="u0")
        txn.to_dict = MagicMock(return_value={"id": "u0"})
        block.transactions = [txn]
        meta = {
            "settled_indexes": [10, 11, 12, 13],
            "payout_txn_ids": ["u0", "u1"],
            "payout_txn_id": "u0",
        }
        await p.record_template_settlement(meta, block)
        self.assertEqual(p.config.mongo.async_db.share_payout.update_one.await_count, 4)


class TestDoPayoutDeprecated(AsyncTestCase):
    async def test_noop(self):
        p = _mk_payer()
        self.assertIsNone(await p.do_payout())
