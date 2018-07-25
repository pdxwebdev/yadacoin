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
import pymongo
from multiprocessing import Process, Value, Array, Pool
from pymongo import MongoClient
from socketIO_client import SocketIO, BaseNamespace
from flask import Flask, render_template, request, Response
from blockchainutils import BU
from transactionutils import TU
from blockchain import Blockchain, BlockChainException
from block import Block
from transaction import TransactionFactory, Transaction, MissingInputTransactionException, Input, Output
from node import node
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress



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
    db = mongo_client[config.get('database')]
    collection = db.blocks
    consensus = db.consensus
    BU.collection = collection
    Block.collection = collection
    BU.consensus = consensus
    Block.consensus = consensus
    synced = False
    block_heights = {}
    latest_block = BU.get_latest_block()
    if not latest_block:
        genesis_block = Block.from_dict({
            "nonce": 8153, 
            "index": 0, 
            "hash": "96bc737dbfdb5a27a119fc0fd7e233e83b680af3e82da96c73b49d988368322f", 
            "transactions": [
                {
                    "public_key": "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570", 
                    "fee": 0.0, 
                    "hash": "71429326f00ba74c6665988bf2c0b5ed9de1d57513666633efd88f0696b3d90f", 
                    "dh_public_key": "", 
                    "relationship": "", 
                    "inputs": [], 
                    "outputs": [
                        {
                            "to": "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4", 
                            "value": 50.0
                        }
                    ], 
                    "rid": "", 
                    "id": "MEUCIQDs4oeAH42DhwJ1SIN6v8ywkmF+l8Tdeuhr4BzbRvFpfQIgCRjufiYRdG4WntCUaLdbZiC4ynyf3C4RCRCDJGkRyrQ="
                }
            ], 
            "public_key": "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570", 
            "prevHash": "", 
            "id": "MEQCID5baV/LExDA3uG5EhfGgNyDJaUSyi1+h7Q2GTiOw8ofAiAJ7EV5aih1OjnZz2XFjFI9fzRPRVGoZWoBKMW/9jRRkA==", 
            "merkleRoot": "705d831ced1a8545805bbb474e6b271a28cbea5ada7f4197492e9a3825173546"
        })
        genesis_block.save()
        db.consensus.insert({
            'block': genesis_block.to_dict(),
            'peer': 'me',
            'id': genesis_block.signature,
            'index': 0
            })
        latest_block = genesis_block.to_dict()
        db.consensus.insert({
            'block': genesis_block.to_dict(),
            'index': genesis_block.to_dict().get('index'),
            'id': genesis_block.to_dict().get('id')})

    data = db.miner_transactions.find({}, {'_id': False})
    for txn in data:
        res = db.blocks.find({"transactions.id": txn['id']})
        if res.count():
            db.miner_transactions.remove({'id': txn['id']})

    if latest_block:
        next_index = int(latest_block.get('index')) + 1
    else:
        next_index = 0

    winning_block = {}
    while 1:
        latests = db.consensus.find({}).sort('index', pymongo.DESCENDING)
        if latests.count():
            print latests[0]['index']
            records = db.consensus.find({'index': latests[0]['index']})
            if records.count():
                heighest = 0
                for record in records:
                    val = len(re.search(r'^[0]+', record['block']['hash']).group(0))
                    if val > heighest:
                        winning_block = record['block']
                        peer = record['peer']
        else:
            print "no records cound at index:", next_index
            break

        if winning_block:
            if latest_block.get('hash') == winning_block.get('prevHash'):
                # everything jives with our current history, everyone is happy
                db.blocks.insert(winning_block)
                print 'winning block inserted at: ', winning_block.get('index')
                latest_block = BU.get_latest_block()
                next_index = int(latest_block.get('index')) + 1
            else:
                winning_block = Block.from_dict(winning_block)
                print retrace(winning_block, db, peer)
        else:
            print 'no winning block for index:', next_index
            break



