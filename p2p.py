import socketio
import eventlet
import eventlet.wsgi
import json
import time
import signal
import sys
import requests
import base64
from multiprocessing import Process, Value, Array, Pool
from pymongo import MongoClient
from socketIO_client import SocketIO, BaseNamespace
from flask import Flask, render_template, request
from blockchainutils import BU
from blockchain import Blockchain, BlockChainException
from block import Block
from transaction import Transaction
from node import node


mongo_client = MongoClient('localhost')
db = mongo_client.yadacoin
collection = db.blocks
BU.collection = collection
Block.collection = collection
sio = socketio.Server()
app = Flask(__name__)
collection.remove({})


def output(string):
    sys.stdout.write(string)  # write the next character
    sys.stdout.flush()                # flush stdout buffer (actual character display)
    sys.stdout.write(''.join(['\b' for i in range(len(string))])) # erase the last written char

def signal_handler(signal, frame):
        print('Closing...')
        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

def getblocks(sid):
    print("getblocks ")
    sio.emit('getblocksreply', data=[x for x in BU.get_blocks()], room=sid, namespace='/chat')
    print 'sent blocks!'

votes = {}
def newblock(sid, data):
    print("new block ", data)
    try:
        incoming_block = Block.from_dict(data)
        incoming_block.verify()
    except Exception as e:
        print "block is bad"
        print e
        return
    except BaseException as e:
        print "block is bad"
        print e
        return
    try:
        block = BU.get_block_by_index(incoming_block.index)
    except:
        return
    if block:
        # we have the same block. let the voting begin!
        try:
            if incoming_block.index not in votes:
                votes[incoming_block.index] = {}
            votes[incoming_block.index][incoming_block.signature] = 1
            sio.emit('getblockvote', data=incoming_block.to_dict(), skip_sid=sid, namespace='/chat')
        except:
            print 'there was a problem when initializing a vote on a new block'
    else:
        # dry run this block in the blockchain. Does it belong?
        try:
            blocks = BU.get_block_objs()
            blocks.append(incoming_block)
            blocks_sorted = sorted(blocks, key=lambda x: x.index)
            blockchain = Blockchain(blocks_sorted)
            blockchain.verify()
        except:
            print 'something went wrong with the blockchain dry run of new block'
        try:
            incoming_block.save()
        except:
            print 'error while saving'

def newtransaction(sid, data):
    print("new transaction ", data)
    try:
        incoming_txn = Transaction.from_dict(data)
    except Exception as e:
        print "transaction is bad"
        print e
    except BaseException as e:
        print "transaction is bad"
        print e

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
        print e
    except BaseException as e:
        print e

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
        print e
    except BaseException as e:
        print e

def new_block_checker(current_index):
    while 1:
        try:
            current_index.value = BU.get_latest_block().get('index')
        except:
            pass
        time.sleep(1)


def sync(peers, config):
    connected = {}
    while 1:
        synced = False
        block_heights = {}
        latest_block = BU.get_latest_block()
        if latest_block:
            next_index = int(latest_block.get('index')) + 1
        else:
            next_index = 0
        for peer in peers:
            try:
                res = requests.get('http://{peer}:8000/getblock?index={index}'.format(peer=peer['ip'], index=next_index), timeout=0.01)
                content = json.loads(res.content)
                if not content:
                    print 'continue'
                    continue
                block = Block.from_dict(json.loads(res.content))
                sofar = db.consensus.find({'peer': peer['ip'], 'index': next_index})
                if not sofar.count():
                    if latest_block and latest_block.get('hash') == block.prev_hash:
                        db.consensus.insert({'peer': peer['ip'], 'index': next_index, 'id': block.signature, 'block': block.to_dict()})
                    else:
                        db.consensus.insert({'peer': peer['ip'], 'index': next_index, 'id': block.signature, 'block': block.to_dict()})
                print 'not blah'
            except:
                print 'blah'
                pass

        consensus = db.consensus.find({'index': next_index})
        counts = {}
        peers_already_used = []
        winning_block = {}
        for record in consensus:
            if record['peer'] in peers_already_used:
                continue
            peers_already_used.append(record['peer'])
            if record['id'] not in counts:
                counts[record['id']] = 0
            counts[record['id']] += 1
            if (float(counts[record['id']]) / float(len(peers))) > 0.51:
                winning_block = record['block']
        if winning_block:
            winning_block_obj = Block.from_dict(winning_block)
            winning_block_obj.save()

        time.sleep(1)


@app.route('/getblocks')
def app_getblocks():
    return json.dumps([x for x in BU.get_blocks()])

@app.route('/getblockheight')
def app_getblockheight():
    return json.dumps({'block_height': BU.get_latest_block().get('index')})

@app.route('/getblock')
def app_getblock():
    idx = int(request.args.get('index'))
    block = BU.get_block_by_index(idx)
    if block:
        return json.dumps(block)
    else:
        return '{}'

@sio.on('custom', namespace='/chat')
def custom(sid):
    print("custom hahahahaha ")

@sio.on('connect', namespace='/chat')
def connect(sid, environ):
    print("connect ", sid)

@sio.on('newblock', namespace='/chat')
def sio_newblock(sid, data):
    newblock(sid, data)

@sio.on('newtransaction', namespace='/chat')
def sio_newtransaction(sid, data):
    newtransaction(sid, data)

@sio.on('getblocksreply', namespace='/chat')
def sio_getblocksreply(sid, data):
    getblocksreply(sid, data)

@sio.on('blockvotereply', namespace='/chat')
def sio_blockvotereply(sid, data):
    blockvotereply(sid, data)

@sio.on('getblocks', namespace='/chat')
def sio_getblocks(sid):
    getblocks(sid)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', nargs=None, help='server or node')
    args = parser.parse_args()

    with open('config.json') as f:
        config = json.loads(f.read())

    with open('peers.json') as f:
        peers = json.loads(f.read())

    if args.mode == 'sync':
        sync(peers, config)
    elif args.mode == 'mine':
        node(config)
    elif args.mode == 'serve':
        # wrap Flask application with engineio's middleware
        app = socketio.Middleware(sio, app)

        # deploy as an eventlet WSGI server
        eventlet.wsgi.server(eventlet.listen(('', 8000)), app)
