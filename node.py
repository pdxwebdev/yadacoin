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
    latest_block_index = Value('i', 0)
    my_peer = config.get('peer')
    p = Process(target=new_block_checker, args=(latest_block_index,))
    status = Array('c', 'asldkjf')
    p.start()
    from pymongo import MongoClient
    mongo_client = MongoClient('localhost')
    db = mongo_client[config.get('database')]
    collection = db.blocks
    BU.database = config.get('database')
    BU.collection = collection
    Block.collection = collection
    public_key = config.get('public_key')
    private_key = config.get('private_key')
    TU.private_key = private_key
    BU.private_key = private_key
    # default run state will be to mine some blocks!


    # proof of work time!
    coinbase = config.get('coinbase')
    difficulty = '0000'


    print '\r\n\r\n\r\n//// YADA COIN MINER ////'
    print "Welcome!! Mining beginning with difficulty of:", difficulty
    block = BU.get_latest_block()
    if not block:
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
        block = BU.get_latest_block()

    latest_block_index.value = block.get('index')
    start = time.time()

    dup_test = db.consensus.find({'peer': 'me', 'index': BU.get_latest_block().get('index') + 1})

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
                    db.failed_transactions.insert({'reason': 'input presumably spent already', 'txn': transaction.to_dict()})
                elif failed2:
                    db.miner_transactions.remove({'id': transaction.transaction_signature})
                    print 'transaction removed: using an input used by another transaction in this block', transaction.transaction_signature
                    db.failed_transactions.insert({'reason': 'using an input used by another transaction in this block', 'txn': transaction.to_dict()})
                else:
                    transaction_objs.append(transaction)
            except MissingInputTransactionException as e:
                print 'missing this input transaction, will try again later'
            except InvalidTransactionSignatureException as e:
                print 'InvalidTransactionSignatureException: transaction removed'
                db.miner_transactions.remove({'id': transaction.transaction_signature})
                db.failed_transactions.insert({'reason': 'InvalidTransactionSignatureException', 'txn': transaction.to_dict()})
            except InvalidTransactionException as e:
                print 'InvalidTransactionException: transaction removed'
                db.miner_transactions.remove({'id': transaction.transaction_signature})
                db.failed_transactions.insert({'reason': 'InvalidTransactionException', 'txn': transaction.to_dict()})
            except Exception as e:
                print e
                print 'rejected transaction', txn['id']
            except BaseException as e:
                print e
                print 'rejected transaction', txn['id']
        print '\r\nStarting to mine...'
        try:
            block = BlockFactory.mine(transaction_objs, coinbase, difficulty, public_key, private_key, output, latest_block_index, status)
        except Exception as e:
            raise e
        if block:
            dup_test = db.consensus.find({'peer': 'me', 'index': block.index})
            if not dup_test.count():
                print '\r\nCandidate submitted for index:', block.index
                print '\r\nTransactions:'
                for x in block.transactions:
                    print x.transaction_signature 
                db.consensus.insert({'peer': 'me', 'index': block.index, 'id': block.signature, 'block': block.to_dict()})
                print '\r\nSent block to:'
                for peer in peers:
                    try:
                        block_dict = block.to_dict()
                        block_dict['peer'] = my_peer
                        requests.post(
                            'http://{peer}/newblock'.format(
                                peer=peer['host'] + ":" + peer['port']
                            ),
                            json=block_dict,
                            timeout=3,
                            headers={'Connection':'close'}
                        )
                        print peer['host'] + ":" + peer['port']
                    except Exception as e:
                        print e
        else:
            print 'greatest block height changed during mining'

        if time.time() - start < 60:
            difficulty = difficulty + '0'
        elif time.time() - start > 90:
            difficulty = difficulty[:-1]
        else:
            difficulty = re.search(r'^[0]+', BU.get_latest_block().get('hash')).group(0)

    p.terminate()
