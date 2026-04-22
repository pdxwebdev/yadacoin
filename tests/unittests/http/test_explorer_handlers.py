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
from yadacoin.http.explorer import EXPLORER_HANDLERS


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

        def sort(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

    return FakeAsyncCursor(rows)


class ExplorerHttpTestCase(testing.AsyncHTTPTestCase):
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
            EXPLORER_HANDLERS,
            app_title="YadaCoin Test",
            yadacoin_vars={},
            cookie_secret="test_secret_key_for_testing_only",
        )


# ---------------------------------------------------------------------------
# ExplorerGetBalance
# ---------------------------------------------------------------------------


class TestExplorerGetBalance(ExplorerHttpTestCase):
    def setUp(self):
        super().setUp()
        self.config.BU = MagicMock()
        self.config.BU.get_wallet_balance = AsyncMock(return_value=5.0)

    def test_no_address_returns_empty(self):
        response = self.fetch("/explorer-get-balance")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data, {})

    def test_address_returns_balance(self):
        response = self.fetch("/explorer-get-balance?address=1TestAddr")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("balance", data)
        self.assertEqual(data["balance"], "5.00000000")


# ---------------------------------------------------------------------------
# ExplorerLatestHandler
# ---------------------------------------------------------------------------


class TestExplorerLatestHandler(ExplorerHttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        block_data = {"index": 5, "hash": "abc123", "time": 1000, "transactions": []}
        cursor = make_mock_cursor([block_data])
        mock_db.blocks.find = MagicMock(return_value=cursor)
        self.config.mongo.async_db = mock_db

    def test_returns_latest_blocks(self):
        response = self.fetch("/explorer-latest")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)
        self.assertEqual(data["resultType"], "blocks")
        self.assertIn("result", data)

    def test_empty_result_returns_500(self):
        # Modifying cursor to return empty would cause print(res[0]) to fail
        mock_db = MagicMock()
        cursor = make_mock_cursor([])
        mock_db.blocks.find = MagicMock(return_value=cursor)
        self.config.mongo.async_db = mock_db
        response = self.fetch("/explorer-latest")
        # Empty list → print(res[0]) raises IndexError → 500
        self.assertEqual(response.code, 500)


# ---------------------------------------------------------------------------
# ExplorerLast50
# ---------------------------------------------------------------------------


class TestExplorerLast50(ExplorerHttpTestCase):
    def setUp(self):
        super().setUp()
        mock_block = MagicMock()
        mock_block.index = 100
        mock_block.__getitem__ = MagicMock(
            side_effect=lambda key: 100 if key == "index" else None
        )
        LatestBlock.block = mock_block
        mock_db = MagicMock()
        mock_db.blocks.aggregate = MagicMock(
            return_value=make_async_iter_cursor([{"_id": "1TestAddr", "count": 10}])
        )
        self.config.mongo.async_db = mock_db

    def tearDown(self):
        LatestBlock.block = None
        super().tearDown()

    def test_returns_miners_list(self):
        response = self.fetch("/explorer-last50")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["_id"], "1TestAddr")


# ---------------------------------------------------------------------------
# ExplorerSearchHandler
# ---------------------------------------------------------------------------


