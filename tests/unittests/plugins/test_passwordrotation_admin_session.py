"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

from plugins.passwordrotation.handlers import (
    PasswordAdminSessionHandler,
    is_admin_branch_peer,
    request_origin,
)

from ..test_setup import AsyncTestCase


class TestAdminOrigin(AsyncTestCase):
    def test_request_origin_and_peer_match(self):
        h = MagicMock()
        h.request.protocol = "http"
        h.request.host = "127.0.0.1:8001"
        h.request.headers = {}
        self.assertEqual(request_origin(h), "http://127.0.0.1:8001")
        self.assertTrue(is_admin_branch_peer(h, "http://127.0.0.1:8001"))
        self.assertTrue(is_admin_branch_peer(h, "http://127.0.0.1:8001/"))
        self.assertFalse(is_admin_branch_peer(h, "https://evil.example"))

    def test_forwarded_proto_and_https_peer_match(self):
        h = MagicMock()
        h.request.protocol = "http"
        h.request.host = "yadacoin.io"
        h.request.headers = {
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "yadacoin.io",
        }
        self.assertEqual(request_origin(h), "https://yadacoin.io")
        self.assertTrue(is_admin_branch_peer(h, "https://yadacoin.io"))
        # Browser https origin vs plain http node still matches by host
        h2 = MagicMock()
        h2.request.protocol = "http"
        h2.request.host = "yadacoin.io"
        h2.request.headers = {}
        self.assertTrue(is_admin_branch_peer(h2, "https://yadacoin.io"))


class TestAdminSession(AsyncTestCase):
    def _handler(self, origin="http://127.0.0.1:8001", body=b"{}"):
        h = PasswordAdminSessionHandler.__new__(PasswordAdminSessionHandler)
        h.request = MagicMock()
        h.request.protocol = "http"
        h.request.host = "127.0.0.1:8001"
        h.request.headers = {"Origin": origin}
        h.request.body = body
        h.config = MagicMock()
        h.config.jwt_secret_key = None
        h.config.mongo.async_db.key_event_log.find_one = AsyncMock(return_value=None)
        h.config.mongo.async_db.config.update_one = AsyncMock()
        h.set_status = MagicMock()
        h.set_secure_cookie = MagicMock()
        h.render_as_json = MagicMock()
        h.issue_operator_session = AsyncMock(return_value="tok")
        return h

    async def test_origin_mismatch_forbidden(self):
        h = self._handler(
            origin="https://evil.example",
            body=b'{"branch_peer":"https://evil.example","password":"x"}',
        )
        await PasswordAdminSessionHandler.post(h)
        h.set_status.assert_called_with(403)

    async def test_no_branch_unauthorized(self):
        h = self._handler()
        await PasswordAdminSessionHandler.post(h)
        h.set_status.assert_called_with(401)

    async def test_recent_tip_without_matching_identity_rejected(self):
        h = self._handler()
        h.config.username = "nodeuser"
        h.config.kel_manager = None
        h.config.inception = None
        h.config.mongo.async_db.key_event_log.find_one = AsyncMock(
            return_value={
                "counter": 2,
                "timestamp": time.time(),
                "password": {},
                "inception_public_key_hash": "1ForeignInceptionXXXXXXXXXXXXXXX",
            }
        )
        with patch(
            "plugins.passwordrotation.handlers.node_inception_pkh",
            AsyncMock(return_value="1NodeInceptionXXXXXXXXXXXXXXXXXX"),
        ):
            await PasswordAdminSessionHandler.post(h)
        h.set_status.assert_called_with(403)
        h.issue_operator_session.assert_not_called()

    async def test_matching_identity_wrong_password_rejected(self):
        h = self._handler(body=b'{"password":"nope"}')
        h.config.mongo.async_db.key_event_log.find_one = AsyncMock(
            return_value={
                "counter": 2,
                "timestamp": time.time(),
                "inception_public_key_hash": "1NodeInceptionXXXXXXXXXXXXXXXXXX",
                "password": {"prerotated_password_hash": "00" * 32},
            }
        )
        with patch(
            "plugins.passwordrotation.handlers.node_inception_pkh",
            AsyncMock(return_value="1NodeInceptionXXXXXXXXXXXXXXXXXX"),
        ), patch(
            "plugins.passwordrotation.handlers._verify_password",
            return_value=False,
        ):
            await PasswordAdminSessionHandler.post(h)
        h.set_status.assert_called_with(401)
        h.issue_operator_session.assert_not_called()

    async def test_stale_tip_without_password_rejected(self):
        h = self._handler()
        h.config.mongo.async_db.key_event_log.find_one = AsyncMock(
            return_value={
                "counter": 2,
                "timestamp": time.time() - 9999,
                "inception_public_key_hash": "1NodeInceptionXXXXXXXXXXXXXXXXXX",
                "password": {},
            }
        )
        with patch(
            "plugins.passwordrotation.handlers.node_inception_pkh",
            AsyncMock(return_value="1NodeInceptionXXXXXXXXXXXXXXXXXX"),
        ):
            await PasswordAdminSessionHandler.post(h)
        h.set_status.assert_called_with(401)


class TestGetAuthCutoff(AsyncTestCase):
    async def test_cutoff_is_process_epoch_not_stale_cookie(self):
        from yadacoin.decorators.jwtauth import AUTH_REVOCATION_CUTOFF
        from yadacoin.http.base import BaseHandler

        h = BaseHandler.__new__(BaseHandler)
        h.config = MagicMock()
        epoch = float(AUTH_REVOCATION_CUTOFF) + 1000.0
        h.config.operator_session_epoch = epoch
        cutoff = await BaseHandler.get_auth_cutoff(h)
        self.assertEqual(cutoff, epoch)
        self.assertLess(epoch - 1, cutoff)
