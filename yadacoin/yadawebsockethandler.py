"""
Web socket handler for yadacoin
"""

import json
from socketio import AsyncServer, AsyncNamespace
from logging import getLogger

from yadacoin.transaction import Transaction
from yadacoin.config import get_config
from yadacoin.blockchainutils import BU
from yadacoin.poolnamespace import PoolNamespace


SIO = None


# TODO: rename "chat" to something more meaningful, like "yada" or "node" ?
class ChatNamespace(AsyncNamespace):

    async def on_connect(self, sid, environ):
        if not 'config' in self.__dict__:
            # ChatNamespace is a singleton, same instance for everyone
            self.config = get_config()  # Will be done once at first request
            self.app_log = getLogger("tornado.application")
            self.peers = self.config.peers
        IP = environ['REMOTE_ADDR']
        if self.peers.free_inbound_slots <= 0:
            self.app_log.warning('No free slot, client rejected: {}'.format(IP))
            return False  # This will close the socket
        if not self.peers.allow_ip(IP):
            self.app_log.info('Client rejected: {}'.format(IP))
            return False  # This will close the socket
        self.config.peers.on_new_ip(IP)  # Store the ip to avoid duplicate connections
        await self.save_session(sid, {'IP': IP})
        if self.config.debug:
            self.app_log.info('Client connected: {}'.format(sid))

    async def on_disconnect_request(sid):
        # print('Disconnect request')
        await SIO.disconnect(sid, namespace='/chat')

    async def on_disconnect(self, sid):
        if self.config.debug:
            self.app_log.info('Client disconnected: {}'.format(sid))
        try:
            await self.config.peers.on_close_inbound(sid)
        except Exception as e:
            self.app_log.warning("Error on_disconnect: {}".format(e))

    async def force_close(self, sid):
        # TODO: can we force close the socket?
        await SIO.disconnect(sid, namespace='/chat')
        # This processes a disconnect event, but does not close the underlying socket. Client still can send messages.

    async def on_newtransaction(self, sid, data):
        # TODO: generic test, is the peer known and has rights for this command? Decorator?
        if self.config.debug:
            self.app_log.info('WS newtransaction: {} {}'.format(sid, json.dumps(data)))
        try:
            incoming_txn = Transaction.from_dict(BU().get_latest_block()['index'], data)
            # print(incoming_txn.transaction_signature)
            dup_check_count = await get_config().mongo.async_db.miner_transactions.count_documents({'id': incoming_txn.transaction_signature})
            if dup_check_count:
                self.app_log.warning('found duplicate tx {}'.format(incoming_txn.transaction_signature))
                raise Exception("duplicate tx {}".format(incoming_txn.transaction_signature))
            await get_config().mongo.async_db.miner_transactions.insert_one(incoming_txn.to_dict())
        except Exception as e:
            self.app_log.warning("Bad transaction: {}".format(e))
            await self.force_close(sid)

    async def on_hello(self, sid, data):
        self.app_log.info('WS hello: {} {}'.format(sid, json.dumps(data)))
        try:
            async with self.session(sid) as session:
                if session['IP'] != data['ip']:
                    raise Exception("IP mismatch")
                # TODO: test version also (ie: protocol version)
                # If peer data seem correct, add to our pool of inbound peers
                await self.config.peers.on_new_inbound(session['IP'], data['port'], data['version'], sid)
        except Exception as e:
            self.app_log.warning("bad hello: {}".format(e))
            await self.force_close(sid)

    async def on_peers(self, sid, data):
        """we got a list of peers"""
        self.app_log.info('WS peers: {} {}'.format(sid, json.dumps(data)))
        # This will process and insert the new peers if any, then queue them for testing
        await self.peers.on_new_peer_list(data['peers'])
        #

    async def on_get_peers(self, sid, data):
        """peer ask for list of our list of peers"""
        self.app_log.info('WS get-peers: {} {}'.format(sid, json.dumps(data)))
        data = self.peers.to_dict()  # this only includes active peers from last refresh
        # TODO: include refresh date?
        await self.emit('peers', data, room=sid)

#


def get_sio():
    global SIO
    if SIO is None:
        ws_init()
    return SIO


def ws_init():
    global SIO
    SIO = AsyncServer(async_mode='tornado', logger=False, engineio_logger=None)
    # see https://github.com/miguelgrinberg/python-socketio/blob/master/examples/server/tornado/app.py
    SIO.register_namespace(ChatNamespace('/chat'))
    # See https://python-socketio.readthedocs.io/en/latest/server.html#namespaces
    if get_config().max_miners > 0:
        # Only register pool namespace if we want to run a pool
        SIO.register_namespace(PoolNamespace('/pool'))




# no newblock websocket event seems used
"""
@SIO.on('newblock', namespace='/chat')
async def on_newblock(self, data):
    # print("new block ", data)
    try:
        peer = Peer.from_string(WS_CONFIG, WS_MONGO, request.json.get('peer'))
        block = Block.from_dict(WS_CONFIG, WS_MONGO, data)
        if block.index == 0:
            return
        if int(block.version) != BU().get_version_for_height(block.index):
            print('rejected old version %s from %s' % (block.version, peer))
            return
        WS_MONGO.db.consensus.update({
            'index': block.to_dict().get('index'),
            'id': block.to_dict().get('id'),
            'peer': peer.to_string()
        },
            {
                'block': block.to_dict(),
                'index': block.to_dict().get('index'),
                'id': block.to_dict().get('id'),
                'peer': peer.to_string()
            }, upsert=True)

    except Exception as e:
        print("block is bad")
        raise e
"""


