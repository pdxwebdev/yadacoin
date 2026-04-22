"""
Branch coverage tests for yadacoin.core.graph.
"""

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.graph import Graph

from ..test_setup import AsyncTestCase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _agen(items):
    for it in items:
        yield it


def _make_to_list_cursor(items):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=items)
    return cursor


def _make_async_iter_cursor(items):
    cursor = MagicMock()
    # async-iterable
    cursor.__aiter__ = lambda self: _agen(items)
    cursor.limit = MagicMock(return_value=cursor)
    return cursor


def _mk_config(username_signature="srv", username="srv_user"):
    cfg = MagicMock()
    cfg.username_signature = username_signature
    cfg.username = username
    cfg.public_key = "pk"
    cfg.private_key = "priv"
    cfg.wif = "wif"
    cfg.cipher = MagicMock()
    cfg.cipher.decrypt = MagicMock(return_value=b'{"a":1}')
    cfg.mongo = MagicMock()
    cfg.mongo.async_db = MagicMock()
    return cfg


def _mk_mongo():
    mongo = MagicMock()
    mongo.db = MagicMock()
    mongo.db.miner_transactions.find = MagicMock(return_value=[])
    mongo.db.blocked_users.find = MagicMock(return_value=[])
    mongo.db.flagged_content.find = MagicMock(return_value=[])
    return mongo


async def _build_graph(
    user_sig="user",
    ids=None,
    rids=None,
    key_or_wif=None,
    update_last_collection_time=False,
):
    g = Graph()
    cfg = _mk_config()
    mongo = _mk_mongo()
    # Pre-stub the async user_collection_last_activity to avoid awaitable errors.
    cfg.mongo.async_db.user_collection_last_activity.find_one = AsyncMock(
        return_value=None
    )
    cfg.mongo.async_db.user_collection_last_activity.update_one = AsyncMock()
    await g.async_init(
        cfg,
        mongo,
        user_sig,
        ids if ids is not None else ["id1"],
        rids if rids is not None else ["rid1"],
        key_or_wif=key_or_wif,
        update_last_collection_time=update_last_collection_time,
    )
    return g


# ---------------------------------------------------------------------------
# async_init / from_dict / to_dict / to_json
# ---------------------------------------------------------------------------


class TestInitAndSerialization(AsyncTestCase):
    async def test_async_init_default(self):
        g = await _build_graph()
        self.assertEqual(g.username_signature, "user")
        self.assertFalse(g.wallet_mode)
        # rid is sha256(sorted concat)
        sigs = sorted(["srv", "user"], key=str.lower)
        expected = hashlib.sha256((sigs[0] + sigs[1]).encode("utf-8")).digest().hex()
        self.assertEqual(g.rid, expected)

    async def test_async_init_wallet_mode_with_wif(self):
        g = await _build_graph(key_or_wif="wif")
        self.assertTrue(g.wallet_mode)

    async def test_async_init_wallet_mode_with_private_key(self):
        g = await _build_graph(key_or_wif="priv")
        self.assertTrue(g.wallet_mode)

    async def test_to_dict_and_from_dict_and_to_json(self):
        g = await _build_graph()
        g.posts = ["p"]
        g.logins = ["l"]
        g.messages = ["m"]
        d = g.to_dict()
        self.assertIn("rid", d)
        # from_dict
        g2 = await _build_graph()
        g2.from_dict(
            {
                "friends": ["f"],
                "sent_friend_requests": [],
                "friend_requests": [],
                "posts": [],
                "logins": [],
                "messages": [],
                "rid": "x",
                "username": "u",
            }
        )
        self.assertEqual(g2.friends, ["f"])
        self.assertEqual(g2.rid, "x")
        # to_json returns valid json
        s = g.to_json()
        self.assertIsInstance(json.loads(s), dict)


# ---------------------------------------------------------------------------
# update_collection_last_activity
# ---------------------------------------------------------------------------


