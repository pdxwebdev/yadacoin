import argparse
import hashlib
import json
import requests
import time
from uuid import uuid4
from ecdsa import SigningKey, SECP256k1
from block import Block, BlockFactory
from transaction import Transaction, Input
from blockchainutils import BU
from transactionutils import TU
from transaction import TransactionFactory

def verify_block(block):
    pass

def verify_transaction(transaction):
    signature = transaction.signature

def generate_block(blocks, coinbase, block_reward, transactions):
    block = {
        'index': len(blocks),
        'prevHash': blocks[len(blocks)-1]['hash'] if len(blocks) > 0 else '',
        'reward': {
            'to': coinbase,
            'value': block_reward
        },
        'nonce': str(uuid4()),
        'transactions': transactions
    }
    block['hash'] = hashlib.sha256(json.dumps(block)).digest().encode('hex')
    return block

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
    block_reward = config.get('block_reward')
    difficulty = config.get('difficulty')

    blocks = BU.get_block_objs()  # verifies as the blocks are created so no need to call block.verify() on each block
    print 'waiting for transactions...'
    while 1:
        with open('miner_transactions.json', 'r+') as f:
            transactions_parsed = json.loads(f.read())
            if transactions_parsed:
                f.seek(0)
                f.write('[]')
                f.truncate()
            transactions = []
            for txn in transactions_parsed:
                transaction = Transaction(
                    transaction_signature=txn.get('id'),
                    rid=txn.get('rid', ''),
                    relationship=txn.get('relationship', ''),
                    public_key=txn.get('public_key'),
                    value=txn.get('value'),
                    fee=txn.get('fee'),
                    requester_rid=txn.get('requester_rid', ''),
                    requested_rid=txn.get('requested_rid', ''),
                    challenge_code=txn.get('challenge_code', ''),
                    answer=txn.get('answer', ''),
                    txn_hash=txn.get('hash', ''),
                    post_text=txn.get('post_text', ''),
                    to=txn.get('to', ''),
                    inputs=[Input(
                        transaction_signature=input_txn.get('id', ''),
                        rid=input_txn.get('rid', ''),
                        relationship=input_txn.get('relationship', ''),
                        public_key=input_txn.get('public_key', ''),
                        value=input_txn.get('value', ''),
                        fee=input_txn.get('fee', ''),
                        requester_rid=input_txn.get('requester_rid', ''),
                        requested_rid=input_txn.get('requested_rid', ''),
                        challenge_code=input_txn.get('challenge_code', ''),
                        answer=input_txn.get('answer', ''),
                        txn_hash=input_txn.get('hash', ''),
                        post_text=input_txn.get('post_text', ''),
                        to=input_txn.get('to', ''),
                        inputs=input_txn.get('inputs', ''),
                        coinbase=True
                    ) for input_txn in txn.get('inputs', '')]
                )
                transactions.append(transaction)

        if not transactions and len(blocks):
            pass
        elif not transactions and not len(blocks):
            block = BlockFactory.mine(transactions, coinbase, 50, difficulty, public_key, private_key)
            txn = TransactionFactory(
                public_key=public_key,
                private_key=private_key,
                value=10,
                fee=0.1,
                to='1CHVGmXNZgznyYVHzs64WcDVYn3aV8Gj4u',
                coinbase=True,
                inputs=block.transactions
            ).generate_transaction()
            BlockFactory.mine([txn,], coinbase, 1, difficulty, public_key, private_key)
            print 'waiting for transactions...'
            blocks = BU.get_block_objs()
        else:
            BlockFactory.mine(transactions, coinbase, block_reward, difficulty, public_key, private_key)
            print 'waiting for transactions...'
            blocks = BU.get_block_objs()

        time.sleep(1)
