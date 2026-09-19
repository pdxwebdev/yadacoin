"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import time

import tornado.ioloop

from yadacoin.core.config import Config
from yadacoin.enums.modes import MODES


class HealthItem:
    last_activity = time.time()
    timeout = 120
    status = True
    ignore = False

    def __init__(self):
        self.config = Config()

    def report_bad_health(self, message):
        self.config.app_log.error(message)

    def report_status(self, status, ignore=False):
        self.ignore = ignore
        self.status = status
        return status

    def to_dict(self):
        return {
            "last_activity  ": int(self.last_activity),
            "status         ": self.status,
            "time_until_fail": self.timeout
            - (int(time.time()) - int(self.last_activity)),
            "ignore         ": self.ignore,
        }

    async def reset(self):
        pass


class TCPServerHealth(HealthItem):
    async def check_health(self):
        streams = (
            await self.config.peer.get_all_inbound_streams()
            + await self.config.peer.get_all_miner_streams()
        )
        if not streams:
            return self.report_status(True, ignore=True)

        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health("TCP Server health check failed")
            return self.report_status(False)

        for stream in streams:
            if time.time() - stream.last_activity > 720:
                await self.config.node_server_instance.remove_peer(
                    stream, reason="Stale stream detected in TCPServer, peer removed"
                )
                self.report_bad_health(
                    "Stale stream detected in TCPServer, peer removed"
                )

        return self.report_status(True)

    async def reset(self):
        self.config.node_server_instance.stop()
        self.config.node_server_instance = self.config.nodeServer()
        self.config.node_server_instance.bind(self.config.peer_port)
        self.config.node_server_instance.start(1)
        return self.report_status(True)


class TCPClientHealth(HealthItem):
    async def check_health(self):
        streams = await self.config.peer.get_all_outbound_streams()
        if not streams:
            return self.report_status(True, ignore=True)

        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health("TCP Client health check failed")
            streams = await self.config.peer.get_all_outbound_streams()
            for stream in streams:
                if time.time() - stream.last_activity > self.timeout:
                    await self.config.nodeClient.remove_peer(
                        stream, reason="TCPClientHealth: Stream timeout"
                    )

            return self.report_status(False)

        return self.report_status(True)

    async def reset(self):
        streams = await self.config.peer.get_all_outbound_streams()
        self.config.app_log.info(streams)
        for stream in streams:
            await self.config.nodeClient.remove_peer(
                stream, reason="TCPClientHealth: reset"
            )


class ConsenusHealth(HealthItem):
    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health("Consensus health check failed")
            return self.report_status(False)

        return self.report_status(True)

    async def reset(self):
        # if the block queue has items that will not move out, consensus will halt
        self.config.processing_queues.block_queue.queue = {}


class PeerHealth(HealthItem):
    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            tornado.ioloop.IOLoop.current().spawn_callback(
                self.config.application.background_peers
            )
            self.report_bad_health("Background peer health check failed, restarting...")
            return self.report_status(False)

        return self.report_status(True)


class BlockCheckerHealth(HealthItem):
    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health("Background block checker health check failed")
            return self.report_status(False)

        return self.report_status(True)


class MessageSenderHealth(HealthItem):
    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            tornado.ioloop.IOLoop.current().spawn_callback(
                self.config.application.background_message_sender
            )
            self.report_bad_health(
                "Background message sender health check failed, restarting..."
            )
            return self.report_status(False)

        return self.report_status(True)


class BlockInserterHealth(HealthItem):
    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health("Background block inserter health check failed")
            return self.report_status(False)

        return self.report_status(True)


class TransactionProcessorHealth(HealthItem):
    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health(
                "Background transaction processor health check failed"
            )
            return self.report_status(False)

        return self.report_status(True)


class NonceProcessorHealth(HealthItem):
    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health("Background nonce processor health check failed")
            return self.report_status(False)

        return self.report_status(True)


class PoolPayerHealth(HealthItem):
    async def check_health(self):
        if not self.config.pp:
            return self.report_status(True, ignore=True)

        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health("Background pool payer health check failed")
            return self.report_status(False)

        return self.report_status(True)


