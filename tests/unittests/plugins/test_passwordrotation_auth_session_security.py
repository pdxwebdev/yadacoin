"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import base64
import hashlib
import json
import time
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from coincurve import PrivateKey

from plugins.passwordrotation import auth_session as asess
from plugins.passwordrotation.handlers import (
    PasswordAuthSessionCreateHandler,
    PasswordAuthSessionGetHandler,
    PasswordAuthSessionPendingHandler,
    PasswordAuthSessionResultHandler,
)


class AsyncTestCase(IsolatedAsyncioTestCase):
    """Local async tests that do not need Mongo (unlike tests.test_setup)."""


def _handler(cls, *, body=None, args=None, headers=None):
    h = cls.__new__(cls)
    h.request = MagicMock()
    h.request.body = json.dumps(body or {}).encode("utf-8")
    h.request.headers = headers or {}
    h.request.remote_ip = "127.0.0.1"
    h.request.protocol = "http"
    h.request.host = "node.example"
    params = args or {}
    h.get_query_argument = MagicMock(
        side_effect=lambda name, default="": params.get(name, default)
    )
    h.get_argument = MagicMock(
        side_effect=lambda name, default="": params.get(name, default)
    )
    h.set_status = MagicMock()
    h.render_as_json = MagicMock()
    h.set_secure_cookie = MagicMock()
    h.clear_cookie = MagicMock()
    h.config = MagicMock()
    return h


class TestVerificationCodeFormat(AsyncTestCase):
    def test_codes_are_six_digits(self):
        for _ in range(20):
            self.assertRegex(asess.new_verification_code(), r"^[0-9]{6}$")

    def test_public_view_never_exposes_code(self):
        doc = {
            "session_id": "s1",
            "status": "pending",
            "action": "operator",
            "verification_code": "123456",
            "result_token": "rt",
            "rp_token": "rp",
        }
        view = asess.public_session_view(doc)
        self.assertNotIn("verification_code", view)
        self.assertNotIn("result_token", view)
        self.assertNotIn("rp_token", view)


class TestAuthSessionReadToken(AsyncTestCase):
    async def test_get_requires_rp_token(self):
        h = _handler(PasswordAuthSessionGetHandler, args={"rp_token": ""})
        doc = {
            "session_id": "s1",
            "status": "approved",
            "expires_at": time.time() + 100,
            "rp_token": "secret",
            "result": {"ok": True, "token": "operator-token"},
        }
        with patch.object(asess, "get_session", AsyncMock(return_value=doc)):
            await PasswordAuthSessionGetHandler.get(h, "s1")
        h.set_status.assert_called_with(404)
        h.render_as_json.assert_called_once()
        self.assertFalse(h.render_as_json.call_args[0][0].get("token"))

    async def test_get_wrong_token_returns_not_found(self):
        h = _handler(PasswordAuthSessionGetHandler, args={"rp_token": "wrong"})
        doc = {
            "session_id": "s1",
            "status": "approved",
            "expires_at": time.time() + 100,
            "rp_token": "secret",
            "result": {"ok": True, "token": "operator-token"},
        }
        with patch.object(asess, "get_session", AsyncMock(return_value=doc)):
            await PasswordAuthSessionGetHandler.get(h, "s1")
        h.set_status.assert_called_with(404)
        self.assertFalse(h.render_as_json.call_args[0][0].get("token"))

    async def test_get_valid_token_claims_once(self):
        doc = {
            "session_id": "s1",
            "status": "approved",
            "expires_at": time.time() + 100,
            "rp_token": "secret",
            "result": {"ok": True, "token": "operator-token", "operator_session": True},
        }
        h = _handler(PasswordAuthSessionGetHandler, args={"rp_token": "secret"})
        with patch.object(
            asess, "get_session", AsyncMock(return_value=dict(doc))
        ), patch.object(
            asess, "claim_session_result", AsyncMock(return_value=dict(doc))
        ):
            await PasswordAuthSessionGetHandler.get(h, "s1")
        first = h.render_as_json.call_args[0][0]
        self.assertEqual(first.get("token"), "operator-token")

        h2 = _handler(PasswordAuthSessionGetHandler, args={"rp_token": "secret"})
        with patch.object(
            asess, "get_session", AsyncMock(return_value=dict(doc))
        ), patch.object(asess, "claim_session_result", AsyncMock(return_value=None)):
            await PasswordAuthSessionGetHandler.get(h2, "s1")
        second = h2.render_as_json.call_args[0][0]
        self.assertNotIn("token", second)