class TestUpdateCollectionLastActivity(AsyncTestCase):
    async def test_no_existing_no_update(self):
        g = await _build_graph(update_last_collection_time=False)
        g.config.mongo.async_db.user_collection_last_activity.find_one = AsyncMock(
            return_value=None
        )
        g.config.mongo.async_db.user_collection_last_activity.update_one = AsyncMock()
        await g.update_collection_last_activity()
        self.assertEqual(g.last_collection_time, 0)
        g.config.mongo.async_db.user_collection_last_activity.update_one.assert_not_called()

    async def test_existing_with_update(self):
        g = await _build_graph(update_last_collection_time=True, rids=["r1", "r2"])
        g.config.mongo.async_db.user_collection_last_activity.find_one = AsyncMock(
            return_value={"time": 123}
        )
        g.config.mongo.async_db.user_collection_last_activity.update_one = AsyncMock()
        await g.update_collection_last_activity()
        self.assertEqual(g.last_collection_time, 123)
        self.assertEqual(
            g.config.mongo.async_db.user_collection_last_activity.update_one.await_count,
            2,
        )


# ---------------------------------------------------------------------------
# get_lookup_rids / get_request_rids_for_rid
# ---------------------------------------------------------------------------


class TestLookupRids(AsyncTestCase):
    async def test_get_lookup_rids(self):
        g = await _build_graph()
        with patch("yadacoin.core.graph.GU") as MockGU:
            inst = MockGU.return_value
            inst.get_friend_requests.return_value = [{"rid": "a"}]
            inst.get_sent_friend_requests.return_value = [{"rid": "b"}, {"rid": "a"}]
            r = g.get_lookup_rids()
        self.assertEqual(set(r), {g.rid, "a", "b"})

    async def test_get_request_rids_for_rid(self):
        g = await _build_graph()
        with patch("yadacoin.core.graph.GU") as MockGU:
            inst = MockGU.return_value
            inst.get_friend_requests.return_value = [
                {"rid": "a", "requester_rid": "r1"},
                {"rid": "a", "requester_rid": "r2"},
            ]
            inst.get_sent_friend_requests.return_value = [
                {"rid": "b", "requested_rid": "r3"},
            ]
            out = g.get_request_rids_for_rid()
        self.assertEqual(out["a"], ["r1", "r2"])
        self.assertEqual(out["b"], ["r3"])

    async def test_generate_rid(self):
        g = await _build_graph()
        r = g.generate_rid("alice", "bob")
        sigs = sorted(["alice", "bob"], key=str.lower)
        expected = hashlib.sha256((sigs[0] + sigs[1]).encode("utf-8")).digest().hex()
        self.assertEqual(r, expected)


# ---------------------------------------------------------------------------
# get_friend_requests / get_sent_friend_requests
# ---------------------------------------------------------------------------


class TestFriendRequests(AsyncTestCase):
    async def test_get_friend_requests(self):
        g = await _build_graph()
        g.config.mongo.async_db.miner_transactions.find = MagicMock(
            return_value=_make_to_list_cursor([{"id": "t1"}])
        )
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_friend_requests.return_value = [{"id": "f"}]
            await g.get_friend_requests("rid1")
        self.assertEqual(len(g.friend_requests), 2)
        self.assertTrue(g.friend_requests[1]["pending"])

    async def test_get_sent_friend_requests(self):
        g = await _build_graph()
        g.config.mongo.async_db.miner_transactions.find = MagicMock(
            return_value=_make_to_list_cursor([{"id": "t1"}])
        )
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_sent_friend_requests.return_value = [{"id": "s"}]
            await g.get_sent_friend_requests("rid1")
        self.assertEqual(len(g.sent_friend_requests), 2)


# ---------------------------------------------------------------------------
# get_messages / get_sent_messages / get_new_messages
# ---------------------------------------------------------------------------


