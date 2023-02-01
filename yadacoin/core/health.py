import time
import tornado.ioloop
from yadacoin.core.config import get_config

class HealthItem:
    last_activity = time.time()
    timeout = 120
    status = True
    ignore = False

    def __init__(self):
        self.config = get_config()

    def report_bad_health(self, message):
        self.config.app_log.error(message)

    def report_status(self, status, ignore=False):
        self.ignore = ignore
        self.status = status
        return status

    def to_dict(self):
        return {
            'last_activity  ': int(self.last_activity),
            'status         ': self.status,
            'time_until_fail': self.timeout - (int(time.time()) - int(self.last_activity)),
            'ignore         ': self.ignore
        }
    async def reset(self):
        pass


class TCPServerHealth(HealthItem):

    async def check_health(self):
        streams = await self.config.peer.get_all_inbound_streams() + await self.config.peer.get_all_miner_streams()
        if not streams:
            return self.report_status(True, ignore=True)

        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health('TCP Server health check failed')
            return self.report_status(False)

        status = True
        for stream in streams:
            if time.time() - stream.last_activity > self.timeout:
                await self.config.node_server_instance.remove_peer(stream)
                self.report_bad_health('Stale stream detected in TCPServer, peer removed')
                status = False

        return self.report_status(status)

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

            self.report_bad_health('TCP Client health check failed')
            streams = await self.config.peer.get_all_outbound_streams()
            for stream in streams:
                if time.time() - stream.last_activity > self.timeout:
                    await self.config.nodeClient.remove_peer(stream)

            return self.report_status(False)

        return self.report_status(True)

    async def reset(self):
        streams = await self.config.peer.get_all_outbound_streams()
        self.config.app_log.info(streams)
        for stream in streams:
            await self.config.nodeClient.remove_peer(stream)


class ConsenusHealth(HealthItem):

    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health('Consensus health check failed')
            return self.report_status(False)

        return self.report_status(True)


    async def reset(self):
        # if the block queue has items that will not move out, consensus will halt
        self.config.consensus.block_queue.queue = {}


class PeerHealth(HealthItem):

    async def check_health(self):

        if time.time() - self.last_activity > self.timeout:
            tornado.ioloop.IOLoop.current().spawn_callback(self.config.application.background_peers)
            self.report_bad_health('Background peer health check failed, restarting...')
            return self.report_status(False)

        return self.report_status(True)


class BlockCheckerHealth(HealthItem):

    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health('Background block checker health check failed')
            return self.report_status(False)

        return self.report_status(True)


class MessageSenderHealth(HealthItem):

    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            tornado.ioloop.IOLoop.current().spawn_callback(self.config.application.background_message_sender)
            self.report_bad_health('Background message sender health check failed, restarting...')
            return self.report_status(False)

        return self.report_status(True)


class BlockInserterHealth(HealthItem):

    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health('Background block inserter health check failed')
            return self.report_status(False)

        return self.report_status(True)


class TransactionProcessorHealth(HealthItem):

    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health('Background transaction processor health check failed')
            return self.report_status(False)

        return self.report_status(True)


class NonceProcessorHealth(HealthItem):

    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health('Background nonce processor health check failed')
            return self.report_status(False)

        return self.report_status(True)


class PoolPayerHealth(HealthItem):

    async def check_health(self):
        if not self.config.pp:
            return self.report_status(True, ignore=True)

        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health('Background pool payer health check failed')
            return self.report_status(False)

        return self.report_status(True)


class CacheValidatorHealth(HealthItem):

    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health('Background cache validator health check failed')
            return self.report_status(False)

        return self.report_status(True)


class MempoolCleanerHealth(HealthItem):
    timeout = 3600
    async def check_health(self):
        if time.time() - self.last_activity > self.timeout:
            self.report_bad_health('Background mempool cleaner health check failed')
            return self.report_status(False)

        return self.report_status(True)


class Health:
    def __init__(self):
        self.config = get_config()
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
            self.mempool_cleaner
        ]
        if 'pool' in self.config.modes:
            self.nonce_processor = NonceProcessorHealth()
            self.health_items.append(self.nonce_processor)

    async def check_health(self):
        for x in self.health_items:
            if not await x.check_health() and not x.ignore:
                await x.reset()
                self.status = False
                return False
        self.status = True
        return True

    def to_dict(self):
        out = {x.__class__.__name__: x.to_dict() for x in self.health_items if not x.ignore}
        out['status'] = self.status
        return out
