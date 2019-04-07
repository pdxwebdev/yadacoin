"""
Web socket handler for yadacoin
"""

# import json
import socketio
from yadacoin.transaction import Transaction

from yadacoin.config import get_config
from yadacoin.blockchainutils import BU

SIO = socketio.AsyncServer(async_mode='tornado')
# see https://github.com/miguelgrinberg/python-socketio/blob/master/examples/server/tornado/app.py

# TODO: refactor as a class or use a global CONFIG var from yadacoin.config, would avoid passing config as param everywhere
# Same goes for mongo
#WS_CONFIG = None
#WS_MONGO = None


@SIO.on('connect', namespace='/chat')
async def chat_connect(sid, environ):
    pass
    # print('Client connected')
    # await SIO.emit('my response', {'data': 'Connected', 'count': 0}, room=sid, namespace='/chat')


@SIO.on('disconnect request', namespace='/chat')
async def disconnect_request(sid):
    # print('Disconnect request')
    await SIO.disconnect(sid, namespace='/chat')


@SIO.on('disconnect', namespace='/chat')
def chat_disconnect(sid):
    pass
    # print('Client disconnected')


@SIO.on('newtransaction', namespace='/chat')
async def newtransaction(sid, data):
    print("newtransaction", data)
    try:
        incoming_txn = Transaction.from_dict(BU().get_latest_block()['index'], data)
    except Exception as e:
        print("transaction is bad", e)
        raise Exception("transaction is bad")

    try:
        print(incoming_txn.transaction_signature)
        dup_check = get_config().mongo.db.miner_transactions.find({'id': incoming_txn.transaction_signature})
        if dup_check.count():
            print('found duplicate')
            raise Exception("duplicate")
            get_config().mongo.db.miner_transactions.update(incoming_txn.to_dict(), incoming_txn.to_dict(), upsert=True)
    except Exception as e:
        raise Exception("transaction is bad", e)

@SIO.on('hello', namespace='/chat')
async def newtransaction(sid, data):
    print("hello", data)
    try:
        pass
    except Exception as e:
        raise Exception("bad hello")

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