class TestMessages(AsyncTestCase):
    async def test_get_messages_non_wallet(self):
        g = await _build_graph()  # wallet_mode False
        g.config.mongo.async_db.miner_transactions.find = MagicMock(
            return_value=_make_to_list_cursor([{"id": "t"}])
        )
        with patch("yadacoin.core.graph.GU") as MockGU:
            inst = MockGU.return_value
            inst.get_friend_requests.return_value = []
            inst.get_sent_friend_requests.return_value = []
            inst.get_collection.return_value = _agen([{"id": "c"}])
            await g.get_messages()
        self.assertEqual(len(g.messages), 2)
        self.assertTrue(g.messages[1]["pending"])

    async def test_get_sent_messages_wallet_mode_no_not_mine(self):
        """Covers wallet-mode path of get_sent_messages without not_mine filter."""
        g = await _build_graph(key_or_wif="wif")
        g.mongo.db.miner_transactions.find = MagicMock(
            return_value=[{"relationship": "e", "id": "i1"}]
        )
        # Force decrypt failure to cover except branch.
        g.config.cipher.decrypt = MagicMock(side_effect=Exception("bad"))
        g.config.mongo.async_db.miner_transactions.find = MagicMock(
            return_value=_make_to_list_cursor([])
        )
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_transactions_by_rid.return_value = [
                {"id": "a", "rid": "r", "relationship": {"x": 1}, "public_key": "pk"},
            ]
            await g.get_sent_messages(not_mine=False)
        self.assertEqual(len(g.messages), 1)

    async def test_get_messages_wallet_mode(self):
        g = await _build_graph(key_or_wif="wif")
        # mongo.db.miner_transactions.find returns iterable transactions
        good_txn = {"relationship": "encrypted", "id": "i1"}
        bad_txn = {"relationship": "encrypted_bad", "id": "i2"}
        g.mongo.db.miner_transactions.find = MagicMock(return_value=[good_txn, bad_txn])

        def _decrypt(value):
            if value == "encrypted_bad":
                raise ValueError("bad")
            return b'{"x":1}'

        g.config.cipher.decrypt = MagicMock(side_effect=_decrypt)

        g.config.mongo.async_db.miner_transactions.find = MagicMock(
            return_value=_make_to_list_cursor([])
        )
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_transactions_by_rid.return_value = [
                {
                    "id": "a",
                    "rid": "r",
                    "relationship": {"x": 1},
                    "public_key": "pk",
                },
                {
                    "id": "a",
                    "rid": "r",
                    "relationship": {"x": 1},
                    "public_key": "pk",
                },  # duplicate id skipped
                {
                    "id": "b",
                    "rid": "r",
                    "relationship": {"x": 1},
                    "public_key": "other_pk",
                },
            ]
            await g.get_messages(not_mine=True)
        # not_mine filters out public_key == cfg.public_key="pk"
        self.assertEqual(len(g.messages), 1)
        self.assertEqual(g.messages[0]["public_key"], "other_pk")

    async def test_get_sent_messages_non_wallet(self):
        g = await _build_graph()
        g.config.mongo.async_db.miner_transactions.find = MagicMock(
            return_value=_make_to_list_cursor([{"id": "t"}])
        )
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_collection.return_value = _agen([{"id": "c"}])
            await g.get_sent_messages()
        self.assertEqual(len(g.messages), 2)

    async def test_get_sent_messages_wallet_mode_not_mine(self):
        g = await _build_graph(key_or_wif="wif")
        g.mongo.db.miner_transactions.find = MagicMock(
            return_value=[{"relationship": "e", "id": "i1"}]
        )
        g.config.mongo.async_db.miner_transactions.find = MagicMock(
            return_value=_make_to_list_cursor([])
        )
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_transactions_by_rid.return_value = [
                {"id": "a", "rid": "r", "relationship": {}, "public_key": "pk"},
                {
                    "id": "b",
                    "rid": "r",
                    "relationship": {"x": 1},
                    "public_key": "x",
                },
            ]
            await g.get_sent_messages(not_mine=True)
        # 'a' has empty relationship -> skipped; 'b' kept
        self.assertEqual(len(g.messages), 1)

    async def test_get_new_messages(self):
        g = await _build_graph()

        # Pre-populate self.messages by patching get_messages
        async def fake_get_messages(not_mine=False):
            g.messages = [
                {"rid": "r1", "time": "100"},
                {"rid": "r1", "time": "200"},
                {"rid": "r2", "time": "150"},
            ]

        g.get_messages = fake_get_messages
        await g.get_new_messages()
        # After sort desc by time: r1@200, r2@150, r1@100. Dedup by rid.
        self.assertEqual([m["rid"] for m in g.new_messages], ["r1", "r2"])


# ---------------------------------------------------------------------------
# get_group_messages
# ---------------------------------------------------------------------------