class CacheValidatorHealth(HealthItem):
    timeout = 3600

    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health("Background cache validator health check failed")
            return self.report_status(False)

        return self.report_status(True)


class MempoolCleanerHealth(HealthItem):
    timeout = 3600

    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health("Background mempool cleaner health check failed")
            return self.report_status(False)

        return self.report_status(True)


class NodeTesterHealth(HealthItem):
    timeout = 60 * 60 * 2  # 2 hours (runs every 1 hour)

    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health("Background node tester health check failed")
            return self.report_status(False)

        return self.report_status(True)


class PeerBranchHealth(HealthItem):
    """Watch peer-branch key_event_log growth (spam / bug detector).

    Does not fail the whole node health bit on soft warnings; hard oversize
    or rate-limit blocks are logged via kel_manager and reflected in to_dict.
    """

    timeout = 600  # expect a check at least every 10 minutes
    last_snapshot = None

    async def check_health(self):
        self.last_activity = time.time()
        mgr = getattr(self.config, "kel_manager", None)
        if mgr is None or not hasattr(mgr, "peer_branch_monitor_snapshot"):
            return self.report_status(True, ignore=True)
        try:
            snap = await mgr.peer_branch_monitor_snapshot()
        except Exception as exc:
            self.report_bad_health(f"PeerBranchHealth snapshot failed: {exc}")
            return self.report_status(False)
        self.last_snapshot = snap
        limits = snap.get("limits") or {}
        max_total = int(limits.get("max_total_docs") or 20000)
        total = int(snap.get("total_peer_branch_docs") or 0)
        oversize = snap.get("oversize_peers") or []
        blocked = int(snap.get("advances_blocked") or 0)
        if oversize:
            self.report_bad_health(
                "PeerBranchHealth: oversize peer branches: "
                + ", ".join(
                    f"{p.get('peer') or p.get('branch')} docs={p.get('docs')}"
                    for p in oversize[:5]
                )
            )
        if total > max_total:
            self.report_bad_health(
                f"PeerBranchHealth: total peer-branch docs {total} > {max_total}"
            )
            return self.report_status(False)
        if blocked and blocked > 0:
            # Rate-limit fired — warn but do not mark node dead.
            self.config.app_log.warning(
                "PeerBranchHealth: advances_blocked=%s (rate/size guard active)",
                blocked,
            )
        return self.report_status(True)

    def to_dict(self):
        out = super().to_dict()
        if self.last_snapshot:
            out["snapshot"] = self.last_snapshot
        return out


class Health:
    def __init__(self):
        self.config = Config()
        self.status = True
        self.tcp_server = TCPServerHealth()
        self.tcp_client = TCPClientHealth()
        self.consensus = ConsenusHealth()
        self.peer = PeerHealth()
        self.block_checker = BlockCheckerHealth()
        self.message_sender = MessageSenderHealth()
        self.block_inserter = BlockInserterHealth()
        self.transaction_processor = TransactionProcessorHealth()
        self.pool_payer = PoolPayerHealth()
        self.cache_validator = CacheValidatorHealth()
        self.mempool_cleaner = MempoolCleanerHealth()
        self.node_tester = NodeTesterHealth()
        self.peer_branch = PeerBranchHealth()
        self.health_items = [
            self.consensus,
            self.tcp_server,
            self.tcp_client,
            self.peer,
            self.block_checker,
            self.message_sender,
            self.block_inserter,
            self.transaction_processor,
            self.pool_payer,
            self.cache_validator,
            self.mempool_cleaner,
            self.node_tester,
            self.peer_branch,
        ]
        if MODES.POOL.value in self.config.modes:
            self.nonce_processor = NonceProcessorHealth()
            self.health_items.append(self.nonce_processor)

    async def check_health(self):
        status = True
        for x in self.health_items:
            if not await x.check_health() and not x.ignore:
                await x.reset()
                status = False
        self.status = status
        return self.status

    def to_dict(self):
        out = {x.__class__.__name__: x.to_dict() for x in self.health_items}
        out["status"] = self.status
        return out
