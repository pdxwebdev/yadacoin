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
from transaction import TransactionFactory, InvalidTransactionSignatureException, MissingInputTransactionException, InvalidTransactionException
from blockchain import Blockchain
from bitcoin.wallet import P2PKHBitcoinAddress




try:
    f = open('block_rewards.json', 'r')
    BU.block_rewards = json.loads(f.read())
    f.close()
except:
    raise BaseException("Block reward file not found")

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

def node(config, peers):
    from pymongo import MongoClient
    mongo_client = MongoClient()
    db = mongo_client.yadacoin
    collection = db.blocks
    BU.collection = collection
    Block.collection = collection
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
    if not block:
        genesis_block = Block.from_dict({
            "nonce" : 8153,
            "index" : 0,
            "hash" : "000dcccd6beb576cadebf0bab1f53c0b75f0d85d6b4ebfae24d7640a703c1856",
            "transactions" : [ 
                {
                    "public_key" : "037349fe3a9fc5d13dae523baaa83a05856018d2b0df769a8047c4692c53eb5cc1",
                    "inputs" : [],
                    "fee" : "0.1",
                    "hash" : "300d98126fbbba7354a6c1d0060398c292b5ec314c636f74c8edc5291e7674a8",
                    "relationship" : "",
                    "outputs" : [ 
                        {
                            "to" : "14opV2ZB6uuzzYPQZhWFewo9oF7RM6pJeQ",
                            "value" : 50.0000000000000000
                        }
                    ],
                    "rid" : "",
                    "id" : "HwigxNWHeG0n6bVQXog3t62VlLJ/ilhkP1m19y/z18d3QqVrDxeVo1bZQd3jG1C2+GZ7LGbFsz2ekRJyv6KPF2A="
                }
            ],
            "public_key" : "037349fe3a9fc5d13dae523baaa83a05856018d2b0df769a8047c4692c53eb5cc1",
            "prevHash" : "",
            "id" : "INFWIvJ18Ez1TH6841bUv8T+BBNUhYXIb/3X6LyhmLE2dTXqbSG/7cTeR1MCNMCMRFSOBwnZhHQymUKhsqcOSQ0=",
            "merkleRoot" : "0d069b93dcbb5cb8a2ad61db32bbcef16719c4380a65d79c1aa27982a12f21d4"
        })
        genesis_block.save()
        block = BU.get_latest_block()

    latest_block_index = Value('i', int(block['index']))
    p = Process(target=new_block_checker, args=(latest_block_index,))

    status = Array('c', 'asldkjf')
    p.start()

    start = time.time()

    dup_test = db.consensus.find({'peer': 'me', 'index': int(latest_block_index.value) + 1})
    pending_txns = db.miner_transactions.find()
    if not dup_test.count():
        transactions = db.miner_transactions.find()
        transaction_objs = []
        unspent_indexed = {}
        for txn in transactions:
            try:
                transaction = Transaction.from_dict(txn)
                transaction.verify()
                #check double spend
                address = str(P2PKHBitcoinAddress.from_pubkey(transaction.public_key.decode('hex')))
                if address in unspent_indexed:
                    unspent_ids = unspent_indexed[address]
                else:
                    res = BU.get_wallet_unspent_transactions(address)
                    unspent_ids = [x['id'] for x in res]
                    unspent_indexed[address] = unspent_ids
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
            except InvalidTransactionException as e:
                print 'InvalidTransactionException: transaction removed'
                db.miner_transactions.remove({'id': transaction.transaction_signature})
            except Exception as e:
                print e
                print 'rejected transaction', txn['id']
        print 'starting to mine...'
        try:
            block = BlockFactory.mine(transaction_objs, coinbase, difficulty, public_key, private_key, output, latest_block_index, status)
        except Exception as e:
            raise e
        if block:
            dup_test = db.consensus.find({'peer': 'me', 'index': block.index})
            if not dup_test.count():
                print 'candidate submitted', block.transactions, block.index
                db.consensus.insert({'peer': 'me', 'index': block.index, 'id': block.signature, 'block': block.to_dict()})
                for peer in peers:
                    try:
                        requests.post(
                            'http://{peer}:8000/newblock'.format(
                                peer=peer['ip']
                            ),
                            json=block.to_dict(),
                            timeout=1,
                            headers={'Connection':'close'}
                        )
                        print 'successfully sent block'
                    except Exception as e:
                        print e
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
    p.terminate()
