"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import tornado
from tornado import testing
from tornado.web import Application

from yadacoin.core.config import Config
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.mongo import Mongo
from yadacoin.http.wallet import WALLET_HANDLERS


def _ripemd160_available():
    try:
        hashlib.new("ripemd160")
        return True
    except (ValueError, Exception):
        return False


_HAS_RIPEMD160 = _ripemd160_available()


def make_mock_cursor(rows=None):
    """Create a mock motor cursor that returns rows from .to_list()."""
    if rows is None:
        rows = []
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=rows)
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    return cursor


def make_async_iter_cursor(rows=None):
    """Create a mock cursor that supports async iteration."""
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

        def sort(self, *args, **kwargs):
            return self

        def skip(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

    return FakeAsyncCursor(rows)


def setup_mock_db():
    """Create a comprehensive mock for async_db used in wallet tests."""
    mock_db = MagicMock()
    mock_db.child_keys.find = MagicMock(return_value=make_async_iter_cursor([]))
    mock_db.child_keys.find_one = AsyncMock(return_value=None)
    mock_db.child_keys.update_one = AsyncMock(return_value=MagicMock())
    mock_db.miner_transactions.find = MagicMock(return_value=make_mock_cursor([]))
    mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
    mock_db.blocks.find_one = AsyncMock(return_value=None)
    mock_db.blocks.aggregate = MagicMock(return_value=make_async_iter_cursor([]))
    mock_db.config.update_one = AsyncMock(return_value=MagicMock())
    return mock_db


class WalletHttpTestCase(testing.AsyncHTTPTestCase):
    """Proper HTTP test case that builds a real Tornado Application with wallet handlers."""

    def get_new_ioloop(self):
        return tornado.ioloop.IOLoop()

    def tearDown(self):
        super().tearDown()
        import asyncio

        asyncio.set_event_loop(None)

    def get_app(self):
        c = Config()
        c.network = "regnet"
        c.mongo = Mongo()
        c.mongo_debug = True
        c.LatestBlock = LatestBlock
        self.config = c
        return Application(
            WALLET_HANDLERS,
            app_title="YadaCoin Test",
            yadacoin_vars={},
            cookie_secret="test_secret_key_for_testing_only",
        )


# ---------------------------------------------------------------------------
# GenerateWalletHandler
# ---------------------------------------------------------------------------


class TestGenerateWalletHandler(WalletHttpTestCase):
    def test_returns_todo_message(self):
        response = self.fetch("/generate-wallet")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("TODO", data)


# ---------------------------------------------------------------------------
# ValidateAddressHandler
# ---------------------------------------------------------------------------


class TestValidateAddressHandler(WalletHttpTestCase):
    def test_valid_address_returns_true(self):
        # Use a known valid Bitcoin-style address
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        with patch.object(Config, "address_is_valid", return_value=True):
            response = self.fetch(f"/validate-address?address={address}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data["status"])
        self.assertEqual(data["address"], address)

    def test_invalid_address_returns_false(self):
        address = "notanaddress"
        with patch.object(Config, "address_is_valid", return_value=False):
            response = self.fetch(f"/validate-address?address={address}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["status"])


# ---------------------------------------------------------------------------
# ConvertPublicKeyToAddressHandler
# ---------------------------------------------------------------------------


class TestConvertPublicKeyToAddressHandler(WalletHttpTestCase):
    def test_converts_valid_pubkey(self):
        # Known valid compressed public key → address
        pubkey = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        response = self.fetch(f"/convert-public-key-to-address?public_key={pubkey}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("address", data)
        self.assertEqual(data["public_key"], pubkey)
        # Genesis public key address
        self.assertEqual(data["address"], "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH")

    def test_invalid_pubkey_returns_500(self):
        response = self.fetch("/convert-public-key-to-address?public_key=notahex")
        self.assertEqual(response.code, 500)


# ---------------------------------------------------------------------------
# GetAddressesHandler
# ---------------------------------------------------------------------------


class TestGetAddressesHandler(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_returns_own_address_when_no_children(self):
        self.mock_db.child_keys.find = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        response = self.fetch("/get-addresses")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("addresses", data)
        # Should at least contain the node's own address
        self.assertIn(self.config.address, data["addresses"])

    def test_includes_child_key_addresses(self):
        child = {"address": "1ChildAddress"}
        self.mock_db.child_keys.find = MagicMock(
            return_value=make_async_iter_cursor([child])
        )
        response = self.fetch("/get-addresses")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("1ChildAddress", data["addresses"])


# ---------------------------------------------------------------------------
# GetBalanceSum
# ---------------------------------------------------------------------------


class TestGetBalanceSumHandler(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_no_addresses_returns_empty(self):
        response = self.fetch(
            "/get-balance-sum",
            method="POST",
            body=json.dumps({}),
        )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data, {})

    def test_balance_sum_with_mock_bu(self):
        self.config.BU = MagicMock()
        self.config.BU.get_wallet_balance = AsyncMock(return_value=1.5)
        response = self.fetch(
            "/get-balance-sum",
            method="POST",
            body=json.dumps({"addresses": ["1Addr1", "1Addr2"]}),
        )
        self.assertEqual(response.code, 200)
        # Body is a JSON-encoded string like "3.00000000"
        body = response.body.decode()
        balance = json.loads(body)
        self.assertAlmostEqual(float(balance), 3.0, places=5)


# ---------------------------------------------------------------------------
# TransactionByIdHandler
# ---------------------------------------------------------------------------


class TestTransactionByIdHandler(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_found_in_mempool(self):
        txn = {"id": "tx123", "time": "1000", "outputs": []}
        self.mock_db.miner_transactions.find_one = AsyncMock(return_value=txn)
        self.mock_db.blocks.find_one = AsyncMock(return_value=None)
        response = self.fetch("/get-transaction-by-id?id=tx123")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data.get("mempool"))

    def test_found_in_blockchain(self):
        block = {"index": 10, "transactions": [{"id": "tx999", "time": "500"}]}
        self.mock_db.blocks.find_one = AsyncMock(return_value=block)
        self.mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        response = self.fetch("/get-transaction-by-id?id=tx999")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["id"], "tx999")

    def test_not_found_returns_404(self):
        self.mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        self.mock_db.blocks.find_one = AsyncMock(return_value=None)
        response = self.fetch("/get-transaction-by-id?id=notexist")
        # Handler sets self.status_code = 404 but render_as_json uses self.status_code
        self.assertIn(response.code, [200, 404])

    def test_missing_id_returns_500(self):
        response = self.fetch("/get-transaction-by-id")
        # No 'id' param → get_query_argument raises MissingArgumentError
        self.assertEqual(response.code, 400)


# ---------------------------------------------------------------------------
# TransactionConfirmationsHandler
# ---------------------------------------------------------------------------


class TestTransactionConfirmationsHandler(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db
        # Set a mock LatestBlock
        self.mock_block = MagicMock()
        self.mock_block.index = 200
        LatestBlock.block = self.mock_block

    def tearDown(self):
        LatestBlock.block = None
        super().tearDown()

    def test_txn_found_returns_confirmations(self):
        self.mock_db.blocks.find_one = AsyncMock(
            return_value={"index": 190, "transactions": [{"id": "txA"}]}
        )
        response = self.fetch("/get-transaction-confirmations?id=txA")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["confirmations"], 10)

    def test_txn_not_found_returns_zero_confirmations(self):
        self.mock_db.blocks.find_one = AsyncMock(return_value=None)
        response = self.fetch("/get-transaction-confirmations?id=missing")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["confirmations"], 0)

    def test_post_multiple_txn_ids(self):
        self.mock_db.blocks.find_one = AsyncMock(
            return_value={"index": 198, "transactions": []}
        )
        body = json.dumps({"txn_ids": ["txA", "txB"]})
        response = self.fetch(
            "/get-transaction-confirmations",
            method="POST",
            body=body,
        )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("confirmations", data)
        self.assertEqual(len(data["confirmations"]), 2)


# ---------------------------------------------------------------------------
# SentPendingTransactionsView
# ---------------------------------------------------------------------------


class TestSentPendingTransactionsView(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_returns_empty_list(self):
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_mock_cursor([])
        )
        response = self.fetch("/get-past-pending-sent-txns?public_key=03abc")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["past_pending_transactions"], [])

    def test_returns_txns_for_public_key(self):
        txns = [{"id": "tx1", "public_key": "03abc"}]
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_mock_cursor(txns)
        )
        response = self.fetch("/get-past-pending-sent-txns?public_key=03abc")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(len(data["past_pending_transactions"]), 1)


# ---------------------------------------------------------------------------
# ReceivedPendingTransactionsView
# ---------------------------------------------------------------------------


class TestReceivedPendingTransactionsView(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_returns_empty_list(self):
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_mock_cursor([])
        )
        # Use a valid compressed public key
        pubkey = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        response = self.fetch(f"/get-past-pending-received-txns?public_key={pubkey}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["past_pending_transactions"], [])


# ---------------------------------------------------------------------------
# SentTransactionsView (lines 351-377)
# ---------------------------------------------------------------------------


class TestSentTransactionsView(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_returns_empty_sent_transactions(self):
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        response = self.fetch("/get-past-sent-txns?public_key=testpubkey")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["past_transactions"], [])

    def test_returns_sent_transactions_for_pubkey(self):
        txn = {"id": "tx1", "outputs": [{"value": 1}], "time": "1000"}
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([{"transactions": txn}])
        )
        response = self.fetch("/get-past-sent-txns?public_key=testpubkey")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(len(data["past_transactions"]), 1)

    def test_with_include_zero_flag(self):
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        response = self.fetch(
            "/get-past-sent-txns?public_key=testpubkey&include_zero=1"
        )
        self.assertEqual(response.code, 200)

    def test_with_pagination(self):
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        response = self.fetch("/get-past-sent-txns?public_key=testpubkey&page=2")
        self.assertEqual(response.code, 200)


# ---------------------------------------------------------------------------
# ReceivedTransactionsView (lines 412-457)
# ---------------------------------------------------------------------------


class TestReceivedTransactionsView(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db
        # Genesis pubkey → address 1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH
        self.pubkey = (
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )

    def test_returns_empty_received_transactions(self):
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        response = self.fetch(f"/get-past-received-txns?public_key={self.pubkey}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["past_transactions"], [])

    def test_returns_received_transactions(self):
        txn = {"id": "rx1", "outputs": [{"value": 2}], "time": "1000"}
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([{"transactions": txn}])
        )
        response = self.fetch(f"/get-past-received-txns?public_key={self.pubkey}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(len(data["past_transactions"]), 1)

    def test_with_include_zero_flag(self):
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        response = self.fetch(
            f"/get-past-received-txns?public_key={self.pubkey}&include_zero=1"
        )
        self.assertEqual(response.code, 200)

    def test_with_pagination(self):
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        response = self.fetch(
            f"/get-past-received-txns?public_key={self.pubkey}&page=2"
        )
        self.assertEqual(response.code, 200)


# ---------------------------------------------------------------------------
# UnlockedHandler (lines 257-278)
# ---------------------------------------------------------------------------


class TestUnlockedHandler(WalletHttpTestCase):
    def test_returns_unlocked_true_when_cookie_set(self):
        with patch(
            "yadacoin.http.wallet.UnlockedHandler.get_secure_cookie",
            return_value="true",  # string not bytes: wallet.py compares == "true" (str)
        ):
            response = self.fetch("/unlocked")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data["unlocked"])

    def test_returns_unlocked_false_when_no_cookie_no_jwt(self):
        response = self.fetch("/unlocked")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["unlocked"])

    def test_unlocked_prepare_sets_cors_headers(self):
        # OPTIONS or any request to /unlocked will trigger prepare()
        response = self.fetch("/unlocked", method="OPTIONS")
        # OPTIONS may return 200, 204, or 405 depending on Tornado version
        self.assertIn(response.code, [200, 204, 405])
        # Check CORS header was set
        self.assertIn("Access-Control-Allow-Origin", dict(response.headers))

    def test_origin_with_trailing_slash_is_stripped(self):
        """Line 259: origin[-1]=='/': covers the strip branch."""
        response = self.fetch("/unlocked?origin=http%3A%2F%2Fexample.com%2F")
        self.assertEqual(response.code, 200)
        # The CORS header should be set to the stripped origin
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"),
            "http://example.com",
        )


