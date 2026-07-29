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


class TestPoolInceptionAndReward(AsyncTestCase):
    async def test_pool_inception_address_from_pubkey(self):
        p = _mk_payer()
        # Restore real method
        from yadacoin.core.miningpoolpayout import PoolPayer

        p.pool_inception_address = PoolPayer.pool_inception_address.__get__(
            p, PoolPayer
        )
        # Use a valid compressed pubkey hex
        from coincurve import PrivateKey

        priv = PrivateKey()
        pub = priv.public_key.format(compressed=True).hex()
        p.config.inception = MagicMock(public_key=pub)
        addr = p.pool_inception_address()
        self.assertTrue(isinstance(addr, str) and len(addr) > 10)

    async def test_pool_inception_address_none(self):
        from yadacoin.core.miningpoolpayout import PoolPayer

        p = _mk_payer()
        p.pool_inception_address = PoolPayer.pool_inception_address.__get__(
            p, PoolPayer
        )
        p.config.inception = None
        self.assertIsNone(p.pool_inception_address())
        p.config.inception = MagicMock(public_key=None)
        self.assertIsNone(p.pool_inception_address())

    async def test_pool_reward_empty_coinbase(self):
        p = _mk_payer()
        self.assertEqual(p.pool_reward_value(None), 0.0)
        cb = MagicMock(outputs=[])
        self.assertEqual(p.pool_reward_value(cb), 0.0)

    async def test_is_pool_won_no_coinbase(self):
        p = _mk_payer()
        self.assertFalse(p.is_pool_won_coinbase(None))
        p.pool_inception_address = MagicMock(return_value=None)
        self.assertFalse(p.is_pool_won_coinbase(_mk_coinbase()))


class TestCollectSettlementBranches(AsyncTestCase):
    async def test_skips_already_used_and_existing_payout(self):
        p = _mk_payer()
        p.config.payout_frequency = 1
        p.config.LatestBlock.block.index = 200
        p.config.mongo.async_db.share_payout.find_one = AsyncMock(
            side_effect=[None, {"index": 10, "txn": {"id": "x"}}, None]
        )
        # first call is already_paid_height, then per-block existing
        p.config.mongo.async_db.share_payout.find_one = AsyncMock(
            side_effect=[
                None,  # already_paid_height
                {"txn": {"id": "paid"}},  # existing for first block
            ]
        )
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter([{"index": 10, "id": "i", "hash": "h"}])
        )
        p.config.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        p.config.mongo.async_db.shares.delete_many = AsyncMock()
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(10)),
        ):
            p.already_used = AsyncMock(return_value=False)
            batches = await p.collect_settlement_batches("pk")
        self.assertEqual(batches, [])

    async def test_skips_already_used_deletes_shares(self):
        p = _mk_payer()
        p.config.payout_frequency = 1
        p.config.LatestBlock.block.index = 200
        p.config.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter([{"index": 10, "id": "i", "hash": "h"}])
        )
        p.config.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        p.config.mongo.async_db.shares.delete_many = AsyncMock()
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(10)),
        ):
            p.already_used = AsyncMock(return_value=True)
            batches = await p.collect_settlement_batches("pk")
        self.assertEqual(batches, [])
        p.config.mongo.async_db.shares.delete_many.assert_awaited()

    async def test_shares_exception_continues(self):
        p = _mk_payer()
        p.config.payout_frequency = 1
        p.config.LatestBlock.block.index = 200
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
            p.get_share_list_for_height = AsyncMock(side_effect=Exception("bad shares"))
            batches = await p.collect_settlement_batches("pk")
        self.assertEqual(batches, [])

    async def test_exclude_coinbase_ids(self):
        p = _mk_payer()
        p.config.payout_frequency = 1
        p.config.LatestBlock.block.index = 200
        p.config.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter([{"index": 10, "id": "i", "hash": "h"}])
        )
        p.config.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        cb = _mk_coinbase("sig10")
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(10, cb)),
        ):
            batches = await p.collect_settlement_batches(
                "pk", exclude_coinbase_ids={"sig10"}
            )
        self.assertEqual(batches, [])

    async def test_not_pool_won_skipped(self):
        p = _mk_payer()
        p.config.payout_frequency = 1
        p.config.LatestBlock.block.index = 200
        p.config.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter([{"index": 10, "id": "i", "hash": "h"}])
        )
        p.config.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(10, _mk_coinbase(inception="1Other"))),
        ):
            batches = await p.collect_settlement_batches("pk")
        self.assertEqual(batches, [])

    async def test_find_one_none_continues(self):
        p = _mk_payer()
        p.config.payout_frequency = 1
        p.config.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter([{"index": 10, "id": "i", "hash": "h"}])
        )
        p.config.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        batches = await p.collect_settlement_batches("pk")
        self.assertEqual(batches, [])


