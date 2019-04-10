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
        self.app_log.debug('client /Chat connected to {}'.format(ip_port))
        #print(self.client.connection_url)
        await self.emit('hello', data={"version": 2, "ip": self.config.peer_host, "port": self.config.peer_port}, namespace="/chat")
        # ask the peer active list
        await self.emit('get_peers', data={}, namespace="/chat")

    def on_disconnect(self):
        _, ip_port = self.client.connection_url.split('//')  # extract ip:port
        self.app_log.debug('client /Chat disconnected from {}')
        pass

    async def on_peers(self, data):
        _, ip_port = self.client.connection_url.split('//')  # extract ip:port
        self.app_log.debug("client got peers from {}: {}".format(ip_port, data))
        ip, port = ip_port.split(':')
        self.config.peers.on_new_outbound(ip, port, self.client)


class YadaWebSocketClient(object):

    WAIT_FOR_PEERS = 30

    def __init__(self, peer):
        self.client = AsyncClient()
        self.peer = peer
        self.config = get_config()
        self.app_log = getLogger("tornado.application")

    async def start(self):
        try:
            self.client.register_namespace(ClientChatNamespace('/chat'))
            await self.client.connect("http://{}:{}".format(self.peer.host, self.peer.port))
            await async_sleep(self.WAIT_FOR_PEERS)  # wait for an answer
            if self.peer.host not in self.config.peers.outbound:
                # if we are not in the outgoing, we did not receive a peers answer, old peer (but ok)
                self.app_log.warning("{} was not connected after {} sec, probable old node"
                                     .format(self.peer.to_string(), self.WAIT_FOR_PEERS))
                return
            while True:
                self.app_log.debug("{} loop".format(self.peer.to_string()))
                await async_sleep(30)
        except Exception as e:
            self.app_log.warning("Exception {} connecting to {}".format(e, self.peer.to_string()))
        finally:
            pass