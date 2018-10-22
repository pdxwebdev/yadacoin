import socketio
import socket
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
import endpoints
import multiprocessing
from sys import exit
from multiprocessing import Process, Value, Array, Pool
from socketIO_client import SocketIO, BaseNamespace
from flask import Flask, render_template, request, Response
from flask_cors import CORS
from yadacoin import TransactionFactory, Transaction, \
                    MissingInputTransactionException, \
                    Input, Output, Block, Config, Peers, \
                    Blockchain, BlockChainException, TU, BU, \
                    Mongo, BlockFactory, NotEnoughMoneyException, Peer
from node import MiningPool
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from gevent import pywsgi
from miniupnpc import UPnP


class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

def output(string):
    sys.stdout.write(string)  # write the next character
    sys.stdout.flush()                # flush stdout buffer (actual character display)
    sys.stdout.write(''.join(['\b' for i in range(len(string))])) # erase the last written char

def signal_handler(signal, frame):
        print('Closing... Or use ctrl + \\')
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
class BadPeerException(Exception):
    pass

class AboveTargetException(Exception):
    pass

class ForkException(Exception):
    pass

class Consensus():
    lowest = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    def __init__(self):
        Mongo.init()
        latest_block = BU.get_latest_block()
        if latest_block:
            self.latest_block = Block.from_dict(latest_block)
        else:
            self.insert_genesis()
        self.existing_blockchain = Blockchain([x for x in Mongo.db.blocks.find({})])

    def log(self, message):
        print message

    def insert_genesis(self):
        #insert genesis if it doesn't exist
        genesis_block = BlockFactory.get_genesis_block()
        genesis_block.save()
        Mongo.db.consensus.update({
            'block': genesis_block.to_dict(),
            'peer': 'me',
            'id': genesis_block.signature,
            'index': 0
        },
        {
            'block': genesis_block.to_dict(),
            'peer': 'me',
            'id': genesis_block.signature,
            'index': 0
        },
        upsert=True)
        self.latest_block = genesis_block

    def verify_existing_blockchain(self):
        self.log('verifying existing blockchain')
        result = self.existing_blockchain.verify(output)
        if not result['verified']:
            Mongo.db.blocks.remove({"index": {"$gt": result['last_good_block'].index}}, multi=True)

    def remove_pending_transactions_now_in_chain(self):
        #remove transactions from miner_transactions collection in the blockchain
        data = Mongo.db.miner_transactions.find({}, {'_id': 0})
        for txn in data:
            res = Mongo.db.blocks.find({"transactions.id": txn['id']})
            if res.count():
                Mongo.db.miner_transactions.remove({'id': txn['id']})

    def get_latest_consensus_blocks(self):
        for x in Mongo.db.consensus.find({}, {'_id': 0}).sort([('index', -1)]):
            if BU.get_version_for_height(x['block']['index']) == int(x['block']['version']):
                yield x

    def get_latest_consensus_block(self):
        latests = self.get_latest_consensus_blocks()
        for latest in latests:
            if int(latest['block']['version']) == BU.get_version_for_height(latest['block']['index']):
                return Block.from_dict(latest['block'])

    def get_consensus_blocks_by_index(self, index):
        return Mongo.db.consensus.find({'index': index, 'block.prevHash': {'$ne': ''}, 'block.version': BU.get_version_for_height(index)}, {'_id': 0})

    def get_consensus_block_by_index(self, index):
        return self.get_consensus_blocks_by_index(index).limit(1)[0]

    def rank_consenesus_blocks(self):
        # rank is based on target, total chain difficulty, and chain validity
        records = self.get_consensus_blocks_by_index(self.latest_block.index + 1)
        lowest = self.lowest

        ranks = []
        for record in records:
            peer = Peer.from_string(record['peer'])
            block = Block.from_dict(record['block'])
            target = int(record['block']['hash'], 16)
            if target < lowest:
                ranks.append({
                    'target': target,
                    'block': block,
                    'peer': peer
                })
        return sorted(ranks, key=lambda x: x['target'])

    def get_previous_consensus_block_from_local(self, block, peer):
        #table cleanup
        new_block = Mongo.db.consensus.find_one({
            'block.hash': block.prev_hash,
            'block.index': (block.index - 1),
            'block.version': BU.get_version_for_height((block.index - 1))
        })
        if new_block:
            new_block = Block.from_dict(new_block['block'])
            if int(new_block.version) == BU.get_version_for_height(new_block.index):
                return new_block
            else:
                return None
        return None

    def get_previous_consensus_block_from_remote(self, block, peer):
        try:
            url = 'http://' + peer.to_string() + '/get-block?hash=' + block.prev_hash
            print 'getting block', url
            res = requests.get(url, timeout=3)
        except:
            raise BadPeerException()
        try:
            print 'response code: ', res.status_code
            new_block = Block.from_dict(json.loads(res.content))
            if int(new_block.version) == BU.get_version_for_height(new_block.index):
                return new_block
            else:
                return None
        except:
            return None

    def insert_consensus_block(self, block, peer):
        Mongo.db.consensus.update({
            'id': block.to_dict().get('id'),
            'peer': peer.to_string()
        },
        {
            'block': block.to_dict(),
            'index': block.to_dict().get('index'),
            'id': block.to_dict().get('id'),
            'peer': peer.to_string()
        }, upsert=True)

    def sync_bottom_up(self):
        #bottom up syncing

        self.latest_block = Block.from_dict(BU.get_latest_block())
        self.remove_pending_transactions_now_in_chain()

        latest_consensus = Mongo.db.consensus.find_one({'index': self.latest_block.index + 1})
        if latest_consensus:
            latest_consensus = Block.from_dict(latest_consensus['block'])
            print latest_consensus.index, "latest consensus_block"

            records = Mongo.db.consensus.find({'index': self.latest_block.index + 1, 'block.version': BU.get_version_for_height(self.latest_block.index + 1)})
            for record in sorted(records, key=lambda x: int(x['block']['target'], 16)):
                self.import_block(record)
        else:
            self.log('up to date, height: ' + str(self.latest_block.index))
            return

    def sync_top_down(self):
        #top down syncing

        self.latest_block = Block.from_dict(BU.get_latest_block())
        self.remove_pending_transactions_now_in_chain()

        latest_consensus = Mongo.db.consensus.find_one({}, sort=[('index', -1)])
        if latest_consensus:
            latest_consensus = Block.from_dict(latest_consensus['block'])
            if self.latest_block.index == latest_consensus.index:
                self.log('up to date, height: ' + str(self.latest_block.index))
                return
            print latest_consensus.index, "latest consensus_block"

            records = Mongo.db.consensus.find({'index': latest_consensus.index, 'block.version': BU.get_version_for_height(latest_consensus.index)})
            for record in sorted(records, key=lambda x: int(x['block']['target'], 16)):
                self.import_block(record)
        else:
            self.log('up to date, height: ' + str(self.latest_block.index))
            return

    def import_block(self, block_data):
        block = Block.from_dict(block_data['block'])
        peer = Peer.from_string(block_data['peer'])
        print self.latest_block.hash, block.prev_hash, self.latest_block.index, (block.index - 1)
        try:
            self.integrate_block_with_existing_chain(block, self.existing_blockchain)
        except AboveTargetException as e:
            pass
        except ForkException as e:
            self.retrace(block, peer)
        except IndexError as e:
            self.retrace(block, peer)

    def integrate_block_with_existing_chain(self, block, blockchain):
        if block.index == 0:
            return True
        height = block.index
        last_block = blockchain.blocks[block.index - 1]
        if not last_block:
            raise ForkException()
        last_time = last_block.time
        target = BlockFactory.get_target(height, last_time, last_block, blockchain)
        if int(block.hash, 16) < target or block.special_min:
            if last_block.index == (block.index - 1) and last_block.hash == block.prev_hash:
                dup = Mongo.db.blocks.find_one({'index': block.index, 'hash': block.hash})
                if not dup:
                    Mongo.db.blocks.update({'index': block.index}, block.to_dict(), upsert=True)
                    print "New block inserted for height: ", block.index
                return True
            else:
                raise ForkException()
        else:
            raise AboveTargetException()
        return False

    def retrace(self, block, peer):
        self.log("retracing...")
        blocks = []
        blocks.append(block)
        while 1:
            self.log(block.hash)
            self.log(block.index)
            # get the previous block from either the consensus collection in mongo
            # or attempt to get the block from the remote peer
            previous_consensus_block = self.get_previous_consensus_block_from_local(block, peer)
            if previous_consensus_block:
                    block = previous_consensus_block
                    blocks.append(block)
            else:
                if peer.is_me:
                    Mongo.db.consensus.remove({'peer': peer.to_string(), 'index': {'$gte': block.index}}, multi=True)
                    return
                try:
                    previous_consensus_block = self.get_previous_consensus_block_from_remote(block, peer)
                except BadPeerException as e:
                    Mongo.db.consensus.remove({'peer': peer.to_string(), 'index': {'$gte': block.index}}, multi=True)
                except:
                    pass
                if previous_consensus_block and previous_consensus_block.index + 1 == block.index:
                    block = previous_consensus_block
                    blocks.append(block)
                    self.insert_consensus_block(block, peer)
                else:
                    # identify missing and prune
                    # if the pruned chain is still longer, we'll take it
                    if previous_consensus_block:
                        block = previous_consensus_block
                        blocks = [block]
                    else:
                        return

            print 'attempting sync at', block.prev_hash
            # if they do have it, query our consensus collection for prevHash of that block, repeat 1 and 2 until index 1
            prev_blocks_check = Mongo.db.blocks.find_one({'hash': block.prev_hash, 'index': block.index - 1})

            if prev_blocks_check:
                prev_blocks_check = Block.from_dict(prev_blocks_check)
                print prev_blocks_check.hash, prev_blocks_check.index
                missing_blocks = Mongo.db.blocks.find({'index': {'$lte': prev_blocks_check.index}})
                complete_incoming_chain = blocks[:]
                for missing_block in missing_blocks:
                    complete_incoming_chain.append(Block.from_dict(missing_block))
                # if we have it in our blockchain, then we've hit the fork point
                # now we have to loop through the current block array and build a blockchain
                # then we compare the block height and difficulty of the two chains
                # replace our current chain if necessary by removing them from the database
                # then looping though our new chain, inserting the new blocks
                self.existing_blockchain = Blockchain([x for x in Mongo.db.blocks.find({})])
                blockchain = Blockchain([x for x in complete_incoming_chain])

                # If the block height is equal, we throw out the inbound chain, it muse be greater
                # If the block height is lower, we throw it out
                # if the block height is heigher, we compare the difficulty of the entire chain

                inbound_difficulty = blockchain.get_difficulty()

                existing_difficulty = self.existing_blockchain.get_difficulty()

                if blockchain.get_highest_block_height() > self.existing_blockchain.get_highest_block_height() \
                    and inbound_difficulty > existing_difficulty:
                    for block in sorted(blockchain.blocks, key=lambda x: x.index):
                        try:
                            if block.index == 0:
                                continue
                            self.integrate_block_with_existing_chain(block, blockchain)
                        except ForkException as e:
                            return
                        except AboveTargetException as e:
                            return
                    print "Replaced chain with incoming"
                    return
                else:
                    print "Incoming chain lost", blockchain.get_difficulty(), self.existing_blockchain.get_difficulty(), blockchain.get_highest_block_height(), self.existing_blockchain.get_highest_block_height()
                    for block in blocks:
                        Mongo.db.consensus.remove({'block.hash': block.hash}, multi=True)
                    return
            # lets go down the hash path to see where prevHash is in our blockchain, hopefully before the genesis block
            # we need some way of making sure we have all previous blocks until we hit a block with prevHash in our main blockchain
            #there is no else, we just loop again
            # if we get to index 1 and prev hash doesn't match the genesis, throw out the chain and black list the peer
            # if we get a fork point, prevHash is found in our consensus or genesis, then we compare the current
            # blockchain against the proposed chain. 
            if block.index == 0:
                print "zero index reached"
                return
        print "doesn't follow any known chain" # throwing out the block for now
        return

