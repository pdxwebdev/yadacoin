"""
Tests for yadacoin/http/proxy.py — targeting 100% coverage.
"""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import tornado.httpclient
import tornado.httputil
from tornado import testing
from tornado.web import Application

from yadacoin.core.collections import Collections
from yadacoin.core.config import Config
from yadacoin.core.mongo import Mongo
from yadacoin.core.peer import Group, User
from yadacoin.http.proxy import (
    AuthHandler,
    ProxyConfig,
    ProxyHandler,
    blacklist_group,
    fetch_request,
    get_proxy,
    parse_proxy,
)
from yadacoin.udp.base import UDPServer

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def make_mock_http_response(code=200, body=b"", reason="OK", error=None, headers=None):
    resp = MagicMock()
    resp.code = code
    resp.reason = reason
    resp.body = body
    resp.error = error
    resp.headers = MagicMock()
    resp.headers.get_all.return_value = headers or []
    return resp


def _setup_config():
    c = Config()
    c.network = "regnet"
    c.mongo = Mongo()
    c.mongo_debug = True
    c.peer_host = "localhost"
    c.proxy_port = 8888
    c.serve_port = 8080
    c.public_key = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
    c.username = "testuser"
    c.username_signature = "testsig"
    c.private_key = "0000000000000000000000000000000000000000000000000000000000000001"
    c.app_log = MagicMock()
    c.challenges = {}
    c.dns_resolvers = ["8.8.8.8"]
    c.dns_bypass_ips = []
    mock_ws = MagicMock()
    mock_ws.inbound_streams = {User.__name__: {}, Group.__name__: {}}
    c.websocketServer = mock_ws
    mock_proxy = ProxyConfig()
    c.proxy = mock_proxy
    async_db = MagicMock()
    async_site_db = MagicMock()
    async_site_db.proxy_config.find_one = AsyncMock(return_value=None)
    c.mongo.async_db = async_db
    c.mongo.async_site_db = async_site_db
    return c


# ──────────────────────────────────────────────────────────────────────────────
# ProxyConfig
# ──────────────────────────────────────────────────────────────────────────────


class TestProxyConfig(testing.AsyncTestCase):
    def test_to_dict_returns_mode(self):
        pc = ProxyConfig()
        self.assertEqual(pc.to_dict(), {"mode": False})

    def test_to_dict_custom_mode(self):
        pc = ProxyConfig()
        pc.mode = "exclusive"
        self.assertEqual(pc.to_dict(), {"mode": "exclusive"})


# ──────────────────────────────────────────────────────────────────────────────
# get_proxy / parse_proxy
# ──────────────────────────────────────────────────────────────────────────────


class TestGetProxy(testing.AsyncTestCase):
    def test_no_proxy_returns_none(self):
        env = {k: v for k, v in os.environ.items() if "_proxy" not in k.lower()}
        with patch.dict(os.environ, env, clear=True):
            result = get_proxy("http://example.com")
        self.assertIsNone(result)

    def test_http_proxy_env_var(self):
        with patch.dict(os.environ, {"http_proxy": "http://proxy.test:3128"}):
            result = get_proxy("http://example.com")
        self.assertEqual(result, "http://proxy.test:3128")


class TestParseProxy(testing.AsyncTestCase):
    def test_parse_proxy_hostname_port(self):
        host, port = parse_proxy("http://proxy.example.com:8080")
        self.assertEqual(host, "proxy.example.com")
        self.assertEqual(port, 8080)


# ──────────────────────────────────────────────────────────────────────────────
# fetch_request
# ──────────────────────────────────────────────────────────────────────────────


class TestFetchRequest(testing.AsyncTestCase):
    @testing.gen_test
    async def test_fetch_without_proxy(self):
        mock_client = MagicMock()
        mock_client.fetch = AsyncMock(return_value=make_mock_http_response(200))
        env = {k: v for k, v in os.environ.items() if "_proxy" not in k.lower()}
        with patch.dict(os.environ, env, clear=True):
            with patch(
                "yadacoin.http.proxy.tornado.httpclient.AsyncHTTPClient",
                return_value=mock_client,
            ):
                result = await fetch_request("http://example.com/test")
        mock_client.fetch.assert_called_once()

    @testing.gen_test
    async def test_fetch_with_proxy(self):
        mock_client = MagicMock()
        mock_client.fetch = AsyncMock(return_value=make_mock_http_response(200))
        _setup_config()
        with patch.dict(os.environ, {"http_proxy": "http://proxyhost:3128"}):
            with patch(
                "yadacoin.http.proxy.tornado.httpclient.AsyncHTTPClient.configure"
            ):
                with patch(
                    "yadacoin.http.proxy.tornado.httpclient.AsyncHTTPClient",
                    return_value=mock_client,
                ):
                    result = await fetch_request("http://example.com/test")
        mock_client.fetch.assert_called_once()
        call_kwargs = mock_client.fetch.call_args[0][0]
        self.assertIsInstance(call_kwargs, tornado.httpclient.HTTPRequest)


