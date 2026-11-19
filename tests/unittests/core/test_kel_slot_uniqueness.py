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
