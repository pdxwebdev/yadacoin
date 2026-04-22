"""
Branch coverage tests for yadacoin.core.graphutils.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.graphutils import GraphUtils

from ..test_setup import AsyncTestCase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _agen(items):
    for it in items:
        yield it


def _to_list_cursor(items):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=items)
    return cursor


def _async_iter_cursor(items):
    cursor = MagicMock()
    cursor.__aiter__ = lambda self: _agen(items)
    return cursor


def _sortable_cursor(items, count=None):
    """Mimics mongo find().sort() with .count_documents() and indexing."""
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.count_documents = MagicMock(
        return_value=len(items) if count is None else count
    )
    cursor.__getitem__ = lambda self, i: items[i]
    cursor.__iter__ = lambda self: iter(items)
    return cursor


def _mk_config(public_key="pk", username_signature="srv_sig", wif="wif"):
    cfg = MagicMock()
    cfg.public_key = public_key
    cfg.username_signature = username_signature
    cfg.wif = wif
    cfg.cipher = MagicMock()
    cfg.cipher.decrypt = MagicMock(return_value=b'{"ok":1}')
    cfg.LatestBlock.block.index = 100
    cfg.LatestBlock.block.hash = "lblockhash"
    cfg.skynet_url = "http://skynet"
    cfg.skynet_api_key = "k"
    cfg.BU = MagicMock()
    cfg.BU.get_transactions = MagicMock(return_value="txns")
    cfg.BU.get_blocks = MagicMock(return_value=[])
    cfg.BU.get_transaction_by_id = AsyncMock(return_value={"id": "x"})
    cfg.mongo = MagicMock()
    cfg.mongo.db = MagicMock()
    cfg.mongo.async_db = MagicMock()
    return cfg


def _make_gu():
    cfg = _mk_config()
    with patch("yadacoin.core.graphutils.Config", return_value=cfg):
        gu = GraphUtils()
    gu.config = cfg
    gu.mongo = cfg.mongo
    return gu, cfg


# ---------------------------------------------------------------------------
# __init__ + simple search methods
# ---------------------------------------------------------------------------


class TestSimpleSearch(AsyncTestCase):
    async def test_get_all_usernames(self):
        gu, cfg = _make_gu()
        r = await gu.get_all_usernames()
        self.assertEqual(r, "txns")
        cfg.BU.get_transactions.assert_called()

    async def test_get_all_groups(self):
        gu, cfg = _make_gu()
        r = await gu.get_all_groups()
        self.assertEqual(r, "txns")

    async def test_search_username(self):
        gu, cfg = _make_gu()
        r = await gu.search_username("alice")
        self.assertEqual(r, "txns")

    async def test_search_ns_username_minimal(self):
        gu, cfg = _make_gu()
        cfg.mongo.async_db.name_server.find = MagicMock(
            return_value=_to_list_cursor([{"x": 1}])
        )
        r = await gu.search_ns_username("alice")
        self.assertEqual(r, [{"x": 1}])

    async def test_search_ns_username_with_extras(self):
        gu, cfg = _make_gu()
        cfg.mongo.async_db.name_server.find = MagicMock(
            return_value=_to_list_cursor([])
        )
        r = await gu.search_ns_username("alice", ns_requested_rid="rrid", id_type="t")
        self.assertEqual(r, [])

    async def test_search_ns_requested_rid_minimal(self):
        gu, cfg = _make_gu()
        cfg.mongo.async_db.name_server.find = MagicMock(
            return_value=_to_list_cursor([])
        )
        await gu.search_ns_requested_rid("rrid")

    async def test_search_ns_requested_rid_with_extras(self):
        gu, cfg = _make_gu()
        cfg.mongo.async_db.name_server.find = MagicMock(
            return_value=_to_list_cursor([])
        )
        await gu.search_ns_requested_rid("rrid", ns_username="alice", id_type="t")

    async def test_search_ns_requester_rid_minimal(self):
        gu, cfg = _make_gu()
        cfg.mongo.async_db.name_server.find = MagicMock(
            return_value=_to_list_cursor([])
        )
        await gu.search_ns_requester_rid("rrid")

    async def test_search_ns_requester_rid_with_extras(self):
        gu, cfg = _make_gu()
        cfg.mongo.async_db.name_server.find = MagicMock(
            return_value=_to_list_cursor([])
        )
        await gu.search_ns_requester_rid("rrid", ns_username="alice", id_type="t")

    async def test_search_rid_list(self):
        gu, cfg = _make_gu()
        r = await gu.search_rid(["a", "b"])
        self.assertEqual(r, "txns")

    async def test_search_rid_scalar(self):
        gu, cfg = _make_gu()
        r = await gu.search_rid("a")
        self.assertEqual(r, "txns")


# ---------------------------------------------------------------------------
# get_posts / get_reacts / get_comments — share structure
# ---------------------------------------------------------------------------


def _setup_post_like(gu, cfg, cache_collection, cache_items=None, agg_items=None):
    cache_items = cache_items or []
    agg_items = agg_items or []
    getattr(gu.mongo.db, cache_collection).find = MagicMock(
        return_value=_sortable_cursor(cache_items)
    )
    getattr(gu.mongo.db, cache_collection).find_one = MagicMock(return_value=None)
    getattr(gu.mongo.db, cache_collection).update = MagicMock()
    getattr(gu.mongo.db, cache_collection).insert = MagicMock()
    gu.mongo.db.blocks.aggregate = MagicMock(return_value=iter(agg_items))
    gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))
    gu.mongo.db.fastgraph_transaction_cache.find = MagicMock(return_value=iter([]))


class TestGetPosts(AsyncTestCase):
    async def test_get_posts_no_cache_no_friends_inserts_marker(self):
        gu, cfg = _make_gu()
        _setup_post_like(gu, cfg, "posts_cache")
        gu.get_mutual_username_signatures = MagicMock(return_value=[])
        gu.get_transactions_by_rid = MagicMock(return_value=iter([]))
        out = list(gu.get_posts("rid1"))
        self.assertEqual(out, [])
        gu.mongo.db.posts_cache.insert.assert_called()

    async def test_get_posts_with_cache_existing(self):
        gu, cfg = _make_gu()
        _setup_post_like(
            gu,
            cfg,
            "posts_cache",
            cache_items=[{"height": 50}],
            agg_items=[],
        )
        # Existing cached post yielded at end
        gu.mongo.db.posts_cache.find = MagicMock(
            side_effect=[
                _sortable_cursor([{"height": 50}]),
                iter(
                    [
                        {
                            "txn": {"id": "p1"},
                            "height": 60,
                            "username_signature": "us",
                        }
                    ]
                ),
            ]
        )
        gu.get_mutual_username_signatures = MagicMock(return_value=[])
        gu.get_transactions_by_rid = MagicMock(return_value=iter([]))
        out = list(gu.get_posts(["rid1"]))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["height"], 60)

    async def test_get_posts_decrypt_success(self):
        gu, cfg = _make_gu()
        _setup_post_like(
            gu,
            cfg,
            "posts_cache",
            agg_items=[
                {
                    "txn": {"id": "p1", "relationship": "encrypted"},
                    "height": 60,
                }
            ],
        )
        gu.mongo.db.posts_cache.find = MagicMock(
            side_effect=[
                _sortable_cursor([]),
                iter([]),
            ]
        )
        gu.get_mutual_username_signatures = MagicMock(return_value=["sig1"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter(
                [{"relationship": {"their_username_signature": "friend_sig"}}]
            )
        )
        # Patch Crypt: decrypt returns base64-encoded JSON with postText
        import base64

        payload = base64.b64encode(b'{"postText":"hi"}')

        class FakeCrypt:
            def __init__(self, *a, **k):
                pass

            def decrypt(self, _):
                return payload

        with patch("yadacoin.core.crypt.Crypt", FakeCrypt), patch(
            "yadacoin.core.crypt.Crypt", FakeCrypt
        ):
            out = list(gu.get_posts("rid1"))
        # had_txns=True means insert marker was NOT called
        gu.mongo.db.posts_cache.insert.assert_not_called()
        gu.mongo.db.posts_cache.update.assert_called()
        # output is from cached posts which we set to empty
        self.assertEqual(out, [])

    async def test_get_posts_decrypt_failure(self):
        gu, cfg = _make_gu()
        _setup_post_like(
            gu,
            cfg,
            "posts_cache",
            agg_items=[
                {
                    "txn": {"id": "p1", "relationship": "encrypted"},
                    "height": 60,
                }
            ],
        )
        gu.mongo.db.posts_cache.find = MagicMock(
            side_effect=[_sortable_cursor([]), iter([])]
        )
        gu.get_mutual_username_signatures = MagicMock(return_value=["sig1"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter([{"relationship": {"their_username_signature": "fs"}}])
        )

        class FakeCrypt:
            def __init__(self, *a, **k):
                pass

            def decrypt(self, _):
                raise Exception("bad")

        with patch("yadacoin.core.crypt.Crypt", FakeCrypt), patch(
            "yadacoin.core.crypt.Crypt", FakeCrypt
        ):
            list(gu.get_posts("rid1"))
        # update called with success=False
        gu.mongo.db.posts_cache.update.assert_called()
        gu.mongo.db.posts_cache.insert.assert_called()  # had_txns False

    async def test_get_posts_cached_skip(self):
        gu, cfg = _make_gu()
        _setup_post_like(
            gu,
            cfg,
            "posts_cache",
            agg_items=[
                {
                    "txn": {"id": "p1", "relationship": "e"},
                    "height": 60,
                }
            ],
        )
        gu.mongo.db.posts_cache.find = MagicMock(
            side_effect=[_sortable_cursor([]), iter([])]
        )
        gu.mongo.db.posts_cache.find_one = MagicMock(return_value={"id": "p1"})
        gu.get_mutual_username_signatures = MagicMock(return_value=["sig1"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter([{"relationship": {"their_username_signature": "fs"}}])
        )
        list(gu.get_posts("rid1"))

    async def test_get_posts_fastgraph_yield(self):
        gu, cfg = _make_gu()
        _setup_post_like(gu, cfg, "posts_cache")
        gu.get_mutual_username_signatures = MagicMock(return_value=[])
        gu.get_transactions_by_rid = MagicMock(return_value=iter([]))
        gu.mongo.db.fastgraph_transaction_cache.find = MagicMock(
            return_value=iter([{"txn": {"id": "ftx"}}])
        )
        out = list(gu.get_posts("rid1"))
        self.assertEqual(out[0]["height"], 1)


class TestGetReacts(AsyncTestCase):
    async def test_get_reacts_no_friends(self):
        gu, cfg = _make_gu()
        _setup_post_like(gu, cfg, "reacts_cache")
        gu.get_mutual_username_signatures = MagicMock(return_value=[])
        gu.get_transactions_by_rid = MagicMock(return_value=iter([]))
        list(gu.get_reacts("rid1", ["id1"]))
        gu.mongo.db.reacts_cache.insert.assert_called()

    async def test_get_reacts_existing_cache(self):
        gu, cfg = _make_gu()
        _setup_post_like(gu, cfg, "reacts_cache")
        gu.mongo.db.reacts_cache.find = MagicMock(
            side_effect=[
                _sortable_cursor([{"height": 50}]),
                iter(
                    [
                        {
                            "txn": {
                                "id": "r1",
                                "relationship": {"id": "post1", "react": "y"},
                            },
                            "height": 60,
                            "username_signature": "us",
                        }
                    ]
                ),
            ]
        )
        gu.get_mutual_username_signatures = MagicMock(return_value=[])
        gu.get_transactions_by_rid = MagicMock(return_value=iter([]))
        out = list(gu.get_reacts(["rid1"], ["post1"]))
        self.assertEqual(len(out), 1)

    async def test_get_reacts_decrypt_success(self):
        gu, cfg = _make_gu()
        import base64

        _setup_post_like(
            gu,
            cfg,
            "reacts_cache",
            agg_items=[{"txn": {"id": "r1", "relationship": "e"}, "height": 60}],
        )
        gu.mongo.db.reacts_cache.find = MagicMock(
            side_effect=[_sortable_cursor([]), iter([])]
        )
        gu.get_mutual_username_signatures = MagicMock(return_value=["sig"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter([{"relationship": {"their_username_signature": "fs"}}])
        )
        payload = base64.b64encode(b'{"react":"y"}')

        class FakeCrypt:
            def __init__(self, *a, **k):
                pass

            def decrypt(self, _):
                return payload

        with patch("yadacoin.core.crypt.Crypt", FakeCrypt):
            list(gu.get_reacts("rid1", ["id1"]))

    async def test_get_reacts_decrypt_failure(self):
        gu, cfg = _make_gu()
        _setup_post_like(
            gu,
            cfg,
            "reacts_cache",
            agg_items=[{"txn": {"id": "r1", "relationship": "e"}, "height": 60}],
        )
        gu.mongo.db.reacts_cache.find = MagicMock(
            side_effect=[_sortable_cursor([]), iter([])]
        )
        gu.get_mutual_username_signatures = MagicMock(return_value=["sig"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter([{"relationship": {"their_username_signature": "fs"}}])
        )

        class FakeCrypt:
            def __init__(self, *a, **k):
                pass

            def decrypt(self, _):
                raise Exception("bad")

        with patch("yadacoin.core.crypt.Crypt", FakeCrypt):
            list(gu.get_reacts("rid1", ["id1"]))

    async def test_get_reacts_cached_skip(self):
        gu, cfg = _make_gu()
        _setup_post_like(
            gu,
            cfg,
            "reacts_cache",
            agg_items=[{"txn": {"id": "r1", "relationship": "e"}, "height": 60}],
        )
        gu.mongo.db.reacts_cache.find = MagicMock(
            side_effect=[_sortable_cursor([]), iter([])]
        )
        gu.mongo.db.reacts_cache.find_one = MagicMock(return_value={"id": "r1"})
        gu.get_mutual_username_signatures = MagicMock(return_value=["sig"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter([{"relationship": {"their_username_signature": "fs"}}])
        )
        list(gu.get_reacts("rid1", ["id1"]))


class TestGetComments(AsyncTestCase):
    async def test_get_comments_no_friends(self):
        gu, cfg = _make_gu()
        _setup_post_like(gu, cfg, "comments_cache")
        gu.get_mutual_username_signatures = MagicMock(return_value=[])
        gu.get_transactions_by_rid = MagicMock(return_value=iter([]))
        list(gu.get_comments("rid1", ["id1"]))
        gu.mongo.db.comments_cache.insert.assert_called()

    async def test_get_comments_existing_cache(self):
        gu, cfg = _make_gu()
        _setup_post_like(gu, cfg, "comments_cache")
        gu.mongo.db.comments_cache.find = MagicMock(
            side_effect=[
                _sortable_cursor([{"height": 50}]),
                iter(
                    [
                        {
                            "txn": {
                                "id": "c1",
                                "relationship": {
                                    "id": "post1",
                                    "comment": "x",
                                },
                            },
                            "height": 60,
                            "username_signature": "us",
                        }
                    ]
                ),
            ]
        )
        gu.get_mutual_username_signatures = MagicMock(return_value=[])
        gu.get_transactions_by_rid = MagicMock(return_value=iter([]))
        out = list(gu.get_comments(["rid1"], ["post1"]))
        self.assertEqual(len(out), 1)

    async def test_get_comments_decrypt_success(self):
        gu, cfg = _make_gu()
        import base64

        _setup_post_like(
            gu,
            cfg,
            "comments_cache",
            agg_items=[{"txn": {"id": "c1", "relationship": "e"}, "height": 60}],
        )
        gu.mongo.db.comments_cache.find = MagicMock(
            side_effect=[_sortable_cursor([]), iter([])]
        )
        gu.get_mutual_username_signatures = MagicMock(return_value=["sig"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter([{"relationship": {"their_username_signature": "fs"}}])
        )
        payload = base64.b64encode(b'{"comment":"hi"}')

        class FakeCrypt:
            def __init__(self, *a, **k):
                pass

            def decrypt(self, _):
                return payload

        with patch("yadacoin.core.crypt.Crypt", FakeCrypt):
            list(gu.get_comments("rid1", ["id1"]))

    async def test_get_comments_decrypt_failure(self):
        gu, cfg = _make_gu()
        _setup_post_like(
            gu,
            cfg,
            "comments_cache",
            agg_items=[{"txn": {"id": "c1", "relationship": "e"}, "height": 60}],
        )
        gu.mongo.db.comments_cache.find = MagicMock(
            side_effect=[_sortable_cursor([]), iter([])]
        )
        gu.get_mutual_username_signatures = MagicMock(return_value=["sig"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter([{"relationship": {"their_username_signature": "fs"}}])
        )

        class FakeCrypt:
            def __init__(self, *a, **k):
                pass

            def decrypt(self, _):
                raise Exception("bad")

        with patch("yadacoin.core.crypt.Crypt", FakeCrypt):
            list(gu.get_comments("rid1", ["id1"]))

    async def test_get_comments_cached_skip(self):
        gu, cfg = _make_gu()
        _setup_post_like(
            gu,
            cfg,
            "comments_cache",
            agg_items=[{"txn": {"id": "c1", "relationship": "e"}, "height": 60}],
        )
        gu.mongo.db.comments_cache.find = MagicMock(
            side_effect=[_sortable_cursor([]), iter([])]
        )
        gu.mongo.db.comments_cache.find_one = MagicMock(return_value={"id": "c1"})
        gu.get_mutual_username_signatures = MagicMock(return_value=["sig"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter([{"relationship": {"their_username_signature": "fs"}}])
        )
        list(gu.get_comments("rid1", ["id1"]))


# ---------------------------------------------------------------------------
# get_relationships
# ---------------------------------------------------------------------------


class TestGetRelationships(AsyncTestCase):
    async def test_get_relationships_success_and_failure(self):
        gu, cfg = _make_gu()
        cfg.BU.get_blocks.return_value = [
            {
                "transactions": [
                    {"relationship": "good"},
                    {"relationship": "bad"},
                ]
            }
        ]

        class FakeCrypt:
            def __init__(self, _):
                pass

            def decrypt(self, val):
                if val == "bad":
                    raise Exception()
                return b'{"x":1}'

        with patch("yadacoin.core.crypt.Crypt", FakeCrypt):
            r = gu.get_relationships("wif")
        self.assertEqual(r, [{"x": 1}])


# ---------------------------------------------------------------------------
# get_transaction_by_rid
# ---------------------------------------------------------------------------


class TestGetTransactionByRid(AsyncTestCase):
    async def test_returns_match_with_rid_list(self):
        gu, cfg = _make_gu()
        gu.mongo.db.blocks.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [
                            {
                                "rid": "selA",
                                "relationship": "raw",
                                "public_key": "pkA",
                            }
                        ]
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))
        r = gu.get_transaction_by_rid(["selA"], rid=True, raw=True)
        self.assertEqual(r["rid"], "selA")

    async def test_returns_match_with_scalar_rid(self):
        gu, cfg = _make_gu()
        gu.mongo.db.blocks.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [
                            {
                                "rid": "selA",
                                "relationship": "raw",
                                "public_key": "pkA",
                            }
                        ]
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))
        r = gu.get_transaction_by_rid("selA", rid=True, raw=True)
        self.assertEqual(r["rid"], "selA")

    async def test_with_username_signature_hashes(self):
        gu, cfg = _make_gu()
        gu.mongo.db.blocks.find = MagicMock(return_value=iter([]))
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))
        r = gu.get_transaction_by_rid("sel", username_signature="u", raw=True)
        self.assertIsNone(r)

    async def test_theirs_skips_matching_pub(self):
        gu, cfg = _make_gu()
        gu.mongo.db.blocks.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [
                            {
                                "rid": "sel",
                                "relationship": "r",
                                "public_key": "mypk",
                            }
                        ]
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))
        r = gu.get_transaction_by_rid(
            "sel", rid=True, raw=True, theirs=True, public_key="mypk"
        )
        self.assertIsNone(r)

    async def test_my_skips_non_matching_pub(self):
        gu, cfg = _make_gu()
        gu.mongo.db.blocks.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [
                            {
                                "rid": "sel",
                                "relationship": "r",
                                "public_key": "other",
                            }
                        ]
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))
        r = gu.get_transaction_by_rid(
            "sel", rid=True, raw=True, my=True, public_key="mypk"
        )
        self.assertIsNone(r)

    async def test_raw_false_decrypt_success(self):
        gu, cfg = _make_gu()
        gu.mongo.db.blocks.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [
                            {
                                "rid": "sel",
                                "relationship": "enc",
                                "public_key": "pk",
                            }
                        ]
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))

        class FakeCrypt:
            def __init__(self, _):
                pass

            def decrypt(self, _):
                return b'{"x":1}'

        with patch("yadacoin.core.crypt.Crypt", FakeCrypt):
            r = gu.get_transaction_by_rid("sel", wif="w", rid=True)
        self.assertEqual(r["relationship"], {"x": 1})

    async def test_raw_false_decrypt_failure_continues(self):
        gu, cfg = _make_gu()
        gu.mongo.db.blocks.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [
                            {
                                "rid": "sel",
                                "relationship": "enc",
                                "public_key": "pk",
                            }
                        ]
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))

        class FakeCrypt:
            def __init__(self, _):
                pass

            def decrypt(self, _):
                raise Exception()

        with patch("yadacoin.core.crypt.Crypt", FakeCrypt):
            r = gu.get_transaction_by_rid("sel", wif="w", rid=True)
        self.assertIsNone(r)


# ---------------------------------------------------------------------------
# get_transactions_by_rid_v2
# ---------------------------------------------------------------------------


class TestGetTransactionsByRidV2(AsyncTestCase):
    def _setup(self, gu, miner_items, block_items):
        gu.config.mongo.async_db.miner_transactions.find = MagicMock(
            return_value=_async_iter_cursor(miner_items)
        )
        gu.config.mongo.async_db.blocks.find = MagicMock(
            return_value=_async_iter_cursor(block_items)
        )

    async def test_rid_branch(self):
        gu, cfg = _make_gu()
        self._setup(
            gu,
            [{"relationship": "r"}, {"relationship": ""}],
            [
                {
                    "transactions": [
                        {"rid": "x", "relationship": "r"},
                        {"rid": "x", "relationship": ""},
                        {"rid": "other", "relationship": "r"},
                    ]
                }
            ],
        )
        out = [t async for t in gu.get_transactions_by_rid_v2(rid="x")]
        # 1 from miner + 1 from blocks (with relationship and matching rid)
        self.assertEqual(len(out), 2)

    async def test_requested_rid_branch(self):
        gu, cfg = _make_gu()
        self._setup(
            gu,
            [{"relationship": "r"}],
            [
                {
                    "transactions": [
                        {"requested_rid": "x", "relationship": "r"},
                    ]
                }
            ],
        )
        out = [t async for t in gu.get_transactions_by_rid_v2(requested_rid="x")]
        self.assertEqual(len(out), 2)

    async def test_requester_rid_branch(self):
        gu, cfg = _make_gu()
        self._setup(
            gu,
            [{"relationship": "r"}],
            [
                {
                    "transactions": [
                        {"requester_rid": "x", "relationship": "r"},
                    ]
                }
            ],
        )
        out = [t async for t in gu.get_transactions_by_rid_v2(requester_rid="x")]
        self.assertEqual(len(out), 2)


# ---------------------------------------------------------------------------
# get_transactions_by_rid + worker
# ---------------------------------------------------------------------------


class TestGetTransactionsByRid(AsyncTestCase):
    def _setup_worker_empty(self, gu):
        # Both find() calls in worker use .sort()
        def make_cur(items=()):
            c = MagicMock()
            c.sort = MagicMock(return_value=c)
            c.count_documents = MagicMock(return_value=0)
            c.__iter__ = lambda self: iter(items)
            return c

        gu.mongo.db.transactions_by_rid_cache.find = MagicMock(
            side_effect=lambda *a, **k: make_cur()
        )
        gu.mongo.db.transactions_by_rid_cache.insert = MagicMock()
        gu.mongo.db.blocks.find = MagicMock(return_value=iter([]))
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))

    async def test_basic_no_data(self):
        gu, cfg = _make_gu()
        self._setup_worker_empty(gu)
        out = list(gu.get_transactions_by_rid("rid1", "us", rid=True))
        self.assertEqual(out, [])

    async def test_rid_false_hashes(self):
        gu, cfg = _make_gu()
        self._setup_worker_empty(gu)
        out = list(gu.get_transactions_by_rid("sel", "us", rid=False))
        self.assertEqual(out, [])

    async def test_inc_mempool_cached_success(self):
        gu, cfg = _make_gu()
        self._setup_worker_empty(gu)
        gu.config.mongo.db.miner_transactions.find = MagicMock(
            return_value=MagicMock(
                sort=MagicMock(return_value=iter([{"id": "t1", "relationship": "e"}]))
            )
        )
        gu.config.mongo.db.miner_transactions_cache.find_one = MagicMock(
            return_value={"id": "t1", "success": True}
        )
        out = list(gu.get_transactions_by_rid("rid1", "us", rid=True, inc_mempool=True))
        self.assertEqual(len(out), 1)

    async def test_inc_mempool_cached_failure_skipped(self):
        gu, cfg = _make_gu()
        self._setup_worker_empty(gu)
        gu.config.mongo.db.miner_transactions.find = MagicMock(
            return_value=MagicMock(
                sort=MagicMock(return_value=iter([{"id": "t1", "relationship": "e"}]))
            )
        )
        gu.config.mongo.db.miner_transactions_cache.find_one = MagicMock(
            return_value={"id": "t1", "success": False}
        )
        out = list(gu.get_transactions_by_rid("rid1", "us", rid=True, inc_mempool=True))
        self.assertEqual(out, [])

    async def test_inc_mempool_decrypt_success(self):
        gu, cfg = _make_gu()
        self._setup_worker_empty(gu)
        gu.config.mongo.db.miner_transactions.find = MagicMock(
            return_value=MagicMock(
                sort=MagicMock(return_value=iter([{"id": "t1", "relationship": "e"}]))
            )
        )
        gu.config.mongo.db.miner_transactions_cache.find_one = MagicMock(
            return_value=None
        )
        gu.config.mongo.db.miner_transactions_cache.update = MagicMock()
        # cipher = self.config.cipher (because wif unset)
        cfg.cipher.decrypt.return_value = b'{"x":1}'
        out = list(gu.get_transactions_by_rid("rid1", "us", rid=True, inc_mempool=True))
        self.assertEqual(out[0]["relationship"], {"x": 1})

    async def test_inc_mempool_decrypt_failure(self):
        gu, cfg = _make_gu()
        self._setup_worker_empty(gu)
        gu.config.mongo.db.miner_transactions.find = MagicMock(
            return_value=MagicMock(
                sort=MagicMock(return_value=iter([{"id": "t1", "relationship": "e"}]))
            )
        )
        gu.config.mongo.db.miner_transactions_cache.find_one = MagicMock(
            return_value=None
        )
        gu.config.mongo.db.miner_transactions_cache.update = MagicMock()
        cfg.cipher.decrypt.side_effect = Exception("bad")
        out = list(gu.get_transactions_by_rid("rid1", "us", rid=True, inc_mempool=True))
        self.assertEqual(out, [])

    async def test_inc_mempool_with_different_wif_uses_new_cipher(self):
        gu, cfg = _make_gu()
        self._setup_worker_empty(gu)
        gu.config.mongo.db.miner_transactions.find = MagicMock(
            return_value=MagicMock(
                sort=MagicMock(return_value=iter([{"id": "t1", "relationship": "e"}]))
            )
        )
        gu.config.mongo.db.miner_transactions_cache.find_one = MagicMock(
            return_value=None
        )
        gu.config.mongo.db.miner_transactions_cache.update = MagicMock()

        class FakeCrypt:
            def __init__(self, _):
                pass

            def decrypt(self, _):
                return b'{"x":1}'

            def shared_decrypt(self, _):
                return b'{"x":1}'

        with patch("yadacoin.core.graphutils.Crypt", FakeCrypt):
            out = list(
                gu.get_transactions_by_rid(
                    "rid1",
                    "us",
                    wif="other",
                    rid=True,
                    inc_mempool=True,
                    shared_decrypt=True,
                )
            )
        self.assertEqual(out[0]["relationship"], {"x": 1})

    async def test_inc_mempool_raw_skip_cipher(self):
        gu, cfg = _make_gu()
        self._setup_worker_empty(gu)
        gu.config.mongo.db.miner_transactions.find = MagicMock(
            return_value=MagicMock(
                sort=MagicMock(return_value=iter([{"id": "t1", "relationship": "e"}]))
            )
        )
        out = list(
            gu.get_transactions_by_rid(
                "rid1", "us", rid=True, raw=True, inc_mempool=True
            )
        )
        self.assertEqual(len(out), 1)

    async def test_inc_mempool_requested_rid(self):
        gu, cfg = _make_gu()
        self._setup_worker_empty(gu)
        gu.config.mongo.db.miner_transactions.find = MagicMock(
            return_value=MagicMock(sort=MagicMock(return_value=iter([])))
        )
        list(
            gu.get_transactions_by_rid(
                "rid1",
                "us",
                rid=True,
                inc_mempool=True,
                requested_rid="r",
            )
        )


class TestGetTransactionsByRidWorker(AsyncTestCase):
    async def test_with_lt_block_height(self):
        gu, cfg = _make_gu()
        cur = MagicMock()
        cur.sort = MagicMock(return_value=cur)
        cur.count_documents = MagicMock(return_value=0)
        cur.__iter__ = lambda self: iter([])
        gu.mongo.db.transactions_by_rid_cache.find = MagicMock(return_value=cur)
        gu.mongo.db.blocks.find = MagicMock(return_value=iter([]))
        gu.mongo.db.transactions_by_rid_cache.insert = MagicMock()
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))
        out = list(
            gu.get_transactions_by_rid_worker(
                "sel",
                "us",
                rid=True,
                lt_block_height=100,
                requested_rid=True,
            )
        )
        self.assertEqual(out, [])

    async def test_processes_block_with_decrypt_success(self):
        gu, cfg = _make_gu()
        cur1 = MagicMock()
        cur1.sort = MagicMock(return_value=cur1)
        cur1.count_documents = MagicMock(return_value=0)
        cur2 = MagicMock()
        cur2.sort = MagicMock(return_value=iter([{"txn": {"id": "t1"}}]))
        gu.mongo.db.transactions_by_rid_cache.find = MagicMock(side_effect=[cur1, cur2])
        gu.mongo.db.transactions_by_rid_cache.insert = MagicMock()
        gu.mongo.db.blocks.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [
                            {
                                "rid": "sel",
                                "relationship": "e",
                            }
                        ],
                        "index": 1,
                        "hash": "h",
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(
            return_value=iter([{"txn": {"id": "ftx"}}])
        )

        class FakeCrypt:
            def __init__(self, _):
                pass

            def decrypt(self, _):
                return b'{"x":1}'

        with patch("yadacoin.core.crypt.Crypt", FakeCrypt):
            out = list(
                gu.get_transactions_by_rid_worker("sel", "us", wif="w", rid=True)
            )
        # fastgraph yields ftx, then cached transactions yields t1
        self.assertEqual(len(out), 2)

    async def test_processes_block_with_decrypt_failure_continues(self):
        gu, cfg = _make_gu()
        cur1 = MagicMock()
        cur1.sort = MagicMock(return_value=cur1)
        cur1.count_documents = MagicMock(return_value=0)
        cur2 = MagicMock()
        cur2.sort = MagicMock(return_value=iter([]))
        gu.mongo.db.transactions_by_rid_cache.find = MagicMock(side_effect=[cur1, cur2])
        gu.mongo.db.transactions_by_rid_cache.insert = MagicMock()
        gu.mongo.db.blocks.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [{"rid": "sel", "relationship": "e"}],
                        "index": 1,
                        "hash": "h",
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))

        class FakeCrypt:
            def __init__(self, _):
                pass

            def decrypt(self, _):
                raise Exception()

        with patch("yadacoin.core.crypt.Crypt", FakeCrypt):
            list(gu.get_transactions_by_rid_worker("sel", "us", wif="w", rid=True))

    async def test_shared_decrypt_branch(self):
        gu, cfg = _make_gu()
        cur1 = MagicMock()
        cur1.sort = MagicMock(return_value=cur1)
        cur1.count_documents = MagicMock(return_value=0)
        cur2 = MagicMock()
        cur2.sort = MagicMock(return_value=iter([]))
        gu.mongo.db.transactions_by_rid_cache.find = MagicMock(side_effect=[cur1, cur2])
        gu.mongo.db.transactions_by_rid_cache.insert = MagicMock()
        gu.mongo.db.blocks.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [{"rid": "sel", "relationship": "e"}],
                        "index": 1,
                        "hash": "h",
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))

        class FakeCrypt:
            def __init__(self, _):
                pass

            def shared_decrypt(self, _):
                return b'{"x":1}'

        with patch("yadacoin.core.crypt.Crypt", FakeCrypt):
            list(
                gu.get_transactions_by_rid_worker(
                    "sel", "us", wif="other", rid=True, shared_decrypt=True
                )
            )

    async def test_raw_skip_decrypt_with_existing_cache(self):
        gu, cfg = _make_gu()
        cur1 = MagicMock()
        cur1.sort = MagicMock(return_value=cur1)
        cur1.count_documents = MagicMock(return_value=1)
        cur1.__getitem__ = lambda self, i: {"height": 50}
        cur2 = MagicMock()
        cur2.sort = MagicMock(return_value=iter([]))
        gu.mongo.db.transactions_by_rid_cache.find = MagicMock(side_effect=[cur1, cur2])
        gu.mongo.db.transactions_by_rid_cache.insert = MagicMock()
        gu.mongo.db.blocks.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [{"requested_rid": "sel", "relationship": "r"}],
                        "index": 60,
                        "hash": "h",
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))
        list(
            gu.get_transactions_by_rid_worker(
                "sel", "us", rid=True, raw=True, requested_rid=True
            )
        )


# ---------------------------------------------------------------------------
# get_second_degree_transactions_by_rids
# ---------------------------------------------------------------------------


class TestSecondDegree(AsyncTestCase):
    async def test_collects(self):
        gu, cfg = _make_gu()
        gu.mongo.db.blocks.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [
                            {"requester_rid": "a", "requested_rid": "z"},
                            {"requester_rid": "x", "requested_rid": "b"},
                            {"requester_rid": "x", "requested_rid": "z"},
                        ]
                    }
                ]
            )
        )
        r = gu.get_second_degree_transactions_by_rids(["a", "b"], None)
        self.assertEqual(len(r), 2)

    async def test_scalar_rid(self):
        gu, cfg = _make_gu()
        gu.mongo.db.blocks.find = MagicMock(return_value=iter([]))
        gu.get_second_degree_transactions_by_rids("a", 10)


# ---------------------------------------------------------------------------
# get_friend_requests / get_sent_friend_requests
# ---------------------------------------------------------------------------


class TestFriendRequests(AsyncTestCase):
    async def test_get_friend_requests_no_data(self):
        gu, cfg = _make_gu()
        cur = MagicMock()
        cur.sort = MagicMock(return_value=cur)
        cur.count_documents = MagicMock(return_value=0)
        gu.mongo.db.friend_requests_cache.find = MagicMock(side_effect=[cur, iter([])])
        gu.mongo.db.friend_requests_cache.insert = MagicMock()
        gu.mongo.db.friend_requests_cache.update = MagicMock()
        gu.mongo.db.blocks.aggregate = MagicMock(return_value=iter([]))
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))
        out = list(gu.get_friend_requests("rid1"))
        self.assertEqual(out, [])
        gu.mongo.db.friend_requests_cache.insert.assert_called()

    async def test_get_friend_requests_with_data(self):
        gu, cfg = _make_gu()
        cur = MagicMock()
        cur.sort = MagicMock(return_value=cur)
        cur.count_documents = MagicMock(return_value=1)
        cur.__getitem__ = lambda self, i: {"height": 50}
        gu.mongo.db.friend_requests_cache.find = MagicMock(
            side_effect=[cur, iter([{"txn": {"id": "f1"}}])]
        )
        gu.mongo.db.friend_requests_cache.insert = MagicMock()
        gu.mongo.db.friend_requests_cache.update = MagicMock()
        gu.mongo.db.blocks.aggregate = MagicMock(
            return_value=iter(
                [
                    {
                        "txn": {"requested_rid": "rid1", "id": "f1"},
                        "height": 60,
                        "block_hash": "h",
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(
            return_value=iter([{"txn": {"id": "ftx"}}])
        )
        out = list(gu.get_friend_requests(["rid1"]))
        # 1 fastgraph + 1 cache
        self.assertEqual(len(out), 2)
        gu.mongo.db.friend_requests_cache.insert.assert_not_called()

    async def test_get_sent_friend_requests_no_data(self):
        gu, cfg = _make_gu()
        cur = MagicMock()
        cur.sort = MagicMock(return_value=cur)
        cur.count_documents = MagicMock(return_value=0)
        gu.mongo.db.sent_friend_requests_cache.find = MagicMock(
            side_effect=[cur, iter([])]
        )
        gu.mongo.db.sent_friend_requests_cache.update = MagicMock()
        gu.mongo.db.blocks.aggregate = MagicMock(return_value=iter([]))
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))
        out = list(gu.get_sent_friend_requests("rid1"))
        self.assertEqual(out, [])

    async def test_get_sent_friend_requests_with_data(self):
        gu, cfg = _make_gu()
        cur = MagicMock()
        cur.sort = MagicMock(return_value=cur)
        cur.count_documents = MagicMock(return_value=1)
        cur.__getitem__ = lambda self, i: {"height": 50}
        gu.mongo.db.sent_friend_requests_cache.find = MagicMock(
            side_effect=[cur, iter([{"txn": {"id": "s1"}}])]
        )
        gu.mongo.db.sent_friend_requests_cache.update = MagicMock()
        gu.mongo.db.blocks.aggregate = MagicMock(
            return_value=iter(
                [
                    {
                        "txn": {"requester_rid": "rid1", "id": "s1"},
                        "height": 60,
                        "block_hash": "h",
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(
            return_value=iter([{"txn": {"id": "ftx"}}])
        )
        out = list(gu.get_sent_friend_requests(["rid1"]))
        self.assertEqual(len(out), 2)


# ---------------------------------------------------------------------------
# get_collection (async)
# ---------------------------------------------------------------------------


class TestGetCollection(AsyncTestCase):
    async def test_no_rids(self):
        gu, cfg = _make_gu()
        out = [x async for x in gu.get_collection([])]
        self.assertEqual(out, [])

    async def test_with_cache_and_yields(self):
        gu, cfg = _make_gu()
        cfg.mongo.async_db.messages_cache.find_one = AsyncMock(
            return_value={"height": 50}
        )
        cfg.mongo.async_db.messages_cache.update_one = AsyncMock()
        # transactions aggregator
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_async_iter_cursor(
                [
                    {
                        "txn": {
                            "id": "t1",
                            "rid": "rid1",
                            "requester_rid": None,
                            "requested_rid": None,
                        },
                        "height": 60,
                        "block_hash": "h",
                    }
                ]
            )
        )
        cfg.mongo.async_db.messages_cache.find = MagicMock(
            return_value=_async_iter_cursor([{"txn": {"id": "t1"}, "height": 60}])
        )
        out = [x async for x in gu.get_collection(["rid1"])]
        self.assertEqual(len(out), 1)
        cfg.mongo.async_db.messages_cache.update_one.assert_awaited()

    async def test_with_no_cache_scalar_rid(self):
        gu, cfg = _make_gu()
        cfg.mongo.async_db.messages_cache.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.messages_cache.update_one = AsyncMock()
        cfg.mongo.async_db.blocks.aggregate = MagicMock(
            return_value=_async_iter_cursor([])
        )
        cfg.mongo.async_db.messages_cache.find = MagicMock(
            return_value=_async_iter_cursor([])
        )
        out = [x async for x in gu.get_collection("rid1")]
        self.assertEqual(out, [])


# ---------------------------------------------------------------------------
# get_mutual_rids / get_mutual_username_signatures / get_shared_secrets_by_rid
# ---------------------------------------------------------------------------


class TestMutualAndSharedSecrets(AsyncTestCase):
    async def test_get_mutual_rids(self):
        gu, cfg = _make_gu()
        gu.get_sent_friend_requests = MagicMock(return_value=[{"requested_rid": "a"}])
        gu.get_friend_requests = MagicMock(
            return_value=[{"requester_rid": "b"}, {"requester_rid": "a"}]
        )
        r = gu.get_mutual_rids("rid1")
        self.assertEqual(set(r), {"a", "b"})

    async def test_get_mutual_username_signatures(self):
        gu, cfg = _make_gu()
        gu.get_mutual_rids = MagicMock(return_value=["a"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter(
                [
                    {"relationship": {"their_username_signature": "u1"}},
                    {"relationship": {}},
                ]
            )
        )
        r = gu.get_mutual_username_signatures("rid1")
        self.assertEqual(r, ["u1"])

    async def test_get_shared_secrets_by_rid(self):
        gu, cfg = _make_gu()
        # First call (non-raw) yields self txn with private key
        # Second call (raw=True) yields other txn with public key
        priv_hex = "11" * 32
        pub_hex = "22" * 32
        calls = []

        def _gtbr(*a, **k):
            calls.append(k)
            if k.get("raw"):
                return iter(
                    [
                        {
                            "public_key": "other",
                            "dh_public_key": pub_hex,
                        }
                    ]
                )
            return iter(
                [
                    {
                        "public_key": "pk",
                        "relationship": {"dh_private_key": priv_hex},
                    }
                ]
            )

        gu.get_transactions_by_rid = MagicMock(side_effect=_gtbr)
        r = gu.get_shared_secrets_by_rid("rid1")
        self.assertEqual(len(r), 1)


# ---------------------------------------------------------------------------
# verify_message
# ---------------------------------------------------------------------------


class TestVerifyMessage(AsyncTestCase):
    async def test_existing_cache_hit(self):
        gu, cfg = _make_gu()
        gu.mongo.db.verify_message_cache.find_one = MagicMock(return_value={"x": 1})
        sent, received = await gu.verify_message("r", "m", "pk", "tx")
        self.assertFalse(sent)
        self.assertTrue(received)

    async def test_decrypt_success_received(self):
        gu, cfg = _make_gu()
        gu.mongo.db.verify_message_cache.find_one = MagicMock(side_effect=[None, None])
        gu.mongo.db.verify_message_cache.update = MagicMock()
        gu.get_shared_secrets_by_rid = MagicMock(return_value=[b"secret"])
        txn = MagicMock()
        txn.public_key = "other_pk"
        txn.transaction_signature = "sig"
        txn.relationship = "rel"
        txn.verify = AsyncMock()

        with patch(
            "yadacoin.core.graphutils.Transaction.from_dict", return_value=txn
        ), patch("yadacoin.core.crypt.Crypt") as MockCrypt:
            MockCrypt.return_value.shared_decrypt.return_value = b'{"signIn":"m"}'
            sent, received = await gu.verify_message(
                "r", "m", "pk", "tx", txn={"any": 1}
            )
        self.assertFalse(sent)
        self.assertTrue(received)

    async def test_decrypt_success_sent(self):
        gu, cfg = _make_gu()
        gu.mongo.db.verify_message_cache.find_one = MagicMock(side_effect=[None, None])
        gu.mongo.db.verify_message_cache.update = MagicMock()
        gu.get_shared_secrets_by_rid = MagicMock(return_value=[b"secret"])
        txn = MagicMock()
        txn.public_key = "pk"
        txn.transaction_signature = "sig"
        txn.relationship = "rel"
        txn.verify = AsyncMock()
        # txn is Transaction instance
        from yadacoin.core.transaction import Transaction

        with patch.object(Transaction, "verify", AsyncMock()), patch(
            "yadacoin.core.crypt.Crypt"
        ) as MockCrypt:
            MockCrypt.return_value.shared_decrypt.return_value = b'{"signIn":"m"}'
            real_txn = Transaction.__new__(Transaction)
            real_txn.public_key = "pk"
            real_txn.transaction_signature = "sig"
            real_txn.relationship = "rel"
            sent, received = await gu.verify_message("r", "m", "pk", "tx", txn=real_txn)
        self.assertTrue(sent)
        self.assertFalse(received)

    async def test_decrypt_failure_records_failure(self):
        gu, cfg = _make_gu()
        gu.mongo.db.verify_message_cache.find_one = MagicMock(side_effect=[None, None])
        gu.mongo.db.verify_message_cache.update = MagicMock()
        gu.get_shared_secrets_by_rid = MagicMock(return_value=[b"secret"])
        txn = MagicMock()
        txn.public_key = "pk"
        txn.transaction_signature = "sig"
        txn.relationship = "rel"
        txn.verify = AsyncMock()

        with patch(
            "yadacoin.core.graphutils.Transaction.from_dict", return_value=txn
        ), patch("yadacoin.core.crypt.Crypt") as MockCrypt:
            MockCrypt.return_value.shared_decrypt.side_effect = Exception("bad")
            sent, received = await gu.verify_message(
                "r", "m", "pk", "tx", txn={"any": 1}
            )
        self.assertFalse(sent)
        self.assertFalse(received)

    async def test_inner_cache_success(self):
        gu, cfg = _make_gu()
        gu.mongo.db.verify_message_cache.find_one = MagicMock(
            side_effect=[
                None,  # outer cache miss
                {"success": True, "message": {"signIn": "m"}},  # per-secret hit
            ]
        )
        gu.mongo.db.verify_message_cache.update = MagicMock()
        gu.get_shared_secrets_by_rid = MagicMock(return_value=[b"secret"])
        txn = MagicMock()
        txn.public_key = "other"
        txn.transaction_signature = "sig"
        txn.verify = AsyncMock()
        with patch("yadacoin.core.graphutils.Transaction.from_dict", return_value=txn):
            sent, received = await gu.verify_message(
                "r", "m", "pk", "tx", txn={"any": 1}
            )
        self.assertTrue(received)

    async def test_inner_cache_failure_continues(self):
        gu, cfg = _make_gu()
        gu.mongo.db.verify_message_cache.find_one = MagicMock(
            side_effect=[
                None,
                {"success": False, "message": ""},
            ]
        )
        gu.get_shared_secrets_by_rid = MagicMock(return_value=[b"secret"])
        txn = MagicMock()
        txn.public_key = "pk"
        txn.transaction_signature = "sig"
        txn.verify = AsyncMock()
        with patch("yadacoin.core.graphutils.Transaction.from_dict", return_value=txn):
            sent, received = await gu.verify_message(
                "r", "m", "pk", "tx", txn={"any": 1}
            )
        self.assertFalse(sent)
        self.assertFalse(received)

    async def test_no_txn_provided_fetches(self):
        gu, cfg = _make_gu()
        gu.mongo.db.verify_message_cache.find_one = MagicMock(side_effect=[None, None])
        gu.get_shared_secrets_by_rid = MagicMock(return_value=[])
        txn = MagicMock()
        txn.public_key = "pk"
        txn.transaction_signature = "sig"
        txn.verify = AsyncMock()
        cfg.BU.get_transaction_by_id = AsyncMock(return_value={"id": "x"})
        with patch("yadacoin.core.graphutils.Transaction.from_dict", return_value=txn):
            await gu.verify_message("r", "m", "pk", "tx")


# ---------------------------------------------------------------------------
# sia_upload
# ---------------------------------------------------------------------------


class TestSiaUpload(AsyncTestCase):
    async def test_success_first_try(self):
        gu, cfg = _make_gu()
        fake_client = MagicMock()
        fake_client.upload = MagicMock(return_value="sia://abc")
        with patch.dict(
            "sys.modules",
            {"siaskynet": MagicMock()},
        ):
            import sys

            sys.modules["siaskynet"].SkynetClient = MagicMock(return_value=fake_client)
            sys.modules["siaskynet"].utils = MagicMock()
            sys.modules["siaskynet"].utils.strip_prefix = MagicMock(return_value="abc")
            r = await gu.sia_upload("file.txt", b"data")
        self.assertEqual(r, "abc")

    async def test_first_fails_second_succeeds(self):
        gu, cfg = _make_gu()
        fake_client = MagicMock()
        # First call raises, second returns
        fake_client.upload = MagicMock(side_effect=[Exception("network"), "sia://xyz"])
        with patch.dict(
            "sys.modules",
            {"siaskynet": MagicMock()},
        ):
            import sys

            sys.modules["siaskynet"].SkynetClient = MagicMock(return_value=fake_client)
            sys.modules["siaskynet"].utils = MagicMock()
            sys.modules["siaskynet"].utils.strip_prefix = MagicMock(return_value="xyz")
            r = await gu.sia_upload("file.txt", b"data")
        self.assertEqual(r, "xyz")


# ---------------------------------------------------------------------------
# Branch coverage for remaining missing lines
# ---------------------------------------------------------------------------


def _bad_b64_crypt():
    class FakeCrypt:
        def __init__(self, *a, **k):
            pass

        def decrypt(self, _):
            return bytes([255, 255]) + b" not base64"

    return FakeCrypt


class TestRemainingBranches(AsyncTestCase):
    async def test_get_posts_b64decode_raises(self):
        gu, cfg = _make_gu()
        _setup_post_like(
            gu,
            cfg,
            "posts_cache",
            agg_items=[{"txn": {"id": "p1", "relationship": "e"}, "height": 60}],
        )
        gu.mongo.db.posts_cache.find = MagicMock(
            side_effect=[_sortable_cursor([]), iter([])]
        )
        gu.get_mutual_username_signatures = MagicMock(return_value=["sig"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter([{"relationship": {"their_username_signature": "fs"}}])
        )
        with patch("yadacoin.core.crypt.Crypt", _bad_b64_crypt()):
            list(gu.get_posts("rid1"))

    async def test_get_reacts_b64decode_raises(self):
        gu, cfg = _make_gu()
        _setup_post_like(
            gu,
            cfg,
            "reacts_cache",
            agg_items=[{"txn": {"id": "r1", "relationship": "e"}, "height": 60}],
        )
        gu.mongo.db.reacts_cache.find = MagicMock(
            side_effect=[_sortable_cursor([]), iter([])]
        )
        gu.get_mutual_username_signatures = MagicMock(return_value=["sig"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter([{"relationship": {"their_username_signature": "fs"}}])
        )
        with patch("yadacoin.core.crypt.Crypt", _bad_b64_crypt()):
            list(gu.get_reacts("rid1", ["id1"]))

    async def test_get_comments_b64decode_raises(self):
        gu, cfg = _make_gu()
        _setup_post_like(
            gu,
            cfg,
            "comments_cache",
            agg_items=[{"txn": {"id": "c1", "relationship": "e"}, "height": 60}],
        )
        gu.mongo.db.comments_cache.find = MagicMock(
            side_effect=[_sortable_cursor([]), iter([])]
        )
        gu.get_mutual_username_signatures = MagicMock(return_value=["sig"])
        gu.get_transactions_by_rid = MagicMock(
            return_value=iter([{"relationship": {"their_username_signature": "fs"}}])
        )
        with patch("yadacoin.core.crypt.Crypt", _bad_b64_crypt()):
            list(gu.get_comments("rid1", ["id1"]))

    async def test_get_transaction_by_rid_fastgraph_yield(self):
        gu, cfg = _make_gu()
        gu.mongo.db.blocks.find = MagicMock(return_value=iter([]))
        gu.mongo.db.fastgraph_transactions.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [
                            {"rid": "sel", "relationship": "r", "public_key": "pk"}
                        ]
                    }
                ]
            )
        )
        r = gu.get_transaction_by_rid("sel", rid=True, raw=True)
        self.assertEqual(r["rid"], "sel")

    async def test_get_transactions_by_rid_list_selector_and_yield(self):
        gu, cfg = _make_gu()

        def fake_worker(*a, **k):
            yield {"id": "ftx"}

        gu.get_transactions_by_rid_worker = fake_worker
        out = list(gu.get_transactions_by_rid(["selA"], "us", rid=True))
        self.assertEqual(out, [{"id": "ftx"}])

    async def test_worker_cipher_is_config_wif_string(self):
        gu, cfg = _make_gu()
        cur1 = MagicMock()
        cur1.sort = MagicMock(return_value=cur1)
        cur1.count_documents = MagicMock(return_value=0)
        cur2 = MagicMock()
        cur2.sort = MagicMock(return_value=iter([]))
        gu.mongo.db.transactions_by_rid_cache.find = MagicMock(side_effect=[cur1, cur2])
        gu.mongo.db.transactions_by_rid_cache.insert = MagicMock()
        gu.mongo.db.blocks.find = MagicMock(
            return_value=iter(
                [
                    {
                        "transactions": [{"rid": "sel", "relationship": "e"}],
                        "index": 1,
                        "hash": "h",
                    }
                ]
            )
        )
        gu.mongo.db.fastgraph_transactions.find = MagicMock(return_value=iter([]))
        list(gu.get_transactions_by_rid_worker("sel", "us", wif=None, rid=True))

    async def test_verify_message_outer_except_branch(self):
        gu, cfg = _make_gu()
        gu.mongo.db.verify_message_cache.find_one = MagicMock(side_effect=[None, None])
        gu.mongo.db.verify_message_cache.update = MagicMock()
        gu.get_shared_secrets_by_rid = MagicMock(return_value=[b"secret"])
        txn = MagicMock()
        txn.public_key = "pk"
        txn.transaction_signature = "sig"
        txn.relationship = "rel"
        txn.verify = AsyncMock()

        with patch(
            "yadacoin.core.graphutils.Transaction.from_dict", return_value=txn
        ), patch("yadacoin.core.crypt.Crypt") as MockCrypt:
            # b'null' -> json.loads = None -> 'in None' raises -> outer except
            MockCrypt.return_value.shared_decrypt.return_value = b"null"
            sent, received = await gu.verify_message(
                "r", "m", "pk", "tx", txn={"any": 1}
            )
        self.assertFalse(sent)
        self.assertFalse(received)
