"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import base64
import json
import socket
import time
from datetime import timedelta
from traceback import format_exc
from uuid import uuid4

from coincurve import verify_signature
from tornado.iostream import StreamClosedError
from tornado.tcpclient import TCPClient
from tornado.tcpserver import TCPServer
from tornado.util import TimeoutError

from yadacoin.core.config import Config

REQUEST_RESPONSE_MAP = {
    "blockresponse": "getblock",
    "blocksresponse": "getblocks",
    "keepalive": "keepalive",
}

REQUEST_ONLY = [
    "connect",
    "challenge",
    "authenticate",
    "newblock",
    "blockresponse_confirmed",
    "blocksresponse_confirmed",
    "newblock_confirmed",
    "newtxn_confirmed",
    "disconnect",
]


class BaseRPC:
    def __init__(self):
        self.config = Config()

    async def write_result(self, stream, method, data, req_id):
        await self.write_as_json(stream, method, data, "result", req_id)

    async def write_params(self, stream, method, data):
        await self.write_as_json(stream, method, data, "params")

    async def write_as_json(self, stream, method, data, rpc_type, req_id=None):
        if isinstance(stream, DummyStream):
            self.config.app_log.warning(
                "Stream is an instance of DummyStream, cannot send data."
            )
            return
        rpc_data = {
            "id": req_id if req_id else str(uuid4()),
            "method": method,
            "jsonrpc": 2.0,
            rpc_type: data,
        }
        if rpc_type == "params":
            if method not in stream.message_queue:
                stream.message_queue[method] = {}
            if len(stream.message_queue[method].keys()) > 25:
                queue_key = list(stream.message_queue[method].keys())[0]
                del stream.message_queue[method][queue_key]
            stream.message_queue[method][rpc_data["id"]] = rpc_data
        try:
            await stream.write("{}\n".format(json.dumps(rpc_data)).encode())
        except StreamClosedError:
            if hasattr(stream, "peer"):
                self.config.app_log.warning(
                    "Disconnected from {}: {}".format(
                        stream.peer.__class__.__name__, stream.peer.to_json()
                    )
                )
            await self.remove_peer(stream)
            return
        except:
            if hasattr(stream, "peer"):
                await self.remove_peer(stream, reason="BaseRPC: unhandled exception 1")
            else:
                stream.close()
            self.config.app_log.warning(format_exc())
            return
        if (
            hasattr(self.config, "tcp_traffic_debug")
            and self.config.tcp_traffic_debug == True
        ):
            if hasattr(stream, "peer"):
                self.config.app_log.debug(
                    f"SENT {stream.peer.host} {method} {data} {rpc_type} {req_id}"
                )

    async def remove_peer(self, stream, close=True, reason=None):
        if reason:
            await self.write_params(stream, "disconnect", {"reason": reason})
        if close:
            stream.close()
        if not hasattr(stream, "peer"):
            return
        id_attr = getattr(stream.peer, stream.peer.id_attribute)
        if (
            id_attr
            in self.config.nodeServer.inbound_streams[stream.peer.__class__.__name__]
        ):
            del self.config.nodeServer.inbound_streams[stream.peer.__class__.__name__][
                id_attr
            ]

        if (
            id_attr
            in self.config.nodeServer.inbound_pending[stream.peer.__class__.__name__]
        ):
            del self.config.nodeServer.inbound_pending[stream.peer.__class__.__name__][
                id_attr
            ]

        if (
            id_attr
            in self.config.nodeClient.outbound_streams[stream.peer.__class__.__name__]
        ):
            del self.config.nodeClient.outbound_streams[stream.peer.__class__.__name__][
                id_attr
            ]

        if (
            id_attr
            in self.config.nodeClient.outbound_pending[stream.peer.__class__.__name__]
        ):
            del self.config.nodeClient.outbound_pending[stream.peer.__class__.__name__][
                id_attr
            ]
        try:
            for y in self.config.nodeServer.retry_messages.copy():
                if y[0] == id_attr:
                    del self.config.nodeServer.retry_messages[y]
        except:
            pass
        try:
            for y in self.config.nodeClient.retry_messages.copy():
                if y[0] == id_attr:
                    del self.config.nodeClient.retry_messages[y]
        except:
            pass


