import socketio
import json
import time
import signal
import sys
import requests
import base64
import humanhash
import re
import pymongo
import subprocess
import os
from sys import exit
from multiprocessing import Process, Value, Array, Pool
from socketIO_client import SocketIO, BaseNamespace
from flask import Flask, render_template, request, Response
from yadacoin import TransactionFactory, Transaction, \
                    MissingInputTransactionException, \
                    Input, Output, Block, Config, Peers, \
                    Blockchain, BlockChainException, TU, BU, \
                    Mongo, BlockFactory, NotEnoughMoneyException
from node import node
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from endpoints import *
from gevent import pywsgi


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

def send(to, value):
    Peers.init()
    Mongo.init()
    used_inputs = []
    new_inputs = []

    try:
        transaction = TransactionFactory(
            fee=0.01,
            public_key=Config.public_key,
            private_key=Config.private_key,
            outputs=[
                Output(to=to, value=value)
            ]
        )
    except NotEnoughMoneyException as e:
        print "not enough money yet"
        return
    except:
        raise
    try:
        transaction.transaction.verify()
    except:
        print 'transaction failed'
    TU.save(transaction.transaction)
    print 'Transaction generated successfully. Sending:', value, 'To:', to 
    for peer in Peers.peers:
        try:
            socketIO = SocketIO(peer.host, peer.port, wait_for_connection=False)
            chat_namespace = socketIO.define(ChatNamespace, '/chat')
            chat_namespace.emit('newtransaction', transaction.transaction.to_dict())
            socketIO.disconnect()
            print 'Sent to:', peer.host, peer.port
        except Exception as e:
            print e

def faucet():
    Mongo.init()
    used_inputs = []
    new_inputs = []
    for x in Mongo.site_db.faucet.find({'active': True}):
        balance = BU.get_wallet_balance(x['address'])
        if balance >= 25:
            Mongo.site_db.faucet.update({'_id': x['_id']}, {'active': False, 'address': x['address']})

            continue
        last_id_in_blockchain = x.get('last_id')
        if last_id_in_blockchain and not Mongo.db.blocks.find({'transactions.id': last_id_in_blockchain}).count():

            continue

        try:
            transaction = TransactionFactory(
                fee=0.01,
                public_key=Config.public_key,
                private_key=Config.private_key,
                outputs=[
                    Output(to=x['address'], value=5)
                ]
            )
        except NotEnoughMoneyException as e:
            print "not enough money yet"
            return
        except Exception as e:
            print x
        try:
            transaction.transaction.verify()
        except:
            Mongo.site_db.failed_faucet_transactions.insert(transaction.transaction.to_dict())
            print 'faucet transaction failed'
        TU.save(transaction.transaction)
        x['last_id'] = transaction.transaction.transaction_signature
        Mongo.site_db.faucet.update({'_id': x['_id']}, x)
        print 'saved. sending...', x['address']
        for peer in Peers.peers:
            try:
                socketIO = SocketIO(peer.host, peer.port, wait_for_connection=False)
                chat_namespace = socketIO.define(ChatNamespace, '/chat')
                chat_namespace.emit('newtransaction', transaction.transaction.to_dict())
                socketIO.disconnect()
            except Exception as e:
                print e

