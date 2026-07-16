"""
YadaCoin Open Source License (YOSL) v1.1

Tests for the KEL cross-signing mutual authentication protocol.

Covers:
  - NodeRPC._process_ratchet_auth
  - NodeRPC._handle_kel_connect
  - NodeRPC.connected
  - NodeRPC.request_sig
  - NodeRPC.sig_response
  - NodeSocketClient.connect (ECDH key storage)
"""

import base64
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ..test_setup import AsyncTestCase

# ─── helpers ──────────────────────────────────────────────────────────────────


def _make_config():
    """Minimal config mock suitable for NodeRPC tests."""
    from yadacoin.core.config import Config

    config = Config()
    config.network = "regnet"
    config.username = "testnode"
    config.public_key = (
        "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
    )
    config.private_key = (
        "0000000000000000000000000000000000000000000000000000000000000001"
    )
    config.username_signature = "testsig"
    config.peer_host = "127.0.0.1"
    config.serve_port = 8000
    config.proxy_port = 8888
    config.kel_anchor_public_key = None
    config.kel_manager = MagicMock()
    config.kel_manager.advance_peer_auth_ratchet = AsyncMock(
        return_value=("default_priv", "default_pub", None, None, "default_tpkh", False)
    )
    # Peer-branch anchor lookup — returns falsy by default so ratchet_chain
    # delta building takes the "no anchor" short-circuit, matching the
    # pre-branching tests' expectation of an empty chain by default.
    config.kel_manager.peer_branch_anchor_pub = AsyncMock(return_value="")
    config.peer = MagicMock()
    config.peer.to_dict = MagicMock(return_value={"host": "127.0.0.1"})

    # mock LatestBlock
    config.LatestBlock = MagicMock()
    config.LatestBlock.block = MagicMock()
    config.LatestBlock.block.index = 999_999

    # mock Mongo async collections
    db = MagicMock()
    for col in (
        "key_event_log",
        "miner_transactions",
        "blocks",
        "peers_recent",
        "peer_history",
    ):
        coll = AsyncMock()
        coll.find_one = AsyncMock(return_value=None)
        coll.replace_one = AsyncMock(return_value=None)
        coll.delete_many = AsyncMock(return_value=None)
        coll.count_documents = AsyncMock(return_value=0)
        # find() chain: .sort().to_list()
        find_mock = MagicMock()
        to_list_mock = AsyncMock(return_value=[])
        sort_mock = MagicMock()
        sort_mock.to_list = to_list_mock
        find_mock.return_value = sort_mock
        find_mock.sort = MagicMock(return_value=sort_mock)
        coll.find = find_mock
        setattr(db, col, coll)

    config.mongo = MagicMock()
    config.mongo.async_db = db
    config.app_log = MagicMock()
    return config


def _make_stream(peer=None):
    """Minimal stream mock."""
    stream = MagicMock()
    stream.closed.return_value = False
    stream.peer = peer or _make_peer()
    stream.session_cipher = None
    stream._ecdh_priv = None
    stream._ecdh_pub_sent = None
    stream._server_ecdh_pub = None
    stream._peer_ecdh_pub = None
    stream._peer_k0 = None
    stream._client_kel_tip_pkh_expected = ""
    stream._connect_ratchet_chain = []
    stream._connect_latest_ratchet_pkh = ""
    return stream


def _make_peer(host="127.0.0.2"):
    peer = MagicMock()
    peer.host = host
    peer.authenticated = False
    peer.identity = MagicMock()
    peer.identity.username = "peernode"
    peer.identity.username_signature = "peernode_username_signature"
    peer.to_dict = MagicMock(return_value={"host": host})
    return peer


def _make_rpc():
    """Construct a NodeRPC instance with a minimal config, no real IO."""
    from yadacoin.tcpsocket.node import NodeRPC

    config = _make_config()
    rpc = NodeRPC.__new__(NodeRPC)
    rpc.config = config
    rpc.inbound_streams = {}
    rpc.outbound_streams = {}
    return rpc


# ---------------------------------------------------------------------------
# Real secp256k1 helpers for building valid cross-signatures
# ---------------------------------------------------------------------------


def _real_keys():
    """Generate a real secp256k1 private/public key pair (hex strings)."""
    import os

    import coincurve

    priv_bytes = os.urandom(32)
    priv = coincurve.PrivateKey(priv_bytes)
    pub_hex = priv.public_key.format(compressed=True).hex()
    priv_hex = priv_bytes.hex()
    return priv_hex, pub_hex


