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
import contextvars
import json
import logging
import socket
import time
from datetime import timedelta
from traceback import format_exc
from uuid import uuid4

from coincurve import verify_signature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from tornado.iostream import StreamClosedError
from tornado.log import LogFormatter
from tornado.tcpclient import TCPClient
from tornado.tcpserver import TCPServer
from tornado.util import TimeoutError

from yadacoin.core.config import Config


class ProtocolVersionTooLowError(Exception):
    """Raised when a peer announces a protocol version below the minimum."""


# ---------------------------------------------------------------------------
# Peer-aware logging
# ---------------------------------------------------------------------------
#
# The Tornado pretty logger prefix looks like ``[I 260712 03:19:57 node:1026]``.
# To attribute log lines to the peer they belong to, the tcpsocket server and
# client loops set a context-local label (the peer's username, falling back to
# its host, then ``(blank)``).  Only these loops set it, so log lines emitted
# from other modules keep the default empty label.

peer_label_var = contextvars.ContextVar("peer_label", default="")


def peer_label_for(stream_or_peer) -> str:
    """Return a short label for a peer: username, else host, else ``(blank)``."""
    peer = getattr(stream_or_peer, "peer", stream_or_peer)
    if not peer:
        return "(blank)"
    identity = getattr(peer, "identity", None)
    username = getattr(identity, "username", None) or ""
    if username:
        return username
    host = getattr(peer, "host", None) or ""
    if host:
        return host
    return "(blank)"


class PeerContextFilter(logging.Filter):
    """Inject the current peer label into every log record."""

    def filter(self, record):
        record.peer_label = peer_label_var.get()
        return True


