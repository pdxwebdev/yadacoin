import argparse
import hashlib
import json
import requests
import time
import re
import itertools
import sys
from uuid import uuid4
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

