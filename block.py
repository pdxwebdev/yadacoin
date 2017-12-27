import json
import hashlib
import os
import argparse
import qrcode
import base64
import time

from decimal import Decimal, getcontext
from io import BytesIO
from uuid import uuid4
from ecdsa import SECP256k1, SigningKey, VerifyingKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
from transaction import TransactionFactory, Transaction, Output
from blockchainutils import BU
from transactionutils import TU
from bitcoin.signmessage import BitcoinMessage, VerifyMessage, SignMessage
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress


class BlockFactory(object):
    def __init__(self, transactions, coinbase, public_key, private_key):
        BU.private_key = private_key
        TU.private_key = private_key
        blocks = BU.get_blocks()
        self.index = BU.get_latest_block().get('index', -1) + 1
        self.prev_hash = blocks[blocks.count()-1]['hash'] if blocks.count() > 0 else ''
        self.public_key = public_key
        self.private_key = private_key

        transaction_objs = []
        fee_sum = 0.0
        for txn in transactions:
            if isinstance(txn, Transaction):
                transaction_obj = txn
            else:
                transaction_obj = Transaction.from_dict(txn)
            transaction_obj.verify()
            #check double spend
            res = BU.get_wallet_unspent_transactions(str(P2PKHBitcoinAddress.from_pubkey(transaction_obj.public_key.decode('hex'))))
            unspent_ids = [x['id'] for x in res]
            failed = False
            for x in transaction_obj.inputs:
                if x.id not in unspent_ids:
                    failed = True
            if not failed:
                transaction_objs.append(transaction_obj)
                fee_sum += float(transaction_obj.fee)
        block_reward = BU.get_block_reward()
        coinbase_txn = TransactionFactory(
            public_key=self.public_key,
            private_key=self.private_key,
            outputs=[Output(
                value=block_reward + float(fee_sum),
                to=str(P2PKHBitcoinAddress.from_pubkey(coinbase.decode('hex')))
            )],
            coinbase=True
        ).generate_transaction()
        transaction_objs.append(coinbase_txn)

        self.transactions = transaction_objs
        txn_hashes = self.get_transaction_hashes()
        self.set_merkle_root(txn_hashes)
        self.block = Block(
            block_index=self.index,
            prev_hash=self.prev_hash,
            transactions=self.transactions,
            merkle_root=self.merkle_root,
            public_key=self.public_key
        )

    @classmethod
    def generate_hash(cls, block, nonce):
        return hashlib.sha256(
            str(block.index) +
            block.prev_hash +
            str(nonce) +
            block.merkle_root
        ).hexdigest()

    def get_transaction_hashes(self):
        return sorted([str(x.hash) for x in self.transactions], key=str.lower)

    def set_merkle_root(self, txn_hashes):
        hashes = []
        for i in range(0, len(txn_hashes), 2):
            txn1 = txn_hashes[i]
            try:
                txn2 = txn_hashes[i+1]
            except:
                txn2 = ''
            hashes.append(hashlib.sha256(txn1+txn2).digest().encode('hex'))
        if len(hashes) > 1:
            self.set_merkle_root(hashes)
        else:
            self.merkle_root = hashes[0]

    @classmethod
    def mine(cls, transactions, coinbase, difficulty, public_key, private_key, callback=None, current_index=None, status=None):
        blocks = BU.get_block_objs()
        import itertools, sys
        spinner = itertools.cycle(['-', '/', '|', '\\'])
        block_factory = cls(
            transactions=transactions,
            coinbase=coinbase,
            public_key=public_key,
            private_key=private_key)
        initial_current_index = current_index.value
        nonce = 0
        while 1:
            if callback:
                callback(current_index.value)
            hash_test = cls.generate_hash(block_factory.block, str(nonce))
            # print hash_test
            if hash_test.startswith(difficulty):
                # create the block with the reward
                # gather friend requests from the network
                block = block_factory.block
                block.hash = hash_test
                block.nonce = nonce
                block.signature = BU.generate_signature(hash_test)
                status.value = 'mined'
                return block
            if current_index.value > initial_current_index:
                status.value = 'exited'
                break
            nonce += 1


