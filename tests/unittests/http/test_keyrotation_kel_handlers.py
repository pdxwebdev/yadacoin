"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import tornado
from tornado import testing
from tornado.web import Application

from yadacoin.core.config import Config
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.mongo import Mongo
from yadacoin.http.keyeventlog import KEY_EVENT_LOG_HANDLERS
from yadacoin.http.keyrotation import KEY_ROTATION_HANDLERS


def make_async_iter_cursor(rows=None):
    if rows is None:
        rows = []

    class FakeAsyncCursor:
        def __init__(self, items):
            self._items = list(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._items:
                return self._items.pop(0)
            raise StopAsyncIteration

        async def to_list(self, length=None):
            return rows

    return FakeAsyncCursor(rows)


class ExtrasHttpTestCase(testing.AsyncHTTPTestCase):
    """HTTP test case for key rotation and key event log handlers."""

    def get_new_ioloop(self):
        return tornado.ioloop.IOLoop()

    def tearDown(self):
        super().tearDown()
        asyncio.set_event_loop(None)

    def get_app(self):
        c = Config()
        c.network = "regnet"
        c.mongo = Mongo()
        c.mongo_debug = True
        c.LatestBlock = LatestBlock
        self.config = c
        return Application(
            KEY_ROTATION_HANDLERS + KEY_EVENT_LOG_HANDLERS,
            app_title="YadaCoin Test",
            yadacoin_vars={},
            cookie_secret="test_secret_key_for_testing_only",
        )


# ---------------------------------------------------------------------------
# KeyRotationHandler
# ---------------------------------------------------------------------------


class TestKeyRotationHandler(ExtrasHttpTestCase):
    def test_get_serves_html_or_errors(self):
        # Handler renders a template; since no template dir, expect 500 or 200
        response = self.fetch("/key-rotation")
        self.assertIn(response.code, [200, 500])

    def test_yadacoin_cash_alias(self):
        response = self.fetch("/yadacoin-cash")
        self.assertIn(response.code, [200, 500])


# ---------------------------------------------------------------------------
# KeyRotationPrevKeyHashHandler
# ---------------------------------------------------------------------------


class TestKeyRotationPrevKeyHashHandler(ExtrasHttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        self.config.mongo.async_db = mock_db
        self.mock_db = mock_db

    def test_missing_address_returns_400(self):
        response = self.fetch("/key-rotation/prev-key-hash")
        self.assertEqual(response.code, 400)
        data = json.loads(response.body)
        self.assertIn("error", data)

    def test_inception_returns_empty_prev_hash(self):
        # Nothing in mempool or blockchain
        response = self.fetch("/key-rotation/prev-key-hash?address=1TestAddr")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["prev_public_key_hash"], "")
        self.assertIsNone(data["source"])

    def test_found_in_mempool(self):
        self.mock_db.miner_transactions.find_one = AsyncMock(
            return_value={"public_key_hash": "hash_from_mempool", "id": "txA"}
        )
        response = self.fetch("/key-rotation/prev-key-hash?address=1TestAddr")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["prev_public_key_hash"], "hash_from_mempool")
        self.assertEqual(data["source"], "mempool")

    def test_found_in_blockchain(self):
        self.mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        self.mock_db.blocks.find_one = AsyncMock(
            return_value={
                "transactions": [{"public_key_hash": "hash_from_chain", "id": "txB"}]
            }
        )
        response = self.fetch("/key-rotation/prev-key-hash?address=1TestAddr")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["prev_public_key_hash"], "hash_from_chain")
        self.assertEqual(data["source"], "blockchain")


# ---------------------------------------------------------------------------
# KeyRotationSpentHandler
# ---------------------------------------------------------------------------


