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

def node(config):
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

        BlockFactory.mine(transactions, coinbase, difficulty, public_key, private_key, output, latest_block_index, status)
        if start - time.time() < 60:
            difficulty = difficulty + '0'
        else:
            difficulty = re.search(r'^[0]+', BU.get_latest_block().get('hash')).group(0)
