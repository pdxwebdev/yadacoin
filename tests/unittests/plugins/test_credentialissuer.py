"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from plugins.credentialissuer.handlers import CredentialListHandler
from plugins.credentialissuer.service import (
    _anchor_issue_kel,
    issue_credential,
    partition_issue_kel,
)
from plugins.credentialissuer.zkp import generate_proof
from yadacoin.core.keyeventlog import KeyEventFlag
from yadacoin.core.locationrecovery import verify_proof

from ..test_setup import AsyncTestCase


class TestZKP(AsyncTestCase):
    def test_generate_and_verify(self):
        subject = "subjectUsernameSignature"
        proof = generate_proof("ab" * 32, prev_key_hash=subject)
        self.assertTrue(
            verify_proof(
                proof["commitment"], proof["R"], proof["s"], prev_key_hash=subject
            )
        )
        self.assertFalse(
            verify_proof(
                proof["commitment"], proof["R"], proof["s"], prev_key_hash="other"
            )
        )


class TestWalletUnlock(AsyncTestCase):
    async def test_wallet_locked_returns_401_on_mint_routes(self):
        handler = CredentialListHandler.__new__(CredentialListHandler)
        handler.request = MagicMock()
        handler.request.method = "POST"
        handler.request.path = "/credential-issuer/api/v1/credentials"
        handler._finished = False
        handler.set_status = MagicMock()
        handler.render_as_json = MagicMock()
        handler.wallet_is_unlocked = AsyncMock(return_value=False)

        from yadacoin.http.base import BaseHandler

        async def fake_prepare(self, exceptions=None):
            return None

        with patch.object(BaseHandler, "prepare", fake_prepare):
            await CredentialListHandler.prepare(handler)
        handler.set_status.assert_called_with(401)


class _KelTxn:
    def __init__(self, sig, pkh, prev, flag, prerot):
        self.transaction_signature = sig
        self.public_key_hash = pkh
        self.prev_public_key_hash = prev
        self.prerotated_key_hash = prerot
        self.flag = flag

    def are_kel_fields_populated(self):
        return True


def _links(prev, kid, **_kwargs):
    if prev.public_key_hash != kid.prev_public_key_hash:
        raise ValueError("prev")
    if prev.prerotated_key_hash != kid.public_key_hash:
        raise ValueError("prerot")


def _allowed(prev_flag, next_flag):
    if prev_flag == KeyEventFlag.UNCONFIRMED:
        return next_flag == KeyEventFlag.CONFIRMING
    return next_flag in (KeyEventFlag.CONFIRMING, KeyEventFlag.UNCONFIRMED)


def _complete(entries):
    if not entries:
        return False
    return entries[-1].flag == KeyEventFlag.CONFIRMING


class TestIssueKelParent(AsyncTestCase):
    def _partition(self, onchain, mempool):
        with patch(
            "yadacoin.core.keyeventlog.classify_key_event_flag",
            side_effect=lambda txn: txn.flag,
        ), patch(
            "yadacoin.core.keyeventlog.kel_successor_flag_allowed",
            side_effect=_allowed,
        ), patch(
            "yadacoin.core.keyeventlog.verify_kel_step",
            side_effect=_links,
        ), patch(
            "yadacoin.core.keyeventlog.is_kel_chain_complete",
            side_effect=_complete,
        ):
            return partition_issue_kel(onchain, mempool)

    def test_drops_orphan_confirming_above_onchain_tip(self):
        onchain = _KelTxn("onchain", "tip", "older", KeyEventFlag.CONFIRMING, "next")
        orphan = _KelTxn(
            "MEUCIQCO2pfp",
            "orphan-pkh",
            "missing-parent",
            KeyEventFlag.CONFIRMING,
            "child",
        )
        keep, drop = self._partition(onchain, [orphan])
        self.assertEqual(keep, [])
        self.assertEqual(drop, [orphan])

    def test_keeps_stuck_unconfirmed_for_confirming_synthesis(self):
        onchain = _KelTxn("onchain", "tip", "older", KeyEventFlag.CONFIRMING, "file-u")
        stuck = _KelTxn(
            "file-u",
            "file-u",
            "tip",
            KeyEventFlag.UNCONFIRMED,
            "file-c",
        )
        keep, drop = self._partition(onchain, [stuck])
        self.assertEqual(keep, [stuck])
        self.assertEqual(drop, [])

    def test_keeps_complete_pair_and_drops_unlinked_orphan(self):
        onchain = _KelTxn("onchain", "tip", "older", KeyEventFlag.CONFIRMING, "file-u")
        unconfirmed = _KelTxn(
            "file-u", "file-u", "tip", KeyEventFlag.UNCONFIRMED, "file-c"
        )
        confirming = _KelTxn(
            "file-c", "file-c", "file-u", KeyEventFlag.CONFIRMING, "cred-u"
        )
        orphan = _KelTxn("orphan", "orphan", "gone", KeyEventFlag.CONFIRMING, "nowhere")
        keep, drop = self._partition(onchain, [orphan, confirming, unconfirmed])
        self.assertEqual(keep, [unconfirmed, confirming])
        self.assertEqual(drop, [orphan])


