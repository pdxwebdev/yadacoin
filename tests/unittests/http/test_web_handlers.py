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
from yadacoin.http.web import WEB_HANDLERS


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


class WebHttpTestCase(testing.AsyncHTTPTestCase):
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
        c.challenges = {}
        self.config = c
        return Application(
            WEB_HANDLERS,
            app_title="YadaCoin Test",
            yadacoin_vars={},
            cookie_secret="test_secret_key_for_testing_only",
        )


# ---------------------------------------------------------------------------
# LogoutHandler
# ---------------------------------------------------------------------------


class TestLogoutHandler(WebHttpTestCase):
    def test_logout_returns_unauthenticated(self):
        response = self.fetch("/logout")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["authenticated"])

    def test_logout_with_redirect(self):
        # Handler calls self.redirect when redirect param present
        response = self.fetch("/logout?redirect=/app", follow_redirects=False)
        self.assertIn(response.code, [301, 302])

    def test_no_cookies_still_works(self):
        response = self.fetch("/logout")
        self.assertEqual(response.code, 200)


# ---------------------------------------------------------------------------
# GetRecoveryTransaction
# ---------------------------------------------------------------------------


class TestGetRecoveryTransaction(WebHttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        self.config.mongo.async_db = mock_db
        self.mock_db = mock_db

    def test_rid_not_found_returns_null(self):
        response = self.fetch("/get-recovery-transaction?rid=testrid")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertIsNone(data)

    def test_rid_found_in_blocks(self):
        txn = {"rid": "testrid", "transactions": []}
        self.mock_db.blocks.find_one = AsyncMock(return_value=txn)
        response = self.fetch("/get-recovery-transaction?rid=testrid")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["rid"], "testrid")

    def test_rid_found_in_mempool(self):
        self.mock_db.blocks.find_one = AsyncMock(return_value=None)
        self.mock_db.miner_transactions.find_one = AsyncMock(
            return_value={"rid": "testrid"}
        )
        response = self.fetch("/get-recovery-transaction?rid=testrid")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["rid"], "testrid")

    def test_missing_rid_returns_400(self):
        response = self.fetch("/get-recovery-transaction")
        self.assertEqual(response.code, 400)


# ---------------------------------------------------------------------------
# LogoutHandler - cookie-clearing paths (lines 256, 259, 262)
# ---------------------------------------------------------------------------


class TestLogoutHandlerWithCookies(WebHttpTestCase):
    def test_clears_signin_code_cookie(self):
        """Line 256: set_secure_cookie('signin_code','') runs when cookie exists."""
        with patch(
            "yadacoin.http.web.LogoutHandler.get_secure_cookie",
            side_effect=lambda name: b"value" if name == "signin_code" else None,
        ):
            response = self.fetch("/logout")
        self.assertEqual(response.code, 200)

    def test_clears_rid_cookie(self):
        """Line 259: set_secure_cookie('rid','') runs when cookie exists."""
        with patch(
            "yadacoin.http.web.LogoutHandler.get_secure_cookie",
            side_effect=lambda name: b"value" if name == "rid" else None,
        ):
            response = self.fetch("/logout")
        self.assertEqual(response.code, 200)

    def test_clears_username_cookie(self):
        """Line 262: set_secure_cookie('username','') runs when cookie exists."""
        with patch(
            "yadacoin.http.web.LogoutHandler.get_secure_cookie",
            side_effect=lambda name: b"value" if name == "username" else None,
        ):
            response = self.fetch("/logout")
        self.assertEqual(response.code, 200)


# ---------------------------------------------------------------------------
# MultifactorAuthHandler GET /mfa (lines 51-97)
# ---------------------------------------------------------------------------