def _real_sign(message: str, priv_hex: str) -> str:
    """Sign message using coincurve; return base64 string matching TU.generate_signature."""
    import hashlib

    import coincurve

    priv = coincurve.PrivateKey(bytes.fromhex(priv_hex))
    msg_hash = hashlib.sha256(message.encode()).digest()
    sig = priv.sign(msg_hash, hasher=None)
    return base64.b64encode(sig).decode()


# ─── KEL "start over" resync ──────────────────────────────────────────────────


class TestIdentityAnnouncementPull(AsyncTestCase):
    """_request_peer_identity_announcement / request_identity_announcement /
    identity_announcement_response."""

    def setUp(self):
        from yadacoin.tcpsocket.node import NodeRPC

        NodeRPC._ia_resync_waiters.clear()
        NodeRPC._resync_reauth.clear()

    async def test_request_is_non_blocking(self):
        """_request_peer_identity_announcement sends the request and returns
        immediately (no future/await) so the read loop stays free."""
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.write_params = AsyncMock()

        await rpc._request_peer_identity_announcement(stream, "some_txn_id")

        rpc.write_params.assert_awaited_once()
        self.assertEqual(
            rpc.write_params.call_args[0][1], "request_identity_announcement"
        )

    async def test_response_ingests_txn_and_fires_callback(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.write_params = AsyncMock()
        rpc._accept_peer_kel_chain = AsyncMock()
        reauth_cb = AsyncMock()

        await rpc._request_peer_identity_announcement(
            stream, "some_txn_id", reauth_cb=reauth_cb
        )
        req_id = next(iter(rpc._ia_resync_waiters))

        await rpc.identity_announcement_response(
            {"params": {"id": req_id, "txn": {"id": "ia_txn_123"}}}, stream
        )

        rpc._accept_peer_kel_chain.assert_awaited_once_with([{"id": "ia_txn_123"}])
        reauth_cb.assert_awaited_once_with({"id": "ia_txn_123"})
        self.assertEqual(rpc._ia_resync_waiters, {})
        self.assertEqual(rpc._resync_reauth, {})

    async def test_response_with_empty_txn_does_not_ingest(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.write_params = AsyncMock()
        rpc._accept_peer_kel_chain = AsyncMock()
        reauth_cb = AsyncMock()

        await rpc._request_peer_identity_announcement(
            stream, "some_txn_id", reauth_cb=reauth_cb
        )
        req_id = next(iter(rpc._ia_resync_waiters))

        await rpc.identity_announcement_response(
            {"params": {"id": req_id, "txn": {}}}, stream
        )

        rpc._accept_peer_kel_chain.assert_not_awaited()
        reauth_cb.assert_awaited_once_with({})

    async def test_response_ignores_unknown_request_id(self):
        rpc = _make_rpc()
        stream = _make_stream()
        await rpc.identity_announcement_response(
            {"params": {"id": "no-such-id", "txn": {}}}, stream
        )

    async def test_handler_finds_txn_in_mempool(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.write_params = AsyncMock()

        rpc.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value={"id": "ia_txn_123", "public_key": "abc"}
        )

        await rpc.request_identity_announcement(
            {"params": {"id": "req1", "txn_id": "ia_txn_123"}}, stream
        )

        payload = rpc.write_params.call_args[0][2]
        self.assertEqual(payload["id"], "req1")
        self.assertEqual(payload["txn"]["id"], "ia_txn_123")

    async def test_handler_finds_txn_in_blocks(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.write_params = AsyncMock()

        rpc.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value=None
        )
        fake_block_txn = {"id": "ia_txn_456", "public_key": "def"}

        class _AsyncIter:
            def __init__(self, items):
                self._items = list(items)

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._items:
                    return self._items.pop(0)
                raise StopAsyncIteration

        def mock_aggregate(pipeline):
            return _AsyncIter([fake_block_txn])

        rpc.config.mongo.async_db.blocks.aggregate = mock_aggregate

        await rpc.request_identity_announcement(
            {"params": {"id": "req2", "txn_id": "ia_txn_456"}}, stream
        )

        payload = rpc.write_params.call_args[0][2]
        self.assertEqual(payload["txn"]["id"], "ia_txn_456")

    async def test_handler_not_found_sends_empty(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.write_params = AsyncMock()

        rpc.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value=None
        )

        class _AsyncIter:
            def __init__(self, items):
                self._items = list(items)

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._items:
                    return self._items.pop(0)
                raise StopAsyncIteration

        def mock_aggregate(pipeline):
            return _AsyncIter([])

        rpc.config.mongo.async_db.blocks.aggregate = mock_aggregate

        await rpc.request_identity_announcement(
            {"params": {"id": "req3", "txn_id": "missing"}}, stream
        )

        payload = rpc.write_params.call_args[0][2]
        self.assertEqual(payload["txn"], {})


class TestKelResync(AsyncTestCase):
    """_request_peer_kel_resync / request_kel_resync / kel_resync_response."""

    def setUp(self):
        from yadacoin.tcpsocket.node import NodeRPC

        NodeRPC._kel_resync_waiters.clear()
        NodeRPC._resync_reauth.clear()

    async def test_request_is_non_blocking(self):
        """_request_peer_kel_resync sends the request and returns
        immediately (no future/await) so the read loop stays free."""
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.write_params = AsyncMock()

        await rpc._request_peer_kel_resync(stream)

        rpc.write_params.assert_awaited_once()
        self.assertEqual(rpc.write_params.call_args[0][1], "request_kel_resync")

    async def test_response_ingests_chain_and_fires_callback(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.write_params = AsyncMock()
        rpc._accept_peer_kel_chain = AsyncMock()
        reauth_cb = AsyncMock()

        await rpc._request_peer_kel_resync(stream, reauth_cb=reauth_cb)
        req_id = next(iter(rpc._kel_resync_waiters))

        await rpc.kel_resync_response(
            {"params": {"id": req_id, "kel_chain": [{"id": "inception_txn"}]}},
            stream,
        )

        rpc._accept_peer_kel_chain.assert_awaited_once_with([{"id": "inception_txn"}])
        reauth_cb.assert_awaited_once_with([{"id": "inception_txn"}])
        self.assertEqual(rpc._kel_resync_waiters, {})
        self.assertEqual(rpc._resync_reauth, {})

    async def test_response_with_empty_chain_does_not_ingest(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.write_params = AsyncMock()
        rpc._accept_peer_kel_chain = AsyncMock()
        reauth_cb = AsyncMock()

        await rpc._request_peer_kel_resync(stream, reauth_cb=reauth_cb)
        req_id = next(iter(rpc._kel_resync_waiters))

        await rpc.kel_resync_response(
            {"params": {"id": req_id, "kel_chain": []}}, stream
        )

        rpc._accept_peer_kel_chain.assert_not_awaited()
        reauth_cb.assert_awaited_once_with([])

    async def test_kel_resync_response_ignores_unknown_request_id(self):
        rpc = _make_rpc()
        stream = _make_stream()
        await rpc.kel_resync_response(
            {"params": {"id": "no-such-id", "kel_chain": []}}, stream
        )

    async def test_request_kel_resync_handler_sends_local_kel(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.write_params = AsyncMock()

        fake_txn_older = MagicMock()
        fake_txn_older.to_dict = MagicMock(return_value={"id": "older_entry"})
        fake_txn_anchor = MagicMock()
        fake_txn_anchor.to_dict = MagicMock(return_value={"id": "anchor_entry"})

        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value={"public_key": "abc123"},
        ), patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new_callable=AsyncMock,
            return_value=[fake_txn_older, fake_txn_anchor],
        ):
            await rpc.request_kel_resync({"params": {"id": "req1"}}, stream)

        rpc.write_params.assert_awaited_once()
        call_args = rpc.write_params.call_args
        self.assertEqual(call_args[0][1], "kel_resync_response")
        payload = call_args[0][2]
        self.assertEqual(payload["id"], "req1")
        self.assertEqual(payload["kel_chain"], [{"id": "anchor_entry"}])

    async def test_request_kel_resync_handler_no_k0_sends_empty_chain(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.write_params = AsyncMock()

        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value=None,
        ):
            await rpc.request_kel_resync({"params": {"id": "req2"}}, stream)

        payload = rpc.write_params.call_args[0][2]
        self.assertEqual(payload["kel_chain"], [])


# ─── _process_ratchet_auth ────────────────────────────────────────────────────


class TestProcessRatchetAuthEmptyChain(AsyncTestCase):
    """_process_ratchet_auth with an empty ratchet_chain and no KEL should remove_peer."""

    async def test_no_kel_inception_removes_peer(self):
        rpc = _make_rpc()
        stream = _make_stream()

        rpc.remove_peer = AsyncMock(return_value=None)

        # All DB lookups return None (no KEL found)
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "yadacoin.core.transaction.Transaction.verify",
            new_callable=AsyncMock,
        ):
            result = await rpc._process_ratchet_auth(
                stream,
                ratchet_chain=[],
                ratchet_public_key="0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
            )

        self.assertIsNone(result)
        rpc.remove_peer.assert_awaited_once()
        call_kwargs = rpc.remove_peer.call_args
        self.assertIn("no KEL inception", call_kwargs[1].get("reason", ""))


def _fix_key_event_log_find_chain(rpc):
    """The shared _make_config() mock's find().sort().to_list() chain is
    only wired correctly for a MagicMock().find() call *object*, not for
    chaining .sort() off the .find() *return value* — harmless while
    _peer_k0 stays falsy (never exercised), but the resync-retry tests
    below need _peer_k0 truthy to reach this code path at all."""
    sort_result = MagicMock()
    sort_result.to_list = AsyncMock(return_value=[])
    find_result = MagicMock()
    find_result.sort = MagicMock(return_value=sort_result)
    rpc.config.mongo.async_db.key_event_log.find = MagicMock(return_value=find_result)


class TestProcessRatchetAuthResyncRetry(AsyncTestCase):
    """_process_ratchet_auth should attempt a "start over" resync before
    giving up on a missing KEL inception, and retry exactly once."""

    async def test_resync_request_sent_and_returns_none(self):
        """When _has_kel is False on the first pass, _process_ratchet_auth
        sends a non-blocking KEL resync request and returns None
        immediately (rather than blocking / recursing) so the stream's read
        loop is free to dispatch the peer's response."""
        rpc = _make_rpc()
        stream = _make_stream()
        stream.peer.identity_announcement = None
        rpc.remove_peer = AsyncMock(return_value=None)
        _fix_key_event_log_find_chain(rpc)

        rpc.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value=None
        )
        rpc._request_peer_kel_resync = AsyncMock()

        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value={"public_key": "peerpub123"},
        ):
            result = await rpc._process_ratchet_auth(
                stream,
                ratchet_chain=[],
                ratchet_public_key="0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
            )

        # Non-blocking: returns None immediately, resync request sent, no
        # remove_peer (that only happens if the retried pass also fails or
        # the request was never sent).
        self.assertIsNone(result)
        rpc._request_peer_kel_resync.assert_awaited_once()
        rpc.remove_peer.assert_not_awaited()

    async def test_resync_skipped_on_retry_removes_peer(self):
        """If already retried (_retried=True) and still no KEL, skip the
        resync and remove the peer."""
        rpc = _make_rpc()
        stream = _make_stream()
        stream.peer.identity_announcement = None
        rpc.remove_peer = AsyncMock(return_value=None)
        _fix_key_event_log_find_chain(rpc)

        rpc.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value=None
        )
        rpc._request_peer_kel_resync = AsyncMock()

        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value={"public_key": "peerpub123"},
        ):
            result = await rpc._process_ratchet_auth(
                stream,
                ratchet_chain=[],
                ratchet_public_key="0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
                _retried=True,
            )

        self.assertIsNone(result)
        rpc._request_peer_kel_resync.assert_not_awaited()
        rpc.remove_peer.assert_awaited_once()
        reason = rpc.remove_peer.call_args[1].get("reason", "")
        self.assertIn("no KEL inception", reason)

    async def test_no_peer_k0_skips_resync_attempt(self):
        """Without a resolvable peer K0 there's nobody to ask — must not
        attempt a resync at all."""
        rpc = _make_rpc()
        stream = _make_stream()
        stream.peer.identity_announcement = None
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc._request_peer_kel_resync = AsyncMock()
        _fix_key_event_log_find_chain(rpc)

        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await rpc._process_ratchet_auth(
                stream,
                ratchet_chain=[],
                ratchet_public_key="0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
            )

        self.assertIsNone(result)
        rpc._request_peer_kel_resync.assert_not_awaited()