class TestOperatorApprovalBinding(AsyncTestCase):
    async def test_operator_result_from_other_browser_rejected(self):
        h = _handler(
            PasswordAuthSessionResultHandler,
            body={
                "result_token": "secret",
                "ok": True,
                "action": "operator",
                "password_enc": "sealed",
            },
        )
        doc = {
            "session_id": "s1",
            "action": "operator",
            "bind_id": "bind-of-requester",
            "status": "pending",
            "expires_at": time.time() + 100,
            "result_token": "secret",
            "nonce": "n",
        }
        with patch.object(
            asess, "get_session", AsyncMock(return_value=doc)
        ), patch.object(
            asess, "peek_signin_bind", AsyncMock(return_value={"bind_id": "other"})
        ), patch.object(
            asess, "mark_result", AsyncMock()
        ) as mark:
            await PasswordAuthSessionResultHandler.post(h, "s1")
        h.set_status.assert_called_with(403)
        mark.assert_not_called()


class TestVerificationCode(AsyncTestCase):
    def _result_handler(self, body):
        return _handler(PasswordAuthSessionResultHandler, body=body)

    def _doc(self, code="123456"):
        return {
            "session_id": "s1",
            "action": "operator",
            "status": "pending",
            "expires_at": time.time() + 100,
            "result_token": "secret",
            "rp_token": "rp",
            "verification_code": code,
            "bind_id": "bind",
            "nonce": "n",
        }

    async def test_operator_approval_requires_code(self):
        h = self._result_handler(
            {"result_token": "secret", "ok": True, "action": "operator"}
        )
        with patch.object(
            asess, "get_session", AsyncMock(return_value=self._doc())
        ), patch.object(
            asess, "peek_signin_bind", AsyncMock(return_value=None)
        ), patch.object(
            asess, "mark_result", AsyncMock()
        ) as mark:
            await PasswordAuthSessionResultHandler.post(h, "s1")
        h.set_status.assert_called_with(403)
        mark.assert_not_called()

    async def test_operator_approval_rejects_wrong_code(self):
        h = self._result_handler(
            {
                "result_token": "secret",
                "ok": True,
                "action": "operator",
                "verification_code": "000000",
            }
        )
        with patch.object(
            asess, "get_session", AsyncMock(return_value=self._doc())
        ), patch.object(
            asess, "peek_signin_bind", AsyncMock(return_value=None)
        ), patch.object(
            asess, "mark_result", AsyncMock()
        ) as mark:
            await PasswordAuthSessionResultHandler.post(h, "s1")
        h.set_status.assert_called_with(403)
        mark.assert_not_called()

    async def test_operator_deny_does_not_require_code(self):
        h = self._result_handler(
            {"result_token": "secret", "ok": False, "deny": True, "action": "operator"}
        )
        with patch.object(
            asess, "get_session", AsyncMock(return_value=self._doc())
        ), patch.object(
            asess, "peek_signin_bind", AsyncMock(return_value=None)
        ), patch.object(
            asess, "mark_result", AsyncMock(return_value=None)
        ) as mark:
            await PasswordAuthSessionResultHandler.post(h, "s1")
        h.set_status.assert_not_called()
        mark.assert_awaited_once()

    async def _approve(self, body):
        h = self._result_handler(body)
        with patch.object(
            asess, "get_session", AsyncMock(return_value=self._doc())
        ), patch.object(
            asess, "peek_signin_bind", AsyncMock(return_value=None)
        ), patch.object(
            asess, "mark_result", AsyncMock(return_value=None)
        ) as mark:
            await PasswordAuthSessionResultHandler.post(h, "s1")
        return h, mark

    async def test_same_browser_rp_token_bypasses_code(self):
        h, mark = await self._approve(
            {
                "result_token": "secret",
                "ok": True,
                "action": "operator",
                "rp_token": "rp",
            }
        )
        h.set_status.assert_not_called()
        mark.assert_awaited_once()

    async def test_wrong_rp_token_still_requires_code(self):
        h, mark = await self._approve(
            {
                "result_token": "secret",
                "ok": True,
                "action": "operator",
                "rp_token": "not-the-rp-token",
            }
        )
        h.set_status.assert_called_with(403)
        mark.assert_not_called()

    async def test_wrong_rp_token_with_valid_code_approves(self):
        h, mark = await self._approve(
            {
                "result_token": "secret",
                "ok": True,
                "action": "operator",
                "rp_token": "nope",
                "verification_code": "123456",
            }
        )
        h.set_status.assert_not_called()
        mark.assert_awaited_once()