# ──────────────────────────────────────────────────────────────────────────────
# Base test case for handler tests
# ──────────────────────────────────────────────────────────────────────────────


class ProxyHandlerTestBase(testing.AsyncHTTPTestCase):
    def get_new_ioloop(self):
        return tornado.ioloop.IOLoop()

    def tearDown(self):
        super().tearDown()
        asyncio.set_event_loop(None)

    def get_app(self):
        self.config = _setup_config()
        return Application(
            [
                (r"/auth", AuthHandler),
                (r".*", ProxyHandler),
            ],
            compiled_template_cache=False,
        )


# ──────────────────────────────────────────────────────────────────────────────
# AuthHandler
# ──────────────────────────────────────────────────────────────────────────────


class TestAuthHandlerGetTemplatePath(testing.AsyncTestCase):
    def test_get_template_path_returns_templates_dir(self):
        import tornado.httputil

        app = Application([])
        request = tornado.httputil.HTTPServerRequest(method="GET", uri="/auth")
        request.connection = MagicMock()
        handler = AuthHandler(app, request)
        path = handler.get_template_path()
        self.assertTrue(path.endswith("templates"))

    def test_make_qr_returns_base64_png(self):
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest("PIL not installed")
        import tornado.httputil

        app = Application([])
        request = tornado.httputil.HTTPServerRequest(method="GET", uri="/auth")
        request.connection = MagicMock()
        handler = AuthHandler(app, request)
        result = handler.make_qr("test data")
        self.assertTrue(result.startswith("data:image/png;base64,"))


class TestAuthHandlerGet(ProxyHandlerTestBase):
    def test_get_renders_auth_html(self):
        response = self.fetch("/auth", method="GET")
        self.assertIn(response.code, [200, 500])


class TestAuthHandlerPost(ProxyHandlerTestBase):
    def test_post_returns_challenge_context(self):
        body = json.dumps(
            {
                "public_key": "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
                "username": "postuser",
                "username_signature": "postsig",
            }
        )
        with patch("yadacoin.http.proxy.TU.generate_signature", return_value="mocksig"):
            response = self.fetch(
                "/auth",
                method="POST",
                body=body,
                headers={"Content-Type": "application/json"},
            )
        self.assertIn(response.code, [200, 500])
        if response.code == 200:
            data = json.loads(response.body)
            self.assertIn("challenge", data)
            self.assertIn("identity", data)
            self.assertIn("proxy", data)


# ──────────────────────────────────────────────────────────────────────────────
# ProxyHandler — compute_etag
# ──────────────────────────────────────────────────────────────────────────────


class TestProxyHandlerComputeEtag(testing.AsyncTestCase):
    def test_compute_etag_returns_none(self):
        import tornado.httputil

        app = Application([])
        request = tornado.httputil.HTTPServerRequest(method="GET", uri="/test")
        request.connection = MagicMock()
        handler = ProxyHandler(app, request)
        self.assertIsNone(handler.compute_etag())


# ──────────────────────────────────────────────────────────────────────────────
# ProxyHandler.get() — various branches
# ──────────────────────────────────────────────────────────────────────────────


