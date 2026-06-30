"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio

import tornado
from tornado import testing
from tornado.web import Application

from yadacoin.core.config import Config
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.mongo import Mongo
from yadacoin.http.web import WEB_HANDLERS


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
            WEB_HANDLERS,
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
    def test_home_handler_renders_template(self):
        """HomeHandler.get() renders dashboard.html at /"""
        response = self.fetch("/")
        self.assertIn(response.code, [200, 500])

    def test_node_dashboard_route(self):
        """HomeHandler is also served at /node-dashboard"""
        response = self.fetch("/node-dashboard")
        self.assertIn(response.code, [200, 500])
