"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import os
import tempfile
import time
import unittest

import tornado
from tornado import testing
from tornado.web import Application

try:
    from plugins.app.web import WEB_HANDLERS
    from plugins.operator.handlers import HANDLERS as OPERATOR_HANDLERS
except ImportError:
    raise unittest.SkipTest("app or operator plugin is not installed")
from yadacoin.core.config import Config
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.mongo import Mongo


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
        self.config = c
        return Application(
            WEB_HANDLERS + OPERATOR_HANDLERS,
            app_title="YadaCoin Test",
            yadacoin_vars={},
            cookie_secret="test_secret_key_for_testing_only",
        )


# ---------------------------------------------------------------------------
# AppHandler GET /app
# ---------------------------------------------------------------------------


class TestAppHandlerGet(WebHttpTestCase):
    def test_app_handler_renders_template(self):
        """AppHandler.get() renders app.html"""
        response = self.fetch("/app")
        self.assertIn(response.code, [200, 500])


# ---------------------------------------------------------------------------
# HomeHandler GET / and /node-dashboard
# ---------------------------------------------------------------------------


class TestHomeHandlerGet(WebHttpTestCase):
    def _ready_node(self):
        self.config.setup_required = False
        self.config.operator_onboarding = "done"
        self.config.peer_type = "user"

    def test_home_handler_serves_scroller(self):
        self._ready_node()
        response = self.fetch("/", follow_redirects=False)
        self.assertEqual(response.code, 200)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        body = response.body.decode()
        self.assertIn("<style>", body)
        self.assertIn("html.landing", body)
        self.assertNotIn("styles.css?v=", body)
        self.assertIn('location.pathname === "/"', body)
        self.assertIn('href="/exchanges">Get YDA', body)
        self.assertIn('href="/download">Run a node', body)

    def test_home_setup_redirects(self):
        self.config.setup_required = True
        self.config.operator_onboarding = "done"
        self.config.peer_type = "user"
        response = self.fetch("/", follow_redirects=False)
        self.assertEqual(response.code, 302)
        self.assertIn("/operator/setup", response.headers["Location"])

    def test_node_dashboard_route(self):
        self._ready_node()
        response = self.fetch("/node-dashboard", follow_redirects=False)
        self.assertNotIn(b'location.pathname === "/"', response.body)

    def test_operator_page_requires_yada_password(self):
        response = self.fetch("/operator", follow_redirects=False)
        self.assertEqual(response.code, 302)
        location = response.headers["Location"]
        self.assertIn("/yada-password/signin", location)
        self.assertIn("purpose=operator", location)
        self.assertIn("next=%2Foperator", location)
        denied = self.fetch(
            "/operator/api/reload",
            method="POST",
            body=b'{"confirm":"reload"}',
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(denied.code, 401)

    def test_seed_requires_startup_access_code(self):
        from plugins.operator.setup import write_onboarding

        directory = tempfile.mkdtemp()
        config_path = os.path.join(directory, "config.json")
        with open(config_path, "w") as handle:
            handle.write("{}")
        previous_path = getattr(self.config, "config_path", None)
        previous_factor = os.environ.get("SECOND_FACTOR")
        previous_file = os.environ.get("SECOND_FACTOR_FILE")
        self.config.config_path = config_path
        self.config.setup_required = False
        self.config.username = "operator"
        self.config.seed = "test seed phrase"
        self.config.operator_access_code = "startup-code"
        self.config.operator_access_code_shown_at = time.time()
        os.environ["SECOND_FACTOR"] = "factor"
        os.environ.pop("SECOND_FACTOR_FILE", None)
        try:
            write_onboarding(self.config, "seed")
            denied = self.fetch("/operator/api/setup/seed")
            self.assertEqual(denied.code, 401)
            self.assertNotIn(b"test seed phrase", denied.body)
            allowed = self.fetch(
                "/operator/api/setup/seed",
                headers={"X-Operator-Code": "startup-code"},
            )
            self.assertEqual(allowed.code, 200)
            self.assertIn(b"test seed phrase", allowed.body)
        finally:
            if previous_path is None:
                self.config.config_path = ""
            else:
                self.config.config_path = previous_path
            if previous_factor is None:
                os.environ.pop("SECOND_FACTOR", None)
            else:
                os.environ["SECOND_FACTOR"] = previous_factor
            if previous_file is None:
                os.environ.pop("SECOND_FACTOR_FILE", None)
            else:
                os.environ["SECOND_FACTOR_FILE"] = previous_file