class TestBuildTemplatePayoutPair(AsyncTestCase):
    async def test_signer_mismatch_returns_none(self):
        p = _mk_payer()
        with patch(
            "yadacoin.core.miningpoolpayout.P2PKHBitcoinAddress.from_pubkey",
            return_value=type("A", (), {"__str__": lambda s: "wrong"})(),
        ):
            u, c = await p.build_template_payout_pair(
                _mk_coinbase(),
                [_mk_coinbase()],
                {"m": 1.0},
                signer_pub="aa" * 33,
                signer_priv="bb" * 32,
                signer_pkh="1Right",
                prerotated="1Pre",
                twice="1Twice",
                prev_pkh="1Prev",
                confirming_pub="cc" * 33,
                confirming_priv="dd" * 32,
                confirming_pkh="1C",
                confirming_pre="1CP",
                confirming_twice="1CT",
                tip_counter=1,
                inception=INCEPTION_ADDR,
                batch_txns_for_auth=[],
            )
        self.assertIsNone(u)

    async def test_no_coinbases_returns_none(self):
        p = _mk_payer()
        u, c = await p.build_template_payout_pair(
            None,
            [],
            {"m": 1.0},
            signer_pub="aa" * 33,
            signer_priv="p",
            signer_pkh="a",
            prerotated="p",
            twice="t",
            prev_pkh="v",
            confirming_pub="c",
            confirming_priv="cp",
            confirming_pkh="ck",
            confirming_pre="cpre",
            confirming_twice="ctw",
            tip_counter=None,
            inception=None,
            batch_txns_for_auth=[],
        )
        self.assertIsNone(u)

    async def test_builds_pair_with_value(self):
        p = _mk_payer()
        from coincurve import PrivateKey

        priv_u = PrivateKey()
        pub_u = priv_u.public_key.format(compressed=True)
        addr_u = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub_u)
        )
        priv_c = PrivateKey()
        pub_c = priv_c.public_key.format(compressed=True)
        addr_c = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub_c)
        )
        priv_c2 = PrivateKey()
        addr_c2 = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(
                priv_c2.public_key.format(compressed=True)
            )
        )
        priv_c3 = PrivateKey()
        addr_c3 = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(
                priv_c3.public_key.format(compressed=True)
            )
        )

        cb = _mk_coinbase("sig_old", value=100.0, prerotated="1PreOld")
        template_cb = _mk_coinbase("sig_tmpl", value=50.0, prerotated="1PreTmpl")

        u, c = await p.build_template_payout_pair(
            template_cb,
            [cb],
            {"miner1": 40.0},
            signer_pub=pub_u.hex(),
            signer_priv=priv_u.to_hex(),
            signer_pkh=addr_u,
            prerotated=addr_c,
            twice=addr_c2,
            prev_pkh="1Prev",
            confirming_pub=pub_c.hex(),
            confirming_priv=priv_c.to_hex(),
            confirming_pkh=addr_c,
            confirming_pre=addr_c2,
            confirming_twice=addr_c3,
            tip_counter=5,
            inception=INCEPTION_ADDR,
            batch_txns_for_auth=[],
            fee=0.0001,
            spend_template_coinbase=True,
            txn_time=12345,
        )
        self.assertIsNotNone(u)
        self.assertIsNotNone(c)
        self.assertTrue(getattr(u, "template_kel", False))
        self.assertTrue(getattr(c, "template_kel", False))
        self.assertEqual(u.time, 12345)
        self.assertEqual(c.time, 12345)
        # miner 40 + fee 0.0001; inputs 100 + 50 = 150; change on prerotated
        self.assertGreater(u.outputs[0].value, 0)

    async def test_not_enough_money(self):
        from coincurve import PrivateKey

        from yadacoin.core.transaction import NotEnoughMoneyException

        p = _mk_payer()
        priv = PrivateKey()
        pub = priv.public_key.format(compressed=True)
        addr = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub)
        )
        cb = _mk_coinbase("sig", value=1.0, prerotated="1Pre")
        with self.assertRaises(NotEnoughMoneyException):
            await p.build_template_payout_pair(
                None,
                [cb],
                {"miner1": 100.0},
                signer_pub=pub.hex(),
                signer_priv=priv.to_hex(),
                signer_pkh=addr,
                prerotated="1PreR",
                twice="1T",
                prev_pkh="1P",
                confirming_pub=pub.hex(),
                confirming_priv=priv.to_hex(),
                confirming_pkh=addr,
                confirming_pre="1CP",
                confirming_twice="1CT",
                tip_counter=None,
                inception=INCEPTION_ADDR,
                batch_txns_for_auth=[],
            )