def consensus():
    Mongo.init()
    synced = False
    block_heights = {}
    latest_block = BU.get_latest_block()
    if not latest_block:
        genesis_block = BlockFactory.get_genesis_block()
        genesis_block.save()
        Mongo.db.consensus.insert({
            'block': genesis_block.to_dict(),
            'peer': 'me',
            'id': genesis_block.signature,
            'index': 0
            })
        latest_block = genesis_block.to_dict()
        Mongo.db.consensus.insert({
            'block': genesis_block.to_dict(),
            'index': genesis_block.to_dict().get('index'),
            'id': genesis_block.to_dict().get('id')})

    data = Mongo.db.miner_transactions.find({}, {'_id': False})
    for txn in data:
        res = Mongo.db.blocks.find({"transactions.id": txn['id']})
        if res.count():
            Mongo.db.miner_transactions.remove({'id': txn['id']})

    if latest_block:
        next_index = int(latest_block.get('index')) + 1
    else:
        next_index = 0

    winning_block = {}
    latests = Mongo.db.consensus.find({}).sort('index', pymongo.DESCENDING)
    latest_blocks = Mongo.db.blocks.find({}).sort('index', pymongo.DESCENDING)
    if latests.count():
        if latest_blocks[0]['index'] == latests[0]['index']:
            print 'up to date, height:', latests[0]['index']
            return
        records = Mongo.db.consensus.find({'index': latests[0]['index']})
        if records.count():
            lowest = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
            for record in records:
                val = int(record['block']['hash'], 16)
                if val < lowest:
                    lowest = val
                    winning_block = record['block']
                    peer = record['peer']
            if winning_block:
                print latest_block.get('hash'), latest_block.get('index')
                print winning_block.get('prevHash'), winning_block.get('index')
                print winning_block.get('hash'), winning_block.get('index')
                if latest_block.get('hash') == winning_block.get('prevHash'):
                    # everything jives with our current history, everyone is happy
                    Mongo.db.blocks.update(winning_block, winning_block, upsert=True)
                    print 'winning block inserted at: ', winning_block.get('index')
                    latest_block = BU.get_latest_block()
                else:
                    winning_block = Block.from_dict(winning_block)
                    result = retrace(winning_block, peer)
                    if result == "peer has broken chain or response was invalid":
                        Mongo.db.consensus.remove({'peer': peer}, multi=True)
                    return
            else:
                print 'no winning block for index:', next_index
        else:
            print 'no winning block for index:', next_index
            return
    else:
        print "no records found at index:", next_index
        return

