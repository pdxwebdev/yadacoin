"""
Client side of the websocket /chat
"""

from asyncio import sleep as async_sleep
from logging import getLogger

from socketio import AsyncClient, AsyncClientNamespace

from yadacoin.config import get_config
from yadacoin.chain import CHAIN


class ClientChatNamespace(AsyncClientNamespace):

    async def on_connect(self):
        self.config = get_config()
        self.app_log = getLogger("tornado.application")
        _, ip_port = self.client.connection_url.split('//')  # extract ip:port
        self.ip, self.port = ip_port.split(':')
        self.app_log.debug('ws client /Chat connected to {}:{} - {}'.format(self.ip, self.port, self.client))
        await self.emit('hello', data={"version": 2, "ip": self.config.peer_host, "port": self.config.peer_port}, namespace="/chat")
        # ask the peer active list
        await self.emit('get_peers', data={}, namespace="/chat")

    def on_disconnect(self):
        """Disconnect from our side or the server's one."""
        self.app_log.debug('ws client /Chat disconnected from {}:{}'.format(self.ip, self.port))
        pass

    async def on_latest_block(self, data):
        """Peer sent us its latest block, store it and consider it a valid peer."""
        self.app_log.debug("ws client got latest block {} from {}:{} {}".format(data['index'], self.ip, self.port, data))
        await self.config.peers.on_latest_block_outgoing(data, self.ip, self.port)
        await self.client.manager.on_latest_block(data)

    async def on_peers(self, data):
        self.app_log.debug("ws client got peers from {}:{} {}".format(self.ip, self.port, data))
        self.config.peers.on_new_outbound(self.ip, self.port, self.client)
        await self.config.peers.on_new_peer_list(data['peers'])
        # Get the peers current block as sync starting point
        await self.emit('get_latest_block', data={}, namespace="/chat")

    async def on_blocks(self, data):
        """Peer sent us its latest block, store it and consider it a valid peer."""
        self.app_log.debug("ws client got {} blocks from {}:{} {}".format(len(data), self.ip, self.port, data))
        if self.config.peers.syncing:
            self.app_log.debug("Ignoring, already syncing")
            return
        # TODO: if index match and enough blocks, Set syncing and do it


class YadaWebSocketClient(object):

    WAIT_FOR_PEERS = 20

    def __init__(self, peer):
        self.client = AsyncClient(reconnection=False, logger=False)
        self.peer = peer
        self.config = get_config()
        self.peers = self.config.peers
        self.app_log = getLogger("tornado.application")

        self.latest_block = None

    async def start(self):
        try:
            self.client.manager = self
            self.client.register_namespace(ClientChatNamespace('/chat'))
            await self.client.connect("http://{}:{}".format(self.peer.host, self.peer.port))
            await async_sleep(self.WAIT_FOR_PEERS)  # wait for an answer
            if self.peer.host not in self.config.peers.outbound:
                # if we are not in the outgoing, we did not receive a peers answer, old peer (but ok)
                self.app_log.warning("{} was not connected after {} sec, probable old node"
                                     .format(self.peer.to_string(), self.WAIT_FOR_PEERS))
                await self.client.disconnect()
                return
            while True:
                self.app_log.debug("{} loop".format(self.peer.to_string(), self.client.eio.state))
                await async_sleep(30)
        except Exception as e:
            self.app_log.warning("Exception {} connecting to {}".format(e, self.peer.to_string()))
        finally:
            pass

    async def on_latest_block(self, data):
        from yadacoin.block import Block  # Circular reference. Not good! - Do we need the object here?
        self.latest_block = Block.from_dict(data)
        if not self.peers.syncing:
            self.app_log.debug("Trying to sync on latest block from {}".format(self.peer.to_string()))
            my_index = self.config.BU.get_latest_block()['index']
            if data['index'] == my_index + 1:
                self.app_log.debug("TODO: next index, should try to merge from {}".format(self.peer.to_string()))
            elif data['index'] > my_index + 1:
                self.app_log.debug("TODO: missing blocks between {} and {} , asking more to {}".format(my_index, data['index'], self.peer.to_string()))
                data = {"start_index": my_index + 1, "end_index": my_index + 1 + CHAIN.MAX_BLOCKS_PER_MESSAGE}
                await self.client.emit('get_blocks', data=data, namespace="/chat")