if __name__ == '__main__':
    multiprocessing.freeze_support()
    import argparse
    import os.path
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', nargs=None, help='serve, mine, or consensus')
    parser.add_argument('config', default="config.json", nargs="?", help='config file')
    parser.add_argument('to', default="", nargs="?", help='to')
    parser.add_argument('value', default=0, nargs="?", help='amount')
    parser.add_argument('-c', '--cores', default=multiprocessing.cpu_count(), help='Specify number of cores to use')
    parser.add_argument('-p', '--pool', default='', help='Specify pool to use')
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
        Peers.init()
        consensus = Consensus()
        consensus.verify_existing_blockchain()
        while 1:
            consensus.sync_top_down()
            consensus.sync_bottom_up()
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
        print '\r\n\r\n\r\n//// YADA COIN MINER ////'
        print "Core count:", args.cores
        def get_mine_data():
            print "http://{pool}/pool".format(pool=args.pool)
            return json.loads(requests.get("http://{pool}/pool".format(pool=args.pool)).content)
        running_processes = []
        Mongo.init()
        while 1:
            Peers.init()
            if not Peers.peers:
                time.sleep(1)
                continue
            if len(running_processes) >= int(args.cores):
                for i, proc in enumerate(running_processes):
                    if not proc.is_alive():
                        proc.terminate()
                        data = get_mine_data()
                        p = Process(target=MiningPool.pool_mine, args=(args.pool, data['header'], data['target'], data['nonces'], data['special_min']))
                        p.start()
                        running_processes[i] = p
            else:
                data = get_mine_data()
                p = Process(target=MiningPool.pool_mine, args=(args.pool, data['header'], data['target'], data['nonces'], data['special_min']))
                p.start()
                running_processes.append(p)
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

        app = Flask(__name__)
        app.debug = True
        app.secret_key = '23ljk2l9a08sd7f09as87df09as87df3k4j'
        CORS(app)
        sio = socketio.Server(async_mode='gevent')

        @sio.on('newblock', namespace='/chat')
        def newblock(data):
            #print("new block ", data)
            try:
                peer = Peer.from_string(request.json.get('peer'))
                block = Block.from_dict(data)
                if block.index == 0:
                    return
                if int(block.version) != BU.get_version_for_height(block.index):
                    print 'rejected old version %s from %s' % (block.version, peer)
                    return
                Mongo.db.consensus.update({
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
                print "block is bad"
                print e
            except BaseException as e:
                print "block is bad"
                print e
            try:
                requests.post(
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
                Mongo.db.miner_transactions.update(incoming_txn.to_dict(), incoming_txn.to_dict(), upsert=True)
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
            return json.dumps(Mongo.db.blocks.find_one({'hash': request.args.get('hash')}, {'_id': 0}))

        def get_base_graph():
            bulletin_secret = request.args.get('bulletin_secret').replace(' ', '+')
            graph = Graph(bulletin_secret, wallet_mode=True)
            return graph
        endpoints.BaseGraphView.get_base_graph = get_base_graph

        app.add_url_rule('/transaction', view_func=endpoints.TransactionView.as_view('transaction'), methods=['GET', 'POST'])
        app.add_url_rule('/get-graph-info', view_func=endpoints.GraphView.as_view('graph'), methods=['GET', 'POST'])
        app.add_url_rule('/get-graph-sent-friend-requests', view_func=endpoints.GraphSentFriendRequestsView.as_view('graphsentfriendrequests'), methods=['GET', 'POST'])
        app.add_url_rule('/get-graph-friend-requests', view_func=endpoints.GraphFriendRequestsView.as_view('graphfriendrequests'), methods=['GET', 'POST'])
        app.add_url_rule('/get-graph-friends', view_func=endpoints.GraphFriendsView.as_view('graphfriends'), methods=['GET', 'POST'])
        app.add_url_rule('/get-graph-posts', view_func=endpoints.GraphPostsView.as_view('graphposts'), methods=['GET', 'POST'])
        app.add_url_rule('/get-graph-messages', view_func=endpoints.GraphMessagesView.as_view('graphmessages'), methods=['GET', 'POST'])
        app.add_url_rule('/get-graph-new-messages', view_func=endpoints.GraphNewMessagesView.as_view('graphnewmessages'), methods=['GET', 'POST'])
        app.add_url_rule('/wallet', view_func=endpoints.WalletView.as_view('wallet'))
        app.add_url_rule('/faucet', view_func=endpoints.FaucetView.as_view('faucet'))
        app.add_url_rule('/pool', view_func=endpoints.MiningPoolView.as_view('pool'))
        app.add_url_rule('/pool-submit', view_func=endpoints.MiningPoolSubmitView.as_view('poolsubmit'), methods=['GET', 'POST'])

        app = socketio.Middleware(sio, app)
        # deploy as an eventlet WSGI server
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((Config.serve_host, 0))
            server_port = sock.getsockname()[1]
            sock.close()
            eport = server_port
            u = UPnP(None, None, 200, 0)
            u.discover()
            u.selectigd()
            r = u.getspecificportmapping(eport, 'TCP')
            while r != None and eport < 65536:
                eport = eport + 1
                r = u.getspecificportmapping(eport, 'TCP')
            b = u.addportmapping(eport, 'TCP', u.lanaddr, server_port, 'UPnP YadaCoin Serve port %u' % eport, '')
            Config.serve_host = '0.0.0.0'
            Config.serve_port = server_port
            Config.peer_host = u.externalipaddress()
            Config.peer_port = server_port
        except:
            Config.serve_host = Config.serve_host
            Config.serve_port = Config.serve_port
            Config.peer_host = Config.peer_host
            Config.peer_port = Config.peer_port
            print 'UPnP failed: you must forward and/or whitelist port', Config.peer_port

        peer = Config.peer_host + ":" + str(Config.peer_port)
        print peer
        
        Mongo.init()
        Mongo.db.config.update({'mypeer': {"$ne": ""}}, {'mypeer': peer}, upsert=True)
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

        Peers.init()
        if not Peers.peers:
            raise Exception("peer service unavailble, restart this process")
        pywsgi.WSGIServer((Config.serve_host, Config.serve_port), app).serve_forever()