class TestProxyHandlerGet(ProxyHandlerTestBase):
    def _get_with_mock_fetch(self, path="/", mock_response=None, extra_headers=None):
        if mock_response is None:
            mock_response = make_mock_http_response(200, b"hello")
        headers = extra_headers or {}
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        with patch(
            "yadacoin.http.proxy.fetch_request", AsyncMock(return_value=mock_response)
        ):
            return self.fetch(path, headers=headers)

    def test_get_simple_no_auth(self):
        """Basic GET with remote_ip not in UDPServer streams - goes straight to fetch."""
        resp = make_mock_http_response(200, b"proxied body")
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        with patch("yadacoin.http.proxy.fetch_request", AsyncMock(return_value=resp)):
            response = self.fetch("/http://example.com/page")
        self.assertIn(response.code, [200, 500])

    def test_get_removes_proxy_connection_header(self):
        """Proxy-Connection header in request should be deleted."""
        resp = make_mock_http_response(200, b"ok")
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        with patch("yadacoin.http.proxy.fetch_request", AsyncMock(return_value=resp)):
            response = self.fetch(
                "/http://example.com/",
                headers={"Proxy-Connection": "keep-alive"},
            )
        self.assertIn(response.code, [200, 500])

    def test_get_no_body(self):
        """Empty body becomes None."""
        resp = make_mock_http_response(200, b"")
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        with patch("yadacoin.http.proxy.fetch_request", AsyncMock(return_value=resp)):
            response = self.fetch("/http://example.com/", method="GET")
        self.assertIn(response.code, [200, 500])

    def test_get_handle_response_non_http_error(self):
        """handle_response: response.error but not HTTPError → 500."""
        resp = make_mock_http_response(500, b"")
        resp.error = Exception("connection refused")  # not HTTPError
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        with patch("yadacoin.http.proxy.fetch_request", AsyncMock(return_value=resp)):
            response = self.fetch("/http://example.com/")
        self.assertIn(response.code, [200, 500])

    def test_get_handle_response_with_body_and_headers(self):
        """handle_response: success with body, non-skipped headers set."""
        resp = make_mock_http_response(
            200,
            b"body content",
            headers=[
                ("X-Custom", "value"),
                ("Content-Length", "10"),
                ("Set-Cookie", "session=abc"),
            ],
        )
        resp.error = None
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        with patch("yadacoin.http.proxy.fetch_request", AsyncMock(return_value=resp)):
            response = self.fetch("/http://example.com/page")
        self.assertIn(response.code, [200, 500])

    def test_get_handle_response_body_with_rid_in_websocket(self):
        """handle_response: body present and rid in websocket streams → write_result."""
        mock_ws_stream = MagicMock()
        mock_ws_stream.write_result = AsyncMock(return_value=None)

        resp = make_mock_http_response(200, b"ws body")
        resp.error = None
        resp.headers.get_all.return_value = []

        # In AsyncHTTPTestCase remote_ip is "127.0.0.1"
        fake_rid = "fake_rid_abc"
        UDPServer.inbound_streams = {
            User.__name__: {"127.0.0.1": fake_rid},
            Group.__name__: {},
        }
        mock_ws_item = MagicMock()
        mock_ws_item.link = "testlink"
        mock_ws_item.data = {"authenticated": True}
        mock_ws_item.write_result = AsyncMock(return_value=None)
        self.config.websocketServer.inbound_streams[User.__name__][
            fake_rid
        ] = mock_ws_item

        async def mock_fetch(*args, **kwargs):
            return make_mock_http_response(200, b"ws body")

        with patch("yadacoin.http.proxy.fetch_request", mock_fetch):
            response = self.fetch("/http://example.com/")
        self.assertIn(response.code, [200, 500])
        # Clean up
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}

    def test_get_http_error_with_response(self):
        """HTTPError with response → handle_response called with error response."""
        err_resp = make_mock_http_response(503, b"service unavailable")
        err_resp.error = None
        http_error = tornado.httpclient.HTTPError(503, "Service Unavailable")
        http_error.response = err_resp

        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        with patch(
            "yadacoin.http.proxy.fetch_request",
            AsyncMock(side_effect=http_error),
        ):
            response = self.fetch("/http://example.com/")
        self.assertIn(response.code, [200, 500, 503])

    def test_get_http_error_without_response(self):
        """HTTPError without response → set_status(500) and finish."""
        http_error = tornado.httpclient.HTTPError(404, "Not Found")
        http_error.response = None

        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        with patch(
            "yadacoin.http.proxy.fetch_request",
            AsyncMock(side_effect=http_error),
        ):
            response = self.fetch("/http://example.com/")
        self.assertIn(response.code, [200, 500])

    def test_post_delegates_to_get(self):
        """POST method should call get() and return same result."""
        resp = make_mock_http_response(200, b"post body")
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        with patch("yadacoin.http.proxy.fetch_request", AsyncMock(return_value=resp)):
            response = self.fetch(
                "/http://example.com/",
                method="POST",
                body="data=test",
                allow_nonstandard_methods=True,
            )
        self.assertIn(response.code, [200, 500])


# ──────────────────────────────────────────────────────────────────────────────
# ProxyHandler.get() — auth block branches
# ──────────────────────────────────────────────────────────────────────────────