class TestGroupMessages(AsyncTestCase):
    async def test_wallet_mode(self):
        g = await _build_graph(key_or_wif="wif")
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_transactions_by_rid.return_value = ["tx"]
            g.get_group_messages()
        self.assertEqual(g.rid_transactions, ["tx"])

    async def test_non_wallet_filters_blocked_and_flagged(self):
        g = await _build_graph()
        # Set up rid_usernames mapping
        sig = "other_sig"
        rids_sorted = sorted(["srv", sig], key=str.lower)
        rid_for_sig = (
            hashlib.sha256((rids_sorted[0] + rids_sorted[1]).encode("utf-8"))
            .digest()
            .hex()
        )
        g.rid_usernames = {rid_for_sig: "alice"}
        g.mongo.db.blocked_users.find = MagicMock(return_value=[{"username": "bob"}])
        g.mongo.db.flagged_content.find = MagicMock(return_value=[{"id": "flagged_id"}])

        posts = [
            {"username_signature": sig, "id": "p1"},
            {"username_signature": sig, "id": "flagged_id"},  # flagged
            {"username_signature": "unknown_sig", "id": "p2"},  # not in rid_usernames
        ]
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_posts.return_value = posts
            g.get_group_messages()
        self.assertEqual(len(g.posts), 1)
        self.assertEqual(g.posts[0]["id"], "p1")

    async def test_non_wallet_blocked_username(self):
        g = await _build_graph()
        sig = "other_sig"
        rids_sorted = sorted(["srv", sig], key=str.lower)
        rid_for_sig = (
            hashlib.sha256((rids_sorted[0] + rids_sorted[1]).encode("utf-8"))
            .digest()
            .hex()
        )
        g.rid_usernames = {rid_for_sig: "blocked_user"}
        g.mongo.db.blocked_users.find = MagicMock(
            return_value=[{"username": "blocked_user"}]
        )
        g.mongo.db.flagged_content.find = MagicMock(return_value=[])
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_posts.return_value = [
                {"username_signature": sig, "id": "p1"}
            ]
            g.get_group_messages()
        self.assertEqual(g.posts, [])


# ---------------------------------------------------------------------------
# get_comments
# ---------------------------------------------------------------------------


class TestGetComments(AsyncTestCase):
    async def test_wallet_mode(self):
        g = await _build_graph(key_or_wif="wif")
        await g.get_comments()
        self.assertEqual(g.comments, [])

    async def test_no_ids_returns_empty(self):
        g = await _build_graph(ids=[])
        r = await g.get_comments()
        self.assertEqual(r, json.dumps({}))

    async def test_filters_and_dedups(self):
        g = await _build_graph(ids=["id1"])
        sig = "sig_a"
        rids_sorted = sorted(["srv", sig], key=str.lower)
        rid_a = (
            hashlib.sha256((rids_sorted[0] + rids_sorted[1]).encode("utf-8"))
            .digest()
            .hex()
        )
        g.rid_usernames = {rid_a: "alice"}
        g.mongo.db.blocked_users.find = MagicMock(return_value=[{"username": "bob"}])
        g.mongo.db.flagged_content.find = MagicMock(return_value=[{"id": "flagged"}])
        comments = [
            {
                "id": "c1",
                "username": "alice",
                "username_signature": sig,
                "relationship": {"id": "p1"},
            },
            {
                "id": "c1",  # duplicate
                "username": "alice",
                "username_signature": sig,
                "relationship": {"id": "p1"},
            },
            {
                "id": "flagged",
                "username": "alice",
                "username_signature": sig,
                "relationship": {"id": "p1"},
            },
            {
                "id": "c3",
                "username": "someone",  # required when rid not in rid_usernames
                "username_signature": "unknown",
                "relationship": {"id": "p2"},
            },
        ]
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_comments.return_value = comments
            await g.get_comments()
        self.assertIn("p1", g.comments)
        # c1 (kept), flagged (also appended since username not blocked) -> 2
        self.assertEqual(len(g.comments["p1"]), 2)

    async def test_blocked_username_excluded_from_out(self):
        g = await _build_graph(ids=["id1"])
        sig = "sig_a"
        rids_sorted = sorted(["srv", sig], key=str.lower)
        rid_a = (
            hashlib.sha256((rids_sorted[0] + rids_sorted[1]).encode("utf-8"))
            .digest()
            .hex()
        )
        g.rid_usernames = {rid_a: "blocked_user"}
        g.mongo.db.blocked_users.find = MagicMock(
            return_value=[{"username": "blocked_user"}]
        )
        g.mongo.db.flagged_content.find = MagicMock(return_value=[])
        comments = [
            {
                "id": "c1",
                "username_signature": sig,
                "relationship": {"id": "p1"},
            }
        ]
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_comments.return_value = comments
            await g.get_comments()
        self.assertEqual(g.comments["p1"], [])