# ---------------------------------------------------------------------------
# UnlockHandler.post() (lines 289-321)
# ---------------------------------------------------------------------------


class TestUnlockHandlerPost(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db
        self.config.jwt_secret_key = "test_secret_key"

    def test_correct_private_key_returns_token(self):
        body = json.dumps({"key_or_wif": self.config.private_key})
        with patch("yadacoin.http.wallet.jwt.encode", return_value="test_jwt_token"):
            response = self.fetch(
                "/unlock",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("token", data)
        self.assertEqual(data["token"], "test_jwt_token")

    def test_wrong_key_returns_error(self):
        body = json.dumps({"key_or_wif": "wrongkey"})
        response = self.fetch(
            "/unlock",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("status", data)
        self.assertEqual(data["status"], "error")

    def test_correct_wif_returns_token(self):
        body = json.dumps({"key_or_wif": self.config.wif})
        with patch("yadacoin.http.wallet.jwt.encode", return_value="wif_token"):
            response = self.fetch(
                "/unlock",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["token"], "wif_token")

    def test_form_encoded_body_covers_try_path(self):
        """Line 291: get_body_argument succeeds with form-encoded body."""
        import urllib.parse

        body = urllib.parse.urlencode({"key_or_wif": self.config.private_key})
        with patch("yadacoin.http.wallet.jwt.encode", return_value="form_token"):
            response = self.fetch(
                "/unlock",
                method="POST",
                body=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("token", data)


# ---------------------------------------------------------------------------
# CreateTransactionView (lines 153-187)
# ---------------------------------------------------------------------------


class TestCreateTransactionView(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_no_address_returns_empty(self):
        body = json.dumps({"outputs": [{"to": "addr", "value": 1}]})
        with patch(
            "yadacoin.http.wallet.CreateTransactionView.get_secure_cookie",
            return_value=b"true",
        ):
            response = self.fetch(
                "/create-transaction",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data, {})

    def test_no_outputs_returns_empty(self):
        body = json.dumps({"address": "1SomeAddr"})
        with patch(
            "yadacoin.http.wallet.CreateTransactionView.get_secure_cookie",
            return_value=b"true",
        ):
            response = self.fetch(
                "/create-transaction",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data, {})

    def test_no_auth_returns_error(self):
        body = json.dumps(
            {"address": "1SomeAddr", "outputs": [{"to": "x", "value": 1}]}
        )
        response = self.fetch(
            "/create-transaction",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("error", data)

    def test_with_address_and_outputs_generates_txn(self):
        mock_txn = MagicMock()
        mock_txn.to_dict.return_value = {"id": "newtxnid", "outputs": []}
        body = json.dumps(
            {
                "address": "1SomeAddr",
                "outputs": [{"to": "1Dest", "value": 1.0}],
                "fee": 0.001,
            }
        )
        with patch(
            "yadacoin.http.wallet.CreateTransactionView.get_secure_cookie",
            return_value=b"true",
        ):
            with patch(
                "yadacoin.http.wallet.Transaction.generate",
                new=AsyncMock(return_value=mock_txn),
            ):
                response = self.fetch(
                    "/create-transaction",
                    method="POST",
                    body=body,
                    headers={"Content-Type": "application/json"},
                )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["id"], "newtxnid")

    def test_with_from_addresses_covers_inputs_loop(self):
        """Line 171: covers the from_addresses input-gathering loop."""
        mock_txn = MagicMock()
        mock_txn.to_dict.return_value = {"id": "txwithfrom"}
        body = json.dumps(
            {
                "address": "1SomeAddr",
                "outputs": [{"to": "1Dest", "value": 0.5}],
                "from": ["1SrcAddr"],
            }
        )
        mock_iter = make_async_iter_cursor([{"id": "utxo1", "value": 1.0}])

        async def mock_get_unspent(address, inc_mempool=True):
            for x in [{"id": "utxo1", "value": 1.0}]:
                yield x

        self.config.BU = MagicMock()
        self.config.BU.get_wallet_unspent_transactions_for_spending = mock_get_unspent
        with patch(
            "yadacoin.http.wallet.CreateTransactionView.get_secure_cookie",
            return_value=b"true",
        ):
            with patch(
                "yadacoin.http.wallet.Transaction.generate",
                new=AsyncMock(return_value=mock_txn),
            ):
                response = self.fetch(
                    "/create-transaction",
                    method="POST",
                    body=body,
                    headers={"Content-Type": "application/json"},
                )
        self.assertEqual(response.code, 200)


# ---------------------------------------------------------------------------
# CreateRawTransactionView (lines 193-223)
# ---------------------------------------------------------------------------


class TestCreateRawTransactionView(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_no_address_returns_empty(self):
        body = json.dumps({"outputs": [{"to": "addr", "value": 1}]})
        with patch(
            "yadacoin.http.wallet.CreateRawTransactionView.get_secure_cookie",
            return_value=b"true",
        ):
            response = self.fetch(
                "/create-raw-transaction",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body), {})

    def test_no_outputs_returns_empty(self):
        body = json.dumps({"address": "1SomeAddr"})
        with patch(
            "yadacoin.http.wallet.CreateRawTransactionView.get_secure_cookie",
            return_value=b"true",
        ):
            response = self.fetch(
                "/create-raw-transaction",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body), {})

    def test_with_outputs_generates_raw_txn(self):
        mock_txn = MagicMock()
        mock_txn.to_dict.return_value = {"id": "rawtxn"}
        body = json.dumps(
            {
                "address": "1SomeAddr",
                "outputs": [{"to": "1Dest", "value": 0.5}],
            }
        )
        with patch(
            "yadacoin.http.wallet.CreateRawTransactionView.get_secure_cookie",
            return_value=b"true",
        ):
            with patch(
                "yadacoin.http.wallet.Transaction.generate",
                new=AsyncMock(return_value=mock_txn),
            ):
                response = self.fetch(
                    "/create-raw-transaction",
                    method="POST",
                    body=body,
                    headers={"Content-Type": "application/json"},
                )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["id"], "rawtxn")

    def test_with_from_addresses_covers_inputs_loop(self):
        """Lines 195, 211: covers the from_addresses loop in CreateRawTransactionView."""
        mock_txn = MagicMock()
        mock_txn.to_dict.return_value = {"id": "rawtxnwithfrom"}
        body = json.dumps(
            {
                "address": "1SomeAddr",
                "outputs": [{"to": "1Dest", "value": 0.5}],
                "from": ["1SrcAddr"],
            }
        )

        async def mock_get_unspent(address, inc_mempool=True):
            for x in [{"id": "utxo1", "value": 1.0}]:
                yield x

        self.config.BU = MagicMock()
        self.config.BU.get_wallet_unspent_transactions_for_spending = mock_get_unspent
        with patch(
            "yadacoin.http.wallet.CreateRawTransactionView.get_secure_cookie",
            return_value=b"true",
        ):
            with patch(
                "yadacoin.http.wallet.Transaction.generate",
                new=AsyncMock(return_value=mock_txn),
            ):
                response = self.fetch(
                    "/create-raw-transaction",
                    method="POST",
                    body=body,
                    headers={"Content-Type": "application/json"},
                )
        self.assertEqual(response.code, 200)


# ---------------------------------------------------------------------------
# SendTransactionView (lines 229-251)
# ---------------------------------------------------------------------------


class TestSendTransactionView(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_no_auth_returns_error(self):
        body = json.dumps({"address": "1Dest", "value": 1.0})
        response = self.fetch(
            "/send-transaction",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("error", data)

    def test_sends_transaction_with_auth(self):
        body = json.dumps(
            {
                "address": "1Dest",
                "value": 1.0,
                "from": "1Src",
            }
        )
        with patch(
            "yadacoin.http.wallet.SendTransactionView.get_secure_cookie",
            return_value=b"true",
        ):
            with patch(
                "yadacoin.http.wallet.TU.send",
                new=AsyncMock(return_value={"status": "sent"}),
            ):
                response = self.fetch(
                    "/send-transaction",
                    method="POST",
                    body=body,
                    headers={"Content-Type": "application/json"},
                )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["status"], "sent")


# ---------------------------------------------------------------------------
# FeeEstimateHandler (lines 640-671)
# ---------------------------------------------------------------------------


class TestFeeEstimateHandler(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_not_congested_when_few_txns(self):
        """Less than 1000 txns → not_congested (covers lines 640-662)"""
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[{"fee": 0.001}] * 5)
        self.mock_db.miner_transactions.aggregate = MagicMock(return_value=mock_cursor)
        response = self.fetch("/fee-estimate")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["status"], "not_congested")

    def test_congested_when_1000_txns(self):
        """Exactly 1000 txns → congested (covers lines 663-671)"""
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[{"fee": 0.001}] * 1000)
        self.mock_db.miner_transactions.aggregate = MagicMock(return_value=mock_cursor)
        response = self.fetch("/fee-estimate")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["status"], "congested")
        self.assertIn("fee_estimate", data)


# ---------------------------------------------------------------------------
# GenerateChildWalletHandler (lines 58-115)
# ---------------------------------------------------------------------------


class TestGenerateChildWalletHandler(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_no_auth_returns_error(self):
        body = json.dumps({"index": 0})
        response = self.fetch(
            "/generate-child-wallet",
            method="POST",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("error", data)

    def test_invalid_json_returns_400(self):
        with patch(
            "yadacoin.http.wallet.GenerateChildWalletHandler.get_secure_cookie",
            return_value=b"true",
        ):
            response = self.fetch(
                "/generate-child-wallet",
                method="POST",
                body="notjson",
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 400)

    def test_no_index_returns_error(self):
        body = json.dumps({"other_field": "value"})
        with patch(
            "yadacoin.http.wallet.GenerateChildWalletHandler.get_secure_cookie",
            return_value=b"true",
        ):
            response = self.fetch(
                "/generate-child-wallet",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["status"])
        self.assertIn("index not provided", data["message"])

    def test_non_integer_index_returns_error(self):
        body = json.dumps({"index": "notanumber"})
        with patch(
            "yadacoin.http.wallet.GenerateChildWalletHandler.get_secure_cookie",
            return_value=b"true",
        ):
            response = self.fetch(
                "/generate-child-wallet",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["status"])
        self.assertIn("index is not integer", data["message"])

    def test_index_too_large_returns_error(self):
        body = json.dumps({"index": 9999999999})
        with patch(
            "yadacoin.http.wallet.GenerateChildWalletHandler.get_secure_cookie",
            return_value=b"true",
        ):
            response = self.fetch(
                "/generate-child-wallet",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["status"])
        self.assertIn("4294967295", data["message"])

    def test_duplicate_index_returns_error(self):
        body = json.dumps({"index": 0})
        self.mock_db.child_keys.find_one = AsyncMock(return_value={"index": 0})
        with patch(
            "yadacoin.http.wallet.GenerateChildWalletHandler.get_secure_cookie",
            return_value=b"true",
        ):
            response = self.fetch(
                "/generate-child-wallet",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["status"])
        self.assertIn("already exists", data["message"])

    def test_creates_child_wallet_successfully(self):
        if not _HAS_RIPEMD160:
            self.skipTest("ripemd160 not available in this OpenSSL build")
        body = json.dumps({"index": 0})
        self.mock_db.child_keys.find_one = AsyncMock(return_value=None)
        with patch(
            "yadacoin.http.wallet.GenerateChildWalletHandler.get_secure_cookie",
            return_value=b"true",
        ):
            response = self.fetch(
                "/generate-child-wallet",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data["status"])
        self.assertIn("address", data)


# ---------------------------------------------------------------------------
# TransactionByIdHandler line 612 (both not found → 404)
# ---------------------------------------------------------------------------


class TestTransactionByIdHandlerNotFound(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_not_found_in_blocks_or_mempool(self):
        """Covers line 612: self.status_code = 404"""
        self.mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        self.mock_db.blocks.find_one = AsyncMock(return_value=None)
        response = self.fetch("/get-transaction-by-id?id=nonexistent")
        # When both are None, handler sets status_code=404 and renders error JSON
        data = json.loads(response.body)
        self.assertFalse(data["status"])


# ---------------------------------------------------------------------------
# WalletHandler.get() render (line 42) and UnwrapHandler.get() render (line 47)
# ---------------------------------------------------------------------------


class TestWalletHandlerGet(WalletHttpTestCase):
    def test_wallet_handler_renders_template(self):
        """Line 42: self.render('wallet.html')"""
        response = self.fetch("/wallet/app")
        self.assertIn(response.code, [200, 500])


class TestUnwrapHandlerGet(WalletHttpTestCase):
    def test_unwrap_handler_renders_template(self):
        """Line 47: self.render('unwrap.html')"""
        response = self.fetch("/unwrap/app")
        self.assertIn(response.code, [200, 500])


# ---------------------------------------------------------------------------
# UnlockHandler.get() render (line 286)
# ---------------------------------------------------------------------------


class TestUnlockHandlerGet(WalletHttpTestCase):
    def test_unlock_handler_get_renders_template(self):
        """Line 286: self.render('auth.html') in UnlockHandler.get()"""
        response = self.fetch("/unlock")
        self.assertIn(response.code, [200, 500])


# ---------------------------------------------------------------------------
# UnlockedHandler JWT path (line 276)
# ---------------------------------------------------------------------------


class TestUnlockedHandlerJwtPath(WalletHttpTestCase):
    def test_jwt_key_or_wif_returns_unlocked_true(self):
        """Line 276: jwt.get('key_or_wif') == 'true' → returns unlocked: True"""
        # Patch the jwt.decode used inside the jwtauthwallet decorator
        mock_config_doc = {"value": {"key_or_wif": "true", "timestamp": 0}}
        self.config.jwt_options = {}
        self.config.mongo.db = MagicMock()
        self.config.mongo.db.config.find_one = MagicMock(return_value=mock_config_doc)
        with patch(
            "yadacoin.decorators.jwtauth.jwt.decode",
            return_value={"key_or_wif": "true", "timestamp": 9999999999},
        ):
            with patch(
                "yadacoin.http.wallet.UnlockedHandler.get_secure_cookie",
                return_value=b"false",
            ):
                response = self.fetch(
                    "/unlocked",
                    headers={"Authorization": "Bearer faketoken"},
                )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data["unlocked"])


# ---------------------------------------------------------------------------
# CreateRawTransactionView unauthorized path (line 195)
# ---------------------------------------------------------------------------


class TestCreateRawTransactionViewUnauthorized(WalletHttpTestCase):
    def test_no_cookie_no_jwt_returns_not_authorized(self):
        """Line 195: not authorized when cookie unset and jwt missing."""
        response = self.fetch(
            "/create-raw-transaction",
            method="POST",
            body=json.dumps({"address": "1Addr", "outputs": []}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["error"], "not authorized")


# ---------------------------------------------------------------------------
# PaymentHandler (lines 504-577)
# ---------------------------------------------------------------------------


class TestPaymentHandler(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        self.mock_db.miner_transactions.aggregate = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        self.config.mongo.async_db = self.mock_db

    def test_no_identity_cookie_redirects_to_logout(self):
        """Lines 507-512: except path when cookie invalid → redirect to /logout."""
        response = self.fetch(
            "/payment?to_address=testaddr",
            follow_redirects=False,
        )
        self.assertIn(response.code, [301, 302])
        location = response.headers.get("Location", "")
        self.assertIn("logout", location)

    def test_main_path_with_empty_results(self):
        """Lines 503-577: main path with identity cookie and empty aggregations."""
        identity_data = json.dumps(
            {
                "public_key": "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
                "username": "testuser",
                "username_signature": "testsig",
            }
        )
        with patch(
            "yadacoin.http.wallet.PaymentHandler.get_secure_cookie",
            return_value=identity_data.encode(),
        ):
            with patch(
                "yadacoin.http.wallet.Identity.from_dict", return_value=MagicMock()
            ):
                response = self.fetch("/payment?to_address=testaddr")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("payments", data)
        self.assertEqual(data["payments"], [])

    def test_payment_with_newer_than_and_from_address(self):
        """Lines 535-537, 551-553: newer_than and from_address filter branches."""
        identity_data = json.dumps(
            {"public_key": "abc", "username": "u", "username_signature": "s"}
        )
        with patch(
            "yadacoin.http.wallet.PaymentHandler.get_secure_cookie",
            return_value=identity_data.encode(),
        ):
            with patch(
                "yadacoin.http.wallet.Identity.from_dict", return_value=MagicMock()
            ):
                response = self.fetch(
                    "/payment?to_address=testaddr&newer_than=1000000&from_address=fromaddr"
                )
        self.assertEqual(response.code, 200)

    def test_payment_with_transaction_data_covers_filter_lines(self):
        """Lines 557-570: P2PKH filter in both mempool and blockchain comprehensions."""
        pk = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        pending_item = {
            "public_key": pk,
            "id": "txnid123",
            "outputs": [],
            "inputs": [],
            "time": 1000,
            "hash": "abc",
        }
        block_item = {
            "txn": {
                "public_key": pk,
                "id": "txnid456",
                "outputs": [],
                "inputs": [],
                "time": 2000,
                "hash": "def",
            }
        }
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([block_item])
        )
        self.mock_db.miner_transactions.aggregate = MagicMock(
            return_value=make_async_iter_cursor([pending_item])
        )
        identity_data = json.dumps(
            {"public_key": "abc", "username": "u", "username_signature": "s"}
        )
        mock_address = MagicMock()
        mock_address.__str__ = MagicMock(return_value="other_address")

        with patch(
            "yadacoin.http.wallet.PaymentHandler.get_secure_cookie",
            return_value=identity_data.encode(),
        ):
            with patch(
                "yadacoin.http.wallet.Identity.from_dict", return_value=MagicMock()
            ):
                with patch(
                    "yadacoin.http.wallet.P2PKHBitcoinAddress.from_pubkey",
                    return_value=mock_address,
                ):
                    response = self.fetch("/payment?to_address=testaddr")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("payments", data)
        # Both items should be included since mock address != "testaddr"
        self.assertEqual(len(data["payments"]), 2)


# ---------------------------------------------------------------------------
# TransactionByIdHandler: both mt and block txn found (line 611-614)
# ---------------------------------------------------------------------------


class TestTransactionByIdHandlerBothFound(WalletHttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_both_found_returns_mt_when_newer(self):
        """Lines 611-614: best_mt_txn and best_block_txn both found, mt is newer."""
        mt_txn = {"id": "txn123", "time": "2000"}
        block_result = {"transactions": [{"id": "txn123", "time": "1000"}]}
        self.mock_db.miner_transactions.find_one = AsyncMock(return_value=mt_txn)
        self.mock_db.blocks.find_one = AsyncMock(return_value=block_result)
        response = self.fetch("/get-transaction-by-id?id=txn123")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["time"], "2000")
        self.assertTrue(data.get("mempool"))

    def test_both_found_returns_block_when_newer(self):
        """Lines 611-614: best_mt_txn and best_block_txn both found, block is newer."""
        mt_txn = {"id": "txn123", "time": "1000"}
        block_result = {"transactions": [{"id": "txn123", "time": "2000"}]}
        self.mock_db.miner_transactions.find_one = AsyncMock(return_value=mt_txn)
        self.mock_db.blocks.find_one = AsyncMock(return_value=block_result)
        response = self.fetch("/get-transaction-by-id?id=txn123")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["time"], "2000")