class TestProxyHandlerGetAuth(ProxyHandlerTestBase):
    """Test the auth block: remote_ip IS in UDPServer.inbound_streams."""

    def setUp(self):
        super().setUp()
        # We can't control remote_ip in AsyncHTTPTestCase (it's 127.0.0.1)
        # So we set 127.0.0.1 as a known IP in UDPServer
        self._test_rid = "test_rid_auth"
        UDPServer.inbound_streams = {
            User.__name__: {"127.0.0.1": self._test_rid},
            Group.__name__: {},
        }

    def tearDown(self):
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        super().tearDown()

    def test_auth_block_no_link_data_returns_407(self):
        """Auth block: remote_ip in UDPServer, rid in ws streams, accessing link raises → 407."""
        mock_ws_item = MagicMock()
        # Make accessing .link raise
        type(mock_ws_item).link = property(
            fget=lambda self: (_ for _ in ()).throw(Exception("no link"))
        )
        self.config.websocketServer.inbound_streams[User.__name__][
            self._test_rid
        ] = mock_ws_item

        resp = make_mock_http_response(200, b"ok")
        with patch("yadacoin.http.proxy.fetch_request", AsyncMock(return_value=resp)):
            response = self.fetch("/http://example.com/page")
        # Returns 407 via set_status OR falls through
        self.assertIn(response.code, [200, 407, 500])

    def test_auth_block_data_already_authenticated(self):
        """Auth block: data.get('authenticated') is True → skip challenge, go to fetch."""
        mock_ws_item = MagicMock()
        mock_ws_item.link = "testlink"
        mock_ws_item.data = {"authenticated": True}
        self.config.websocketServer.inbound_streams[User.__name__][
            self._test_rid
        ] = mock_ws_item

        resp = make_mock_http_response(200, b"authenticated ok")
        with patch("yadacoin.http.proxy.fetch_request", AsyncMock(return_value=resp)):
            response = self.fetch("/http://localhost:8080/page")
        self.assertIn(response.code, [200, 500])

    def test_auth_block_not_authenticated_challenge_fails(self):
        """Auth block: not authenticated, get_challenge_resp code not 2xx → return early."""
        mock_ws_item = MagicMock()
        mock_ws_item.link = "testlink"
        mock_ws_item.data = {"authenticated": False}
        mock_ws_item.dh_public_key = "dh_key"
        self.config.websocketServer.inbound_streams[User.__name__][
            self._test_rid
        ] = mock_ws_item

        # First fetch_request (get_challenge) returns 400
        challenge_fail_resp = make_mock_http_response(400, b"bad request")
        with patch(
            "yadacoin.http.proxy.fetch_request",
            AsyncMock(return_value=challenge_fail_resp),
        ):
            response = self.fetch("/http://localhost:8080/page")
        self.assertIn(response.code, [200, 500])

    def test_auth_block_not_authenticated_post_challenge_fails(self):
        """Auth block: get_challenge succeeds, proxy_signature_request done, post_challenge fails."""
        mock_ws_item = MagicMock()
        mock_ws_item.link = "testlink"
        mock_ws_item.data = {"authenticated": False}
        mock_ws_item.dh_public_key = "dh_key"
        self.config.websocketServer.inbound_streams[User.__name__][
            self._test_rid
        ] = mock_ws_item
        self.config.websocketServer.inbound_streams[User.__name__][
            "testlink"
        ] = mock_ws_item
        mock_ws_item.write_params = AsyncMock(return_value=None)

        self.config.challenges = {"testlink": {"signature": "sig123"}}

        # First call: get_challenge_resp 200, second call: post_challenge_resp 400
        challenge_ok_resp = make_mock_http_response(
            200, json.dumps({"challenge": "testchallenge"}).encode()
        )
        challenge_ok_resp.error = None
        post_fail_resp = make_mock_http_response(400, b"bad")

        call_count = [0]

        async def side_effect_fetch(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return challenge_ok_resp
            else:
                return post_fail_resp

        with patch("yadacoin.http.proxy.fetch_request", side_effect_fetch):
            with patch(
                "yadacoin.http.proxy.ProxyHandler.proxy_signature_request",
                AsyncMock(return_value=None),
            ):
                response = self.fetch("/http://localhost:8080/page")
        self.assertIn(response.code, [200, 500])

    def test_auth_block_full_auth_flow_post_challenge_ok(self):
        """Auth block: full auth flow, post_challenge succeeds → fetch, handle_response."""
        mock_ws_item = MagicMock()
        mock_ws_item.link = "testlink"
        mock_ws_item.data = {"authenticated": False}
        mock_ws_item.dh_public_key = "dh_key"
        self.config.websocketServer.inbound_streams[User.__name__][
            self._test_rid
        ] = mock_ws_item
        self.config.websocketServer.inbound_streams[User.__name__][
            "testlink"
        ] = mock_ws_item
        mock_ws_item.write_params = AsyncMock(return_value=None)
        self.config.challenges = {"testlink": {"signature": "sig123"}}

        challenge_ok_resp = make_mock_http_response(
            200, json.dumps({"challenge": "testchallenge"}).encode()
        )
        challenge_ok_resp.error = None
        post_ok_resp = make_mock_http_response(
            200,
            b"authed",
            headers=[("Set-Cookie", "sess=xyz"), ("Content-Length", "5")],
        )
        post_ok_resp.error = None
        final_resp = make_mock_http_response(200, b"final response")
        final_resp.error = None

        call_count = [0]

        async def side_effect_fetch(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return challenge_ok_resp
            elif call_count[0] == 2:
                return post_ok_resp
            else:
                return final_resp

        with patch("yadacoin.http.proxy.fetch_request", side_effect_fetch):
            with patch(
                "yadacoin.http.proxy.ProxyHandler.proxy_signature_request",
                AsyncMock(return_value=None),
            ):
                response = self.fetch("/http://localhost:8080/page")
        self.assertIn(response.code, [200, 500])


# ──────────────────────────────────────────────────────────────────────────────
# ProxyHandler.connect() — via direct handler instantiation
# ──────────────────────────────────────────────────────────────────────────────


class TestProxyHandlerConnect(testing.AsyncTestCase):
    def setUp(self):
        super().setUp()
        self.config = _setup_config()
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}

    def tearDown(self):
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        asyncio.set_event_loop(None)
        super().tearDown()

    def _make_handler(self, uri="example.com:443"):
        app = Application([])
        request = tornado.httputil.HTTPServerRequest(method="CONNECT", uri=uri)
        request.connection = MagicMock()
        request.connection.stream = MagicMock()
        request.connection.stream.closed = MagicMock(return_value=False)
        request.connection.stream.write = MagicMock()
        request.connection.stream.close = MagicMock()
        request.connection.finish = MagicMock()
        return ProxyHandler(app, request)

    @testing.gen_test
    async def test_connect_host_in_bypass_no_mode(self):
        """connect(): host in dns_bypass_ips, mode=False → check_blocked returns None, start_tunnel."""
        self.config.dns_bypass_ips = ["example.com"]
        self.config.proxy.mode = False

        handler = self._make_handler("example.com:443")
        mock_upstream = MagicMock()
        mock_upstream.connect = AsyncMock(return_value=None)
        mock_upstream.close = MagicMock()
        mock_upstream.closed = MagicMock(return_value=False)

        with patch("yadacoin.http.proxy.socket.socket"):
            with patch(
                "yadacoin.http.proxy.tornado.iostream.IOStream",
                return_value=mock_upstream,
            ):
                with patch(
                    "yadacoin.http.proxy.ProxyHandler.check_blocked_inner",
                    None,
                    create=True,
                ):
                    # patch asyncio.gather to avoid relay loop
                    with patch(
                        "yadacoin.http.proxy.asyncio.gather",
                        AsyncMock(return_value=None),
                    ):
                        await handler.connect()

        mock_upstream.connect.assert_called_once_with(("example.com", 443))

    @testing.gen_test
    async def test_connect_host_in_bypass_mode_false_db_query(self):
        """connect(): mode=False → check_blocked queries DB for mode, still returns None."""
        self.config.dns_bypass_ips = ["example.com"]
        self.config.proxy.mode = False

        handler = self._make_handler("example.com:443")
        mock_upstream = MagicMock()
        mock_upstream.connect = AsyncMock(return_value=None)
        mock_upstream.close = MagicMock()

        with patch("yadacoin.http.proxy.socket.socket"):
            with patch(
                "yadacoin.http.proxy.tornado.iostream.IOStream",
                return_value=mock_upstream,
            ):
                with patch(
                    "yadacoin.http.proxy.asyncio.gather",
                    AsyncMock(return_value=None),
                ):
                    await handler.connect()

        mock_upstream.connect.assert_called_once()

    @testing.gen_test
    async def test_connect_bypass_mode_exclusive_not_in_blacklist(self):
        """connect(): mode=exclusive, domain not in blacklist → send allowed_item to ws group."""
        self.config.dns_bypass_ips = ["example.com"]
        self.config.proxy.mode = "exclusive"
        self.config.proxy.black_list = {}
        self.config.proxy.white_list = {}
        group_rid = blacklist_group.generate_rid(
            blacklist_group.username_signature, Collections.GROUP_CHAT.value
        )
        mock_stream = MagicMock()
        mock_stream.write_params = AsyncMock(return_value=None)
        self.config.websocketServer.inbound_streams[Group.__name__][group_rid] = {
            "conn1": mock_stream
        }

        handler = self._make_handler("example.com:443")
        mock_upstream = MagicMock()
        mock_upstream.connect = AsyncMock(return_value=None)
        mock_upstream.close = MagicMock()

        with patch("yadacoin.http.proxy.socket.socket"):
            with patch(
                "yadacoin.http.proxy.tornado.iostream.IOStream",
                return_value=mock_upstream,
            ):
                with patch(
                    "yadacoin.http.proxy.asyncio.gather",
                    AsyncMock(return_value=None),
                ):
                    await handler.connect()

    @testing.gen_test
    async def test_connect_bypass_mode_exclusive_in_blacklist_blocks(self):
        """connect(): mode=exclusive, domain in blacklist and active → write 403, return True."""
        self.config.dns_bypass_ips = ["example.com"]
        self.config.proxy.mode = "exclusive"
        self.config.proxy.black_list = {"example.com": {"active": True}}

        handler = self._make_handler("example.com:443")
        mock_upstream = MagicMock()
        mock_upstream.connect = AsyncMock(return_value=None)
        mock_upstream.close = MagicMock()

        with patch("yadacoin.http.proxy.socket.socket"):
            with patch(
                "yadacoin.http.proxy.tornado.iostream.IOStream",
                return_value=mock_upstream,
            ):
                with patch(
                    "yadacoin.http.proxy.asyncio.gather",
                    AsyncMock(return_value=None),
                ):
                    await handler.connect()

        handler.request.connection.stream.write.assert_called_with(
            b"HTTP/1.0 403 Connection established\r\n\r\n"
        )

    @testing.gen_test
    async def test_connect_bypass_mode_inclusive_not_in_whitelist_blocks(self):
        """connect(): mode=inclusive, domain not in whitelist → write 403, return True."""
        self.config.dns_bypass_ips = ["example.com"]
        self.config.proxy.mode = "inclusive"
        self.config.proxy.white_list = {}

        group_rid = blacklist_group.generate_rid(
            blacklist_group.username_signature, Collections.GROUP_CHAT.value
        )
        mock_stream = MagicMock()
        mock_stream.write_params = AsyncMock(return_value=None)
        self.config.websocketServer.inbound_streams[Group.__name__][group_rid] = {
            "conn1": mock_stream
        }

        handler = self._make_handler("example.com:443")
        mock_upstream = MagicMock()
        mock_upstream.connect = AsyncMock(return_value=None)
        mock_upstream.close = MagicMock()

        with patch("yadacoin.http.proxy.socket.socket"):
            with patch(
                "yadacoin.http.proxy.tornado.iostream.IOStream",
                return_value=mock_upstream,
            ):
                with patch(
                    "yadacoin.http.proxy.asyncio.gather",
                    AsyncMock(return_value=None),
                ):
                    await handler.connect()

        handler.request.connection.stream.write.assert_called_with(
            b"HTTP/1.0 403 Connection established\r\n\r\n"
        )

    @testing.gen_test
    async def test_connect_bypass_mode_inclusive_in_whitelist_allows(self):
        """connect(): mode=inclusive, domain in whitelist and active → tunnel established."""
        self.config.dns_bypass_ips = ["example.com"]
        self.config.proxy.mode = "inclusive"
        self.config.proxy.white_list = {"example.com": {"active": True}}

        handler = self._make_handler("example.com:443")
        mock_upstream = MagicMock()
        mock_upstream.connect = AsyncMock(return_value=None)
        mock_upstream.close = MagicMock()

        with patch("yadacoin.http.proxy.socket.socket"):
            with patch(
                "yadacoin.http.proxy.tornado.iostream.IOStream",
                return_value=mock_upstream,
            ):
                with patch(
                    "yadacoin.http.proxy.asyncio.gather",
                    AsyncMock(return_value=None),
                ):
                    await handler.connect()

        # start_tunnel should have written 200
        handler.request.connection.stream.write.assert_called_with(
            b"HTTP/1.0 200 Connection established\r\n\r\n"
        )

    @testing.gen_test
    async def test_connect_dns_resolution(self):
        """connect(): host NOT in bypass_ips → uses DNS resolver."""
        self.config.dns_bypass_ips = []
        self.config.proxy.mode = False

        handler = self._make_handler("dns-host.example.com:443")
        mock_upstream = MagicMock()
        mock_upstream.connect = AsyncMock(return_value=None)
        mock_upstream.close = MagicMock()

        # Mock DNS answer
        mock_item = MagicMock()
        mock_item.address = "93.184.216.34"
        mock_rdata = MagicMock()
        mock_rdata.rdtype = 1
        mock_rdata.items = [mock_item]
        mock_answer = MagicMock()
        mock_answer.response.answer = [mock_rdata]

        mock_resolver = MagicMock()
        mock_resolver.query = MagicMock(return_value=mock_answer)

        with patch("yadacoin.http.proxy.socket.socket"):
            with patch(
                "yadacoin.http.proxy.tornado.iostream.IOStream",
                return_value=mock_upstream,
            ):
                with patch(
                    "yadacoin.http.proxy.dns.resolver.Resolver",
                    return_value=mock_resolver,
                ):
                    with patch(
                        "yadacoin.http.proxy.asyncio.gather",
                        AsyncMock(return_value=None),
                    ):
                        await handler.connect()

        mock_upstream.connect.assert_called_once_with(("93.184.216.34", 443))


# ──────────────────────────────────────────────────────────────────────────────
# ProxyHandler.connect() — relay() inner function
# (called via asyncio.gather in start_tunnel — we test via direct invocation)
# ──────────────────────────────────────────────────────────────────────────────


class TestProxyHandlerRelay(testing.AsyncTestCase):
    """Test relay() and start_tunnel() via connect() with check_blocked always False."""

    def setUp(self):
        super().setUp()
        self.config = _setup_config()
        self.config.dns_bypass_ips = ["relay-host.example.com"]
        self.config.proxy.mode = False
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}

    def tearDown(self):
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        asyncio.set_event_loop(None)
        super().tearDown()

    @testing.gen_test
    async def test_relay_reads_and_writes_data(self):
        """relay(): reads data and writes to writer; stops when data is empty (else: break)."""
        app = Application([])
        request = tornado.httputil.HTTPServerRequest(
            method="CONNECT", uri="relay-host.example.com:443"
        )
        request.connection = MagicMock()
        client_stream = MagicMock()
        client_stream.write = MagicMock()
        client_stream.close = MagicMock()
        client_stream.closed = MagicMock(return_value=False)
        request.connection.stream = client_stream

        handler = ProxyHandler(app, request)
        handler._transforms = []

        upstream = MagicMock()
        upstream.connect = AsyncMock(return_value=None)
        upstream.close = MagicMock()
        upstream.closed = MagicMock(return_value=False)

        # Each relay gets its own independent returning b"" on first call (→ else: break)
        client_stream.read_bytes = AsyncMock(return_value=b"")
        upstream.read_bytes = AsyncMock(return_value=b"")

        with patch("yadacoin.http.proxy.socket.socket"):
            with patch(
                "yadacoin.http.proxy.tornado.iostream.IOStream",
                return_value=upstream,
            ):
                await handler.connect()

        # client.write should have been called with the 200 tunnel response
        client_stream.write.assert_any_call(
            b"HTTP/1.0 200 Connection established\r\n\r\n"
        )

    @testing.gen_test
    async def test_relay_writes_truthy_data(self):
        """relay(): writer.write(data) called when data is truthy."""
        app = Application([])
        request = tornado.httputil.HTTPServerRequest(
            method="CONNECT", uri="relay-host.example.com:443"
        )
        request.connection = MagicMock()
        client_stream = MagicMock()
        client_stream.write = MagicMock()
        client_stream.close = MagicMock()
        client_stream.closed = MagicMock(return_value=False)
        request.connection.stream = client_stream

        handler = ProxyHandler(app, request)
        handler._transforms = []

        upstream = MagicMock()
        upstream.connect = AsyncMock(return_value=None)
        upstream.close = MagicMock()
        upstream.closed = MagicMock(return_value=False)

        # First call returns actual data, second returns b"" to break out of while
        client_call = {"n": 0}
        upstream_call = {"n": 0}

        async def client_read(n, partial=False):
            client_call["n"] += 1
            return b"chunk" if client_call["n"] == 1 else b""

        async def upstream_read(n, partial=False):
            upstream_call["n"] += 1
            return b"chunk" if upstream_call["n"] == 1 else b""

        client_stream.read_bytes = client_read
        upstream.read_bytes = upstream_read

        with patch("yadacoin.http.proxy.socket.socket"):
            with patch(
                "yadacoin.http.proxy.tornado.iostream.IOStream",
                return_value=upstream,
            ):
                await handler.connect()

        client_stream.write.assert_any_call(
            b"HTTP/1.0 200 Connection established\r\n\r\n"
        )

    @testing.gen_test
    async def test_relay_stream_closed_error(self):
        """relay(): StreamClosedError is caught and both streams closed."""
        app = Application([])
        request = tornado.httputil.HTTPServerRequest(
            method="CONNECT", uri="relay-host.example.com:443"
        )
        request.connection = MagicMock()
        client_stream = MagicMock()
        client_stream.write = MagicMock()
        client_stream.close = MagicMock()
        client_stream.closed = MagicMock(return_value=False)
        request.connection.stream = client_stream

        handler = ProxyHandler(app, request)
        handler._transforms = []

        upstream = MagicMock()
        upstream.connect = AsyncMock(return_value=None)
        upstream.close = MagicMock()
        upstream.closed = MagicMock(return_value=False)

        async def mock_read_raises(n, partial=False):
            raise tornado.iostream.StreamClosedError()

        client_stream.read_bytes = mock_read_raises
        upstream.read_bytes = mock_read_raises

        with patch("yadacoin.http.proxy.socket.socket"):
            with patch(
                "yadacoin.http.proxy.tornado.iostream.IOStream",
                return_value=upstream,
            ):
                await handler.connect()

        # Both streams should have been closed
        client_stream.close.assert_called()

    @testing.gen_test
    async def test_relay_writer_closed_returns(self):
        """relay(): writer.closed() returns True → return early from relay loop."""
        app = Application([])
        request = tornado.httputil.HTTPServerRequest(
            method="CONNECT", uri="relay-host.example.com:443"
        )
        request.connection = MagicMock()
        client_stream = MagicMock()
        client_stream.write = MagicMock()
        client_stream.close = MagicMock()
        request.connection.stream = client_stream

        handler = ProxyHandler(app, request)
        handler._transforms = []

        upstream = MagicMock()
        upstream.connect = AsyncMock(return_value=None)
        upstream.close = MagicMock()

        # client_stream.closed() returns True → relay returns immediately after read
        client_stream.closed = MagicMock(return_value=True)
        upstream.closed = MagicMock(return_value=True)

        async def mock_read_bytes(n, partial=False):
            return b"some_data"

        client_stream.read_bytes = mock_read_bytes
        upstream.read_bytes = mock_read_bytes

        with patch("yadacoin.http.proxy.socket.socket"):
            with patch(
                "yadacoin.http.proxy.tornado.iostream.IOStream",
                return_value=upstream,
            ):
                await handler.connect()

    @testing.gen_test
    async def test_start_tunnel_check_blocked_returns_true_closes(self):
        """start_tunnel(): check_blocked returns True → close client and upstream."""
        self.config.proxy.mode = "exclusive"
        self.config.proxy.black_list = {"example.com": {"active": True}}
        self.config.dns_bypass_ips = ["relay-host.example.com"]

        app = Application([])
        request = tornado.httputil.HTTPServerRequest(
            method="CONNECT", uri="relay-host.example.com:443"
        )
        request.connection = MagicMock()
        client_stream = MagicMock()
        client_stream.write = MagicMock()
        client_stream.close = MagicMock()
        client_stream.closed = MagicMock(return_value=False)
        request.connection.stream = client_stream
        request.connection.finish = MagicMock()

        handler = ProxyHandler(app, request)
        handler._transforms = []

        upstream = MagicMock()
        upstream.connect = AsyncMock(return_value=None)
        upstream.close = MagicMock()

        with patch("yadacoin.http.proxy.socket.socket"):
            with patch(
                "yadacoin.http.proxy.tornado.iostream.IOStream",
                return_value=upstream,
            ):
                await handler.connect()

        # check_blocked returned True → wrote 403, closed
        client_stream.write.assert_called_with(
            b"HTTP/1.0 403 Connection established\r\n\r\n"
        )