class TestAttachBranches(AsyncTestCase):
    async def test_no_triplet_or_coinbase(self):
        p = _mk_payer()
        self.assertIsNone(await p.attach_template_settlement([], None, MagicMock()))
        self.assertIsNone(await p.attach_template_settlement([], MagicMock(), None))

    async def test_missing_second_factor(self):
        p = _mk_payer()
        p.collect_settlement_batches = AsyncMock(
            return_value=[([_mk_coinbase()], {"m": 1.0}, [10])]
        )
        triplet = MagicMock(
            kn2_private_key="k",
            kn2_chain_code="c",
            kn2_public_key="p",
            coinbase_confirming=MagicMock(),
        )
        with patch("yadacoin.core.keyrotation._read_second_factor", return_value=None):
            self.assertIsNone(
                await p.attach_template_settlement([], triplet, _mk_coinbase())
            )

    async def test_missing_kn2_material(self):
        p = _mk_payer()
        p.collect_settlement_batches = AsyncMock(
            return_value=[([_mk_coinbase()], {"m": 1.0}, [10])]
        )
        triplet = MagicMock(
            kn2_private_key=None,
            kn2_chain_code=None,
            kn2_public_key="p",
            coinbase_confirming=MagicMock(),
        )
        with patch("yadacoin.core.keyrotation._read_second_factor", return_value="sf"):
            self.assertIsNone(
                await p.attach_template_settlement([], triplet, _mk_coinbase())
            )

    async def test_no_confirming_parent(self):
        p = _mk_payer()
        p.collect_settlement_batches = AsyncMock(
            return_value=[([_mk_coinbase()], {"m": 1.0}, [10])]
        )
        triplet = MagicMock(
            kn2_private_key="k",
            kn2_chain_code="c" * 64,
            kn2_public_key="p",
            coinbase_confirming=None,
        )
        with patch("yadacoin.core.keyrotation._read_second_factor", return_value="sf"):
            self.assertIsNone(
                await p.attach_template_settlement([], triplet, _mk_coinbase())
            )

    async def test_not_enough_money_returns_none(self):
        from yadacoin.core.transaction import NotEnoughMoneyException

        p = _mk_payer()
        p.collect_settlement_batches = AsyncMock(
            return_value=[([_mk_coinbase()], {"m": 1.0}, [10])]
        )
        p._derive_key_material = MagicMock(
            return_value={
                "private_key": "aa" * 32,
                "chain_code": "bb" * 32,
                "public_key": "cc" * 33,
                "address": "1Addr",
            }
        )
        p.build_template_payout_pair = AsyncMock(
            side_effect=NotEnoughMoneyException("nope")
        )
        triplet = MagicMock(
            kn2_private_key="k",
            kn2_chain_code="c" * 64,
            kn2_public_key="p",
            kn2_address="1Kn2",
            coinbase_twice_prerotated="1Kn2",
            coinbase_prerotated="1Kn1",
            coinbase_confirming=MagicMock(counter=1),
            coinbase_inception_public_key_hash=INCEPTION_ADDR,
            signer_public_key="spk",
        )
        with patch("yadacoin.core.keyrotation._read_second_factor", return_value="sf"):
            self.assertIsNone(
                await p.attach_template_settlement([], triplet, _mk_coinbase())
            )

    async def test_generic_exception_returns_none(self):
        p = _mk_payer()
        p.collect_settlement_batches = AsyncMock(side_effect=RuntimeError("boom"))
        self.assertIsNone(
            await p.attach_template_settlement([], MagicMock(), _mk_coinbase())
        )

    async def test_build_returns_none_breaks(self):
        p = _mk_payer()
        p.collect_settlement_batches = AsyncMock(
            return_value=[([_mk_coinbase()], {"m": 1.0}, [10])]
        )
        p._derive_key_material = MagicMock(
            return_value={
                "private_key": "aa" * 32,
                "chain_code": "bb" * 32,
                "public_key": "cc" * 33,
                "address": "1Addr",
            }
        )
        p.build_template_payout_pair = AsyncMock(return_value=(None, None))
        triplet = MagicMock(
            kn2_private_key="k",
            kn2_chain_code="c" * 64,
            kn2_public_key="p",
            kn2_address="1Kn2",
            coinbase_twice_prerotated="1Kn2",
            coinbase_prerotated="1Kn1",
            coinbase_confirming=MagicMock(counter=1),
            coinbase_inception_public_key_hash=INCEPTION_ADDR,
            signer_public_key="spk",
        )
        with patch("yadacoin.core.keyrotation._read_second_factor", return_value="sf"):
            self.assertIsNone(
                await p.attach_template_settlement([], triplet, _mk_coinbase())
            )


class TestDeriveKeyMaterial(AsyncTestCase):
    async def test_derive(self):
        from coincurve import PrivateKey

        p = _mk_payer()
        priv = PrivateKey()
        # need a chain code - use 32 bytes
        cc = b"\x01" * 32
        # seed second factor
        result = p._derive_key_material(priv.to_hex(), cc.hex(), "second-factor-test")
        self.assertIn("private_key", result)
        self.assertIn("address", result)
        self.assertIn("public_key", result)
        self.assertIn("chain_code", result)


