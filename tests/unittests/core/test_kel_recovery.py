"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 - for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.
"""

"""
Tests for KEL location-recovery delegation
(``yadacoin.core.keyeventlog`` recovery helpers + verifier).
"""

import os
import unittest
from hashlib import sha256
from unittest.mock import AsyncMock, MagicMock, patch

from coincurve import PublicKey

import yadacoin.core.config
from yadacoin.core.config import Config
from yadacoin.core.keyeventlog import (
    KELRecoveryAlreadyConsumedException,
    KELRecoveryAnnouncementMissingException,
    KELRecoveryInvalidProofException,
    KELRecoveryMalformedProofException,
    KELRecoveryUnknownPreviousKELException,
    KeyEvent,
    KeyEventChainStatus,
    KeyEventFlag,
    KeyEventLog,
    find_active_recovery_witness_hash,
    get_recovers_proof,
    get_recovery_announcement_witness_hash,
    is_recovers_inception,
    is_recovery_announcement,
)
from yadacoin.core.locationrecovery import CURVE_N
from yadacoin.core.mongo import Mongo
from yadacoin.core.transaction import Transaction

from ..test_setup import AsyncTestCase

# ── Schnorr proof helper (mirrors JS prover) ──────────────────────────────────


def _make_proof(x: int, prev_key_hash: str = None, r: int = None):
    """Return a valid recovers-proof tuple ``(commitment, R, s)`` (all hex)."""
    if r is None:
        while True:
            r = int.from_bytes(os.urandom(32), "big") % CURVE_N
            if r != 0:
                break
    x_bytes = x.to_bytes(32, "big")
    r_bytes = r.to_bytes(32, "big")
    C_hex = PublicKey.from_secret(x_bytes).format(compressed=True).hex()
    R_hex = PublicKey.from_secret(r_bytes).format(compressed=True).hex()
    prev_bytes = prev_key_hash.encode("utf-8") if prev_key_hash else b"\x00" * 32
    e = (
        int.from_bytes(
            sha256(bytes.fromhex(R_hex) + bytes.fromhex(C_hex) + prev_bytes).digest(),
            "big",
        )
        % CURVE_N
    )
    s = (r - e * x) % CURVE_N
    return C_hex, R_hex, s.to_bytes(32, "big").hex()


def _witness_hash_for(commitment_hex: str) -> str:
    return sha256(bytes.fromhex(commitment_hex)).hexdigest()


def _random_scalar() -> int:
    while True:
        n = int.from_bytes(os.urandom(32), "big") % CURVE_N
        if n != 0:
            return n


# ── Fixture builders ──────────────────────────────────────────────────────────


def _make_txn(
    relationship="",
    public_key_hash="",
    prev_public_key_hash="",
    prerotated="",
    twice_prerotated="",
    txn_id=None,
    public_key="02" + "00" * 32,
):
    """Return a Transaction parsed from a minimal dict (so __init__ runs)."""
    return Transaction.from_dict(
        {
            "time": 1,
            "id": txn_id or "sig-" + os.urandom(8).hex(),
            "rid": "",
            "relationship": relationship,
            "public_key": public_key,
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "h" + os.urandom(8).hex(),
            "inputs": [],
            "outputs": [{"to": prerotated or public_key_hash, "value": 0}],
            "version": 7,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": prerotated,
            "twice_prerotated_key_hash": twice_prerotated,
            "public_key_hash": public_key_hash,
            "prev_public_key_hash": prev_public_key_hash,
        }
    )


def _wrap_block(txn: Transaction, index: int):
    """Wrap a single Transaction into a minimal block dict for DB insertion."""
    return {
        "version": 5,
        "time": 1,
        "index": index,
        "public_key": txn.public_key,
        "prevHash": "0" * 64,
        "nonce": "0",
        "transactions": [txn.to_dict()],
        "hash": "blockhash-" + os.urandom(8).hex(),
        "merkleRoot": "0" * 64,
        "special_min": False,
        "target": "0" * 63 + "1",
        "special_target": "0" * 63 + "1",
        "header": "h",
        "id": "blockid-" + os.urandom(8).hex(),
        "updated_at": 1.0,
    }


# ── Pure helper-function tests (no DB) ────────────────────────────────────────


class TestRecoveryRelationshipHelpers(unittest.TestCase):
    def test_get_recovery_announcement_witness_hash_present(self):
        txn = _make_txn(relationship={"recovery": "deadbeef" * 8})
        self.assertEqual(get_recovery_announcement_witness_hash(txn), "deadbeef" * 8)

    def test_get_recovery_announcement_witness_hash_absent(self):
        self.assertIsNone(
            get_recovery_announcement_witness_hash(_make_txn(relationship=""))
        )

    def test_get_recovery_announcement_witness_hash_wrong_type(self):
        # non-string value should be rejected
        txn = _make_txn(relationship={"recovery": 42})
        self.assertIsNone(get_recovery_announcement_witness_hash(txn))

    def test_get_recovery_announcement_witness_hash_empty_string(self):
        txn = _make_txn(relationship={"recovery": ""})
        self.assertIsNone(get_recovery_announcement_witness_hash(txn))

    def test_get_recovers_proof_present(self):
        txn = _make_txn(
            relationship={"recovers": {"commitment": "ab", "R": "cd", "s": "ef"}}
        )
        self.assertEqual(
            get_recovers_proof(txn), {"commitment": "ab", "R": "cd", "s": "ef"}
        )

    def test_get_recovers_proof_missing_field(self):
        txn = _make_txn(relationship={"recovers": {"commitment": "ab", "R": "cd"}})
        self.assertIsNone(get_recovers_proof(txn))

    def test_get_recovers_proof_field_wrong_type(self):
        txn = _make_txn(
            relationship={"recovers": {"commitment": 1, "R": "cd", "s": "ef"}}
        )
        self.assertIsNone(get_recovers_proof(txn))

    def test_get_recovers_proof_not_a_dict(self):
        txn = _make_txn(relationship={"recovers": "deadbeef"})
        self.assertIsNone(get_recovers_proof(txn))

    def test_is_recovery_announcement(self):
        self.assertTrue(
            is_recovery_announcement(_make_txn(relationship={"recovery": "ab" * 32}))
        )
        self.assertFalse(is_recovery_announcement(_make_txn(relationship="")))

    def test_is_recovers_inception_requires_prev_pkh_and_proof(self):
        good = _make_txn(
            relationship={"recovers": {"commitment": "a", "R": "b", "s": "c"}},
            prev_public_key_hash="1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8",
        )
        self.assertTrue(is_recovers_inception(good))

    def test_is_recovers_inception_no_prev_pkh(self):
        no_prev = _make_txn(
            relationship={"recovers": {"commitment": "a", "R": "b", "s": "c"}},
        )
        self.assertFalse(is_recovers_inception(no_prev))

    def test_is_recovers_inception_no_proof(self):
        no_proof = _make_txn(
            relationship="",
            prev_public_key_hash="1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8",
        )
        self.assertFalse(is_recovers_inception(no_proof))

    def test_find_active_recovery_witness_hash_returns_latest(self):
        log = [
            _make_txn(),
            _make_txn(relationship={"recovery": "aa" * 32}),
            _make_txn(),
            _make_txn(relationship={"recovery": "bb" * 32}),  # newer wins
            _make_txn(),
        ]
        self.assertEqual(find_active_recovery_witness_hash(log), "bb" * 32)

    def test_find_active_recovery_witness_hash_none_when_empty(self):
        self.assertIsNone(find_active_recovery_witness_hash([_make_txn()]))

    def test_get_recovery_announcement_witness_hash_from_recovery_transition(self):
        """Line 190: RecoveryTransition relationship → returns announcement.witness_hash."""
        from unittest.mock import MagicMock

        from yadacoin.core.recoveryannouncement import (
            RecoveryAnnouncement,
            RecoveryProof,
            RecoveryTransition,
        )

        proof = RecoveryProof("aa", "bb", "cc")
        ann = RecoveryAnnouncement("eeffgghh")
        rt = RecoveryTransition(proof, ann)
        txn = MagicMock()
        txn.relationship = rt
        self.assertEqual(get_recovery_announcement_witness_hash(txn), "eeffgghh")

    def test_get_recovers_proof_from_recovery_transition(self):
        """Lines 204-205: RecoveryTransition relationship → returns proof dict."""
        from unittest.mock import MagicMock

        from yadacoin.core.recoveryannouncement import (
            RecoveryAnnouncement,
            RecoveryProof,
            RecoveryTransition,
        )

        proof = RecoveryProof("aa", "bb", "cc")
        ann = RecoveryAnnouncement("dd")
        rt = RecoveryTransition(proof, ann)
        txn = MagicMock()
        txn.relationship = rt
        result = get_recovers_proof(txn)
        self.assertEqual(result, {"commitment": "aa", "R": "bb", "s": "cc"})


# ── verify_recovery_inception (mocked DB) ─────────────────────────────────────


class TestVerifyRecoveryInception(AsyncTestCase):
    """Cover ``KeyEvent.verify_recovery_inception`` paths.

    The DB lookup, ``build_from_public_key`` reconstruction, and successor
    search are all mocked so each test can target one specific failure mode.
    Mongo is replaced with a MagicMock so these tests run without a live DB.
    """

    async def asyncSetUp(self):
        yadacoin.core.config.CONFIG = Config()
        Config().network = "regnet"
        # Mock mongo so we don't need a live DB; aggregate is patched per-test.
        mock_mongo = MagicMock()
        mock_mongo.async_db = MagicMock()
        Config().mongo = mock_mongo
        self.config = Config()

        class AppLog:
            def warning(self, m):
                pass

            def info(self, m):
                pass

        Config().app_log = AppLog()

    def _make_recovers_ke(
        self,
        commitment,
        R,
        s,
        prev_pkh,
        public_key_hash="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
        prerotated="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
        twice_prerotated="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
        flag=KeyEventFlag.INCEPTION,
        status=KeyEventChainStatus.MEMPOOL,
    ):
        txn = _make_txn(
            relationship={"recovers": {"commitment": commitment, "R": R, "s": s}},
            public_key_hash=public_key_hash,
            prev_public_key_hash=prev_pkh,
            prerotated=prerotated,
            twice_prerotated=twice_prerotated,
        )
        ke = KeyEvent.__new__(KeyEvent)
        ke.txn = txn
        ke.flag = flag
        ke.status = status
        ke.config = Config()
        return ke

    def _delegator_log(self, prev_pkh, witness_hash):
        """Return a fake delegator KEL whose tip's pkh matches prev_pkh and
        whose latest entry announces ``witness_hash``."""
        tip = _make_txn(
            relationship={"recovery": witness_hash},
            public_key_hash=prev_pkh,
            prerotated="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
            twice_prerotated="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
        )
        return [tip]

    def _patch_delegator(self, delegator_log):
        """Patch the on-chain blocks lookup AND build_from_public_key to
        return *delegator_log*."""
        cursor = MagicMock()
        cursor.to_list = AsyncMock(
            return_value=[{"transactions": delegator_log[-1].to_dict()}]
        )
        Config().mongo.async_db.blocks.aggregate = MagicMock(return_value=cursor)
        return patch.object(
            KeyEventLog,
            "build_from_public_key",
            new=AsyncMock(return_value=delegator_log),
        )

    async def test_happy_path(self):
        prev_pkh = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        x = _random_scalar()
        C, R, s = _make_proof(x, prev_key_hash=prev_pkh)
        wh = _witness_hash_for(C)
        ke = self._make_recovers_ke(C, R, s, prev_pkh)

        with self._patch_delegator(self._delegator_log(prev_pkh, wh)):
            with patch.object(
                KeyEventLog, "find_recovery_successor", new=AsyncMock(return_value=None)
            ):
                # Should not raise
                await ke.verify_recovery_inception()

    async def test_unknown_previous_kel_raises(self):
        prev_pkh = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        x = _random_scalar()
        C, R, s = _make_proof(x, prev_key_hash=prev_pkh)
        ke = self._make_recovers_ke(C, R, s, prev_pkh)

        # No delegator txn matches in DB (blocks)
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[])
        Config().mongo.async_db.blocks.aggregate = MagicMock(return_value=cursor)
        # No delegator txn in mempool either → should raise
        Config().mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value=None
        )

        with self.assertRaises(KELRecoveryUnknownPreviousKELException):
            await ke.verify_recovery_inception()

    async def test_announcement_missing_raises(self):
        prev_pkh = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        x = _random_scalar()
        C, R, s = _make_proof(x, prev_key_hash=prev_pkh)
        ke = self._make_recovers_ke(C, R, s, prev_pkh)

        # Delegator KEL exists but has NO {recovery: ...} announcement.
        tip = _make_txn(
            relationship="",
            public_key_hash=prev_pkh,
            prerotated="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
            twice_prerotated="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
        )
        with self._patch_delegator([tip]):
            with patch.object(
                KeyEventLog,
                "find_recovery_successor",
                new=AsyncMock(return_value=None),
            ):
                with self.assertRaises(KELRecoveryAnnouncementMissingException):
                    await ke.verify_recovery_inception()

    async def test_commitment_does_not_match_announced_witness_hash_raises(self):
        prev_pkh = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        x = _random_scalar()
        C, R, s = _make_proof(x, prev_key_hash=prev_pkh)
        # Announce a witness hash for a DIFFERENT commitment.
        other_C, _, _ = _make_proof(_random_scalar(), prev_key_hash=prev_pkh)
        wrong_wh = _witness_hash_for(other_C)
        ke = self._make_recovers_ke(C, R, s, prev_pkh)

        with self._patch_delegator(self._delegator_log(prev_pkh, wrong_wh)):
            with patch.object(
                KeyEventLog,
                "find_recovery_successor",
                new=AsyncMock(return_value=None),
            ):
                with self.assertRaises(KELRecoveryInvalidProofException):
                    await ke.verify_recovery_inception()

    async def test_invalid_schnorr_proof_raises(self):
        prev_pkh = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        x = _random_scalar()
        C, R, s = _make_proof(x, prev_key_hash=prev_pkh)
        # Tamper s to break verification, but keep its 32-byte length so it
        # passes the announcement-hash binding.
        bad_s = ((int(s, 16) + 1) % CURVE_N).to_bytes(32, "big").hex()
        wh = _witness_hash_for(C)
        ke = self._make_recovers_ke(C, R, bad_s, prev_pkh)

        with self._patch_delegator(self._delegator_log(prev_pkh, wh)):
            with patch.object(
                KeyEventLog,
                "find_recovery_successor",
                new=AsyncMock(return_value=None),
            ):
                with self.assertRaises(KELRecoveryInvalidProofException):
                    await ke.verify_recovery_inception()

    async def test_proof_bound_to_other_kel_rejected(self):
        """A proof generated for KEL A must NOT verify against KEL B even if
        the announced witness hash on KEL B happens to match."""
        prev_a = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        prev_b = "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar"
        x = _random_scalar()
        C, R, s = _make_proof(x, prev_key_hash=prev_a)  # bound to A
        wh = _witness_hash_for(C)
        ke = self._make_recovers_ke(C, R, s, prev_b)  # claims B

        with self._patch_delegator(self._delegator_log(prev_b, wh)):
            with patch.object(
                KeyEventLog,
                "find_recovery_successor",
                new=AsyncMock(return_value=None),
            ):
                with self.assertRaises(KELRecoveryInvalidProofException):
                    await ke.verify_recovery_inception()

    async def test_already_consumed_raises(self):
        prev_pkh = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        x = _random_scalar()
        C, R, s = _make_proof(x, prev_key_hash=prev_pkh)
        wh = _witness_hash_for(C)
        ke = self._make_recovers_ke(C, R, s, prev_pkh)

        prior_successor = _make_txn(
            relationship={"recovers": {"commitment": "x", "R": "y", "s": "z"}},
            public_key_hash="1NewKeyHashBxxxxxxxxxxxxxxxxxxxxx",
            prev_public_key_hash=prev_pkh,
            prerotated="1NewKeyHashBxxxxxxxxxxxxxxxxxxxxx",
            twice_prerotated="1NewKeyHashBxxxxxxxxxxxxxxxxxxxxx",
            txn_id="prior-successor-id",
        )

        with self._patch_delegator(self._delegator_log(prev_pkh, wh)):
            with patch.object(
                KeyEventLog,
                "find_recovery_successor",
                new=AsyncMock(return_value=prior_successor),
            ):
                with self.assertRaises(KELRecoveryAlreadyConsumedException):
                    await ke.verify_recovery_inception()

    async def test_idempotent_self_is_not_already_consumed(self):
        """If find_recovery_successor returns *this* same txn, it counts as
        re-validation rather than a second consumption."""
        prev_pkh = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        x = _random_scalar()
        C, R, s = _make_proof(x, prev_key_hash=prev_pkh)
        wh = _witness_hash_for(C)
        ke = self._make_recovers_ke(C, R, s, prev_pkh)

        with self._patch_delegator(self._delegator_log(prev_pkh, wh)):
            with patch.object(
                KeyEventLog,
                "find_recovery_successor",
                new=AsyncMock(return_value=ke.txn),
            ):
                # Same transaction_signature → not a second consumption.
                await ke.verify_recovery_inception()

    async def test_malformed_proof_raises(self):
        prev_pkh = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        # Missing required fields.
        txn = _make_txn(
            relationship={"recovers": {"commitment": "ab"}},
            public_key_hash="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
            prev_public_key_hash=prev_pkh,
            prerotated="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
            twice_prerotated="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
        )
        ke = KeyEvent.__new__(KeyEvent)
        ke.txn = txn
        ke.flag = KeyEventFlag.INCEPTION
        ke.status = KeyEventChainStatus.MEMPOOL
        ke.config = Config()

        with self.assertRaises(KELRecoveryMalformedProofException):
            await ke.verify_recovery_inception()

    async def test_malformed_commitment_hex_raises(self):
        prev_pkh = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        x = _random_scalar()
        _, R, s = _make_proof(x, prev_key_hash=prev_pkh)
        # Non-hex commitment
        ke = self._make_recovers_ke("zzzz", R, s, prev_pkh)
        wh = "00" * 32

        with self._patch_delegator(self._delegator_log(prev_pkh, wh)):
            with patch.object(
                KeyEventLog,
                "find_recovery_successor",
                new=AsyncMock(return_value=None),
            ):
                with self.assertRaises(KELRecoveryMalformedProofException):
                    await ke.verify_recovery_inception()


# ── find_recovery_successor (real DB) ─────────────────────────────────────────


_VALID_PKH = "1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR"
_VALID_PREV = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"


class TestFindRecoverySuccessor(AsyncTestCase):
    async def asyncSetUp(self):
        yadacoin.core.config.CONFIG = Config()
        Config().mongo = Mongo()
        Config().network = "regnet"
        self.config = Config()

        class AppLog:
            def warning(self, m):
                pass

            def info(self, m):
                pass

        Config().app_log = AppLog()
        # Sentinel index range we use only for these tests.
        await self.config.mongo.async_db.blocks.delete_many(
            {"index": {"$gte": 900000, "$lt": 901000}}
        )
        await self.config.mongo.async_db.miner_transactions.delete_many(
            {"id": {"$regex": "^kel-recovery-test-"}}
        )

    async def asyncTearDown(self):
        await self.config.mongo.async_db.blocks.delete_many(
            {"index": {"$gte": 900000, "$lt": 901000}}
        )
        await self.config.mongo.async_db.miner_transactions.delete_many(
            {"id": {"$regex": "^kel-recovery-test-"}}
        )

    async def test_returns_none_when_no_successor(self):
        result = await KeyEventLog.find_recovery_successor(
            "1NoSuchKeyxxxxxxxxxxxxxxxxxxxxxxxx"
        )
        self.assertIsNone(result)

    async def test_finds_onchain_successor(self):
        successor_txn = _make_txn(
            relationship={"recovers": {"commitment": "ab", "R": "cd", "s": "ef"}},
            public_key_hash=_VALID_PKH,
            prev_public_key_hash=_VALID_PREV,
            prerotated=_VALID_PKH,
            twice_prerotated=_VALID_PKH,
            txn_id="kel-recovery-test-onchain",
        )
        await self.config.mongo.async_db.blocks.insert_one(
            _wrap_block(successor_txn, 900001)
        )

        result = await KeyEventLog.find_recovery_successor(_VALID_PREV)
        self.assertIsNotNone(result)
        self.assertEqual(result.transaction_signature, "kel-recovery-test-onchain")

    async def test_ignores_non_recovers_txn(self):
        """A txn with prev_public_key_hash but NO {recovers: ...} relationship
        is a normal rotation, not a recovery successor."""
        rot_txn = _make_txn(
            relationship="",
            public_key_hash=_VALID_PKH,
            prev_public_key_hash=_VALID_PREV,
            prerotated=_VALID_PKH,
            twice_prerotated=_VALID_PKH,
            txn_id="kel-recovery-test-rotation",
        )
        await self.config.mongo.async_db.blocks.insert_one(_wrap_block(rot_txn, 900002))

        self.assertIsNone(await KeyEventLog.find_recovery_successor(_VALID_PREV))

    async def test_finds_mempool_successor_when_not_onchain_only(self):
        succ = _make_txn(
            relationship={"recovers": {"commitment": "ab", "R": "cd", "s": "ef"}},
            public_key_hash=_VALID_PKH,
            prev_public_key_hash=_VALID_PREV,
            prerotated=_VALID_PKH,
            twice_prerotated=_VALID_PKH,
            txn_id="kel-recovery-test-mempool",
        )
        await self.config.mongo.async_db.miner_transactions.insert_one(succ.to_dict())

        # onchain_only=False → finds mempool entry
        result = await KeyEventLog.find_recovery_successor(
            _VALID_PREV, onchain_only=False
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.transaction_signature, "kel-recovery-test-mempool")

        # onchain_only=True → ignores mempool entry
        self.assertIsNone(
            await KeyEventLog.find_recovery_successor(_VALID_PREV, onchain_only=True)
        )


if __name__ == "__main__":
    unittest.main()