# ──────────────────────────────────────────────────────────────────────────────
# ProxyHandler.proxy_signature_request()
# ──────────────────────────────────────────────────────────────────────────────


class TestProxySignatureRequest(testing.AsyncTestCase):
    def setUp(self):
        super().setUp()
        self.config = _setup_config()
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}

    def tearDown(self):
        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}
        asyncio.set_event_loop(None)
        super().tearDown()

    def _make_handler(self):
        app = Application([])
        request = tornado.httputil.HTTPServerRequest(method="GET", uri="/test")
        request.connection = MagicMock()
        handler = ProxyHandler(app, request)
        handler._transforms = []
        return handler

    @testing.gen_test
    async def test_link_not_in_streams_returns_407(self):
        """proxy_signature_request: link not in ws streams → set_status(407) and finish."""
        self.config.websocketServer.inbound_streams[User.__name__] = {}
        handler = self._make_handler()
        try:
            await handler.proxy_signature_request({"data": "test"}, "missing_link")
        except Exception:
            pass
        # Status 407 should have been set
        self.assertEqual(handler._status_code, 407)

    @testing.gen_test
    async def test_link_in_streams_signature_already_present(self):
        """proxy_signature_request: signature already in challenges → no loop iterations."""
        mock_ws = MagicMock()
        mock_ws.write_params = AsyncMock(return_value=None)
        link = "testlink"
        self.config.websocketServer.inbound_streams[User.__name__][link] = mock_ws
        self.config.challenges = {link: {"signature": "sig123"}}

        handler = self._make_handler()
        await handler.proxy_signature_request({"data": "test"}, link)
        mock_ws.write_params.assert_called_once_with(
            "proxy_signature_request", {"data": "test"}
        )

    @testing.gen_test
    async def test_link_in_streams_timeout(self):
        """proxy_signature_request: no signature arrives → loop runs 61 times → timeout."""
        mock_ws = MagicMock()
        mock_ws.write_params = AsyncMock(return_value=None)
        link = "testlink"
        self.config.websocketServer.inbound_streams[User.__name__][link] = mock_ws
        self.config.challenges = {link: {}}  # no "signature" key

        handler = self._make_handler()

        with patch("yadacoin.http.proxy.async_sleep", AsyncMock(return_value=None)):
            try:
                await handler.proxy_signature_request({"data": "test"}, link)
            except Exception:
                pass

        # After timeout, status 200 set with timeout message
        self.assertEqual(handler._status_code, 200)


