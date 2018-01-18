import argparse
import hashlib
import json
import requests
import time
import re
import itertools
import sys
from uuid import uuid4
from multiprocessing import Process, Value, Array, Pool
from ecdsa import SigningKey, SECP256k1
from socketIO_client import SocketIO, BaseNamespace
from requests.exceptions import ConnectionError
from block import Block, BlockFactory
from transaction import Transaction, Input, Output
from blockchainutils import BU
from transactionutils import TU
from transaction import TransactionFactory, InvalidTransactionSignatureException, MissingInputTransactionException
from pymongo import MongoClient
from blockchain import Blockchain
from bitcoin.wallet import P2PKHBitcoinAddress


mongo_client = MongoClient()
db = mongo_client.yadacoin
collection = db.blocks
BU.collection = collection
Block.collection = collection

def verify_block(block):
    pass

spinner = itertools.cycle(['-', '/', '|', '\\'])
def output(current_index):
    string = spinner.next() + ' block height: ' + str(current_index+1)
    sys.stdout.write(string)  # write the next character
    sys.stdout.flush()                # flush stdout buffer (actual character display)
    sys.stdout.write(''.join(['\b' for i in range(len(string))])) # erase the last written char

def verify_transaction(transaction):
    signature = transaction.signature

def new_block_checker(current_index):
    while 1:
        try:
            current_index.value = BU.get_latest_block().get('index')
        except:
            pass
        time.sleep(1)

class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

def node(config):
    public_key = config.get('public_key')
    private_key = config.get('private_key')
    TU.private_key = private_key
    BU.private_key = private_key

    # default run state will be to mine some blocks!

    # proof of work time!
    coinbase = config.get('coinbase')

    blocks = BU.get_block_objs()  # verifies as the blocks are created so no need to call block.verify() on each block

    if len(blocks):
        difficulty = '000'
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

        start = time.time()
        status = Array('c', 'asldkjf')

        dup_test = db.consensus.find({'peer': 'me', 'index': int(latest_block_index.value) + 1})
        if not dup_test.count():
            transactions = db.miner_transactions.find()
            transaction_objs = []
            for txn in transactions:
                try:
                    transaction = Transaction.from_dict(txn)
                    transaction.verify()
                    #check double spend
                    res = BU.get_wallet_unspent_transactions(str(P2PKHBitcoinAddress.from_pubkey(transaction.public_key.decode('hex'))))
                    unspent_ids = [x['id'] for x in res]
                    failed1 = False
                    failed2 = False
                    used_ids_in_this_txn = []
                    for x in transaction.inputs:
                        if x.id not in unspent_ids:
                            failed1 = True
                        if x.id in used_ids_in_this_txn:
                            failed2 = True
                        used_ids_in_this_txn.append(x.id)
                    if failed1:
                        db.miner_transactions.remove({'id': transaction.transaction_signature})
                        print 'transaction removed: input presumably spent already, not in unspent outputs', transaction.transaction_signature
                    elif failed2:
                        db.miner_transactions.remove({'id': transaction.transaction_signature})
                        print 'transaction removed: using an input used by another transaction in this block', transaction.transaction_signature
                    else:
                        transaction_objs.append(transaction)
                except MissingInputTransactionException as e:
                    print 'missing this input transaction, will try again later'
                except InvalidTransactionSignatureException as e:
                    print 'InvalidTransactionSignatureException: transaction removed'
                    db.miner_transactions.remove({'id': transaction.transaction_signature})
                except Exception as e:
                    print e
                    print 'rejected transaction', txn['id']
            print 'starting to mine...'
            block = BlockFactory.mine(transaction_objs, coinbase, difficulty, public_key, private_key, output, latest_block_index, status)

            if block:
                print 'candidate submitted', block.transactions, block.index
                db.consensus.insert({'peer': 'me', 'index': block.index, 'id': block.signature, 'block': block.to_dict()})
            else:
                print 'greatest block height changed during mining'

        """
        if time.time() - start < 10:
            difficulty = difficulty + '0'
        elif time.time() - start > 20:
            difficulty = difficulty[:-1]
        else:
            difficulty = re.search(r'^[0]+', BU.get_latest_block().get('hash')).group(0)
        """