class PeerLogFormatter(LogFormatter):
    """Tornado-style prefix that appends the peer label to the bracket.

    Only used by the console (pretty) handler; the rotating file handler keeps
    its own one-line format.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._fmt = (
            "%(color)s[%(levelname)1.1s %(asctime)s "
            "%(module)s:%(lineno)d %(peer_label)s]%(end_color)s %(message)s"
        )


# ---------------------------------------------------------------------------
# Session encryption (X25519 ECDH + AES-256-GCM)
# ---------------------------------------------------------------------------

#: Methods sent before the session cipher is established — always plain.
PRE_AUTH_METHODS = frozenset({"connect", "challenge"})


class SessionCipher:
    """Symmetric AES-256-GCM cipher for an established P2P session.

    Key is derived once via X25519 ECDH + HKDF at the end of the
    challenge/authenticate handshake.  Separate monotonic counters are kept
    for each direction so the nonces never collide.
    """

    NONCE_SIZE = 12  # 96-bit nonce required by AES-GCM
    _HKDF_INFO = b"yadacoin-p2p-session-v5"

    def __init__(self, session_key: bytes):
        self._aes = AESGCM(session_key)
        self._send_counter = 0
        self._recv_counter = 0

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = self._send_counter.to_bytes(self.NONCE_SIZE, "big")
        self._send_counter += 1
        return nonce + self._aes.encrypt(nonce, plaintext, None)

    def decrypt(self, data: bytes) -> bytes:
        nonce, ct = data[: self.NONCE_SIZE], data[self.NONCE_SIZE :]
        return self._aes.decrypt(nonce, ct, None)

    # ------------------------------------------------------------------
    # ECDH helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_keypair() -> tuple:
        """Return ``(X25519PrivateKey, b64_public_key_str)``."""
        priv = X25519PrivateKey.generate()
        pub_b64 = base64.b64encode(
            priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode()
        return priv, pub_b64

    @staticmethod
    def derive(
        my_priv: X25519PrivateKey,
        peer_pub_b64: str,
        token: str,
    ) -> "SessionCipher":
        """Perform ECDH and derive the AES session key.

        ``token`` (the challenge token) is used as the HKDF salt so the
        session key is bound to a specific authenticated exchange.
        """
        peer_pub_bytes = base64.b64decode(peer_pub_b64)
        peer_pub = X25519PublicKey.from_public_bytes(peer_pub_bytes)
        shared = my_priv.exchange(peer_pub)
        session_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=token.encode("utf-8"),
            info=SessionCipher._HKDF_INFO,
        ).derive(shared)
        return SessionCipher(session_key)


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

        if not hasattr(stream, "peer"):
            self.config.app_log.warning("Stream has no peer, closing connection.")
            stream.close()
            return

        peer_host = getattr(stream.peer, "host", "Unknown")

        rpc_data = {
            "id": req_id if req_id else str(uuid4()),
            "method": method,
            "jsonrpc": 2.0,
            rpc_type: data,
        }

        if rpc_type == "params":
            if method not in stream.message_queue:
                stream.message_queue[method] = {}
            stream.message_queue[method][rpc_data["id"]] = rpc_data

        try:
            cipher = getattr(stream, "session_cipher", None)
            if cipher and method not in PRE_AUTH_METHODS:
                plain = json.dumps(rpc_data).encode("utf-8")
                ct = cipher.encrypt(plain)
                line = (
                    json.dumps({"enc": base64.b64encode(ct).decode()}) + "\n"
                ).encode()
            else:
                line = "{}\n".format(json.dumps(rpc_data)).encode()
            await asyncio.wait_for(stream.write(line), timeout=5)

        except asyncio.TimeoutError:
            self.config.app_log.warning(
                f"Timeout! Stream {peer_host} is unresponsive. Removing peer..."
            )
            await self.remove_peer(stream)
            return

        except StreamClosedError:
            self.config.app_log.warning(
                f"StreamClosedError: Peer {peer_host} is already disconnected."
            )
            await self.remove_peer(stream)
            return

        except Exception as e:
            self.config.app_log.warning(f"Exception in write_as_json(): {e}")
            await self.remove_peer(stream)
            return

        if hasattr(self.config, "tcp_traffic_debug") and self.config.tcp_traffic_debug:
            self.config.app_log.debug(
                f"SENT {peer_host} {method} {data} {rpc_type} {req_id}"
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
            token = peer_label_var.set(peer_label_for(stream))
            try:
                data = await stream.read_until(b"\n")
                stream.last_activity = int(time.time())
                self.config.health.tcp_server.last_activity = time.time()
                try:
                    # Decrypt if the peer has an established session cipher
                    raw = data.strip()
                    cipher = getattr(stream, "session_cipher", None)
                    if cipher and raw.startswith(b'{"enc":'):
                        enc_obj = json.loads(raw)
                        ct = base64.b64decode(enc_obj["enc"])
                        raw = cipher.decrypt(ct)
                    body = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self.config.app_log.warning(
                        f"Invalid data from peer, skipping message: {data[:200]}"
                    )
                    continue
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
                if (
                    hasattr(self.config, "tcp_traffic_debug")
                    and self.config.tcp_traffic_debug == True
                ):
                    _peer_addr = (
                        getattr(getattr(stream, "peer", None), "host", None)
                        or getattr(getattr(stream, "peer", None), "address", None)
                        or getattr(stream, "socket", None)
                        or "unknown"
                    )
                    self.config.app_log.debug(
                        f"SERVER RECEIVED {_peer_addr} {method} {body}"
                    )
                if hasattr(stream, "peer"):
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
                        "Disconnected from {0}.{1}".format(
                            stream.peer.__class__.__name__,
                            stream.peer.identity.username or "(blank)",
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
            finally:
                peer_label_var.reset(token)

    async def keepalive(self, body, stream):
        """
        Handles incoming KeepAlive messages to confirm connection status.

        When a KeepAlive message is received, this method updates the last activity timestamp
        for both the stream and the TCP server health tracker. It then responds with an
        acknowledgment message, ensuring that the peer also updates its connection status.
        """
        stream.last_activity = int(time.time())
        self.config.health.tcp_server.last_activity = time.time()
        self.config.app_log.debug(
            f"KeepAlive received from {stream.peer.host}. Connection is active."
        )

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
        token = peer_label_var.set(peer_label_for(peer))
        try:
            stream = None
            # Resolve an on-chain identity_announcement (if any) into a concrete
            # Identity before any peer comparisons or signature verification.
            resolved = await peer.resolve_identity_announcement()
            if not resolved:
                self.config.app_log.warning(
                    "Cannot resolve identity_announcement for {}: {}".format(
                        peer.__class__.__name__, peer.to_json()
                    )
                )
                return
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
            if peer.identity is not None and (
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
                if stream.peer.identity is not None:
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
                else:
                    self.config.app_log.warning(
                        "new {} peer has no resolvable identity".format(
                            peer.__class__.__name__
                        )
                    )
                    await self.remove_peer(
                        stream,
                        reason="RPCSocketClient: peer identity could not be resolved",
                    )
                    return
            except Exception as exc:
                self.config.app_log.warning("invalid peer identity signature: %s", exc)
                await self.remove_peer(
                    stream, reason="RPCSocketClient: invalid peer identity signature"
                )
                return
            if id_attr in self.outbound_pending[peer.__class__.__name__]:
                del self.outbound_pending[peer.__class__.__name__][id_attr]
            self.outbound_streams[peer.__class__.__name__][id_attr] = stream
            self.config.app_log.info(
                "Connected to {}: {}".format(
                    stream.peer.__class__.__name__,
                    stream.peer.identity.username or "(blank)",
                )
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
        finally:
            peer_label_var.reset(token)

    async def wait_for_data(self, stream):
        while True:
            token = peer_label_var.set(peer_label_for(stream))
            try:
                raw = (await stream.read_until(b"\n")).strip()
                # Decrypt if the peer has an established session cipher
                cipher = getattr(stream, "session_cipher", None)
                if cipher and raw.startswith(b'{"enc":'):
                    try:
                        enc_obj = json.loads(raw)
                        ct = base64.b64decode(enc_obj["enc"])
                        raw = cipher.decrypt(ct)
                    except Exception:
                        self.config.app_log.warning(
                            "wait_for_data: decryption failed, skipping message"
                        )
                        continue
                body = json.loads(raw)

                if body.get("method") == "keepalive":
                    self.config.health.tcp_client.last_activity = time.time()
                    stream.last_activity = int(time.time())
                    self.config.app_log.debug(
                        f"KeepAlive response received from {stream.peer.host}"
                    )
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
            except ProtocolVersionTooLowError as e:
                await self.remove_peer(stream, reason=str(e))
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
            finally:
                peer_label_var.reset(token)

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
                self.config.app_log.warning(
                    f"Stream to {stream.peer.host} is closed. Stopping KeepAlive."
                )
                break

            try:
                self.config.app_log.debug(f"Sending KeepAlive to {stream.peer.host}")
                await self.write_params(
                    stream, "keepalive", {"timestamp": int(time.time())}
                )

            except Exception as e:
                self.config.app_log.warning(
                    f"Failed to send KeepAlive to {stream.peer.host}: {e}"
                )
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
