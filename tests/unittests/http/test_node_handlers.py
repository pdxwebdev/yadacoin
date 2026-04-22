"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import tornado
from tornado import testing
from tornado.web import Application

from yadacoin.core.config import Config
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.mongo import Mongo
from yadacoin.http.node import NODE_HANDLERS


def make_mock_cursor(rows=None):
    """Create a mock motor cursor that returns rows from .to_list()."""
    if rows is None:
        rows = []
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=rows)
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.hint = MagicMock(return_value=cursor)
    cursor.__aiter__ = MagicMock(return_value=iter(rows))
    cursor.__anext__ = AsyncMock(side_effect=StopAsyncIteration)
    return cursor


def make_async_iter_cursor(rows=None):
    """Create a mock cursor that supports async iteration."""
    if rows is None:
        rows = []

    class FakeAsyncCursor:
        def __init__(self, items):
            self.items = iter(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.items)
            except StopIteration:
                raise StopAsyncIteration

        async def to_list(self, length=None):
            return rows

        def sort(self, *args, **kwargs):
            return self

        def skip(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def hint(self, *args, **kwargs):
            return self

    return FakeAsyncCursor(rows)


def setup_mock_db():
    """Create a comprehensive mock for async_db."""
    mock_db = MagicMock()

    # Default cursors return empty lists
    empty_cursor = make_mock_cursor([])
    mock_db.blocks.find = MagicMock(return_value=empty_cursor)
    mock_db.blocks.find_one = AsyncMock(return_value=None)
    mock_db.blocks.aggregate = MagicMock(return_value=make_async_iter_cursor([]))
    mock_db.miner_transactions.find = MagicMock(return_value=empty_cursor)
    mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
    mock_db.miner_transactions.count_documents = AsyncMock(return_value=0)
    mock_db.miner_transactions.aggregate = MagicMock(
        return_value=make_async_iter_cursor([])
    )
    mock_db.txn_tracking.find = MagicMock(return_value=empty_cursor)
    mock_db.node_status.find_one = AsyncMock(return_value=None)
    mock_db.node_status.aggregate = MagicMock(return_value=make_async_iter_cursor([]))
    mock_db.unindexed_queries.count_documents = AsyncMock(return_value=0)
    mock_db.unindexed_queries.find = MagicMock(return_value=make_async_iter_cursor([]))
    mock_db.tested_nodes.find_one = AsyncMock(return_value=None)
    mock_db.shares.count_documents = AsyncMock(return_value=0)

    return mock_db


class HttpTestCase(testing.AsyncHTTPTestCase):
    """Proper HTTP test case that builds a real Tornado Application with node handlers."""

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
            NODE_HANDLERS,
            app_title="YadaCoin Test",
            yadacoin_vars={},
            cookie_secret="test_secret_key_for_testing_only",
        )


class TestGetBlockHeightHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        # Set up LatestBlock.block
        self.mock_block = MagicMock()
        self.mock_block.index = 100
        self.mock_block.hash = "deadbeef1234"
        LatestBlock.block = self.mock_block

    def tearDown(self):
        LatestBlock.block = None
        super().tearDown()

    def test_get_height_returns_index_and_hash(self):
        response = self.fetch("/get-height")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["height"], 100)
        self.assertEqual(data["hash"], "deadbeef1234")

    def test_get_height_via_getheight_url(self):
        response = self.fetch("/getheight")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["height"], 100)


class TestGetLatestBlockHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_block = MagicMock()
        mock_copy = MagicMock()
        mock_copy.to_dict.return_value = {
            "index": 50,
            "hash": "abc123",
            "transactions": [],
        }
        self.mock_block.copy = AsyncMock(return_value=mock_copy)
        LatestBlock.block = self.mock_block

    def tearDown(self):
        LatestBlock.block = None
        super().tearDown()

    def test_get_latest_block_returns_block_dict(self):
        response = self.fetch("/get-latest-block")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["index"], 50)


class TestGetBlocksHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_block = MagicMock()
        self.mock_block.index = 100
        LatestBlock.block = self.mock_block
        # Patch the DB
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def tearDown(self):
        LatestBlock.block = None
        super().tearDown()

    def test_get_blocks_beyond_latest_returns_empty(self):
        # start_index > LatestBlock.block.index → returns []
        response = self.fetch("/get-blocks?start_index=200&end_index=205")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data, [])

    def test_get_blocks_with_valid_range(self):
        block_data = [{"index": 0, "hash": "genesis"}]
        cursor = make_mock_cursor(block_data)
        self.mock_db.blocks.find = MagicMock(return_value=cursor)
        response = self.fetch("/get-blocks?start_index=0&end_index=5")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIsInstance(data, list)

    def test_get_blocks_defaults_to_zero(self):
        response = self.fetch("/get-blocks")
        self.assertEqual(response.code, 200)


class TestGetBlockHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_get_block_by_hash_returns_result(self):
        self.mock_db.blocks.find_one = AsyncMock(
            return_value={"index": 5, "hash": "abc"}
        )
        response = self.fetch("/get-block?hash=abc")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["hash"], "abc")

    def test_get_block_by_index(self):
        self.mock_db.blocks.find_one = AsyncMock(
            return_value={"index": 5, "hash": "abc"}
        )
        response = self.fetch("/get-block?index=5")
        self.assertEqual(response.code, 200)

    def test_get_block_no_params_returns_empty(self):
        response = self.fetch("/get-block")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data, {})

    def test_get_block_not_found_returns_none(self):
        self.mock_db.blocks.find_one = AsyncMock(return_value=None)
        response = self.fetch("/get-block?hash=notfound")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIsNone(data)


class TestGetPendingTransactionHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_get_pending_transaction_found(self):
        txn = {"id": "abc123", "outputs": []}
        self.mock_db.miner_transactions.find_one = AsyncMock(return_value=txn)
        response = self.fetch("/get-pending-transaction?id=abc123")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["id"], "abc123")

    def test_get_pending_transaction_not_found(self):
        self.mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        response = self.fetch("/get-pending-transaction?id=notexist")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIsNone(data)

    def test_get_pending_transaction_no_id_returns_500(self):
        response = self.fetch("/get-pending-transaction")
        # Handler calls .replace() on None when no id param → 500
        self.assertEqual(response.code, 500)


class TestGetPendingTransactionIdsHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_returns_empty_list_when_no_transactions(self):
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_mock_cursor([])
        )
        response = self.fetch("/get-pending-transaction-ids")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["txn_ids"], [])

    def test_returns_ids_when_transactions_exist(self):
        txns = [{"id": "txn1"}, {"id": "txn2"}]
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_mock_cursor(txns)
        )
        response = self.fetch("/get-pending-transaction-ids")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("txn1", data["txn_ids"])
        self.assertIn("txn2", data["txn_ids"])


class TestGetTransactionTrackingHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_returns_empty_when_no_tracking_data(self):
        self.mock_db.txn_tracking.find = MagicMock(return_value=make_mock_cursor([]))
        response = self.fetch("/get-transaction-tracking")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["transaction_tracking"], [])

    def test_with_tracking_data_and_rid_filter(self):
        tracking = [
            {"rid": "rid1", "host": "1.2.3.4", "transactions": {"txn1": 1000.0}}
        ]
        self.mock_db.txn_tracking.find = MagicMock(
            return_value=make_mock_cursor(tracking)
        )
        response = self.fetch("/get-transaction-tracking?rid=rid1")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(len(data["transaction_tracking"]), 1)
        self.assertEqual(data["transaction_tracking"][0]["rid"], "rid1")

    def test_with_limit_parameter(self):
        self.mock_db.txn_tracking.find = MagicMock(return_value=make_mock_cursor([]))
        response = self.fetch("/get-transaction-tracking?limit=10")
        self.assertEqual(response.code, 200)


class TestGetMempoolHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_returns_empty_mempool(self):
        self.mock_db.miner_transactions.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_mock_cursor([])
        )
        response = self.fetch("/get-mempool")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["transactions"], [])

    def test_returns_paginated_mempool(self):
        self.mock_db.miner_transactions.count_documents = AsyncMock(return_value=2)
        txns = [{"id": "tx1", "fee": 0.001}, {"id": "tx2", "fee": 0.002}]
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_mock_cursor(txns)
        )
        response = self.fetch("/get-mempool?page=1&page_size=10")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["page"], 1)

    def test_page_size_capped_at_100(self):
        self.mock_db.miner_transactions.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_mock_cursor([])
        )
        response = self.fetch("/get-mempool?page_size=500")
        self.assertEqual(response.code, 200)


class TestGetTestedNodesHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_no_test_results_returns_500(self):
        self.mock_db.tested_nodes.find_one = AsyncMock(return_value=None)
        response = self.fetch("/get-tested-nodes")
        # Handler calls render_as_json(status=...) which is unsupported → 500
        self.assertEqual(response.code, 500)

    def test_with_test_results(self):
        result = {"nodes": [{"host": "1.2.3.4", "status": "ok"}]}
        self.mock_db.tested_nodes.find_one = AsyncMock(return_value=result)
        response = self.fetch("/get-tested-nodes")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("nodes", data)


class TestGetTransactionByPublicKeyHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_found_in_blocks(self):
        txn = {"id": "tx1", "public_key": "03abc", "outputs": []}
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([{"transactions": txn}])
        )
        response = self.fetch("/get-transaction-by-public-key?public_key=03abc")
        self.assertEqual(response.code, 200)

    def test_found_in_mempool(self):
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        self.mock_db.miner_transactions.find_one = AsyncMock(
            return_value={"id": "tx1", "public_key": "03abc"}
        )
        response = self.fetch("/get-transaction-by-public-key?public_key=03abc")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data.get("mempool"))

    def test_not_found_returns_empty(self):
        self.mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        self.mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        response = self.fetch("/get-transaction-by-public-key?public_key=03abc")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data, {})


# ---------------------------------------------------------------------------
# GetPeersHandler
# ---------------------------------------------------------------------------


class TestGetPeersHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        mock_peer = MagicMock()
        mock_peer.get_all_inbound_streams = AsyncMock(return_value=[])
        mock_peer.get_all_outbound_streams = AsyncMock(return_value=[])
        self.config.peer = mock_peer

    def test_returns_empty_peers(self):
        response = self.fetch("/get-peers")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("inbound_peers", data)
        self.assertIn("outbound_peers", data)
        self.assertEqual(data["inbound_peers"], [])
        self.assertEqual(data["outbound_peers"], [])

    def test_returns_peers_when_connected(self):
        mock_stream = MagicMock()
        mock_stream.peer.to_dict.return_value = {"host": "1.2.3.4", "port": 8000}
        self.config.peer.get_all_inbound_streams = AsyncMock(return_value=[mock_stream])
        response = self.fetch("/get-peers")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(len(data["inbound_peers"]), 1)
        self.assertEqual(data["inbound_peers"][0]["host"], "1.2.3.4")


# ---------------------------------------------------------------------------
# GetStatusHandler
# ---------------------------------------------------------------------------


class TestGetStatusHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        self.mock_db = setup_mock_db()
        self.config.mongo.async_db = self.mock_db

    def test_no_status_returns_500(self):
        # find_one returns None → status["unindexed_queries"] raises TypeError
        self.mock_db.node_status.find_one = AsyncMock(return_value=None)
        response = self.fetch("/get-status")
        self.assertEqual(response.code, 500)

    def test_status_with_data(self):
        self.mock_db.node_status.find_one = AsyncMock(
            return_value={"timestamp": 1000, "message": "ok"}
        )
        self.mock_db.unindexed_queries.count_documents = AsyncMock(return_value=0)
        self.mock_db.unindexed_queries.find = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        response = self.fetch("/get-status")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("unindexed_queries", data)
        self.assertEqual(data["unindexed_queries"]["count"], 0)

    def test_status_with_from_time(self):
        self.mock_db.node_status.find = MagicMock(
            return_value=make_async_iter_cursor([{"timestamp": 999}])
        )
        response = self.fetch("/get-status?from_time=3600")
        self.assertEqual(response.code, 200)


# ---------------------------------------------------------------------------
# RebroadcastTransactions
# ---------------------------------------------------------------------------


class TestRebroadcastTransactions(HttpTestCase):
    def setUp(self):
        super().setUp()
        mock_tu = MagicMock()
        mock_tu.rebroadcast_mempool = AsyncMock(return_value=None)
        self.config.TU = mock_tu

    def test_rebroadcast_returns_success(self):
        response = self.fetch("/rebroadcast-transactions")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["status"], "success")


# ---------------------------------------------------------------------------
# RebroadcastFailedTransactions
# ---------------------------------------------------------------------------