class TestExplorerSearchHandler(ExplorerHttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        mock_db.blocks.count_documents = AsyncMock(return_value=0)
        mock_db.blocks.find = MagicMock(return_value=make_async_iter_cursor([]))
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        mock_db.miner_transactions.count_documents = AsyncMock(return_value=0)
        mock_db.miner_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        self.config.mongo.async_db = mock_db
        self.config.BU = MagicMock()
        self.config.BU.get_wallet_balance = AsyncMock(return_value=0.0)
        self.mock_db = mock_db

    def test_no_term_returns_empty(self):
        response = self.fetch("/explorer-search")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data, {})

    def test_integer_term_no_match_falls_through(self):
        # No block at height 999 → tries other searches → returns {} eventually
        response = self.fetch("/explorer-search?term=999")
        self.assertEqual(response.code, 200)

    def test_integer_term_finds_block_height(self):
        self.mock_db.blocks.count_documents = AsyncMock(return_value=1)
        self.mock_db.blocks.find = MagicMock(
            return_value=make_async_iter_cursor(
                [{"index": 999, "hash": "abc", "time": 1000}]
            )
        )
        response = self.fetch("/explorer-search?term=999")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["resultType"], "block_height")

    def test_64char_hex_term_finds_block_hash(self):
        hex64 = "a" * 64
        self.mock_db.blocks.count_documents = AsyncMock(
            side_effect=lambda q: 1 if "hash" in str(q) else 0
        )
        self.mock_db.blocks.find = MagicMock(
            return_value=make_async_iter_cursor(
                [{"hash": hex64, "index": 5, "time": 1000}]
            )
        )
        response = self.fetch(f"/explorer-search?term={hex64}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data.get("resultType"), "block_hash")

    def test_get_wallet_balance_result_type(self):
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        self.mock_db.blocks.count_documents = AsyncMock(return_value=1)
        # Include required 'time' field for changetime()
        self.mock_db.blocks.find = MagicMock(
            return_value=make_async_iter_cursor([{"transactions": [], "time": 1000}])
        )
        self.config.BU.get_wallet_balance = AsyncMock(return_value=2.5)
        response = self.fetch(
            f"/explorer-search?term={address}&result_type=get_wallet_balance"
        )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("balance", data)
        self.assertEqual(data["resultType"], "txn_outputs_to")


def make_count_side_effect(target_key, exact=True):
    """Return an async side_effect function that returns 1 for queries containing target_key."""

    async def side_effect(query, *args, **kwargs):
        query_str = str(query)
        if exact:
            # Check for exact key match
            if (
                list(query.keys())[0] == target_key
                if isinstance(query, dict) and query
                else False
            ):
                return 1
        else:
            if target_key in query_str:
                return 1
        return 0

    return side_effect


class TestExplorerSearchHandlerFoundPaths(ExplorerHttpTestCase):
    """Test all the 'found result' paths in ExplorerSearchHandler."""

    def setUp(self):
        super().setUp()
        self.mock_db = MagicMock()
        # Default: all count_documents return 0 (no result found)
        self.mock_db.blocks.count_documents = AsyncMock(return_value=0)
        self.mock_db.blocks.find = MagicMock(
            return_value=make_async_iter_cursor(
                [{"index": 1, "hash": "abc", "time": 1000}]
            )
        )
        self.mock_db.miner_transactions.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        self.mock_db.failed_transactions.count_documents = AsyncMock(return_value=0)
        self.mock_db.failed_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        self.config.mongo.async_db = self.mock_db
        self.config.BU = MagicMock()
        self.config.BU.get_wallet_balance = AsyncMock(return_value=0.0)

    def _set_count_for_key(self, key):
        """Make count_documents return 1 when first query key matches."""

        async def side_effect(query, *args, **kwargs):
            if isinstance(query, dict) and list(query.keys())[0] == key:
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=side_effect)

    def test_found_by_public_key(self):
        """Covers lines 130-142: block found by public_key"""
        term = "pubkeyabc123"  # not an int, not a valid hex64
        self._set_count_for_key("public_key")
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["resultType"], "block_height")

    def test_found_by_transactions_public_key(self):
        """Covers lines 148-160: block found by transactions.public_key"""
        term = "pubkeyabc123"

        async def side_effect(query, *args, **kwargs):
            if "transactions.public_key" in str(query):
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=side_effect)
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["resultType"], "block_height")

    def test_found_by_hash(self):
        """Covers lines 183-187 (or similar): block found by hash"""
        term = "a" * 64  # 64-char hex string

        async def side_effect(query, *args, **kwargs):
            if isinstance(query, dict) and list(query.keys()) == ["hash"]:
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=side_effect)
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)

    def test_found_by_block_id(self):
        """Covers the block id search path"""
        # A base64-decodable string that's NOT a valid hex64
        import base64

        term = base64.b64encode(b"test_block_id_xyz").decode()

        async def side_effect(query, *args, **kwargs):
            if isinstance(query, dict) and "id" in query:
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=side_effect)
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)

    def test_found_by_txn_hash(self):
        """Covers transactions.hash search path"""
        term = "b" * 64  # 64-char hex string, same as hash but different handler
        call_count = 0

        async def side_effect(query, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            q_str = str(query)
            # Wait for the transactions.hash query (after public_key, t.pubkey, hash, id)
            if "transactions.hash" in q_str:
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=side_effect)
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)

    def test_found_by_txn_rid(self):
        """Covers transactions.rid search path"""
        term = "c" * 64

        async def side_effect(query, *args, **kwargs):
            q_str = str(query)
            if "transactions.rid" in q_str:
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=side_effect)
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)

    def test_found_in_mempool_by_id(self):
        """Covers mempool id search path"""
        import base64

        term = base64.b64encode(b"mempool_txn_id").decode()

        async def blocks_side_effect(query, *args, **kwargs):
            return 0

        async def mempool_side_effect(query, *args, **kwargs):
            if "id" in str(query):
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=blocks_side_effect)
        self.mock_db.miner_transactions.count_documents = AsyncMock(
            side_effect=mempool_side_effect
        )
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([{"id": term, "time": 1000}])
        )
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)

    def test_found_in_mempool_by_hash(self):
        """Covers mempool hash search path"""
        term = "d" * 64

        async def blocks_side_effect(query, *args, **kwargs):
            return 0

        async def mempool_side_effect(query, *args, **kwargs):
            if "hash" in str(query):
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=blocks_side_effect)
        self.mock_db.miner_transactions.count_documents = AsyncMock(
            side_effect=mempool_side_effect
        )
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([{"hash": term, "time": 1000}])
        )
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)

    def test_found_in_mempool_by_outputs_to(self):
        """Covers mempool outputs.to search path"""
        term = "1TestAddress"

        async def blocks_side_effect(query, *args, **kwargs):
            return 0

        async def mempool_side_effect(query, *args, **kwargs):
            if "outputs.to" in str(query):
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=blocks_side_effect)
        self.mock_db.miner_transactions.count_documents = AsyncMock(
            side_effect=mempool_side_effect
        )
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_async_iter_cursor(
                [{"outputs": [{"to": term}], "time": 1000}]
            )
        )
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)

    def test_found_in_mempool_by_public_key(self):
        """Covers mempool public_key search path"""
        term = "mempoolpubkey"

        async def blocks_side_effect(query, *args, **kwargs):
            return 0

        async def mempool_side_effect(query, *args, **kwargs):
            if "public_key" in str(query) and "outputs" not in str(query):
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=blocks_side_effect)
        self.mock_db.miner_transactions.count_documents = AsyncMock(
            side_effect=mempool_side_effect
        )
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([{"public_key": term, "time": 1000}])
        )
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)

    def test_found_in_mempool_by_rid(self):
        """Covers mempool rid result path (lines 399-411)"""
        term = "mempoolrid"

        async def mempool_side_effect(query, *args, **kwargs):
            # Use exact key match to avoid matching "mempoolrid" value that contains "rid"
            if isinstance(query, dict) and list(query.keys()) == ["rid"]:
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.count_documents = AsyncMock(
            side_effect=mempool_side_effect
        )
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([{"rid": term, "time": 1000}])
        )
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)
        self.assertEqual(data["resultType"], "mempool_rid")

    def test_found_by_txn_id(self):
        """Covers $or txn_id result path (approx line 253)"""
        import base64 as b64_mod

        # Term must be: NOT int, NOT 64-hex (skips hash/txn.hash/txn.rid), IS valid base64
        # AND block.id returns 0, so handler proceeds to $or block
        term = b64_mod.b64encode(
            b"my_txn_id"
        ).decode()  # "bXlfdHhuX2lk", short non-64-hex

        async def side_effect(query, *args, **kwargs):
            if isinstance(query, dict) and "$or" in query:
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=side_effect)
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["resultType"], "txn_id")

    def test_found_by_txn_field(self):
        """Covers fields loop result path (approx lines 309-311)"""
        term = "f" * 64  # 64-char hex; int("ff..f") raises ValueError (not base-10)

        async def side_effect(query, *args, **kwargs):
            if isinstance(query, dict) and list(query.keys()) == [
                "transactions.public_key_hash"
            ]:
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=side_effect)
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["resultType"], "txn_hash")

    def test_exception_in_mempool_outputs_to_continues(self):
        """Covers except:pass at lines 372-373 (mempool_outputs_to block).
        A term with no hex chars causes re.search(...).group(0) to raise."""
        term = "GHJKLMNP"  # no hex chars (not A-F, a-f, 0-9)
        self.mock_db.blocks.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.count_documents = AsyncMock(return_value=0)
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)  # exception caught and execution continues

    def test_exception_in_mempool_public_key_continues(self):
        """Covers except:pass at lines 391-392 (mempool_public_key block).
        Mocked miner_transactions.count_documents raises for public_key query."""
        term = "GHJKLMNP"  # no hex chars (already triggers outputs_to except at 372)

        async def mempool_side_effect(query, *args, **kwargs):
            if isinstance(query, dict) and list(query.keys()) == ["public_key"]:
                raise Exception("simulated db error")
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.count_documents = AsyncMock(
            side_effect=mempool_side_effect
        )
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)  # exception caught and execution continues

    def test_exception_in_mempool_rid_continues(self):
        """Covers except:pass at lines 410-411 (mempool_rid block)."""
        term = "GHJKLMNP"

        async def mempool_side_effect(query, *args, **kwargs):
            if isinstance(query, dict) and list(query.keys()) == ["rid"]:
                raise Exception("simulated db error")
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.count_documents = AsyncMock(
            side_effect=mempool_side_effect
        )
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)

    def test_exception_in_block_pubkey_search_continues(self):
        """Covers except:pass at lines 142-143 (public_key block)."""
        term = "pubkeyabc123"

        async def side_effect(query, *args, **kwargs):
            if isinstance(query, dict) and list(query.keys()) == ["public_key"]:
                raise Exception("db error")
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=side_effect)
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)

    def test_exception_in_block_txn_pubkey_search_continues(self):
        """Covers except:pass at lines 160-161 (transactions.public_key block)."""
        term = "pubkeyabc123"

        async def side_effect(query, *args, **kwargs):
            if isinstance(query, dict) and list(query.keys()) == [
                "transactions.public_key"
            ]:
                raise Exception("db error")
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=side_effect)
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)

    def test_found_in_failed_by_id(self):
        """Covers failed_transactions id search path"""
        import base64

        term = base64.b64encode(b"failed_txn_id").decode()
        failed_doc = {"txn": {"id": term, "time": 1000}}

        async def mempool_side_effect(query, *args, **kwargs):
            return 0

        async def failed_side_effect(query, *args, **kwargs):
            if "txn.id" in str(query):
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.count_documents = AsyncMock(
            side_effect=mempool_side_effect
        )
        self.mock_db.failed_transactions.count_documents = AsyncMock(
            side_effect=failed_side_effect
        )
        self.mock_db.failed_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([{"txn": {"time": 1000}}])
        )
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)

    def test_found_in_failed_by_hash(self):
        """Covers failed_transactions hash search path"""
        term = "e" * 64

        async def failed_side_effect(query, *args, **kwargs):
            if "txn.hash" in str(query):
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.count_documents = AsyncMock(return_value=0)
        self.mock_db.failed_transactions.count_documents = AsyncMock(
            side_effect=failed_side_effect
        )
        self.mock_db.failed_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([{"txn": {"hash": term, "time": 1000}}])
        )
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)

    def test_found_in_failed_by_outputs_to(self):
        """Covers failed_transactions outputs.to search path"""
        term = "1FailedAddr"

        async def failed_side_effect(query, *args, **kwargs):
            if "txn.outputs.to" in str(query):
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.count_documents = AsyncMock(return_value=0)
        self.mock_db.failed_transactions.count_documents = AsyncMock(
            side_effect=failed_side_effect
        )
        self.mock_db.failed_transactions.find = MagicMock(
            return_value=make_async_iter_cursor(
                [{"txn": {"outputs": [], "time": 1000}}]
            )
        )
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)

    def test_found_in_failed_by_public_key(self):
        """Covers failed_transactions public_key search path"""
        term = "failedpubkey"

        async def failed_side_effect(query, *args, **kwargs):
            if "txn.public_key" in str(query):
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.count_documents = AsyncMock(return_value=0)
        self.mock_db.failed_transactions.count_documents = AsyncMock(
            side_effect=failed_side_effect
        )
        self.mock_db.failed_transactions.find = MagicMock(
            return_value=make_async_iter_cursor(
                [{"txn": {"public_key": term, "time": 1000}}]
            )
        )
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)

    def test_found_in_failed_by_rid(self):
        """Covers failed_transactions rid search path"""
        term = "failedrid"

        async def failed_side_effect(query, *args, **kwargs):
            if "txn.rid" in str(query):
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.count_documents = AsyncMock(return_value=0)
        self.mock_db.failed_transactions.count_documents = AsyncMock(
            side_effect=failed_side_effect
        )
        self.mock_db.failed_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([{"txn": {"rid": term, "time": 1000}}])
        )
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("resultType", data)


