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
from yadacoin import Block, BlockFactory, Transaction, Input, Output, \
                     BU, TU, TransactionFactory, InvalidTransactionSignatureException, \
                     MissingInputTransactionException, InvalidTransactionException, \
                     Blockchain, Config, Peers, Mongo
from bitcoin.wallet import P2PKHBitcoinAddress


def verify_block(block):
    pass

spinner = itertools.cycle(['-', '/', '|', '\\'])
def output(current_index, iteration, test_int, target):
    string = spinner.next() + ' nonce: ' + str(iteration) + ' target: ' + hex(target) + ' hash: ' + str(test_int)
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

def node(nonces=None):
    latest_block_index = Value('i', 0)
    my_peer = Config.peer_host + ":" + str(Config.peer_port)
    Config.max_duration = 300000
    Config.block_version = 1
    #p = Process(target=new_block_checker, args=(latest_block_index,))
    status = Array('c', 'asldkjf')
    #p.start()
    Mongo.init()
    # default run state will be to mine some blocks!
    block = BU.get_latest_block()
    if block:
        latest_block_index.value = block.get('index') + 1
    else:
        genesis_block = BlockFactory.get_genesis_block()
        genesis_block.save()
        Mongo.db.consensus.insert({
            'block': genesis_block.to_dict(),
            'peer': 'me',
            'id': genesis_block.signature,
            'index': 0
            })
        block = BU.get_latest_block()
        latest_block_index.value = block.get('index')

    dup_test = Mongo.db.consensus.find({'peer': 'me', 'index': latest_block_index.value, 'block.version': BU.get_version_for_height(latest_block_index.value + 1)}).sort([('index', -1)])
    if dup_test.count():
        print 'returning', latest_block_index.value + 1, BU.get_version_for_height(latest_block_index.value + 1)
        return

    transactions = Mongo.db.miner_transactions.find()
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
                needed_value = sum([float(x.value) for x in transaction.outputs]) + float(transaction.fee)
                res = BU.get_wallet_unspent_transactions(address, needed_value=needed_value)
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
                Mongo.db.miner_transactions.remove({'id': transaction.transaction_signature})
                print 'transaction removed: input presumably spent already, not in unspent outputs', transaction.transaction_signature
                Mongo.db.failed_transactions.insert({'reason': 'input presumably spent already', 'txn': transaction.to_dict()})
            elif failed2:
                Mongo.db.miner_transactions.remove({'id': transaction.transaction_signature})
                print 'transaction removed: using an input used by another transaction in this block', transaction.transaction_signature
                Mongo.db.failed_transactions.insert({'reason': 'using an input used by another transaction in this block', 'txn': transaction.to_dict()})
            else:
                transaction_objs.append(transaction)
        except MissingInputTransactionException as e:
            #print 'missing this input transaction, will try again later'
            pass
        except InvalidTransactionSignatureException as e:
            print 'InvalidTransactionSignatureException: transaction removed'
            Mongo.db.miner_transactions.remove({'id': transaction.transaction_signature})
            Mongo.db.failed_transactions.insert({'reason': 'InvalidTransactionSignatureException', 'txn': transaction.to_dict()})
        except InvalidTransactionException as e:
            print 'InvalidTransactionException: transaction removed'
            Mongo.db.miner_transactions.remove({'id': transaction.transaction_signature})
            Mongo.db.failed_transactions.insert({'reason': 'InvalidTransactionException', 'txn': transaction.to_dict()})
        except Exception as e:
            #print e
            #print 'rejected transaction', txn['id']
            pass
        except BaseException as e:
            #print e
            #print 'rejected transaction', txn['id']
            pass
    try:
        block = BlockFactory.mine(transaction_objs, Config.public_key, Config.private_key, Config.max_duration, output, latest_block_index, status, nonces)
    except Exception as e:
        raise
    if block:
        dup_test = Mongo.db.consensus.find_one({'peer': 'me', 'index': block.index, 'block.version': BU.get_version_for_height(block.index)})
        if not dup_test:
            print '\r\nCandidate submitted for index:', block.index
            print '\r\nTransactions:'
            for x in block.transactions:
                print x.transaction_signature 
            Mongo.db.consensus.insert({'peer': 'me', 'index': block.index, 'id': block.signature, 'block': block.to_dict()})
            print '\r\nSent block to:'
            for peer in Peers.peers:
                try:
                    block_dict = block.to_dict()
                    block_dict['peer'] = my_peer
                    requests.post(
                        'http://{peer}/newblock'.format(
                            peer=peer.host + ":" + str(peer.port)
                        ),
                        json=block_dict,
                        timeout=3,
                        headers={'Connection':'close'}
                    )
                    print peer.host + ":" + str(peer.port)
                except Exception as e:
                    print e
                    try:
                        print 'reporting bad peer'
                        requests.post(
                            'https://yadacoin.io/peers',
                            json={'host': peer.host, 'port': str(peer.port), 'failed': True},
                            timeout=3,
                            headers={'Connection':'close'}
                        )
                    except:
                        print 'failed to report bad peer'
                        pass    
