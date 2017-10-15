import json
import hashlib
import os
import argparse
import qrcode
import base64

from io import BytesIO
from uuid import uuid4
from ecdsa import NIST384p, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
from transaction import TransactionFactory, Transaction
from blockchainutils import BU


class BlockFactory(object):
    def __init__(self, transactions, coinbase, block_reward, public_key, private_key, answer, difficulty):
        blocks = BU.get_blocks()
        self.index = len(blocks)
        self.prev_hash = blocks[len(blocks)-1]['hash'] if len(blocks) > 0 else ''
        self.nonce = str(uuid4())
        self.public_key = public_key
        self.private_key = private_key
        self.answer = answer
        self.difficulty = difficulty

        transaction_objs = []
        for txn in transactions:
            if isinstance(txn, Transaction):
                txn.verify()
                transaction_obj = txn
            else:
                transaction_obj = Transaction(
                    transaction_signature=txn.get('id', ''),
                    rid=txn.get('rid', ''),
                    relationship=txn.get('relationship', ''),
                    public_key=txn.get('public_key', ''),
                    value=txn.get('value', ''),
                    fee=txn.get('fee', ''),
                    requester_rid=txn.get('requester_rid', ''),
                    requested_rid=txn.get('requested_rid', ''),
                    challenge_code=txn.get('challenge_code', '')
                )
            transaction_objs.append(transaction_obj)
        transaction_objs.append(TransactionFactory(
            public_key=self.public_key,
            private_key=self.private_key,
            value=block_reward).generate_transaction())
        self.transactions = transaction_objs
        txn_hashes = self.get_transaction_hashes()
        self.set_merkle_root(txn_hashes)
        self.hash = hashlib.sha256(
            str(self.index) +
            self.prev_hash +
            self.nonce +
            self.merkle_root +
            self.answer + 
            self.difficulty
        ).digest().encode('hex')
        self.block = Block(
            block_index=self.index,
            prev_hash=self.prev_hash,
            nonce=self.nonce,
            transactions=self.transactions,
            block_hash=self.hash,
            merkle_root=self.merkle_root,
            answer=self.answer,
            difficulty=self.difficulty
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
    def mine(cls, transactions, coinbase, block_reward, difficulty, public_key, private_key):
        i = 0
        blocks = BU.get_block_objs()
        while 1:
            if blocks:
                prev_nonce = blocks[-1].nonce
            else:
                prev_nonce = ''
            hash_test = hashlib.sha256("%s%s" % (prev_nonce, i)).digest().encode('hex')
            if hash_test.endswith(difficulty):
                print 'got a block!'
                print 'verify answer, nonce: ', prev_nonce, 'interation: ', i, 'hash: ', hashlib.sha256("%s%s" % (prev_nonce, i)).hexdigest()
                # create the block with the reward
                # gather friend requests from the network

                block = cls(
                    transactions=transactions,
                    coinbase=coinbase,
                    block_reward=block_reward,
                    public_key=public_key,
                    private_key=private_key,
                    answer=hashlib.sha256("%s%s" % (prev_nonce, i)).hexdigest(),
                    difficulty=difficulty)
                block.block.save()
                break
            i += 1


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
        difficulty=''
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
        self.verify()

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
                self.difficulty).hexdigest()
            if self.hash != hashtest:
                raise BaseException('Invalid block')
        except:
            raise

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
        with open('blockchain.json', 'r+') as f:
            blocks = BU.get_blocks()
            blocks.append(self.toDict())
            f.seek(0)
            f.write(json.dumps({'blocks': blocks}, indent=4))
            f.truncate()

    def toDict(self):
        return {
            'index': self.index,
            'prevHash': self.prev_hash,
            'nonce': self.nonce,
            'transactions': [x.toDict() for x in self.transactions],
            'hash': self.hash,
            'merkleRoot': self.merkle_root,
            'answer': self.answer,
            'difficulty': self.difficulty
        }

    def toJson(self):
        return json.dumps(self.toDict())
