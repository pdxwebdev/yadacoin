"""
Client side of the websocket /chat
"""

import json
from asyncio import sleep as async_sleep
from logging import getLogger

from socketio import AsyncClient, AsyncClientNamespace

from yadacoin.config import get_config
from yadacoin.chain import CHAIN
from yadacoin.common import ts_to_utc


class ClientChatNamespace(AsyncClientNamespace):

    async def on_connect(self):
        self.app_log = getLogger("tornado.application")
        print("CONNECT WS")
        self.config = get_config()
        self.mongo = self.config.mongo
        _, ip_port = self.client.connection_url.split('//')  # extract ip:port
        self.ip, self.port = ip_port.split(':')
        self.app_log.debug('ws client /Chat connected to {}:{} - {}'.format(self.ip, self.port, self.client))
        self.client.manager.connected = True
        await self.emit('hello', data={"version": 2, "ip": self.config.public_ip, "port": self.config.peer_port}, namespace="/chat")
        # ask the peer active list
        await self.emit('get_peers', data={}, namespace="/chat")

    async def on_disconnect(self):
        """Disconnected from our side or the server's one."""
        #
        self.client.manager.connected = False
        if not hasattr(self, 'ip'): # never connected, but this event fires for some reason
            _, ip_port = self.client.connection_url.split('//')  # extract ip:port
            self.ip, self.port = ip_port.split(':')
        
        try:
            self.app_log.debug('ws client /Chat disconnected from {}:{}'.format(self.ip, self.port))
        except:
            print('ws client /Chat disconnected from {}:{}'.format(self.ip, self.port))

    async def on_latest_block(self, data):
        """Peer sent us its latest block, store it and consider it a valid peer."""
        self.app_log.debug("ws client got latest block {} from {}:{} {}".format(data['index'], self.ip, self.port, data))
        await self.client.manager.on_latest_block(data)

    async def on_peers(self, data):
        self.app_log.debug("ws client got peers from {}:{} {}".format(self.ip, self.port, data))
        self.config.peers.on_new_outbound(self.ip, self.port, self.client)
        try:
            await self.config.peers.on_new_peer_list(data['peers'])
        except Exception as e:
            print(data)
            self.app_log.warning('ws on_peers error {}'.format(e))
        # Get the peers current block as sync starting point
        await self.emit('get_latest_block', data={}, namespace="/chat")

    async def on_blocks(self, data):
        """Peer sent us its latest block, store it and consider it a valid peer."""
        self.app_log.debug("ws client got {} blocks from {}:{}".format(len(data), self.ip, self.port))
        if self.config.peers.syncing:
            self.app_log.debug("Ignoring, already syncing")
            return
        if not len(data):
            return
        # TODO: if index match and enough blocks, Set syncing and do it
        await self.client.manager.on_blocks(data)

    async def on_get_latest_block(self, data):
        """Peer sent us its latest block, store it and consider it a valid peer."""
        self.app_log.error("ws client got {} on_get_latest_block from {}:{}, IGNORED".format(data, self.ip, self.port))

    async def on_get_blocks(self, data):
        """server ask for list of blocks"""
        try:
            # TODO: dup code between http route and websocket handlers. AND... ws client + server!!!
            self.app_log.info('WSclient get-blocks: {}'.format(json.dumps(data)))
            start_index = int(data.get("start_index", 0))
            # safety, add bound on block# to fetch
            end_index = min(int(data.get("end_index", 0)), start_index + CHAIN.MAX_BLOCKS_PER_MESSAGE)
            # global chain object with cache of current block height,
            # so we can instantly answer to pulling requests without any db request
            if start_index > self.config.BU.get_latest_block()['index']:
                # early exit without request
                await self.emit('blocks', data=[], namespace="/chat")
            else:
                blocks = self.mongo.async_db.blocks.find({
                    '$and': [
                        {'index':
                            {'$gte': start_index}

                        },
                        {'index':
                            {'$lte': end_index}
                        }
                    ]
                }, {'_id': 0}).sort([('index',1)])
                await self.emit('blocks',
                                data=await blocks.to_list(length=CHAIN.MAX_BLOCKS_PER_MESSAGE),
                                namespace="/chat")
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
        self.config = get_config()
        self.consensus = self.config.consensus
        self.peers = self.config.peers
        self.app_log = getLogger("tornado.application")

        self.latest_peer_block = None
        self.connected = False
        self.probable_old = False

    async def start(self):
        try:
            self.client.manager = self
            self.client.register_namespace(ClientChatNamespace('/chat'))
            url = "http://{}:{}".format(self.peer.host, self.peer.port)
            self.app_log.info("ws client connecting to {}".format(url))
            await self.client.connect(url, namespaces=['/chat'])
            # self.connected = True
            await async_sleep(self.WAIT_FOR_PEERS)  # wait for an answer
            if not self.connected:
                self.app_log.warning("{} was not connected after {} sec, incrementing fails"
                                     .format(self.peer.to_string(), self.WAIT_FOR_PEERS))
                # await self.peers.increment_failed(self.peer)
                self.probable_old = True
                return
            if self.peer.host not in self.config.peers.outbound:
                # if we are not in the outgoing, we did not receive a peers answer, old peer (but ok)
                self.app_log.warning("{} was not connected after {} sec, probable old node"
                                     .format(self.peer.to_string(), self.WAIT_FOR_PEERS))
                self.probable_old = True
                await self.client.disconnect()
                return
            while self.connected:
                self.app_log.debug("{} loop, state:{}".format(self.peer.to_string(), self.client.eio.state))
                # This is a mess, surely we can do better.
                if self.client.eio.state == 'disconnected':
                    self.connected = False
                    return
                await async_sleep(30)
                # TODO: poll here after some time without activity?
        except Exception as e:
            self.app_log.warning("Exception {} connecting to {}".format(e, self.peer.to_string()))
        finally:
            pass

    async def on_latest_block(self, data):
        from yadacoin.block import Block  # Circular reference. Not good! - Do we need the object here?
        # processing in this object rather than ClientChatNamespace so consensus data is available from peers
        self.latest_peer_block = Block.from_dict(data)
        if not self.peers.syncing:
            self.app_log.debug("Trying to sync on latest block from {}".format(self.peer.to_string()))
            my_index = self.config.BU.get_latest_block()['index']
            if data['index'] == my_index + 1:
                self.app_log.debug("Next index, trying to merge from {}".format(self.peer.to_string()))
                if await self.consensus.process_next_block(data, self.peer):
                    pass
                    # if ok, block was inserted and event triggered by import block
                    # await self.peers.on_block_insert(data)
            elif data['index'] > my_index + 1:
                self.app_log.debug("Missing blocks between {} and {} , asking more to {}".format(my_index, data['index'], self.peer.to_string()))
                data = {"start_index": my_index + 1, "end_index": my_index + 1 + CHAIN.MAX_BLOCKS_PER_MESSAGE}
                await self.client.emit('get_blocks', data=data, namespace="/chat")
            elif data['index'] == my_index:
                self.app_log.debug("Same index, ignoring {} from {}".format(data['index'], self.peer.to_string()))
            else:
                # We have better
                self.app_log.debug("We have higher index, sending {} to ws {}".format(data['index'], self.peer.to_string()))
                block = self.config.BU.get_latest_block()
                block['time_utc'] = ts_to_utc(block['time'])
                await self.client.emit('latest_block', data=block, namespace="/chat")

    async def on_blocks(self, data):
        my_index = self.config.BU.get_latest_block()['index']
        if data[0]['index'] != my_index + 1:
            return
        self.peers.syncing = True
        try:
            inserted = False
            block = None  # Avoid linter warning
            for block in data:
                # print("looking for ", self.existing_blockchain.blocks[-1].index + 1)
                if block['index'] == my_index + 1:
                    if await self.consensus.process_next_block(block, self.peer, trigger_event=False):
                        inserted = True
                        my_index = block['index']
                    else:
                        break
                else:
                    # As soon as a block fails, abort
                    break
            if inserted:
                # If import was successful, inform out peers once the batch is processed
                await self.peers.on_block_insert(block)
                # then ask for the potential next batch
                data = {"start_index": my_index + 1, "end_index": my_index + 1 + CHAIN.MAX_BLOCKS_PER_MESSAGE}
                await self.client.emit('get_blocks', data=data, namespace="/chat")
            else:
               self.app_log.debug("Import aborted block: {}".format(my_index))
               return
        except Exception as e:
            import sys, os
            self.app_log.warning("Exception {} on_blocks".format(e))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)

        finally:
            self.peers.syncing = False
