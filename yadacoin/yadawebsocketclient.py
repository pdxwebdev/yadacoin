"""
Client side of the websocket /chat
"""

from socketio import AsyncClient, AsyncClientNamespace
from yadacoin.config import get_config
from asyncio import sleep as async_sleep


class ClientChatNamespace(AsyncClientNamespace):

    async def on_connect(self):
        self.config = get_config()
        print('client /Chat connected')
        print(self.client.connection_url)
        await self.emit('hello', data={"version": 2, "ip": self.config.peer_host, "port": self.config.peer_port}, namespace="/chat")
        # ask the peer active list
        await self.emit('get_peers', data={}, namespace="/chat")

    def on_disconnect(self):
        print('client /Chat disconnected')
        pass

    async def on_peers(self, data):
        print("client peers", data)


class YadaWebSocketClient(object):

    def __init__(self, peer):
        self.client = AsyncClient()
        self.peer = peer
        self.config = get_config()

    async def start(self):
        try:
            self.client.register_namespace(ClientChatNamespace('/chat'))
            await self.client.connect("http://{}:{}".format(self.peer.host, self.peer.port))
            # reserve IP since we should be ok
            self.config.peers.on_new_ip(self.peer.host)
            await async_sleep(20)  # wait for an answer
            # if we are not in the outgoing, we did not receive a peers answer, old peer (but ok)
            # remove ip
            # else register outgoing
            while True:
                await async_sleep(10)
        except Exception as e:
            print(e)