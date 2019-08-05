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
from yadacoin.common import ts_to_utc
from yadacoin.chain import CHAIN
from yadacoin.peers import Peer
from yadacoin.transactionbroadcaster import TxnBroadcaster

SIO = None


# TODO: rename "chat" to something more meaningful, like "yada" or "node" ?
class ChatNamespace(AsyncNamespace):

    async def on_connect(self, sid, environ):
        if not 'config' in self.__dict__:
            # ChatNamespace is a singleton, same instance for everyone
            self.config = get_config()  # Will be done once at first request
            self.mongo = self.config.mongo
            self.app_log = getLogger("tornado.application")
            self.peers = self.config.peers
            self.consensus = self.config.consensus
        IP = environ['tornado.handler'].request.remote_ip
        if self.peers.free_inbound_slots <= 0:
            self.app_log.warning('No free slot, client rejected: {}'.format(IP))
            return False  # This will close the socket
        if not self.peers.allow_ip(IP):
            self.app_log.info('Client rejected: {}'.format(IP))
            return False  # This will close the socket
        self.config.peers.on_new_ip(IP)  # Store the ip to avoid duplicate connections
        await self.save_session(sid, {'ip': IP})
        if self.config.debug:
            self.app_log.info('Client connected: {}'.format(sid))

    async def on_disconnect_request(self, sid):
        # print('Disconnect request')
        await SIO.disconnect(sid, namespace='/chat')

    async def on_disconnect(self, sid):
        if self.config.debug:
            self.app_log.info('Client disconnected: {}'.format(sid))
        try:
            # This will also unregister the ip
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
            if incoming_txn.in_the_future():
                # Most important
                raise ValueError('In the future {}'.format(incoming_txn.transaction_signature))
            # print(incoming_txn.transaction_signature)
            dup_check_count = await get_config().mongo.async_db.miner_transactions.count_documents({'id': incoming_txn.transaction_signature})
            if dup_check_count:
                self.app_log.warning('found duplicate tx {}'.format(incoming_txn.transaction_signature))
                raise Exception("duplicate tx {}".format(incoming_txn.transaction_signature))
            await get_config().mongo.async_db.miner_transactions.insert_one(incoming_txn.to_dict())
            tb = TxnBroadcaster(self.config)
            await tb.txn_broadcast_job(incoming_txn)
        except Exception as e:
            self.app_log.warning("Bad transaction: {}".format(e))
            await self.force_close(sid)

    async def on_hello(self, sid, data):
        self.app_log.info('WS hello: {} {}'.format(sid, json.dumps(data)))
        try:
            async with self.session(sid) as session:
                if session['ip'] != data['ip']:
                    await self.config.peers.on_close_inbound(sid, ip=session['ip'])
                    raise Exception("IP mismatch")
                # TODO: test version also (ie: protocol version)
                # If peer data seem correct, add to our pool of inbound peers
            await self.save_session(sid, {'ip': data['ip'], 'port': data['port']})
            await self.config.peers.on_new_inbound(session['ip'], data['port'], data['version'], sid)
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

    async def on_get_latest_block(self, sid, data):
        """peer ask for our latest block"""
        self.app_log.info('WS get-latest-block: {} {}'.format(sid, json.dumps(data)))
        block = self.config.BU.get_latest_block()
        block['time_utc'] = ts_to_utc(block['time'])
        await self.emit('latest_block', data=block, room=sid)

    async def on_get_blocks(self, sid, data):
        """peer ask for list of blocks"""
        # TODO: dup code between http route and websocket handlers. move to a .mongo method?
        self.app_log.info('WS get-blocks: {} {}'.format(sid, json.dumps(data)))
        start_index = int(data.get("start_index", 0))
        # safety, add bound on block# to fetch
        end_index = min(int(data.get("end_index", 0)), start_index + CHAIN.MAX_BLOCKS_PER_MESSAGE)
        # global chain object with cache of current block height,
        # so we can instantly answer to pulling requests without any db request
        if start_index > self.config.BU.get_latest_block()['index']:
            # early exit without request
            await self.emit('blocks', data=[], room=sid)
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
            await self.emit('blocks', data=await blocks.to_list(length=CHAIN.MAX_BLOCKS_PER_MESSAGE), room=sid)

    async def on_latest_block(self, sid, data):
        """Client informs us of its new block"""
        # from yadacoin.block import Block  # Circular reference. Not good! - Do we need the object here?
        self.app_log.info('WS latest-block: {} {}'.format(sid, json.dumps(data)))
        # TODO: handle a dict here to store the consensus state
        # self.latest_peer_block = Block.from_dict(data)
        if not self.peers.syncing:
            async with self.session(sid) as session:
                peer = Peer(session['ip'], session['port'])
            self.app_log.debug("Trying to sync on latest block from {}".format(peer.to_string()))
            my_index = self.config.BU.get_latest_block()['index']
            if data['index'] == my_index + 1:
                self.app_log.debug("Next index, trying to merge from {}".format(peer.to_string()))
                if await self.consensus.process_next_block(data, peer):
                    pass
                    # if ok, block was inserted and event triggered by import block
                    # await self.peers.on_block_insert(data)
            elif data['index'] > my_index + 1:
                self.app_log.debug(
                    "Missing blocks between {} and {} , asking more to {}".format(my_index, data['index'],
                                                                                  peer.to_string()))
                data = {"start_index": my_index + 1, "end_index": my_index + 1 + CHAIN.MAX_BLOCKS_PER_MESSAGE}
                await self.emit('get_blocks', data=data, room=sid)
            else:
                # Remove later on
                self.app_log.debug(
                    "Old or same index, ignoring {} from {}".format(data['index'], peer.to_string()))

    async def on_blocks(self, sid, data):
        self.app_log.info('WS blocks: {} {}'.format(sid, json.dumps(data)))
        if not len(data):
            return
        my_index = self.config.BU.get_latest_block()['index']
        if data[0]['index'] != my_index + 1:
            return
        self.peers.syncing = True
        try:
            async with self.session(sid) as session:
                peer = Peer(session['ip'], session['port'])
            inserted = False
            block = None  # Avoid linter warning
            for block in data:
                # print("looking for ", self.existing_blockchain.blocks[-1].index + 1)
                if block['index'] == my_index + 1:
                    if await self.consensus.process_next_block(block, peer, trigger_event=False):
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
                await self.emit('get_blocks', data=data, room=sid)
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
        if int(block.version) != CHAIN.get_version_for_height(block.index):
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