class RPCSocketServer(TCPServer, BaseRPC):
    inbound_streams = {}
    inbound_pending = {}
    config = None

    async def handle_stream(self, stream, address):
        stream.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        # OPTIONAL: Adjust keepalive settings if needed
        if hasattr(socket, "TCP_KEEPIDLE"):
            stream.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
        if hasattr(socket, "TCP_KEEPINTVL"):
            stream.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 15)
        if hasattr(socket, "TCP_KEEPCNT"):
            stream.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)

        stream.synced = False
        stream.syncing = False
        stream.message_queue = {}
        while True:
            try:
                data = await stream.read_until(b"\n")
                stream.last_activity = int(time.time())
                self.config.health.tcp_server.last_activity = time.time()
                body = json.loads(data)
                method = body.get("method")
                if "result" in body:
                    if method in REQUEST_RESPONSE_MAP:
                        if body["id"] in stream.message_queue.get(
                            REQUEST_RESPONSE_MAP[method], {}
                        ):
                            del stream.message_queue[REQUEST_RESPONSE_MAP[method]][
                                body["id"]
                            ]
                if not hasattr(self, method):
                    continue
                if hasattr(stream, "peer"):
                    if hasattr(stream.peer, "host"):
                        if (
                            hasattr(self.config, "tcp_traffic_debug")
                            and self.config.tcp_traffic_debug == True
                        ):
                            self.config.app_log.debug(
                                f"SERVER RECEIVED {stream.peer.host} {method} {body}"
                            )
                    if hasattr(stream.peer, "address"):
                        if (
                            hasattr(self.config, "tcp_traffic_debug")
                            and self.config.tcp_traffic_debug == True
                        ):
                            self.config.app_log.debug(
                                f"SERVER RECEIVED {stream.peer.address} {method} {body}"
                            )
                    id_attr = getattr(stream.peer, stream.peer.id_attribute)
                    if (
                        id_attr
                        not in self.config.nodeServer.inbound_streams[
                            stream.peer.__class__.__name__
                        ]
                    ):
                        await self.remove_peer(
                            stream,
                            reason=f"{id_attr} not in nodeServer.inbound_streams",
                        )
                if not hasattr(stream, "peer") and method not in ["login", "connect"]:
                    await self.remove_peer(stream)
                    break
                await getattr(self, method)(body, stream)
            except StreamClosedError:
                if hasattr(stream, "peer"):
                    self.config.app_log.warning(
                        "Disconnected from {}: {}".format(
                            stream.peer.__class__.__name__, stream.peer.to_json()
                        )
                    )
                await self.remove_peer(stream)
                break
            except:
                if hasattr(stream, "peer"):
                    self.config.app_log.warning(
                        "Bad data from {}: {}".format(
                            stream.peer.__class__.__name__, stream.peer.to_json()
                        )
                    )
                await self.remove_peer(stream, reason="BaseRPC: unhandled exception 2")
                self.config.app_log.warning("{}".format(format_exc()))
                self.config.app_log.warning(data)
                break

    async def keepalive(self, body, stream):
        """
        Handles incoming KeepAlive messages to confirm connection status.

        When a KeepAlive message is received, this method updates the last activity timestamp
        for both the stream and the TCP server health tracker. It then responds with an
        acknowledgment message, ensuring that the peer also updates its connection status.
        """
        stream.last_activity = int(time.time())
        self.config.health.tcp_server.last_activity = time.time()
        self.config.app_log.info(f"KeepAlive received from {stream.peer.host}. Connection is active.")

        await self.write_result(stream, "keepalive", {"ok": True}, body["id"])

    async def remove_peer(self, stream, close=True, reason=None):
        if reason:
            await self.write_params(stream, "disconnect", {"reason": reason})
        if close:
            stream.close()
        if not hasattr(stream, "peer"):
            return
        id_attr = getattr(stream.peer, stream.peer.id_attribute)
        if (
            id_attr
            in self.config.nodeServer.inbound_streams[stream.peer.__class__.__name__]
        ):
            del self.config.nodeServer.inbound_streams[stream.peer.__class__.__name__][
                id_attr
            ]
        if (
            id_attr
            in self.config.nodeServer.inbound_pending[stream.peer.__class__.__name__]
        ):
            del self.config.nodeServer.inbound_pending[stream.peer.__class__.__name__][
                id_attr
            ]
        try:
            for y in self.config.nodeServer.retry_messages.copy():
                if y[0] == id_attr:
                    del self.config.nodeServer.retry_messages[y]
        except:
            pass


