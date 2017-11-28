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


mongo_client = MongoClient()
db = mongo_client.yadacointest
BU.collection = db.blocks
Block.collection = db.blocks

class ChatNamespace(BaseNamespace):
    def on_reply(self, *args):
        print 'on_chat_response', args

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
            current_index.value = BU.get_latest_block()[0]['index']
        except:
            pass
        time.sleep(1)

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
    if len(blocks):
        difficulty = re.search(r'^[0]+', blocks[-1].hash).group(0)
    else:
        difficulty = '000'
    print '//// YADA COIN MINER ////'
    print "Welcome!! Mining beginning with difficulty of:", difficulty
    if args.runtype == 'node':
        with open('peers.json') as f:
            peers = json.loads(f.read())

        for peer in peers:
            socketIO = SocketIO(peer['ip'], 8000)
            chat_namespace = socketIO.define(ChatNamespace, '/chat')

        block = BU.get_latest_block()
        if block.count():
            latest_block_index = Value('i', int(block[0]['index']))
        else:
            latest_block_index = Value('i', 0)
        p = Process(target=new_block_checker, args=(latest_block_index,))
        p.start()
        while 1:
            try:
                open('miner_transactions.json', 'r')
            except:
                f = open('miner_transactions.json', 'w+')
                f.write('{}')
                f.close()

            with open('miner_transactions.json', 'r+') as f:
                transactions_parsed = json.loads(f.read())
                if transactions_parsed:
                    f.seek(0)
                    f.write('[]')
                    f.truncate()
                transactions = []
                for txn in transactions_parsed:
                    transaction = Transaction.from_dict(txn)
                    transactions.append(transaction)

            start = time.time()
            status = Array('c', 'asldkjf')
            p2 = Process(target=BlockFactory.mine, args=(transactions, coinbase, difficulty, public_key, private_key, output, latest_block_index, status))
            p2.start()
            p2.join()

            block = BU.get_latest_block()[0]
            chat_namespace.emit('chat message', block)
            if status.value == 'mined':
                print 'block discovered: {nonce:', str(block['nonce']) + ',', 'hash: ', block['hash'] + '}'
                if time.time() - start < 60:
                    difficulty = difficulty + '0'
                elif time.time() - start > 240:
                    difficulty = difficulty[:-1]
                else:
                    difficulty = difficulty
            else:
                print 'block chain updated, restarting mining from latest block'
                difficulty = re.search(r'^[0]+', block['hash']).group(0)

            blocks = BU.get_block_objs()

    elif args.runtype == 'block_getter':
        pass