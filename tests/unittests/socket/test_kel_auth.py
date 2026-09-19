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
    config.inception = MagicMock()
    config.inception.to_dict = MagicMock(
        return_value={
            "id": "inception_txn",
            "public_key": "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
            "relationship": {
                "identity": {
                    "username": "testnode",
                    "username_signature": "testsig",
                }
            },
        }
    )
    config.kel_manager = MagicMock()
    config.kel_manager.advance_peer_auth_ratchet = AsyncMock(
        return_value=("default_priv", "default_pub", None, None, "default_tpkh", False)
    )
    # Reconnects use tip keys without advancing (sign-once tip reuse).
    config.kel_manager.get_peer_auth_keys = AsyncMock(
        return_value=("default_priv", "default_pub", None, None, "default_tpkh", False)
    )
    config.kel_manager._peer_branch_tip_by_hash_link = AsyncMock(return_value=None)
    # Peer-branch anchor lookup — returns falsy by default so ratchet_chain
    # delta building takes the "no anchor" short-circuit, matching the
    # pre-branching tests' expectation of an empty chain by default.
    config.kel_manager.peer_branch_anchor_pub = AsyncMock(return_value="")
    config.kel_manager.peer_branch_inception_public_key_hash = AsyncMock(
        return_value=""
    )
    config.kel_manager.peer_branch_wire_bundle = AsyncMock(
        return_value={
            "branch_inception_pkh": "",
            "branch_generation": 0,
            "supersedes_branch_inception_pkh": "",
            "announcement_txn": None,
            "confirming_txn": None,
            "bridge_txn": None,
        }
    )
    config.kel_manager.peer_branch_contains_pkh = AsyncMock(return_value=False)
    config.peer = MagicMock()
    config.peer.to_dict = MagicMock(return_value={"host": "127.0.0.1"})

    # mock LatestBlock
    config.LatestBlock = MagicMock()
    config.LatestBlock.block = MagicMock()
    config.LatestBlock.block.index = 999_999

    # mock Mongo async collections
    class _EmptyAsyncIter:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

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
        coll.delete_one = AsyncMock(return_value=None)
        coll.delete_many = AsyncMock(return_value=None)
        coll.count_documents = AsyncMock(return_value=0)
        coll.bulk_write = AsyncMock(return_value=None)
        coll.aggregate = MagicMock(return_value=_EmptyAsyncIter())
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
    peer.identity_announcement = None
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


