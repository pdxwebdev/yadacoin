import argparse
import hashlib
import json
import requests
import time
import re
import itertools
import sys
from uuid import uuid4
from multiprocessing import Process, Value, Array
from socketIO_client import SocketIO, BaseNamespace
from ecdsa import SigningKey, SECP256k1
from block import Block, BlockFactory
from transaction import Transaction, Input, Output
from blockchainutils import BU
from transactionutils import TU
from transaction import TransactionFactory
from pymongo import MongoClient
from blockchain import Blockchain


mongo_client = MongoClient()
db = mongo_client.yadacoin
collection = db.blocks
BU.collection = collection
Block.collection = collection

class ChatNamespace(BaseNamespace):
    def on_reply(self, *args):
        print 'on_chat_response', args

    def on_getblocksreply(self, *args):
        blocks = []
        for block_dict in args[0]:
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

    def on_newtransaction(sid, *args):
        print("new transaction ", args[0])
        try:
            incoming_txn = Transaction.from_dict(args[0])
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

    def on_getblocks(self, *args):
        print("getblocks ")
        self.emit('getblocksreply', [x for x in BU.get_blocks()])

    def on_error(self, event, *args):
        print 'error'

def verify_block(block):
    pass

spinner = itertools.cycle(['-', '/', '|', '\\'])
def output():
    sys.stdout.write(spinner.next())  # write the next character
    sys.stdout.flush()                # flush stdout buffer (actual character display)
    sys.stdout.write('\b')            # erase the last written char

def verify_transaction(transaction):
    signature = transaction.signature

def new_block_checker(current_index):
    while 1:
        try:
            current_index.value = BU.get_latest_block().get('index')
        except:
            pass
        time.sleep(1)

def get_peers(peer_pool):
    with open('peers.json') as f:
        peers = json.loads(f.read())
    for peer in peers:
        try:
            socketIO = SocketIO(peer['ip'], 8000, wait_for_connection=False)
            chat_namespace = socketIO.define(ChatNamespace, '/chat')
            chat_namespace.emit('getblocks')
            socketIO.wait(seconds=1)
            peer_pool.append(chat_namespace)
        except Exception as e:
            raise e

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('runtype',
                    help='If you want to mine blocks')
    parser.add_argument('--conf',
                    help='set your config file')
    args = parser.parse_args()

    with open(args.conf) as f:
        config = json.loads(f.read())

    public_key = config.get('public_key')
    private_key = config.get('private_key')
    TU.private_key = private_key
    BU.private_key = private_key

    # default run state will be to mine some blocks!

    # proof of work time!
    coinbase = config.get('coinbase')

    blocks = BU.get_block_objs()  # verifies as the blocks are created so no need to call block.verify() on each block
    blockchain = Blockchain(blocks)
    blockchain.verify()
    if len(blocks):
        difficulty = re.search(r'^[0]+', blocks[-1].hash).group(0)
    else:
        difficulty = '000'
    print '//// YADA COIN MINER ////'
    print "Welcome!! Mining beginning with difficulty of:", difficulty
    if args.runtype == 'node':
        peer_pool = []
        chat_namespace = get_peers(peer_pool)
        print len(peer_pool), 'peers'
        block = BU.get_latest_block()
        if block:
            latest_block_index = Value('i', int(block['index']))
        else:
            latest_block_index = Value('i', 0)
        p = Process(target=new_block_checker, args=(latest_block_index,))
        p.start()
        while 1:
            try:
                with open('miner_transactions.json', 'r') as f:
                    transactions_parsed = json.loads(f.read())
            except:
                with open('miner_transactions.json', 'w') as f:
                    f.write('[]')
                    transactions_parsed = []

            with open('miner_transactions.json', 'r+') as f:
                if transactions_parsed:
                    f.seek(0)
                    f.write('[]')
                    f.truncate()
                transactions = []
                rejected = []
                for txn in transactions_parsed:
                    transaction = Transaction.from_dict(txn)
                    try:
                        transaction.verify()
                        transactions.append(transaction)
                    except:
                        rejected.append(txn)
                f.write(json.dumps(rejected))

            start = time.time()
            status = Array('c', 'asldkjf')
            p2 = Process(target=BlockFactory.mine, args=(transactions, coinbase, difficulty, public_key, private_key, output, latest_block_index, status))
            p2.start()
            p2.join()
            # check for more peers to add to peer_pool
            block = BU.get_latest_block()
            for peer in peer_pool:
                peer.emit('new block', block)
                peer.disconnect()
            peer_pool = []
            chat_namespace = get_peers(peer_pool)
            if status.value == 'mined':
                print 'block discovered: {nonce:', str(block['nonce']) + ',', 'hash: ', block['hash'] + '}'
                if time.time() - start < 30:
                    difficulty = difficulty + '0'
                elif time.time() - start > 60:
                    difficulty = difficulty[:-1]
                else:
                    difficulty = difficulty
            else:
                print 'block chain updated, restarting mining from latest block'
                difficulty = re.search(r'^[0]+', block['hash']).group(0)

            blocks = BU.get_block_objs()

    elif args.runtype == 'block_getter':
        pass