def faucet(peers, config):
    from pymongo import MongoClient
    public_key = config.get('public_key')
    my_address = str(P2PKHBitcoinAddress.from_pubkey(public_key.decode('hex')))
    private_key = config.get('private_key')
    TU.private_key = private_key
    BU.private_key = private_key
    mongo_client = MongoClient('localhost')
    db = mongo_client[config.get('database')]
    collection = db.blocks
    consensus = db.consensus
    miner_transactions = db.miner_transactions
    BU.database = config.get('database')
    BU.collection = collection
    TU.collection = collection
    BU.consensus = consensus
    TU.consensus = consensus
    BU.miner_transactions = miner_transactions
    TU.miner_transactions = miner_transactions
    used_inputs = []
    new_inputs = []
    for x in mongo_client[config.get('site_database')].faucet.find({'active': True}):
        balance = BU.get_wallet_balance(x['address'])
        if balance >= 25:
            mongo_client[config.get('site_database')].faucet.update({'_id': x['_id']}, {'active': False, 'address': x['address']})

            continue
        last_id_in_blockchain = x.get('last_id')
        if last_id_in_blockchain and not mongo_client[config.get('database')].blocks.find({'transactions.id': last_id_in_blockchain}).count():

            continue

        input_txns = BU.get_wallet_unspent_transactions(my_address)
        miner_transactions = db.miner_transactions.find()
        mtxn_ids = []
        for mtxn in miner_transactions:
            for mtxninput in mtxn['inputs']:
                mtxn_ids.append(mtxninput['id'])

        inputs = [Input.from_dict(input_txn) for input_txn in input_txns if input_txn['id'] not in mtxn_ids]

        needed_inputs = []
        input_sum = 0
        done = False
        for y in inputs:
            txn = BU.get_transaction_by_id(y.id, instance=True)
            for txn_output in txn.outputs:
                if txn_output.to == my_address:
                    input_sum += txn_output.value
                    needed_inputs.append(y)
                    db.checked_out_txn_ids.insert({'id': y.id})
                    if input_sum >= 1.1:
                        done = True
                        break
            if done == True:
                break
        if not done:
            print 'not enough money'
            return
        return_change_output = Output(
            to=my_address,
            value=input_sum-1.1
        )
        try:
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
        except Exception as e:
            print x
        try:
            transaction.transaction.verify()
        except:
            mongo_client[config.get('site_database')].failed_faucet_transactions.insert(transaction.transaction.to_dict())
            print 'faucet transaction failed'
        TU.save(transaction.transaction)
        x['last_id'] = transaction.transaction.transaction_signature
        mongo_client[config.get('site_database')].faucet.update({'_id': x['_id']}, x)
        print 'saved. sending...', x['address']
        for peer in peers:
            try:
                socketIO = SocketIO(peer['ip'][:-5], peer['ip'][-4:], wait_for_connection=False)
                chat_namespace = socketIO.define(ChatNamespace, '/chat')
                chat_namespace.emit('newtransaction', transaction.transaction.to_dict())
                socketIO.disconnect()
            except Exception as e:
                print e