def _auth_transcript(
    client_ecdh="",
    server_ecdh="",
    client_tip="",
    server_tip="",
    challenge="",
):
    """Match NodeRPC._auth_transcript field order."""
    return "|".join(
        [
            client_ecdh or "",
            server_ecdh or "",
            client_tip or "",
            server_tip or "",
            challenge or "",
        ]
    )


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

        fake_txn_anchor = MagicMock()
        fake_txn_anchor.to_dict = MagicMock(return_value={"id": "anchor_entry"})
        fake_txn_anchor.mempool = False
        fake_txn_anchor.transaction_signature = "anchor_entry"
        fake_txn_anchor.public_key_hash = "tip_pkh"

        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value={"public_key": "abc123"},
        ), patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new_callable=AsyncMock,
            return_value=fake_txn_anchor,
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

    async def test_empty_chain_authorizes_from_stored_tip(self):
        """Tip-only reconnect: empty ratchet_chain still auths if tip is on disk."""
        from bitcoin.wallet import P2PKHBitcoinAddress

        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)

        pub = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        conf_pub = "03fff97bd5755eeea420453a14355235d382f6472f8568a18b2f057a1460297556"
        sign_pkh = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(pub)))
        conf_pkh = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(conf_pub)))
        tip_txn = {
            "id": "tip-sig",
            "public_key": pub,
            "public_key_hash": sign_pkh,
            "prerotated_key_hash": conf_pkh,
            "prev_public_key_hash": "1Parent",
            "hash": "ab" * 32,
            "inputs": [],
            "outputs": [{"to": conf_pkh, "value": 0}],
            "fee": 0,
            "time": 1,
            "version": 7,
        }
        tip_doc = {
            "counter": 1,
            "branch_inception_public_key_hash": "1BranchRoot",
            "public_key_hash": sign_pkh,
            "prerotated_key_hash": conf_pkh,
            "public_key": pub,
            "txn": tip_txn,
        }

        async def _find_one(query, *args, **kwargs):
            if query.get("public_key_hash") == sign_pkh:
                return tip_doc
            if query.get("branch_inception_public_key_hash") == "1BranchRoot":
                return tip_doc
            return None

        rpc.config.mongo.async_db.key_event_log.find_one = AsyncMock(
            side_effect=_find_one
        )

        tip_txn_obj = MagicMock()
        tip_txn_obj.public_key_hash = sign_pkh
        tip_txn_obj.prerotated_key_hash = conf_pkh
        tip_txn_obj.public_key = pub
        tip_txn_obj.prev_public_key_hash = "1Parent"
        tip_txn_obj.transaction_signature = "tip-sig"
        tip_txn_obj.to_dict = MagicMock(return_value=tip_txn)
        ke = MagicMock()
        ke.txn = tip_txn_obj

        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value={"public_key": pub},
        ), patch(
            "yadacoin.core.transaction.Transaction.verify",
            new_callable=AsyncMock,
        ), patch(
            "yadacoin.core.transaction.Transaction.from_dict",
            return_value=tip_txn_obj,
        ), patch(
            "yadacoin.core.keyeventlog.KeyEvent",
            return_value=ke,
        ):
            result = await rpc._process_ratchet_auth(
                stream,
                ratchet_chain=[],
                ratchet_public_key=pub,
                confirming_public_key=conf_pub,
            )

        self.assertIsNotNone(result)
        rpc.remove_peer.assert_not_awaited()


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

    async def test_missing_input_does_not_remove_peer(self):
        """Unsynced UTXOs on ratchet entries must not abort auth."""
        from yadacoin.core.transaction import MissingInputTransactionException

        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc._request_peer_kel_resync = AsyncMock()

        fake_txn = MagicMock()
        fake_txn.public_key = (
            "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
        )
        fake_txn.public_key_hash = "addr0"
        fake_txn.prev_public_key_hash = "prev"
        fake_txn.prerotated_key_hash = "pre"
        fake_txn.transaction_signature = "sig"
        fake_txn.to_dict.return_value = {"id": "sig"}
        fake_txn.relationship = "peer-kel-branch"
        fake_txn.verify = AsyncMock(
            side_effect=MissingInputTransactionException("Input not found")
        )

        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "yadacoin.core.transaction.Transaction.from_dict",
            return_value=fake_txn,
        ), patch(
            "yadacoin.core.keyeventlog.is_branch_announcement",
            return_value=True,
        ):
            # tip matches signing key so auth can succeed past verify deferral
            tip_txn = MagicMock()
            tip_txn.public_key_hash = (
                "1BgGZ9tcN4rm9KBzDn7T2PLhf8L6bUj8f"  # addr of secp k*G
            )
            tip_txn.prerotated_key_hash = ""
            # Use real P2PKH of the test pubkey
            from bitcoin.wallet import P2PKHBitcoinAddress

            tip_txn.public_key_hash = str(
                P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(fake_txn.public_key))
            )
            kel_doc = {
                "counter": 1,
                "txn": {"id": "tip"},
                "branch_inception_public_key_hash": "addr0",
            }
            rpc.config.mongo.async_db.key_event_log.find_one = AsyncMock(
                return_value=kel_doc
            )
            rpc.config.mongo.async_db.key_event_log.replace_one = AsyncMock()
            with patch(
                "yadacoin.core.keyeventlog.KeyEvent",
                return_value=MagicMock(txn=tip_txn),
            ), patch(
                "yadacoin.core.transaction.Transaction.from_dict",
                side_effect=[fake_txn, tip_txn],
            ):
                result = await rpc._process_ratchet_auth(
                    stream,
                    ratchet_chain=[{"id": "sig"}],
                    ratchet_public_key=fake_txn.public_key,
                )

        # Must not disconnect solely for missing inputs
        for call in rpc.remove_peer.await_args_list:
            reason = (call.kwargs or {}).get("reason") or (
                call[1].get("reason") if len(call) > 1 else ""
            )
            self.assertNotIn("invalid txn", str(reason))


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
        rpc.config.kel_manager.get_peer_auth_keys = AsyncMock(
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
        req = next(p for m, p in written_calls if m == "request_sig")
        self.assertTrue(req.get("auth_challenge"))
        self.assertEqual(len(req["auth_challenge"]), 32)  # secrets.token_hex(16)
        self.assertIn("server_ecdh_pub", req)
        self.assertIn("server_kel_tip_pkh", req)

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
        rpc.config.kel_manager.get_peer_auth_keys = AsyncMock(
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
        self.assertTrue(getattr(stream, "_auth_challenge", ""))
        self.assertTrue(getattr(stream, "_auth_transcript", ""))
        self.assertIn(stream._auth_challenge, stream._auth_transcript)

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
        rpc.config.kel_manager.get_peer_auth_keys = AsyncMock(
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
                body={
                    "params": {
                        "ecdh_public_key": _ecdh_pub,
                        "identity_announcement": _make_config().inception.to_dict(),
                    }
                },
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
                body={
                    "params": {
                        "ecdh_public_key": _ecdh_pub,
                        "identity_announcement": _make_config().inception.to_dict(),
                    }
                },
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
            body={
                "params": {
                    "ecdh_public_key": _ecdh_pub,
                    "identity_announcement": _make_config().inception.to_dict(),
                }
            },
            stream=stream,
        )

        self.assertIsNone(stream.session_cipher)


# ─── request_sig ─────────────────────────────────────────────────────────────


class TestAuthTranscript(unittest.TestCase):
    def test_field_order_stable(self):
        from yadacoin.tcpsocket.node import NodeRPC

        t = NodeRPC._auth_transcript("c", "s", "ct", "st", "ch")
        self.assertEqual(t, "c|s|ct|st|ch")
        self.assertEqual(
            NodeRPC._auth_transcript("", "", "", "", "ch"),
            "||||ch",
        )


class TestRequestSig(AsyncTestCase):
    """Client-side request_sig handler."""

    def _body(
        self,
        server_signed,
        ratchet_pub,
        server_kel_tip_pkh="",
        server_ecdh_pub="serverecdh",
        client_kel_tip_pkh="",
        auth_challenge="deadbeefcafebabe0123456789abcdef",
        **extras,
    ):
        p = {
            "server_signed": server_signed,
            "ratchet_public_key": ratchet_pub,
            "server_kel_tip_pkh": server_kel_tip_pkh,
            "server_ecdh_pub": server_ecdh_pub,
            "client_kel_tip_pkh": client_kel_tip_pkh,
            "auth_challenge": auth_challenge,
            "ratchet_chain": [],
            "latest_ratchet_pkh": "",
        }
        p.update(extras)
        return {"params": p}

    async def test_missing_server_signed_removes_peer(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)

        await rpc.request_sig(body={"params": {}}, stream=stream)

        rpc.remove_peer.assert_awaited_once()

    async def test_missing_auth_challenge_removes_peer(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        stream._ecdh_pub_sent = "clientecdh"

        _auth_priv, _auth_pub = _real_keys()
        body = self._body(
            server_signed="c2ln",
            ratchet_pub=_auth_pub,
            auth_challenge="",
        )
        await rpc.request_sig(body=body, stream=stream)
        rpc.remove_peer.assert_awaited_once()
        reason = rpc.remove_peer.call_args[1].get("reason", "")
        self.assertIn("auth challenge", reason)

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
        rpc.config.kel_manager.get_peer_auth_keys = AsyncMock(
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
        server_ecdh_pub = "serverecdh"
        challenge = "deadbeefcafebabe0123456789abcdef"
        nonce = _auth_transcript(
            _client_ecdh_pub, server_ecdh_pub, "", server_kel_tip_pkh, challenge
        )
        valid_sig = _real_sign(nonce, _auth_priv)

        body = self._body(
            server_signed=valid_sig,
            ratchet_pub=_auth_pub,
            server_kel_tip_pkh=server_kel_tip_pkh,
            server_ecdh_pub=server_ecdh_pub,
            auth_challenge=challenge,
        )

        # _process_ratchet_auth returns success tuple
        rpc._process_ratchet_auth = AsyncMock(
            return_value=(_auth_pub, True, "ratchet", 1)
        )

        rpc.config.kel_manager.advance_peer_auth_ratchet = AsyncMock(
            return_value=(_auth_priv, _auth_pub, None, None, "tpkh", False)
        )
        rpc.config.kel_manager.get_peer_auth_keys = AsyncMock(
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

        server_ecdh_pub = "serverecdh"
        challenge = "deadbeefcafebabe0123456789abcdef"
        nonce = _auth_transcript(_client_ecdh_pub, server_ecdh_pub, "", "", challenge)
        valid_sig = _real_sign(nonce, _auth_priv)

        body = self._body(
            server_signed=valid_sig,
            ratchet_pub=_auth_pub,
            server_ecdh_pub=server_ecdh_pub,
            auth_challenge=challenge,
        )

        rpc._process_ratchet_auth = AsyncMock(return_value=None)

        rpc.config.kel_manager.advance_peer_auth_ratchet = AsyncMock(
            return_value=(_auth_priv, _auth_pub, None, None, "tpkh", False)
        )
        rpc.config.kel_manager.get_peer_auth_keys = AsyncMock(
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

    def _prime_stream_auth(
        self,
        stream,
        client_ecdh="clientecdh",
        server_ecdh="serverecdh",
        client_tip="",
        server_tip="",
        challenge="deadbeefcafebabe0123456789abcdef",
    ):
        stream._peer_ecdh_pub = client_ecdh
        stream._server_ecdh_pub = server_ecdh
        stream._client_kel_tip_pkh_expected = client_tip
        stream._server_kel_tip_pkh = server_tip
        stream._auth_challenge = challenge
        stream._auth_transcript = _auth_transcript(
            client_ecdh, server_ecdh, client_tip, server_tip, challenge
        )
        return stream._auth_transcript

    async def test_invalid_client_sig_removes_peer(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)

        _auth_priv, _auth_pub = _real_keys()
        _other_priv, _other_pub = _real_keys()

        self._prime_stream_auth(stream)
        bad_sig = _real_sign("wrong transcript", _other_priv)
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
        rpc.send_mempool = AsyncMock()

        _auth_priv, _auth_pub = _real_keys()

        transcript = self._prime_stream_auth(stream)
        valid_sig = _real_sign(transcript, _auth_priv)

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
        # Must authorize the key that signed the transcript
        self.assertEqual(rpc._process_ratchet_auth.call_args[0][2], _auth_pub)

    async def test_ratchet_auth_failure_does_not_authenticate(self):
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.send_block_to_peer = AsyncMock()
        rpc.get_next_block = AsyncMock()

        _auth_priv, _auth_pub = _real_keys()

        transcript = self._prime_stream_auth(stream)
        valid_sig = _real_sign(transcript, _auth_priv)

        stream._connect_ratchet_chain = []
        stream._connect_latest_ratchet_pkh = ""

        body = self._body(client_signed=valid_sig, ratchet_pub=_auth_pub)

        rpc._process_ratchet_auth = AsyncMock(return_value=None)

        await rpc.sig_response(body=body, stream=stream)

        self.assertFalse(stream.peer.authenticated)
        rpc.send_block_to_peer.assert_not_awaited()

    async def test_merges_connect_and_response_ratchet_chains(self):
        """sig_response must merge connect chain + response delta so the
        post-connect advance tip is authorized (not connect tip alone)."""
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.send_block_to_peer = AsyncMock()
        rpc.get_next_block = AsyncMock()
        rpc.send_mempool = AsyncMock()

        _auth_priv, _auth_pub = _real_keys()

        transcript = self._prime_stream_auth(stream)
        valid_sig = _real_sign(transcript, _auth_priv)

        stored_chain = [{"id": "stored_txn"}]
        stream._connect_ratchet_chain = stored_chain
        stream._connect_latest_ratchet_pkh = "tipkh"

        body = self._body(
            client_signed=valid_sig,
            ratchet_pub=_auth_pub,
            ratchet_chain=[{"id": "response_txn"}],
        )

        rpc._process_ratchet_auth = AsyncMock(
            return_value=(_auth_pub, True, "ratchet", 1)
        )

        await rpc.sig_response(body=body, stream=stream)

        call_kwargs = rpc._process_ratchet_auth.call_args
        passed_chain = call_kwargs[0][1]
        self.assertEqual(passed_chain, [{"id": "stored_txn"}, {"id": "response_txn"}])

    async def test_falls_back_to_sig_response_chain_on_first_contact(self):
        """When stream._connect_ratchet_chain is empty (first contact),
        sig_response must use the ratchet_chain sent by the client
        in this very message."""
        rpc = _make_rpc()
        stream = _make_stream()
        rpc.remove_peer = AsyncMock(return_value=None)
        rpc.send_block_to_peer = AsyncMock()
        rpc.get_next_block = AsyncMock()
        rpc.send_mempool = AsyncMock()

        _auth_priv, _auth_pub = _real_keys()

        transcript = self._prime_stream_auth(stream)
        valid_sig = _real_sign(transcript, _auth_priv)

        # First contact: connect sent an empty ratchet_chain
        stream._connect_ratchet_chain = []
        stream._connect_latest_ratchet_pkh = ""

        response_chain = [{"id": "first_branch_txn"}]
        body = self._body(
            client_signed=valid_sig,
            ratchet_pub=_auth_pub,
            ratchet_chain=response_chain,
        )

        rpc._process_ratchet_auth = AsyncMock(
            return_value=(_auth_pub, True, "ratchet", 1)
        )

        await rpc.sig_response(body=body, stream=stream)

        call_kwargs = rpc._process_ratchet_auth.call_args
        passed_chain = call_kwargs[0][1]
        self.assertEqual(passed_chain, response_chain)


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


class TestPeerBranchRatchetDelta(AsyncTestCase):
    """Hash-link deltas must include the signing tip despite bad counters."""

    async def test_delta_includes_tip_when_counter_corrupted(self):
        rpc = _make_rpc()
        branch = "branch0"
        # tip has low counter; stale junk has huge counter and different pkh
        docs = [
            {
                "id": "root",
                "counter": 0,
                "public_key_hash": "A",
                "prerotated_key_hash": "B",
                "txn": {
                    "id": "root",
                    "public_key_hash": "A",
                    "prerotated_key_hash": "B",
                    "prev_public_key_hash": "",
                },
            },
            {
                "id": "mid",
                "counter": 1,
                "public_key_hash": "B",
                "prerotated_key_hash": "C",
                "txn": {
                    "id": "mid",
                    "public_key_hash": "B",
                    "prerotated_key_hash": "C",
                    "prev_public_key_hash": "A",
                },
            },
            {
                "id": "tip",
                "counter": 2,
                "public_key_hash": "C",
                "prerotated_key_hash": "D",
                "txn": {
                    "id": "tip",
                    "public_key_hash": "C",
                    "prerotated_key_hash": "D",
                    "prev_public_key_hash": "B",
                },
            },
            {
                "id": "junk",
                "counter": 99999,
                "public_key_hash": "Z",
                "prerotated_key_hash": "Y",
                "txn": {
                    "id": "junk",
                    "public_key_hash": "Z",
                    "prerotated_key_hash": "Y",
                    "prev_public_key_hash": "X",
                },
            },
        ]
        by_pkh = {}
        for d in docs:
            by_pkh.setdefault(d["public_key_hash"], []).append(d)

        class _Cursor:
            def __init__(self, items):
                self._items = items

            async def to_list(self, length=None):
                return list(self._items)

        async def _find_one(query, *args, **kwargs):
            pkh = query.get("public_key_hash")
            if pkh and pkh in by_pkh:
                return max(by_pkh[pkh], key=lambda x: x.get("counter") or 0)
            if query.get("counter") == {"$gt": 0} or (
                isinstance(query.get("counter"), dict)
                and "$gt" in (query.get("counter") or {})
            ):
                active = [d for d in docs if d.get("counter", 0) > 0]
                if active:
                    return max(active, key=lambda x: x.get("counter") or 0)
            return None

        def _find(query, *args, **kwargs):
            pkh = query.get("public_key_hash")
            if pkh and pkh in by_pkh:
                return _Cursor(by_pkh[pkh])
            return _Cursor([])

        rpc.config.mongo.async_db.key_event_log.find_one = AsyncMock(
            side_effect=_find_one
        )
        rpc.config.mongo.async_db.key_event_log.find = MagicMock(side_effect=_find)
        rpc.config.kel_manager._peer_branch_tip_by_hash_link = AsyncMock(
            return_value=docs[2]
        )

        # Epoch wire chain excludes permanent bridge (counter 0).
        full = await rpc._peer_branch_ratchet_delta(branch, tip_pkh="C")
        self.assertEqual([t["id"] for t in full], ["mid", "tip"])

        delta = await rpc._peer_branch_ratchet_delta(branch, after_pkh="B", tip_pkh="C")
        self.assertEqual([t["id"] for t in delta], ["tip"])

        # Caps + meta: truncated gap reports eof=False
        short, eof, tip = await rpc._peer_branch_ratchet_delta(
            branch, tip_pkh="C", limit=1, return_meta=True
        )
        self.assertEqual([t["id"] for t in short], ["tip"])
        self.assertFalse(eof)
        self.assertEqual(tip, "C")

        # Already at tip → empty delta, eof
        empty, eof2, _ = await rpc._peer_branch_ratchet_delta(
            branch, after_pkh="C", tip_pkh="C", return_meta=True
        )
        self.assertEqual(empty, [])
        self.assertTrue(eof2)


class TestPeerBranchHandshakePayload(AsyncTestCase):
    """Epoch reroot wire helpers: announce + delta reset + remote GC."""

    def _rpc(self):
        from yadacoin.tcpsocket.node import NodeRPC

        return NodeRPC()

    async def test_branch_doc_helpers(self):
        from yadacoin.tcpsocket.node import NodeRPC

        self.assertEqual(NodeRPC._branch_doc_pkh(None), "")
        self.assertEqual(
            NodeRPC._branch_doc_pkh({"txn": {"public_key_hash": "T"}}), "T"
        )
        self.assertEqual(NodeRPC._branch_doc_pre({}), "")
        self.assertEqual(
            NodeRPC._branch_doc_pre({"txn": {"prerotated_key_hash": "P"}}), "P"
        )
        self.assertEqual(NodeRPC._branch_doc_prev({}), "")
        self.assertEqual(NodeRPC._branch_doc_prev({"prev_public_key_hash": "V"}), "V")
        self.assertEqual(NodeRPC._branch_doc_ctr({"counter": "x"}), 0)
        self.assertEqual(NodeRPC._branch_doc_ctr({"counter": 3}), 3)

    async def test_append_kel_txn_dedupes_and_skips_junk(self):
        rpc = self._rpc()
        out, seen = [], set()
        rpc._append_kel_txn(out, seen, None)
        rpc._append_kel_txn(out, seen, "not-a-dict")
        rpc._append_kel_txn(out, seen, {"id": "a", "x": 1})
        rpc._append_kel_txn(out, seen, {"id": "a", "x": 2})
        rpc._append_kel_txn(out, seen, {"hash": "h1", "y": 1})

        class _T:
            def to_dict(self):
                return {"id": "b", "z": 1}

        rpc._append_kel_txn(out, seen, _T())
        self.assertEqual(len(out), 3)
        self.assertEqual({d.get("id") or d.get("hash") for d in out}, {"a", "h1", "b"})

    async def test_handshake_payload_force_announce_on_stale_tip(self):
        rpc = self._rpc()
        cfg = _make_config()
        rpc.config = cfg
        bridge_txn = {"id": "bridge1", "public_key_hash": "BR"}
        ann = {"id": "ann1"}
        conf = {"id": "conf1"}
        tip_txn = {"id": "tip1", "public_key_hash": "TIP"}
        cfg.kel_manager.peer_branch_wire_bundle = AsyncMock(
            return_value={
                "branch_inception_pkh": "BR",
                "branch_generation": 2,
                "supersedes_branch_inception_pkh": "OLD",
                "announcement_txn": ann,
                "confirming_txn": conf,
                "bridge_txn": bridge_txn,
            }
        )
        cfg.kel_manager.peer_branch_inception_public_key_hash = AsyncMock(
            return_value="BR"
        )
        cfg.kel_manager.peer_branch_contains_pkh = AsyncMock(return_value=False)
        rpc._peer_branch_ratchet_delta = AsyncMock(
            return_value=([tip_txn], True, "TIP")
        )
        rpc._get_kel_chain_for_peer = AsyncMock(return_value=[])

        hs = await rpc._peer_branch_handshake_payload(
            "peer_key",
            is_new_branch=False,
            peer_after_pkh="STALE_TIP",
            tip_pkh="TIP",
            peer_latest_kel_pkh="KEL",
            peer_reported_branch_inception="OLD",
        )
        self.assertTrue(hs["force_announce"])
        self.assertEqual(hs["branch_generation"], 2)
        self.assertEqual(hs["supersedes_branch_inception_pkh"], "OLD")
        ids = [t.get("id") for t in hs["ratchet_chain"]]
        self.assertIn("bridge1", ids)
        kel_ids = [t.get("id") for t in hs["kel_chain"]]
        self.assertIn("ann1", kel_ids)
        self.assertIn("conf1", kel_ids)
        # stale after → empty after_pkh used for delta
        rpc._peer_branch_ratchet_delta.assert_called()
        call_kw = rpc._peer_branch_ratchet_delta.call_args
        self.assertEqual(
            call_kw.kwargs.get("after_pkh") or call_kw[1].get("after_pkh"), ""
        )

    async def test_handshake_payload_tip_proof_when_delta_empty(self):
        rpc = self._rpc()
        cfg = _make_config()
        rpc.config = cfg
        cfg.kel_manager.peer_branch_wire_bundle = AsyncMock(
            return_value={
                "branch_inception_pkh": "BR",
                "branch_generation": 0,
                "supersedes_branch_inception_pkh": "",
                "announcement_txn": None,
                "confirming_txn": None,
                "bridge_txn": None,
            }
        )
        cfg.kel_manager.peer_branch_contains_pkh = AsyncMock(return_value=True)
        tip = {"id": "only_tip", "public_key_hash": "T"}
        rpc._peer_branch_ratchet_delta = AsyncMock(
            side_effect=[
                ([], True, "T"),
                ([tip], True, "T"),
            ]
        )
        rpc._get_kel_chain_for_peer = AsyncMock(return_value=[])
        hs = await rpc._peer_branch_handshake_payload(
            "pk",
            is_new_branch=False,
            peer_after_pkh="T",
            tip_pkh="T",
        )
        # after_pkh == tip and contains → no force; empty delta may still tip-proof
        self.assertTrue(any(t.get("id") == "only_tip" for t in hs["ratchet_chain"]))

    async def test_note_remote_branch_epoch_gc(self):
        rpc = self._rpc()
        cfg = _make_config()
        rpc.config = cfg
        stream = MagicMock()
        kel = cfg.mongo.async_db.key_event_log
        kel.update_many = AsyncMock()
        kel.delete_many = AsyncMock()
        await rpc._note_remote_branch_epoch(
            stream,
            branch_inception_pkh="NEW",
            branch_generation="3",
            supersedes_branch_inception_pkh="OLD",
        )
        self.assertEqual(stream._peer_branch_inception_pkh, "NEW")
        self.assertEqual(stream._peer_branch_generation, 3)
        kel.update_many.assert_awaited()
        kel.delete_many.assert_awaited()

        # bad generation + GC exception soft-fail
        kel.update_many = AsyncMock(side_effect=RuntimeError("x"))
        await rpc._note_remote_branch_epoch(
            stream,
            branch_inception_pkh="N2",
            branch_generation=object(),
            supersedes_branch_inception_pkh="OLD2",
        )
        self.assertEqual(stream._peer_branch_generation, 0)

    async def test_branch_sync_request_reroot_mismatch(self):
        rpc = self._rpc()
        cfg = _make_config()
        rpc.config = cfg
        stream = MagicMock()
        stream.peer = MagicMock()
        stream.peer.identity_announcement = "peer_ia"
        stream.peer.identity = MagicMock(username_signature="usig")
        stream.peer.host = "1.2.3.4"
        cfg.kel_manager.peer_branch_inception_public_key_hash = AsyncMock(
            return_value="OUR_BR"
        )
        cfg.kel_manager.peer_branch_wire_bundle = AsyncMock(
            return_value={
                "branch_inception_pkh": "OUR_BR",
                "branch_generation": 4,
                "supersedes_branch_inception_pkh": "THEIR_OLD",
                "bridge_txn": {"id": "br", "public_key_hash": "OUR_BR"},
                "announcement_txn": {"id": "ann"},
                "confirming_txn": {"id": "conf"},
            }
        )
        rpc.write_params = AsyncMock()
        body = {
            "params": {
                "branch_inception_pkh": "THEIR_OLD",
                "after_pkh": "X",
                "want_tip_pkh": "Y",
            }
        }
        await rpc.branch_sync_request(body, stream)
        rpc.write_params.assert_awaited()
        args = rpc.write_params.await_args
        self.assertEqual(args[0][1], "branch_sync_response")
        payload = args[0][2]
        self.assertEqual(payload.get("error"), "branch_rerooted")
        self.assertEqual(payload.get("branch_inception_pkh"), "OUR_BR")
        self.assertTrue(payload.get("kel_chain"))

    async def test_branch_sync_response_reroot_accepts_kel(self):
        rpc = self._rpc()
        cfg = _make_config()
        rpc.config = cfg
        stream = MagicMock()
        rpc._accept_peer_kel_chain = AsyncMock()
        rpc._note_remote_branch_epoch = AsyncMock()
        rpc._ingest_branch_sync_entries = AsyncMock()
        body = {
            "params": {
                "error": "branch_rerooted",
                "branch_inception_pkh": "NEW",
                "branch_generation": 5,
                "supersedes_branch_inception_pkh": "OLD",
                "kel_chain": [{"id": "ann"}],
                "entries": [],
                "eof": True,
            }
        }
        await rpc.branch_sync_response(body, stream)
        rpc._accept_peer_kel_chain.assert_awaited()
        rpc._note_remote_branch_epoch.assert_awaited()

        # hard error path
        rpc._accept_peer_kel_chain.reset_mock()
        await rpc.branch_sync_response({"params": {"error": "nope"}}, stream)
        rpc._accept_peer_kel_chain.assert_not_awaited()

        # reroot kel accept failure soft
        rpc._accept_peer_kel_chain = AsyncMock(side_effect=RuntimeError("kel"))
        await rpc.branch_sync_response(
            {
                "params": {
                    "error": "branch_rerooted",
                    "kel_chain": [{"id": "x"}],
                    "eof": True,
                }
            },
            stream,
        )

        # continue chunk request when not eof
        rpc.write_params = AsyncMock()
        rpc._ingest_branch_sync_entries = AsyncMock()
        await rpc.branch_sync_response(
            {
                "params": {
                    "entries": [{"public_key_hash": "A"}],
                    "eof": False,
                    "next_after_pkh": "",
                    "branch_inception_pkh": "BR",
                    "tip_pkh": "T",
                }
            },
            stream,
        )
        rpc.write_params.assert_awaited()

    async def test_branch_sync_request_normal_path(self):
        rpc = self._rpc()
        cfg = _make_config()
        rpc.config = cfg
        stream = MagicMock()
        stream.peer = MagicMock()
        stream.peer.identity_announcement = "ia"
        stream.peer.identity = None
        cfg.kel_manager.peer_branch_inception_public_key_hash = AsyncMock(
            return_value="BR"
        )
        rpc._peer_branch_ratchet_delta = AsyncMock(
            return_value=([{"id": "e1", "public_key_hash": "P"}], True, "TIP")
        )
        rpc.write_params = AsyncMock()
        await rpc.branch_sync_request(
            {"params": {"branch_inception_pkh": "BR", "limit": "bad"}}, stream
        )
        payload = rpc.write_params.await_args[0][2]
        self.assertEqual(payload["entries"][0]["id"], "e1")
        self.assertEqual(payload["next_after_pkh"], "P")

        # empty branch_inception → use ours
        rpc.write_params.reset_mock()
        await rpc.branch_sync_request({"params": {}}, stream)
        self.assertEqual(
            rpc.write_params.await_args[0][2]["branch_inception_pkh"], "BR"
        )

    async def test_peer_branch_doc_walk_helpers(self):
        rpc = self._rpc()
        cfg = _make_config()
        rpc.config = cfg

        class _Cur:
            def __init__(self, items):
                self._items = items

            async def to_list(self, length=None):
                return list(self._items)

        parent = {
            "public_key_hash": "A",
            "prerotated_key_hash": "B",
            "counter": 1,
            "txn": {
                "public_key_hash": "A",
                "prerotated_key_hash": "B",
                "prev_public_key_hash": "",
            },
        }
        child = {
            "public_key_hash": "B",
            "prerotated_key_hash": "C",
            "counter": 2,
            "txn": {
                "public_key_hash": "B",
                "prerotated_key_hash": "C",
                "prev_public_key_hash": "A",
            },
        }
        kel = cfg.mongo.async_db.key_event_log
        kel.find = MagicMock(return_value=_Cur([parent]))
        got = await rpc._peer_branch_parent_doc("BR", child)
        self.assertEqual(got["public_key_hash"], "A")

        kel.find = MagicMock(return_value=_Cur([]))
        self.assertIsNone(await rpc._peer_branch_parent_doc("BR", child))
        self.assertIsNone(
            await rpc._peer_branch_parent_doc(
                "BR", {"txn": {"prev_public_key_hash": ""}}
            )
        )

        kel.find = MagicMock(return_value=_Cur([child]))
        got_c = await rpc._peer_branch_child_doc("BR", parent)
        self.assertEqual(got_c["public_key_hash"], "B")
        kel.find = MagicMock(return_value=_Cur([]))
        self.assertIsNone(await rpc._peer_branch_child_doc("BR", parent))
        self.assertIsNone(
            await rpc._peer_branch_child_doc("BR", {"prerotated_key_hash": ""})
        )

        self.assertIsNone(await rpc._peer_branch_doc_by_pkh("", "x"))
        self.assertIsNone(await rpc._peer_branch_doc_by_pkh("b", ""))

        # delta empty branch / no tip
        self.assertEqual(await rpc._peer_branch_ratchet_delta(""), [])
        empty_m = await rpc._peer_branch_ratchet_delta("", return_meta=True)
        self.assertEqual(empty_m, ([], True, ""))
        cfg.kel_manager._peer_branch_tip_by_hash_link = AsyncMock(return_value=None)
        self.assertEqual(
            await rpc._peer_branch_ratchet_delta("BR", tip_pkh=""),
            [],
        )
        none_m = await rpc._peer_branch_ratchet_delta("BR", return_meta=True)
        self.assertEqual(none_m, ([], True, ""))

        # tip-only proof when walk empty
        tip_doc = {
            "counter": 1,
            "public_key_hash": "T",
            "txn": {"id": "tip", "public_key_hash": "T", "prev_public_key_hash": "BR"},
        }
        cfg.kel_manager._peer_branch_tip_by_hash_link = AsyncMock(return_value=tip_doc)
        kel.find_one = AsyncMock(return_value=None)
        rpc._peer_branch_parent_doc = AsyncMock(return_value=None)
        out = await rpc._peer_branch_ratchet_delta("BR", tip_pkh="T")
        self.assertEqual(out[0].get("id"), "tip")

        # parent/child max(cands) — restore real methods (not AsyncMock stubs)
        from yadacoin.tcpsocket.node import NodeRPC as _NR

        rpc._peer_branch_parent_doc = _NR._peer_branch_parent_doc.__get__(rpc, _NR)
        rpc._peer_branch_child_doc = _NR._peer_branch_child_doc.__get__(rpc, _NR)
        lo = {
            "public_key_hash": "A",
            "prerotated_key_hash": "ZZ",
            "counter": 1,
            "txn": {"public_key_hash": "A", "prerotated_key_hash": "ZZ"},
        }
        hi = {
            "public_key_hash": "A",
            "prerotated_key_hash": "YY",
            "counter": 9,
            "txn": {"public_key_hash": "A", "prerotated_key_hash": "YY"},
        }
        kel.find = MagicMock(return_value=_Cur([lo, hi]))
        child = {
            "public_key_hash": "B",
            "txn": {"prev_public_key_hash": "A", "public_key_hash": "B"},
        }
        got = await rpc._peer_branch_parent_doc("BR", child)
        self.assertEqual(got["counter"], 9)
        parent = {
            "public_key_hash": "A",
            "prerotated_key_hash": "B",
            "txn": {"public_key_hash": "A", "prerotated_key_hash": "B"},
        }
        c_lo = {
            "public_key_hash": "B",
            "counter": 1,
            "txn": {"prev_public_key_hash": "X", "public_key_hash": "B"},
        }
        c_hi = {
            "public_key_hash": "B",
            "counter": 5,
            "txn": {"prev_public_key_hash": "Y", "public_key_hash": "B"},
        }
        kel.find = MagicMock(return_value=_Cur([c_lo, c_hi]))
        got_c = await rpc._peer_branch_child_doc("BR", parent)
        self.assertEqual(got_c["counter"], 5)

        # delta walk cycle break + local/remote tip helpers
        mid = {
            "id": "mid",
            "counter": 2,
            "public_key_hash": "M",
            "txn": {"id": "mid", "public_key_hash": "M", "prev_public_key_hash": "A"},
        }
        tip2 = {
            "id": "tip2",
            "counter": 3,
            "public_key_hash": "T2",
            "txn": {"id": "tip2", "public_key_hash": "T2", "prev_public_key_hash": "M"},
        }
        cfg.kel_manager._peer_branch_tip_by_hash_link = AsyncMock(return_value=tip2)

        async def parent_cycle(br, cur):
            if cur is tip2 or (isinstance(cur, dict) and cur.get("id") == "tip2"):
                return mid
            if cur is mid or (isinstance(cur, dict) and cur.get("id") == "mid"):
                return mid  # same id → seen break
            return None

        rpc._peer_branch_parent_doc = parent_cycle
        rpc._peer_branch_doc_by_pkh = AsyncMock(return_value=None)
        walked = await rpc._peer_branch_ratchet_delta("BR", tip_pkh="T2", limit=10)
        self.assertTrue(any(t.get("id") == "tip2" for t in walked))

        cfg.kel_manager.peer_branch_inception_public_key_hash = AsyncMock(
            return_value=""
        )
        self.assertEqual(await rpc._local_peer_branch_tip_pkh(""), "")
        self.assertEqual(await rpc._local_peer_branch_tip_pkh("pk"), "")
        cfg.kel_manager.peer_branch_inception_public_key_hash = AsyncMock(
            return_value="BR"
        )
        cfg.kel_manager._peer_branch_tip_by_hash_link = AsyncMock(return_value=None)
        self.assertEqual(await rpc._local_peer_branch_tip_pkh("pk"), "")
        cfg.kel_manager._peer_branch_tip_by_hash_link = AsyncMock(
            return_value={"public_key_hash": "LT"}
        )
        self.assertEqual(await rpc._local_peer_branch_tip_pkh("pk"), "LT")

        self.assertEqual(await rpc._stored_remote_branch_tip_pkh(""), "")
        kel.find_one = AsyncMock(return_value=None)
        self.assertEqual(await rpc._stored_remote_branch_tip_pkh("pk"), "")
        kel.find_one = AsyncMock(return_value={"public_key_hash": "RT"})
        self.assertEqual(await rpc._stored_remote_branch_tip_pkh("pk"), "RT")

    async def test_ingest_branch_sync_entries(self):
        rpc = self._rpc()
        cfg = _make_config()
        rpc.config = cfg
        stream = MagicMock()
        stream.peer = MagicMock()
        stream.peer.identity_announcement = "ia"
        stream.peer.identity = None

        # empty / junk
        await rpc._ingest_branch_sync_entries(stream, [])
        await rpc._ingest_branch_sync_entries(stream, ["x", 1])

        mock_txn = MagicMock()
        mock_txn.verify = AsyncMock()
        mock_txn.transaction_signature = "sig1"
        mock_txn.public_key = "pub"
        mock_txn.public_key_hash = "PKH"
        mock_txn.prerotated_key_hash = "PRE"
        mock_txn.prev_public_key_hash = "PREV"
        mock_txn.to_dict = MagicMock(return_value={"id": "sig1"})

        with patch(
            "yadacoin.core.transaction.Transaction.from_dict",
            return_value=mock_txn,
        ):
            kel = cfg.mongo.async_db.key_event_log
            kel.find_one = AsyncMock(return_value=None)
            kel.replace_one = AsyncMock()
            await rpc._ingest_branch_sync_entries(
                stream, [{"id": "sig1", "public_key_hash": "PKH"}]
            )
            kel.replace_one.assert_awaited()

            # already stored skips write — enough find_one returns
            kel.replace_one.reset_mock()
            kel.find_one = AsyncMock(return_value={"id": "sig1", "counter": 3})
            await rpc._ingest_branch_sync_entries(
                stream, [{"id": "sig1", "public_key_hash": "PKH"}]
            )
            kel.replace_one.assert_not_awaited()

            # verify hard failure aborts
            mock_txn.verify = AsyncMock(side_effect=RuntimeError("bad"))
            kel.find_one = AsyncMock(return_value=None)
            kel.replace_one.reset_mock()
            await rpc._ingest_branch_sync_entries(
                stream, [{"id": "sig1", "public_key_hash": "PKH"}]
            )
            kel.replace_one.assert_not_awaited()

        # parse error path
        with patch(
            "yadacoin.core.transaction.Transaction.from_dict",
            side_effect=ValueError("nope"),
        ):
            await rpc._ingest_branch_sync_entries(stream, [{"id": "bad"}])

        # branch_sync_response: no next_after and no entries → return
        rpc.write_params = AsyncMock()
        await rpc.branch_sync_response(
            {"params": {"entries": [], "eof": False, "next_after_pkh": ""}},
            stream,
        )
        rpc.write_params.assert_not_awaited()

        # deferred KEL verify exceptions are ignored (continue ingest)
        from yadacoin.core.transaction import MissingInputTransactionException

        mock_txn2 = MagicMock()
        mock_txn2.verify = AsyncMock(
            side_effect=MissingInputTransactionException("later")
        )
        mock_txn2.transaction_signature = "sig2"
        mock_txn2.public_key = "pub"
        mock_txn2.public_key_hash = "PKH2"
        mock_txn2.prerotated_key_hash = "PRE2"
        mock_txn2.prev_public_key_hash = ""
        mock_txn2.to_dict = MagicMock(return_value={"id": "sig2"})
        with patch(
            "yadacoin.core.transaction.Transaction.from_dict",
            return_value=mock_txn2,
        ):
            kel = cfg.mongo.async_db.key_event_log
            kel.find_one = AsyncMock(return_value=None)
            kel.replace_one = AsyncMock()
            await rpc._ingest_branch_sync_entries(
                stream, [{"id": "sig2", "public_key_hash": "PKH2"}]
            )
            kel.replace_one.assert_awaited()

    async def test_delta_bridge_and_tip_proof_edges(self):
        rpc = self._rpc()
        cfg = _make_config()
        rpc.config = cfg
        bridge = {
            "id": "br0",
            "counter": 0,
            "public_key_hash": "BR",
            "txn": {"id": "br0", "public_key_hash": "BR", "prev_public_key_hash": ""},
        }
        tip = {
            "id": "tip",
            "counter": 1,
            "public_key_hash": "T",
            "txn": {"id": "tip", "public_key_hash": "T", "prev_public_key_hash": "BR"},
        }
        cfg.kel_manager._peer_branch_tip_by_hash_link = AsyncMock(return_value=tip)
        rpc._peer_branch_doc_by_pkh = AsyncMock(return_value=None)

        # walk hits bridge (counter 0) and stops; tip-proof still emitted
        async def parent_to_bridge(br, cur):
            if cur is tip or (isinstance(cur, dict) and cur.get("id") == "tip"):
                return bridge
            return None

        rpc._peer_branch_parent_doc = parent_to_bridge
        out, eof, _ = await rpc._peer_branch_ratchet_delta(
            "BR", tip_pkh="T", return_meta=True
        )
        self.assertTrue(any(t.get("id") == "tip" for t in out))
        self.assertTrue(eof)

        # tip is bridge (counter 0): walk breaks at 957; tip-proof fills chain
        cfg.kel_manager._peer_branch_tip_by_hash_link = AsyncMock(return_value=bridge)
        rpc._peer_branch_parent_doc = AsyncMock(return_value=None)
        out2, eof2, _ = await rpc._peer_branch_ratchet_delta(
            "BR", tip_pkh="BR", return_meta=True
        )
        self.assertEqual(out2[0].get("id"), "br0")
        self.assertTrue(eof2)

        # after_pkh already at tip → empty (no tip-proof)
        out3 = await rpc._peer_branch_ratchet_delta("BR", after_pkh="BR", tip_pkh="BR")
        self.assertEqual(out3, [])

        # after_pkh matches bridge pkh while walking from tip (skip early break)
        tip_b = {
            "id": "t3",
            "counter": 1,
            "public_key_hash": "T3",
            "txn": {
                "id": "t3",
                "public_key_hash": "T3",
                "prev_public_key_hash": "BR",
            },
        }
        cfg.kel_manager._peer_branch_tip_by_hash_link = AsyncMock(return_value=tip_b)

        async def parent_bridge(br, cur):
            return bridge

        rpc._peer_branch_parent_doc = parent_bridge
        # Force walk onto bridge as *cur* by making tip counter 0 after first step
        # Start tip as bridge with after_pkh=BR so 954 condition is false then 959 breaks
        cfg.kel_manager._peer_branch_tip_by_hash_link = AsyncMock(return_value=bridge)
        out4 = await rpc._peer_branch_ratchet_delta(
            "BR", after_pkh="BR", tip_pkh="BR", return_meta=False
        )
        self.assertEqual(out4, [])


class TestAcceptPeerKelChainCoinbase(AsyncTestCase):
    """Coinbases must never enter mempool; classify via containing block."""

    async def _coinbase_raw(self):
        from bitcoin.wallet import P2PKHBitcoinAddress

        from yadacoin.core.config import Config
        from yadacoin.core.transaction import Transaction

        pub = Config().public_key
        priv = Config().private_key
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(pub)))
        prerotated = "13kpmLEktnfyaahRvQ5385EzUBLYa9PU8d"
        txn = await Transaction.generate(
            public_key=pub,
            private_key=priv,
            coinbase=True,
            outputs=[{"to": prerotated, "value": 12.5}],
            prerotated_key_hash=prerotated,
            public_key_hash=address,
        )
        return txn, txn.to_dict(), pub, address, prerotated

    async def test_coinbase_shaped_without_block_not_stored(self):
        """Input-less value txn with no local block is treated as coinbase."""
        from yadacoin.core.transaction import Transaction

        rpc = _make_rpc()
        _txn, raw, _pub, _address, _pre = await self._coinbase_raw()
        loaded = Transaction.from_dict(raw)
        self.assertFalse(loaded.coinbase)

        await rpc._accept_peer_kel_chain([raw])

        mt = rpc.config.mongo.async_db.miner_transactions
        self.assertFalse(mt.bulk_write.await_count)
        self.assertFalse(mt.replace_one.await_count)

    async def test_onchain_coinbase_classified_via_block_not_stored(self):
        """Resolve containing block, classify as coinbase, skip mempool."""
        from yadacoin.core.block import Block
        from yadacoin.core.transaction import Transaction

        rpc = _make_rpc()
        txn, raw, pub, address, prerotated = await self._coinbase_raw()
        block_doc = {
            "index": 1,
            "hash": "abc",
            "public_key": pub,
            "prevHash": "0" * 64,
            "nonce": "1",
            "id": "sig",
            "merkleRoot": "0" * 64,
            "target": "f" * 64,
            "time": int(txn.time or 1),
            "version": 5,
            "transactions": [raw],
        }
        rpc.config.mongo.async_db.blocks.find_one = AsyncMock(return_value=block_doc)

        real_block = await Block.from_dict(block_doc)
        self.assertTrue(Block.is_coinbase(real_block, Transaction.from_dict(raw)))

        await rpc._accept_peer_kel_chain([raw])

        mt = rpc.config.mongo.async_db.miner_transactions
        self.assertFalse(mt.bulk_write.await_count)
        self.assertFalse(mt.replace_one.await_count)

    async def test_pending_non_coinbase_kel_is_cached_not_mempool(self):
        """Non-inception peer KEL rotations cache in key_event_log, not mempool."""
        from bitcoin.wallet import P2PKHBitcoinAddress

        from yadacoin.core.config import Config
        from yadacoin.core.transaction import Transaction

        rpc = _make_rpc()
        pub = Config().public_key
        priv = Config().private_key
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(pub)))
        prerotated = "13kpmLEktnfyaahRvQ5385EzUBLYa9PU8d"
        txn = await Transaction.generate(
            public_key=pub,
            private_key=priv,
            outputs=[{"to": prerotated, "value": 0}],
            prerotated_key_hash=prerotated,
            public_key_hash=address,
            prev_public_key_hash=address,
        )
        raw = txn.to_dict()
        self.assertFalse(Transaction.from_dict(raw).coinbase)

        await rpc._accept_peer_kel_chain([raw])

        mt = rpc.config.mongo.async_db.miner_transactions
        self.assertFalse(mt.bulk_write.await_count)
        self.assertFalse(mt.replace_one.await_count)
        kel = rpc.config.mongo.async_db.key_event_log
        self.assertTrue(kel.replace_one.await_count)

    async def test_peer_inception_goes_to_mempool(self):
        """Brand-new peer inception may enter mempool for on-chain announce."""
        from bitcoin.wallet import P2PKHBitcoinAddress

        from yadacoin.core.config import Config
        from yadacoin.core.transaction import Transaction

        rpc = _make_rpc()
        pub = Config().public_key
        priv = Config().private_key
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(pub)))
        prerotated = "13kpmLEktnfyaahRvQ5385EzUBLYa9PU8d"
        txn = await Transaction.generate(
            public_key=pub,
            private_key=priv,
            outputs=[{"to": prerotated, "value": 0}],
            prerotated_key_hash=prerotated,
            public_key_hash=address,
            prev_public_key_hash="",
        )
        raw = txn.to_dict()

        await rpc._accept_peer_kel_chain([raw])

        mt = rpc.config.mongo.async_db.miner_transactions
        self.assertTrue(mt.bulk_write.await_count or mt.replace_one.await_count)

    async def test_verify_keeps_cache_when_input_missing(self):
        """Unsynced chain context must not purge peer main-KEL cache."""
        from yadacoin.core.transaction import MissingInputTransactionException

        rpc = _make_rpc()
        txn = MagicMock()
        txn.transaction_signature = "sig-missing-input"
        txn.coinbase = False
        txn.prev_public_key_hash = "prev"
        txn.verify = AsyncMock(
            side_effect=MissingInputTransactionException("Input not found")
        )
        rpc._resolve_block_for_txn = AsyncMock(return_value=None)
        rpc._is_coinbase_shaped = MagicMock(return_value=False)
        rpc._purge_mempool_txn = AsyncMock()
        rpc._purge_peer_kel_cache_txn = AsyncMock()

        await rpc._verify_peer_kel_chain([txn])

        rpc._purge_mempool_txn.assert_not_awaited()
        rpc._purge_peer_kel_cache_txn.assert_not_awaited()
        txn.verify.assert_awaited()
        self.assertTrue(txn.verify.await_args.kwargs.get("check_kel"))


if __name__ == "__main__":
    unittest.main()