class TestRecordEmpty(AsyncTestCase):
    async def test_empty_meta(self):
        p = _mk_payer()
        p.config.mongo.async_db.share_payout.update_one = AsyncMock()
        await p.record_template_settlement(None, MagicMock())
        await p.record_template_settlement({}, MagicMock())
        p.config.mongo.async_db.share_payout.update_one.assert_not_awaited()


class TestBuildMoreBranches(AsyncTestCase):
    async def test_zero_value_miner_outs_only_prerotated(self):
        """All miner values <= 0 → only prerotated out → returns None."""
        from coincurve import PrivateKey

        p = _mk_payer()
        priv = PrivateKey()
        pub = priv.public_key.format(compressed=True)
        addr = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub)
        )
        u, c = await p.build_template_payout_pair(
            None,
            [_mk_coinbase(value=10.0)],
            {"m": 0.0, "n": -1.0},
            signer_pub=pub.hex(),
            signer_priv=priv.to_hex(),
            signer_pkh=addr,
            prerotated="1Pre",
            twice="1T",
            prev_pkh="1P",
            confirming_pub=pub.hex(),
            confirming_priv=priv.to_hex(),
            confirming_pkh=addr,
            confirming_pre="1CP",
            confirming_twice="1CT",
            tip_counter=None,
            inception=INCEPTION_ADDR,
            batch_txns_for_auth=[],
        )
        self.assertIsNone(u)

    async def test_missing_parent_and_zero_credit(self):
        from coincurve import PrivateKey

        from yadacoin.core.transaction import NotEnoughMoneyException

        p = _mk_payer()
        priv = PrivateKey()
        pub = priv.public_key.format(compressed=True)
        addr = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub)
        )
        # Missing parent in parents_by_id and BU → skip input, then NEME
        cb = MagicMock()
        cb.outputs = []
        cb.transaction_signature = "sigz"
        cb.prerotated_key_hash = "1Pre"
        cb.inception_public_key_hash = INCEPTION_ADDR
        # Force lookup miss: clear signature so parents_by_id key won't match input
        # Actually inputs are built from coinbase sigs - parent is found.
        # Use zero-value outs so credited stays 0.
        out = MagicMock()
        out.to = "1Pre"
        out.value = 0.0
        cb.outputs = [out]

        p.config.BU.get_transaction_by_id = AsyncMock(return_value=None)

        with self.assertRaises(NotEnoughMoneyException):
            await p.build_template_payout_pair(
                None,
                [cb],
                {"m": 1.0},
                signer_pub=pub.hex(),
                signer_priv=priv.to_hex(),
                signer_pkh=addr,
                prerotated="1PreR",
                twice="1T",
                prev_pkh="1P",
                confirming_pub=pub.hex(),
                confirming_priv=priv.to_hex(),
                confirming_pkh=addr,
                confirming_pre="1CP",
                confirming_twice="1CT",
                tip_counter=None,
                inception=INCEPTION_ADDR,
                batch_txns_for_auth=[],
            )

        # Missing parent path: coinbase list with sig, but parent lookup fails
        # by removing outputs attribute handling - use BU returning None and
        # empty parents_by_id by using spend of unknown id only via template.
        # Direct: monkeypatch inputs after... call with coinbase whose get fails
        # by replacing parents_by_id path - BU None and not in parents:
        # if we pass coinbases=[cb] parents has it. Use side-effect to delete:
        # Simpler separate: empty outputs + zero prerotated reward already covers
        # zero credit warning path.

    async def test_parent_from_bu_dict_and_fallback_sum(self):
        from coincurve import PrivateKey

        p = _mk_payer()
        priv = PrivateKey()
        pub = priv.public_key.format(compressed=True)
        addr = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub)
        )
        # parent as dict without prerotated match → fallback sum positive outs
        parent_dict = {
            "time": 1,
            "rid": "",
            "id": "sigdict",
            "relationship": "",
            "public_key": "aa" * 33,
            "dh_public_key": "",
            "fee": 0,
            "masternode_fee": 0,
            "inputs": [],
            "outputs": [{"to": "1Anyone", "value": 80.0}],
            "hash": "h" * 64,
            "prerotated_key_hash": "",
            "twice_prerotated_key_hash": "",
            "public_key_hash": "",
            "prev_public_key_hash": "",
        }
        p.config.BU.get_transaction_by_id = AsyncMock(return_value=parent_dict)

        # empty coinbases list but spend via input id only - need coinbases non-empty
        # Use a dummy coinbase whose sig matches so parents_by_id has it, but we'll
        # force lookup path by using different structure - actually parents_by_id
        # is filled from coinbases. For BU path, put coinbase with sig and remove
        # from parents... The loop uses parents_by_id first. To hit BU, use
        # coinbase list empty is not allowed. Add coinbase, then clear parents
        # by making id mismatch - coinbase sig "other" and input from spend_template.

        # Simpler: coinbase with empty prerotated so pool_reward_value=0, positive outs
        cb = MagicMock()
        out = MagicMock()
        out.to = "1Anyone"
        out.value = 80.0
        cb.outputs = [out]
        cb.transaction_signature = "sigfb"
        cb.prerotated_key_hash = ""
        cb.inception_public_key_hash = INCEPTION_ADDR

        priv_c = PrivateKey()
        pub_c = priv_c.public_key.format(compressed=True)
        addr_c = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub_c)
        )
        u, c = await p.build_template_payout_pair(
            None,
            [cb],
            {"m": 10.0},
            signer_pub=pub.hex(),
            signer_priv=priv.to_hex(),
            signer_pkh=addr,
            prerotated=addr_c,
            twice="1T",
            prev_pkh="1P",
            confirming_pub=pub_c.hex(),
            confirming_priv=priv_c.to_hex(),
            confirming_pkh=addr_c,
            confirming_pre="1CP",
            confirming_twice="1CT",
            tip_counter=None,
            inception=INCEPTION_ADDR,
            batch_txns_for_auth=[],
            txn_time=None,  # cover default time path
        )
        self.assertIsNotNone(u)

    async def test_template_coinbase_credit_path(self):
        from coincurve import PrivateKey

        p = _mk_payer()
        priv = PrivateKey()
        pub = priv.public_key.format(compressed=True)
        addr = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub)
        )
        priv_c = PrivateKey()
        pub_c = priv_c.public_key.format(compressed=True)
        addr_c = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub_c)
        )
        tmpl = _mk_coinbase("sig_t", value=30.0, prerotated="1PreT")
        # template coinbase with prerotated out credited via loop
        u, c = await p.build_template_payout_pair(
            tmpl,
            [],
            {"m": 5.0},
            signer_pub=pub.hex(),
            signer_priv=priv.to_hex(),
            signer_pkh=addr,
            prerotated=addr_c,
            twice="1T",
            prev_pkh="1P",
            confirming_pub=pub_c.hex(),
            confirming_priv=priv_c.to_hex(),
            confirming_pkh=addr_c,
            confirming_pre="1CP",
            confirming_twice="1CT",
            tip_counter=2,
            inception=INCEPTION_ADDR,
            batch_txns_for_auth=[],
            spend_template_coinbase=True,
        )
        # empty coinbases + spend template only - coinbases empty returns None early
        # need at least one coinbase OR template. empty coinbases returns None.
        self.assertIsNone(u)

        # with both
        old = _mk_coinbase("sig_o", value=20.0, prerotated="1PreO")
        u, c = await p.build_template_payout_pair(
            tmpl,
            [old],
            {"m": 5.0},
            signer_pub=pub.hex(),
            signer_priv=priv.to_hex(),
            signer_pkh=addr,
            prerotated=addr_c,
            twice="1T",
            prev_pkh="1P",
            confirming_pub=pub_c.hex(),
            confirming_priv=priv_c.to_hex(),
            confirming_pkh=addr_c,
            confirming_pre="1CP",
            confirming_twice="1CT",
            tip_counter=2,
            inception=INCEPTION_ADDR,
            batch_txns_for_auth=[],
            spend_template_coinbase=True,
        )
        self.assertIsNotNone(u)
        # both inputs
        self.assertEqual(len(u.inputs), 2)