def retrace(block, db, peer):
    print "retracing..."
    blocks = {}
    blocks[block.index] = block
    db.consensus.insert({
        'block': block.to_dict(),
        'index': block.to_dict().get('index'),
        'id': block.to_dict().get('id'),
        'peer': peer})
    while 1:
        try:
            # 2. if we don't, query the peer for the prevHash
            res = db.consensus.find({'block.hash': block.prev_hash})
            if res.count():
                block = Block.from_dict(res[0]['block'])
            else:
                res = requests.get(peer + '/get-block?hash=' + block.prev_hash)
                block = Block.from_dict(json.loads(res.content))
                db.consensus.insert({
                    'block': block.to_dict(),
                    'index': block.to_dict().get('index'),
                    'id': block.to_dict().get('id'),
                    'peer': peer})
            blocks[block.index] = block
        except:
            # if they don't have it, throw out the chain
            return "peer has broken chain or response was invalid"

        # if they do have it, query our consensus collection for prevHash of that block, repeat 1 and 2 until index 1
        prev_blocks_check = db.blocks.find({'hash': block.prev_hash})
        
        if prev_blocks_check.count():
            # if we have it in our blockchain, then we've hit the fork point
            # now we have to loop through the current block array and build a blockchain
            # then we compare the block height and difficulty of the two chains
            # replace our current chain if necessary by removing them from the database
            # then looping though our new chain, inserting the new blocks
            existing_blockchain = Blockchain([x for x in db.blocks.find({})])
            blockchain = Blockchain([x for i, x in blocks.iteritems()])
            # If the block height is equal, we throw out the inbound chain, it muse be greater
            # If the block height is lower, we throw it out
            # if the block height is heigher, we compare the difficulty of the entire chain
            if blockchain.get_difficulty() > existing_blockchain.get_difficulty() and \
                blockchain.get_highest_block_height() > existing_blockchain.get_highest_block_height():
                    for idx, block in blocks.items():
                        db.blocks.remove({'index': block.index})
                        db.blocks.insert(block.to_dict())
                    return "fully synced"
            else:
                return "This chain lost", blockchain.get_difficulty(), existing_blockchain.get_difficulty()
        # lets go down the hash path to see where prevHash is in our blockchain, hopefully before the genesis block
        # we need some way of making sure we have all previous blocks until we hit a block with prevHash in our main blockchain
        #there is no else, we just loop again
        # if we get to index 1 and prev hash doesn't match the genesis, throw out the chain and black list the peer
        # if we get a fork point, prevHash is found in our consensus or genesis, then we compare the current
        # blockchain against the proposed chain. 
        if block.index == 0:
            return "zero index reached"
    return "doesn't follow any known chain" # throwing out the block for now

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', nargs=None, help='serve, mine, or faucet')
    parser.add_argument('config', default="config.json", nargs=None, help='config file')
    parser.add_argument('peers', default="peers.json", nargs=None, help='peers')
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.loads(f.read())

    with open(args.peers) as f:
        peers = json.loads(f.read())

    if args.mode == 'consensus':
        while 1:
            consensus(peers, config)
            time.sleep(1)
            """
            p = Process(target=consensus, args=(peers, config))
            p.start()
            p.join()
            """
    elif args.mode == 'mine':
        while 1:
            node(config, peers)
            """
            p = Process(target=node, args=(config, peers))
            p.start()
            p.join()
            """
            time.sleep(10)
    elif args.mode == 'faucet':
        while 1:
            p = Process(target=faucet, args=(peers, config))
            p.start()
            p.join()
            time.sleep(1)
    elif args.mode == 'serve':
        # wrap Flask application with engineio's middleware
        from pymongo import MongoClient
        mongo_client = MongoClient('localhost')
        db = mongo_client[config.get('database')]
        sio = socketio.Server()
        app = Flask(__name__)

        @sio.on('newblock', namespace='/chat')
        def newblock(data):
            #print("new block ", data)
            try:
                incoming_block = Block.from_dict(data)
                if incoming_block.index == 0:
                    return
            except Exception as e:
                print "block is bad"
                print e
            except BaseException as e:
                print "block is bad"
                print e

            try:
                peer = request.json.get('peer')
                dup_check = db.consensus.find({'id': incoming_block.signature, 'peer': peer})
                if dup_check.count():
                    return "dup"
                db.consensus.insert({
                    'block': incoming_block.to_dict(),
                    'index': incoming_block.to_dict().get('index'),
                    'id': incoming_block.to_dict().get('id'),
                    'peer': peer})
                # before inserting, we need to check it's chain
                # search consensus for prevHash of incoming block.
                #prev_blocks_check = db.blocks.find({'hash': incoming_block.prev_hash})
                #if prev_blocks_check.count():
                    # 1. if we have it, then insert it.
                #    db.consensus.insert({
                #        'block': incoming_block.to_dict(),
                #        'index': incoming_block.to_dict().get('index'),
                #        'id': incoming_block.to_dict().get('id'),
                #        'peer': peer})
                #else:
                    # 2 scenarios
                    # 1. the 3 is late to the game
                    # 2. 1 and 2 do not find prev_hash from 3 and 
                    # we have a fork
                    # the consensus has the previous block to the incoming block but it's not in the block chain
                    # we need to do the chain compare routine here and decide if we're going with the blockchain
                    # belongs to the incoming block, or stay with our existing one
                    
                    #retrace(incoming_block, db, peer)
                   # return
            except Exception as e:
                print e
            except BaseException as e:
                print e

        @sio.on('newtransaction', namespace='/chat')
        def newtransaction(sid, data):
            #print("new transaction ", data)
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

        @app.route('/get-blocks')
        def get_blocks():
            from pymongo import MongoClient
            mongo_client = MongoClient('localhost')
            db = mongo_client.yadacoin
            blocks = [x for x in db.blocks.find({
                '$and': [
                    {'index': 
                        {'$gte': int(request.args.get('start_index'))}
                    }, 
                    {'index': 
                        {'$lte': int(request.args.get('end_index'))}
                    }
                ]
            }, {'_id': 0}).sort([('index',1)])]

            def generate(blocks):
                for i, block in enumerate(blocks):
                    print 'sending block index:', block['index']
                    prefix = '[' if i == 0 else ''
                    suffix = ']' if i >= len(blocks) -1  else ','
                    yield prefix + json.dumps(block) + suffix
            return Response(generate(blocks), mimetype='application/json')

        @app.route('/getblocks')
        def app_getblocks():
            return json.dumps([x for x in BU.get_blocks()])

        @app.route('/newblock', methods=['POST'])
        def app_newblock():
            newblock(request.json)
            return 'ok'

        @app.route('/getblockheight')
        def app_getblockheight():
            return json.dumps({'block_height': BU.get_latest_block().get('index')})

        @app.route('/get-block', methods=['GET'])
        def app_getblock():
            res = db.consensus.find({'block.hash': request.args.get('hash')}, {'_id': 0})
            return json.dumps(res[0]['block'])

        app = socketio.Middleware(sio, app)
        # deploy as an eventlet WSGI server
        eventlet.wsgi.server(eventlet.listen((config.get('host'), config.get('port'))), app)