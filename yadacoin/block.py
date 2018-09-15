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
from coincurve.utils import verify_signature
from config import Config
from mongo import Mongo


class BlockFactory(object):
    def __init__(self, transactions, public_key, private_key, version, index=None):
        self.version = version
        self.time = str(int(time.time()))
        blocks = BU.get_blocks()
        self.index = index if index > -1 else BU.get_latest_block().get('index', -1) + 1
        self.prev_hash = '' if index > -1 else elseblocks[blocks.count()-1]['hash'] if blocks.count() > 0 else ''
        self.public_key = public_key
        self.private_key = private_key

        transaction_objs = []
        fee_sum = 0.0
        unspent_indexed = {}
        used_sigs = []
        for txn in transactions:
            if isinstance(txn, Transaction):
                transaction_obj = txn
            else:
                transaction_obj = Transaction.from_dict(txn)
            if transaction_obj.transaction_signature in used_sigs:
                print 'duplicate transaction found and removed'
                continue
            used_sigs.append(transaction_obj.transaction_signature)
            transaction_obj.verify()
            #check double spend
            address = str(P2PKHBitcoinAddress.from_pubkey(transaction_obj.public_key.decode('hex')))
            if address in unspent_indexed:
                unspent_ids = unspent_indexed[address]
            else:
                res = BU.get_wallet_unspent_transactions(address)
                unspent_ids = [x['id'] for x in res]
                unspent_indexed[address] = unspent_ids

            failed = False
            used_ids_in_this_txn = []
            for x in transaction_obj.inputs:
                if x.id not in unspent_ids:
                    failed = True
                if x.id in used_ids_in_this_txn:
                    failed = True
                used_ids_in_this_txn.append(x.id)
            if not failed:
                transaction_objs.append(transaction_obj)
                fee_sum += float(transaction_obj.fee)
        block_reward = BU.get_block_reward()
        coinbase_txn_fctry = TransactionFactory(
            public_key=self.public_key,
            private_key=self.private_key,
            outputs=[Output(
                value=block_reward + float(fee_sum),
                to=str(P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex')))
            )],
            coinbase=True
        )
        coinbase_txn = coinbase_txn_fctry.generate_transaction()
        transaction_objs.append(coinbase_txn)

        self.transactions = transaction_objs
        txn_hashes = self.get_transaction_hashes()
        self.set_merkle_root(txn_hashes)
        self.block = Block(
            version=self.version,
            block_time=self.time,
            block_index=self.index,
            prev_hash=self.prev_hash,
            transactions=self.transactions,
            merkle_root=self.merkle_root,
            public_key=self.public_key
        )

    @classmethod
    def generate_hash(cls, block, nonce):
        return hashlib.sha256(
            str(block.version) +
            str(block.time) +
            block.public_key +
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
    def mine(cls, transactions, difficulty, public_key, private_key, max_duration, callback=None, current_index=None, status=None):
        import itertools, sys
        if hasattr(current_index, 'value'):
            height = current_index.value
        else:
            height = current_index
        spinner = itertools.cycle(['-', '/', '|', '\\'])
        block_factory = cls(
            transactions=transactions,
            public_key=public_key,
            private_key=private_key,
            index=height,
            version=Config.block_version)
        if current_index:
            initial_current_index = current_index.value
        nonce = 0
        start = time.time()
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
                if status:
                    status.value = 'mined'
                return block
            if current_index and current_index.value > initial_current_index:
                status.value = 'exited'
                break
            nonce += 1
            if time.time() - start > max_duration:
                break

    @classmethod
    def get_genesis_block(cls):
        return Block.from_dict({
            "nonce": 377932127, 
            "index": 0, 
            "version": "1", 
            "hash": "00000000faa3ce27aabd73e157343bb591027f46ecf6b1d99c5b5040ca2d17c1", 
            "public_key": "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570", 
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
                    "id": "MEQCIFMKD8OB1CPyY6O9sk5cbxXi0bcDZwljMs6KjhXEraOsAiBan2w1BV9X/haquYwuFt3V2gEnOsW5kXS5IBcC82BQyw=="
                }
            ], 
            "time": "1536913414", 
            "prevHash": "", 
            "id": "MEUCIQDQwa1FU/8dK61T6b3j8kgZKjiiJuVU1pMqoPwl5U2AogIgfSRtWzHBTtCwzfHw+TT+AXi49Mj46NOo0ID8Pcuhxf4=", 
            "merkleRoot": "705d831ced1a8545805bbb474e6b271a28cbea5ada7f4197492e9a3825173546"
        })

class Block(object):
    def __init__(
        self,
        version='',
        block_time='',
        block_index='',
        prev_hash='',
        nonce='',
        transactions='',
        block_hash='',
        merkle_root='',
        public_key='',
        signature=''
    ):
        self.version = version
        self.time = block_time
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
            version=block.get('version'),
            block_time=block.get('time'),
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

        address = P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex'))
        try:
            result = verify_signature(base64.b64decode(self.signature), self.hash, self.public_key.decode('hex'))
            if not result:
                raise
        except:
            try:
                result = VerifyMessage(address, BitcoinMessage(self.hash, magic=''), self.signature)
                if not result:
                    raise
            except:
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

        if Decimal(str(fee_sum)[:10]) != (Decimal(str(coinbase_sum)[:10]) - Decimal(str(reward)[:10])):
            raise BaseException("Coinbase output total does not equal block reward + transaction fees", fee_sum, (coinbase_sum - reward))

    def generate_hash(self):
        return hashlib.sha256(
            str(self.version) +
            str(self.time) +
            self.public_key +
            str(self.index) +
            self.prev_hash +
            str(self.nonce) +
            self.merkle_root
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
            self.verify_merkle_root = hashes[0]

    def save(self):
        self.verify()
        for txn in self.transactions:
            if txn.inputs:
                address = str(P2PKHBitcoinAddress.from_pubkey(txn.public_key.decode('hex')))
                unspent = BU.get_wallet_unspent_transactions(address, [x.id for x in txn.inputs])
                unspent_ids = [x['id'] for x in unspent]
                failed = False
                used_ids_in_this_txn = []
                for x in txn.inputs:
                    if x.id not in unspent_ids:
                        failed = True
                    if x.id in used_ids_in_this_txn:
                        failed = True
                    used_ids_in_this_txn.append(x.id)
                if failed:
                    raise BaseException('double spend', [x.id for x in txn.inputs])
        res = Mongo.db.blocks.find({"index": (int(self.index) - 1)})
        if res.count() and res[0]['hash'] == self.prev_hash or self.index == 0:
            Mongo.db.blocks.insert(self.to_dict())
        else:
            print "CRITICAL: block rejected..."

    def delete(self):
        Mongo.db.blocks.remove({"index": self.index})

    def to_dict(self):
        return {
            'version': self.version,
            'time': self.time,
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
        return json.dumps(self.to_dict(), indent=4)