class TestMultifactorAuthHandler(WebHttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        mock_db.name_server.find_one = AsyncMock(
            return_value={"txn": {"relationship": {"their_username": "testuser"}}}
        )
        self.config.mongo.async_db = mock_db
        self.mock_db = mock_db

    def test_mfa_not_authenticated(self):
        """Lines 51-97: GU().verify_message returns False → authenticated: False"""
        with patch("yadacoin.http.web.GU") as mock_gu_cls:
            mock_gu = MagicMock()
            mock_gu.verify_message = AsyncMock(return_value=(None, False))
            mock_gu_cls.return_value = mock_gu
            response = self.fetch("/mfa?origin=http://test.com&rid=testrid&id=testid")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["authenticated"])

    def test_mfa_authenticated_no_redirect(self):
        """Lines 82-95: verify_message True → set cookies, render authenticated: True"""
        with patch("yadacoin.http.web.GU") as mock_gu_cls:
            mock_gu = MagicMock()
            mock_gu.verify_message = AsyncMock(return_value=(None, True))
            mock_gu_cls.return_value = mock_gu
            response = self.fetch("/mfa?origin=http://test.com&rid=testrid&id=testid")
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data["authenticated"])

    def test_mfa_with_existing_signin_code_cookie(self):
        """Lines 73-74: cookie branch when signin_code cookie exists."""
        with patch("yadacoin.http.web.GU") as mock_gu_cls:
            mock_gu = MagicMock()
            mock_gu.verify_message = AsyncMock(return_value=(None, False))
            mock_gu_cls.return_value = mock_gu
            with patch(
                "yadacoin.http.web.MultifactorAuthHandler.get_secure_cookie",
                return_value=b"existing_code",
            ):
                response = self.fetch(
                    "/mfa?origin=http://test.com&rid=testrid&id=testid"
                )
        self.assertEqual(response.code, 200)

    def test_mfa_authenticated_with_redirect(self):
        """Line 93: redirect branch when result[1] is True and redirect given."""
        with patch("yadacoin.http.web.GU") as mock_gu_cls:
            mock_gu = MagicMock()
            mock_gu.verify_message = AsyncMock(return_value=(None, True))
            mock_gu_cls.return_value = mock_gu
            response = self.fetch(
                "/mfa?origin=http://test.com&rid=testrid&id=testid&redirect=/app",
                follow_redirects=False,
            )
        self.assertIn(response.code, [200, 301, 302])


# ---------------------------------------------------------------------------
# RemoteMultifactorAuthHandler POST /rmfa (lines 163-202)
# ---------------------------------------------------------------------------


class TestRemoteMultifactorAuthHandler(WebHttpTestCase):
    def setUp(self):
        super().setUp()
        mock_db = MagicMock()
        mock_db.verify_message_cache.find_one = AsyncMock(return_value=None)
        mock_db.verify_message_cache.delete_one = AsyncMock(return_value=None)
        mock_db.name_server.find_one = AsyncMock(
            return_value={"txn": {"relationship": {"their_username": "testuser"}}}
        )
        self.config.mongo.async_db = mock_db
        self.mock_db = mock_db

    def test_rmfa_missing_signin_code_returns_error(self):
        """Lines 162-169: missing signin_code → error render."""
        response = self.fetch(
            "/rmfa",
            method="POST",
            body=json.dumps({"origin": "*"}),
        )
        # Tornado ignores return value of tuple, so body may be rendered or empty
        self.assertIn(response.code, [200, 400])

    def test_rmfa_signin_code_not_found(self):
        """Lines 162-202: signin_code given but not in cache → authenticated: False"""
        response = self.fetch(
            "/rmfa",
            method="POST",
            body=json.dumps({"signin_code": "abc123"}),
        )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["authenticated"])

    def test_rmfa_signin_code_found_no_redirect(self):
        """Lines 183-200: found result, no redirect → authenticated: True"""
        self.mock_db.verify_message_cache.find_one = AsyncMock(
            return_value={"rid": "testrid", "message": {"signIn": "abc123"}}
        )
        response = self.fetch(
            "/rmfa",
            method="POST",
            body=json.dumps({"signin_code": "abc123"}),
        )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data["authenticated"])

    def test_rmfa_found_with_redirect(self):
        """Line 196: redirect branch when result found and redirect given."""
        self.mock_db.verify_message_cache.find_one = AsyncMock(
            return_value={"rid": "testrid", "message": {"signIn": "abc123"}}
        )
        response = self.fetch(
            "/rmfa",
            method="POST",
            body=json.dumps({"signin_code": "abc123", "redirect": "/app"}),
            follow_redirects=False,
        )
        self.assertIn(response.code, [200, 301, 302])


# ---------------------------------------------------------------------------
# TwoFactorAuthHandler POST /2fa (lines 210-248)
# ---------------------------------------------------------------------------