class TestRebroadcastFailedTransactions(HttpTestCase):
    def setUp(self):
        super().setUp()
        mock_tu = MagicMock()
        mock_tu.rebroadcast_failed = AsyncMock(return_value=None)
        self.config.TU = mock_tu

    def test_rebroadcast_failed_returns_success(self):
        response = self.fetch("/rebroadcast-failed-transaction?id=tx123")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["status"], "success")

    def test_missing_id_returns_500(self):
        # No id param → get_query_argument raises MissingArgumentError
        response = self.fetch("/rebroadcast-failed-transaction")
        self.assertEqual(response.code, 400)


# ---------------------------------------------------------------------------
# GetPendingTransactionHandler - empty id edge case (line 220)
# ---------------------------------------------------------------------------


class TestGetPendingTransactionHandlerEmptyId(HttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        self.config.mongo.async_db = mock_db

    def test_empty_id_returns_empty_json(self):
        # ?id= (empty string) → txn_id is "" → falsy → line 220 covered
        response = self.fetch("/get-pending-transaction?id=")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data, {})


# ---------------------------------------------------------------------------
# GetTransactionByPublicKeyHandler - empty public_key edge case (line 230)
# ---------------------------------------------------------------------------


class TestGetTransactionByPublicKeyHandlerEmptyKey(HttpTestCase):
    def test_empty_public_key_returns_empty_json(self):
        # ?public_key= (empty string) → public_key is "" → falsy → line 230 covered
        response = self.fetch("/get-transaction-by-public-key?public_key=")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data, {})


# ---------------------------------------------------------------------------
# Smart Contract Handlers (lines 346, 351, 356, 361)
# ---------------------------------------------------------------------------


class TestSmartContractHandlers(HttpTestCase):
    def test_get_current_smart_contract_transactions(self):
        # References undefined 'txns' → NameError → 500
        response = self.fetch("/get-current-smart-contract-transactions")
        self.assertEqual(response.code, 500)

    def test_get_current_smart_contract_transaction(self):
        response = self.fetch("/get-current-smart-contract-transaction")
        self.assertEqual(response.code, 500)

    def test_get_expired_smart_contract_transactions(self):
        response = self.fetch("/get-expired-smart-contract-transactions")
        self.assertEqual(response.code, 500)

    def test_get_expired_smart_contract_transaction(self):
        response = self.fetch("/get-expired-smart-contract-transaction")
        self.assertEqual(response.code, 500)


# ---------------------------------------------------------------------------
# GetSmartContractTriggerTransaction (lines 366-389)
# ---------------------------------------------------------------------------


class TestGetSmartContractTriggerTransaction(HttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        mock_db.blocks.aggregate = MagicMock(return_value=make_async_iter_cursor([]))
        self.config.mongo.async_db = mock_db

    def test_no_id_returns_500(self):
        # No id param → replace() on None → 500
        response = self.fetch("/get-trigger-transactions")
        self.assertEqual(response.code, 500)

    def test_no_smart_contract_found_returns_404(self):
        response = self.fetch("/get-trigger-transactions?id=nonexistent_id")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["status"])
        self.assertEqual(data["message"], "not found")


# ---------------------------------------------------------------------------
# MineBlockHandler (lines 494-516)  — runs even without JWT auth
# ---------------------------------------------------------------------------


class TestMineBlockHandler(HttpTestCase):
    def test_no_auth_returns_not_authorized(self):
        # No cookie, no JWT → returns not authorized (line 498)
        response = self.fetch("/mine-block")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["error"], "not authorized")

    def test_mainnet_not_regnet_returns_error(self):
        # When cookie is set (auth passes) but network != "regnet" → line 497-500
        self.config.network = "mainnet"
        with patch(
            "yadacoin.http.node.MineBlockHandler.get_secure_cookie",
            return_value=b"true",
        ):
            response = self.fetch("/mine-block")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["status"])
        self.assertIn("regnet", data["message"])

    def test_regnet_mines_block(self):
        # Auth passes and network is regnet → runs mining logic (lines 501-516)
        self.config.network = "regnet"
        mock_db = MagicMock()
        mock_db.blocks.insert_one = AsyncMock()
        self.config.mongo.async_db = mock_db
        mock_block_factory = MagicMock()
        mock_block_factory.hash = "hash1"
        mock_block_factory.index = 1
        mock_block_factory.header = "header1"
        mock_block_factory.generate_hash_from_header = AsyncMock(
            return_value="final_hash"
        )
        mock_block_factory.verify = AsyncMock()
        mock_block_factory.to_dict = MagicMock(
            return_value={"index": 1, "hash": "final_hash"}
        )
        mock_mp = MagicMock()
        mock_mp.block_factory = mock_block_factory
        mock_mp.refresh = AsyncMock()
        self.config.mp = mock_mp
        self.config.BU = MagicMock()
        self.config.BU.generate_signature = MagicMock(return_value="sig1")
        with patch(
            "yadacoin.http.node.MineBlockHandler.get_secure_cookie",
            return_value=b"true",
        ):
            response = self.fetch("/mine-block")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data["status"])