class TestPendingAuthProof(AsyncTestCase):
    def test_pending_signature_roundtrip(self):
        priv = PrivateKey()
        public_key = priv.public_key.format(compressed=True).hex()
        message = asess.pending_auth_message("alice", 123)
        signature = priv.sign(
            hashlib.sha256(message.encode("utf-8")).digest(), hasher=None
        )
        encoded = base64.b64encode(signature).decode("ascii")
        self.assertTrue(
            asess.verify_identity_signature(
                public_key=public_key, message=message, signature_b64=encoded
            )
        )
        self.assertFalse(
            asess.verify_identity_signature(
                public_key=public_key,
                message=message + "|tampered",
                signature_b64=encoded,
            )
        )

    async def test_pending_requires_signature(self):
        h = _handler(
            PasswordAuthSessionPendingHandler,
            args={"username": "alice", "timestamp": "1", "signature": ""},
        )
        await PasswordAuthSessionPendingHandler.get(h)
        h.set_status.assert_called_with(401)

    async def test_pending_rejects_bad_signature(self):
        h = _handler(
            PasswordAuthSessionPendingHandler,
            args={"username": "alice", "timestamp": "100", "signature": "bad"},
        )
        with patch.object(asess, "_now", return_value=100), patch.object(
            asess,
            "resolve_identity",
            AsyncMock(return_value={"public_key": "ab" * 33, "identity": {}}),
        ), patch.object(
            asess, "verify_identity_signature", return_value=False
        ), patch.object(
            asess, "list_pending_for_identity", AsyncMock(return_value=[])
        ) as listing:
            await PasswordAuthSessionPendingHandler.get(h)
        h.set_status.assert_called_with(401)
        listing.assert_not_called()

    async def test_pending_with_valid_signature_returns_own_rows(self):
        h = _handler(
            PasswordAuthSessionPendingHandler,
            args={"username": "alice", "timestamp": "100", "signature": "good"},
        )
        row = {
            "session_id": "s1",
            "status": "pending",
            "result_token": "rt",
            "username": "alice",
        }
        with patch.object(asess, "_now", return_value=100), patch.object(
            asess,
            "resolve_identity",
            AsyncMock(
                return_value={
                    "public_key": "ab" * 33,
                    "identity": {"username_signature": "us"},
                }
            ),
        ), patch.object(
            asess, "verify_identity_signature", return_value=True
        ), patch.object(
            asess, "_pkh_from_pubhex", return_value="pkh"
        ), patch.object(
            asess, "list_pending_for_identity", AsyncMock(return_value=[row])
        ) as listing, patch.object(
            asess, "update_session", AsyncMock()
        ), patch.object(
            asess, "push_payload_from_session", return_value={"session_id": "s1"}
        ):
            await PasswordAuthSessionPendingHandler.get(h)
        h.set_status.assert_not_called()
        listing.assert_awaited_once()
        kwargs = listing.call_args.kwargs
        self.assertEqual(kwargs.get("username"), "alice")
        self.assertEqual(kwargs.get("username_signature"), "us")
        self.assertEqual(kwargs.get("inception_pkh"), "pkh")
        data = h.render_as_json.call_args[0][0]
        self.assertTrue(data.get("status"))
        self.assertEqual(data.get("pending"), [{"session_id": "s1"}])