# ---------------------------------------------------------------------------
# get_reacts
# ---------------------------------------------------------------------------


class TestGetReacts(AsyncTestCase):
    async def test_wallet_mode(self):
        g = await _build_graph(key_or_wif="wif")
        await g.get_reacts()
        self.assertEqual(g.reacts, [])

    async def test_no_ids_returns_empty(self):
        g = await _build_graph(ids=[])
        r = await g.get_reacts()
        self.assertEqual(r, json.dumps({}))

    async def test_filters(self):
        g = await _build_graph(ids=["id1"])
        sig = "sig_a"
        rids_sorted = sorted(["srv", sig], key=str.lower)
        rid_a = (
            hashlib.sha256((rids_sorted[0] + rids_sorted[1]).encode("utf-8"))
            .digest()
            .hex()
        )
        g.rid_usernames = {rid_a: "alice"}
        g.mongo.db.blocked_users.find = MagicMock(return_value=[{"username": "bob"}])
        g.mongo.db.flagged_content.find = MagicMock(return_value=[{"id": "flagged"}])
        reacts = [
            {
                "id": "r1",
                "username": "alice",
                "username_signature": sig,
                "relationship": {"id": "p1"},
            },
            {
                "id": "flagged",
                "username": "alice",
                "username_signature": sig,
                "relationship": {"id": "p1"},
            },
            {
                "id": "r3",
                "username": "someone",
                "username_signature": "unknown",
                "relationship": {"id": "p2"},
            },
        ]
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_reacts.return_value = reacts
            await g.get_reacts()
        self.assertIn("p1", g.reacts)

    async def test_blocked_username_excluded(self):
        g = await _build_graph(ids=["id1"])
        sig = "sig_a"
        rids_sorted = sorted(["srv", sig], key=str.lower)
        rid_a = (
            hashlib.sha256((rids_sorted[0] + rids_sorted[1]).encode("utf-8"))
            .digest()
            .hex()
        )
        g.rid_usernames = {rid_a: "blocked_user"}
        g.mongo.db.blocked_users.find = MagicMock(
            return_value=[{"username": "blocked_user"}]
        )
        g.mongo.db.flagged_content.find = MagicMock(return_value=[])
        reacts = [
            {
                "id": "r1",
                "username_signature": sig,
                "relationship": {"id": "p1"},
            }
        ]
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_reacts.return_value = reacts
            await g.get_reacts()
        self.assertEqual(g.reacts["p1"], [])


# ---------------------------------------------------------------------------
# get_collection
# ---------------------------------------------------------------------------


class TestGetCollection(AsyncTestCase):
    async def test_no_rids_returns(self):
        g = await _build_graph(rids=[])
        await g.get_collection()
        self.assertEqual(g.collection, [])

    async def test_collects_with_new_count(self):
        g = await _build_graph(rids=["r1"])
        g.config.mongo.async_db.user_collection_last_activity.find_one = AsyncMock(
            return_value={"time": 100}
        )
        # async cursor with limit()
        g.config.mongo.async_db.miner_transactions.find = MagicMock(
            return_value=_make_async_iter_cursor(
                [
                    {"time": 50, "id": "old_pending"},  # not new
                    {"time": 200, "id": "new_pending"},  # new
                ]
            )
        )
        with patch("yadacoin.core.graph.GU") as MockGU:
            MockGU.return_value.get_collection.return_value = _agen(
                [
                    {"time": 50, "id": "old"},
                    {"time": 200, "id": "newish"},
                ]
            )
            await g.get_collection()
        self.assertEqual(len(g.collection), 4)
        # 2 items have time > 100 -> new_count == 2
        self.assertEqual(g.new_count, 2)
