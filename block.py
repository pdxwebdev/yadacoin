import json
import hashlib
import os
import argparse
import qrcode
import base64
import time

from decimal import Decimal
from pymongo import MongoClient
from io import BytesIO
from uuid import uuid4
from ecdsa import SECP256k1, SigningKey, VerifyingKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
from transaction import TransactionFactory, Transaction, Output
from blockchainutils import BU
from bitcoin.signmessage import BitcoinMessage, VerifyMessage, SignMessage
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress

mongo_client = MongoClient()
db = mongo_client.yadacoin


class BlockFactory(object):
    def __init__(self, transactions, coinbase, public_key, private_key, answer, difficulty, next_difficulty):
        blocks = BU.get_blocks()
        self.index = blocks.count()
        self.prev_hash = blocks[blocks.count()-1]['hash'] if blocks.count() > 0 else ''
        self.nonce = str(uuid4())
        self.public_key = public_key
        self.private_key = private_key
        self.answer = answer
        self.difficulty = difficulty
        self.next_difficulty = next_difficulty

        transaction_objs = []
        fee_sum = 0
        for txn in transactions:
            if isinstance(txn, Transaction):
                transaction_obj = txn
            else:
                transaction_obj = Transaction.from_dict(txn)
            transaction_obj.verify()
            transaction_objs.append(transaction_obj)
            fee_sum += transaction_obj.fee
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

        used = []
        verified_txns = []
        for transaction in transaction_objs:
            bad_txn = False
            address = str(P2PKHBitcoinAddress.from_pubkey(transaction.public_key.decode('hex')))
            utxns = []
            for utxn in BU.get_wallet_unspent_transactions(address):
                utxns.append(utxn['id'])

            for input_txn in transaction.inputs:
                if input_txn.id not in utxns or (transaction.public_key, input_txn.id) in used:
                    bad_txn = True
                used.append((transaction.public_key, input_txn.id))

            if not bad_txn:
                verified_txns.append(transaction)

        self.transactions = verified_txns
        txn_hashes = self.get_transaction_hashes()
        self.set_merkle_root(txn_hashes)
        self.hash = hashlib.sha256(
            str(self.index) +
            self.prev_hash +
            self.nonce +
            self.merkle_root +
            self.answer + 
            self.difficulty +
            self.next_difficulty
        ).digest().encode('hex')
        self.signature = BU.generate_signature(self.hash)
        self.block = Block(
            block_index=self.index,
            prev_hash=self.prev_hash,
            nonce=self.nonce,
            transactions=self.transactions,
            block_hash=self.hash,
            merkle_root=self.merkle_root,
            answer=self.answer,
            difficulty=self.difficulty,
            next_difficulty=self.next_difficulty,
            public_key=self.public_key,
            signature=self.signature
        )

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
    def mine(cls, transactions, coinbase, difficulty, public_key, private_key):
        i = 0
        blocks = BU.get_block_objs()
        start = time.time()
        import itertools, sys
        spinner = itertools.cycle(['-', '/', '|', '\\'])
        while 1:
            sys.stdout.write(spinner.next())  # write the next character
            sys.stdout.flush()                # flush stdout buffer (actual character display)
            sys.stdout.write('\b')            # erase the last written char
            if blocks:
                prev_nonce = blocks[-1].nonce
            else:
                prev_nonce = 'genesis block'
            hash_test = hashlib.sha256("%s%s" % (prev_nonce, i)).digest().encode('hex')
            # print hash_test
            if hash_test.startswith(difficulty):
                if time.time() - start < 60:
                    next_difficulty = difficulty + '0'
                elif time.time() - start > 240:
                    next_difficulty = difficulty[:-1]
                else:
                    next_difficulty = difficulty

                print 'block discovered: {previous nonce:', prev_nonce + ',', 'interation:', str(i) + ',', 'hash: ', hashlib.sha256("%s%s" % (prev_nonce, i)).hexdigest()
                # create the block with the reward
                # gather friend requests from the network
                block_factory = cls(
                    transactions=transactions,
                    coinbase=coinbase,
                    public_key=public_key,
                    private_key=private_key,
                    answer=hashlib.sha256("%s%s" % (prev_nonce, i)).hexdigest(),
                    difficulty=difficulty,
                    next_difficulty=next_difficulty)

                start = time.time()
                break
            i += 1
        try:
            return getattr(block_factory, 'block')
        except:
            pass


class Block(object):
    def __init__(
        self,
        block_index='',
        prev_hash='',
        nonce='',
        transactions='',
        block_hash='',
        merkle_root='',
        answer='',
        difficulty='',
        next_difficulty='',
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
        self.answer = answer
        self.difficulty = difficulty
        self.next_difficulty = next_difficulty
        self.public_key = public_key
        self.signature = signature
        self.verify()

    @classmethod
    def from_dict(cls, block):
        transactions = []
        for txn in block.get('transactions'):
            # TODO: do validify checking for coinbase transactions
            txn['coinbase'] = True if str(P2PKHBitcoinAddress.from_pubkey(block.get('public_key').decode('hex'))) in [x['to'] for x in txn.get('outputs', '')] else False
            transactions.append(Transaction.from_dict(txn))

        return cls(
            block_index=block.get('index'),
            public_key=block.get('public_key'),
            prev_hash=block.get('prevHash'),
            nonce=block.get('nonce'),
            transactions=transactions,
            block_hash=block.get('hash'),
            merkle_root=block.get('merkleRoot'),
            answer=block.get('answer'),
            difficulty=block.get('difficulty'),
            next_difficulty=block.get('nextDifficulty'),
            signature=block.get('id')
        )

    def verify(self):
        try:
            txns = self.get_transaction_hashes()
            self.set_merkle_root(txns)
            if self.verify_merkle_root != self.merkle_root:
                raise BaseException("Invalid block")
        except:
            raise

        try:
            hashtest = hashlib.sha256(
                str(self.index) +
                self.prev_hash +
                self.nonce +
                self.merkle_root +
                self.answer +
                self.difficulty +
                self.next_difficulty).hexdigest()
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

        fee_sum = 0
        for txn in self.transactions:
            if not txn.coinbase:
                fee_sum += txn.fee
        reward = BU.get_block_reward(self)

        try:
            with open('block_rewards.json', 'r') as f:
                block_rewards = json.loads(f.read())
        except:
            raise BaseException("Block reward file not found")

        if fee_sum != (coinbase_sum - reward):
            raise BaseException("Coinbase output total does not equal block reward + transaction fees")

        latest_block = db.blocks.find({'index': self.index - 1}).limit(1).sort([('$natural',-1)])
        if latest_block.count():
            if latest_block[0]['nextDifficulty'] != self.difficulty:
                raise BaseException("Block difficulty does not match difficulty set by previous block")

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
        db.blocks.insert(self.to_dict())

    def to_dict(self):
        return {
            'index': self.index,
            'public_key': self.public_key,
            'prevHash': self.prev_hash,
            'nonce': self.nonce,
            'transactions': [x.to_dict() for x in self.transactions],
            'hash': self.hash,
            'merkleRoot': self.merkle_root,
            'difficulty': self.difficulty,
            'nextDifficulty': self.next_difficulty,
            'answer': self.answer,
            'id': self.signature
        }

    def to_json(self):
        return json.dumps(self.to_dict())
