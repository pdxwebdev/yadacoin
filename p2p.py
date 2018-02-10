import socketio
import eventlet
import eventlet.wsgi
import json
import time
import signal
import sys
import requests
import base64
import humanhash
import re
from multiprocessing import Process, Value, Array, Pool
from pymongo import MongoClient
from socketIO_client import SocketIO, BaseNamespace
from flask import Flask, render_template, request
from blockchainutils import BU
from transactionutils import TU
from blockchain import Blockchain, BlockChainException
from block import Block
from transaction import TransactionFactory, Transaction, MissingInputTransactionException, Input, Output
from node import node
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress


sio = socketio.Server()
app = Flask(__name__)

class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

def output(string):
    sys.stdout.write(string)  # write the next character
    sys.stdout.flush()                # flush stdout buffer (actual character display)
    sys.stdout.write(''.join(['\b' for i in range(len(string))])) # erase the last written char

def signal_handler(signal, frame):
        print('Closing...')
        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

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
        dup_check = db.miner_transactions.find({'id': incoming_txn.transaction_signature})
        if dup_check.count():
            return
        db.miner_transactions.insert(incoming_txn.to_dict())
    except Exception as e:
        print e
    except BaseException as e:
        print e

def newblock(sid, data):
    print("new block ", data)
    try:
        incoming_block = Block.from_dict(data)
    except Exception as e:
        print "block is bad"
        print e
    except BaseException as e:
        print "block is bad"
        print e

    try:
        dup_check = db.consensus.find({'id': incoming_block.signature})
        if dup_check.count():
            return
        db.consensus.insert(incoming_block.to_dict())
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

def consensus(peers, config):
    from pymongo import MongoClient
    mongo_client = MongoClient('localhost')
    db = mongo_client.yadacoin
    collection = db.blocks
    consensus = db.consensus
    BU.collection = collection
    Block.collection = collection
    BU.consensus = consensus
    Block.consensus = consensus
    synced = False
    block_heights = {}
    latest_block = BU.get_latest_block()
    blockchain_difficulty = 0
    for block in BU.get_blocks():
        blockchain_difficulty += len(re.search(r'^[0]+', block.get('hash')).group(0))
    print blockchain_difficulty
    data = db.miner_transactions.find({}, {'_id': False})
    for txn in data:
        res = db.blocks.find({"transactions.id": txn['id']})
        if res.count():
            db.miner_transactions.remove({'id': txn['id']})

    if latest_block:
        next_index = int(latest_block.get('index')) + 1
    else:
        next_index = 0

    consensus = db.consensus.find({'index': next_index})
    highest_difficulty = 0
    peers_already_used = []
    winning_block = {}
    for record in consensus:
        difficulty = len(re.search(r'^[0]+', record['block'].get('hash')).group(0))
        if difficulty > highest_difficulty:
            highest_difficulty = difficulty
            winning_block = record['block']
    
    if winning_block:
        if latest_block.get('hash') == winning_block.get('prevHash'):
            # everything jives with our current history, everyone is happy
            winning_block_obj = Block.from_dict(winning_block)
            winning_block_obj.save()
        else:
            #need to rebase
            prev_hash = winning_block.get('prevHash')
            find_index = next_index - 1
            while 1:
                prev_block = db.consensus.find({'index': find_index, 'block.hash': prev_hash})
                if prev_block.count():
                    prev_block = prev_block[0]
                    difficulty += len(re.search(r'^[0]+', prev_block.get('hash')).group(0))
                    if (difficulty + highest_difficulty) > blockchain_difficulty:
                        db.blocks.remove({'index': latest_block.get('index'), 'hash': latest_block.get('hash')})
                        block = Block.from_dict(prev_block)
                        block.save()
                        break
                else:
                    for peer in peers:
                        try:
                            res = requests.get(
                                'http://{peer}:5000/getblockcandidate?index={index}&hash={hash}'.format(
                                    peer=peer,
                                    index=next_index,
                                    hash=prev_hash),
                                timeout=1)
                            resdata = json.loads(res.content)
                            break
                        except:
                            resdata = None

                    if resdata:
                        prev_hash = data.get('prevHash')
                        find_index -= 1
                        if find_index < 0:
                            break
                    else:
                        print 'block not found on network, fubar'
                        break
                        #this is bad
    else:
        print 'no winning block', next_index