def retrace(block, peer):
    print "retracing..."
    blocks = {}
    blocks[block.index] = block
    Mongo.db.consensus.insert({
        'block': block.to_dict(),
        'index': block.to_dict().get('index'),
        'id': block.to_dict().get('id'),
        'peer': peer})
    while 1:
        try:
            # 2. if we don't, query the peer for the prevHash
            print 'getting hash:', block.prev_hash
            print 'for height:', block.index - 1
            res = Mongo.db.consensus.find({'block.hash': block.prev_hash})
            if res.count():
                block = Block.from_dict(res[0]['block'])
            else:
                res = requests.get('http://' + peer + '/get-block?hash=' + block.prev_hash)
                block = Block.from_dict(json.loads(res.content))
                Mongo.db.consensus.insert({
                    'block': block.to_dict(),
                    'index': block.to_dict().get('index'),
                    'id': block.to_dict().get('id'),
                    'peer': peer})
            blocks[block.index] = block
        except:
            # if they don't have it, throw out the chain
            return "peer has broken chain or response was invalid"

        # if they do have it, query our consensus collection for prevHash of that block, repeat 1 and 2 until index 1
        prev_blocks_check = Mongo.db.blocks.find({'hash': block.prev_hash})
        
        if prev_blocks_check.count():
            print prev_blocks_check[0]['hash'], prev_blocks_check[0]['index']
            missing_blocks = Mongo.db.blocks.find({'index': {'$lte': prev_blocks_check[0]['index']}})
            for missing_block in missing_blocks:
                blocks[missing_block['index']] = Block.from_dict(missing_block)
            # if we have it in our blockchain, then we've hit the fork point
            # now we have to loop through the current block array and build a blockchain
            # then we compare the block height and difficulty of the two chains
            # replace our current chain if necessary by removing them from the database
            # then looping though our new chain, inserting the new blocks
            existing_blockchain = Blockchain([x for x in Mongo.db.blocks.find({})])
            blockchain = Blockchain([x for i, x in blocks.iteritems()])
            # If the block height is equal, we throw out the inbound chain, it muse be greater
            # If the block height is lower, we throw it out
            # if the block height is heigher, we compare the difficulty of the entire chain
            if blockchain.get_difficulty() > existing_blockchain.get_difficulty() and \
                blockchain.get_highest_block_height() > existing_blockchain.get_highest_block_height():
                    for idx, block in blocks.items():
                        Mongo.db.blocks.remove({'index': block.index})
                        Mongo.db.blocks.insert(block.to_dict())
                    return "Replaced chain with incoming"
            else:
                return "Incoming chain lost", blockchain.get_difficulty(), existing_blockchain.get_difficulty(), blockchain.get_highest_block_height(), existing_blockchain.get_highest_block_height()
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
    import os.path
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', nargs=None, help='serve, mine, or consensus')
    parser.add_argument('config', default="config.json", nargs="?", help='config file')
    parser.add_argument('to', default="", nargs="?", help='to')
    parser.add_argument('value', default=0, nargs="?", help='amount')
    args = parser.parse_args()

    if args.mode == 'config' and args.config:
        if not os.path.isfile(args.config):
            with open(args.config, 'w+') as f:
                from utils import generate_config
                f.write(generate_config.generate())
        else:
            print '\'%s\' already exists! You must rename, move, or delete the existing file.' % args.config
        exit()

    if os.path.isfile(args.config):
        with open(args.config) as f:
            Config.from_dict(json.loads(f.read()))
    else:
        print 'no config file found at \'%s\'' % args.config
        exit()

    if args.mode == 'consensus':
        try:
            res = requests.post(
                'https://yadacoin.io/peers',
                json.dumps({
                    'host': Config.peer_host,
                    'port': Config.peer_port
                }),
                headers={
                    "Content-Type": "application/json"
                }
            )
        except:
            print 'ERROR: failed to get peers, exiting...'
            exit()
        while 1:
            Peers.init()
            if not Peers.peers:
                time.sleep(1)
                continue
            consensus()
            """
            p = Process(target=)
            p.start()
            p.join()
            """
            time.sleep(1)
    elif args.mode == 'send':
        send(args.to, float(args.value))
    elif args.mode == 'mine':
        print Config.to_json()
        while 1:
            Peers.init()
            if not Peers.peers:
                time.sleep(1)
                continue
            node()
            """
            p = Process(target=node)
            p.start()
            p.join()
            """
            time.sleep(1)
    elif args.mode == 'faucet':
        while 1:
            Peers.init()
            if not Peers.peers:
                time.sleep(1)
                continue
            faucet()
            """
            p = Process(target=faucet)
            p.start()
            p.join()
            """
            time.sleep(1)
    elif args.mode == 'serve':
        print Config.to_json()
        Peers.init()
        if not Peers.peers:
            raise Exception("peer service unavailble, restart this process")
        # wrap Flask application with engineio's middleware
        Mongo.init()
        sio = socketio.Server(async_mode='gevent')

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
                dup_check = Mongo.db.consensus.find({'id': incoming_block.signature, 'peer': peer})
                if dup_check.count():
                    return "dup"
                Mongo.db.consensus.insert({
                    'block': incoming_block.to_dict(),
                    'index': incoming_block.to_dict().get('index'),
                    'id': incoming_block.to_dict().get('id'),
                    'peer': peer})
                # before inserting, we need to check it's chain
                # search consensus for prevHash of incoming block.
                #prev_blocks_check = Mongo.db.blocks.find({'hash': incoming_block.prev_hash})
                #if prev_blocks_check.count():
                    # 1. if we have it, then insert it.
                #    Mongo.db.consensus.insert({
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
                dup_check = Mongo.db.miner_transactions.find({'id': incoming_txn.transaction_signature})
                if dup_check.count():
                    print 'found duplicate'
                    return
                Mongo.db.miner_transactions.insert(incoming_txn.to_dict())
            except Exception as e:
                print e
            except BaseException as e:
                print e

        @app.route('/get-blocks')
        def get_blocks():
            blocks = [x for x in Mongo.db.blocks.find({
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

        @app.route('/newtransaction', methods=['POST'])
        def app_newtransaction():
            newtransaction(None, request.json)
            return 'ok'

        @app.route('/getblockheight')
        def app_getblockheight():
            return json.dumps({'block_height': BU.get_latest_block().get('index')})

        @app.route('/get-block', methods=['GET'])
        def app_getblock():
            res = Mongo.db.consensus.find({'block.hash': request.args.get('hash')}, {'_id': 0})
            return json.dumps(res[0]['block'])

        app = socketio.Middleware(sio, app)
        # deploy as an eventlet WSGI server
        pywsgi.WSGIServer((Config.serve_host, Config.serve_port), app).serve_forever()