class TestProcessRatchetAuthMalformedTxn(AsyncTestCase):
    """_process_ratchet_auth with a malformed txn dict should remove_peer."""

    async def test_malformed_txn_removes_peer(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)

        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await rpc._process_ratchet_auth(
                stream,
                ratchet_chain=[{"not_a_real_field": True}],
                ratchet_public_key="0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
            )

        self.assertIsNone(result)
        rpc.remove_peer.assert_awaited_once()
        reason = rpc.remove_peer.call_args[1].get("reason", "")
        # From-dict succeeds for simple dicts; verify() raises — check remove was called
        self.assertIn("ratchet:", reason)


# ─── _handle_kel_connect ──────────────────────────────────────────────────────


class TestHandleKelConnect(AsyncTestCase):
    """_handle_kel_connect should send 'connected' then encrypted 'request_sig'."""

    async def test_missing_ecdh_pub_removes_peer(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)

        await rpc._handle_kel_connect(stream, params={})

        rpc.remove_peer.assert_awaited_once()
        reason = rpc.remove_peer.call_args[1].get("reason", "")
        self.assertIn("missing ecdh_public_key", reason)

    async def test_sends_connected_then_request_sig(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)

        written_calls = []

        async def mock_write_params(s, method, payload):
            written_calls.append((method, payload))

        rpc.write_params = mock_write_params

        _ecdh_priv, _ecdh_pub = (
            "a" * 64,
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
        )
        _auth_priv, _auth_pub = _real_keys()
        rpc.config.kel_manager.advance_peer_auth_ratchet = AsyncMock(
            return_value=(_auth_priv, _auth_pub, None, None, "tpkh", False)
        )

        with patch(
            "yadacoin.tcpsocket.node.SessionCipher.generate_keypair",
            return_value=(_ecdh_priv, _ecdh_pub),
        ), patch(
            "yadacoin.tcpsocket.node.SessionCipher.derive",
            return_value=MagicMock(),
        ), patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "yadacoin.core.keyrotation.NodeKeyRotationManager._sign",
            return_value="mocksig",
        ):
            await rpc._handle_kel_connect(
                stream,
                params={
                    "ecdh_public_key": _ecdh_pub,
                    "ratchet_chain": [],
                    "latest_ratchet_pkh": "",
                },
            )

        methods = [c[0] for c in written_calls]
        self.assertIn("connected", methods)
        self.assertIn("request_sig", methods)
        # 'connected' must come before 'request_sig'
        self.assertLess(methods.index("connected"), methods.index("request_sig"))

    async def test_stores_state_on_stream(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.write_params = AsyncMock()

        _ecdh_priv, _ecdh_pub = (
            "a" * 64,
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
        )
        _auth_priv, _auth_pub = _real_keys()
        rpc.config.kel_manager.advance_peer_auth_ratchet = AsyncMock(
            return_value=(_auth_priv, _auth_pub, None, None, "tpkh", False)
        )

        with patch(
            "yadacoin.tcpsocket.node.SessionCipher.generate_keypair",
            return_value=(_ecdh_priv, _ecdh_pub),
        ), patch(
            "yadacoin.tcpsocket.node.SessionCipher.derive",
            return_value=MagicMock(),
        ), patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "yadacoin.core.keyrotation.NodeKeyRotationManager._sign",
            return_value="mocksig",
        ):
            await rpc._handle_kel_connect(
                stream,
                params={
                    "ecdh_public_key": _ecdh_pub,
                    "ratchet_chain": [],
                    "latest_ratchet_pkh": "",
                },
            )

        self.assertEqual(stream._peer_ecdh_pub, _ecdh_pub)
        self.assertEqual(stream._server_ecdh_pub, _ecdh_pub)

    async def test_session_cipher_activated_after_connected(self):
        """Session cipher must be set on stream before request_sig is sent."""
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)

        cipher_activated_before_request_sig = []
        fake_cipher = MagicMock(name="FakeCipher")

        async def mock_write_params(s, method, payload):
            if method == "request_sig":
                cipher_activated_before_request_sig.append(s.session_cipher)

        rpc.write_params = mock_write_params

        _ecdh_priv, _ecdh_pub = (
            "a" * 64,
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
        )
        _auth_priv, _auth_pub = _real_keys()
        rpc.config.kel_manager.advance_peer_auth_ratchet = AsyncMock(
            return_value=(_auth_priv, _auth_pub, None, None, "tpkh", False)
        )

        with patch(
            "yadacoin.tcpsocket.node.SessionCipher.generate_keypair",
            return_value=(_ecdh_priv, _ecdh_pub),
        ), patch(
            "yadacoin.tcpsocket.node.SessionCipher.derive",
            return_value=fake_cipher,
        ), patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "yadacoin.core.keyrotation.NodeKeyRotationManager._sign",
            return_value="mocksig",
        ):
            await rpc._handle_kel_connect(
                stream,
                params={
                    "ecdh_public_key": _ecdh_pub,
                    "ratchet_chain": [],
                    "latest_ratchet_pkh": "",
                },
            )

        self.assertTrue(
            cipher_activated_before_request_sig,
            "write_params('request_sig') was never called",
        )
        self.assertEqual(
            cipher_activated_before_request_sig[0],
            fake_cipher,
            "Session cipher was not activated before request_sig was sent",
        )