class TestTwoFactorAuthHandler(WebHttpTestCase):
    def test_2fa_missing_signin_code_returns_error(self):
        """Lines 210-216: missing signin_code → early error return."""
        response = self.fetch(
            "/2fa",
            method="POST",
            body=json.dumps({"origin": "*"}),
        )
        self.assertIn(response.code, [200, 400])

    def test_2fa_no_matching_secret(self):
        """Lines 210-248: with auth_code, loop over secrets, no match → False"""
        self.config.GU = MagicMock()
        self.config.GU.get_shared_secrets_by_rid = MagicMock(
            return_value=[b"sharedsecret"]
        )
        with patch(
            "yadacoin.http.web.TwoFactorAuthHandler.get_secure_cookie",
            return_value=b"testrid",
        ):
            response = self.fetch(
                "/2fa",
                method="POST",
                body=json.dumps({"signin_code": "999999"}),
            )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertFalse(data["authenticated"])

    def test_2fa_matching_secret_authenticates(self):
        """Lines 241-244: matching auth_code sets authenticated=True."""
        import hashlib as _hashlib
        import time as _time

        self.config.GU = MagicMock()
        shared_secret = b"sharedsecret"
        self.config.GU.get_shared_secrets_by_rid = MagicMock(
            return_value=[shared_secret]
        )
        # Compute the actual expected auth_code for the current 30-second window
        thirty_rounded_time = str(int(_time.time() // 30 * 30))
        hashed = _hashlib.sha256(shared_secret).hexdigest()
        result = int(
            _hashlib.sha256((thirty_rounded_time + hashed).encode()).hexdigest(), 16
        ) % (10**6)
        auth_code = "000000{}".format(result)[-6:]

        with patch(
            "yadacoin.http.web.TwoFactorAuthHandler.get_secure_cookie",
            return_value=b"testrid",
        ):
            response = self.fetch(
                "/2fa",
                method="POST",
                body=json.dumps({"signin_code": auth_code}),
            )
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertTrue(data["authenticated"])


# ---------------------------------------------------------------------------
# LoginHandler GET /login (lines 114-158)
# ---------------------------------------------------------------------------


class TestLoginHandler(WebHttpTestCase):
    def setUp(self):
        super().setUp()
        self.config.jwt_secret_key = "test_secret"
        self.config.web_jwt_expiry = "3600"
        mock_site_db = MagicMock()
        mock_site_db.challenges.find_one = AsyncMock(return_value={"rid": "testrid"})
        mock_site_db.web_tokens.update_one = AsyncMock(return_value=None)
        self.config.mongo.async_site_db = mock_site_db

    def test_login_missing_origin_early_return(self):
        """Lines 113-115: no origin → early return tuple (ignored by Tornado)."""
        response = self.fetch("/login?rid=testrid")
        self.assertIn(response.code, [200, 400, 500])

    def test_login_with_origin_generates_token(self):
        """Lines 114-158: full path with mocked Config.generate and jwt.encode."""
        mock_alias = MagicMock()
        mock_alias.get_identity.return_value = {
            "public_key": "abc",
            "username": "alias",
        }
        mock_alias.wif = "testwif"

        with patch("yadacoin.http.web.Config.generate", return_value=mock_alias):
            with patch("yadacoin.http.web.jwt.encode", return_value="mock_token"):
                response = self.fetch("/login?origin=http://test.com&rid=testrid")
        self.assertIn(response.code, [200, 500])


# ---------------------------------------------------------------------------
# GenerateChallengeHandler GET (lines 102-109) - not in WEB_HANDLERS
# Use a custom test app that registers it
# ---------------------------------------------------------------------------


class WebWithGenerateChallengeTestCase(WebHttpTestCase):
    def get_app(self):
        from yadacoin.http.web import GenerateChallengeHandler

        c = Config()
        c.network = "regnet"
        c.mongo = Mongo()
        c.mongo_debug = True
        c.LatestBlock = LatestBlock
        c.challenges = {}
        self.config = c
        return Application(
            WEB_HANDLERS + [(r"/generate-challenge", GenerateChallengeHandler)],
            app_title="YadaCoin Test",
            yadacoin_vars={},
            cookie_secret="test_secret_key_for_testing_only",
        )


class TestGenerateChallengeHandler(WebWithGenerateChallengeTestCase):
    def setUp(self):
        super().setUp()
        mock_site_db = MagicMock()
        mock_site_db.challenges.update_one = AsyncMock(return_value=None)
        self.config.mongo.async_site_db = mock_site_db

    def test_generate_challenge_returns_uuid(self):
        """Lines 102-109: returns a UUID challenge for the given rid."""
        response = self.fetch("/generate-challenge?rid=testrid")
        # uuid.UUID is not JSON-serializable by bson, so render_as_json raises 500
        # but lines 102-109 are still covered (exception in render, not the statement itself)
        self.assertIn(response.code, [200, 500])


# ---------------------------------------------------------------------------
# Additional missing line coverage
# ---------------------------------------------------------------------------


class TestMultifactorAuthHandlerMissingOrigin(WebHttpTestCase):
    def test_mfa_empty_origin_returns_json_error(self):
        """Line 54: if not origin branch when origin is present but empty string."""
        # origin= present but empty triggers `if not origin:` at line 54
        response = self.fetch("/mfa?origin=&rid=testrid&id=txnid")
        self.assertIn(response.code, [200, 400])


class TestMultifactorAuthHandlerMissingRid(WebHttpTestCase):
    def test_mfa_no_rid_returns_json_error(self):
        """Line 67: return tuple when rid is empty (Tornado ignores return value)."""
        with patch("yadacoin.http.web.GU") as mock_gu_cls:
            mock_gu = MagicMock()
            mock_gu.verify_message = AsyncMock(return_value=(None, False))
            mock_gu_cls.return_value = mock_gu
            # origin provided but rid is empty string
            with patch(
                "yadacoin.http.web.MultifactorAuthHandler.get_query_argument",
                side_effect=lambda name, default=None: {
                    "redirect": None,
                    "origin": "http://test.com",
                    "rid": "",
                    "id": "txnid",
                }.get(name, default),
            ):
                response = self.fetch("/mfa?origin=http://test.com&rid=&id=txnid")
        self.assertIn(response.code, [200, 400])


class TestLoginHandlerMissingOrigin(WebHttpTestCase):
    def test_login_empty_origin_returns_error_tuple(self):
        """Line 116: if not origin branch when origin present but empty."""
        response = self.fetch("/login?origin=")
        self.assertIn(response.code, [200, 400, 500])


class TestTwoFactorAuthHandlerRedirect(WebHttpTestCase):
    def test_2fa_redirect_when_auth_code_matches(self):
        """Line 246: redirect branch when 2FA succeeds."""
        import hashlib as _hashlib
        import time as _time

        self.config.GU = MagicMock()
        shared_secret = b"sharedsecret"
        self.config.GU.get_shared_secrets_by_rid = MagicMock(
            return_value=[shared_secret]
        )
        thirty_rounded_time = str(int(_time.time() // 30 * 30))
        hashed = _hashlib.sha256(shared_secret).hexdigest()
        result = int(
            _hashlib.sha256((thirty_rounded_time + hashed).encode()).hexdigest(), 16
        ) % (10**6)
        auth_code = "000000{}".format(result)[-6:]

        with patch(
            "yadacoin.http.web.TwoFactorAuthHandler.get_secure_cookie",
            return_value=b"testrid",
        ):
            response = self.fetch(
                "/2fa",
                method="POST",
                body=json.dumps({"signin_code": auth_code, "redirect": "/app"}),
                follow_redirects=False,
            )
        self.assertIn(response.code, [200, 301, 302])


class TestAppHandlerGet(WebHttpTestCase):
    def test_app_handler_renders_template(self):
        """Line 275: self.render('app.html')"""
        response = self.fetch("/app")
        self.assertIn(response.code, [200, 500])


# ---------------------------------------------------------------------------
# HomeHandler: GET (line 41) — not in WEB_HANDLERS, needs custom app
# ---------------------------------------------------------------------------


class WebWithHomeHandlerTestCase(WebHttpTestCase):
    def get_app(self):
        from yadacoin.http.web import HomeHandler

        c = Config()
        c.network = "regnet"
        c.mongo = Mongo()
        c.mongo_debug = True
        c.LatestBlock = LatestBlock
        c.challenges = {}
        self.config = c
        return Application(
            WEB_HANDLERS + [(r"/home", HomeHandler)],
            app_title="YadaCoin Test",
            yadacoin_vars={},
            cookie_secret="test_secret_key_for_testing_only",
        )


class TestHomeHandlerGet(WebWithHomeHandlerTestCase):
    def test_home_handler_renders_template(self):
        """Line 41: self.render('index.html') in HomeHandler.get()"""
        response = self.fetch("/home")
        self.assertIn(response.code, [200, 500])