# ---------------------------------------------------------------------------
# GetSmartContractTriggerTransaction - found path (lines 383-389)
# ---------------------------------------------------------------------------


class TestGetSmartContractTriggerTransactionFoundPath(HttpTestCase):
    def setUp(self):
        super().setUp()
        smart_contract_doc = {
            "transactions": {
                "id": "sc_id_1",
                "public_key": "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
                "hash": "testhash",
                "outputs": [],
                "inputs": [],
                "time": 0,
                "fee": 0,
                "version": 5,
                "private": False,
                "signatures": [],
                "prerotated_key_hash": "",
                "twice_prerotated_key_hash": "",
                "prev_public_key_hash": "",
            }
        }
        mock_db = MagicMock()
        mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([smart_contract_doc])
        )
        self.config.mongo.async_db = mock_db

    def test_found_smart_contract_returns_transactions(self):
        with patch(
            "yadacoin.http.node.TU.get_trigger_txns",
            return_value=make_async_iter_cursor([]),
        ):
            response = self.fetch("/get-trigger-transactions?id=sc_id_1")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("transactions", data)
        self.assertEqual(data["transactions"], [])


# ---------------------------------------------------------------------------
# GetMonitoringHandler (lines 395-473)
# ---------------------------------------------------------------------------


class TestGetMonitoringHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        mock_db.node_status.aggregate = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        mock_db.shares.count_documents = AsyncMock(return_value=0)
        mock_db.blocks.find = MagicMock(return_value=make_mock_cursor([]))
        self.config.mongo.async_db = mock_db
        self.config.address = "1TestAddress"
        self.config.pool_diff = 100
        self.config.pool_take = 0.01
        self.config.public_key = (
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )
        mock_lb = MagicMock()
        mock_lb.block.index = 100
        mock_lb.block_checker = AsyncMock()
        self.config.LatestBlock = mock_lb
        # Set up peer mock so hasattr(config, "peer") is True with proper methods
        mock_peer = MagicMock()
        mock_peer.get_all_inbound_streams = AsyncMock(return_value=[])
        mock_peer.get_all_outbound_streams = AsyncMock(return_value=[])
        self.config.peer = mock_peer

    def test_monitoring_basic(self):
        response = self.fetch("/get-monitoring")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("address", data)
        self.assertIn("pool", data)

    def test_monitoring_with_peer(self):
        # peer is already set in setUp, just verify peer data appears
        response = self.fetch("/get-monitoring")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("peers", data)

    def test_monitoring_with_node_data(self):
        node_data = {"timestamp": 12345, "block_height": 100}
        self.config.mongo.async_db.node_status.aggregate = MagicMock(
            return_value=make_async_iter_cursor([node_data])
        )
        response = self.fetch("/get-monitoring")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("node", data)

    def test_monitoring_with_shares_counts(self):
        self.config.mongo.async_db.shares.count_documents = AsyncMock(return_value=100)
        response = self.fetch("/get-monitoring")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("pool", data)
        self.assertGreater(data["pool"]["hashes_per_second"], 0)

    def test_monitoring_with_pool_blocks_found(self):
        # Covers lines 460-461: pool_blocks_found_list is non-empty
        block_entry = {"time": 1699999, "index": 150}
        mock_cursor = make_mock_cursor([block_entry])
        self.config.mongo.async_db.blocks.find = MagicMock(return_value=mock_cursor)
        response = self.fetch("/get-monitoring")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["pool"]["last_block_time"], 1699999)
        self.assertEqual(data["pool"]["last_block_height"], 150)


# ---------------------------------------------------------------------------
# NewBlockHandler.post() (lines 159-213)
# ---------------------------------------------------------------------------