class DummyStream:
    peer = None

    def __init__(self, peer):
        self.peer = peer

    def close(self):
        return


class RPCSocketClient(TCPClient):
    outbound_streams = {}
    outbound_pending = {}
    outbound_ignore = {}
    config = None

    async def connect(self, peer):
        try:
            stream = None
            id_attr = getattr(peer, peer.id_attribute)
            if id_attr in self.outbound_ignore[peer.__class__.__name__]:
                return
            if id_attr in self.outbound_pending[peer.__class__.__name__]:
                return
            if id_attr in self.outbound_streams[peer.__class__.__name__]:
                return
            if (
                id_attr
                in self.config.nodeServer.inbound_pending[peer.__class__.__name__]
            ):
                return
            if (
                id_attr
                in self.config.nodeServer.inbound_streams[peer.__class__.__name__]
            ):
                return
            if (
                self.config.peer.identity.username_signature
                == peer.identity.username_signature
            ):
                return
            if (self.config.peer.host, self.config.peer.port) == (peer.host, peer.port):
                return
            stream = DummyStream(peer)
            stream.last_activity = int(time.time())
            self.outbound_pending[peer.__class__.__name__][id_attr] = stream
            stream = await super(RPCSocketClient, self).connect(
                peer.host, peer.port, timeout=timedelta(seconds=1)
            )
            stream.synced = False
            stream.syncing = False
            stream.message_queue = {}
            stream.peer = peer
            self.config.health.tcp_client.last_activity = time.time()
            stream.last_activity = int(time.time())
            try:
                result = verify_signature(
                    base64.b64decode(stream.peer.identity.username_signature),
                    stream.peer.identity.username.encode(),
                    bytes.fromhex(stream.peer.identity.public_key),
                )
                if not result:
                    self.config.app_log.warning(
                        "new {} peer signature is invalid".format(
                            peer.__class__.__name__
                        )
                    )
                    await self.remove_peer(
                        stream,
                        reason="RPCSocketClient: invalid peer identity signature",
                    )
                    return
                self.config.app_log.info(
                    "new {} peer is valid".format(peer.__class__.__name__)
                )
            except:
                self.config.app_log.warning("invalid peer identity signature")
                await self.remove_peer(
                    stream, reason="RPCSocketClient: invalid peer identity signature"
                )
                return
            if id_attr in self.outbound_pending[peer.__class__.__name__]:
                del self.outbound_pending[peer.__class__.__name__][id_attr]
            self.outbound_streams[peer.__class__.__name__][id_attr] = stream
            self.config.app_log.info(
                "Connected to {}: {}".format(peer.__class__.__name__, peer.to_json())
            )
            return stream
        except StreamClosedError:
            if not stream:
                stream = DummyStream(peer)

            await self.remove_peer(stream)
            self.config.app_log.warning(
                "Stream closed for {}: {}".format(
                    peer.__class__.__name__, peer.to_json()
                )
            )
            self.outbound_ignore[peer.__class__.__name__][
                peer.identity.username_signature
            ] = time.time()
        except TimeoutError:
            if not stream:
                stream = DummyStream(peer)

            await self.remove_peer(
                stream, reason="RPCSocketClient: unhandled exception 1"
            )
            self.config.app_log.warning(
                "Timeout connecting to {}: {}".format(
                    peer.__class__.__name__, peer.to_json()
                )
            )
            self.outbound_ignore[peer.__class__.__name__][
                peer.identity.username_signature
            ] = time.time()
        except socket.gaierror:
            if not stream:
                stream = DummyStream(peer)

            await self.remove_peer(
                stream, reason="RPCSocketClient: unhandled exception 1"
            )
            self.config.app_log.warning(
                "Timeout connecting to {}: {}".format(
                    peer.__class__.__name__, peer.to_json()
                )
            )
            self.outbound_ignore[peer.__class__.__name__][
                peer.identity.username_signature
            ] = time.time()
        except:
            if hasattr(stream, "peer"):
                self.config.app_log.warning(
                    "Unhandled exception from {}: {}".format(
                        stream.peer.__class__.__name__, stream.peer.to_json()
                    )
                )

            await self.remove_peer(
                stream, reason="RPCSocketClient: unhandled exception 2"
            )
            self.config.app_log.warning("{}".format(format_exc()))

    async def wait_for_data(self, stream):
        while True:
            try:
                body = json.loads(await stream.read_until(b"\n"))

                if body.get("method") == "keepalive":
                    self.config.health.tcp_client.last_activity = time.time()
                    stream.last_activity = int(time.time())
                    self.config.app_log.info(f"✅ KeepAlive response received from {stream.peer.host}")
                    continue

                if "result" in body:
                    if body["method"] in REQUEST_RESPONSE_MAP:
                        if body["id"] in stream.message_queue.get(
                            REQUEST_RESPONSE_MAP[body["method"]], {}
                        ):
                            del stream.message_queue[
                                REQUEST_RESPONSE_MAP[body["method"]]
                            ][body["id"]]
                if hasattr(stream, "peer"):
                    if (
                        hasattr(self.config, "tcp_traffic_debug")
                        and self.config.tcp_traffic_debug == True
                    ):
                        self.config.app_log.debug(
                            f'CLIENT RECEIVED {stream.peer.host} {body["method"]} {body}'
                        )
                else:
                    stream.close()
                self.config.health.tcp_client.last_activity = time.time()
                stream.last_activity = int(time.time())
                await getattr(self, body.get("method"))(body, stream)
            except StreamClosedError:
                await self.remove_peer(stream)
                break
            except:
                if hasattr(stream, "peer"):
                    self.config.app_log.warning(
                        "Unhandled exception from {}: {}".format(
                            stream.peer.__class__.__name__, stream.peer.to_json()
                        )
                    )

                await self.remove_peer(
                    stream, reason="RPCSocketClient: unhandled exception 3"
                )
                self.config.app_log.warning("{}".format(format_exc()))
                break


    async def send_keepalive(self, stream):
        """
        Periodically sends KeepAlive messages to maintain an active connection.

        This method runs in an infinite loop, sending a KeepAlive message every 90 seconds
        to the connected peer. It helps prevent unnecessary disconnections due to inactivity
        by ensuring regular communication. If sending fails, the loop terminates, assuming
        the connection is lost.
        """
        while True:
            await asyncio.sleep(90)

            if stream.closed():
                self.config.app_log.warning(f"Stream to {stream.peer.host} is closed. Stopping KeepAlive.")
                break

            try:
                self.config.app_log.info(f"Sending KeepAlive to {stream.peer.host}")
                await self.write_params(stream, "keepalive", {"timestamp": int(time.time())})

            except Exception as e:
                self.config.app_log.warning(f"Failed to send KeepAlive to {stream.peer.host}: {e}")
                break

    async def remove_peer(self, stream, close=True, reason=None):
        if reason:
            try:
                await self.write_params(stream, "disconnect", {"reason": reason})
            except:
                self.config.app_log.warning("{}".format(format_exc()))
        if close:
            stream.close()
        if not hasattr(stream, "peer"):
            return
        if stream.peer.rid in self.outbound_streams[stream.peer.__class__.__name__]:
            del self.outbound_streams[stream.peer.__class__.__name__][stream.peer.rid]
        if stream.peer.rid in self.outbound_pending[stream.peer.__class__.__name__]:
            del self.outbound_pending[stream.peer.__class__.__name__][stream.peer.rid]
        try:
            for y in self.config.nodeClient.retry_messages.copy():
                if y[0] == stream.peer.rid:
                    del self.config.nodeClient.retry_messages[y]
        except:
            pass