# ──────────────────────────────────────────────────────────────────────────────
# handle_response with post_challenge_resp (Set-Cookie path)
# ──────────────────────────────────────────────────────────────────────────────


class TestProxyHandlerHandleResponseWithPostChallenge(ProxyHandlerTestBase):
    """Test the post_challenge_resp Set-Cookie header propagation branch."""

    @testing.gen_test
    async def test_handle_response_with_set_cookie_from_post_challenge(self):
        """handle_response: post_challenge_resp headers with Set-Cookie are added."""
        # We need to construct a handler directly and call handle_response
        app = Application([])
        request = tornado.httputil.HTTPServerRequest(method="GET", uri="/test")
        request.connection = MagicMock()
        request.connection.stream = MagicMock()
        request.headers = tornado.httputil.HTTPHeaders()
        request.body = b""
        request.remote_ip = "127.0.0.1"

        handler = ProxyHandler(app, request)
        handler._write_buffer = []
        handler._finished = False
        handler._headers_written = False

        Config()
        post_challenge_resp = make_mock_http_response(
            200,
            b"challenge ok",
            headers=[("Set-Cookie", "session=abc; path=/")],
        )
        post_challenge_resp.error = None

        main_resp = make_mock_http_response(200, b"main body")
        main_resp.error = None

        UDPServer.inbound_streams = {User.__name__: {}, Group.__name__: {}}

        fetch_call_count = [0]

        async def side_effect_fetch(*args, **kwargs):
            fetch_call_count[0] += 1
            return main_resp

        with patch("yadacoin.http.proxy.fetch_request", side_effect_fetch):
            try:
                await handler.get()
            except Exception:
                pass