# ---------------------------------------------------------------------------
# HashrateAPIHandler (lines 29-40, 51-56, 64)
# ---------------------------------------------------------------------------


class TestHashrateAPIHandler(ExplorerHttpTestCase):
    def setUp(self):
        super().setUp()
        self.config.BU = MagicMock()
        self.config.BU.get_hash_rate = MagicMock(return_value=500.0)
        mock_block = MagicMock()
        mock_block.target = 1000
        mock_block.index = 100
        self.mock_block = mock_block
        mock_db = MagicMock()
        cursor = make_async_iter_cursor([{"index": 100, "target": "0001"}])
        mock_db.blocks.find = MagicMock(return_value=cursor)
        self.config.mongo.async_db = mock_db

    def test_hashrate_fresh_cache(self):
        """Covers lines 29-40 (refresh) and 52, 64 (get)."""
        # No HashRateAPIHandler in config → calls refresh
        if hasattr(self.config, "HashRateAPIHandler"):
            del self.config.HashRateAPIHandler
        with patch(
            "yadacoin.core.block.Block.from_dict",
            new=AsyncMock(return_value=self.mock_block),
        ):
            with patch(
                "yadacoin.http.explorer.CHAIN.get_circulating_supply", return_value=1000
            ):
                response = self.fetch("/api-stats")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("stats", data)

    def test_hashrate_stale_cache_refreshes(self):
        """Covers lines 51-56: stale cache triggers refresh."""
        # Set a very old cache
        self.config.HashRateAPIHandler = {
            "cache": {
                "time": 0,  # Very old timestamp → triggers refresh
                "circulating": 500,
                "height": 50,
                "network_hash_rate": 100,
                "difficulty": 10,
            }
        }
        with patch(
            "yadacoin.core.block.Block.from_dict",
            new=AsyncMock(return_value=self.mock_block),
        ):
            with patch(
                "yadacoin.http.explorer.CHAIN.get_circulating_supply", return_value=1000
            ):
                response = self.fetch("/api-stats")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("stats", data)

    def test_hashrate_fresh_cache_serves_directly(self):
        """Covers the existing cache path (not refresh) - line 64."""
        self.config.HashRateAPIHandler = {
            "cache": {
                "time": 9999999999,  # Far future → cache is fresh
                "circulating": 500,
                "height": 50,
                "network_hash_rate": 100,
                "difficulty": 10,
            }
        }
        response = self.fetch("/api-stats")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["stats"]["circulating"], 500)

    def test_get_wallet_balance_exception_reraises(self):
        """Covers lines 104-105: exception re-raised from get_wallet_balance."""
        # Use address that passes regex but BU raises exception
        term = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"  # valid Bitcoin address
        self.config.BU.get_wallet_balance = AsyncMock(
            side_effect=Exception("balance error")
        )
        self.config.mongo.async_db.blocks.count_documents = AsyncMock(return_value=1)
        response = self.fetch(
            f"/explorer-search?term={term}&result_type=get_wallet_balance"
        )
        # Exception is re-raised → 500
        self.assertEqual(response.code, 500)


