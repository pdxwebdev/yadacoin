"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import os
import unittest


class TestYadaScrollerSignin(unittest.TestCase):
    def _app_js(self):
        root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        path = os.path.join(
            root,
            "plugins",
            "fileannouncement",
            "demos",
            "yadascrollerdemo",
            "app.js",
        )
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_signin_uses_client_handoff(self):
        src = self._app_js()
        self.assertIn('action: "client"', src)
        self.assertNotIn('action: "operator"', src)

    def test_username_is_not_prefilled_from_node_identity(self):
        src = self._app_js()
        self.assertNotIn("/yada-config", src)
        self.assertNotIn("identity.username", src)

    def test_username_comes_from_active_extension_identity(self):
        src = self._app_js()
        self.assertIn("YADA_PASSWORD_CLIENT", src)
        self.assertIn("YADA_PASSWORD_CLIENT_RESULT", src)
        self.assertIn("syncExtensionUsername", src)

    def test_poll_sends_rp_token(self):
        src = self._app_js()
        self.assertIn("X-Password-Auth-RP-Token", src)
        self.assertIn("created.rp_token", src)

    def test_signin_persists_active_session_for_extension(self):
        src = self._app_js()
        self.assertIn("yadaActiveAuthSession", src)
        self.assertIn("sessionStorage.setItem", src)

    def test_signin_shows_verification_code(self):
        src = self._app_js()
        self.assertIn("created.verification_code", src)
        self.assertIn("showSigninCode", src)