class TestCreateReturnsReadToken(AsyncTestCase):
    async def test_create_returns_rp_token_not_result_token(self):
        h = _handler(
            PasswordAuthSessionCreateHandler,
            body={
                "username": "alice",
                "site": "https://node.example",
                "action": "signin",
            },
        )
        route = {
            "status": True,
            "public_key": "ab" * 33,
            "username_signature": "sig",
            "node_http_base": "",
            "is_local": True,
        }
        with patch.object(asess, "check_rate_limits", return_value=None), patch.object(
            asess, "resolve_password_route", AsyncMock(return_value=route)
        ), patch.object(asess, "_pkh_from_pubhex", return_value="pkh"), patch.object(
            asess, "this_node_http_base", return_value=""
        ), patch.object(
            asess, "issue_signin_bind", AsyncMock(return_value="bind")
        ), patch.object(
            asess, "insert_session", AsyncMock()
        ) as insert, patch.object(
            asess, "push_password_auth_request", AsyncMock(return_value=False)
        ), patch.object(
            asess, "_now", return_value=time.time()
        ):
            await PasswordAuthSessionCreateHandler.post(h)
        view = h.render_as_json.call_args[0][0]
        self.assertTrue(view.get("rp_token"))
        self.assertNotIn("result_token", view)
        self.assertRegex(view.get("verification_code") or "", r"^[0-9]{6}$")
        inserted = insert.call_args[0][0]
        self.assertEqual(inserted.get("rp_token"), view.get("rp_token"))
        self.assertEqual(
            inserted.get("verification_code"), view.get("verification_code")
        )

    async def test_loopback_site_uses_local_home_even_with_remote_route(self):
        h = _handler(
            PasswordAuthSessionCreateHandler,
            body={
                "username": "alice",
                "site": "http://localhost:8111",
                "action": "client",
            },
        )
        h.request.host = "localhost:8111"
        route = {
            "status": True,
            "public_key": "ab" * 33,
            "username_signature": "sig",
            "node_http_base": "https://serviceprovider.example",
            "is_local": False,
        }
        with patch.object(asess, "check_rate_limits", return_value=None), patch.object(
            asess, "resolve_password_route", AsyncMock(return_value=route)
        ), patch.object(asess, "_pkh_from_pubhex", return_value="pkh"), patch.object(
            asess, "this_node_http_base", return_value="http://localhost:8111"
        ), patch.object(
            asess, "issue_signin_bind", AsyncMock(return_value="bind")
        ), patch.object(
            asess, "insert_session", AsyncMock()
        ) as insert, patch.object(
            asess, "push_password_auth_request", AsyncMock(return_value=True)
        ) as push, patch.object(
            asess, "_now", return_value=time.time()
        ):
            await PasswordAuthSessionCreateHandler.post(h)
        view = h.render_as_json.call_args[0][0]
        self.assertEqual(view.get("home_node"), "http://localhost:8111")
        self.assertNotIn("proxied", view)
        inserted = insert.call_args[0][0]
        self.assertEqual(inserted.get("home_node"), "http://localhost:8111")
        push.assert_awaited_once()


class TestWebsocketPresenceProof(AsyncTestCase):
    def _signed(self, priv, username, ts):
        message = asess.password_auth_presence_message(username, ts)
        sig = priv.sign(hashlib.sha256(message.encode("utf-8")).digest(), hasher=None)
        return base64.b64encode(sig).decode("ascii")

    def _server(self, username, public_key):
        from yadacoin.websocket.base import RCPWebSocketServer

        ws = RCPWebSocketServer.__new__(RCPWebSocketServer)
        ws.peer = MagicMock()
        ws.peer.identity = MagicMock(username=username, public_key=public_key)
        return ws

    async def test_presence_requires_onchain_key_and_fresh_signature(self):
        priv = PrivateKey()
        pub = priv.public_key.format(compressed=True).hex()
        ts = int(time.time())
        sig = self._signed(priv, "alice", ts)
        ws = self._server("alice", pub)
        params = {"timestamp": ts, "signature": sig}
        with patch.object(
            asess, "resolve_identity", AsyncMock(return_value={"public_key": pub})
        ):
            self.assertTrue(await ws._verified_password_auth_presence(params))
            # replay of the same proof is refused
            self.assertFalse(await ws._verified_password_auth_presence(params))
        self.assertFalse(await ws._verified_password_auth_presence({"timestamp": ts}))

    async def test_presence_rejects_key_not_announced_on_chain(self):
        attacker = PrivateKey()
        victim = PrivateKey()
        victim_pub = victim.public_key.format(compressed=True).hex()
        attacker_pub = attacker.public_key.format(compressed=True).hex()
        ts = int(time.time())
        ws = self._server("alice", attacker_pub)
        params = {"timestamp": ts, "signature": self._signed(attacker, "alice", ts)}
        with patch.object(
            asess,
            "resolve_identity",
            AsyncMock(return_value={"public_key": victim_pub}),
        ):
            self.assertFalse(await ws._verified_password_auth_presence(params))

    async def test_presence_rejects_stale_timestamp(self):
        priv = PrivateKey()
        pub = priv.public_key.format(compressed=True).hex()
        ts = int(time.time()) - 10_000
        ws = self._server("alice", pub)
        params = {"timestamp": ts, "signature": self._signed(priv, "alice", ts)}
        with patch.object(
            asess, "resolve_identity", AsyncMock(return_value={"public_key": pub})
        ):
            self.assertFalse(await ws._verified_password_auth_presence(params))