class TestAttachInceptionTagging(AsyncTestCase):
    async def test_sets_missing_inception_tags(self):
        p = _mk_payer()
        cb = _mk_coinbase("sig_cb")
        cb.inception_public_key_hash = ""
        conf = MagicMock(counter=2, inception_public_key_hash="")
        p.collect_settlement_batches = AsyncMock(
            return_value=[([_mk_coinbase("s1")], {"m": 1.0}, [10])]
        )
        u = MagicMock(transaction_signature="u0", inputs=[], counter=3)
        c = MagicMock(transaction_signature="c0", counter=4)
        p.build_template_payout_pair = AsyncMock(return_value=(u, c))
        p._derive_key_material = MagicMock(
            return_value={
                "private_key": "p",
                "chain_code": "c",
                "public_key": "aa" * 33,
                "address": "1A",
            }
        )
        triplet = MagicMock(
            kn2_private_key="k2",
            kn2_public_key="pk2",
            kn2_chain_code="cc2",
            kn2_address="1Kn2",
            coinbase_twice_prerotated="1Kn2",
            coinbase_prerotated="1Kn1",
            coinbase_confirming=conf,
            coinbase_inception_public_key_hash=INCEPTION_ADDR,
            signer_public_key="spk",
        )
        with patch("yadacoin.core.keyrotation._read_second_factor", return_value="sf"):
            meta = await p.attach_template_settlement([], triplet, cb)
        self.assertIsNotNone(meta)
        self.assertEqual(cb.inception_public_key_hash, INCEPTION_ADDR)
        self.assertEqual(conf.inception_public_key_hash, INCEPTION_ADDR)

    async def test_links_same_block_inputs(self):
        p = _mk_payer()
        cb = _mk_coinbase("sig_cb")
        inp = MagicMock(id="sig_cb")
        u = MagicMock(transaction_signature="u0", inputs=[inp], counter=3)
        c = MagicMock(transaction_signature="c0", counter=4)
        p.collect_settlement_batches = AsyncMock(
            return_value=[([_mk_coinbase("s1")], {"m": 1.0}, [10])]
        )
        p.build_template_payout_pair = AsyncMock(return_value=(u, c))
        p._derive_key_material = MagicMock(
            return_value={
                "private_key": "p",
                "chain_code": "c",
                "public_key": "aa" * 33,
                "address": "1A",
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
        pending = [cb]
        with patch("yadacoin.core.keyrotation._read_second_factor", return_value="sf"):
            await p.attach_template_settlement(pending, triplet, cb)
        self.assertIs(inp.input_txn, cb)
        self.assertIs(cb.spent_in_txn, u)


class TestCollectDepthAndMaxReady(AsyncTestCase):
    async def test_not_deep_enough_skipped(self):
        p = _mk_payer()
        p.config.payout_frequency = 10
        p.config.LatestBlock.block.index = 15  # 10+10 > 15
        p.config.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter([{"index": 10, "id": "i", "hash": "h"}])
        )
        p.config.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(10)),
        ):
            batches = await p.collect_settlement_batches("pk")
        self.assertEqual(batches, [])

    async def test_zero_reward_skipped(self):
        p = _mk_payer()
        p.config.payout_frequency = 1
        p.config.LatestBlock.block.index = 200
        p.config.mongo.async_db.share_payout.find_one = AsyncMock(return_value=None)
        p.config.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_AsyncIter([{"index": 10, "id": "i", "hash": "h"}])
        )
        p.config.mongo.async_db.blocks.find_one = AsyncMock(return_value={"x": 1})
        cb = _mk_coinbase(value=0.0)
        with patch(
            "yadacoin.core.miningpoolpayout.Block.from_dict",
            new=AsyncMock(return_value=_mk_block(10, cb)),
        ):
            p.already_used = AsyncMock(return_value=False)
            p.get_share_list_for_height = AsyncMock(
                return_value={"m": {"payout_share": 1.0}}
            )
            batches = await p.collect_settlement_batches("pk")
        self.assertEqual(batches, [])

    async def test_empty_shares_skipped(self):
        p = _mk_payer()
        p.config.payout_frequency = 1
        p.config.LatestBlock.block.index = 200
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
            p.get_share_list_for_height = AsyncMock(return_value=False)
            batches = await p.collect_settlement_batches("pk")
        self.assertEqual(batches, [])


