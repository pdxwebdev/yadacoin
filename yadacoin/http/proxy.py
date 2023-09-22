#!/usr/bin/env python
#
# Simple asynchronous HTTP proxy with tunnelling (CONNECT).
#
# GET/POST proxying based on
# http://groups.google.com/group/python-tornado/msg/7bea08e7a049cf26
#
# Copyright (C) 2012 Senko Rasic <senko.rasic@dobarkod.hr>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import asyncio
import base64
import json
import os
import socket
import sys
import uuid
from asyncio import sleep as async_sleep
from io import BytesIO
from socketserver import UDPServer
from time import time

import qrcode

if sys.version_info[0] == 2:
    from urlparse import urlparse
else:
    from urllib.parse import urlparse

import dns.resolver
import tornado.httpclient
import tornado.httpserver
import tornado.httputil
import tornado.ioloop
import tornado.iostream
import tornado.web

from yadacoin.core.collections import Collections
from yadacoin.core.config import Config
from yadacoin.core.identity import Identity
from yadacoin.core.peer import Group, User
from yadacoin.core.transactionutils import TU
from yadacoin.udp.base import UDPServer

__all__ = ["ProxyHandler"]
whitelist_group = Identity.from_dict(
    {
        "public_key": "03c68f337dc3a78efd8c9801d989edbc7cd03b67381e8836cc6b81e59998f338ae",
        "username": "proxy_whitelist",
        "username_signature": "MEUCIQCYIJ8Ko+LUYPlOrapnB/ULCzInRTyVxLPHjNqIriVcsgIgPHmSW+qnimsA+AWDo/Omouulx+nymMtGPQ362vvgIW8=",
        "wif": "L5StyB39tftmH5r83o26iUVXBQHNsgN7Mf8uyU9x9DVhHBP5vdEA",
    }
)
blacklist_group = Identity.from_dict(
    {
        "public_key": "02541da5105b05682013c51e09389042809d8fd16dcaaaba30a358ddf45027d1b5",
        "username": "proxy_blacklist",
        "username_signature": "MEQCID9KVtd8H0pMq3qCwGt6j765TX+Duip9Ujr7q7D2kRw/AiBbq8136Gk4WCuzwlZ62UXCwQGuhNH+RtJZlHSd6zoBnA==",
        "wif": "L5h5LnUzSJygwxTvJP9wgRdpkJGBSuZP6UsqYqZTqH8BkLQ5SWDf",
    }
)


class ProxyConfig:
    mode = False
    white_list = {}
    black_list = {}

    def to_dict(self):
        return {"mode": self.mode}


def get_proxy(url):
    url_parsed = urlparse(url, scheme="http")
    proxy_key = "%s_proxy" % url_parsed.scheme
    return os.environ.get(proxy_key)


def parse_proxy(proxy):
    proxy_parsed = urlparse(proxy, scheme="http")
    return proxy_parsed.hostname, proxy_parsed.port


def fetch_request(url, **kwargs):
    proxy = get_proxy(url)
    if proxy:
        Config().app_log.debug("Forward request via upstream proxy %s", proxy)
        tornado.httpclient.AsyncHTTPClient.configure(
            "tornado.curl_httpclient.CurlAsyncHTTPClient"
        )
        host, port = parse_proxy(proxy)
        kwargs["proxy_host"] = host
        kwargs["proxy_port"] = port

    req = tornado.httpclient.HTTPRequest(url, **kwargs)
    client = tornado.httpclient.AsyncHTTPClient()
    return client.fetch(req, raise_error=False)


class AuthHandler(tornado.web.RequestHandler):
    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "..", "..", "templates")

    def make_qr(self, data):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        out = BytesIO()
        qr_img = qr.make_image()
        qr_img = qr_img.convert("RGBA")
        qr_img.save(out, "PNG")
        out.seek(0)
        return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()

    async def get(self):
        config = Config()
        return self.render(
            "auth.html",
            proxy_address=f"{config.peer_host}:{config.proxy_port}",
            http_address=f"{config.peer_host}:{config.serve_port}",
        )

    async def post(self):
        data = json.loads(self.request.body)
        user_identity = Identity.from_dict(data)
        config = Config()
        challenge = str(uuid.uuid4())
        challenge_signature = TU.generate_signature(challenge, config.private_key)
        url = f"{config.peer_host}:{config.serve_port}/websocket"
        url_signature = TU.generate_signature(url, config.private_key)
        server_identity = Identity.from_dict(
            {
                "public_key": config.public_key,
                "username": config.username,
                "username_signature": config.username_signature,
            }
        )
        rid = server_identity.generate_rid(user_identity.username_signature)
        context = {
            "identity": {
                "public_key": config.public_key,
                "username": config.username,
                "username_signature": config.username_signature,
            },
            "challenge": {"message": challenge, "signature": challenge_signature},
            "url": {"message": url, "signature": url_signature},
            "proxy": f"{rid[:32]}.{rid[32:]}.yadaproxy",
        }
        return self.write(json.dumps(context))