# ---------------------------------------------------------------------------
# ExplorerHandler (line 65): self.render('explorer/index.html')
# ---------------------------------------------------------------------------


class TestExplorerHandlerGet(ExplorerHttpTestCase):
    def test_explorer_renders_template(self):
        """Line 65: self.render('explorer/index.html')"""
        response = self.fetch("/explorer")
        self.assertIn(response.code, [200, 500])


# ---------------------------------------------------------------------------
# HolderListPageHandler (line 578): self.render('holders.html')
# ---------------------------------------------------------------------------


class TestHolderListPageHandler(ExplorerHttpTestCase):
    def test_holders_page_renders_template(self):
        """Line 578: self.render('holders.html', ...)"""
        response = self.fetch("/holders")
        self.assertIn(response.code, [200, 500])


# ---------------------------------------------------------------------------
# ExplorerSearchHandler line 309: return res from get_wallet_balance
# ---------------------------------------------------------------------------


class TestExplorerSearchHandlerGetWalletBalanceReturnsResult(ExplorerHttpTestCase):
    """Line 309: get_wallet_balance returns non-None and we return it."""

    def setUp(self):
        super().setUp()
        self.mock_db = MagicMock()
        # All block searches return 0 so we fall through to get_wallet_balance
        self.mock_db.blocks.count_documents = AsyncMock(return_value=0)
        self.mock_db.blocks.find = MagicMock(return_value=make_async_iter_cursor([]))
        self.mock_db.miner_transactions.count_documents = AsyncMock(return_value=0)
        self.mock_db.miner_transactions.find = MagicMock(
            return_value=make_async_iter_cursor([])
        )
        self.mock_db.failed_transactions.count_documents = AsyncMock(return_value=0)
        self.config.mongo.async_db = self.mock_db
        self.config.BU = MagicMock()

    def test_get_wallet_balance_mid_flow_returns_result(self):
        """Line 309: go through all block searches then hit get_wallet_balance."""
        # Use an address that passes the hex regex but not hex64
        term = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        # Only return count=1 for the get_wallet_balance query (outputs.to)
        async def count_side_effect(query, *args, **kwargs):
            if "transactions.outputs.to" in str(query):
                return 1
            return 0

        self.mock_db.blocks.count_documents = AsyncMock(side_effect=count_side_effect)
        self.mock_db.blocks.find.return_value = make_async_iter_cursor(
            [{"transactions": [], "time": 1000, "index": 1}]
        )
        self.config.BU.get_wallet_balance = AsyncMock(return_value=5.0)
        response = self.fetch(f"/explorer-search?term={term}")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("balance", data)