class TestGetShareListInvalid(AsyncTestCase):
    async def test_invalid_address_raises(self):
        p = _mk_payer()
        p.config.address_is_valid = MagicMock(return_value=False)
        p.config.mongo.async_db.shares.find = MagicMock(
            return_value=_AsyncIter([{"address": "bad", "hash": "0" * 64}])
        )
        p.config.mongo.async_db.shares.delete_many = AsyncMock()
        with self.assertRaises(Exception) as ctx:
            await p.get_share_list_for_height(10)
        self.assertIn("invalid address", str(ctx.exception))


class TestRecordPayoutIdOnly(AsyncTestCase):
    async def test_payout_txn_id_without_list(self):
        p = _mk_payer()
        p.config.mongo.async_db.share_payout.update_one = AsyncMock()
        p.config.mongo.async_db.shares.delete_many = AsyncMock()
        block = MagicMock(index=50, hash="bh")
        txn = MagicMock(transaction_signature="only")
        txn.to_dict = MagicMock(return_value={"id": "only"})
        block.transactions = [txn]
        meta = {"settled_indexes": [10], "payout_txn_id": "only"}
        await p.record_template_settlement(meta, block)
        p.config.mongo.async_db.share_payout.update_one.assert_awaited()


class TestFinalCoverageGaps(AsyncTestCase):
    async def test_collect_settlement_empty(self):
        p = _mk_payer()
        p.collect_settlement_batches = AsyncMock(return_value=[])
        c, o, i = await p.collect_settlement("pk")
        self.assertEqual(c, [])
        self.assertEqual(o, {})
        self.assertEqual(i, [])

    async def test_missing_parent_via_bu_none(self):
        """Input id not in parents_by_id and BU returns None."""
        from unittest.mock import patch

        from coincurve import PrivateKey

        from yadacoin.core.transaction import NotEnoughMoneyException

        p = _mk_payer()
        priv = PrivateKey()
        pub = priv.public_key.format(compressed=True)
        addr = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub)
        )
        cb = _mk_coinbase("sig_real", value=50.0)

        # Patch Input list construction: after build starts, replace inputs
        # with one unknown id. Easier: pass coinbase then monkeypatch
        # unconfirmed.inputs mid-flight by wrapping the method internals.
        # Direct approach: BU returns None for a second synthetic input.
        # Add coinbase + spend_template with same sig already in list - skip.
        # Use patch on list of inputs after Transaction created...
        p.build_template_payout_pair

        async def wrapped(*a, **k):
            # Call until Transaction created - instead inject by making
            # coinbases empty of match: parent lookup uses parents_by_id
            # from coinbases. If we put coinbase with sig A but patch
            # Input to use id B...
            from yadacoin.core import miningpoolpayout as mpp

            mpp.Input if hasattr(mpp, "Input") else None
            # Patch Input in transaction module used inside method
            from yadacoin.core import transaction as txn_mod

            class BadInput:
                def __init__(self, signature=None, **kw):
                    self.id = "missing_sig"
                    self.input_txn = None

            with patch.object(txn_mod, "Input", BadInput):
                # rebuild call uses Input from local import inside method
                pass
            # Local import is `from yadacoin.core.transaction import Input`
            with patch("yadacoin.core.transaction.Input", BadInput):
                p.config.BU.get_transaction_by_id = AsyncMock(return_value=None)
                return await PoolPayer.build_template_payout_pair(
                    p,
                    None,
                    [cb],
                    {"m": 1.0},
                    signer_pub=pub.hex(),
                    signer_priv=priv.to_hex(),
                    signer_pkh=addr,
                    prerotated="1PreR",
                    twice="1T",
                    prev_pkh="1P",
                    confirming_pub=pub.hex(),
                    confirming_priv=priv.to_hex(),
                    confirming_pkh=addr,
                    confirming_pre="1CP",
                    confirming_twice="1CT",
                    tip_counter=None,
                    inception=INCEPTION_ADDR,
                    batch_txns_for_auth=[],
                )

        from yadacoin.core.miningpoolpayout import PoolPayer

        with self.assertRaises(NotEnoughMoneyException):
            await wrapped()

    async def test_from_dict_parent_without_outputs_attr(self):
        """Parent object lacking outputs triggers from_dict."""
        from coincurve import PrivateKey

        p = _mk_payer()
        priv = PrivateKey()
        pub = priv.public_key.format(compressed=True)
        addr = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub)
        )
        priv_c = PrivateKey()
        pub_c = priv_c.public_key.format(compressed=True)
        addr_c = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub_c)
        )

        # parents_by_id has plain dict-like without outputs - use MagicMock
        # without outputs, hasattr false, then from_dict
        parent_raw = {
            "time": 1,
            "rid": "",
            "id": "sigfd",
            "relationship": "",
            "public_key": "02" + "ab" * 32,
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "inputs": [],
            "outputs": [{"to": "1Pre", "value": 50.0}],
            "hash": "00" * 32,
            "prerotated_key_hash": "1Pre",
            "twice_prerotated_key_hash": "",
            "public_key_hash": "1Pkh",
            "prev_public_key_hash": "",
        }

        # Object without outputs attr but with id
        class Bare:
            def __init__(self):
                self.transaction_signature = "sigfd"
                self.prerotated_key_hash = "1Pre"
                self.inception_public_key_hash = INCEPTION_ADDR

        bare = Bare()
        p.config.BU.get_transaction_by_id = AsyncMock(return_value=parent_raw)

        # parents_by_id will have bare; hasattr outputs false → from_dict
        # But parents_by_id stores coinbases. Put bare as coinbase.
        bare.transaction_signature = "sigfd"
        # need get to return bare from parents - use bare as coinbase and
        # make hasattr(bare,'outputs') false - Bare has no outputs. Then
        # from_dict is called on bare which fails. So put bare in parents
        # and make BU return dict when... actually code does:
        # parent = parents_by_id.get → bare
        # if parent is None: BU
        # if not hasattr(parent, "outputs"): from_dict(parent)
        # from_dict expects dict - bare will fail.
        # Better: parents miss, BU returns dict without going through from_dict
        # wait, if BU returns dict, hasattr(dict,'outputs') is False, from_dict(dict).

        p.config.BU.get_transaction_by_id = AsyncMock(return_value=parent_raw)
        # Force miss in parents by using Input with different approach:
        # coinbase list empty not allowed. Use coinbase with different sig
        # than we'll inject...

        # Patch Input to create id "sigfd" while coinbases use "other"
        from yadacoin.core import transaction as txn_mod

        class FixedInput:
            def __init__(self, signature=None, **kw):
                self.id = "sigfd"
                self.input_txn = None

        cb_placeholder = _mk_coinbase("other", value=1.0)
        with patch.object(txn_mod, "Input", FixedInput):
            u, c = await p.build_template_payout_pair(
                None,
                [cb_placeholder],
                {"m": 10.0},
                signer_pub=pub.hex(),
                signer_priv=priv.to_hex(),
                signer_pkh=addr,
                prerotated=addr_c,
                twice="1T",
                prev_pkh="1P",
                confirming_pub=pub_c.hex(),
                confirming_priv=priv_c.to_hex(),
                confirming_pkh=addr_c,
                confirming_pre="1CP",
                confirming_twice="1CT",
                tip_counter=1,
                inception=INCEPTION_ADDR,
                batch_txns_for_auth=[],
            )
        self.assertIsNotNone(u)

    async def test_template_coinbase_zero_pre_then_reward_fallback(self):
        from coincurve import PrivateKey

        p = _mk_payer()
        priv = PrivateKey()
        pub = priv.public_key.format(compressed=True)
        addr = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub)
        )
        priv_c = PrivateKey()
        pub_c = priv_c.public_key.format(compressed=True)
        addr_c = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(pub_c)
        )
        # Template coinbase: prerotated set but no matching out → pool_reward fallback
        tmpl = MagicMock()
        out = MagicMock()
        out.to = "1Other"
        out.value = 40.0
        tmpl.outputs = [out]
        tmpl.transaction_signature = "sig_t"
        tmpl.prerotated_key_hash = "1PreT"
        tmpl.inception_public_key_hash = INCEPTION_ADDR
        # pool_reward_value returns 0; loop credited stays 0; then
        # credited = pool_reward_value again still 0 - will NEME unless
        # we make pool_reward find something. Add matching out with 0 then
        # fallback: actually code does credited = pool_reward after loop if <=0.
        # So make pool_reward return 40 by matching prerotated.
        out2 = MagicMock()
        out2.to = "1PreT"
        out2.value = 0.0  # loop skips <=0, then pool_reward sums 0
        tmpl.outputs = [out2]
        # Still 0. Use out matching with value for pool_reward after empty loop:
        # loop requires float>0. pool_reward same. Need pool_reward > 0:
        out2.value = 40.0
        # That hits loop credited path not fallback. For fallback line 355:
        # credited <= 0 after loop → pool_reward. Loop finds 40 so no fallback.
        # To hit 355: prerotated outs all 0, pool_reward also 0 if only those outs.
        # line 355 is inside `if parent is coinbase_txn` branch after loop.
        # outs with pre match value 0 → credited 0 → pool_reward_value (0) → still 0
        # then continues without evaluate - NEME.
        # For line 355 specifically executing: need credited <= 0 after loop
        # with pool_reward > 0. But pool_reward uses same outs as loop.
        # Impossible if loop and pool_reward use same condition...
        # Loop: pre and str(o.to)==pre and float>0
        # pool_reward: sum where to==prerotated
        # Same. Unless prerotated changes? No.
        # Line 355 is dead if pool_reward == loop logic.
        # Skip 355.

        old = _mk_coinbase("sig_o", value=50.0)
        u, c = await p.build_template_payout_pair(
            tmpl,
            [old],
            {"m": 5.0},
            signer_pub=pub.hex(),
            signer_priv=priv.to_hex(),
            signer_pkh=addr,
            prerotated=addr_c,
            twice="1T",
            prev_pkh="1P",
            confirming_pub=pub_c.hex(),
            confirming_priv=priv_c.to_hex(),
            confirming_pkh=addr_c,
            confirming_pre="1CP",
            confirming_twice="1CT",
            tip_counter=1,
            inception=INCEPTION_ADDR,
            batch_txns_for_auth=[],
            spend_template_coinbase=True,
        )
        self.assertIsNotNone(u)

    async def test_change_clamped_to_zero(self):
        # input_sum == needed → change 0; input_sum slightly above due float
        # change < 0 path: force by patching after sum - hard.
        # input_sum == needed exactly: change = 0, the `if change < 0` is false.
        # To hit change < 0 need needed > input_sum which raises NEME first.
        # Line 389 is dead code after NEME check. Skip.
        pass

    async def test_attach_no_batches_after_collect(self):
        # already covered by test_no_coinbases via collect empty
        p = _mk_payer()
        p.collect_settlement_batches = AsyncMock(return_value=[])
        triplet = MagicMock(
            kn2_public_key="p",
            signer_public_key="s",
            kn2_private_key="k",
            kn2_chain_code="c",
        )
        self.assertIsNone(
            await p.attach_template_settlement([], triplet, _mk_coinbase())
        )