class ProxyHandler(tornado.web.RequestHandler):
    SUPPORTED_METHODS = ["GET", "POST", "CONNECT"]

    def compute_etag(self):
        return None  # disable tornado Etag

    async def get(self):
        config = Config()
        config.app_log.debug(
            "Handle %s request to %s", self.request.method, self.request.uri
        )
        rid = None
        post_challenge_resp = None

        async def handle_response(response):
            if response.error and not isinstance(
                response.error, tornado.httpclient.HTTPError
            ):
                self.set_status(500)
                self.write("Internal server error:\n" + str(response.error))
            else:
                self.set_status(response.code, response.reason)
                self._headers = (
                    tornado.httputil.HTTPHeaders()
                )  # clear tornado default header

                for header, v in response.headers.get_all():
                    if header not in (
                        "Content-Length",
                        "Transfer-Encoding",
                        "Content-Encoding",
                        "Connection",
                    ):
                        self.clear_header(header)
                        self.add_header(
                            header, v
                        )  # some header appear multiple times, eg 'Set-Cookie'
                if post_challenge_resp:
                    for header, v in post_challenge_resp.headers.get_all():
                        if header == "Set-Cookie":
                            self.add_header(
                                header, v
                            )  # some header appear multiple times, eg 'Set-Cookie'

                # if 'Proxy-Authorization' in self.request.headers:
                #     self.clear_header('Authorization')
                #     self.add_header('Authorization', v)
                # 1. generate qr code with challenge embedded, (do not put this challenge in the hash as it can be used by anyone. The first to sign it, claims it)
                # 2. alias browser client should open a websocket and be ready to receive a new challenge
                # 3. redirect with challenge in url as #hash value (this will persist the challenge on refresh)
                # 4. when a new challenge is received, change challenge hash value in url
                # 5. all refreshes or further actions on this page will also transmit this challenge
                # 6.

                # hold connection response until we get approval from identity device
                # while not ws_response:
                #     await async_sleep(.1)

                # self.add_header('Authorization', ws_response.challenge_signature)

                if response.body:
                    if rid in config.websocketServer.inbound_streams[User.__name__]:
                        self.finish()
                        await config.websocketServer.inbound_streams[User.__name__][
                            rid
                        ].write_result(
                            "content_response", {"cont]ent": response.body.decode()}
                        )
                        return
                    self.set_header("Content-Length", len(response.body))
                    self.write(response.body)
            self.finish()

        body = self.request.body
        if not body:
            body = None
        try:
            if "Proxy-Connection" in self.request.headers:
                del self.request.headers["Proxy-Connection"]
            rid = UDPServer.inbound_streams[User.__name__].get(self.request.remote_ip)
            if (
                self.request.remote_ip in UDPServer.inbound_streams[User.__name__]
                and rid in config.websocketServer.inbound_streams[User.__name__]
                and self.request.uri
                != f"http://{config.peer_host}:{config.proxy_port}/auth"
            ):
                # TODO: verify all of the attributes before forwarding
                # do mobile notification request for authentication here
                try:
                    link = config.websocketServer.inbound_streams[User.__name__][
                        rid
                    ].link
                    data = config.websocketServer.inbound_streams[User.__name__][
                        rid
                    ].data
                except:
                    self.set_status(407)
                    return self.finish()
                if not data.get("authenticated"):
                    url_parsed = urlparse(self.request.uri, scheme="http")
                    get_challenge_resp = await fetch_request(
                        f"http://{url_parsed.netloc}/proxy-challenge",
                        body=json.dumps(data),
                        headers={"Content-type": "application/json"},
                        method="POST",
                        follow_redirects=False,
                        allow_nonstandard_methods=True,
                    )
                    if get_challenge_resp.code < 200 or get_challenge_resp.code > 299:
                        return
                    respdata = json.loads(get_challenge_resp.body)

                    data["challenge"] = {"message": respdata["challenge"]}
                    data["dh_public_key"] = config.websocketServer.inbound_streams[
                        User.__name__
                    ][rid].dh_public_key

                    await self.proxy_signature_request(data, link)
                    data["challenge"]["signature"] = config.challenges[link][
                        "signature"
                    ]
                    post_challenge_resp = await fetch_request(
                        f"http://{url_parsed.netloc}/proxy-challenge",
                        body=json.dumps(data),
                        headers={"Content-type": "application/json"},
                        method="POST",
                        follow_redirects=False,
                        allow_nonstandard_methods=True,
                    )
                    if post_challenge_resp.code < 200 or post_challenge_resp.code > 299:
                        return
                    data["authenticated"] = True
                    for header, v in post_challenge_resp.headers.get_all():
                        if header not in (
                            "Content-Length",
                            "Transfer-Encoding",
                            "Content-Encoding",
                            "Connection",
                        ):
                            self.add_header(
                                header, v
                            )  # some header appear multiple times, eg 'Set-Cookie'
                # await config.websocketServer.inbound_streams[User.__name__][rid].write_result(
                #     'dh_public_key',
                #     {
                #         'dh_public_key': respdata['dh_public_key']
                #     }
                # )
                # self.request.headers['Authorization'] = base64.b64encode(json.dumps(data).encode())
            resp = await fetch_request(
                f"{self.request.uri}",
                method=self.request.method,
                body=body,
                headers=self.request.headers,
                follow_redirects=False,
                allow_nonstandard_methods=True,
            )
            await handle_response(resp)
        except tornado.httpclient.HTTPError as e:
            if hasattr(e, "response") and e.response:
                await handle_response(e.response)
            else:
                self.set_status(500)
                self.write("Internal server error:\n" + str(e))
                self.finish()

    async def post(self):
        return await self.get()

    async def connect(self):
        client = self.request.connection.stream
        config = Config()
        config.app_log.debug("Start CONNECT to %s", self.request.uri)
        host, port = self.request.uri.split(":")
        rid = blacklist_group.generate_rid(
            blacklist_group.username_signature, Collections.GROUP_CHAT.value
        )

        async def check_blocked():
            domain = ".".join((host.split(".")[-2:]))
            if not hasattr(config.proxy, "mode"):
                config.proxy.mode = False
            if not config.proxy.mode:
                config.proxy.mode = (
                    await config.mongo.async_site_db.proxy_config.find_one(
                        {"mode": {"$exists": True}}
                    )
                )
            if config.proxy.mode and config.proxy.mode == "exclusive":
                if (
                    domain in config.proxy.black_list
                    and config.proxy.black_list[domain]["active"]
                ):
                    client.write(b"HTTP/1.0 403 Connection established\r\n\r\n")
                    client.close()
                    self.request.connection.finish()
                    return True
                item = {"domain": domain, "host": host, "timestamp": time()}
                if rid in config.websocketServer.inbound_streams[Group.__name__]:
                    for x in list(
                        config.websocketServer.inbound_streams[Group.__name__][
                            rid
                        ].values()
                    ):
                        await x.write_params("new_allowed_item", item)

            elif config.proxy.mode and config.proxy.mode == "inclusive":
                if (
                    domain not in config.proxy.white_list
                    or not config.proxy.white_list.get(domain, {}).get("active")
                ):
                    client.write(b"HTTP/1.0 403 Connection established\r\n\r\n")
                    client.close()
                    self.request.connection.finish()
                    item = {"domain": domain, "host": host, "timestamp": time()}
                    if rid in config.websocketServer.inbound_streams[Group.__name__]:
                        for x in list(
                            config.websocketServer.inbound_streams[Group.__name__][
                                rid
                            ].values()
                        ):
                            await x.write_params("new_rejected_item", item)
                    return True

        async def relay(reader, writer):
            try:
                while True:
                    if await check_blocked():
                        reader.close()
                        writer.close()
                        return
                    data = await reader.read_bytes(1024 * 64, partial=True)
                    if writer.closed():
                        return
                    if data:
                        writer.write(data)
                    else:
                        break
            except tornado.iostream.StreamClosedError:
                reader.close()
                writer.close()

        async def start_tunnel():
            if await check_blocked():
                client.close()
                upstream.close()
                return
            config.app_log.debug("CONNECT tunnel established to %s", self.request.uri)
            client.write(b"HTTP/1.0 200 Connection established\r\n\r\n")
            # await self.proxy_signature_request(data, link)
            await asyncio.gather(relay(client, upstream), relay(upstream, client))
            client.close()
            upstream.close()

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        upstream = tornado.iostream.IOStream(s)
        resolver = dns.resolver.Resolver()
        resolver.timeout = 1
        resolver.lifetime = 3
        resolver.nameservers = config.dns_resolvers
        if host not in config.dns_bypass_ips:
            answer = resolver.query(qname=host, rdtype=1, rdclass=1, source="0.0.0.0")
            for x in answer.response.answer:
                if x.rdtype == 1:
                    await upstream.connect((x.items[0].address, int(port)))
                    await start_tunnel()
                    break
        else:
            await upstream.connect((host, int(port)))
            await start_tunnel()

    async def proxy_signature_request(self, auth_data, link):
        config = Config()
        if link not in config.websocketServer.inbound_streams[User.__name__]:
            self.set_status(407)
            return self.finish()

        await config.websocketServer.inbound_streams[User.__name__][link].write_params(
            "proxy_signature_request", auth_data
        )
        i = 0
        while "signature" not in config.challenges[link]:
            await async_sleep(1)
            i += 1
            if i > 60:
                self.set_status(200)
                self.write("Timeout waiting for user approval\n")
                return self.finish()
