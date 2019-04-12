"""
Client side of the websocket /chat
"""

from asyncio import sleep as async_sleep
from logging import getLogger

from socketio import AsyncClient, AsyncClientNamespace

from yadacoin.config import get_config


class ClientChatNamespace(AsyncClientNamespace):

    async def on_connect(self):
        self.config = get_config()
        self.app_log = getLogger("tornado.application")
        _, ip_port = self.client.connection_url.split('//')  # extract ip:port
        """
        ip, port = ip_port.split(':')
        if ip in self.config.peers.connected_ips:
            self.app_log.debug('client {} already in connect list'.format(ip_port))
            return False            
        """
        self.app_log.debug('client /Chat connected to {} - {}'.format(ip_port, self.client))
        await self.emit('hello', data={"version": 2, "ip": self.config.peer_host, "port": self.config.peer_port}, namespace="/chat")
        # Get the peers current block as sync starting point
        await self.emit('get_latest_block', data={}, namespace="/chat")


    def on_disconnect(self):
        """Disconnect from our side or the server's one."""
        _, ip_port = self.client.connection_url.split('//')  # extract ip:port
        self.app_log.debug('client /Chat disconnected from {}'.format(ip_port))
        pass

    async def on_latest_block(self, data):
        """Peer sent us its latest block, store it and consider it a valid peer."""
        from yadacoin.block import Block  # TODO: Circular reference. Not good!
        _, ip_port = self.client.connection_url.split('//')  # extract ip:port
        self.app_log.debug("client got latest block {} from {}: {}".format(data['index'], ip_port, data))
        ip, port = ip_port.split(':')
        self.config.peers.on_new_outbound(ip, port, self.client)
        self.client.manager.latest_block = Block.from_dict(data)
        # ask the peer active list
        await self.emit('get_peers', data={}, namespace="/chat")

    async def on_peers(self, data):
        _, ip_port = self.client.connection_url.split('//')  # extract ip:port
        self.app_log.debug("client got peers from {}: {}".format(ip_port, data))
        await self.config.peers.on_new_peer_list(data['peers'])


class YadaWebSocketClient(object):

    WAIT_FOR_PEERS = 20

    def __init__(self, peer):
        self.client = AsyncClient(reconnection=False, logger=False)
        self.peer = peer
        self.config = get_config()
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