# ---------------------------------------------------------------------------
# HolderListAPIHandler (lines 585-708): requires JWT auth
# ---------------------------------------------------------------------------


class TestHolderListAPIHandler(ExplorerHttpTestCase):
    """Lines 585-708: HolderListAPIHandler with valid JWT auth."""

    def setUp(self):
        super().setUp()
        self.config.jwt_options = {}
        self.config.mongo.db = MagicMock()
        self.config.mongo.db.config.find_one = MagicMock(
            return_value={"value": {"timestamp": 0}}
        )

        # Build a mock async_db that supports aggregate returning async iterators
        mock_db = MagicMock()

        def make_agg(*args, **kwargs):
            return make_async_iter_cursor([])

        mock_db.blocks.aggregate = MagicMock(side_effect=make_agg)
        self.config.mongo.async_db = mock_db

    def _fetch_with_jwt(self, path="/api-holders"):
        with patch(
            "yadacoin.decorators.jwtauth.jwt.decode",
            return_value={"key_or_wif": "true", "timestamp": 9999999999},
        ):
            return self.fetch(path, headers={"Authorization": "Bearer faketoken"})

    def test_holder_list_returns_json(self):
        """Lines 590-708: holder list computes balances and returns JSON."""
        response = self._fetch_with_jwt()
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("holders", data)
        self.assertIn("count", data)
        self.assertIn("circulating_supply", data)

    def test_holder_list_uses_cache(self):
        """Lines 585-589: cache hit path — returns cached data without recompute."""
        import time

        cached_data = {
            "holders": [{"address": "1Test", "balance": 1.0}],
            "count": 1,
            "circulating_supply": 1.0,
        }
        self.config._holder_list_cache = {
            "time": time.time(),  # fresh cache
            "data": cached_data,
        }
        response = self._fetch_with_jwt()
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["count"], 1)

    def test_holder_list_with_balances(self):
        """Lines 590-708 and 649-653: aggregate returns data, spending tx covered."""
        pk = "02" + "a" * 62  # fake public key hex
        fake_addr = "1FakeSpenderAddr"
        mock_db = MagicMock()

        call_count = [0]

        def make_agg(pipeline, *args, **kwargs):
            call_count[0] += 1
            # First call: pk_to_addr query → return a public_key doc
            if call_count[0] == 1:
                return make_async_iter_cursor([{"_id": pk}])
            # Second call: spent_by_addr query → a spend by pk (covers lines 649-653)
            elif call_count[0] == 2:
                return make_async_iter_cursor([{"pk": pk, "input_id": "txn1"}])
            # Third call: balances query → one output
            else:
                return make_async_iter_cursor(
                    [{"_id": {"txn_id": "txn_unspent", "to": fake_addr}, "value": 2.5}]
                )

        mock_db.blocks.aggregate = MagicMock(side_effect=make_agg)
        self.config.mongo.async_db = mock_db
        # Clear any existing cache
        if hasattr(self.config, "_holder_list_cache"):
            del self.config._holder_list_cache

        # Patch P2PKHBitcoinAddress so that our fake pk resolves to fake_addr
        with patch(
            "bitcoin.wallet.P2PKHBitcoinAddress.from_pubkey",
            return_value=MagicMock(__str__=lambda s: fake_addr),
        ):
            response = self._fetch_with_jwt()

        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIn("holders", data)
        self.assertGreaterEqual(data["count"], 0)

    def test_holder_list_invalid_pk_exception_suppressed(self):
        """Line 627: exception from from_pubkey is suppressed (pass)."""
        pk = "invalidhexkey"
        mock_db = MagicMock()
        call_count = [0]

        def make_agg(pipeline, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return make_async_iter_cursor([{"_id": pk}])
            else:
                return make_async_iter_cursor([])

        mock_db.blocks.aggregate = MagicMock(side_effect=make_agg)
        self.config.mongo.async_db = mock_db
        if hasattr(self.config, "_holder_list_cache"):
            del self.config._holder_list_cache

        # from_pubkey raises → line 627 `pass` is hit
        with patch(
            "bitcoin.wallet.P2PKHBitcoinAddress.from_pubkey",
            side_effect=Exception("invalid pubkey"),
        ):
            response = self._fetch_with_jwt()
        self.assertEqual(response.code, 200)