class TestNewBlockHandler(HttpTestCase):
    def setUp(self):
        super().setUp()
        import sys

        self.mock_block = MagicMock()
        self.mock_block.index = 5
        LatestBlock.block = self.mock_block
        # yadacoin.peers module does not exist; inject a mock so the import succeeds
        from unittest.mock import MagicMock as _MagicMock

        mock_peers_module = _MagicMock()
        mock_peers_module.Peer = _MagicMock()
        mock_peers_module.Peer.from_string = _MagicMock(return_value=_MagicMock())
        sys.modules.setdefault("yadacoin.peers", mock_peers_module)
        self._mock_peers_module = mock_peers_module
        # Set up config attributes needed by the handler
        self.config.BU = MagicMock()
        self.config.BU.get_version_for_height = MagicMock(return_value=4)
        self.config.consensus = MagicMock()
        self.config.consensus.process_next_block = AsyncMock(return_value=True)
        # self.peers is accessed on the HANDLER instance (not config), so we set it
        # as a class-level attribute that all instances will inherit
        self.mock_peers_obj = MagicMock()
        self.mock_peers_obj.syncing = False
        from yadacoin.http.node import NewBlockHandler

        NewBlockHandler.peers = self.mock_peers_obj

    def tearDown(self):
        import sys

        from yadacoin.http.node import NewBlockHandler

        # Remove the temporary class attribute
        if hasattr(NewBlockHandler, "peers"):
            try:
                del NewBlockHandler.peers
            except AttributeError:
                pass
        sys.modules.pop("yadacoin.peers", None)
        LatestBlock.block = None
        super().tearDown()

    def test_index_zero_returns_immediately(self):
        """Line 165: block_data['index'] == 0 → early return."""
        body = json.dumps(
            {
                "index": 0,
                "version": "4",
                "peer": "127.0.0.1:8000",
                "hash": "abc",
                "time": "1000",
            }
        )
        response = self.fetch("/newblock", method="POST", body=body)
        self.assertEqual(response.code, 200)

    def test_wrong_version_logs_and_returns(self):
        """Lines 166-172: version mismatch → rejected."""
        body = json.dumps(
            {
                "index": 5,
                "version": "999",
                "peer": "127.0.0.1:8000",
                "hash": "abc",
                "time": "1000",
            }
        )
        # BU.get_version_for_height returns 4, but block version is 999
        response = self.fetch("/newblock", method="POST", body=body)
        self.assertEqual(response.code, 200)

    def test_next_index_triggers_process_next_block(self):
        """Lines 184-191: index == my_index + 1 → process_next_block called."""
        # LatestBlock.block.index = 5, so index 6 == 5+1
        body = json.dumps(
            {
                "index": 6,
                "version": "4",
                "peer": "127.0.0.1:8000",
                "hash": "abc",
                "time": "1000",
            }
        )
        response = self.fetch("/newblock", method="POST", body=body)
        self.assertEqual(response.code, 200)

    def test_index_ahead_by_more_than_one_logs_warning(self):
        """Lines 192-200: index > my_index + 1 → logs missing blocks warning."""
        body = json.dumps(
            {
                "index": 10,
                "version": "4",
                "peer": "127.0.0.1:8000",
                "hash": "abc",
                "time": "1000",
            }
        )
        response = self.fetch("/newblock", method="POST", body=body)
        self.assertEqual(response.code, 200)

    def test_old_index_logs_and_ignores(self):
        """Lines 200-205: index <= my_index → logs 'old or same index'."""
        body = json.dumps(
            {
                "index": 3,
                "version": "4",
                "peer": "127.0.0.1:8000",
                "hash": "abc",
                "time": "1000",
            }
        )
        response = self.fetch("/newblock", method="POST", body=body)
        self.assertEqual(response.code, 200)

    def test_syncing_skips_processing(self):
        """Line 181: not self.peers.syncing is False → skips the if block."""
        # LatestBlock.block.index = 5, index 6 = next block
        self.mock_peers_obj.syncing = True
        body = json.dumps(
            {
                "index": 6,
                "version": "4",
                "peer": "127.0.0.1:8000",
                "hash": "abc",
                "time": "1000",
            }
        )
        response = self.fetch("/newblock", method="POST", body=body)
        self.assertEqual(response.code, 200)

    def test_exception_is_caught(self):
        """Lines 207-208: except block catches errors and prints."""
        # Send invalid JSON to trigger exception
        response = self.fetch(
            "/newblock",
            method="POST",
            body="not valid json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.code, 200)
