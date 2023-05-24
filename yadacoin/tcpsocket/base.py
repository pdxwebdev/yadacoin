import json
import socket
import base64
import time
from datetime import timedelta
from json.decoder import JSONDecodeError
from uuid import uuid4
from collections import OrderedDict
from traceback import format_exc

from tornado.tcpserver import TCPServer
from tornado.tcpclient import TCPClient
from tornado.iostream import StreamClosedError
from tornado.util import TimeoutError
from coincurve import verify_signature

from yadacoin.core.config import get_config, Config
from yadacoin.core.chain import CHAIN


REQUEST_RESPONSE_MAP = {
    "blockresponse": "getblock",
    "blocksresponse": "getblocks",
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
        self.config = get_config()

    async def write_result(self, stream, method, data, req_id):
        await self.write_as_json(stream, method, data, "result", req_id)

    async def write_params(self, stream, method, data):
        await self.write_as_json(stream, method, data, "params")

    async def write_as_json(self, stream, method, data, rpc_type, req_id=None):
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
                await self.remove_peer(stream)
            else:
                stream.close()
            self.config.app_log.debug(format_exc())
            return
        if (
            hasattr(self.config, "tcp_traffic_debug")
            and self.config.tcp_traffic_debug == True
        ):
            if hasattr(stream, "peer"):
                self.config.app_log.debug(
                    f"SENT {stream.peer.host} {method} {data} {rpc_type} {req_id}"
                )

    async def remove_peer(self, stream, close=True):
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


class RPCSocketServer(TCPServer, BaseRPC):
    inbound_streams = {}
    inbound_pending = {}
    config = None

    async def handle_stream(self, stream, address):
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
                        not in self.inbound_streams[stream.peer.__class__.__name__]
                    ):
                        await self.write_params(stream, "disconnect", {})
                        await self.remove_peer(stream)
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
                await self.remove_peer(stream)
                self.config.app_log.debug("{}".format(format_exc()))
                break

    async def remove_peer(self, stream, close=True):
        if close:
            stream.close()
        if not hasattr(stream, "peer"):
            return
        id_attr = getattr(stream.peer, stream.peer.id_attribute)
        if id_attr in self.inbound_streams[stream.peer.__class__.__name__]:
            del self.inbound_streams[stream.peer.__class__.__name__][id_attr]
        if id_attr in self.inbound_pending[stream.peer.__class__.__name__]:
            del self.inbound_pending[stream.peer.__class__.__name__][id_attr]


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
            if (self.config.peer.host, self.config.peer.host) == (peer.host, peer.port):
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
                    stream.close()
                    return
                self.config.app_log.info(
                    "new {} peer is valid".format(peer.__class__.__name__)
                )
            except:
                self.config.app_log.warning("invalid peer identity signature")
                await self.remove_peer(stream)
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
        except TimeoutError:
            if not stream:
                stream = DummyStream(peer)

            await self.remove_peer(stream)
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

            await self.remove_peer(stream)
            self.config.app_log.debug("{}".format(format_exc()))

    async def wait_for_data(self, stream):
        while True:
            try:
                body = json.loads(await stream.read_until(b"\n"))
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

                await self.remove_peer(stream)
                self.config.app_log.debug("{}".format(format_exc()))
                break

    async def remove_peer(self, stream, close=True):
        if close:
            stream.close()
        if not hasattr(stream, "peer"):
            return
        if stream.peer.rid in self.outbound_streams[stream.peer.__class__.__name__]:
            del self.outbound_streams[stream.peer.__class__.__name__][stream.peer.rid]
        if stream.peer.rid in self.outbound_pending[stream.peer.__class__.__name__]:
            del self.outbound_pending[stream.peer.__class__.__name__][stream.peer.rid]