class Block(object):
    def __init__(
        self,
        block_index='',
        prev_hash='',
        nonce='',
        transactions='',
        block_hash='',
        merkle_root='',
        public_key='',
        signature=''
    ):
        self.index = block_index
        self.prev_hash = prev_hash
        self.nonce = nonce
        self.transactions = transactions
        txn_hashes = self.get_transaction_hashes()
        self.set_merkle_root(txn_hashes)
        self.merkle_root = merkle_root
        self.hash = block_hash
        self.public_key = public_key
        self.signature = signature

    @classmethod
    def from_dict(cls, block):
        transactions = []
        for txn in block.get('transactions'):
            # TODO: do validify checking for coinbase transactions
            if str(P2PKHBitcoinAddress.from_pubkey(block.get('public_key').decode('hex'))) in [x['to'] for x in txn.get('outputs', '')] and len(txn.get('outputs', '')) == 1 and not txn.get('relationship'):
                txn['coinbase'] = True  
            else:
                txn['coinbase'] = False
            transactions.append(Transaction.from_dict(txn))

        return cls(
            block_index=block.get('index'),
            public_key=block.get('public_key'),
            prev_hash=block.get('prevHash'),
            nonce=block.get('nonce'),
            transactions=transactions,
            block_hash=block.get('hash'),
            merkle_root=block.get('merkleRoot'),
            signature=block.get('id')
        )

    def verify(self):
        getcontext().prec = 8
        try:
            txns = self.get_transaction_hashes()
            self.set_merkle_root(txns)
            if self.verify_merkle_root != self.merkle_root:
                raise BaseException("Invalid block")
        except:
            raise

        try:
            hashtest = BlockFactory.generate_hash(self, str(self.nonce))
            if self.hash != hashtest:
                raise BaseException('Invalid block')
        except:
            raise

        if not VerifyMessage(P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex')), BitcoinMessage(self.hash, magic=''), self.signature):
            raise BaseException("block signature is invalid")

        # verify reward
        coinbase_sum = 0
        for txn in self.transactions:
            if txn.coinbase:
                for output in txn.outputs:
                    coinbase_sum += float(output.value)

        fee_sum = 0.0
        for txn in self.transactions:
            if not txn.coinbase:
                fee_sum += float(txn.fee)
        reward = BU.get_block_reward(self)

        try:
            with open('block_rewards.json', 'r') as f:
                block_rewards = json.loads(f.read())
        except:
            raise BaseException("Block reward file not found")

        if Decimal(str(fee_sum)[:10]) != (Decimal(str(coinbase_sum)[:10]) - Decimal(str(reward)[:10])):
            raise BaseException("Coinbase output total does not equal block reward + transaction fees", fee_sum, (coinbase_sum - reward))

    def get_transaction_hashes(self):
        return sorted([str(x.hash) for x in self.transactions], key=str.lower)

    def set_merkle_root(self, txn_hashes):
        hashes = []
        for i in range(0, len(txn_hashes), 2):
            txn1 = txn_hashes[i]
            try:
                txn2 = txn_hashes[i+1]
            except:
                txn2 = ''
            hashes.append(hashlib.sha256(txn1+txn2).digest().encode('hex'))
        if len(hashes) > 1:
            self.set_merkle_root(hashes)
        else:
            self.verify_merkle_root = hashes[0]

    def save(self):
        self.verify()
        for txn in self.transactions:
            address = str(P2PKHBitcoinAddress.from_pubkey(txn.public_key.decode('hex')))
            unspent = BU.get_wallet_unspent_transactions(address)
            unspent_ids = [x['id'] for x in unspent]
            failed = False
            for x in txn.inputs:
                if x.id not in unspent_ids:
                    failed = True
            if failed:
                raise BaseException('double spend', txn)

        res = self.collection.find({"index": (int(self.index) - 1)})
        if res.count() and res[0]['hash'] == self.prev_hash or self.index == 0:
            self.collection.insert(self.to_dict())
        else:
            print "CRITICAL: block rejected..."

    def delete(self):
        self.collection.remove({"index": self.index})

    def to_dict(self):
        return {
            'index': self.index,
            'public_key': self.public_key,
            'prevHash': self.prev_hash,
            'nonce': self.nonce,
            'transactions': [x.to_dict() for x in self.transactions],
            'hash': self.hash,
            'merkleRoot': self.merkle_root,
            'id': self.signature
        }

    def to_json(self):
        return json.dumps(self.to_dict())
