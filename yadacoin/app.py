"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import importlib
import json
import logging
import ntpath
import os
import pkgutil
import re
import shutil
import ssl
import subprocess
import sys
import tempfile

PLUGIN_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+plugins\.([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE
)

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
try:
    import resource

    resource.setrlimit(resource.RLIMIT_NOFILE, (131072, 131072))
except:
    pass

# ── Python 3.9 macOS workaround ───────────────────────────────────────────────
# On the Xcode Python 3.9 macOS build, asyncio._check_callback calls
# coroutines.iscoroutine() which calls isinstance(obj, _COROUTINE_TYPES).
# _COROUTINE_TYPES includes collections.abc.Coroutine (an ABC), and the ABC
# machinery's __instancecheck__ recurses infinitely due to a platform bug in
# that Python build (RecursionError: maximum recursion depth exceeded).
# Patching iscoroutine early with a try/except guards against this.
import asyncio.coroutines as _asyncio_coroutines

_original_iscoroutine = _asyncio_coroutines.iscoroutine


def _safe_iscoroutine(obj):
    try:
        return _original_iscoroutine(obj)
    except RecursionError:
        return False


_asyncio_coroutines.iscoroutine = _safe_iscoroutine
# ─────────────────────────────────────────────────────────────────────────────
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from hashlib import sha256
from logging.handlers import RotatingFileHandler
from os import path
from time import time
from traceback import format_exc

import tornado.ioloop
import tornado.locks
import tornado.log
from Crypto.PublicKey.ECC import EccKey
from tornado.httpclient import AsyncHTTPClient
from tornado.httpserver import HTTPServer
from tornado.ioloop import PeriodicCallback
from tornado.options import define, options
from tornado.web import Application, StaticFileHandler

import yadacoin.core.blockchainutils
import yadacoin.core.config
import yadacoin.core.transactionutils
from yadacoin import version
from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.chain import CHAIN
from yadacoin.core.consensus import Consensus
from yadacoin.core.crypt import Crypt
from yadacoin.core.graphutils import GraphUtils
from yadacoin.core.health import Health
from yadacoin.core.keyrotation import NodeKeyRotationManager
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.miningpool import MiningPool
from yadacoin.core.miningpoolpayout import PoolPayer
from yadacoin.core.mongo import Mongo
from yadacoin.core.nodestester import NodesTester
from yadacoin.core.peer import (
    Group,
    Miner,
    Peer,
    Peers,
    Pool,
    Seed,
    SeedGateway,
    ServiceProvider,
    User,
)
from yadacoin.core.processingqueue import BlockProcessingQueueItem, ProcessingQueues
from yadacoin.core.smtp import Email
from yadacoin.core.transaction import Transaction
from yadacoin.enums.modes import MODES
from yadacoin.enums.peertypes import PEER_TYPES
from yadacoin.managers.docker import Docker
from yadacoin.tcpsocket.base import PeerContextFilter, PeerLogFormatter
from yadacoin.tcpsocket.node import NodeRPC, NodeSocketClient, NodeSocketServer
from yadacoin.tcpsocket.pool import StratumServer
from yadacoin.websocket.base import WEBSOCKET_HANDLERS, RCPWebSocketServer
from yadacoin.websocket.peerjs import PEERJS_HANDLERS

define("debug", default=False, help="debug mode", type=bool)
define("verbose", default=False, help="verbose mode", type=bool)
define("network", default="", help="Force mainnet, testnet or regnet", type=str)
define(
    "reset",
    default=False,
    help="If blockchain is invalid, truncate at error block",
    type=bool,
)
define(
    "config",
    default="config/config.json",
    help="Config file location, default is 'config/config.json'",
    type=str,
)
define("verify", default=False, help="Verify chain, default False", type=bool)
define("server", default=False, help="Is server for testing", type=bool)
define("client", default=False, help="Is client for testing", type=bool)
define(
    "mongohost",
    default="",
    help="Value to override mongodb_host config value",
    type=str,
)
define(
    "modes",
    default=[],
    type=str,
    multiple=True,
    help="Operation modes. node, web, pool",
)
define("ignore", default=False, help="Added for testing", type=str)


class WorkerVars:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


from tornado.ioloop import IOLoop
from tornado.platform.asyncio import AsyncIOMainLoop


class NodeApplication(Application):
    def __init__(self, test=False):
        options.parse_command_line(final=False)
        self.init_config(options)
        self.configure_logging()
        self.init_config_properties(test=test)
        if test:
            return
        if MODES.NODE.value in self.config.modes:
            self.init_seeds()
            self.init_seed_gateways()
            self.init_service_providers()
            self.init_groups()
            try:
                self.config.app_log.info(
                    "Node: {}:{}".format(self.config.peer_host, self.config.peer_port)
                )
            except Exception as e:
                self.config.app_log.info("{}, starting without node enabled.".format(e))
            if getattr(self.config, "kel_ready", False):
                self.config.node_server_instance = self.config.nodeServer()
                self.config.node_server_instance.bind(self.config.peer_port)
                self.config.node_server_instance.start(1)

        if MODES.WEB.value in self.config.modes:
            if os.path.exists(path.join(path.dirname(__file__), "..", "static")):
                static_path = path.join(path.dirname(__file__), "..", "static")
            else:
                static_path = path.join(
                    path.dirname(__file__), "static"
                )  # probably running from binary

            if os.path.exists(
                path.join(path.join(path.dirname(__file__), "..", "static"), "unwrap")
            ):
                static_unwrap_path = path.join(
                    path.join(path.dirname(__file__), "..", "static"), "unwrap"
                )
            else:
                static_unwrap_path = path.join(
                    path.join(path.dirname(__file__), "static"), "unwrap"
                )  # probably running from binary

            plugin_app_static = path.join(
                path.dirname(__file__),
                "..",
                "plugins",
                "centeridentity",
                "static",
                "app",
            )
            self.default_handlers = [
                (
                    r"/unwrap/([\w\-0-9\/]+\.[\w]+)",
                    StaticFileHandler,
                    {"path": static_unwrap_path},
                ),
                (
                    r"/yadacoinstatic/app/(.*)",
                    StaticFileHandler,
                    {"path": plugin_app_static},
                ),
                (r"/yadacoinstatic/(.*)", StaticFileHandler, {"path": static_path}),
            ]
            self.init_websocket()
            self.init_webui()
            self.init_plugins()
            self.ensure_operator_setup_available()
            self.init_http()
            self.init_whitelist()
            self.init_jwt()
        if MODES.POOL.value in self.config.modes and (
            MODES.NODE.value not in self.config.modes
            or getattr(self.config, "kel_ready", False)
        ):
            self.init_pool()
        self.init_ioloop()

    async def remove_peer(self, stream, close=True, reason=None):
        if reason:
            await self.config.nodeShared.write_params(
                stream, "disconnect", {"reason": reason}
            )
        if close:
            try:
                stream.close()
            except Exception:
                pass
        if not hasattr(stream, "peer"):
            return
        from yadacoin.tcpsocket.base import _stream_peer_key

        id_attr = _stream_peer_key(stream)
        peer_cls = stream.peer.__class__.__name__
        if id_attr in self.config.nodeServer.inbound_streams.get(peer_cls, {}):
            del self.config.nodeServer.inbound_streams[peer_cls][id_attr]

        if id_attr in self.config.nodeServer.inbound_pending.get(peer_cls, {}):
            del self.config.nodeServer.inbound_pending[peer_cls][id_attr]

        if id_attr in self.config.nodeClient.outbound_streams.get(peer_cls, {}):
            del self.config.nodeClient.outbound_streams[peer_cls][id_attr]
            if stream.peer.identity is not None:
                self.config.nodeClient.outbound_ignore[peer_cls][
                    stream.peer.identity.username_signature
                ] = int(time())

        if id_attr in self.config.nodeClient.outbound_pending.get(peer_cls, {}):
            del self.config.nodeClient.outbound_pending[peer_cls][id_attr]
            if stream.peer.identity is not None:
                self.config.nodeClient.outbound_ignore[peer_cls][
                    stream.peer.identity.username_signature
                ] = int(time())

        self.delete_retry_messages(id_attr)

    def delete_retry_messages(self, rid):
        try:
            for y in self.config.nodeServer.retry_messages.copy():
                if y[0] == rid:
                    del self.config.nodeServer.retry_messages[y]
        except:
            pass

        try:
            for y in self.config.nodeClient.retry_messages.copy():
                if y[0] == rid:
                    del self.config.nodeClient.retry_messages[y]
        except:
            pass

    async def background_kel_checker(self):
        """Poll for KEL inception being confirmed on-chain; update active signing key."""
        if not hasattr(self.config, "kel_manager"):
            return
        try:
            await self.config.kel_manager.background_kel_checker()
        except Exception:
            self.config.app_log.error(format_exc())

    async def background_peers(self):
        """Peers management coroutine. responsible for peers testing and outgoing connections"""
        if hasattr(self.config, "background_process_debug"):
            self.config.app_log.debug("background_peers")
        if not hasattr(self.config, "background_peers"):
            self.config.background_peers = WorkerVars(busy=False)
        if self.config.background_peers.busy:
            self.config.app_log.debug("background_peers - busy")
            return
        self.config.background_peers.busy = True
        try:
            await self.config.peer.ensure_peers_connected()
            self.config.health.peer.last_activity = int(time())
        except:
            self.config.app_log.error(format_exc())
        self.config.background_peers.busy = False

    async def background_status(self):
        """This background co-routine is responsible for status collection and display"""
        if hasattr(self.config, "background_process_debug"):
            self.config.app_log.debug("background_status")
        if not hasattr(self.config, "background_status"):
            self.config.background_status = WorkerVars(busy=False, last_summary=None)
            await self.config.mongo.async_db.node_status.delete_many({"archived": True})
            await self.config.mongo.async_db.node_status.update_many(
                {}, {"$set": {"archived": True}}
            )
            if (
                Docker.is_inside_docker()
                and hasattr(self.config, "docker_debug")
                and self.config.docker_debug
            ):
                self.config.background_status.docker = Docker()
        if self.config.background_status.busy:
            self.config.app_log.debug("background_status - busy")
            return
        self.config.background_status.busy = True
        try:
            status = await self.config.get_status()
            status["synced"] = await Peer.is_synced()
            status["timestamp"] = int(time())
            status["processing_queues"] = self.config.processing_queues.to_status_dict()
            await self.config.health.check_health()
            status["health"] = self.config.health.to_dict()
            status["message_sender"] = {
                "nodeServer": {
                    "num_messages": len(list(self.config.nodeServer.retry_messages))
                },
                "nodeClient": {
                    "num_messages": len(list(self.config.nodeClient.retry_messages))
                },
            }
            status["slow_queries"] = {
                "count": len(self.config.mongo.async_db.slow_queries),
                "detail": self.config.mongo.async_db.slow_queries,
            }
            status["transaction_tracker"] = {
                "nodeServer": self.config.nodeServer.newtxn_tracker.to_dict(),
                "nodeClient": self.config.nodeClient.newtxn_tracker.to_dict(),
            }
            status["disconnect_tracker"] = {
                "nodeServer": self.config.nodeServer.disconnect_tracker.to_dict(),
                "nodeClient": self.config.nodeClient.disconnect_tracker.to_dict(),
            }
            if (
                Docker.is_inside_docker()
                and hasattr(self.config, "docker_debug")
                and self.config.docker_debug
            ):
                self.config.background_status.docker.set_container_stats()
                status["docker"] = self.config.background_status.docker.to_dict()

            if hasattr(self.config, "debug_memory") and self.config.debug_memory:
                from pympler import muppy, summary

                all_objects = muppy.get_objects()
                summarized = summary.summarize(all_objects)
                summary.print_(summarized)
                dict_list = []
                for item in summarized:
                    type_str, num_objects, total_size = item
                    dict_list.append(
                        {
                            "type": str(type_str),  # Convert type to string
                            "num_objects": num_objects,
                            "total_size": total_size,
                        }
                    )
                if self.config.background_status.last_summary:
                    diff = summary.get_diff(
                        self.config.background_status.last_summary, summarized
                    )
                    summary.print_(diff)
                    diff_dict_list = []
                    for item in diff:
                        type_str, num_diff, size_diff = item
                        if num_diff or size_diff:
                            diff_dict_list.append(
                                {
                                    "type": str(type_str),  # Convert type to string
                                    "num_diff": num_diff,
                                    "size_diff": size_diff,
                                }
                            )
                    status["memory"] = {"diff": diff_dict_list}
                self.config.background_status.last_summary = summarized

            if (
                hasattr(self.config, "log_health_status")
                and self.config.log_health_status
            ):
                if status["health"]["status"]:
                    self.config.app_log.info(json.dumps(status, indent=4))
                else:
                    self.config.app_log.warning(json.dumps(status, indent=4))
            await self.config.mongo.async_db.node_status.delete_many(
                {"timestamp": {"$lt": status["timestamp"] - (60 * 60 * 24)}}
            )
            await self.config.mongo.async_db.node_status.insert_one(status)
        except Exception:
            self.config.app_log.error(format_exc())
        self.config.background_status.busy = False

    async def background_block_checker(self):
        """
        Responsible for propagating new blocks in the network.

        This coroutine ensures that newly discovered blocks are efficiently distributed to peers.
        It continuously monitors the latest block and triggers propagation only when a change is detected.

        If a new block is found (i.e., its height or hash has changed), it is immediately broadcasted to peers.
        Additionally, if no new block has been found for a defined period,
        it will resend the latest known block to maintain synchronization across nodes (default: 300s).

        This mechanism prevents redundant broadcasts while ensuring all peers
        stay up-to-date with the latest blockchain state.
        """
        if hasattr(self.config, "background_process_debug"):
            self.config.app_log.debug("background_block_checker")
        if not hasattr(self.config, "background_block_checker"):
            self.config.background_block_checker = WorkerVars(
                busy=False, last_send=0, last_block_height=0, last_block_hash=None
            )
        if self.config.background_block_checker.busy:
            self.config.app_log.debug("background_block_checker - busy")
            return
        self.config.background_block_checker.busy = True

        try:
            current_block = LatestBlock.block
            last_block_height = self.config.background_block_checker.last_block_height
            last_block_hash = self.config.background_block_checker.last_block_hash

            if current_block:
                if hasattr(self.config, "background_process_debug"):
                    self.config.app_log.debug(
                        f"Current block: Height={current_block.index}, Hash={current_block.hash}"
                    )

                # Check if the block height or hash has changed
                if (
                    current_block.index != last_block_height
                    or current_block.hash != last_block_hash
                ):
                    self.config.background_block_checker.last_block_height = (
                        current_block.index
                    )
                    self.config.background_block_checker.last_block_hash = (
                        current_block.hash
                    )

                    self.config.app_log.info(
                        f"New block detected: Height={current_block.index}, "
                        f"Hash={current_block.hash}, Time={datetime.fromtimestamp(current_block.time).strftime('%Y-%m-%d %H:%M:%S')}"
                    )

                    # Propagate the new block to peers
                    await self.config.nodeShared.send_block_to_peers(current_block)
                    self.config.background_block_checker.last_send = int(time())
                    self.config.app_log.info(
                        f"Block {current_block.index} successfully propagated to peers."
                    )
                elif int(time()) - self.config.background_block_checker.last_send > 300:
                    # Regular propagation if no new block but timeout exceeded
                    self.config.app_log.info(
                        "Regular propagation triggered after timeout."
                    )
                    self.config.background_block_checker.last_send = int(time())
                    await self.config.nodeShared.send_block_to_peers(current_block)
                else:
                    if hasattr(self.config, "background_process_debug"):
                        self.config.app_log.debug(
                            f"No propagation needed. Last send: {self.config.background_block_checker.last_send}, "
                            f"Time since last send: {int(time()) - self.config.background_block_checker.last_send}s"
                        )
            else:
                self.config.app_log.debug("No current block available to propagate.")

        except Exception:
            self.config.app_log.error(format_exc())
        finally:
            self.config.health.block_checker.last_activity = int(time())
            self.config.background_block_checker.busy = False

    async def background_newblock_stress_test(self):
        # only tests outbound currently
        for peer_cls in list(self.config.nodeClient.outbound_streams.keys()).copy():
            for rid in self.config.nodeClient.outbound_streams[peer_cls]:
                for x in range(50):
                    txn = await Transaction.generate()
                    block = await Block.generate(
                        transactions=[txn],
                        index=600000,
                    )
                    # self.config.nodeClient.retry_messages[
                    #     (rid, "newtxn", txn.transaction_signature)
                    # ] = {
                    #     "transaction": txn.to_dict(),
                    #     "test": True,
                    # }
                    self.config.processing_queues.block_queue.add(
                        BlockProcessingQueueItem(
                            Blockchain(block),
                            self.config.nodeClient.outbound_streams[peer_cls][rid],
                        )
                    )

    async def background_message_sender(self):
        if hasattr(self.config, "background_process_debug"):
            self.config.app_log.debug("background_message_sender")
        if not hasattr(self.config, "background_message_sender"):
            self.config.background_message_sender = WorkerVars(busy=False)
        if self.config.background_message_sender.busy:
            self.config.app_log.debug("background_message_sender - busy")
            return
        self.config.background_message_sender.busy = True
        try:
            for x in self.config.nodeServer.retry_messages.copy():
                message = self.config.nodeServer.retry_messages.get(x)
                if not message:
                    if x in self.config.nodeServer.retry_messages:
                        del self.config.nodeServer.retry_messages[x]
                    self.config.app_log.debug("background_message_sender - continue 1")
                    continue
                message.setdefault("retry_attempts", 0)
                message["retry_attempts"] += 1
                found = False
                for peer_cls in list(
                    self.config.nodeServer.inbound_streams.keys()
                ).copy():
                    if x[0] in self.config.nodeServer.inbound_streams[peer_cls]:
                        found = True
                        if message["retry_attempts"] > 3:
                            self.config.nodeServer.retry_messages.pop(x, None)
                            self.config.app_log.warning(
                                "dropped unacked nodeServer retry; peer left connected: %s",
                                x,
                            )
                            break
                        if len(x) > 3:
                            await self.config.nodeShared.write_result(
                                self.config.nodeServer.inbound_streams[peer_cls][x[0]],
                                x[1],
                                message,
                                x[3],
                            )
                        else:
                            await self.config.nodeShared.write_params(
                                self.config.nodeServer.inbound_streams[peer_cls][x[0]],
                                x[1],
                                message,
                            )
                        break
                if not found:
                    self.delete_retry_messages(
                        x[0],
                    )

            for x in self.config.nodeClient.retry_messages.copy():
                message = self.config.nodeClient.retry_messages.get(x)
                if not message:
                    if x in self.config.nodeClient.retry_messages:
                        del self.config.nodeClient.retry_messages[x]
                    self.config.app_log.debug("background_message_sender - continue 3")
                    continue
                message.setdefault("retry_attempts", 0)
                message["retry_attempts"] += 1
                found = False
                for peer_cls in list(
                    self.config.nodeClient.outbound_streams.keys()
                ).copy():
                    if x[0] in self.config.nodeClient.outbound_streams[peer_cls]:
                        found = True
                        if message["retry_attempts"] > 3:
                            self.config.nodeClient.retry_messages.pop(x, None)
                            self.config.app_log.warning(
                                "dropped unacked nodeClient retry; peer left connected: %s",
                                x,
                            )
                            break
                        if message.get("test"):
                            break
                        if len(x) > 3:
                            await self.config.nodeShared.write_result(
                                self.config.nodeClient.outbound_streams[peer_cls][x[0]],
                                x[1],
                                message,
                                x[3],
                            )
                        else:
                            await self.config.nodeShared.write_params(
                                self.config.nodeClient.outbound_streams[peer_cls][x[0]],
                                x[1],
                                message,
                            )
                        break
                if not found:
                    self.delete_retry_messages(
                        x[0],
                    )

            self.config.health.message_sender.last_activity = int(time())

        except Exception:
            self.config.app_log.error(format_exc())
        self.config.background_message_sender.busy = False

    async def background_txn_queue_processor(self):
        if hasattr(self.config, "background_process_debug"):
            self.config.app_log.debug("background_txn_queue_processor")
        if not hasattr(self.config, "background_txn_queue_processor"):
            self.config.background_txn_queue_processor = WorkerVars(busy=False)
        if self.config.background_txn_queue_processor.busy:
            self.config.app_log.debug("background_txn_queue_processor - busy")
            return
        self.config.background_txn_queue_processor.busy = True
        try:
            if self.config.processing_queues.transaction_queue.queue:
                self.config.processing_queues.transaction_queue.time_sum_start()
                await self.config.node_server_instance.process_transaction_queue()
                self.config.processing_queues.transaction_queue.time_sum_end()
            self.config.health.transaction_processor.last_activity = int(time())
        except:
            self.config.app_log.error(format_exc())
            self.config.processing_queues.transaction_queue.time_sum_end()
        self.config.background_txn_queue_processor.busy = False

    async def background_block_queue_processor(self):
        if hasattr(self.config, "background_process_debug"):
            self.config.app_log.debug("background_block_queue_processor")
        if not hasattr(self.config, "background_block_queue_processor"):
            self.config.background_block_queue_processor = WorkerVars(busy=False)
        if self.config.background_block_queue_processor.busy:
            self.config.app_log.debug("background_block_queue_processor - busy")
            return
        self.config.background_block_queue_processor.busy = True
        while True:
            try:
                synced = await Peer.is_synced()
                skip = False
                if self.config.processing_queues.block_queue.queue:
                    if (
                        time() - self.config.health.consensus.last_activity
                        < CHAIN.FORCE_CONSENSUS_TIME_THRESHOLD
                    ):
                        skip = True
                if not skip or not synced:
                    await self.config.consensus.sync_bottom_up(synced)
                    self.config.health.consensus.last_activity = time()
            except Exception:
                self.config.app_log.error(format_exc())

            try:
                if self.config.processing_queues.block_queue.queue:
                    self.config.processing_queues.block_queue.time_sum_start()
                    await self.config.consensus.process_block_queue()
                    self.config.processing_queues.block_queue.time_sum_end()
                self.config.health.block_inserter.last_activity = int(time())
            except:
                self.config.app_log.error(format_exc())
                self.config.processing_queues.block_queue.time_sum_end()

            synced = await Peer.is_synced()
            if not synced and self.config.processing_queues.block_queue.queue:
                continue
            break
        self.config.background_block_queue_processor.busy = False

    async def background_pool_payer(self):
        """Responsible for paying miners"""
        """
        New blocks will directly trigger the correct event.
        This co-routine checks if new transactions have been received, or if special_min is triggered,
        So we can update the miners.
        """
        if hasattr(self.config, "background_process_debug"):
            self.config.app_log.debug("background_pool_payer")
        if not hasattr(self.config, "background_pool_payer"):
            self.config.background_pool_payer = WorkerVars(busy=False)
        if self.config.background_pool_payer.busy:
            self.config.app_log.debug("background_pool_payer - busy")
            return
        self.config.background_pool_payer.busy = True
        try:
            if self.config.pp:
                await self.config.pp.do_payout()

            self.config.health.pool_payer.last_activity = int(time())
        except Exception:
            self.config.app_log.error(format_exc())
        self.config.background_pool_payer.busy = False

    async def background_cache_validator(self):
        """Responsible for validating the cache and clearing it when necessary"""

        if hasattr(self.config, "background_process_debug"):
            self.config.app_log.debug("background_cache_validator")
        if not hasattr(self.config, "background_cache_validator"):
            self.config.background_cache_validator = WorkerVars(busy=False)
        if self.config.background_cache_validator.busy:
            self.config.app_log.debug("background_cache_validator - busy")
            return
        self.config.background_cache_validator.busy = True
        if not hasattr(self.config, "cache_inited"):
            self.cache_collections = [
                x
                for x in await self.config.mongo.async_db.list_collection_names()
                if x.endswith("_cache")
            ]
            self.cache_last_times = {}
            try:
                async for x in self.config.mongo.async_db.blocks.find(
                    {"updated_at": {"$exists": False}}
                ):
                    await self.config.mongo.async_db.blocks.update_one(
                        {"index": x["index"]}, {"$set": {"updated_at": time()}}
                    )
                for cache_collection in self.cache_collections:
                    self.cache_last_times[cache_collection] = 0
                    await self.config.mongo.async_db[cache_collection].delete_many(
                        {"cache_time": {"$exists": False}}
                    )
                self.config.cache_inited = True
            except Exception:
                self.config.app_log.error(format_exc())
        self.config.background_cache_validator.busy = False

        """
        We check for cache items that are not currently in the blockchain
        If not, we delete the cached item.
        """
        try:
            for cache_collection in self.cache_collections:
                if not self.cache_last_times.get(cache_collection):
                    self.cache_last_times[cache_collection] = 0
                latest = await self.config.mongo.async_db[cache_collection].find_one(
                    {"cache_time": {"$gt": self.cache_last_times[cache_collection]}},
                    sort=[("height", -1)],
                )
                if latest:
                    self.cache_last_times[cache_collection] = latest["cache_time"]
                else:
                    self.cache_last_times[cache_collection] = 0

                pipeline = [
                    {
                        "$match": {
                            "cache_time": {
                                "$gt": self.cache_last_times[cache_collection]
                            }
                        }
                    },
                    {
                        "$group": {
                            "_id": {"block_hash": "$block_hash", "height": "$height"},
                            "cache_time": {"$first": "$cache_time"},
                        }
                    },
                    {"$sort": {"height": -1}},
                ]
                async for txn in self.config.mongo.async_db[cache_collection].aggregate(
                    pipeline
                ):
                    if not await self.config.mongo.async_db.blocks.find_one(
                        {
                            "index": txn["_id"].get("height"),
                            "hash": txn["_id"].get("block_hash"),
                        }
                    ) and not await self.config.mongo.async_db.miner_transactions.find_one(
                        {
                            "id": txn.get("id"),
                        }
                    ):
                        await self.config.mongo.async_db[cache_collection].delete_many(
                            {"height": txn.get("height")}
                        )
                        break
                    else:
                        if txn["cache_time"] > self.cache_last_times[cache_collection]:
                            self.cache_last_times[cache_collection] = txn["cache_time"]

            self.config.health.cache_validator.last_activity = int(time())
        except Exception:
            self.config.app_log.error("error in background_cache_validator")
            self.config.app_log.error(format_exc())

    async def background_mempool_cleaner(self):
        """Responsible for removing failed transactions from the mempool and old transaction confirmations"""

        if hasattr(self.config, "background_process_debug"):
            self.config.app_log.debug("background_mempool_cleaner")
        if not hasattr(self.config, "background_mempool_cleaner"):
            self.config.background_mempool_cleaner = WorkerVars(busy=False)
        if self.config.background_mempool_cleaner.busy:
            self.config.app_log.debug("background_mempool_cleaner - busy")
            return
        self.config.background_mempool_cleaner.busy = True
        try:
            from yadacoin.core.transaction import Transaction

            await Transaction.ensure_kel_slot_index(self.config)
            await self.config.TU.clean_mempool(self.config)
            await self.config.TU.clean_txn_tracking(self.config)
            self.config.health.mempool_cleaner.last_activity = int(time())
        except Exception:
            self.config.app_log.error(format_exc())
        self.config.background_mempool_cleaner.busy = False

    async def background_mempool_sender(self):
        """Responsible for rebroadcasting mempool transactions"""
        if hasattr(self.config, "background_process_debug"):
            self.config.app_log.debug("background_mempool_sender")

        if not hasattr(self.config, "background_mempool_sender"):
            self.config.background_mempool_sender = WorkerVars(busy=False)

        if self.config.background_mempool_sender.busy:
            self.config.app_log.debug("background_mempool_sender - busy")
            return
        self.config.background_mempool_sender.busy = True
        try:
            await self.config.TU.rebroadcast_mempool(self.config, include_zero=True)
        except Exception:
            self.config.app_log.error(format_exc())
        self.config.background_mempool_sender.busy = False

    async def background_transactions_combining(self):
        """Responsible for combining small UTXOs into larger ones in the background"""
        if hasattr(self.config, "background_process_debug"):
            self.config.app_log.debug("background_transactions_combining")

        if not hasattr(self.config, "background_transactions_combining"):
            self.config.background_transactions_combining = WorkerVars(busy=False)
        if self.config.background_transactions_combining.busy:
            self.config.app_log.debug("background_transactions_combining - busy")
            return
        self.config.background_transactions_combining.busy = True
        try:
            await self.config.TU.combine_oldest_transactions(self.config)
        except Exception:
            self.config.app_log.error(format_exc())
        self.config.background_transactions_combining.busy = False

    async def background_nonce_processor(self):
        """Responsible for processing all share submissions from miners"""

        if hasattr(self.config, "background_process_debug"):
            self.config.app_log.debug("background_nonce_processor")
        if not hasattr(self.config, "background_nonce_processor"):
            self.config.background_nonce_processor = WorkerVars(busy=False)
        if self.config.background_nonce_processor.busy:
            self.config.app_log.debug("background_nonce_processor - busy")
            return
        self.config.background_nonce_processor.busy = True
        nonce_queue = getattr(self.config.processing_queues, "nonce_queue", None)
        timing = False
        try:
            if (
                nonce_queue is not None
                and nonce_queue.queue
                and getattr(self.config, "mp", None) is not None
            ):
                nonce_queue.time_sum_start()
                timing = True
                await self.config.mp.process_nonce_queue()
                nonce_queue.time_sum_end()
                timing = False
            self.config.health.nonce_processor.last_activity = int(time())
        except Exception:
            self.config.app_log.error(format_exc())
            if timing:
                nonce_queue.time_sum_end()
        finally:
            self.config.background_nonce_processor.busy = False

    async def background_node_testing(self):
        """Responsible for testing masternodes in the background."""

        block_index = self.config.LatestBlock.block.index

        if block_index < CHAIN.PAY_MASTER_NODES_FORK:
            self.config.app_log.info(
                f"Block height {block_index} is less than PAY_MASTER_NODES_FORK ({CHAIN.PAY_MASTER_NODES_FORK}). Skipping masternode testing."
            )
            return

        if not hasattr(self.config, "background_node_testing"):
            self.config.background_node_testing = WorkerVars(busy=False)

        if self.config.background_node_testing.busy:
            self.config.app_log.debug("background_node_testing - busy")
            return

        self.config.background_node_testing.busy = True
        try:
            from yadacoin.core.nodes import Nodes

            await Nodes.apply_dynamic_nodes()
            successful_nodes = await NodesTester.test_all_nodes(block_index)
            self.config.app_log.info(
                f"Background node testing completed. Successful nodes: {len(successful_nodes)}"
            )
            self.config.health.node_tester.last_activity = int(time())
        except Exception as e:
            self.config.app_log.error(f"Error in background_node_testing: {e}")
        finally:
            self.config.background_node_testing.busy = False

    def configure_logging(self):
        # tornado.log.enable_pretty_logging()
        self.config.app_log = logging.getLogger("tornado.application")
        tornado.log.enable_pretty_logging(logger=self.config.app_log)
        for handler in self.config.app_log.handlers:
            # Only the console (pretty) handler uses the peer-aware prefix; the
            # rotating file handler keeps its own one-line format.
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, RotatingFileHandler
            ):
                handler.setFormatter(
                    PeerLogFormatter(
                        datefmt=tornado.log.LogFormatter.DEFAULT_DATE_FORMAT
                    )
                )
        self.config.app_log.addFilter(PeerContextFilter())
        logfile = path.abspath("yada_app.log")
        # Rotate log after reaching 512K, keep 5 old copies.
        rotateHandler = RotatingFileHandler(logfile, "a", 512 * 1024, 5)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        rotateHandler.setFormatter(formatter)
        self.config.app_log.addHandler(rotateHandler)
        self.config.app_log.setLevel(
            getattr(logging, self.config.log_level, logging.INFO)
        )
        if self.config.debug:
            self.config.app_log.setLevel(logging.DEBUG)
        if hasattr(self.config, "asyncio_debug") and self.config.asyncio_debug:
            logging.basicConfig(level=logging.DEBUG)
            AsyncIOMainLoop().install()
            ioloop = IOLoop.current()
            if hasattr(self.config, "asyncio_debug_duration"):
                asyncio_debug_duration = self.config.asyncio_debug_duration
            else:
                asyncio_debug_duration = 0.05
            ioloop.slow_callback_duration = asyncio_debug_duration

        self.access_log = logging.getLogger("tornado.access")
        tornado.log.enable_pretty_logging()
        logfile2 = path.abspath("yada_access.log")
        rotateHandler2 = RotatingFileHandler(logfile2, "a", 512 * 1024, 5)
        formatter2 = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        rotateHandler2.setFormatter(formatter2)
        self.access_log.addHandler(rotateHandler2)

        self.config.app_log.propagate = False
        self.access_log.propagate = False
        # This logguer config is quite a mess, but works well enough for the time being.
        logging.getLogger("engineio").propagate = False

    def init_config(self, options):
        if not path.isfile(options.config):
            self.config = yadacoin.core.config.Config.generate()
            try:
                os.makedirs(os.path.dirname(options.config))
            except:
                pass
            with open(options.config, "w") as f:
                f.write(self.config.to_json(include_sensitive=True))

        with open(options.config) as f:
            self.config = yadacoin.core.config.Config(json.loads(f.read()))
            # Sets the global var for all objects
            yadacoin.core.config.CONFIG = self.config
            self.config.config_path = os.path.abspath(options.config)
            self.config.debug = options.debug
            # force network, command line one takes precedence
            if options.network != "":
                self.config.network = options.network

        self.config.reset = options.reset
        if options.mongohost and self.config.mongodb_host in (
            "localhost",
            "127.0.0.1",
            "",
        ):
            self.config.mongodb_host = options.mongohost
        if options.modes:
            self.config.modes = options.modes
        try:
            from plugins.operator.setup import apply_setup_gate
        except ImportError:
            apply_setup_gate = None
        if apply_setup_gate is not None:
            apply_setup_gate(self.config)

    def init_consensus(self):
        self.config.consensus = tornado.ioloop.IOLoop.current().run_sync(
            Consensus.init_async
        )
        if options.verify:
            self.config.app_log.info("Verifying existing blockchain")
            tornado.ioloop.IOLoop.current().run_sync(
                self.config.consensus.verify_existing_blockchain
            )
        else:
            self.config.app_log.info(
                "Verification of existing blockchain skipped by config"
            )

    def init_whitelist(self):
        api_whitelist = "api_whitelist.json"
        api_whitelist_filename = options.config.replace(
            ntpath.basename(options.config), api_whitelist
        )
        if path.isfile(api_whitelist_filename):
            with open(api_whitelist_filename) as f:
                self.config.api_whitelist = [x["host"] for x in json.loads(f.read())]

    def _track(self, callback, interval_ms):
        async def guarded():
            if getattr(self.config, "maintenance", False):
                return
            await callback()

        periodic = PeriodicCallback(guarded, interval_ms)
        self._periodics.append(periodic)
        periodic.start()
        return periodic

    def init_ioloop(self):
        self._periodics = []
        self._node_test_call = None
        tornado.ioloop.IOLoop.current().set_default_executor(
            ThreadPoolExecutor(max_workers=1)
        )

        node_ready = MODES.NODE.value not in self.config.modes or getattr(
            self.config, "kel_ready", False
        )
        self._node_services_started = False
        self._pool_started = False
        if MODES.NODE.value in self.config.modes and node_ready:
            self._start_node_periodics()
            self._node_services_started = True
        if MODES.POOL.value in self.config.modes and node_ready:
            self._pool_started = True
        self.init_ioloop_tail()

    def _start_node_periodics(self):
        if getattr(self, "_node_periodics_started", False):
            return
        if MODES.NODE.value in self.config.modes and not getattr(
            self.config, "kel_ready", False
        ):
            return
        self._node_periodics_started = True
        if MODES.NODE.value in self.config.modes:
            self._track(self.background_status, self.config.status_wait * 1000)
            self._track(
                self.background_kel_checker,
                NodeKeyRotationManager.POLL_INTERVAL_SECONDS * 1000,
            )
            self._track(
                self.background_block_checker, self.config.block_checker_wait * 1000
            )
            self._track(
                self.background_cache_validator,
                self.config.cache_validator_wait * 1000,
            )
            self._track(
                self.background_mempool_cleaner, self.config.mempool_cleaner_wait * 1000
            )
            self._track(
                self.background_mempool_sender, self.config.mempool_sender_wait * 1000
            )
            self._track(
                self.background_txn_queue_processor,
                self.config.txn_queue_processor_wait * 1000,
            )
            self._track(
                self.background_block_queue_processor,
                self.config.block_queue_processor_wait * 1000,
            )
            self._track(self.background_peers, self.config.peers_wait * 1000)
            self._track(
                self.background_message_sender, self.config.message_sender_wait * 1000
            )
            self._track(self.background_node_testing, 60 * 60 * 1000)
            # Populate eligible_nodes_by_address immediately on startup so coinbase
            # validation works before the first hourly background_node_testing fires.
            # Delay slightly so the HTTP server is fully listening before the node
            # tests begin (which can take several seconds and block the IOLoop).
            self._node_test_call = tornado.ioloop.IOLoop.current().call_later(
                5, self.background_node_testing
            )

            if self.config.peer_type in [
                PEER_TYPES.SERVICE_PROVIDER.value,
                PEER_TYPES.SEED_GATEWAY.value,
                PEER_TYPES.SEED.value,
                PEER_TYPES.USER.value,
            ] and self.config.peer_type not in [PEER_TYPES.POOL.value]:
                self._track(
                    self.background_transactions_combining,
                    self.config.transactions_combining_wait * 1000,
                )

            if MODES.POOL.value in self.config.modes:
                self._track(
                    self.background_nonce_processor,
                    self.config.nonce_processor_wait * 1000,
                )

    def init_ioloop_tail(self):
        try:
            from plugins.operator.letsencrypt import start_renew_loop
        except ImportError:
            start_renew_loop = None
        if start_renew_loop is not None:
            start_renew_loop(self.config)
        if self.config.pool_payout:
            self.config.app_log.info("PoolPayout activated")
            self.config.pp = PoolPayer()
            self._track(self.background_pool_payer, self.config.pool_payer_wait * 1000)

        if (
            hasattr(self.config, "stress_test_newtxn")
            and self.config.stress_test_newtxn
        ):
            self._track(self.background_newtxn_stress_test, 3000)

        if (
            hasattr(self.config, "stress_test_newblock")
            and self.config.stress_test_newblock
        ):
            self._track(self.background_newblock_stress_test, 3000)

        while True:
            tornado.ioloop.IOLoop.current().start()

    def init_jwt(self):
        jwt_key = EccKey(curve="p256", d=int(self.config.private_key, 16))
        self.config.jwt_secret_key = jwt_key.export_key(format="PEM")
        self.config.jwt_public_key = (
            self.config.jwt_public_key or jwt_key.public_key().export_key(format="PEM")
        )
        self.config.jwt_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_nbf": False,
            "verify_iat": True,
            "verify_aud": False,
        }

    def init_seeds(self):
        if self.config.network == "mainnet":
            self.config.seeds = Peers.get_config_seeds() or Peers.get_seeds()
        elif self.config.network == "regnet":
            self.config.seeds = Peers.get_config_seeds()

    def init_seed_gateways(self):
        if self.config.network == "mainnet":
            self.config.seed_gateways = (
                Peers.get_config_seed_gateways() or Peers.get_seed_gateways()
            )
        elif self.config.network == "regnet":
            self.config.seed_gateways = Peers.get_config_seed_gateways()

    def init_service_providers(self):
        if self.config.network == "mainnet":
            self.config.service_providers = (
                Peers.get_config_service_providers() or Peers.get_service_providers()
            )
        elif self.config.network == "regnet":
            self.config.service_providers = Peers.get_config_service_providers()

    def init_groups(self):
        if self.config.network == "mainnet":
            self.config.groups = Peers.get_config_groups() or Peers.get_groups()
        elif self.config.network == "regnet":
            self.config.groups = Peers.get_config_groups()

    def init_websocket(self):
        self.default_handlers.extend(WEBSOCKET_HANDLERS)

    def init_webui(self):
        if self.config.peer_type == PEER_TYPES.SERVICE_PROVIDER.value or (
            hasattr(self.config, "activate_peerjs")
            and self.config.activate_peerjs == True
        ):
            self.default_handlers.extend(PEERJS_HANDLERS)

    def _plugin_search_dirs(self):
        for deps in (
            path.join(os.environ.get("YADA_PLUGINS_DIR", ""), ".pydeps"),
            "/plugins/.pydeps",
            path.join(path.dirname(__file__), "..", "plugins", ".pydeps"),
        ):
            if deps and path.isdir(deps) and deps not in sys.path:
                sys.path.insert(0, path.abspath(deps))
        search_dirs = []
        env_dir = os.environ.get("YADA_PLUGINS_DIR")
        if env_dir:
            search_dirs.append(env_dir)
        elif path.isdir("/plugins"):
            search_dirs.append("/plugins")
        repo_dir = path.join(path.dirname(__file__), "..", "plugins")
        if path.isdir(repo_dir):
            search_dirs.append(repo_dir)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            search_dirs.insert(0, path.join(meipass, "plugins"))
        resolved = []
        for plugin_dir in search_dirs:
            plugin_dir = path.abspath(plugin_dir)
            if not path.isdir(plugin_dir):
                continue
            parent = path.dirname(plugin_dir)
            if path.basename(plugin_dir) == "plugins" and parent not in sys.path:
                sys.path.insert(0, parent)
            resolved.append(plugin_dir)
        return resolved

    def _plugin_names(self):
        search_dirs = self._plugin_search_dirs()
        names = []
        seen = set()
        for plugin_dir in search_dirs:
            if not path.isdir(plugin_dir):
                continue
            for finder, name, ispkg in pkgutil.iter_modules([plugin_dir]):
                if name in seen or name.startswith("."):
                    continue
                seen.add(name)
                names.append(name)
            for name in os.listdir(plugin_dir):
                if name in seen or name.startswith("."):
                    continue
                pkg = path.join(plugin_dir, name)
                if path.isdir(pkg) and (
                    path.isfile(path.join(pkg, "handlers.py"))
                    or path.isfile(path.join(pkg, "__init__.py"))
                ):
                    seen.add(name)
                    names.append(name)
        return names

    def _plugin_enabled(self, name):
        if name in (
            "operator",
            "app",
            "nodeapi",
            "graphapi",
            "explorerapi",
            "kel",
            "apidocs",
            "product",
            "yadacoinwallet",
            "yadacoinpool",
            "yadapasswordsignin",
            "passwordrotation",
        ):
            return True
        disabled = getattr(self.config, "disabled_plugins", None) or []
        return name not in disabled

    def _plugin_manifest_path(self):
        return path.abspath(path.join(path.dirname(__file__), "..", "plugins.txt"))

    def _plugin_catalog(self):
        """Return {plugin name: clone url} from plugins.txt."""
        catalog = {}
        try:
            with open(self._plugin_manifest_path(), "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line or line.startswith("#") or "\t" not in line:
                        continue
                    name, url = line.split("\t", 1)
                    name = name.strip()
                    url = url.strip()
                    if not name or not url:
                        continue
                    if url.startswith("git@github.com:"):
                        url = "https://github.com/" + url[len("git@github.com:") :]
                    catalog[name] = url
        except OSError:
            return {}
        return catalog

    def _plugin_install_dir(self):
        """Directory where plugin checkouts live."""
        env_dir = os.environ.get("YADA_PLUGINS_DIR")
        if env_dir:
            return path.abspath(env_dir)
        if path.isdir("/plugins"):
            return "/plugins"
        return path.abspath(path.join(path.dirname(__file__), "..", "plugins"))

    def _operator_routes_registered(self):
        for handler in getattr(self, "default_handlers", []):
            if not isinstance(handler, (list, tuple)) or not handler:
                continue
            pattern = handler[0]
            if isinstance(pattern, str) and pattern.startswith("/operator"):
                return True
        return False

    def _node_needs_setup(self):
        """True while the node still needs the browser setup flow."""
        if not (getattr(self.config, "username", "") or "").strip():
            return True
        second_factor_file = os.environ.get("SECOND_FACTOR_FILE", "") or getattr(
            self.config, "second_factor_file", ""
        )
        if second_factor_file:
            try:
                with open(second_factor_file, "r", encoding="utf-8") as handle:
                    return not handle.read().strip()
            except OSError:
                return True
        return not (os.environ.get("SECOND_FACTOR", "") or "").strip()

    def _plugin_dependencies(self, name):
        """Return the plugin names imported by a plugin's Python sources."""
        plugin_dir = path.join(self._plugin_install_dir(), name)
        dependencies = set()
        for dirpath, dirnames, filenames in os.walk(plugin_dir):
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if dirname not in ("__pycache__", ".git")
            ]
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                try:
                    with open(
                        path.join(dirpath, filename),
                        "r",
                        encoding="utf-8",
                        errors="ignore",
                    ) as handle:
                        source = handle.read()
                except OSError:
                    continue
                dependencies.update(PLUGIN_IMPORT_RE.findall(source))
        dependencies.discard(name)
        return dependencies

    def _install_plugin_requirements(self, plugin_dir):
        """Install plugin requirements into the shared .pydeps directory."""
        requirements = path.join(plugin_dir, "requirements.txt")
        if not path.isfile(requirements):
            return
        name = path.basename(plugin_dir)
        deps = path.join(self._plugin_install_dir(), ".pydeps")
        try:
            os.makedirs(deps, exist_ok=True)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-input",
                    "--upgrade",
                    "--target",
                    deps,
                    "-r",
                    requirements,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
        except Exception:
            self.config.app_log.warning(
                "Could not install the %s plugin requirements\n%s",
                name,
                format_exc(),
            )
            return
        if result.returncode != 0:
            self.config.app_log.warning(
                "Could not install the %s plugin requirements: %s",
                name,
                (result.stderr or "").strip(),
            )

    def _install_plugin_checkout(self, name):
        """Clone one catalog plugin into the install directory."""
        url = self._plugin_catalog().get(name)
        if not url:
            self.config.app_log.error(
                "Cannot install the %s plugin: no entry in %s",
                name,
                self._plugin_manifest_path(),
            )
            return False
        root = self._plugin_install_dir()
        dest = path.join(root, name)
        if name != "operator" and path.isfile(path.join(dest, "handlers.py")):
            return True
        try:
            os.makedirs(root, exist_ok=True)
            tmp = tempfile.mkdtemp(prefix=".{}-".format(name), dir=root)
        except OSError:
            self.config.app_log.error(
                "Cannot install the %s plugin in %s\n%s", name, root, format_exc()
            )
            return False
        try:
            cloned = path.join(tmp, name)
            result = subprocess.run(
                ["git", "clone", "--depth", "1", url, cloned],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            if result.returncode != 0 or not path.isfile(
                path.join(cloned, "handlers.py")
            ):
                self.config.app_log.error(
                    "Could not clone the %s plugin from %s: %s",
                    name,
                    url,
                    (result.stderr or "").strip(),
                )
                return False
            self._install_plugin_requirements(cloned)
            if path.isdir(dest):
                shutil.rmtree(dest)
            shutil.move(cloned, dest)
        except Exception:
            self.config.app_log.error(
                "Could not install the %s plugin\n%s", name, format_exc()
            )
            return False
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.config.app_log.info("Installed the %s plugin in %s", name, dest)
        return True

    def _install_plugin_tree(self, name, seen=None):
        """Install a plugin and the plugins it imports."""
        seen = set() if seen is None else seen
        if name in seen:
            return True
        seen.add(name)
        if not self._install_plugin_checkout(name):
            return False
        catalog = self._plugin_catalog()
        for dependency in sorted(self._plugin_dependencies(name)):
            if dependency not in catalog:
                continue
            if not self._install_plugin_tree(dependency, seen):
                return False
        return True

    def _install_operator_plugin(self):
        """Clone the operator plugin and the plugins it imports."""
        return self._install_plugin_tree("operator")

    def ensure_operator_setup_available(self):
        """Offer to install the operator plugin when setup cannot be served.

        An unconfigured node without operator routes prints a setup URL that
        returns 404. Ask on the terminal whether to install the plugin from
        plugins.txt and load it into this process.
        """
        self._apply_operator_setup_gate()
        if self._operator_routes_registered() or not self._node_needs_setup():
            return
        install_dir = path.join(self._plugin_install_dir(), "operator")
        self.config.app_log.warning(
            "The operator plugin is not installed; /operator/setup returns 404."
        )
        stdin = getattr(sys, "stdin", None)
        try:
            interactive = bool(stdin and stdin.isatty())
        except (AttributeError, OSError, ValueError):
            interactive = False
        if not interactive:
            self.config.app_log.warning(
                "Install the operator plugin in %s and restart the node.",
                install_dir,
            )
            return
        if path.isdir(install_dir):
            prompt = (
                "The operator plugin exists at {} but its routes failed to load.\n"
                "Reinstall it (replaces that directory) and enable it now? [y/N] "
            ).format(install_dir)
        else:
            prompt = (
                "The operator plugin is required to finish setting up this node.\n"
                "Install it and enable it now? [y/N] "
            )
        sys.stdout.write(prompt)
        sys.stdout.flush()
        try:
            answer = (stdin.readline() or "").strip().lower()
        except (KeyboardInterrupt, OSError):
            sys.stdout.write("\n")
            sys.stdout.flush()
            answer = ""
        if answer not in ("y", "yes"):
            self.config.app_log.warning(
                "Continuing without the operator plugin; /operator/setup will "
                "return 404 until it is installed and the node restarts."
            )
            return
        if not self._install_operator_plugin():
            self.config.app_log.error(
                "The operator plugin was not installed; continuing without it."
            )
            return
        if not self._activate_operator_plugin():
            self.config.app_log.error(
                "The operator plugin was installed but its routes failed to load; "
                "check the log and restart the node."
            )
            return
        self.config.app_log.info(
            "Loaded the operator plugin from %s without restarting the node",
            install_dir,
        )

    def _activate_operator_plugin(self):
        """Load a freshly installed operator plugin in this process."""
        self._plugin_search_dirs()
        if getattr(self, "wildcard_router", None) is not None:
            self.reload_http_routes()
            loaded = self._operator_routes_registered()
        else:
            loaded = self._activate_plugin_tree("operator", set())
        if loaded:
            self._apply_operator_setup_gate()
        return loaded

    def _apply_operator_setup_gate(self):
        """Recompute setup_required after the operator plugin is available."""
        try:
            from plugins.operator.setup import apply_setup_gate
        except ImportError:
            return False
        apply_setup_gate(self.config)
        return True

    def _activate_plugin_tree(self, name, seen):
        """Load a plugin and its plugin dependencies into this process."""
        if name in seen:
            return True
        seen.add(name)
        catalog = self._plugin_catalog()
        for dependency in sorted(self._plugin_dependencies(name)):
            if dependency in catalog and not self._activate_plugin_tree(
                dependency, seen
            ):
                return False
        return self._load_plugin(name, run_postboot=True)

    def _load_plugin_handlers(self, run_postboot=False):
        for name in self._plugin_names():
            if not self._plugin_enabled(name):
                continue
            self._load_plugin(name, run_postboot=run_postboot)

    def _load_plugin(self, name, run_postboot=False):
        try:
            if run_postboot:
                try:
                    post_boot = importlib.import_module("plugins." + name + ".postboot")
                except ModuleNotFoundError:
                    post_boot = None
                if post_boot is not None and hasattr(post_boot, "go"):
                    tornado.ioloop.IOLoop.current().run_sync(
                        lambda post_boot=post_boot: post_boot.go(self)
                    )
            module_name = "plugins." + name + ".handlers"
            if module_name in sys.modules:
                plugin_handlers = importlib.reload(sys.modules[module_name])
            else:
                plugin_handlers = importlib.import_module(module_name)
        except Exception as exc:
            self.config.app_log.debug(
                "plugin %s load traceback\n%s", name, format_exc()
            )
            detail = str(exc).strip() or exc.__class__.__name__
            self.config.app_log.warning("plugin %s failed to load: %s", name, detail)
            return False
        if not hasattr(plugin_handlers, "HANDLERS"):
            return False
        if name == self.config.root_app:
            for handler in reversed(list(plugin_handlers.HANDLERS)):
                self.default_handlers.insert(0, handler)
        else:
            self.default_handlers.extend(plugin_handlers.HANDLERS)
        return True

    def init_plugins(self):
        self._load_plugin_handlers(run_postboot=True)

    def reload_http_routes(self):
        from tornado.routing import AnyMatches, Rule
        from tornado.web import _ApplicationRouter

        static_handlers = [
            handler
            for handler in getattr(self, "default_handlers", [])
            if isinstance(handler, tuple)
            and handler
            and handler[0]
            in (
                r"/unwrap/([\w\-0-9\/]+\.[\w]+)",
                r"/yadacoinstatic/app/(.*)",
                r"/yadacoinstatic/(.*)",
            )
        ]
        self.default_handlers = list(static_handlers)
        self.init_websocket()
        self.init_webui()
        self._load_plugin_handlers(run_postboot=False)
        self.wildcard_router = _ApplicationRouter(self, self.default_handlers.copy())
        self.default_router = _ApplicationRouter(
            self, [Rule(AnyMatches(), self.wildcard_router)]
        )

    def print_startup_banner(self):
        host = self.config.serve_host
        if host in ("0.0.0.0", "::", ""):
            host = "127.0.0.1"
        from urllib.parse import quote

        url = None
        if self._operator_routes_registered():
            code = quote(
                getattr(self.config, "operator_access_code", "") or "", safe=""
            )
            self.config.operator_access_code_shown_at = time()
            url = "http://{}:{}/operator/setup?code={}".format(
                host, self.config.serve_port, code
            )
        reset = "\033[0m"
        bold = "\033[1m"
        lines = (
            "██╗   ██╗ █████╗ ██████╗  █████╗  ██████╗ ██████╗ ██╗███╗   ██╗",
            "╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔═══██╗██║████╗  ██║",
            " ╚████╔╝ ███████║██║  ██║███████║██║     ██║   ██║██║██╔██╗ ██║",
            "  ╚██╔╝  ██╔══██║██║  ██║██╔══██║██║     ██║   ██║██║██║╚██╗██║",
            "   ██║   ██║  ██║██████╔╝██║  ██║╚██████╗╚██████╔╝██║██║ ╚████║",
            "   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝",
        )
        colors = (
            "\033[38;5;39m",
            "\033[38;5;45m",
            "\033[38;5;51m",
            "\033[38;5;50m",
            "\033[38;5;48m",
            "\033[38;5;46m",
        )
        out = ["", ""]
        for color, line in zip(colors, lines):
            out.append("{}{}{}{}".format(bold, color, line, reset))
        out.append("")
        if url is not None:
            out.append(
                "{}{}  VISIT {}{}{} TO CONFIGURE YOUR NODE{}".format(
                    bold,
                    "\033[38;5;226m",
                    "\033[1;97m",
                    url,
                    "\033[38;5;226m",
                    reset,
                )
            )
        else:
            out.append(
                "{}{}  OPERATOR SETUP UNAVAILABLE - operator plugin not installed{}".format(
                    bold, "\033[38;5;196m", reset
                )
            )
            out.append(
                "  Install it in {} and restart the node.".format(
                    path.join(self._plugin_install_dir(), "operator")
                )
            )
        out.append("")
        sys.stderr.write("\n".join(out) + "\n")
        sys.stderr.flush()

    def init_http(self):
        self.config.app_log.info(
            "API: http://{}:{}".format(self.config.serve_host, self.config.serve_port)
        )
        self.print_startup_banner()
        if os.path.exists(path.join(path.dirname(__file__), "..", "templates")):
            template_path = path.join(path.dirname(__file__), "..", "templates")
        else:
            template_path = path.join(path.dirname(__file__), "templates")
        settings = dict(
            app_title="Yadacoin Node",
            template_path=template_path,
            xsrf_cookies=False,  # TODO: sort out, depending on python client version (< 3.6) does not work with xsrf activated
            cookie_secret=sha256(self.config.private_key.encode("utf-8")).hexdigest(),
            compress_response=True,
            debug=options.debug,  # Also activates auto reload
            autoreload=False,
            serve_traceback=options.debug,
            yadacoin_vars={"node_version": version},
            yadacoin_config=self.config,
            mp=None,
            BU=yadacoin.core.blockchainutils.GLOBAL_BU,
            TU=yadacoin.core.transactionutils.TU,
            compiled_template_cache=False,
        )
        handlers = self.default_handlers.copy()
        super().__init__(handlers, **settings)
        self.config.application = self
        self.config.http_server = HTTPServer(self)
        self.config.http_server.listen(self.config.serve_port, self.config.serve_host)
        if (
            MODES.SSL.value in self.config.modes
            and hasattr(self.config, "ssl")
            and self.config.ssl.is_valid()
        ):
            ssl_ctx = ssl.create_default_context(
                ssl.Purpose.CLIENT_AUTH, cafile=self.config.ssl.ca_file
            )
            ssl_ctx.load_cert_chain(
                self.config.ssl.cert_file, keyfile=self.config.ssl.key_file
            )
            self.config.https_server = HTTPServer(self, ssl_options=ssl_ctx)
            self.config.https_server.listen(self.config.ssl.port)
        if hasattr(self.config, "email") and self.config.email.is_valid():
            self.config.emailer = Email()

    def init_pool(self):
        self.config.app_log.info(
            "Pool: {}:{}".format(self.config.peer_host, self.config.stratum_pool_port)
        )
        pool_ssl_ctx = None
        if getattr(self.config, "stratum_pool_tls", False):
            cert_file = (
                self.config.stratum_pool_tls_certfile or self.config.ssl.cert_file
            )
            key_file = self.config.stratum_pool_tls_keyfile or self.config.ssl.key_file
            ca_file = self.config.stratum_pool_tls_cafile or self.config.ssl.ca_file

            if not cert_file or not key_file:
                raise Exception(
                    "stratum_pool_tls is enabled but cert/key file is missing. "
                    "Set stratum_pool_tls_certfile and stratum_pool_tls_keyfile "
                    "(or configure ssl.certfile / ssl.keyfile)."
                )

            pool_ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            if ca_file:
                pool_ssl_ctx.load_verify_locations(cafile=ca_file)
            pool_ssl_ctx.load_cert_chain(cert_file, keyfile=key_file)
            self.config.app_log.info(
                "Pool TLS enabled on port {}".format(self.config.stratum_pool_port)
            )

        StratumServer.inbound_streams[Miner.__name__] = {}
        self._pool_ssl_ctx = pool_ssl_ctx
        self.config.pool_server = StratumServer(ssl_options=pool_ssl_ctx)
        StratumServer.config = self.config
        # Schedule pool initialization as a proper async task on the running
        # event loop.  Using run_sync here triggers concurrent.futures bridging
        # (_chain_future) inside motor/asyncio that causes a RecursionError in
        # Python 3.9's abc.ABCMeta.__instancecheck__ on macOS.
        StratumServer.config.mp = None
        tornado.ioloop.IOLoop.current().add_callback(self._init_pool_async)
        self.config.pool_server.listen(self.config.stratum_pool_port)

    async def _init_pool_async(self):
        try:
            self.config.mp = await MiningPool.init_async()
            StratumServer.config.mp = self.config.mp
        except Exception:
            from traceback import format_exc

            self.config.app_log.error(
                "Pool initialization failed: {}".format(format_exc())
            )

    def init_config_properties(self, test=False):
        self.config.app_log = logging.getLogger("tornado.application")
        self.config.health = Health()
        self.config.processing_queues = ProcessingQueues()
        self.config.mongo = Mongo()
        self.config.http_client = AsyncHTTPClient()
        self.config.BU = yadacoin.core.blockchainutils.BlockChainUtils()
        self.config.TU = yadacoin.core.transactionutils.TU
        yadacoin.core.blockchainutils.set_BU(self.config.BU)  # To be removed
        self.config.GU = GraphUtils()
        self.config.LatestBlock = LatestBlock
        if test:
            return
        tornado.ioloop.IOLoop.current().run_sync(self.config.LatestBlock.block_checker)
        self.init_consensus()
        self.config.cipher = Crypt(self.config.wif)
        if MODES.NODE.value in self.config.modes:
            # Enforce KEL-based key security: node will not start if seed or
            # SECOND_FACTOR are absent.  Auto-creates inception txn if needed.
            self.config.kel_manager = NodeKeyRotationManager(self.config)
            tornado.ioloop.IOLoop.current().run_sync(
                self.config.kel_manager.startup_check
            )
        # Resolve bootstrap node identities from their on-chain identity
        # announcements (e.g. centeridentity.com) before block generation, which
        # dereferences node.identity.public_key directly.
        from yadacoin.core.nodes import Nodes

        tornado.ioloop.IOLoop.current().run_sync(Nodes.resolve_bootstrap_identities)
        if MODES.NODE.value in self.config.modes:
            # self.config.pyrx = pyrx.PyRX()
            # self.config.pyrx.get_rx_hash(
            #     "header",
            #     binascii.unhexlify(
            #         "4181a493b397a733b083639334bc32b407915b9a82b7917ac361816f0a1f5d4d"
            #     ),
            #     4,
            # )
            self.config.nodeServer = NodeSocketServer
            self.config.nodeShared = NodeRPC()
            self.config.nodeClient = NodeSocketClient()

            for x in [Seed, SeedGateway, ServiceProvider, User, Miner, Pool]:
                if x.__name__ not in self.config.nodeClient.outbound_streams:
                    self.config.nodeClient.outbound_ignore[x.__name__] = {}
                if x.__name__ not in self.config.nodeClient.outbound_streams:
                    self.config.nodeClient.outbound_pending[x.__name__] = {}
                if x.__name__ not in self.config.nodeClient.outbound_streams:
                    self.config.nodeClient.outbound_streams[x.__name__] = {}
            for x in [Seed, SeedGateway, ServiceProvider, User, Miner, Pool]:
                if x.__name__ not in self.config.nodeServer.inbound_pending:
                    self.config.nodeServer.inbound_pending[x.__name__] = {}
                if x.__name__ not in self.config.nodeServer.inbound_streams:
                    self.config.nodeServer.inbound_streams[x.__name__] = {}

        tornado.ioloop.IOLoop.current().add_callback(self.init_peer)

        self.config.websocketServer = RCPWebSocketServer
        self.config.challenges = {}
        if MODES.WEB.value in self.config.modes:
            for x in [User, Group]:
                if x.__name__ not in self.config.websocketServer.inbound_streams:
                    self.config.websocketServer.inbound_streams[x.__name__] = {}

        if MODES.DNS.value in self.config.modes:
            from yadacoin.udp.base import UDPServer

            self.config.udpServer = UDPServer
            self.config.udpServer.inbound_streams = {User.__name__: {}}
            # server = tornado.ioloop.IOLoop.current().run_sync(lambda s=UDPServer, ip='127.0.0.1', port=53: tornado.ioloop.IOLoop.current().asyncio_loop.create_server(s, ip, port))
            # tornado.ioloop.IOLoop.current().run_sync(server.serve_forever)
            (
                self.config.udp_transport,
                _protocol,
            ) = tornado.ioloop.IOLoop.current().run_sync(
                lambda s=UDPServer, local_addr=(
                    "0.0.0.0",
                    53,
                ): tornado.ioloop.IOLoop.current().asyncio_loop.create_datagram_endpoint(
                    s, local_addr=local_addr
                )
            )

    async def _listen_udp(self):
        from yadacoin.udp.base import UDPServer

        (
            self.config.udp_transport,
            _protocol,
        ) = await tornado.ioloop.IOLoop.current().asyncio_loop.create_datagram_endpoint(
            UDPServer, local_addr=("0.0.0.0", 53)
        )

    def _close_http_server(self, server):
        if server is None:
            return
        sockets = list(getattr(server, "_sockets", {}).values())
        try:
            if not getattr(server, "_stopped", False):
                server.stop()
        except Exception:
            self.config.app_log.warning("http server stop failed\n%s", format_exc())
        for sock in sockets:
            try:
                sock.close()
            except Exception:
                pass

    def _rebind_http(self):
        self._close_http_server(getattr(self.config, "http_server", None))
        self.config.http_server = None
        self._close_http_server(getattr(self.config, "https_server", None))
        self.config.https_server = None
        if MODES.WEB.value not in (self.config.modes or []):
            return
        if hasattr(self, "wildcard_router"):
            self.reload_http_routes()
        self.config.http_server = HTTPServer(self)
        self.config.http_server.listen(self.config.serve_port, self.config.serve_host)
        if (
            MODES.SSL.value in self.config.modes
            and hasattr(self.config, "ssl")
            and self.config.ssl.is_valid()
        ):
            ssl_ctx = ssl.create_default_context(
                ssl.Purpose.CLIENT_AUTH, cafile=self.config.ssl.ca_file
            )
            ssl_ctx.load_cert_chain(
                self.config.ssl.cert_file, keyfile=self.config.ssl.key_file
            )
            self.config.https_server = HTTPServer(self, ssl_options=ssl_ctx)
            self.config.https_server.listen(self.config.ssl.port)

    async def apply_saved_config(self, previous_http=None):
        """Pause services so saved config values are the ones that come back up."""
        self.enter_maintenance()
        try:
            modes = list(self.config.modes or [])
            self.config.configured_modes = modes
            if MODES.POOL.value not in modes:
                self.config.pool_server = None
                self._pool_started = False
            if MODES.NODE.value in modes and not getattr(
                self, "_node_services_started", False
            ):
                self.init_seeds()
                self.init_seed_gateways()
                self.init_service_providers()
                self.init_groups()
                self._init_node_peers()
                self._node_services_started = True
            if getattr(self.config, "kel_manager", None) is not None:
                self.config.username_signature = (
                    NodeKeyRotationManager.generate_deterministic_signature(
                        self.config.username
                    )
                )
            await self.leave_maintenance()
            if MODES.NODE.value in modes and not getattr(
                self, "_node_periodics_started", False
            ):
                self._start_node_periodics()
            if MODES.POOL.value in modes and not getattr(self, "_pool_started", False):
                self.init_pool()
                self._pool_started = True
            tornado.ioloop.IOLoop.current().add_callback(self._rebind_http)
        except Exception:
            self.config.maintenance = False
            if getattr(self.config, "mongo", None) is not None:
                try:
                    self.config.mongo.reconnect()
                except Exception:
                    pass
            raise

    async def rebind_after_setup(self):
        """Pause services, re-derive seed keys, then resume without a restart."""
        try:
            from plugins.operator.setup import apply_setup_gate
        except ImportError:
            apply_setup_gate = None

        self.enter_maintenance()
        try:
            if getattr(self.config, "mongo", None) is not None:
                self.config.mongo.reconnect()
            if apply_setup_gate is not None:
                apply_setup_gate(self.config)
            self.config.cipher = Crypt(self.config.wif)
            self.init_jwt()
            if MODES.NODE.value in self.config.modes:
                self.config.kel_manager = NodeKeyRotationManager(self.config)
                await self.config.kel_manager.startup_check()
                if not getattr(self.config, "kel_ready", False):
                    await self.leave_maintenance()
                    return
                self.config.username_signature = (
                    NodeKeyRotationManager.generate_deterministic_signature(
                        self.config.username
                    )
                )
                if not getattr(self, "_node_services_started", False):
                    self.init_seeds()
                    self.init_seed_gateways()
                    self.init_service_providers()
                    self.init_groups()
                    self._init_node_peers()
                    self._node_services_started = True
            await self.leave_maintenance()
            if MODES.NODE.value in self.config.modes and not getattr(
                self, "_node_periodics_started", False
            ):
                self._start_node_periodics()
            if MODES.POOL.value in self.config.modes and not getattr(
                self, "_pool_started", False
            ):
                self.init_pool()
                self._pool_started = True
        except Exception:
            self.config.maintenance = False
            if getattr(self.config, "mongo", None) is not None:
                try:
                    self.config.mongo.reconnect()
                except Exception:
                    pass
            raise

    def enter_maintenance(self):
        if getattr(self.config, "maintenance", False):
            return
        self.config.maintenance = True
        loop = tornado.ioloop.IOLoop.current()
        if self._node_test_call is not None:
            loop.remove_timeout(self._node_test_call)
            self._node_test_call = None
        for periodic in getattr(self, "_periodics", []):
            periodic.stop()
        server = getattr(self.config, "node_server_instance", None)
        if server is not None:
            server.stop()
        self._clear_node_peers()
        pool = getattr(self.config, "pool_server", None)
        if pool is not None:
            pool.stop()
        transport = getattr(self.config, "udp_transport", None)
        if transport is not None:
            transport.close()
            self.config.udp_transport = None
        if getattr(self.config, "mongo", None) is not None:
            self.config.mongo.suspend()
        self.config.app_log.info("maintenance on")

    async def refresh_chain_state(self):
        config = self.config
        if getattr(config, "BU", None) is not None:
            config.BU.invalidate_latest_block()
        queues = getattr(config, "processing_queues", None)
        if queues is not None:
            for queue in queues.queues:
                if hasattr(queue, "queue"):
                    queue.queue = {}
        if getattr(config, "LatestBlock", None) is not None:
            config.LatestBlock.block = None
            await config.LatestBlock.block_checker()
        config.consensus = await Consensus.init_async(prevent_genesis=True)
        if (
            getattr(config, "pool_server", None) is not None
            or getattr(config, "mp", None) is not None
        ):
            try:
                config.mp = await MiningPool.init_async()
                StratumServer.config.mp = config.mp
            except Exception:
                from traceback import format_exc

                config.mp = None
                StratumServer.config.mp = None
                config.app_log.warning(
                    "Pool rebuild after restore failed: {}".format(format_exc())
                )
        block = getattr(config.LatestBlock, "block", None)
        height = block.index if block is not None else None
        config.app_log.info("chain state refreshed height={}".format(height))

    async def leave_maintenance(self):
        if not getattr(self.config, "maintenance", False):
            return
        self.config.mongo.reconnect()
        await self.refresh_chain_state()
        if (
            MODES.NODE.value in self.config.modes
            and getattr(self.config, "kel_ready", False)
            and getattr(self.config, "nodeServer", None)
        ):
            self._init_node_peers()
            self.config.node_server_instance = self.config.nodeServer()
            self.config.node_server_instance.bind(self.config.peer_port)
            self.config.node_server_instance.start(1)
        if getattr(self.config, "pool_server", None) is not None:
            self.config.pool_server = StratumServer(
                ssl_options=getattr(self, "_pool_ssl_ctx", None)
            )
            StratumServer.config = self.config
            self.config.pool_server.listen(self.config.stratum_pool_port)
        if MODES.DNS.value in self.config.modes:
            tornado.ioloop.IOLoop.current().add_callback(self._listen_udp)
        for periodic in getattr(self, "_periodics", []):
            periodic.start()
        if getattr(self.config, "consensus", None) is not None:
            self.config.consensus.syncing = False
        peers = getattr(self.config, "background_peers", None)
        if peers is not None:
            peers.busy = False
        self.config.maintenance = False
        if (
            getattr(self.config, "peer", None) is not None
            and getattr(self.config, "nodeClient", None) is not None
        ):
            tornado.ioloop.IOLoop.current().add_callback(
                self.config.peer.ensure_peers_connected
            )
        self.config.app_log.info("maintenance off")

    def _close_stream_map(self, mapping):
        if not isinstance(mapping, dict):
            return
        for bucket in list(mapping.values()):
            if not isinstance(bucket, dict):
                continue
            for stream in list(bucket.values()):
                close = getattr(stream, "close", None)
                if close is None:
                    continue
                try:
                    close()
                except Exception:
                    pass
            bucket.clear()

    def _clear_node_peers(self):
        server = getattr(self.config, "nodeServer", None)
        client = getattr(self.config, "nodeClient", None)
        if server is not None:
            self._close_stream_map(getattr(server, "inbound_streams", None))
            self._close_stream_map(getattr(server, "inbound_pending", None))
            server.inbound_streams = {}
            server.inbound_pending = {}
            server.retry_messages = {}
        if client is not None:
            self._close_stream_map(getattr(client, "outbound_streams", None))
            self._close_stream_map(getattr(client, "outbound_pending", None))
            client.outbound_streams = {}
            client.outbound_pending = {}
            client.outbound_ignore = {}
            client.retry_messages = {}
        self.config.nodeClient = None

    def _init_node_peers(self):
        self.config.nodeServer = NodeSocketServer
        self.config.nodeShared = NodeRPC()
        self.config.nodeClient = NodeSocketClient()
        for peer_type in [Seed, SeedGateway, ServiceProvider, User, Miner, Pool]:
            name = peer_type.__name__
            self.config.nodeClient.outbound_ignore[name] = {}
            self.config.nodeClient.outbound_pending[name] = {}
            self.config.nodeClient.outbound_streams[name] = {}
            self.config.nodeServer.inbound_pending[name] = {}
            self.config.nodeServer.inbound_streams[name] = {}

    async def init_peer(self):
        pass

        self.config.peer = await Peer.my_peer()


if __name__ == "__main__":
    NodeApplication()