def faucet(peers, config):
    public_key = config.get('public_key')
    my_address = str(P2PKHBitcoinAddress.from_pubkey(public_key.decode('hex')))
    private_key = config.get('private_key')
    TU.private_key = private_key
    BU.private_key = private_key
    mongo_client = MongoClient('localhost')
    db = mongo_client.yadacoin
    collection = db.blocks
    consensus = db.consensus
    miner_transactions = db.miner_transactions
    BU.collection = collection
    TU.collection = collection
    BU.consensus = consensus
    TU.consensus = consensus
    BU.miner_transactions = miner_transactions
    TU.miner_transactions = miner_transactions
    used_inputs = []
    new_inputs = []
    while 1:
        for x in mongo_client.yadacoinsite.faucet.find({'active': True}):
            balance = BU.get_wallet_balance(x['address'])
            if balance >= 25:
                mongo_client.yadacoinsite.faucet.update({'_id': x['_id']}, {'active': False, 'address': x['address']})

                continue
            last_id_in_blockchain = x.get('last_id')
            if last_id_in_blockchain and not mongo_client.yadacoin.blocks.find({'transactions.id': last_id_in_blockchain}).count():

                continue
            input_txns = BU.get_wallet_unspent_transactions(my_address)

            inputs = [Input.from_dict(input_txn) for input_txn in input_txns]
            inputs.extend(new_inputs)
            needed_inputs = []
            input_sum = 0
            done = False
            for y in inputs:
                if y.id in used_inputs:
                    continue
                txn = BU.get_transaction_by_id(y.id, instance=True)
                for txn_output in txn.outputs:
                    if txn_output.to == my_address:
                        input_sum += txn_output.value
                        needed_inputs.append(y)
                        if input_sum >= 1.1:
                            done = True
                            break
                if done == True:
                    break

            return_change_output = Output(
                to=my_address,
                value=input_sum-1.1
            )

            transaction = TransactionFactory(
                fee=0.1,
                public_key=public_key,
                private_key=private_key,
                inputs=needed_inputs,
                outputs=[
                    Output(to=x['address'], value=1),
                    return_change_output
                ]
            )
            TU.save(transaction.transaction)
            used_inputs.extend([n.id for n in needed_inputs])
            new_inputs = [n for n in new_inputs if n.id not in used_inputs]
            new_inputs.append(Input.from_dict(transaction.transaction.to_dict()))
            x['last_id'] = transaction.transaction.transaction_signature
            mongo_client.yadacoinsite.faucet.update({'_id': x['_id']}, x)
            for peer in peers:
                try:
                    socketIO = SocketIO(peer['ip'], 8000, wait_for_connection=False)
                    chat_namespace = socketIO.define(ChatNamespace, '/chat')
                    chat_namespace.emit('newtransaction', transaction.transaction.to_dict())
                    socketIO.wait(seconds=1)
                    socketIO.disconnect()
                except Exception as e:
                    print e
        time.sleep(10)

def add_friends():
    num = 0
    for transaction in BU.get_transactions():
        exists = mongo_client.yadacoinsite.friends.find({'id': transaction['id']})
        if not exists.count():
            transaction['humanized'] = humanhash.humanize(transaction['rid'])
            mongo_client.yadacoinsite.friends.insert(transaction)
        num += 1

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

@app.route('/getblockcandidate')
def app_getblockcandidate():
    idx = int(request.args.get('index'))
    block_hash = request.args.get('hash')
    q = {'index': idx}
    if block_hash:
        q['hash'] = block_hash
    res = db.consensus.find(q)
    if res.count():
        return json.dumps(res[0]['block'])
    else:
        return '{}'

@sio.on('newtransaction', namespace='/chat')
def sio_newtransaction(sid, data):
    newtransaction(sid, data)

@sio.on('newblock', namespace='/chat')
def sio_newblock(sid, data):
    newblock(sid, data)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', nargs=None, help='server or node')
    args = parser.parse_args()

    with open('config.json') as f:
        config = json.loads(f.read())

    with open('peers.json') as f:
        peers = json.loads(f.read())

    if args.mode == 'consensus':
        while 1:
            p = Process(target=consensus, args=(peers, config))
            p.start()
            p.join()
            time.sleep(1)
    elif args.mode == 'friends':
        BU.private_key = config['private_key']
        while 1:
            add_friends()
            time.sleep(1)
    elif args.mode == 'mine':
        node(config, peers)
    elif args.mode == 'serve':
        # wrap Flask application with engineio's middleware
        app = socketio.Middleware(sio, app)

        # deploy as an eventlet WSGI server
        eventlet.wsgi.server(eventlet.listen(('', 8000)), app)
    elif args.mode == 'faucet':
        faucet(peers, config)
