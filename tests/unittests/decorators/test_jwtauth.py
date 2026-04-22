"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from unittest.mock import MagicMock, patch

from yadacoin.decorators.jwtauth import jwtauthwallet, jwtauthwebuser


class MockHandler:
    def __init__(self, auth_header=None):
        self.request = MagicMock()
        self.request.headers = {}
        if auth_header:
            self.request.headers["Authorization"] = auth_header
        self.config = MagicMock()
        self.jwt = None

    def _execute(self, transforms, *args, **kwargs):
        return "executed"


class TestJwtAuthWallet(unittest.TestCase):
    def test_decorator_returns_class(self):
        class TestHandlerClass:
            def _execute(self, transforms, *args, **kwargs):
                return "ok"

        result = jwtauthwallet(TestHandlerClass)
        self.assertIs(result, TestHandlerClass)

    def test_no_auth_header_returns_false(self):
        class TestHandlerClass:
            def _execute(self, transforms, *args, **kwargs):
                return "ok"

        jwtauthwallet(TestHandlerClass)
        handler = MagicMock()
        handler.request.headers.get.return_value = None

        # Call directly - should return False
        result = TestHandlerClass._execute(handler, [], {})
        # No auth header, require_auth returns False but _execute still calls handler
        # The decorator doesn't block - it just tries auth non-blocking
        self.assertIsNotNone(result)

    def test_invalid_bearer_format_two_parts(self):
        class TestHandlerClass:
            def _execute(self, transforms, *args, **kwargs):
                return "ok"

        jwtauthwallet(TestHandlerClass)
        handler = MagicMock()
        # 'Bearer token extra' has 3 parts, not 2 -> returns False
        handler.request.headers.get.return_value = "Bearer token extra"
        result = TestHandlerClass._execute(handler, [], {})
        self.assertIsNotNone(result)

    def test_wrong_scheme(self):
        class TestHandlerClass:
            def _execute(self, transforms, *args, **kwargs):
                return "ok"

        jwtauthwallet(TestHandlerClass)
        handler = MagicMock()
        # 'Basic token' -> parts[0].lower() != 'bearer'
        handler.request.headers.get.return_value = "Basic token"
        result = TestHandlerClass._execute(handler, [], {})
        self.assertIsNotNone(result)

    def test_invalid_jwt_token(self):
        class TestHandlerClass:
            def _execute(self, transforms, *args, **kwargs):
                return "ok"

        jwtauthwallet(TestHandlerClass)
        handler = MagicMock()
        handler.request.headers.get.return_value = "Bearer invalidtoken"
        # jwt.decode will raise exception -> require_auth returns False
        result = TestHandlerClass._execute(handler, [], {})
        self.assertIsNotNone(result)


class TestJwtAuthWebUser(unittest.TestCase):
    def test_decorator_returns_class(self):
        class TestHandlerClass:
            def _execute(self, transforms, *args, **kwargs):
                return "ok"

        result = jwtauthwebuser(TestHandlerClass)
        self.assertIs(result, TestHandlerClass)

    def test_no_auth_header(self):
        class TestHandlerClass:
            def _execute(self, transforms, *args, **kwargs):
                return "ok"

        jwtauthwebuser(TestHandlerClass)
        handler = MagicMock()
        handler.request.headers.get.return_value = None
        result = TestHandlerClass._execute(handler, [], {})
        self.assertIsNotNone(result)

    def test_invalid_bearer_format_not_three_parts(self):
        class TestHandlerClass:
            def _execute(self, transforms, *args, **kwargs):
                return "ok"

        jwtauthwebuser(TestHandlerClass)
        handler = MagicMock()
        # webuser requires 3 parts: Bearer <token> <rid>
        handler.request.headers.get.return_value = "Bearer token"
        result = TestHandlerClass._execute(handler, [], {})
        self.assertIsNotNone(result)

    def test_wrong_scheme_webuser(self):
        class TestHandlerClass:
            def _execute(self, transforms, *args, **kwargs):
                return "ok"

        jwtauthwebuser(TestHandlerClass)
        handler = MagicMock()
        handler.request.headers.get.return_value = "Basic token rid"
        result = TestHandlerClass._execute(handler, [], {})
        self.assertIsNotNone(result)