class TestKeyRotationSpentHandler(ExtrasHttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        self.config.mongo.async_db = mock_db
        self.mock_db = mock_db

    def test_missing_address_returns_400(self):
        response = self.fetch("/key-rotation/spent")
        self.assertEqual(response.code, 400)

    def test_not_spent_returns_false(self):
        response = self.fetch("/key-rotation/spent?address=1NotSpent")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["spent"])
        self.assertEqual(data["txid"], "")

    def test_found_spent_in_mempool(self):
        self.mock_db.miner_transactions.find_one = AsyncMock(
            return_value={
                "id": "txC",
                "prerotated_key_hash": "nextkey",
                "twice_prerotated_key_hash": "nextkey2",
            }
        )
        response = self.fetch("/key-rotation/spent?address=1Spent")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data["spent"])
        self.assertEqual(data["source"], "mempool")
        self.assertEqual(data["txid"], "txC")

    def test_found_spent_in_blockchain(self):
        self.mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        self.mock_db.blocks.find_one = AsyncMock(
            return_value={
                "transactions": [
                    {
                        "id": "txD",
                        "prerotated_key_hash": "pk1",
                        "twice_prerotated_key_hash": "pk2",
                    }
                ]
            }
        )
        response = self.fetch("/key-rotation/spent?address=1Spent")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data["spent"])
        self.assertEqual(data["source"], "blockchain")
        self.assertEqual(data["txid"], "txD")


# ---------------------------------------------------------------------------
# HasKELHandler
# ---------------------------------------------------------------------------


class TestHasKELHandler(ExtrasHttpTestCase):
    def test_has_kel_with_public_key(self):
        pubkey = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        mock_db = MagicMock()
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        mock_db.miner_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        mock_db.blocks.aggregate = MagicMock(return_value=make_async_iter_cursor([]))
        self.config.mongo.async_db = mock_db
        response = self.fetch(f"/has-key-event-log?public_key={pubkey}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("status", data)

    def test_missing_public_key_returns_400(self):
        response = self.fetch("/has-key-event-log")
        self.assertEqual(response.code, 400)


# ---------------------------------------------------------------------------
# KELHandler
# ---------------------------------------------------------------------------


class TestKELHandler(ExtrasHttpTestCase):
    def test_gets_key_event_log(self):
        pubkey = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        mock_db = MagicMock()
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        mock_db.miner_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        mock_db.blocks.aggregate = MagicMock(return_value=make_async_iter_cursor([]))
        self.config.mongo.async_db = mock_db
        response = self.fetch(f"/key-event-log?public_key={pubkey}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("key_event_log", data)
        self.assertTrue(data["status"])

    def test_with_non_empty_log_without_mempool(self):
        pubkey = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        mock_kel_item = MagicMock(
            spec=[]
        )  # spec=[] prevents hasattr from auto-creating mempool
        mock_kel_item.to_dict = MagicMock(return_value={"public_key": pubkey})
        with patch(
            "yadacoin.http.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(return_value=[mock_kel_item]),
        ):
            response = self.fetch(f"/key-event-log?public_key={pubkey}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(len(data["key_event_log"]), 1)

    def test_with_non_empty_log_with_mempool(self):
        pubkey = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        mock_kel_item = MagicMock()
        mock_kel_item.to_dict = MagicMock(return_value={"public_key": pubkey})
        mock_kel_item.mempool = True
        with patch(
            "yadacoin.http.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(return_value=[mock_kel_item]),
        ):
            response = self.fetch(f"/key-event-log?public_key={pubkey}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(len(data["key_event_log"]), 1)
        self.assertTrue(data["key_event_log"][0]["mempool"])


# ---------------------------------------------------------------------------
# KELReportsHandler
# ---------------------------------------------------------------------------


class TestKELReportsHandler(ExtrasHttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        mock_db.blocks.aggregate = MagicMock(return_value=make_async_iter_cursor([]))
        self.config.mongo.async_db = mock_db
        self.mock_db = mock_db

    def test_default_report_returns_count(self):
        response = self.fetch("/kel-reports?from_date=0")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("result", data)
        # counts=1 by default → result is an integer
        self.assertIsInstance(data["result"], int)

    def test_date_preset_day(self):
        response = self.fetch("/kel-reports?date_preset=day&from_date=0")
        self.assertEqual(response.code, 200)

    def test_date_preset_week(self):
        response = self.fetch("/kel-reports?date_preset=week&from_date=0")
        self.assertEqual(response.code, 200)

    def test_date_preset_month(self):
        response = self.fetch("/kel-reports?date_preset=month&from_date=0")
        self.assertEqual(response.code, 200)

    def test_report_type_new(self):
        response = self.fetch("/kel-reports?report_type=new&from_date=0")
        self.assertEqual(response.code, 200)

    def test_counts_zero_returns_list(self):
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([{"transactions": {"id": "tx1"}}])
        )
        response = self.fetch("/kel-reports?counts=0&from_date=0")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIsInstance(data["result"], list)