class _Cursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def __aiter__(self):
        self._i = 0
        return self

    async def __anext__(self):
        if self._i >= len(self._rows):
            raise StopAsyncIteration
        row = self._rows[self._i]
        self._i += 1
        return row


class TestAnchorIssueKel(AsyncTestCase):
    async def test_anchor_deletes_orphan_before_issue(self):
        onchain = _KelTxn("onchain", "tip", "older", KeyEventFlag.CONFIRMING, "next")
        onchain.inception_public_key_hash = "inception"
        orphan = _KelTxn(
            "MEUCIQCO2pfp-orphan",
            "orphan-pkh",
            "missing-parent",
            KeyEventFlag.CONFIRMING,
            "child",
        )
        config = MagicMock()
        config.kel_manager._k0 = {
            "private_key": b"\x11" * 32,
            "chain_code": b"\x00" * 32,
        }
        config.kel_manager._second_factor = "sf"
        config.seed = ""
        deleted = []

        async def delete_one(query):
            deleted.append(query)

        config.mongo.async_db.miner_transactions.find.return_value = _Cursor(
            [{"id": orphan.transaction_signature}]
        )
        config.mongo.async_db.miner_transactions.delete_one = delete_one

        with patch(
            "plugins.fileannouncement.service._kel_material",
            return_value=(config.kel_manager._k0, "sf"),
        ), patch(
            "plugins.fileannouncement.service._k0_from_seed",
            return_value=None,
        ), patch(
            "plugins.fileannouncement.service._key_pub_addr",
            return_value=("k0pub", "k0addr"),
        ), patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_onchain_hashlink_tip",
            AsyncMock(return_value=onchain),
        ), patch(
            "yadacoin.core.transaction.Transaction.from_dict",
            return_value=orphan,
        ), patch(
            "plugins.credentialissuer.service.partition_issue_kel",
            return_value=([], [orphan]),
        ):
            await _anchor_issue_kel(config)

        self.assertEqual(deleted, [{"id": "MEUCIQCO2pfp-orphan"}])

    async def test_issue_anchors_before_broadcast(self):
        from plugins.credentialissuer import service

        config = MagicMock()
        config.username_signature = "issuer-sig"
        config.inception.transaction_signature = "inc-id"
        order = []

        async def anchor(_config):
            order.append("anchor")

        async def generate(_config, _ann):
            order.append("generate")
            txn = MagicMock()
            txn.transaction_signature = "cred-sig"
            return txn

        async def broadcast(_config, _txn):
            order.append("broadcast")

        with patch.object(service, "_anchor_issue_kel", side_effect=anchor), patch(
            "plugins.fileannouncement.service._generate_txn", side_effect=generate
        ), patch(
            "plugins.fileannouncement.service._broadcast", side_effect=broadcast
        ), patch.object(
            service.store, "insert_issued", AsyncMock(return_value={"ok": True})
        ):
            await issue_credential(
                config,
                subject_username_signature="subject-sig",
                witness_hex="ab" * 32,
            )
        self.assertEqual(order, ["anchor", "generate", "broadcast"])


class _StoreCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def sort(self, *args, **kwargs):
        return self

    def skip(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def __aiter__(self):
        self._i = 0
        return self

    async def __anext__(self):
        if self._i >= len(self._rows):
            raise StopAsyncIteration
        row = self._rows[self._i]
        self._i += 1
        return row


class _StoreColl:
    def __init__(self, rows):
        self.rows = list(rows)

    def find(self, query=None, projection=None):
        query = query or {}
        if "id" in query and "$in" in query["id"]:
            wanted = set(query["id"]["$in"])
            return _StoreCursor([row for row in self.rows if row.get("id") in wanted])
        if "transactions.id" in query and "$in" in query["transactions.id"]:
            wanted = set(query["transactions.id"]["$in"])
            matched = []
            for block in self.rows:
                ids = {
                    txn.get("id")
                    for txn in block.get("transactions") or []
                    if txn.get("id")
                }
                if ids & wanted:
                    matched.append(block)
            return _StoreCursor(matched)
        return _StoreCursor(self.rows)


class TestListIssued(AsyncTestCase):
    async def test_hides_credentials_missing_from_mempool_and_chain(self):
        from plugins.credentialissuer.store import list_issued

        config = MagicMock()
        config.mongo.async_db = {
            "issued_credentials": _StoreColl(
                [
                    {"transaction_id": "live-mem", "username": "a", "created_at": 3},
                    {
                        "transaction_id": "live-chain",
                        "username": "b",
                        "created_at": 2,
                    },
                    {
                        "transaction_id": "failed-only",
                        "username": "c",
                        "created_at": 1,
                    },
                ]
            ),
            "miner_transactions": _StoreColl([{"id": "live-mem"}]),
            "blocks": _StoreColl([{"transactions": [{"id": "live-chain"}]}]),
        }
        rows = await list_issued(config)
        self.assertEqual(
            [row["transaction_id"] for row in rows], ["live-mem", "live-chain"]
        )