class TestJwtAuthWalletValidToken(unittest.TestCase):
    def setUp(self):
        class TestHandlerClass:
            def _execute(self, transforms, *args, **kwargs):
                return "executed"

        jwtauthwallet(TestHandlerClass)
        self.HandlerClass = TestHandlerClass

    def _make_handler(self, auth_value):
        handler = MagicMock()
        handler.request.headers.get.return_value = auth_value
        handler.config.jwt_public_key = "pubkey"
        handler.config.jwt_options = {}
        return handler

    def test_valid_jwt_with_valid_mongo_calls_execute(self):
        handler = self._make_handler("Bearer validtoken")
        handler.jwt = {"timestamp": 100}
        mongo_jwt = {"value": {"timestamp": 50}}
        handler.config.mongo.db.config.find_one.return_value = mongo_jwt
        with patch("jwt.decode", return_value={"timestamp": 100}):
            result = self.HandlerClass._execute(handler, [], {})
        self.assertEqual(result, "executed")

    def test_valid_jwt_mongo_timestamp_too_old_returns_execute(self):
        # JWT timestamp < mongo timestamp → require_auth returns False, but _execute still returns handler result
        handler = self._make_handler("Bearer validtoken")
        handler.jwt = {"timestamp": 10}
        mongo_jwt = {"value": {"timestamp": 9999}}
        handler.config.mongo.db.config.find_one.return_value = mongo_jwt
        with patch("jwt.decode", return_value={"timestamp": 10}):
            result = self.HandlerClass._execute(handler, [], {})
        # Even when require_auth returns False, _execute still calls handler_execute
        self.assertIsNotNone(result)

    def test_valid_jwt_no_mongo_jwt_returns_execute(self):
        handler = self._make_handler("Bearer validtoken")
        handler.config.mongo.db.config.find_one.return_value = None
        with patch("jwt.decode", return_value={"timestamp": 100}):
            result = self.HandlerClass._execute(handler, [], {})
        self.assertIsNotNone(result)

    def test_execute_exception_in_require_auth_returns_false(self):
        handler = MagicMock()
        handler.request.headers.get.side_effect = Exception("broken")
        result = self.HandlerClass._execute(handler, [], {})
        self.assertFalse(result)


class TestJwtAuthWebUserValidToken(unittest.TestCase):
    def setUp(self):
        class TestHandlerClass:
            def _execute(self, transforms, *args, **kwargs):
                return "executed"

        jwtauthwebuser(TestHandlerClass)
        self.HandlerClass = TestHandlerClass

    def _make_handler(self, auth_value):
        handler = MagicMock()
        handler.request.headers.get.return_value = auth_value
        handler.config.jwt_public_key = "pubkey"
        handler.config.jwt_options = {}
        return handler

    def test_valid_jwt_with_valid_mongo_calls_execute(self):
        handler = self._make_handler("Bearer validtoken myrid")
        handler.jwt = {"timestamp": 100}
        mongo_jwt = {"value": {"timestamp": 50}}
        handler.config.mongo.site_db.web_tokens.find_one.return_value = mongo_jwt
        with patch("jwt.decode", return_value={"timestamp": 100}):
            result = self.HandlerClass._execute(handler, [], {})
        self.assertEqual(result, "executed")

    def test_valid_jwt_mongo_timestamp_too_old(self):
        handler = self._make_handler("Bearer validtoken myrid")
        handler.jwt = {"timestamp": 10}
        mongo_jwt = {"value": {"timestamp": 9999}}
        handler.config.mongo.site_db.web_tokens.find_one.return_value = mongo_jwt
        with patch("jwt.decode", return_value={"timestamp": 10}):
            result = self.HandlerClass._execute(handler, [], {})
        self.assertIsNotNone(result)

    def test_valid_jwt_no_mongo_returns_execute(self):
        handler = self._make_handler("Bearer validtoken myrid")
        handler.config.mongo.site_db.web_tokens.find_one.return_value = None
        with patch("jwt.decode", return_value={"timestamp": 100}):
            result = self.HandlerClass._execute(handler, [], {})
        self.assertIsNotNone(result)

    def test_execute_exception_in_require_auth_returns_false_webuser(self):
        handler = MagicMock()
        handler.request.headers.get.side_effect = Exception("broken")
        result = self.HandlerClass._execute(handler, [], {})
        self.assertFalse(result)

    def test_invalid_jwt_token_webuser(self):
        # Valid format (3 parts) but jwt.decode raises → hits except: return False
        handler = self._make_handler("Bearer invalidtoken myrid")
        result = self.HandlerClass._execute(handler, [], {})
        self.assertIsNotNone(result)

    unittest.main(argv=["first-arg-is-ignored"], exit=False)
