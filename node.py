import argparse
import hashlib
import json
import requests
import time
from uuid import uuid4
from ecdsa import SigningKey, SECP256k1
from block import Block, BlockFactory
from transaction import Transaction, Input, Output
from blockchainutils import BU
from transactionutils import TU
from transaction import TransactionFactory



def verify_block(block):
    pass

def verify_transaction(transaction):
    signature = transaction.signature

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
        difficulty = blocks[-1].next_difficulty
    else:
        difficulty = '000'
    print '//// YADA COIN MINER ////'
    print "Welcome!! Mining beginning with difficulty of:", difficulty
    if args.runtype == 'node':
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

            if not transactions and len(blocks):
                block = BlockFactory.mine(transactions, coinbase, difficulty, public_key, private_key)
                if block:
                    block.save()
            elif not transactions and not len(blocks):
                block = BlockFactory.mine(transactions, coinbase, difficulty, public_key, private_key)
                if block:
                    block.save()
            else:
                block = BlockFactory.mine(transactions, coinbase, difficulty, public_key, private_key)
                if block:
                    block.save()
            blocks = BU.get_block_objs()
            difficulty = block.next_difficulty
    elif args.runtype == 'block_getter':
        pass