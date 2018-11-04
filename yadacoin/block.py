import json
import hashlib
import os
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
    def __init__(self, transactions, public_key, private_key, version, index=None, force_time=None):
        self.version = BU.get_version_for_height(index)
        if force_time:
            self.time = str(int(force_time))
        else:
            self.time = str(int(time.time()))
        blocks = BU.get_blocks()
        self.index = index
        if self.index == 0:
            self.prev_hash = '' 
        else:
            self.prev_hash = BU.get_latest_block()['hash']
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
    def generate_header(cls, block):
        return str(block.version) + \
            str(block.time) + \
            block.public_key + \
            str(block.index) + \
            block.prev_hash + \
            '{nonce}' + \
            str(block.special_min) + \
            str(block.target) + \
            block.merkle_root

    @classmethod
    def generate_hash_from_header(cls, header, nonce):
        header = header.format(nonce=nonce)
        return hashlib.sha256(hashlib.sha256(header).digest()).digest()[::-1].encode('hex')

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
    def get_target(cls, height, last_time, last_block, blockchain):
        # change target
        max_target = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
        retarget_period = 2016  # blocks
        two_weeks = 1209600  # seconds
        half_week = 302400  # seconds
        if height > 0 and height % retarget_period == 0:
            block_from_2016_ago = Block.from_dict(BU.get_block_by_index(height - retarget_period))
            two_weeks_ago_time = block_from_2016_ago.time
            elapsed_time_from_2016_ago = int(last_time) - int(two_weeks_ago_time)
            # greater than two weeks?
            if elapsed_time_from_2016_ago > two_weeks:
                time_for_target = two_weeks
            elif elapsed_time_from_2016_ago < half_week:
                time_for_target = half_week
            else:
                time_for_target = int(elapsed_time_from_2016_ago)

            block_to_check = last_block
            while 1:
                if block_to_check.special_min:
                    block_to_check = blockchain.blocks[block_to_check.index - 1]
                else:
                    target = block_to_check.target
                    break
            new_target = (time_for_target * target) / two_weeks
            if new_target > max_target:
                target = max_target
            else:
                target = new_target
        # target is stupid
        elif height == 0:
            target = max_target
        else:
            block_to_check = last_block
            while 1:
                if block_to_check.special_min:
                    block_to_check = blockchain.blocks[block_to_check.index - 1]
                else:
                    target = block_to_check.target
                    break
        return target

    @classmethod
    def mine(cls, header, target, nonces, special_min=False):

        lowest = (0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff, 0, '')
        nonce = nonces[0]
        while nonce < nonces[1]:
            hash_test = cls.generate_hash_from_header(header, str(nonce))

            text_int = int(hash_test, 16)
            if text_int < target or special_min:
                return nonce, hash_test

            if text_int < lowest[0]:
                lowest = (text_int, nonce, hash_test)
            nonce += 1
        return lowest[1], lowest[2]

    @classmethod
    def get_genesis_block(cls):
        return Block.from_dict({
            "nonce" : 0,
            "hash" : "0dd0ec9ab91e9defe535841a4c70225e3f97b7447e5358250c2dc898b8bd3139",
            "public_key" : "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
            "id" : "MEUCIQDDicnjg9DTSnGOMLN3rq2VQC1O9ABDiXygW7QDB6SNzwIga5ri7m9FNlc8dggJ9sDg0QXUugrHwpkVKbmr3kYdGpc=",
            "merkleRoot" : "705d831ced1a8545805bbb474e6b271a28cbea5ada7f4197492e9a3825173546",
            "index" : 0,
            "target" : "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "special_min" : False,
            "version" : "1",
            "transactions" : [ 
                {
                    "public_key" : "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
                    "fee" : 0.0000000000000000,
                    "hash" : "71429326f00ba74c6665988bf2c0b5ed9de1d57513666633efd88f0696b3d90f",
                    "dh_public_key" : "",
                    "relationship" : "",
                    "inputs" : [],
                    "outputs" : [ 
                        {
                            "to" : "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4",
                            "value" : 50.0000000000000000
                        }
                    ],
                    "rid" : "",
                    "id" : "MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0="
                }
            ],
            "time" : "1537127756",
            "prevHash" : ""
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
        signature='',
        special_min='',
        target=''
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
        self.special_min = special_min
        self.target = target

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
            signature=block.get('id'),
            special_min=block.get('special_min'),
            target=int(block.get('target'), 16)
        )
    
    def get_coinbase(self):
        for txn in self.transactions:
            if str(P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex'))) in [x.to for x in txn.outputs] and len(txn.outputs) == 1 and not txn.relationship:
                return txn


    def verify(self):
        getcontext().prec = 8
        if int(self.version) != int(BU.get_version_for_height(self.index)):
            raise BaseException("Wrong version for block height", self.version, BU.get_version_for_height(self.index))
        try:
            txns = self.get_transaction_hashes()
            self.set_merkle_root(txns)
            if self.verify_merkle_root != self.merkle_root:
                raise BaseException("Invalid block")
        except:
            raise

        try:
            header = BlockFactory.generate_header(self)
            hashtest = BlockFactory.generate_hash_from_header(header, str(self.nonce))
            if self.hash != hashtest:
                raise BaseException('Invalid block')
        except:
            raise

        address = P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex'))
        try:
            result = verify_signature(base64.b64decode(self.signature), self.hash, self.public_key.decode('hex'))
            if not result:
                raise Exception("block signature is invalid")
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
            'special_min': self.special_min,
            'target': format(self.target, 'x'),
            'id': self.signature
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)
