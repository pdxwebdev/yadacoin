"""
Web socket handler for yadacoin
"""

import json
import socketio
from logging import getLogger
from yadacoin.transaction import Transaction

from yadacoin.config import get_config
from yadacoin.blockchainutils import BU


class ChatNamespace(socketio.AsyncNamespace):

    async def on_connect(self, sid, environ):
        if not 'config' in self.__dict__:
            # ChatNamespace is a singleton, same instance for everyone
            self.config = get_config()  # Will be done once at first request
            self.app_log = getLogger("tornado.application")
            self.peers = self.config.peers
        IP = environ['REMOTE_ADDR']
        if not self.peers.allow_in(IP):
            self.app_log.info('Client rejected: {}'.format(IP))
            return False  # This will close the socket
        await self.save_session(sid, {'IP': IP})
        if self.config.debug:
            self.app_log.info('Client connected: {}'.format(sid))

    async def on_disconnect_request(sid):
        # print('Disconnect request')
        await SIO.disconnect(sid, namespace='/chat')

    def on_disconnect(self, sid):
        if self.config.debug:
            self.app_log.info('Client disconnected: {}'.format(sid))

    async def force_close(self, sid):
        # TODO: can we force close the socket?
        await SIO.disconnect(sid, namespace='/chat')
        # This processes a disconnect event, but does not close the underlying socket. Client still can send messages.

    async def on_newtransaction(self, sid, data):
        self.app_log.info('WS newtransaction: {} {}'.format(sid, json.dumps(data)))
        try:
            incoming_txn = Transaction.from_dict(BU().get_latest_block()['index'], data)
        except Exception as e:
            self.app_log.warning('Bad tx: {}'.format(e))
            await self.force_close(sid)

        try:
            print(incoming_txn.transaction_signature)
            dup_check = get_config().mongo.db.miner_transactions.find({'id': incoming_txn.transaction_signature})
            if dup_check.count():
                self.app_log.warning('found duplicate tx')
                raise Exception("duplicate")
                get_config().mongo.db.miner_transactions.update(incoming_txn.to_dict(), incoming_txn.to_dict(),
                                                                upsert=True)
        except Exception as e:
            self.app_log.warning("transaction is bad", e)
            await self.force_close(sid)

    async def on_hello(self, sid, data):
        self.app_log.info('WS hello: {} {}'.format(sid, json.dumps(data)))
        try:
            async with self.session(sid) as session:
                if session['IP'] != data['ip']:
                    raise Exception("IP mismatch")
                self.config.peers.on_new_inbound(session['IP'], data['port'], data['version'], sid)
        except Exception as e:
            self.app_log.warning("bad hello: {}".format(e))
            await self.force_close(sid)


SIO = socketio.AsyncServer(async_mode='tornado')
# see https://github.com/miguelgrinberg/python-socketio/blob/master/examples/server/tornado/app.py

SIO.register_namespace(ChatNamespace('/chat'))
# See https://python-socketio.readthedocs.io/en/latest/server.html#namespaces




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


