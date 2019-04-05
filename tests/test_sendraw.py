import socketio
import socket
import json
import time
import signal
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)) + '/..')
import requests
import base64
import humanhash
import re
import pymongo
import subprocess
import multiprocessing
import pprint
from sys import exit
from multiprocessing import Process, Value, Array, Pool
from socketIO_client import SocketIO, BaseNamespace
from flask import Flask, render_template, request, Response
from flask_cors import CORS
from yadacoin import (
    TransactionFactory, Transaction, MissingInputTransactionException,
    Input, Output, Block, Config, Peers,
    Blockchain, BlockChainException, TU, BU,
    Mongo, BlockFactory, NotEnoughMoneyException, Peer,
    Consensus, PoolPayer, Faucet, Send, Graph, Serve, endpoints_old, Wallet
)
from yadacoin import MiningPool
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from gevent import pywsgi, pool
from bip32utils import BIP32Key


def subkey(index):
    qtctl_env = os.environ.copy()
    qtctl_env["QTCTL_KEY"] = "xprv9v3URixxtyRbDyys2zmY7xxtt2NvjpsdR3DHu7djw9AckBowqBFuSDamhVpn127WDfcbsGbSwqLayFueXEPrpyPTqMNbJ6XCnS7obNyDsyn"
    qtctl_env["QTCTL_ADDRESSVERSION"] = "0"

    ex_key = BIP32Key.fromExtendedKey(qtctl_env["QTCTL_KEY"])
    key = ex_key.ChildKey(int(index))
    child_key = BIP32Key.fromExtendedKey(key.ExtendedKey())
    private_key = child_key.PrivateKey().hex()
    public_key = child_key.PublicKey().hex()
    address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
    
    return {'public_key': public_key, 'index': index, "private_key": private_key, 'address': address}

def generate_some_blocks(keys):
    for key in keys:
        transactions = []
        existing_input = mongo.db.blocks.find({'transactions.outputs.to': key.get('address')})
        if existing_input.count() == 0:
            config = Wallet(key)
            index = BU.get_latest_block(config, mongo)['index'] + 1
            block = BlockFactory(transactions, key.get('public_key'), key.get('private_key'), index=index)
            block.block.special_min = True
            block.block.target = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
            block.block.nonce = 0
            header = BlockFactory.generate_header(block.block)
            block.block.hash = BlockFactory.generate_hash_from_header(header, block.block.nonce)
            block.block.signature = BU.generate_signature(block.block.hash, key['private_key'])
            mongo.db.consensus.insert({
                'peer': 'me',
                'index': block.block.index,
                'id': block.block.signature,
                'block': block.block.to_dict()
            })
            consensus.sync_bottom_up()

def get_keys():
    existing_keys = mongo.db.keys.find({})
    if existing_keys.count() == 0:
        keys = []
        for i in range(5):
            key = subkey(i)
            mongo.db.keys.insert(key)
            keys.append(key)

        print("generated a keyring of 5 addresses")
    else:
        keys = [x for x in existing_keys]
    return keys

if __name__ == '__main__':
    multiprocessing.freeze_support()
    import argparse
    import os.path
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', nargs=None, help='serve, mine, or consensus')
    parser.add_argument('config', default="config.json", nargs="?", help='config file')
    parser.add_argument('to', default="", nargs="?", help='to')
    parser.add_argument('value', default=0, nargs="?", help='amount')
    parser.add_argument('-n', '--network', default='mainnet', help='Specify mainnet, testnet or regnet')
    parser.add_argument('-c', '--cores', default=multiprocessing.cpu_count(), help='Specify number of cores to use')
    parser.add_argument('-p', '--pool', default='', help='Specify pool to use')
    parser.add_argument('-d', '--debug', default=False, help='Debug messages')
    parser.add_argument('-r', '--reset', default=False, help='If blockchain is invalid, truncate at error block')
    args = parser.parse_args()

    if os.path.isfile(args.config):
        with open(args.config) as f:
            config = Config(json.loads(f.read()))
    else:
        print 'no config file found at \'%s\'' % args.config
        exit()

    mongo = Mongo(config)
    consensus = Consensus(config, mongo, True)
    consensus.sync_bottom_up()

    keys = get_keys()
    generate_some_blocks(keys)
    pprint.pprint(keys)
    # Assemble the list of inputs
    inputs = []
    for key in keys:
        input_txns = BU.get_wallet_unspent_transactions(config, mongo, key.get('address'))
        for tx in input_txns:
            for i, out in enumerate(tx['outputs']):
                if out['to'] != key.get('address'):
                    continue
                inputs.append({
                    "hash": tx['hash'],
                    "id": tx['id'],
                    "index": i,
                    "value": out['value'],
                    "time": tx['time'],
                    "height": tx['height'],
                    "fee": tx['fee'],
                    "public_key": tx['public_key'],
                    "signature": TU.generate_signature(tx['id'], key['private_key']),
                    "address": key.get('address')
                })

    spendable = sum(i['value'] for i in inputs)
    print("collected {:,} spendable inputs totaling {:,}"
            .format(len(inputs), spendable))
    if spendable < float(args.value) + 0.01:
        print("insufficient funds")
        sys.exit()


    picked = []
    picked_sum = 0
    for inp in inputs:
        picked.append(inp)
        picked_sum += inp['value']
        if picked_sum >= float(args.value):
            break

    print("picked {:,} inputs totaling {:,} to send for tx"
            .format(len(inputs), spendable))

    # this
    transaction = Transaction(
        block_height=BU.get_latest_block(config, mongo)['index'],
        fee=0.01,
        public_key=config.public_key,
        outputs=[
            {'to': config.address, 'value': float(args.value)}
        ],
        inputs=picked,
    )
    transaction.hash = transaction.generate_hash()
    transaction.transaction_signature = TU.generate_signature(transaction.hash, config.private_key)
    transaction.verify()
    index = BU.get_latest_block(config, mongo)['index'] + 1
    block = BlockFactory([transaction], config.public_key, config.private_key, index=index)
    block.block.special_min = True
    block.block.target = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    block.block.nonce = 0
    header = BlockFactory.generate_header(block.block)
    block.block.hash = BlockFactory.generate_hash_from_header(header, block.block.nonce)
    block.block.signature = BU.generate_signature(block.block.hash, config.private_key)
    block.block.verify()
    mongo.db.consensus.insert({
        'peer': 'me',
        'index': block.block.index,
        'id': block.block.signature,
        'block': block.block.to_dict()
    })
    consensus.sync_bottom_up()
    print(transaction.to_json())