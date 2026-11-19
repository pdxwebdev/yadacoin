import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.transaction import Transaction


def _aiter(docs):
    async def gen():
        for doc in docs:
            yield doc

    return gen()


def _txn(sig, pkh, prev):
    txn = Transaction.__new__(Transaction)
    txn.transaction_signature = sig
    txn.public_key_hash = pkh
    txn.prev_public_key_hash = prev
    txn.coinbase = False
    txn.template_kel = False
    txn.config = MagicMock()
    return txn


class TestKelSlotUniqueness(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        patcher = patch.object(
            Transaction, "are_kel_fields_populated", lambda self: True
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_siblings_match_same_slot(self):
        a = _txn("a", "P", "X")
        b = _txn("b", "P", "X")
        self.assertTrue(a.kel_slot_matches(b))

    def test_different_key_or_prev_does_not_match(self):
        a = _txn("a", "P", "X")
        self.assertFalse(a.kel_slot_matches(_txn("b", "Q", "X")))
        self.assertFalse(a.kel_slot_matches(_txn("b", "P", "Y")))

    def test_same_signature_is_not_a_sibling(self):
        a = _txn("a", "P", "X")
        self.assertFalse(a.kel_slot_matches(_txn("a", "P", "X")))

    def test_batch_check_detects_sibling(self):
        a = _txn("a", "P", "X")
        b = _txn("b", "P", "X")
        self.assertTrue(a.kel_slot_in_batch([b]))
        self.assertFalse(a.kel_slot_in_batch([_txn("c", "Q", "X")]))
        self.assertFalse(a.kel_slot_in_batch(None))

    def test_coinbase_and_template_are_not_slot_scoped(self):
        a = _txn("a", "P", "X")
        a.coinbase = True
        self.assertFalse(a.is_kel_slot_scoped())
        b = _txn("b", "P", "X")
        b.template_kel = True
        self.assertFalse(b.is_kel_slot_scoped())

    async def test_is_kel_slot_taken_true_when_sibling_stored(self):
        a = _txn("a", "P", "X")
        a.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value={"id": "b"}
        )
        self.assertTrue(await a.is_kel_slot_taken())
        query = a.config.mongo.async_db.miner_transactions.find_one.await_args[0][0]
        self.assertEqual(query["id"], {"$ne": "a"})
        self.assertEqual(query["public_key_hash"], "P")
        self.assertEqual(query["prev_public_key_hash"], "X")

    async def test_is_kel_slot_taken_false_when_empty(self):
        a = _txn("a", "P", "X")
        a.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value=None
        )
        self.assertFalse(await a.is_kel_slot_taken())

    async def test_upsert_mempool_preserves_existing_first_seen(self):
        a = _txn("a", "P", "X")
        db = a.config.mongo.async_db
        db.miner_transactions.find_one = AsyncMock(return_value={"first_seen": 100})
        db.miner_transactions.replace_one = AsyncMock()
        a.to_dict = MagicMock(return_value={"id": "a"})
        await a.upsert_mempool()
        doc = db.miner_transactions.replace_one.await_args[0][1]
        self.assertEqual(doc["first_seen"], 100)

    async def test_upsert_mempool_recovers_first_seen_from_failed(self):
        a = _txn("a", "P", "X")
        db = a.config.mongo.async_db
        db.miner_transactions.find_one = AsyncMock(return_value=None)
        db.failed_transactions.find_one = AsyncMock(return_value={"first_seen": 50})
        db.miner_transactions.replace_one = AsyncMock()
        a.to_dict = MagicMock(return_value={"id": "a"})
        await a.upsert_mempool()
        doc = db.miner_transactions.replace_one.await_args[0][1]
        self.assertEqual(doc["first_seen"], 50)

    async def test_purge_kel_slot_siblings_archives_and_deletes(self):
        confirmed = _txn("winner", "P", "X")
        async_db = MagicMock()
        async_db.miner_transactions.find = MagicMock(
            return_value=_aiter([{"_id": 1, "id": "loser", "first_seen": 9}])
        )
        async_db.failed_transactions.insert_one = AsyncMock()
        async_db.miner_transactions.delete_one = AsyncMock()
        await Transaction.purge_kel_slot_siblings(async_db, [confirmed])
        record = async_db.failed_transactions.insert_one.await_args[0][0]
        self.assertEqual(record["reason"], "KELSlotSuperseded")
        self.assertEqual(record["first_seen"], 9)
        self.assertNotIn("_id", record["txn"])
        async_db.miner_transactions.delete_one.assert_awaited_with({"id": "loser"})


