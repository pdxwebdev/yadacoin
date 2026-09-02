"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import hashlib
import time
import unittest
from unittest.mock import AsyncMock, MagicMock

import yadacoin.core.config
from plugins.credentialissuer.zkp import generate_proof
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.credentialannouncement import (
    CLAIM_AGE_OVER_18,
    CredentialAnnouncement,
    did_for,
)
from yadacoin.core.locationrecovery import verify_proof
from yadacoin.core.transaction import InvalidTransactionException, Transaction

from ..test_setup import AsyncTestCase

_SUBJECT = "subjectUsernameSignatureAAAA"
_ISSUER = "issuerUsernameSignatureBBBB"
_ISSUER_ID = "identityAnnouncementTxnIdCCCC"


def _ann(expires=None):
    expires = int(expires or (time.time() + 3600))
    proof = generate_proof("11" * 32, prev_key_hash=_SUBJECT)
    vc = {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "type": ["VerifiableCredential", "AgeOver18Credential"],
        "issuer": did_for(_ISSUER),
        "credentialSubject": {"id": did_for(_SUBJECT), "ageOver18": True},
        "expirationDate": "2099-01-01T00:00:00Z",
        "expires": expires,
        "issuer_identity_announcement": _ISSUER_ID,
        "proof": proof,
    }
    return CredentialAnnouncement(
        subject_username_signature=_SUBJECT,
        issuer_username_signature=_ISSUER,
        issuer_identity_announcement=_ISSUER_ID,
        claim=CLAIM_AGE_OVER_18,
        expires=expires,
        vc=vc,
    )


class TestCredentialAnnouncement(unittest.TestCase):
    def test_round_trip(self):
        ann = _ann()
        ann2 = CredentialAnnouncement.from_dict(ann.to_dict())
        self.assertEqual(ann.to_string(), ann2.to_string())
        wrapped = {CredentialAnnouncement.RELATIONSHIP_KEY: ann.to_dict()}
        ann3 = CredentialAnnouncement.from_relationship(wrapped)
        self.assertEqual(ann.to_string(), ann3.to_string())

    def test_to_string_order(self):
        ann = _ann(expires=123)
        c, R, s = ann.proof_parts()
        self.assertEqual(
            ann.to_string(),
            _SUBJECT + _ISSUER + _ISSUER_ID + CLAIM_AGE_OVER_18 + "123" + c + R + s,
        )

    def test_zkp_verify_helper(self):
        ann = _ann()
        self.assertTrue(ann.verify_zkp())
        c, R, s = ann.proof_parts()
        self.assertTrue(verify_proof(c, R, s, prev_key_hash=_SUBJECT))
        self.assertFalse(verify_proof(c, R, s, prev_key_hash="wrong"))

    def test_relationship_key_does_not_collide(self):
        self.assertEqual(CredentialAnnouncement.RELATIONSHIP_KEY, "credential")
        self.assertNotEqual(
            CredentialAnnouncement.RELATIONSHIP_KEY, "credential_receipt"
        )


class TestCredentialAnnouncementFork(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        yadacoin.core.config.CONFIG = Config()

    async def test_fork_reject_below_height(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        ann = _ann()
        txn.relationship = ann
        txn.relationship_hash = hashlib.sha256(ann.to_string().encode()).digest().hex()
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = NodeKeyRotationManager._sign(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )
        block = MagicMock()
        block.index = CHAIN.CREDENTIAL_ANNOUNCEMENT_FORK - 1
        with self.assertRaises(InvalidTransactionException) as ctx:
            await txn.verify(check_credential_announcement=False, block=block)
        self.assertIn(
            "Credential announcement transactions not allowed", str(ctx.exception)
        )

    async def test_parse_from_dict(self):
        ann = _ann()
        raw = {
            "id": "fakeid",
            "public_key": "02" + "11" * 32,
            "relationship": {"credential": ann.to_dict()},
            "relationship_hash": "",
        }
        # public_key must be valid hex of a real key from CONFIG
        raw["public_key"] = yadacoin.core.config.CONFIG.public_key
        txn = Transaction.from_dict(raw)
        self.assertIsInstance(txn.relationship, CredentialAnnouncement)
        wrapped = txn.to_dict()["relationship"]
        self.assertIn("credential", wrapped)


class TestUniqueCredentialIssuance(AsyncTestCase):
    def _holder(self, sig="me", claim=None):
        pass

        class Holder:
            pass

        h = Holder()
        h.relationship = _ann()
        if claim:
            h.relationship.claim = claim
        h.transaction_signature = sig
        h.config = MagicMock()

        class Empty:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        h.config.mongo.async_db.blocks.find = MagicMock(return_value=Empty())
        h.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value=None
        )
        return h

    async def test_duplicate_in_batch_rejected(self):
        from yadacoin.core.transaction import InvalidTransactionException, Transaction

        a = self._holder("aaa")
        b = self._holder("bbb")
        with self.assertRaises(InvalidTransactionException) as ctx:
            await Transaction.assert_unique_credential_issuance(
                a, batch_txns=[b], use_mempool=False
            )
        self.assertIn("Duplicate credential issuance", str(ctx.exception))

    async def test_different_claim_allowed(self):
        from yadacoin.core.transaction import Transaction

        a = self._holder("aaa")
        b = self._holder("bbb")
        b.relationship.claim = "otherClaim"
        await Transaction.assert_unique_credential_issuance(
            a, batch_txns=[b], use_mempool=False
        )

    async def test_mempool_duplicate_rejected(self):
        from yadacoin.core.transaction import InvalidTransactionException, Transaction

        a = self._holder("aaa")
        a.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value={"id": "other"}
        )
        with self.assertRaises(InvalidTransactionException):
            await Transaction.assert_unique_credential_issuance(a, use_mempool=True)
