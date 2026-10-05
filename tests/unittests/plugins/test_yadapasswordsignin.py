"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from unittest.mock import MagicMock

from plugins.yadapasswordsignin.handlers import (
    PURPOSES,
    redirect_to_signin,
    safe_keyname,
    safe_next,
    signin_location,
)


class TestYadaPasswordSignin(unittest.TestCase):
    def test_safe_next_rejects_open_redirects(self):
        self.assertEqual(safe_next("/file-announcements"), "/file-announcements")
        self.assertEqual(safe_next("/app?x=1"), "/app?x=1")
        self.assertEqual(safe_next("https://evil.example/app"), "")
        self.assertEqual(safe_next("//evil.example"), "")
        self.assertEqual(safe_next("/\\evil"), "")
        self.assertEqual(safe_next(""), "")

    def test_safe_keyname(self):
        self.assertEqual(
            safe_keyname("operator-node@localhost:8000"),
            "operator-node@localhost:8000",
        )
        self.assertEqual(safe_keyname("usernames-alice"), "")
        self.assertEqual(safe_keyname("operator-"), "")

    def test_signin_location_wallet_and_plugins(self):
        loc = signin_location(
            "wallet", next_path="/app", keyname="operator-node@yadacoin.io"
        )
        self.assertTrue(loc.startswith("/yada-password/signin?"))
        self.assertIn("purpose=wallet", loc)
        self.assertIn("next=%2Fapp", loc)
        self.assertIn("keyname=operator-node%40yadacoin.io", loc)
        for purpose in (
            "file-announcements",
            "credential-issuer",
            "livestream",
            "wallet",
        ):
            self.assertIn(purpose, PURPOSES)
            self.assertTrue(
                signin_location(purpose).startswith("/yada-password/signin?")
            )

    def test_redirect_uses_request_uri(self):
        handler = MagicMock()
        handler.request.uri = "/file-announcements"
        redirect_to_signin(handler, "file-announcements")
        url = handler.redirect.call_args[0][0]
        self.assertIn("purpose=file-announcements", url)
        self.assertIn("next=%2Ffile-announcements", url)