class TestVerifyBatchSlotGate(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from coincurve import PrivateKey

        self.public_key = PrivateKey().public_key.format(compressed=True).hex()
        for patcher in (
            patch.object(Transaction, "are_kel_fields_populated", lambda self: True),
            patch.object(Transaction, "generate_hash", AsyncMock(return_value="h")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _gate_txn(self, sig, pkh, prev):
        txn = _txn(sig, pkh, prev)
        txn.public_key = self.public_key
        return txn

    async def test_batch_sibling_rejected_at_fork(self):
        from yadacoin.core.chain import CHAIN
        from yadacoin.core.transaction import InvalidTransactionException

        block = MagicMock(index=CHAIN.KEL_UNIQUE_SLOT_FORK)
        a = self._gate_txn("a", "P", "X")
        sibling = self._gate_txn("b", "P", "X")
        with self.assertRaisesRegex(InvalidTransactionException, "in this block"):
            await a.verify(check_kel=True, block=block, batch_txns=[sibling])

    async def test_batch_sibling_rejected_when_block_unknown(self):
        from yadacoin.core.transaction import InvalidTransactionException

        a = self._gate_txn("a", "P", "X")
        sibling = self._gate_txn("b", "P", "X")
        with self.assertRaisesRegex(InvalidTransactionException, "in this block"):
            await a.verify(check_kel=True, batch_txns=[sibling])

    async def test_batch_sibling_not_gated_before_fork(self):
        from yadacoin.core.chain import CHAIN
        from yadacoin.core.transaction import InvalidTransactionException

        block = MagicMock(index=CHAIN.KEL_UNIQUE_SLOT_FORK - 1)
        a = self._gate_txn("a", "P", "X")
        sibling = self._gate_txn("b", "P", "X")
        try:
            await a.verify(check_kel=True, block=block, batch_txns=[sibling])
        except InvalidTransactionException as exc:
            self.assertNotIn("in this block", str(exc))
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()


class TestKelSlotHelperBranches(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        patcher = patch.object(
            Transaction, "are_kel_fields_populated", lambda self: True
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_matches_none_and_unscoped_other(self):
        a = _txn("a", "P", "X")
        self.assertFalse(a.kel_slot_matches(None))
        coinbase = _txn("b", "P", "X")
        coinbase.coinbase = True
        self.assertFalse(a.kel_slot_matches(coinbase))

    def test_batch_and_taken_skip_when_self_not_scoped(self):
        a = _txn("a", "P", "X")
        a.coinbase = True
        self.assertFalse(a.kel_slot_in_batch([_txn("b", "P", "X")]))

    async def test_is_kel_slot_taken_skips_query_when_not_scoped(self):
        a = _txn("a", "P", "X")
        a.coinbase = True
        a.config.mongo.async_db.miner_transactions.find_one = AsyncMock()
        self.assertFalse(await a.is_kel_slot_taken())
        a.config.mongo.async_db.miner_transactions.find_one.assert_not_awaited()

    async def test_purge_skips_unscoped_transaction(self):
        coinbase = _txn("cb", "P", "")
        coinbase.coinbase = True
        async_db = MagicMock()
        async_db.miner_transactions.find = MagicMock()
        async_db.failed_transactions.insert_one = AsyncMock()
        async_db.miner_transactions.delete_one = AsyncMock()
        await Transaction.purge_kel_slot_siblings(async_db, [coinbase])
        async_db.miner_transactions.find.assert_not_called()
        async_db.failed_transactions.insert_one.assert_not_awaited()

    async def test_assert_unique_inception_skips_spend_with_inputs(self):
        txn = _txn("spend", "P", "")
        txn.inputs = [MagicMock()]
        txn.config.mongo.async_db.blocks.find_one = AsyncMock()
        await txn.assert_unique_inception(block_index=1)
        txn.config.mongo.async_db.blocks.find_one.assert_not_awaited()

    async def test_verify_rejects_mempool_slot_taken(self):
        from coincurve import PrivateKey

        from yadacoin.core.transaction import InvalidTransactionException

        txn = _txn("a", "P", "X")
        txn.public_key = PrivateKey().public_key.format(compressed=True).hex()
        txn.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value={"id": "b"}
        )
        with patch.object(Transaction, "generate_hash", AsyncMock(return_value="h")):
            with self.assertRaisesRegex(InvalidTransactionException, "Duplicate KEL"):
                await txn.verify(check_kel=True, mempool=True)


class _FakeOid:
    def __init__(self, ts):
        self.generation_time = MagicMock()
        self.generation_time.timestamp = MagicMock(return_value=ts)


def _aiter(docs):
    async def gen():
        for doc in docs:
            yield doc

    return gen()


def _selector_cfg(arrival_docs=None, arrival_error=None):
    cfg = MagicMock()
    cfg.app_log = MagicMock()
    coll = cfg.mongo.async_db.miner_transactions
    if arrival_error is not None:
        coll.find = MagicMock(side_effect=arrival_error)
    else:
        coll.find = MagicMock(return_value=_aiter(arrival_docs or []))
    coll.delete_one = AsyncMock()
    cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock()
    return cfg


def _root(sig, pkh="B", prev="A"):
    txn = _txn(sig, pkh, prev)
    txn.to_dict = MagicMock(return_value={"id": sig})
    return txn


def _patch_select(**overrides):
    defaults = {
        "yadacoin.core.keyeventlog.is_mempool_kel_root": AsyncMock(
            side_effect=lambda t: (t.transaction_signature.startswith("r"), None)
        ),
        "yadacoin.core.keyeventlog.classify_key_event_flag": MagicMock(
            return_value=__import__(
                "yadacoin.core.keyeventlog", fromlist=["KeyEventFlag"]
            ).KeyEventFlag.UNCONFIRMED
        ),
        "yadacoin.core.keyeventlog.kel_successor_flag_allowed": MagicMock(
            return_value=True
        ),
        "yadacoin.core.keyeventlog.verify_kel_step": MagicMock(return_value=None),
        "yadacoin.core.keyeventlog.is_kel_chain_complete": MagicMock(return_value=True),
        "yadacoin.core.block.Block.tag_kel_chain_entries": MagicMock(),
    }
    defaults.update(overrides)
    stack = []
    for target, value in defaults.items():
        patcher = patch(target, new=value)
        patcher.start()
        stack.append(patcher)
    return stack


class TestDuplicateRootHelperBranches(unittest.TestCase):
    def test_skips_empty_public_key_hash(self):
        from yadacoin.core.block import Block

        with patch.object(Transaction, "are_kel_fields_populated", lambda s: True):
            blank = _txn("blank", "", "")
            other = _txn("other", "P", "")
            self.assertIsNone(Block.duplicate_kel_root_slot([blank, other]))

    def test_verify_rejects_two_roots_at_fork(self):
        from yadacoin.core.block import Block
        from yadacoin.core.chain import CHAIN

        index = CHAIN.KEL_UNIQUE_SLOT_FORK
        block = Block.__new__(Block)
        block.index = index
        block.version = CHAIN.get_version_for_height(index)
        coinbase = _txn("cb", "Z", "")
        coinbase.coinbase = True
        block.transactions = [coinbase, _txn("a", "P", ""), _txn("b", "P", "")]
        with patch.object(Transaction, "are_kel_fields_populated", lambda s: True):
            with self.assertRaisesRegex(Exception, "two KEL roots"):
                __import__("asyncio").run(block._verify())


class TestSelectKelChainsSlotCoverage(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        patcher = patch.object(
            Transaction, "are_kel_fields_populated", lambda self: True
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        for p in _patch_select():
            self.addCleanup(p.stop)

    async def _run(self, roots, cfg):
        from yadacoin.core.block import Block

        with patch("yadacoin.core.block.Config", return_value=cfg):
            return await Block.select_kel_chains_for_block(list(roots))

    async def test_arrival_falls_back_to_oid_generation_time(self):
        cfg = _selector_cfg(
            [
                {"id": "r1", "first_seen": 1},
                {"id": "r2", "_id": _FakeOid(5)},
            ]
        )
        accepted, rejected = await self._run([_root("r1"), _root("r2")], cfg)
        self.assertEqual([t.transaction_signature for t in rejected], ["r2"])
        self.assertEqual([t.transaction_signature for t in accepted], ["r1"])

    async def test_arrival_lookup_failure_logs_and_continues(self):
        cfg = _selector_cfg(arrival_error=RuntimeError("boom"))
        accepted, rejected = await self._run([_root("r1"), _root("r2")], cfg)
        cfg.app_log.warning.assert_called()

    async def test_drop_duplicate_failed_insert_logs(self):
        cfg = _selector_cfg(
            [{"id": "r1", "first_seen": 1}, {"id": "r2", "first_seen": 2}]
        )
        cfg.mongo.async_db.failed_transactions.insert_one = AsyncMock(
            side_effect=RuntimeError("db fail")
        )
        await self._run([_root("r1"), _root("r2")], cfg)
        cfg.app_log.warning.assert_called()

    async def test_drop_duplicate_delete_failure_logs(self):
        cfg = _selector_cfg(
            [{"id": "r1", "first_seen": 1}, {"id": "r2", "first_seen": 2}]
        )
        cfg.mongo.async_db.miner_transactions.delete_one = AsyncMock(
            side_effect=RuntimeError("db fail")
        )
        await self._run([_root("r1"), _root("r2")], cfg)
        cfg.app_log.warning.assert_called()

    async def test_ambiguous_template_fork_discards_and_skips_claimed(self):
        template = _txn("t1", "C", "B")
        template.coinbase = True
        template.to_dict = MagicMock(return_value={"id": "t1"})
        c1 = _txn("c1", "C", "B")
        c1.to_dict = MagicMock(return_value={"id": "c1"})
        c1b = _txn("c1", "C", "B")
        c1b.to_dict = MagicMock(return_value={"id": "c1"})
        cfg = _selector_cfg([])
        accepted, rejected = await self._run([_root("r1"), template, c1, c1b], cfg)
        self.assertEqual([t.transaction_signature for t in accepted], ["t1"])
        self.assertEqual([t.transaction_signature for t in rejected], ["r1", "c1"])
        cfg.app_log.warning.assert_not_called()


class TestEnsureKelSlotIndex(unittest.IsolatedAsyncioTestCase):
    def _config(self, groups, existing_marker=None, index_error=None, docs=None):
        cfg = MagicMock()
        cfg.app_log = MagicMock()
        db = cfg.mongo.async_db
        db.migrations.find_one = AsyncMock(return_value=existing_marker)
        db.migrations.update_one = AsyncMock()
        coll = db.miner_transactions
        coll.aggregate = MagicMock(return_value=_aiter(groups))
        coll.find_one = AsyncMock(side_effect=docs or [])
        coll.delete_one = AsyncMock()
        coll.create_indexes = AsyncMock(side_effect=index_error)
        db.failed_transactions.insert_one = AsyncMock()
        return cfg

    async def test_short_circuits_when_migration_complete(self):
        cfg = self._config([], existing_marker={"complete": True})
        await Transaction.ensure_kel_slot_index(cfg)
        cfg.mongo.async_db.miner_transactions.aggregate.assert_not_called()

    async def test_archives_losers_and_marks_migration(self):
        group = {
            "docs": [
                {"id": "win", "first_seen": 1},
                {"id": "loserA", "first_seen": 2},
                {"id": "loserB", "_oid": _FakeOid(3)},
            ]
        }
        cfg = self._config([group], docs=[{"id": "loserA"}, None])
        await Transaction.ensure_kel_slot_index(cfg)
        db = cfg.mongo.async_db
        record = db.failed_transactions.insert_one.await_args[0][0]
        self.assertEqual(record["reason"], "KELSlotDuplicate")
        self.assertEqual(record["txn"], {"id": "loserA"})
        db.miner_transactions.delete_one.assert_awaited_once_with({"id": "loserA"})
        db.miner_transactions.create_indexes.assert_awaited()
        db.migrations.update_one.assert_awaited()

    async def test_index_creation_failure_logs_and_skips_marker(self):
        cfg = self._config([], index_error=RuntimeError("no index"))
        await Transaction.ensure_kel_slot_index(cfg)
        cfg.app_log.error.assert_called()
        cfg.mongo.async_db.migrations.update_one.assert_not_awaited()