# ─── connected ────────────────────────────────────────────────────────────────


class TestConnected(AsyncTestCase):
    """Client-side 'connected' handler."""

    async def test_missing_ecdh_pub_removes_peer(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.ensure_protocol_version = MagicMock()

        await rpc.connected(body={"params": {}}, stream=stream)

        rpc.remove_peer.assert_awaited_once()

    async def test_derives_session_cipher(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.ensure_protocol_version = MagicMock()

        _ecdh_priv, _ecdh_pub = (
            "a" * 64,
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
        )
        stream._ecdh_priv = _ecdh_priv

        fake_cipher = MagicMock(name="FakeCipher")
        with patch(
            "yadacoin.tcpsocket.base.SessionCipher.derive",
            return_value=fake_cipher,
        ):
            await rpc.connected(
                body={"params": {"ecdh_public_key": _ecdh_pub}},
                stream=stream,
            )

        self.assertEqual(stream.session_cipher, fake_cipher)

    async def test_stores_server_ecdh_pub(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.ensure_protocol_version = MagicMock()

        _ecdh_priv, _ecdh_pub = (
            "a" * 64,
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
        )
        stream._ecdh_priv = _ecdh_priv

        with patch(
            "yadacoin.tcpsocket.base.SessionCipher.derive", return_value=MagicMock()
        ):
            await rpc.connected(
                body={"params": {"ecdh_public_key": _ecdh_pub}},
                stream=stream,
            )

        self.assertEqual(stream._server_ecdh_pub, _ecdh_pub)

    async def test_no_priv_key_skips_cipher_derivation(self):
        """If stream._ecdh_priv is None, session_cipher stays None (no crash)."""
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.ensure_protocol_version = MagicMock()
        stream._ecdh_priv = None  # no priv key stored

        _ecdh_pub = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        await rpc.connected(
            body={"params": {"ecdh_public_key": _ecdh_pub}},
            stream=stream,
        )

        self.assertIsNone(stream.session_cipher)


# ─── request_sig ─────────────────────────────────────────────────────────────


class TestRequestSig(AsyncTestCase):
    """Client-side request_sig handler."""

    def _body(
        self,
        server_signed,
        ratchet_pub,
        server_kel_tip_pkh="",
        server_ecdh_pub="",
        **extras,
    ):
        p = {
            "server_signed": server_signed,
            "ratchet_public_key": ratchet_pub,
            "server_kel_tip_pkh": server_kel_tip_pkh,
            "server_ecdh_pub": server_ecdh_pub,
            "ratchet_chain": [],
            "latest_ratchet_pkh": "",
            "client_kel_tip_pkh": "",
        }
        p.update(extras)
        return {"params": p}

    async def test_missing_server_signed_removes_peer(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)

        await rpc.request_sig(body={"params": {}}, stream=stream)

        rpc.remove_peer.assert_awaited_once()

    async def test_invalid_server_sig_removes_peer(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)

        _auth_priv, _auth_pub = _real_keys()
        stream._ecdh_pub_sent = "clientecdh"

        # Sign with a DIFFERENT key than what we claim
        _other_priv, _other_pub = _real_keys()
        bad_sig = _real_sign("clientecdh", _other_priv)

        body = self._body(
            server_signed=bad_sig,
            ratchet_pub=_auth_pub,
            server_kel_tip_pkh="",
        )

        rpc.config.kel_manager.advance_peer_auth_ratchet = AsyncMock(
            return_value=(_auth_priv, _auth_pub, None, None, "tpkh", False)
        )
        await rpc.request_sig(body=body, stream=stream)

        rpc.remove_peer.assert_awaited_once()
        reason = rpc.remove_peer.call_args[1].get("reason", "")
        self.assertIn("server signature invalid", reason)

    async def test_valid_server_sig_sends_sig_response(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.write_params = AsyncMock()
        rpc._accept_peer_kel_chain = AsyncMock()

        _auth_priv, _auth_pub = _real_keys()
        _client_ecdh_pub = (
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )
        stream._ecdh_pub_sent = _client_ecdh_pub

        server_kel_tip_pkh = ""
        nonce = _client_ecdh_pub + server_kel_tip_pkh
        valid_sig = _real_sign(nonce, _auth_priv)

        body = self._body(
            server_signed=valid_sig,
            ratchet_pub=_auth_pub,
            server_kel_tip_pkh=server_kel_tip_pkh,
            server_ecdh_pub="serverecdh",
        )

        # _process_ratchet_auth returns success tuple
        rpc._process_ratchet_auth = AsyncMock(
            return_value=(_auth_pub, True, "ratchet", 1)
        )

        rpc.config.kel_manager.advance_peer_auth_ratchet = AsyncMock(
            return_value=(_auth_priv, _auth_pub, None, None, "tpkh", False)
        )
        with patch(
            "yadacoin.core.keyrotation.NodeKeyRotationManager._sign",
            return_value="clientmocksig",
        ), patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value=None,
        ):
            await rpc.request_sig(body=body, stream=stream)

        rpc.write_params.assert_awaited_once()
        call_args = rpc.write_params.call_args
        self.assertEqual(call_args[0][1], "sig_response")

    async def test_ratchet_auth_failure_stops_handler(self):
        """If _process_ratchet_auth returns None, request_sig must not write params."""
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.write_params = AsyncMock()
        rpc._accept_peer_kel_chain = AsyncMock()

        _auth_priv, _auth_pub = _real_keys()
        _client_ecdh_pub = (
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )
        stream._ecdh_pub_sent = _client_ecdh_pub

        nonce = _client_ecdh_pub
        valid_sig = _real_sign(nonce, _auth_priv)

        body = self._body(
            server_signed=valid_sig,
            ratchet_pub=_auth_pub,
        )

        rpc._process_ratchet_auth = AsyncMock(return_value=None)

        rpc.config.kel_manager.advance_peer_auth_ratchet = AsyncMock(
            return_value=(_auth_priv, _auth_pub, None, None, "tpkh", False)
        )
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value=None,
        ):
            await rpc.request_sig(body=body, stream=stream)

        rpc.write_params.assert_not_awaited()


# ─── sig_response ─────────────────────────────────────────────────────────────


class TestSigResponse(AsyncTestCase):
    """Server-side sig_response handler."""

    def _body(self, client_signed, ratchet_pub, **extras):
        p = {
            "client_signed": client_signed,
            "ratchet_public_key": ratchet_pub,
            "ratchet_chain": [],
        }
        p.update(extras)
        return {"params": p}

    async def test_missing_client_signed_removes_peer(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)

        await rpc.sig_response(body={"params": {}}, stream=stream)

        rpc.remove_peer.assert_awaited_once()
        reason = rpc.remove_peer.call_args[1].get("reason", "")
        self.assertIn("missing auth fields", reason)

    async def test_invalid_client_sig_removes_peer(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)

        _auth_priv, _auth_pub = _real_keys()
        _other_priv, _other_pub = _real_keys()

        stream._server_ecdh_pub = "serverecdh"
        stream._client_kel_tip_pkh_expected = ""

        bad_sig = _real_sign("serverecdh", _other_priv)
        body = self._body(client_signed=bad_sig, ratchet_pub=_auth_pub)

        await rpc.sig_response(body=body, stream=stream)

        rpc.remove_peer.assert_awaited_once()
        reason = rpc.remove_peer.call_args[1].get("reason", "")
        self.assertIn("client signature invalid", reason)

    async def test_valid_auth_marks_peer_authenticated(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.send_block_to_peer = AsyncMock()
        rpc.get_next_block = AsyncMock()

        _auth_priv, _auth_pub = _real_keys()

        server_ecdh_pub = "serverecdh"
        client_kel_tip_pkh = ""
        nonce = server_ecdh_pub + client_kel_tip_pkh
        valid_sig = _real_sign(nonce, _auth_priv)

        stream._server_ecdh_pub = server_ecdh_pub
        stream._client_kel_tip_pkh_expected = client_kel_tip_pkh
        stream._connect_ratchet_chain = []
        stream._connect_latest_ratchet_pkh = ""

        body = self._body(client_signed=valid_sig, ratchet_pub=_auth_pub)

        rpc._process_ratchet_auth = AsyncMock(
            return_value=(_auth_pub, True, "ratchet", 1)
        )

        await rpc.sig_response(body=body, stream=stream)

        self.assertTrue(stream.peer.authenticated)
        rpc.send_block_to_peer.assert_awaited_once()
        rpc.get_next_block.assert_awaited_once()

    async def test_ratchet_auth_failure_does_not_authenticate(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.send_block_to_peer = AsyncMock()
        rpc.get_next_block = AsyncMock()

        _auth_priv, _auth_pub = _real_keys()

        server_ecdh_pub = "serverecdh"
        nonce = server_ecdh_pub
        valid_sig = _real_sign(nonce, _auth_priv)

        stream._server_ecdh_pub = server_ecdh_pub
        stream._client_kel_tip_pkh_expected = ""
        stream._connect_ratchet_chain = []
        stream._connect_latest_ratchet_pkh = ""

        body = self._body(client_signed=valid_sig, ratchet_pub=_auth_pub)

        rpc._process_ratchet_auth = AsyncMock(return_value=None)

        await rpc.sig_response(body=body, stream=stream)

        self.assertFalse(stream.peer.authenticated)
        rpc.send_block_to_peer.assert_not_awaited()

    async def test_uses_connect_ratchet_chain_not_response_chain(self):
        """sig_response should use the ratchet_chain stored from the original
        'connect' message (stream._connect_ratchet_chain), not what the client
        sends in sig_response itself."""
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.send_block_to_peer = AsyncMock()
        rpc.get_next_block = AsyncMock()

        _auth_priv, _auth_pub = _real_keys()

        server_ecdh_pub = "serverecdh"
        nonce = server_ecdh_pub
        valid_sig = _real_sign(nonce, _auth_priv)

        stored_chain = [{"id": "stored_txn"}]
        stream._server_ecdh_pub = server_ecdh_pub
        stream._client_kel_tip_pkh_expected = ""
        stream._connect_ratchet_chain = stored_chain
        stream._connect_latest_ratchet_pkh = "tipkh"

        body = self._body(
            client_signed=valid_sig,
            ratchet_pub=_auth_pub,
            ratchet_chain=[{"id": "response_txn"}],  # should be ignored
        )

        rpc._process_ratchet_auth = AsyncMock(
            return_value=(_auth_pub, True, "ratchet", 1)
        )

        await rpc.sig_response(body=body, stream=stream)

        call_kwargs = rpc._process_ratchet_auth.call_args
        # first positional arg after stream is ratchet_chain
        passed_chain = call_kwargs[0][1]
        self.assertEqual(passed_chain, stored_chain)


# ─── NodeSocketClient.connect ECDH key storage ────────────────────────────────


class TestNodeSocketClientConnectEcdhStorage(AsyncTestCase):
    """NodeSocketClient.connect must store _ecdh_priv and _ecdh_pub_sent."""

    async def test_stores_ecdh_pub_sent_and_priv(self):
        from yadacoin.tcpsocket.node import NodeSocketClient

        client = NodeSocketClient.__new__(NodeSocketClient)
        client.config = _make_config()
        client.config.peer = MagicMock()
        client.config.peer.to_dict = MagicMock(return_value={})
        client.config.kel_anchor_public_key = None
        client.inbound_streams = {}
        client.outbound_streams = {}

        fake_priv = "b" * 64
        fake_pub = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"

        # The stream that super().connect() returns
        stream = _make_stream()
        stream.write = AsyncMock()
        stream.closed.return_value = False
        stream.read_bytes = AsyncMock(return_value=b"")

        peer = _make_peer()
        peer.host = "127.0.0.3"
        peer.port = 8001

        captured_streams = []

        async def mock_write_params(s, method, payload):
            captured_streams.append(s)

        client.write_params = mock_write_params

        async def mock_super_connect(p):
            return stream

        with patch(
            "yadacoin.tcpsocket.node.SessionCipher.generate_keypair",
            return_value=(fake_priv, fake_pub),
        ), patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "yadacoin.tcpsocket.base.RPCSocketClient.connect",
            new_callable=AsyncMock,
            return_value=stream,
        ):
            # _get_pending_kel_chain needs to exist
            client._get_pending_kel_chain = AsyncMock(return_value=[])
            client.send_keepalive = AsyncMock()
            client.wait_for_data = AsyncMock()

            await client.connect(peer)

        # Stream should have ECDH keys set
        self.assertEqual(stream._ecdh_priv, fake_priv)
        self.assertEqual(stream._ecdh_pub_sent, fake_pub)


if __name__ == "__main__":
    unittest.main()
