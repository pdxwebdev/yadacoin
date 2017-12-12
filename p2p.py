import socketio
import eventlet
import eventlet.wsgi
import json
from pymongo import MongoClient
from flask import Flask, render_template
from blockchainutils import BU
from blockchain import Blockchain
from block import Block
from transaction import Transaction


mongo_client = MongoClient()
db = mongo_client.yadacoin
collection = db.blocks
BU.collection = collection
Block.collection = collection
sio = socketio.Server()
app = Flask(__name__)
collection.remove({})
@app.route('/')
def index():
    """Serve the client-side application."""
    return render_template('index.html')

@sio.on('connect', namespace='/chat')
def connect(sid, environ):
    print("connect ", sid)

@sio.on('new block', namespace='/chat')
def newblock(sid, data):
    print("new block ", data)
    try:
        incoming_block = Block.from_dict(data)
        incoming_block.verify()
    except Exception as e:
        print "block is bad"
        raise e
    block = BU.get_block_by_index(incoming_block.index)
    if block:
        # we have the same block. let the voting begin!
        if incoming_block.index not in votes:
            votes[incoming_block.index] = {}
        votes[incoming_block.index][incoming_block.signature] = 1
        sio.emit('getblockvote', data=incoming_block.to_dict(), skip_sid=sid, namespace='/chat')
    else:
        # dry run this block in the blockchain. Does it belong?
        blocks = BU.get_block_objs()
        blocks.append(incoming_block)
        blocks_sorted = sorted(blocks, key=lambda x: x.index)
        blockchain = Blockchain(blocks_sorted)
        try:
            blockchain.verify()
            incoming_block.save()
        except Exception as e:
            raise e

@sio.on('newtransaction', namespace='/chat')
def newtransaction(sid, data):
    print("new transaction ", data)
    try:
        incoming_txn = Transaction.from_dict(data)
    except Exception as e:
        print "transaction is bad"
        raise e

    try:
        with open('miner_transactions.json') as f:
            data = json.loads(f.read())

        with open('miner_transactions.json', 'w') as f:
            abort = False
            for x in data:
                if x.get('id') == incoming_txn.transaction_signature:
                    abort = True
            if not abort:
                data.append(incoming_txn.to_dict())
                f.write(json.dumps(data, indent=4))

    except Exception as e:
        raise e

@sio.on('getblocksreply', namespace='/chat')
def getblocksreply(self, data):
    blocks = []
    for block_dict in data:
        block = Block.from_dict(block_dict)
        block.verify()
        blocks.append(block)

    blocks_sorted = sorted(blocks, key=lambda x: x.index)
    if len(BU.get_latest_block()):
        biggest_index = BU.get_latest_block().get('index')
    else:
        biggest_index = -1
    if blocks_sorted:
        biggest_index_incoming = blocks_sorted[-1].index
    else:
        biggest_index_incoming = -1
    if blocks_sorted and biggest_index < biggest_index_incoming:
        blockchain = Blockchain(blocks_sorted)
        try:
            blockchain.verify()
        except:
            print 'peer blockchain did not verify, aborting update'
            return
        collection.remove({})
        print 'truncating!'
        for block in blocks_sorted:
            block.verify()
            block.save()
            print 'saving!'
    else:
        print 'my chain is longer!', biggest_index, biggest_index_incoming
        return
    print 'on_getblocksreply', 'done!'

votes = {}
@sio.on('blockvotereply', namespace='/chat')
def blockvotereply(sid, data):
    try:
        block = Block.from_dict(data)
        block.verify()
        if block.index not in votes:
            votes[block.index] = {}
        if block.signature not in votes[block.index]:
            votes[block.index][block.signature] = 0
        votes[block.index][block.signature] += 1

        peers = len(sio.manager.rooms['/chat'])

        if float(votes[block.index][block.signature]) / float(peers)  > 0.51:
            blocks = [x for x in BU.get_block_objs() if x.index != block.index]
            blocks.append(block)
            blocks_sorted = sorted(blocks, key=lambda x: x.index)
            blockchain = Blockchain(blocks_sorted)
            try:
                blockchain.verify()
                delete_block = Block.from_dict(BU.get_block_by_index(block.index))
                delete_block.delete()
                block.save()
            except:
                print 'incoming block does not belong here'

    except Exception as e:
        raise e

@sio.on('getblocks', namespace='/chat')
def getblocks(sid):
    print("getblocks ")
    sio.emit('getblocksreply', data=[x for x in BU.get_blocks()], room=sid, namespace='/chat')

@sio.on('disconnect', namespace='/chat')
def disconnect(sid):
    print('disconnect ', sid)

if __name__ == '__main__':
    blockchain = Blockchain(BU.get_blocks())
    blockchain.verify()
    # wrap Flask application with engineio's middleware
    app = socketio.Middleware(sio, app)

    # deploy as an eventlet WSGI server
    eventlet.wsgi.server(eventlet.listen(('', 8000)), app)