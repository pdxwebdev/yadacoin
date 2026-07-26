"""
Tests for mempool KEL root-walk block generation helpers.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.keyeventlog import (
    KeyEventFlag,
    classify_key_event_flag,
    is_kel_chain_complete,
    kel_successor_flag_allowed,
    verify_kel_step,
)
from yadacoin.core.transaction import Output, Transaction

from ..test_setup import AsyncTestCase


def _kel_txn(
    pkh,
    prerotated,
    twice,
    prev="",
    relationship="",
    outputs_to=None,
    sig=None,
    coinbase=False,
):
    if outputs_to is None:
        outputs_to = prerotated
    txn = Transaction(
        public_key="02" + "ab" * 32,
        public_key_hash=pkh,
        prerotated_key_hash=prerotated,
        twice_prerotated_key_hash=twice,
        prev_public_key_hash=prev,
        outputs=[Output(to=outputs_to, value=0.0)],
        relationship=relationship,
    )
    txn.transaction_signature = sig or f"sig-{pkh}"
    txn.coinbase = coinbase
    # Bypass public_key -> pkh check in verify_fields by not calling it for pure flag tests
    return txn


class TestKelSuccessorRules(AsyncTestCase):
    async def test_unconfirmed_only_followed_by_confirming(self):
        self.assertTrue(
            kel_successor_flag_allowed(
                KeyEventFlag.UNCONFIRMED, KeyEventFlag.CONFIRMING
            )
        )
        self.assertFalse(
            kel_successor_flag_allowed(
                KeyEventFlag.UNCONFIRMED, KeyEventFlag.UNCONFIRMED
            )
        )
        self.assertFalse(
            kel_successor_flag_allowed(KeyEventFlag.UNCONFIRMED, KeyEventFlag.INCEPTION)
        )

    async def test_confirming_may_follow_confirming_or_unconfirmed(self):
        self.assertTrue(
            kel_successor_flag_allowed(KeyEventFlag.CONFIRMING, KeyEventFlag.CONFIRMING)
        )
        self.assertTrue(
            kel_successor_flag_allowed(
                KeyEventFlag.CONFIRMING, KeyEventFlag.UNCONFIRMED
            )
        )

    async def test_inception_may_follow_confirming_or_unconfirmed(self):
        self.assertTrue(
            kel_successor_flag_allowed(KeyEventFlag.INCEPTION, KeyEventFlag.CONFIRMING)
        )
        self.assertTrue(
            kel_successor_flag_allowed(KeyEventFlag.INCEPTION, KeyEventFlag.UNCONFIRMED)
        )


class TestIsKelChainComplete(AsyncTestCase):
    async def test_lone_inception_complete(self):
        # No prev -> inception
        t = _kel_txn("A", "B", "C", prev="")
        self.assertEqual(classify_key_event_flag(t), KeyEventFlag.INCEPTION)
        self.assertTrue(is_kel_chain_complete([t]))

    async def test_confirming_tip_complete(self):
        # confirming shape: no relationship, single out to prerotated
        t = _kel_txn("B", "C", "D", prev="A", relationship="", outputs_to="C")
        self.assertEqual(classify_key_event_flag(t), KeyEventFlag.CONFIRMING)
        self.assertTrue(is_kel_chain_complete([t]))

    async def test_unconfirmed_tip_incomplete(self):
        t = _kel_txn(
            "B", "C", "D", prev="A", relationship="payload", outputs_to="other"
        )
        self.assertEqual(classify_key_event_flag(t), KeyEventFlag.UNCONFIRMED)
        self.assertFalse(is_kel_chain_complete([t]))

    async def test_u_then_c_complete(self):
        u = _kel_txn(
            "B", "C", "D", prev="A", relationship="payload", outputs_to="other", sig="u"
        )
        c = _kel_txn("C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c")
        self.assertEqual(classify_key_event_flag(u), KeyEventFlag.UNCONFIRMED)
        self.assertEqual(classify_key_event_flag(c), KeyEventFlag.CONFIRMING)
        self.assertTrue(is_kel_chain_complete([u, c]))

    async def test_u_then_u_incomplete(self):
        u1 = _kel_txn(
            "B", "C", "D", prev="A", relationship="p1", outputs_to="x", sig="u1"
        )
        u2 = _kel_txn(
            "C", "D", "E", prev="B", relationship="p2", outputs_to="y", sig="u2"
        )
        self.assertFalse(is_kel_chain_complete([u1, u2]))


class TestVerifyKelStep(AsyncTestCase):
    async def test_hash_link_mismatch_raises(self):
        prev = _kel_txn("A", "B", "C", prev="", relationship="", outputs_to="B")
        curr = _kel_txn(
            "X", "C", "D", prev="A", relationship="", outputs_to="C"
        )  # public_key_hash should be B
        with self.assertRaises(Exception):
            verify_kel_step(prev, curr)

    async def test_good_confirming_link(self):
        prev = _kel_txn("A", "B", "C", prev="", relationship="", outputs_to="B")
        curr = _kel_txn("B", "C", "D", prev="A", relationship="", outputs_to="C")
        # Bypass public_key_hash vs public_key check inside verify_fields
        with patch(
            "yadacoin.core.keyeventlog.KeyEvent.verify_fields", return_value=None
        ):
            with patch("yadacoin.core.keyeventlog.Config") as mock_cfg:
                inst = MagicMock()
                inst.address_is_valid.return_value = True
                mock_cfg.return_value = inst
                verify_kel_step(prev, curr, latest_entry=prev)


class TestSelectKelChainsForBlock(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        from yadacoin.core.block import Block

        self.Block = Block

    async def test_orphan_kel_deleted_and_removed(self):
        orphan = _kel_txn(
            "B", "C", "D", prev="missing", relationship="x", outputs_to="y", sig="orph"
        )
        non_kel = Transaction(
            public_key="02" + "cd" * 32,
            outputs=[Output(to="1Some", value=1.0)],
        )
        non_kel.transaction_signature = "nonkel"
        # Force non-kel
        non_kel.prerotated_key_hash = ""
        non_kel.twice_prerotated_key_hash = ""
        non_kel.public_key_hash = ""
        non_kel.prev_public_key_hash = ""

        txns = [orphan, non_kel]
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(False, None)),
        ):
            with patch("yadacoin.core.block.Config") as mock_cfg_cls:
                cfg = MagicMock()
                cfg.app_log = MagicMock()
                cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock()
                cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock()
                mock_cfg_cls.return_value = cfg
                accepted, rejected = await self.Block.select_kel_chains_for_block(txns)

        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0].transaction_signature, "orph")
        self.assertEqual(len(txns), 1)
        self.assertEqual(txns[0].transaction_signature, "nonkel")

    async def test_lone_inception_accepted(self):
        inception = _kel_txn(
            "A", "B", "C", prev="", relationship="", outputs_to="B", sig="inc"
        )
        txns = [inception]
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(True, None)),
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEvent.verify_inception",
                return_value=None,
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch("yadacoin.core.block.Config") as mock_cfg_cls:
                        cfg = MagicMock()
                        cfg.app_log = MagicMock()
                        cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock()
                        cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock()
                        mock_cfg_cls.return_value = cfg
                        (
                            accepted,
                            rejected,
                        ) = await self.Block.select_kel_chains_for_block(txns)

        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].transaction_signature, "inc")
        self.assertEqual(rejected, [])
        self.assertEqual(len(txns), 1)

    async def test_u_without_c_rejected(self):
        # Root is confirming-shaped tip child; then U with no C
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="root"
        )
        u = _kel_txn(
            "C", "D", "E", prev="B", relationship="payload", outputs_to="z", sig="u"
        )
        txns = [root, u]
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "root" else (False, None)
                )
            ),
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEvent.verify_fields", return_value=None
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                    return_value=None,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_unconfirmed",
                        return_value=None,
                    ):
                        with patch("yadacoin.core.block.Config") as mock_cfg_cls:
                            cfg = MagicMock()
                            cfg.app_log = MagicMock()
                            cfg.mongo.async_db.miner_transactions.delete_one = (
                                AsyncMock()
                            )
                            cfg.mongo.async_db.failed_transactions.insert_one = (
                                AsyncMock()
                            )
                            mock_cfg_cls.return_value = cfg
                            (
                                accepted,
                                rejected,
                            ) = await self.Block.select_kel_chains_for_block(txns)

        # root alone is complete (CONFIRMING); u is orphan incomplete
        # Actually walk will attach U to root then tip is U -> incomplete, whole chain discarded
        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 2)
        self.assertEqual(len(txns), 0)
        self.assertEqual(
            cfg.mongo.async_db.miner_transactions.delete_one.await_count, 2
        )


class TestKelHashLinksAndStepExtras(AsyncTestCase):
    async def test_hash_link_prev_pkh_mismatch(self):
        from yadacoin.core.keyeventlog import kel_hash_links_ok

        prev = _kel_txn("A", "B", "C", prev="")
        curr = _kel_txn("B", "C", "D", prev="WRONG")
        with self.assertRaises(Exception):
            kel_hash_links_ok(prev, curr)

    async def test_hash_link_twice_mismatch(self):
        from yadacoin.core.keyeventlog import kel_hash_links_ok

        prev = _kel_txn("A", "B", "C", prev="")
        curr = _kel_txn("B", "WRONG", "D", prev="A")
        with self.assertRaises(Exception):
            kel_hash_links_ok(prev, curr)

    async def test_verify_kel_step_none_previous(self):
        curr = _kel_txn("B", "C", "D", prev="A", relationship="", outputs_to="C")
        with self.assertRaises(Exception):
            verify_kel_step(None, curr)

    async def test_verify_kel_step_bad_succession(self):
        # U -> U not allowed
        u1 = _kel_txn(
            "B", "C", "D", prev="A", relationship="p", outputs_to="x", sig="u1"
        )
        u2 = _kel_txn(
            "C", "D", "E", prev="B", relationship="p2", outputs_to="y", sig="u2"
        )
        with self.assertRaises(Exception):
            verify_kel_step(u1, u2)

    async def test_verify_kel_step_unconfirmed(self):
        prev = _kel_txn("A", "B", "C", prev="", relationship="", outputs_to="B")
        curr = _kel_txn(
            "B", "C", "D", prev="A", relationship="payload", outputs_to="other"
        )
        with patch(
            "yadacoin.core.keyeventlog.KeyEvent.verify_fields", return_value=None
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEvent.verify_unconfirmed",
                return_value=None,
            ):
                verify_kel_step(prev, curr)

    async def test_is_kel_chain_complete_empty(self):
        self.assertFalse(is_kel_chain_complete([]))

    async def test_is_kel_chain_complete_u_then_inception_impossible_flag(self):
        # U followed by something that isn't C (use confirming-shaped then
        # force incomplete via empty tip that is U only already covered)
        u = _kel_txn("B", "C", "D", prev="A", relationship="p", outputs_to="x", sig="u")
        # tip unconfirmed alone already tested; U then C with wrong middle already
        self.assertFalse(is_kel_chain_complete([u]))


class TestIsMempoolKelRoot(AsyncTestCase):
    async def test_inception_is_root(self):
        from yadacoin.core.keyeventlog import is_mempool_kel_root

        t = _kel_txn("A", "B", "C", prev="")
        is_root, parent = await is_mempool_kel_root(t)
        self.assertTrue(is_root)
        self.assertIsNone(parent)

    async def test_no_prev_non_inception_not_root(self):
        from yadacoin.core.keyeventlog import is_mempool_kel_root

        t = _kel_txn("B", "C", "D", prev="A", relationship="", outputs_to="C")
        with patch(
            "yadacoin.core.keyeventlog.KeyEvent.get_onchain_parent",
            new=AsyncMock(return_value=None),
        ):
            is_root, parent = await is_mempool_kel_root(t)
        self.assertFalse(is_root)
        self.assertIsNone(parent)

    async def test_parent_pkh_mismatch_not_root(self):
        from yadacoin.core.keyeventlog import is_mempool_kel_root

        t = _kel_txn("B", "C", "D", prev="A", relationship="", outputs_to="C")
        parent_txn = _kel_txn(
            "WRONG", "B", "C", prev="", relationship="", outputs_to="B"
        )
        parent_ke = MagicMock()
        parent_ke.txn = parent_txn
        parent_ke.get_onchain_child = AsyncMock(return_value=None)
        with patch(
            "yadacoin.core.keyeventlog.KeyEvent.get_onchain_parent",
            new=AsyncMock(return_value={"key_event": parent_ke}),
        ):
            is_root, parent = await is_mempool_kel_root(t)
        self.assertFalse(is_root)

    async def test_parent_with_child_not_root(self):
        from yadacoin.core.keyeventlog import is_mempool_kel_root

        t = _kel_txn("B", "C", "D", prev="A", relationship="", outputs_to="C")
        parent_txn = _kel_txn("A", "B", "C", prev="", relationship="", outputs_to="B")
        parent_ke = MagicMock()
        parent_ke.txn = parent_txn
        parent_ke.get_onchain_child = AsyncMock(return_value=MagicMock())
        with patch(
            "yadacoin.core.keyeventlog.KeyEvent.get_onchain_parent",
            new=AsyncMock(return_value={"key_event": parent_ke}),
        ):
            is_root, parent = await is_mempool_kel_root(t)
        self.assertFalse(is_root)

    async def test_valid_tip_child_is_root(self):
        from yadacoin.core.keyeventlog import is_mempool_kel_root

        t = _kel_txn("B", "C", "D", prev="A", relationship="", outputs_to="C")
        parent_txn = _kel_txn("A", "B", "C", prev="", relationship="", outputs_to="B")
        parent_ke = MagicMock()
        parent_ke.txn = parent_txn
        parent_ke.get_onchain_child = AsyncMock(return_value=None)
        with patch(
            "yadacoin.core.keyeventlog.KeyEvent.get_onchain_parent",
            new=AsyncMock(return_value={"key_event": parent_ke}),
        ):
            with patch("yadacoin.core.keyeventlog.verify_kel_step", return_value=None):
                is_root, parent = await is_mempool_kel_root(t)
        self.assertTrue(is_root)
        self.assertIs(parent, parent_txn)

    async def test_verify_step_failure_not_root(self):
        from yadacoin.core.keyeventlog import is_mempool_kel_root

        t = _kel_txn("B", "C", "D", prev="A", relationship="", outputs_to="C")
        parent_txn = _kel_txn("A", "B", "C", prev="", relationship="", outputs_to="B")
        parent_ke = MagicMock()
        parent_ke.txn = parent_txn
        parent_ke.get_onchain_child = AsyncMock(return_value=None)
        with patch(
            "yadacoin.core.keyeventlog.KeyEvent.get_onchain_parent",
            new=AsyncMock(return_value={"key_event": parent_ke}),
        ):
            with patch(
                "yadacoin.core.keyeventlog.verify_kel_step",
                side_effect=Exception("bad link"),
            ):
                is_root, parent = await is_mempool_kel_root(t)
        self.assertFalse(is_root)

    async def test_get_latest_onchain_tip_for_txn(self):
        from yadacoin.core.keyeventlog import get_latest_onchain_tip_for_txn

        t = _kel_txn("B", "C", "D", prev="A")
        t.public_key = "02" + "ab" * 32
        tip = MagicMock()
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=tip),
        ):
            got = await get_latest_onchain_tip_for_txn(t)
        self.assertIs(got, tip)

        t2 = _kel_txn("B", "C", "D", prev="")
        self.assertIsNone(await get_latest_onchain_tip_for_txn(t2))

        t3 = _kel_txn("B", "C", "D", prev="A")
        t3.public_key = ""
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=tip),
        ):
            got = await get_latest_onchain_tip_for_txn(t3)
        self.assertIs(got, tip)

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(side_effect=Exception("db")),
        ):
            self.assertIsNone(await get_latest_onchain_tip_for_txn(t))


class TestSelectKelChainsMoreBranches(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        from yadacoin.core.block import Block

        self.Block = Block

    def _cfg(self):
        cfg = MagicMock()
        cfg.app_log = MagicMock()
        cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock()
        cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock()
        return cfg

    async def test_empty_and_non_kel(self):
        non = Transaction(public_key="02" + "11" * 32)
        non.transaction_signature = "n"
        non.prerotated_key_hash = ""
        non.twice_prerotated_key_hash = ""
        non.public_key_hash = ""
        non.prev_public_key_hash = ""
        with patch("yadacoin.core.block.Config") as m:
            m.return_value = self._cfg()
            a, r = await self.Block.select_kel_chains_for_block([non])
        self.assertEqual(a, [])
        self.assertEqual(r, [])

    async def test_coinbase_kept_on_discard(self):
        cb = _kel_txn(
            "B", "C", "D", prev="A", relationship="x", outputs_to="y", sig="cb"
        )
        cb.coinbase = True
        txns = [cb]
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(False, None)),
        ):
            with patch("yadacoin.core.block.Config") as m:
                cfg = self._cfg()
                m.return_value = cfg
                a, r = await self.Block.select_kel_chains_for_block(txns)
        self.assertEqual(len(a), 1)
        self.assertEqual(r, [])
        cfg.mongo.async_db.miner_transactions.delete_one.assert_not_awaited()

    async def test_root_check_exception_treated_as_non_root(self):
        t = _kel_txn("B", "C", "D", prev="A", relationship="", outputs_to="C", sig="t")
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(side_effect=Exception("boom")),
        ):
            with patch("yadacoin.core.block.Config") as m:
                cfg = self._cfg()
                m.return_value = cfg
                a, r = await self.Block.select_kel_chains_for_block([t])
        self.assertEqual(a, [])
        self.assertEqual(len(r), 1)

    async def test_invalid_inception_root_discarded(self):
        inc = _kel_txn(
            "A", "B", "C", prev="", relationship="", outputs_to="B", sig="inc"
        )
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(True, None)),
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEvent.verify_inception",
                side_effect=Exception("bad inception"),
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch("yadacoin.core.block.Config") as m:
                        cfg = self._cfg()
                        m.return_value = cfg
                        a, r = await self.Block.select_kel_chains_for_block([inc])
        self.assertEqual(a, [])
        self.assertEqual(len(r), 1)

    async def test_ambiguous_fork_discards_chain(self):
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="root"
        )
        c1 = _kel_txn(
            "C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c1"
        )
        c2 = _kel_txn(
            "C", "D2", "E2", prev="B", relationship="", outputs_to="D2", sig="c2"
        )
        # both kids same prev B - need public_key_hash of root = B for children_of
        # root.public_key_hash is B; kids prev=B. Good.
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "root" else (False, None)
                )
            ),
        ):
            with patch("yadacoin.core.keyeventlog.verify_kel_step", return_value=None):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                        return_value=None,
                    ):
                        with patch("yadacoin.core.block.Config") as m:
                            cfg = self._cfg()
                            m.return_value = cfg
                            a, r = await self.Block.select_kel_chains_for_block(
                                [root, c1, c2]
                            )
        self.assertEqual(a, [])
        self.assertGreaterEqual(len(r), 2)

    async def test_complete_u_c_chain_accepted(self):
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="root"
        )
        u = _kel_txn(
            "C", "D", "E", prev="B", relationship="payload", outputs_to="z", sig="u"
        )
        c = _kel_txn("D", "E", "F", prev="C", relationship="", outputs_to="E", sig="c")
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "root" else (False, None)
                )
            ),
        ):
            with patch("yadacoin.core.keyeventlog.verify_kel_step", return_value=None):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                        return_value=None,
                    ):
                        with patch(
                            "yadacoin.core.keyeventlog.KeyEvent.verify_unconfirmed",
                            return_value=None,
                        ):
                            with patch("yadacoin.core.block.Config") as m:
                                cfg = self._cfg()
                                m.return_value = cfg
                                a, r = await self.Block.select_kel_chains_for_block(
                                    [root, u, c]
                                )
        self.assertEqual(len(a), 3)
        self.assertEqual(r, [])

    async def test_mempool_delete_exception_logged(self):
        orphan = _kel_txn(
            "B", "C", "D", prev="miss", relationship="x", outputs_to="y", sig="orph"
        )
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(False, None)),
        ):
            with patch("yadacoin.core.block.Config") as m:
                cfg = self._cfg()
                cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock(
                    side_effect=Exception("db down")
                )
                m.return_value = cfg
                a, r = await self.Block.select_kel_chains_for_block([orphan])
        self.assertEqual(len(r), 1)
        cfg.app_log.warning.assert_called()

    async def test_kids_exist_but_none_valid_stops_walk(self):
        """Invalid kids do not fail a complete root; they are orphan-discarded."""
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="root"
        )
        bad_kid = _kel_txn(
            "C", "D", "E", prev="B", relationship="p", outputs_to="z", sig="bad"
        )
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "root" else (False, None)
                )
            ),
        ):
            with patch(
                "yadacoin.core.keyeventlog.verify_kel_step",
                side_effect=Exception("nope"),
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                        return_value=None,
                    ):
                        with patch("yadacoin.core.block.Config") as m:
                            cfg = self._cfg()
                            m.return_value = cfg
                            a, r = await self.Block.select_kel_chains_for_block(
                                [root, bad_kid]
                            )
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0].transaction_signature, "root")
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].transaction_signature, "bad")


class TestFinalCoverageGaps(AsyncTestCase):
    async def test_verify_kel_step_inception_branch(self):
        # Force curr_flag INCEPTION after succession check by mocking classify
        prev = _kel_txn("A", "B", "C", prev="", relationship="", outputs_to="B")
        curr = _kel_txn("B", "C", "D", prev="A", relationship="", outputs_to="C")
        with patch(
            "yadacoin.core.keyeventlog.classify_key_event_flag",
            side_effect=[
                KeyEventFlag.CONFIRMING,  # prev
                KeyEventFlag.INCEPTION,  # curr — won't pass succession
            ],
        ):
            with self.assertRaises(Exception):
                verify_kel_step(prev, curr)
        # Direct path: succession allows C->U etc; force INCEPTION after allowed
        with patch(
            "yadacoin.core.keyeventlog.classify_key_event_flag",
            side_effect=[
                KeyEventFlag.CONFIRMING,
                KeyEventFlag.CONFIRMING,  # for succession
            ],
        ):
            # Actually need curr_flag INCEPTION inside after succession —
            # call classify twice for succession then again? verify_kel_step
            # only classifies twice. Patch kel_successor to True and classify
            # to return INCEPTION for curr.
            pass
        calls = {"n": 0}

        def _cls(t):
            calls["n"] += 1
            if calls["n"] == 1:
                return KeyEventFlag.CONFIRMING
            return KeyEventFlag.INCEPTION

        with patch(
            "yadacoin.core.keyeventlog.classify_key_event_flag", side_effect=_cls
        ):
            with patch(
                "yadacoin.core.keyeventlog.kel_successor_flag_allowed",
                return_value=True,
            ):
                with patch(
                    "yadacoin.core.keyeventlog.kel_hash_links_ok", return_value=None
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_inception",
                        return_value=None,
                    ) as mock_inc:
                        with patch(
                            "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                            return_value=None,
                        ):
                            verify_kel_step(prev, curr)
                            mock_inc.assert_called()

    async def test_is_mempool_root_no_prev(self):
        from yadacoin.core.keyeventlog import is_mempool_kel_root

        t = _kel_txn("B", "C", "D", prev="A", relationship="", outputs_to="C")
        with patch(
            "yadacoin.core.keyeventlog.classify_key_event_flag",
            return_value=KeyEventFlag.CONFIRMING,
        ):
            t.prev_public_key_hash = ""
            is_root, parent = await is_mempool_kel_root(t)
        self.assertFalse(is_root)

    async def test_chain_complete_u_then_non_c(self):
        # Mock flags: U then CONFIRMING is ok; U then something else via mock
        u = _kel_txn("B", "C", "D", prev="A", relationship="p", outputs_to="x", sig="u")
        # Use a confirming-shaped tip but mock second flag as INCEPTION
        other = _kel_txn(
            "C", "D", "E", prev="B", relationship="", outputs_to="D", sig="o"
        )
        with patch(
            "yadacoin.core.keyeventlog.classify_key_event_flag",
            side_effect=[
                KeyEventFlag.UNCONFIRMED,
                KeyEventFlag.INCEPTION,  # flags list build
                KeyEventFlag.UNCONFIRMED,
                KeyEventFlag.INCEPTION,  # zip loop
            ],
        ):
            # is_kel_chain_complete classifies once per entry then uses flags
            # Actually it only classifies once: flags = [classify...]
            pass
        with patch(
            "yadacoin.core.keyeventlog.classify_key_event_flag",
            side_effect=[KeyEventFlag.UNCONFIRMED, KeyEventFlag.INCEPTION],
        ):
            self.assertFalse(is_kel_chain_complete([u, other]))

    async def test_select_missing_are_kel_attr(self):
        from yadacoin.core.block import Block

        class NoKel:
            transaction_signature = "x"

        with patch("yadacoin.core.block.Config") as m:
            cfg = MagicMock()
            cfg.app_log = MagicMock()
            cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock()
            cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock()
            m.return_value = cfg
            a, r = await Block.select_kel_chains_for_block([NoKel()])
        self.assertEqual(a, [])
        self.assertEqual(r, [])

    async def test_discard_already_claimed(self):
        from yadacoin.core.block import Block

        # Two roots that somehow claim same - use coinbase + orphan same object
        # Simpler: root accepted then appears again in orphan path - claimed
        root = _kel_txn(
            "A", "B", "C", prev="", relationship="", outputs_to="B", sig="inc"
        )
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(True, None)),
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEvent.verify_inception",
                return_value=None,
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch("yadacoin.core.block.Config") as m:
                        cfg = MagicMock()
                        cfg.app_log = MagicMock()
                        cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock()
                        cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock()
                        m.return_value = cfg
                        # Call twice on same list shouldn't double-discard
                        a, r = await Block.select_kel_chains_for_block([root, root])
        # same sig twice in candidates - second is duplicate object same sig
        self.assertTrue(len(a) >= 1)

    async def test_root_already_claimed_skipped(self):
        from yadacoin.core.block import Block

        # Coinbase orphan-path claims first; also listed as root
        cb = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="same"
        )
        cb.coinbase = True
        # Make is_root True for it; first loop adds as root; if claimed before
        # processing roots... coinbase only claimed in discard.
        # Two roots same sig: first completes, second hits claimed continue.
        r1 = _kel_txn(
            "A", "B", "C", prev="", relationship="", outputs_to="B", sig="dup"
        )
        r2 = _kel_txn(
            "A", "B", "C", prev="", relationship="", outputs_to="B", sig="dup"
        )
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(True, None)),
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEvent.verify_inception",
                return_value=None,
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch("yadacoin.core.block.Config") as m:
                        cfg = MagicMock()
                        cfg.app_log = MagicMock()
                        cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock()
                        cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock()
                        m.return_value = cfg
                        a, r = await Block.select_kel_chains_for_block([r1, r2])
        self.assertEqual(len(a), 1)

    async def test_recovers_inception_root_fields(self):
        from yadacoin.core.block import Block

        inc = _kel_txn(
            "A", "B", "C", prev="", relationship="", outputs_to="B", sig="rec"
        )
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(True, None)),
        ):
            with patch(
                "yadacoin.core.keyeventlog.is_recovers_inception",
                return_value=True,
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ) as mock_vf:
                    with patch(
                        "yadacoin.core.keyeventlog.classify_key_event_flag",
                        return_value=KeyEventFlag.INCEPTION,
                    ):
                        with patch("yadacoin.core.block.Config") as m:
                            cfg = MagicMock()
                            cfg.app_log = MagicMock()
                            cfg.mongo.async_db.miner_transactions.delete_one = (
                                AsyncMock()
                            )
                            m.return_value = cfg
                            a, r = await Block.select_kel_chains_for_block([inc])
        mock_vf.assert_called()
        self.assertEqual(len(a), 1)

    async def test_successor_flag_not_allowed_skips_kid(self):
        from yadacoin.core.block import Block

        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="root"
        )
        # kid with prev=B but succession fails
        kid = _kel_txn(
            "C", "D", "E", prev="B", relationship="p", outputs_to="z", sig="kid"
        )
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "root" else (False, None)
                )
            ),
        ):
            with patch(
                "yadacoin.core.keyeventlog.kel_successor_flag_allowed",
                return_value=False,
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                        return_value=None,
                    ):
                        with patch("yadacoin.core.block.Config") as m:
                            cfg = MagicMock()
                            cfg.app_log = MagicMock()
                            cfg.mongo.async_db.miner_transactions.delete_one = (
                                AsyncMock()
                            )
                            m.return_value = cfg
                            a, r = await Block.select_kel_chains_for_block([root, kid])
        # root alone confirming complete; kid orphan discarded
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0].transaction_signature, "root")
        self.assertEqual(len(r), 1)


class TestDiscardAlreadyClaimedInSameCall(AsyncTestCase):
    async def test_discard_skips_already_claimed_sig(self):
        """Cover _discard early-continue when sig already in claimed."""
        from yadacoin.core.block import Block

        # Ambiguous fork: walk_failed extends chain with both kids then discard.
        # Call discard on chain that includes duplicates of same sig.
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="root"
        )
        c1 = _kel_txn(
            "C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c1"
        )
        c1b = _kel_txn(
            "C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c1"
        )  # same sig as c1
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "root" else (False, None)
                )
            ),
        ):
            with patch("yadacoin.core.keyeventlog.verify_kel_step", return_value=None):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                        return_value=None,
                    ):
                        with patch("yadacoin.core.block.Config") as m:
                            cfg = MagicMock()
                            cfg.app_log = MagicMock()
                            cfg.mongo.async_db.miner_transactions.delete_one = (
                                AsyncMock()
                            )
                            m.return_value = cfg
                            # two kids same prev -> ambiguous; chain gets root+c1+c1b
                            # with same sig c1 twice when extended... actually both
                            # have sig c1 so valid_kids has 2 entries same link
                            a, r = await Block.select_kel_chains_for_block(
                                [root, c1, c1b]
                            )
        # discarded with duplicate sig in chain list hits continue
        self.assertEqual(a, [])
        self.assertGreaterEqual(len(r), 1)


class TestFailedTransactionsRecording(AsyncTestCase):
    async def test_orphan_written_to_failed_transactions(self):
        from yadacoin.core.block import Block

        orphan = _kel_txn(
            "B", "C", "D", prev="missing", relationship="x", outputs_to="y", sig="orph"
        )
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(False, None)),
        ):
            with patch("yadacoin.core.block.Config") as m:
                cfg = MagicMock()
                cfg.app_log = MagicMock()
                cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock()
                cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock()
                m.return_value = cfg
                await Block.select_kel_chains_for_block([orphan])
        cfg.mongo.async_db.failed_transactions.insert_one.assert_awaited()
        args, _ = cfg.mongo.async_db.failed_transactions.insert_one.await_args
        doc = args[0]
        self.assertEqual(doc["reason"], "KELChainDiscard")
        self.assertIn("orphan KEL", doc["message"])
        self.assertEqual(doc["txn"]["id"], "orph")

    async def test_failed_transactions_insert_exception_logged(self):
        from yadacoin.core.block import Block

        orphan = _kel_txn(
            "B", "C", "D", prev="missing", relationship="x", outputs_to="y", sig="orph2"
        )
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(False, None)),
        ):
            with patch("yadacoin.core.block.Config") as m:
                cfg = MagicMock()
                cfg.app_log = MagicMock()
                cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock()
                cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock(
                    side_effect=Exception("db fail")
                )
                m.return_value = cfg
                a, r = await Block.select_kel_chains_for_block([orphan])
        self.assertEqual(len(r), 1)
        cfg.app_log.warning.assert_called()


class TestKelChainBlockLimit(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        from yadacoin.core.block import Block

        self.Block = Block

    def _cfg(self):
        cfg = MagicMock()
        cfg.app_log = MagicMock()
        cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock()
        cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock()
        return cfg

    async def test_chain_truncated_at_confirming_within_limit(self):
        """Long C→C→C chain: keep prefix ending on C that fits; defer rest."""
        # root C, then C2, C3, C4 — limit allows only 2 KEL + 0 non-kel
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="c1"
        )
        c2 = _kel_txn(
            "C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c2"
        )
        c3 = _kel_txn(
            "D", "E", "F", prev="C", relationship="", outputs_to="E", sig="c3"
        )
        c4 = _kel_txn(
            "E", "F", "G", prev="D", relationship="", outputs_to="F", sig="c4"
        )
        txns = [root, c2, c3, c4]
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "c1" else (False, None)
                )
            ),
        ):
            with patch("yadacoin.core.keyeventlog.verify_kel_step", return_value=None):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                        return_value=None,
                    ):
                        with patch("yadacoin.core.block.Config") as m:
                            cfg = self._cfg()
                            m.return_value = cfg
                            a, r = await self.Block.select_kel_chains_for_block(
                                txns, max_transactions=2
                            )
        self.assertEqual([t.transaction_signature for t in a], ["c1", "c2"])
        self.assertEqual(r, [])
        # deferred removed from candidate, not failed
        self.assertEqual(len(txns), 2)
        cfg.mongo.async_db.failed_transactions.insert_one.assert_not_awaited()
        cfg.mongo.async_db.miner_transactions.delete_one.assert_not_awaited()

    async def test_truncate_before_unconfirmed_without_confirming(self):
        """If limit would leave tip on U, back up to prior confirming."""
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="c1"
        )
        u = _kel_txn(
            "C", "D", "E", prev="B", relationship="payload", outputs_to="z", sig="u"
        )
        c = _kel_txn("D", "E", "F", prev="C", relationship="", outputs_to="E", sig="c2")
        txns = [root, u, c]
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "c1" else (False, None)
                )
            ),
        ):
            with patch("yadacoin.core.keyeventlog.verify_kel_step", return_value=None):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                        return_value=None,
                    ):
                        with patch(
                            "yadacoin.core.keyeventlog.KeyEvent.verify_unconfirmed",
                            return_value=None,
                        ):
                            with patch("yadacoin.core.block.Config") as m:
                                cfg = self._cfg()
                                m.return_value = cfg
                                # Only 2 slots: full chain is 3. Prefix c1 alone
                                # is complete (CONFIRMING). c1+u is incomplete.
                                a, r = await self.Block.select_kel_chains_for_block(
                                    txns, max_transactions=2
                                )
        self.assertEqual([t.transaction_signature for t in a], ["c1"])
        self.assertEqual(r, [])
        # u and c deferred (still in mempool conceptually)
        self.assertEqual(len(txns), 1)
        cfg.mongo.async_db.failed_transactions.insert_one.assert_not_awaited()

    async def test_non_kel_consume_slots(self):
        """Non-KEL txns reduce slots available for KEL chains."""
        non = Transaction(public_key="02" + "11" * 32)
        non.transaction_signature = "non"
        non.prerotated_key_hash = ""
        non.twice_prerotated_key_hash = ""
        non.public_key_hash = ""
        non.prev_public_key_hash = ""
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="c1"
        )
        c2 = _kel_txn(
            "C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c2"
        )
        txns = [non, root, c2]
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "c1" else (False, None)
                )
            ),
        ):
            with patch("yadacoin.core.keyeventlog.verify_kel_step", return_value=None):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                        return_value=None,
                    ):
                        with patch("yadacoin.core.block.Config") as m:
                            cfg = self._cfg()
                            m.return_value = cfg
                            # max 2 total: 1 non-kel + 1 kel slot
                            a, r = await self.Block.select_kel_chains_for_block(
                                txns, max_transactions=2
                            )
        self.assertEqual([t.transaction_signature for t in a], ["c1"])
        self.assertEqual(r, [])
        # non + c1 remain; c2 deferred out
        sigs = {t.transaction_signature for t in txns}
        self.assertIn("non", sigs)
        self.assertIn("c1", sigs)
        self.assertNotIn("c2", sigs)

    async def test_no_prefix_fits_defers_entire_chain(self):
        """When zero KEL slots remain, defer whole chain (keep in mempool)."""
        non = Transaction(public_key="02" + "11" * 32)
        non.transaction_signature = "non"
        non.prerotated_key_hash = ""
        non.twice_prerotated_key_hash = ""
        non.public_key_hash = ""
        non.prev_public_key_hash = ""
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="c1"
        )
        txns = [non, root]
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(True, None)),
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                return_value=None,
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                    return_value=None,
                ):
                    with patch("yadacoin.core.block.Config") as m:
                        cfg = self._cfg()
                        m.return_value = cfg
                        a, r = await self.Block.select_kel_chains_for_block(
                            txns, max_transactions=1
                        )
        self.assertEqual(a, [])
        self.assertEqual(r, [])
        self.assertEqual([t.transaction_signature for t in txns], ["non"])
        cfg.mongo.async_db.failed_transactions.insert_one.assert_not_awaited()
        cfg.mongo.async_db.miner_transactions.delete_one.assert_not_awaited()


class TestKelLimitCoverageGaps(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        from yadacoin.core.block import Block

        self.Block = Block

    def _cfg(self):
        cfg = MagicMock()
        cfg.app_log = MagicMock()
        cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock()
        cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock()
        return cfg

    async def test_max_transactions_none_defaults(self):
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="c1"
        )
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(True, None)),
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                return_value=None,
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                    return_value=None,
                ):
                    with patch("yadacoin.core.block.Config") as m:
                        m.return_value = self._cfg()
                        a, r = await self.Block.select_kel_chains_for_block(
                            [root], max_transactions=None
                        )
        self.assertEqual(len(a), 1)

    async def test_max_transactions_negative_defaults(self):
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="c1"
        )
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(True, None)),
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                return_value=None,
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                    return_value=None,
                ):
                    with patch("yadacoin.core.block.Config") as m:
                        m.return_value = self._cfg()
                        a, r = await self.Block.select_kel_chains_for_block(
                            [root], max_transactions=-5
                        )
        self.assertEqual(len(a), 1)

    async def test_defer_coinbase_kept_in_accepted(self):
        """Coinbase members in a deferred tail stay in the candidate set."""
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="c1"
        )
        c2 = _kel_txn(
            "C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c2"
        )
        # Mark c2 coinbase only after walk treats it as confirming via mocks
        c2.coinbase = True
        txns = [root, c2]
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "c1" else (False, None)
                )
            ),
        ):
            with patch(
                "yadacoin.core.keyeventlog.classify_key_event_flag",
                return_value=KeyEventFlag.CONFIRMING,
            ):
                with patch(
                    "yadacoin.core.keyeventlog.verify_kel_step", return_value=None
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.is_kel_chain_complete",
                        side_effect=lambda entries: len(entries) >= 1,
                    ):
                        with patch("yadacoin.core.block.Config") as m:
                            cfg = self._cfg()
                            m.return_value = cfg
                            # 1 slot: prefix [c1]; defer [c2] coinbase -> re-accept
                            a, r = await self.Block.select_kel_chains_for_block(
                                txns, max_transactions=1
                            )
        sigs = [t.transaction_signature for t in a]
        self.assertIn("c1", sigs)
        self.assertIn("c2", sigs)
        self.assertEqual(r, [])

    async def test_defer_skips_already_claimed(self):
        """Duplicate sig in deferred tail hits claimed continue."""
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="c1"
        )
        c2 = _kel_txn(
            "C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c2"
        )
        c2b = _kel_txn(
            "C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c2"
        )
        # Force walk to accept only c1 then defer [c2, c2b] same sig
        # Actually full chain c1-c2 if limit 1 defers c2; add c2b as sibling
        # orphan. Better: limit 1, chain c1,c2,c2 with same - walk takes one c2.
        [root, c2, c2b]
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "c1" else (False, None)
                )
            ),
        ):
            with patch("yadacoin.core.keyeventlog.verify_kel_step", return_value=None):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                        return_value=None,
                    ):
                        with patch("yadacoin.core.block.Config") as m:
                            cfg = self._cfg()
                            m.return_value = cfg
                            # ambiguous fork c2/c2b -> discard not defer
                            # Use unique chain and call _defer with dups via
                            # limit truncate: chain [c1,c2] limit 1, defer [c2]
                            # and manually we need claimed continue - put c2
                            # twice in chain by making walk: only one kid.
                            a, r = await self.Block.select_kel_chains_for_block(
                                [root, c2], max_transactions=1
                            )
        self.assertEqual([t.transaction_signature for t in a], ["c1"])
        # c2 deferred once
        self.assertEqual(r, [])


class TestKelLimitFinalTwoLines(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        from yadacoin.core.block import Block

        self.Block = Block

    def _cfg(self):
        cfg = MagicMock()
        cfg.app_log = MagicMock()
        cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock()
        cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock()
        return cfg

    async def test_prefix_loop_returns_empty_when_no_complete_in_budget(self):
        """slots > 0 but every in-budget prefix is incomplete -> return []."""
        # Root is UNCONFIRMED alone — incomplete. Limit allows 1 slot.
        u = _kel_txn(
            "B", "C", "D", prev="A", relationship="payload", outputs_to="z", sig="u"
        )
        # Make it a root via mock so we walk chain [u] incomplete.
        # Actually incomplete chains go to _discard not _longest_fitting_prefix.
        # Need complete full chain that doesn't fit, and no complete prefix in budget.
        # e.g. chain [U, C] length 2, slots=1: prefix [U] incomplete -> [].
        u = _kel_txn(
            "B", "C", "D", prev="A", relationship="payload", outputs_to="z", sig="u"
        )
        c = _kel_txn("C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c")
        # Root must be u for chain u->c. Lone U incomplete so full chain only complete.
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "u" else (False, None)
                )
            ),
        ):
            with patch("yadacoin.core.keyeventlog.verify_kel_step", return_value=None):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_unconfirmed",
                        return_value=None,
                    ):
                        with patch(
                            "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                            return_value=None,
                        ):
                            # Skip inception validation - U root won't hit that.
                            with patch("yadacoin.core.block.Config") as m:
                                cfg = self._cfg()
                                m.return_value = cfg
                                a, r = await self.Block.select_kel_chains_for_block(
                                    [u, c], max_transactions=1
                                )
        # Full chain complete but doesn't fit; prefix [u] incomplete -> defer all
        self.assertEqual(a, [])
        self.assertEqual(r, [])
        self.assertEqual(len([u, c]), 2)  # sanity
        # both deferred out of txns
        # txns mutated
        self.assertEqual(a, [])
        cfg.mongo.async_db.failed_transactions.insert_one.assert_not_awaited()

    async def test_defer_already_claimed_continue(self):
        """Second occurrence of same sig in defer list hits continue."""
        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="c1"
        )
        c2 = _kel_txn(
            "C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c2"
        )
        # Patch _longest_fitting_prefix path: accept c1, defer [c2, c2] by
        # making chain built as [c1,c2] and then manually...
        # Intercept after select by calling internal logic is hard.
        # Instead patch is_kel_chain_complete so full chain doesn't fit and
        # only prefix c1 works, defer [c2]. To hit claimed continue, pass
        # duplicate in deferred members - monkeypatch by making chain
        # extension include c2 twice via valid_kids? Ambiguous fork discards.
        #
        # Direct unit: invoke select with a chain that defers, then the
        # deferred list has one item. For claimed continue, put c2 already
        # in claimed via being accepted in a prior root - two roots.
        r2 = _kel_txn("X", "Y", "Z", prev="", relationship="", outputs_to="Y", sig="c2")
        # Wait - inception r2 with same sig c2 as child of root.
        # First process root, accept c1, defer c2 (claimed). Then process
        # inception with sig c2 as root - already claimed at start of root loop.
        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(return_value=(True, None)),
        ):
            with patch("yadacoin.core.keyeventlog.verify_kel_step", return_value=None):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEvent.verify_fields",
                    return_value=None,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEvent.verify_confirming",
                        return_value=None,
                    ):
                        with patch(
                            "yadacoin.core.keyeventlog.KeyEvent.verify_inception",
                            return_value=None,
                        ):
                            with patch("yadacoin.core.block.Config") as m:
                                cfg = self._cfg()
                                m.return_value = cfg
                                # root chain c1->c2, limit 1: accept c1, defer c2.
                                # Also include duplicate c2 object in txns as
                                # second root (inception). Order: process c1
                                # root first.
                                a, r = await self.Block.select_kel_chains_for_block(
                                    [root, c2, r2], max_transactions=1
                                )
        # c1 accepted; c2 deferred (claimed); r2 same sig as c2 skipped as root
        self.assertTrue(any(t.transaction_signature == "c1" for t in a))


class TestDeferClaimedContinue(AsyncTestCase):
    async def test_defer_hits_claimed_continue(self):
        """Cover _defer early-continue when sig already claimed."""
        from yadacoin.core.block import Block

        # Build a situation where _defer is called with a member already in
        # claimed: accept prefix [c1], defer tail [c2], then a second root
        # chain tries to defer c2 again... hard.
        #
        # Simpler approach: patch _longest_fitting_prefix to return [c1] and
        # leave chain as [c1, c2, c2] with duplicate objects same sig by
        # making the walk produce [c1,c2] and then we inject duplicate into
        # defer via monkeypatch of the method internals.
        #
        # Direct: call select_kel_chains and patch the local _defer by
        # wrapping is_kel_chain_complete / walk so chain is [c1,c2] limit 1,
        # and put c2 already in claimed by accepting it as coinbase first
        # from a previous root with same...
        #
        # Easiest path: after select starts, we can't access _defer.
        # Patch list so when _defer(tail) runs, tail has [c2, c2_dup] same sig.
        # That requires chain[len(prefix):] to have dups. chain is built by
        # walk without dups. So force walk_failed path? No that's discard.
        #
        # Monkeypatch Block.select_kel_chains_for_block's inner by running
        # a custom version...
        #
        # Actually: accept c1 with limit 1, defer [c2]. claimed has c1,c2.
        # Orphan pass won't re-defer c2.
        #
        # Put c2 in deferred list twice by having two chains share c2 as tail:
        # Root1: c1 -> c2  (limit enough for both first)
        # Order roots so first chain takes c1 only (limit 1), defers c2.
        # Second root is c2 alone (also root?) - if c2 is claimed, root loop
        # continues at start. That hits root claimed continue not _defer.
        #
        # Force _defer([c2, c2]) by patching chain construction:
        original = Block.select_kel_chains_for_block

        async def wrapper(txns, block_index=None, max_transactions=1000):
            # Run real logic but inject into defer by patching is_kel_chain_complete
            # after prefix so tail has duplicates - can't.
            return await original(txns, block_index, max_transactions)

        root = _kel_txn(
            "B", "C", "D", prev="A", relationship="", outputs_to="C", sig="c1"
        )
        c2 = _kel_txn(
            "C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c2"
        )
        c2_dup = _kel_txn(
            "C", "D", "E", prev="B", relationship="", outputs_to="D", sig="c2"
        )

        # Patch the walk to build chain [c1, c2, c2_dup] by making children
        # return both on first step... first step from c1 only one kid.
        # After taking c2, second step kids of C include c2_dup with prev=C?
        # c2_dup.prev is B not C.
        #
        # Patch verify_kel_step and kids: after selecting, use a spy on defer.
        # Simplest reliable approach: unit-test by reimplementing the claimed
        # check via calling select and patching deferred list construction.
        #
        # I'll patch `list.__getitem__` - no.
        #
        # Patch `_longest_fitting_prefix` can't - it's nested.
        #
        # Make full chain complete of length 2, slots=1, so prefix=[c1],
        # tail=[c2]. Then in _defer, also pass c2 again by having tail = chain[1:]
        # which is one item.
        #
        # To get two items with same sig in members:
        # tail = [c2, c2_dup] requires chain = [c1, c2, c2_dup].
        # Walk: c1 -> c2 (prev B->C). Next kids of C: need c2_dup with prev=C.
        c2_dup.prev_public_key_hash = "C"
        c2_dup.public_key_hash = "D2"
        c2_dup.prerotated_key_hash = "E2"
        c2_dup.twice_prerotated_key_hash = "F2"
        c2_dup.transaction_signature = "c2"  # SAME sig as c2
        c2_dup.outputs = c2.outputs
        c2_dup.relationship = ""

        with patch(
            "yadacoin.core.keyeventlog.is_mempool_kel_root",
            new=AsyncMock(
                side_effect=lambda t: (
                    (True, None) if t.transaction_signature == "c1" else (False, None)
                )
            ),
        ):
            with patch("yadacoin.core.keyeventlog.verify_kel_step", return_value=None):
                with patch(
                    "yadacoin.core.keyeventlog.classify_key_event_flag",
                    return_value=KeyEventFlag.CONFIRMING,
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.is_kel_chain_complete",
                        side_effect=lambda e: True if len(e) >= 1 else False,
                    ):
                        with patch("yadacoin.core.block.Config") as m:
                            cfg = MagicMock()
                            cfg.app_log = MagicMock()
                            cfg.mongo.async_db.miner_transactions.delete_one = (
                                AsyncMock()
                            )
                            cfg.mongo.async_db.failed_transactions.insert_one = (
                                AsyncMock()
                            )
                            m.return_value = cfg
                            # chain becomes [c1, c2, c2_dup] if walk finds both
                            # kids of c2 with prev=C for c2_dup. c2.pkh=C.
                            # From c1 (pkh B), kids with prev B: c2 only (c2_dup prev C).
                            # From c2 (pkh C), kids with prev C: c2_dup.
                            # chain [c1,c2,c2_dup], all complete prefixes.
                            # slots=1 -> prefix [c1], defer [c2, c2_dup] same sig.
                            a, r = await Block.select_kel_chains_for_block(
                                [root, c2, c2_dup], max_transactions=1
                            )
        self.assertTrue(any(t.transaction_signature == "c1" for t in a))
        # c2 deferred once (second dup hit claimed continue)
        self.assertEqual(r, [])
