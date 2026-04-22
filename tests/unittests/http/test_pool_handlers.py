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
from unittest.mock import AsyncMock, MagicMock

import tornado
from tornado import testing
from tornado.web import Application

from yadacoin.core.config import Config
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.mongo import Mongo
from yadacoin.http.pool import POOL_HANDLERS


def make_mock_cursor(rows=None):
    if rows is None:
        rows = []
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=rows)
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    return cursor


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


class PoolHttpTestCase(testing.AsyncHTTPTestCase):
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
            POOL_HANDLERS,
            app_title="YadaCoin Test",
            yadacoin_vars={},
            cookie_secret="test_secret_key_for_testing_only",
        )


# ---------------------------------------------------------------------------
# MinerStatsHandler
# ---------------------------------------------------------------------------


class TestMinerStatsHandler(PoolHttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        mock_db.shares.aggregate = MagicMock(return_value=make_async_iter_cursor([]))
        self.config.mongo.async_db = mock_db
        self.config.pool_diff = 100

    def test_no_address_returns_error(self):
        response = self.fetch("/miner-stats")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("error", data)

    def test_address_with_no_shares(self):
        response = self.fetch("/miner-stats?address=1TestAddress")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["miner_address"], "1TestAddress")
        self.assertEqual(data["total_hashrate"], 0)
        self.assertEqual(data["total_shares"], 0)
        self.assertEqual(data["workers"], [])

    def test_address_with_shares(self):
        shares_data = [
            {
                "_id": {"worker": "worker1"},
                "total_shares": 50,
                "total_weight": 100,
                "last_share_time": 1000.0,
            }
        ]
        self.config.mongo.async_db.shares.aggregate = MagicMock(
            return_value=make_async_iter_cursor(shares_data)
        )
        response = self.fetch("/miner-stats?address=1TestAddress")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(len(data["workers"]), 1)
        self.assertEqual(data["workers"][0]["worker_name"], "worker1")
        self.assertEqual(data["workers"][0]["worker_shares"], 50)


# ---------------------------------------------------------------------------
# MinerPayoutsHandler
# ---------------------------------------------------------------------------


class TestMinerPayoutsHandler(PoolHttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        mock_cursor = make_async_iter_cursor([])
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_db.share_payout.find = MagicMock(return_value=mock_cursor)
        self.config.mongo.async_db = mock_db
        self.mock_db = mock_db

    def test_no_address_returns_error(self):
        response = self.fetch("/miner-payouts")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("error", data)

    def test_address_with_no_payouts(self):
        response = self.fetch("/miner-payouts?address=1TestAddress")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["payouts"], [])

    def _setup_payout_db(self, payout_data, block=None, in_mempool=0, in_failed=0):
        mock_cursor = make_async_iter_cursor([payout_data])
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        self.mock_db.share_payout.find = MagicMock(return_value=mock_cursor)
        self.mock_db.blocks.find_one = AsyncMock(return_value=block)
        self.mock_db.miner_transactions.count_documents = AsyncMock(
            return_value=in_mempool
        )
        self.mock_db.failed_transactions.count_documents = AsyncMock(
            return_value=in_failed
        )
        source_cursor = make_async_iter_cursor([])
        source_cursor.sort = MagicMock(return_value=source_cursor)
        self.mock_db.blocks.find = MagicMock(return_value=source_cursor)

    def test_payout_confirmed_status(self):
        payout = {"txn": {"hash": "txhash1", "time": 1234, "outputs": [], "inputs": []}}
        self._setup_payout_db(payout, block={"index": 42})
        response = self.fetch("/miner-payouts?address=1TestAddress")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(len(data["payouts"]), 1)
        self.assertEqual(data["payouts"][0]["status"], "Confirmed")
        self.assertEqual(data["payouts"][0]["block_height"], 42)

    def test_payout_pending_status(self):
        payout = {"txn": {"hash": "txhash2", "time": 5678, "outputs": [], "inputs": []}}
        self._setup_payout_db(payout, block=None, in_mempool=1)
        response = self.fetch("/miner-payouts?address=1TestAddress")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["payouts"][0]["status"], "Pending")
        self.assertEqual(data["payouts"][0]["block_height"], "N/A")

    def test_payout_failed_status(self):
        payout = {"txn": {"hash": "txhash3", "time": 9999, "outputs": [], "inputs": []}}
        self._setup_payout_db(payout, block=None, in_mempool=0, in_failed=1)
        response = self.fetch("/miner-payouts?address=1TestAddress")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["payouts"][0]["status"], "Failed")

    def test_payout_unknown_status(self):
        payout = {"txn": {"hash": "txhash4", "time": 0, "outputs": [], "inputs": []}}
        self._setup_payout_db(payout, block=None, in_mempool=0, in_failed=0)
        response = self.fetch("/miner-payouts?address=1TestAddress")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["payouts"][0]["status"], "Unknown")

    def test_payout_with_matching_output(self):
        address = "1TestAddress"
        payout = {
            "txn": {
                "hash": "txhash5",
                "time": 1111,
                "outputs": [{"to": address, "value": 100}],
                "inputs": [],
            }
        }
        self._setup_payout_db(payout, block={"index": 50})
        response = self.fetch(f"/miner-payouts?address={address}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["payouts"][0]["amount"], 100)

    def test_payout_with_input_and_source_block_match(self):
        payout = {
            "txn": {
                "hash": "txhash6",
                "time": 2222,
                "outputs": [],
                "inputs": [{"id": "input_txid_1"}],
            }
        }
        self._setup_payout_db(payout, block={"index": 60})
        # Make source_blocks return a block where last_tx matches input_txid
        source_block = {
            "index": 55,
            "transactions": [
                {"id": "other_txid"},
                {"id": "input_txid_1"},
            ],
        }
        source_cursor = make_async_iter_cursor([source_block])
        self.mock_db.blocks.find = MagicMock(return_value=source_cursor)
        response = self.fetch("/miner-payouts?address=1TestAddress")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["payouts"][0]["for_block"], "55")


# ---------------------------------------------------------------------------
# PoolScanMissedPayoutsHandler
# ---------------------------------------------------------------------------


class TestPoolScanMissedPayoutsHandler(PoolHttpTestCase):
    def test_missing_start_index_returns_400(self):
        response = self.fetch("/scan-missed-payouts")
        self.assertEqual(response.code, 400)

    def test_with_pp_runs_payout(self):
        mock_pp = MagicMock()
        mock_pp.do_payout = AsyncMock()
        self.config.pp = mock_pp
        response = self.fetch("/scan-missed-payouts?start_index=100")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data["status"])


# ---------------------------------------------------------------------------
# CurrentMiningBlockHandler
# ---------------------------------------------------------------------------


class TestCurrentMiningBlockHandler(PoolHttpTestCase):
    def test_no_mp_returns_error(self):
        # config.mp is not set
        if hasattr(self.config, "mp"):
            del self.config.mp
        response = self.fetch("/current-mining-block")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("error", data)

    def test_mp_none_returns_error(self):
        self.config.mp = None
        response = self.fetch("/current-mining-block")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("error", data)

    def test_with_active_mp(self):
        mock_mp = MagicMock()
        mock_mp.block_to_mine_info = AsyncMock(
            return_value={"height": 100, "excluded": []}
        )
        self.config.mp = mock_mp
        response = self.fetch("/current-mining-block")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["height"], 100)
        self.assertEqual(data["excluded"], [])
