import json
import hashlib
import os
import argparse
import qrcode
import base64

from io import BytesIO
from uuid import uuid4
from ecdsa import SECP256k1, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
from transactionutils import TU
from bitcoin.wallet import CBitcoinSecret
from bitcoin.signmessage import BitcoinMessage, VerifyMessage, SignMessage
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from bson.son import SON


class BU(object):  # Blockchain Utilities
    collection = None
    @classmethod
    def get_blocks(cls):
        blocks = cls.collection.find({}, {'_id': 0}).sort([('index',1)])
        return blocks

    @classmethod
    def get_latest_block(cls):
        res = cls.collection.find({}, {'_id': 0}).limit(1).sort([('index',-1)])
        if res.count():
            return res[0]
        else:
            return {}

    @classmethod
    def get_block_by_index(cls, index):
        res = cls.collection.find({'index': index}, {'_id': 0})
        if res.count():
            return res[0]

    @classmethod
    def get_block_objs(cls):
        from block import Block
        from transaction import Transaction, Input, Crypt
        blocks = cls.get_blocks()
        block_objs = []
        for block in blocks:
            block_objs.append(Block.from_dict(block))
        return block_objs

    @classmethod
    def get_wallet_balance(cls, address):
        unspent_transactions = cls.get_wallet_unspent_transactions(address)
        balance = 0
        for txn in unspent_transactions:
            for output in txn['outputs']:
                if address == output['to']:
                    balance += float(output['value'])
        if balance:
            return balance
        else:
            return 0

    @classmethod
    def get_wallet_unspent_transactions(cls, address):

        received = BU.collection.aggregate([
            {
                "$match": {
                    "transactions.outputs.to": address
                }
            },
            {"$unwind": "$transactions" },
            {
                "$project": {
                    "_id": 0,
                    "txn": "$transactions"
                }
            },
            {"$unwind": "$txn.outputs" },
            {
                "$match": {
                    "txn.outputs.to": address
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "public_key": "$txn.public_key",
                    "txn": "$txn"
                }
            }
        ])
        ids = []
        reverse_public_key = ''
        for x in received:
            ids.append(x['txn']['id'])
            xaddress = str(P2PKHBitcoinAddress.from_pubkey(x['public_key'].decode('hex')))
            if xaddress == address:
                reverse_public_key = x['public_key']
                break

        # no reverse means you never spent anything
        # so all transactions are unspent
        if not reverse_public_key:
            received = BU.collection.aggregate([
                {
                    "$match": {
                        "transactions.outputs.to": address
                    }
                },
                {"$unwind": "$transactions" },
                {
                    "$project": {
                        "_id": 0,
                        "txn": "$transactions"
                    }
                },
                {
                    "$match": {
                        "txn.outputs.to": address
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "public_key": "$txn.public_key",
                        "txn": "$txn"
                    }
                }
            ])
            unspent_formatted = []
            for x in received:
                unspent_formatted.append(x['txn'])
            return unspent_formatted

        spent = BU.collection.aggregate([
            {
                "$match": {
                    "transactions.public_key": reverse_public_key
                }
            },
            {"$unwind": "$transactions" },
            {
                "$project": {
                    "_id": 0,
                    "txn": "$transactions"
                }
            },
            {"$unwind": "$txn.inputs" },
            {
                "$match": {
                    "txn.public_key": reverse_public_key
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "public_key": "$txn.public_key",
                    "input_id": "$txn.inputs.id",
                    "txn": "$txn"
                }
            }
        ])

        ids_spent_by_me = []
        for x in spent:
            ids_spent_by_me.append(x['input_id'])

        unspent = BU.collection.aggregate([
            {
                "$match": {
                    "transactions.outputs.to": address
                }
            },
            {"$unwind": "$transactions" },
            {
                "$project": {
                    "_id": 0,
                    "txn": "$transactions"
                }
            },
            {
                "$match": {
                    "txn.outputs.to": address,
                    "txn.id": {"$nin": ids_spent_by_me}
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "txn": "$txn"
                }
            }
        ])
        unspent_formatted = []
        for x in unspent:
            unspent_formatted.append(x['txn'])
        return unspent_formatted

    @classmethod
    def get_transactions(cls, raw=False, skip=None):
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        transactions = []
        for block in cls.collection.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}}):
            for transaction in block.get('transactions'):
                try:
                    if transaction.get('id') in skip:
                        continue
                    if 'relationship' not in transaction:
                        continue
                    if not transaction['relationship']:
                        continue
                    if not raw:
                        cipher = Crypt(cls.private_key)
                        decrypted = cipher.decrypt(transaction['relationship'])
                        relationship = json.loads(decrypted)
                        transaction['relationship'] = relationship
                    transactions.append(transaction)
                except:
                    continue
        return transactions

    @classmethod
    def get_relationships(cls):
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        relationships = []
        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                try:
                    cipher = Crypt(cls.private_key)
                    decrypted = cipher.decrypt(transaction['relationship'])
                    relationship = json.loads(decrypted)
                    relationships.append(relationship)
                except:
                    continue
        return relationships

    @classmethod
    def get_transaction_by_rid(cls, selector, rid=False, raw=False):
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        ds = TU.get_bulletin_secret()
        if not rid:
            selectors = [
                TU.hash(ds+selector),
                TU.hash(selector+ds)
            ]
        else:
            if not isinstance(selector, list):
                selectors = [selector, ]

        for block in cls.collection.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}}):
            for transaction in block.get('transactions'):
                if transaction.get('rid') in selectors:
                    if 'relationship' in transaction:
                        if not raw:
                            try:
                                cipher = Crypt(cls.private_key)
                                decrypted = cipher.decrypt(transaction['relationship'])
                                relationship = json.loads(decrypted)
                                transaction['relationship'] = relationship
                            except:
                                continue
                    return transaction

    @classmethod
    def get_transactions_by_rid(cls, selector, rid=False, raw=False):
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        ds = TU.get_bulletin_secret()
        if not rid:
            selectors = [
                TU.hash(ds+selector),
                TU.hash(selector+ds)
            ]
        else:
            if not isinstance(selector, list):
                selectors = [selector, ]
            else:
                selectors = selector

        transactions = []
        blocks = cls.collection.find({"transactions.rid": {"$in": selectors}, "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}})
        for block in blocks:
            for transaction in block.get('transactions'):
                if 'relationship' in transaction:
                    if not raw:
                        try:
                            cipher = Crypt(cls.private_key)
                            decrypted = cipher.decrypt(transaction['relationship'])
                            relationship = json.loads(decrypted)
                            transaction['relationship'] = relationship
                        except:
                            continue
                    transactions.append(transaction)
        return transactions

    @classmethod
    def get_bulletins(cls, bulletin_secret):
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        bulletins = []
        for block in cls.collection.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}}):
            for transaction in block.get('transactions'):
                if 'post_text' in transaction:
                    try:
                        cipher = Crypt(bulletin_secret)
                        decrypted = cipher.decrypt(transaction['post_text'])
                        decrypted.decode('utf8')
                        if not decrypted:
                            continue
                        transaction['post_text'] = decrypted
                        bulletins.append(transaction)
                    except:
                        continue
        return bulletins

    @classmethod
    def get_second_degree_transactions_by_rids(cls, rids):
        if not isinstance(rids, list):
            rids = [rids, ]
        transactions = []
        for block in cls.collection.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}}):
            for transaction in block.get('transactions'):
                if transaction.get('requester_rid') in rids or transaction.get('requested_rid') in rids:
                    transactions.append(transaction)
        return transactions

    @classmethod
    def generate_signature(cls, message):
        key = CBitcoinSecret(cls.private_key)
        signature = SignMessage(key, BitcoinMessage(message, magic=''))
        return signature

    @classmethod
    def get_transaction_by_id(cls, id, instance=False):
        from transaction import Transaction, Input, Crypt
        try:
            block = cls.collection.find({"transactions.id": id})[0]
            for transaction in block['transactions']:
                if instance:
                    return Transaction.from_dict(transaction)
                else:
                    return transaction
        except:
            return None

    @classmethod
    def get_block_reward(cls, block=None):
        if getattr(cls, 'block_rewards', None):
            block_rewards = cls.block_rewards
        else:
            print 'OPENING FILE: Recommend setting block_rewards class attribute'
            try:
                f = open('block_rewards.json', 'r')
                block_rewards = json.loads(f.read())
                f.close()
            except:
                raise BaseException("Block reward file not found")

        latest_block = BU.get_latest_block()
        if latest_block:
            block_count = (latest_block['index'] + 1)
        else:
            block_count = 0


        for t, block_reward in enumerate(block_rewards):
            if block:
                if block.index >= int(block_reward['block']) and block.index < int(block_rewards[t+1]['block']):
                    break
            else:
                if block_count == 0:
                    break
                if block_count >= int(block_reward['block']) and block_count < int(block_rewards[t+1]['block']):
                    break

        return float(block_reward['reward'])

    @classmethod
    def check_double_spend(cls, transaction_obj):
        double_spends = []
        for txn_input in transaction_obj.inputs:
            res = BU.collection.aggregate([
                {"$unwind": "$transactions" },
                {
                    "$project": {
                        "_id": 0,
                        "txn": "$transactions"
                    }
                },
                {"$unwind": "$txn.inputs" },
                {
                    "$project": {
                        "_id": 0,
                        "input_id": "$txn.inputs.id",
                        "public_key": "$txn.public_key"
                    }
                },
                {"$sort": SON([("count", -1), ("input_id", -1)])},
                {"$match":
                    {
                        "public_key": transaction_obj.public_key,
                        "input_id": txn_input.id
                    }
                }
            ])
            double_spends.extend([x for x in res])
        return double_spends
