"""
Crude websocket client for tests
"""


#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import tornado

from tornado.options import define, options
from asyncio import sleep as async_sleep
from logging import getLogger

from socketio import AsyncClient, AsyncClientNamespace

__version__ = '0.0.1'


DEFAULT_PORT = 8000


class ClientChatNamespace(AsyncClientNamespace):

    async def on_connect(self):
        self.app_log = getLogger("tornado.application")
        print("CONNECT WS")
        # self.config = get_config()
        # self.mongo = self.config.mongo
        _, ip_port = self.client.connection_url.split('//')  # extract ip:port
        self.ip, self.port = ip_port.split(':')
        self.app_log.info('ws client /Chat connected to {}:{} - {}'.format(self.ip, self.port, self.client))
        self.client.manager.connected = True
        await self.emit('hello', data={"version": 2, "ip": options.sourceip, "port": 8000}, namespace="/chat")
        # ask the peer active list
        await self.emit('get_peers', data={}, namespace="/chat")

    async def on_disconnect(self):
        """Disconnected from our side or the server's one."""
        #
        self.client.manager.connected = False
        try:
            self.app_log.info('ws client /Chat disconnected from {}:{}'.format(self.ip, self.port))
        except:
            # self.app_log sometimes seem not to be init?
            print('ws client /Chat disconnected from {}:{}'.format(self.ip, self.port))

    async def on_latest_block(self, data):
        """Peer sent us its latest block, store it and consider it a valid peer."""
        self.app_log.info("ws client got latest block {} from {}:{} {}".format(data['index'], self.ip, self.port, data))
        await self.client.manager.on_latest_block(data)

    async def on_peers(self, data):
        self.app_log.info("ws client got peers from {}:{} {}".format(self.ip, self.port, data))
        # self.config.peers.on_new_outbound(self.ip, self.port, self.client)
        try:
            #await self.config.peers.on_new_peer_list(data['peers'])
            pass
        except Exception as e:
            print(data)
            self.app_log.warning('ws on_peers error {}'.format(e))
        # Get the peers current block as sync starting point
        await self.emit('get_latest_block', data={}, namespace="/chat")

    async def on_blocks(self, data):
        """Peer sent us its latest block, store it and consider it a valid peer."""
        self.app_log.info("ws client got {} blocks from {}:{}".format(len(data), self.ip, self.port))

    async def on_get_latest_block(self, data):
        """Peer sent us its latest block, store it and consider it a valid peer."""
        self.app_log.error("ws client got {} on_get_latest_block from {}:{}, IGNORED".format(data, self.ip, self.port))

    async def on_get_blocks(self, data):
        """server ask for list of blocks"""
        try:
            # TODO: dup code between http route and websocket handlers. AND... ws client + server!!!
            self.app_log.info('WSclient get-blocks: {}'.format(json.dumps(data)))

        except Exception as e:
            import sys, os
            self.app_log.warning("Exception {} on_get_blocks".format(e))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)


class YadaWebSocketClient(object):

    WAIT_FOR_PEERS = 20

    def __init__(self, peer):
        self.client = AsyncClient(reconnection=False, logger=False)
        self.peer = peer
        self.app_log = getLogger("tornado.application")

        self.latest_peer_block = None
        self.connected = False
        self.probable_old = False

    async def start(self):
        try:
            self.client.manager = self
            self.client.register_namespace(ClientChatNamespace('/chat'))
            await self.client.connect("http://{}:{}".format(self.peer['host'], self.peer['port']), namespaces=['/chat'])
            # self.connected = True
            await async_sleep(self.WAIT_FOR_PEERS)  # wait for an answer
            if not self.connected:
                self.app_log.warning("{} was not connected after {} sec, incrementing fails"
                                     .format(self.peer.to_string(), self.WAIT_FOR_PEERS))
                # await self.peers.increment_failed(self.peer)
                self.probable_old = True
                return

            while self.connected:
                self.app_log.debug("{} loop, state:{}".format(self.peer.to_string(), self.client.eio.state))
                await async_sleep(30)
                # TODO: poll here after some time without activity?
        except Exception as e:
            self.app_log.warning("Exception {} connecting to {}".format(e, self.peer.to_string()))
        finally:
            pass


if __name__ == "__main__":

    define("ip", default='127.0.0.1', help="Server IP to connect to, default 127.0.0.1")
    define("sourceip", default='127.0.0.1', help="our outside interface ip")
    define("verbose", default=False, help="verbose")
    options.parse_command_line()

    if options.ip != '127.0.0.1':
        URL = "ws://{}:{}/chat/".format(options.ip, DEFAULT_PORT)
        print("Using {}".format(URL))

    peer= {'host': options.ip, 'port': DEFAULT_PORT}
    client = YadaWebSocketClient(peer)

    tornado.ioloop.IOLoop.current().run_sync(client.start)