import json
import hashlib
import os
import argparse
import qrcode
import base64
import time

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
from coincurve import PrivateKey
from pymongo import MongoClient


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
    def get_wallet_unspent_transactions(cls, address, ids=None):
        res = cls.wallet_unspent_worker(address, ids)
        for x in res:
            yield x['txn']

    @classmethod
    def wallet_unspent_worker(cls, address, ids=None):
        mongo_client = MongoClient('localhost')
        unspent_cache = mongo_client.yadacoin.unspent_cache.find({'address': address}).sort([('height', -1)])

        if unspent_cache.count():
            unspent_cache = unspent_cache[0]
            block_height = unspent_cache['height']
        else:
            block_height = 0

        received_query = [
            {
                "$match": {
                    "index": {"$gt": block_height}
                }
            },
            {
                "$match": {
                    "transactions.outputs.to": address
                }
            },
            {"$unwind": "$transactions" },
            {
                "$project": {
                    "_id": 0,
                    "txn": "$transactions",
                    "height": "$index"
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
                    "txn": "$txn",
                    "height": "$height"
                }
            },
            {
                "$sort": {"height": 1}
            }
        ]

        received = BU.collection.aggregate(received_query)

        reverse_public_key = ''
        for x in received:
            mongo_client.yadacoin.unspent_cache.update({
                'address': address,
                'id': x['txn']['id'],
                'height': x['height'],
            },
            {
                'address': address,
                'id': x['txn']['id'],
                'height': x['height'],
                'spent': False,
                'txn': x['txn']
            },
            upsert=True)

            xaddress = str(P2PKHBitcoinAddress.from_pubkey(x['public_key'].decode('hex')))
            if xaddress == address:
                reverse_public_key = x['public_key']


        if not reverse_public_key:
            # no reverse public key means they have never even created a transaction
            # so no need to check for spend, anything sent to them is unspent
            if ids:
                res = mongo_client.yadacoin.unspent_cache.find({'address': address, 'spent': False, 'id': {'$in': ids}})
            else:
                res = mongo_client.yadacoin.unspent_cache.find({'address': address, 'spent': False})
            return res

        spent = BU.collection.aggregate([
            {
                "$match": {
                    "index": {"$gt": block_height}
                }
            },
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
            {
                "$match": {
                    "txn.public_key": reverse_public_key
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

        ids_spent_by_me = []
        for x in spent:
            for i in x['txn']['inputs']:
                mongo_client.yadacoin.unspent_cache.update({
                    'address': address,
                    'id': i['id']
                },
                {
                    '$set': {
                        'spent': True
                    }
                })

        

        if ids:
            res = mongo_client.yadacoin.unspent_cache.find({'address': address, 'spent': False, 'id': {'$in': ids}})
        else:
            res = mongo_client.yadacoin.unspent_cache.find({'address': address, 'spent': False})
        return res

        

    @classmethod
    def get_transactions(cls, raw=False, skip=None):
        if not skip:
            skip = []
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
    def get_transactions_by_rid(cls, selector, rid=False, raw=False, returnheight=True):
        #selectors is old code before we got an RID by sorting the bulletin secrets
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
        mongo_client = MongoClient('localhost')
        transactions_by_rid_cache = mongo_client.yadacoin.transactions_by_rid_cache.find(
                {
                    'raw': True,
                    'rid': rid,
                    'returnheight': returnheight,
                    'selector': {'$in': selectors}
                }
        ).sort([('height', -1)])
        latest_block = BU.get_latest_block()
        if transactions_by_rid_cache.count():
            transactions_by_rid_cache = transactions_by_rid_cache[0]
            block_height = transactions_by_rid_cache['height']
        else:
            block_height = 0
        transactions = []
        blocks = cls.collection.find({"transactions.rid": {"$in": selectors}, "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}, 'index': {'$gt': block_height}})
        for block in blocks:
            for transaction in block.get('transactions'):
                if 'relationship' in transaction:
                    if returnheight:
                        transaction['block_height'] = block['index']
                    if not raw:
                        try:
                            cipher = Crypt(cls.private_key)
                            decrypted = cipher.decrypt(transaction['relationship'])
                            relationship = json.loads(decrypted)
                            transaction['relationship'] = relationship
                        except:
                            continue
                    for selector in selectors:
                        print 'caching transactions_by_rid at height:', block['index']
                        mongo_client.yadacoin.transactions_by_rid_cache.insert(
                            {
                                'raw': raw,
                                'rid': rid,
                                'returnheight': returnheight,
                                'selector': selector,
                                'txn': transaction,
                                'height': block['index']
                            }
                        )
                    transactions.append(transaction)
        if not transactions:
            for selector in selectors:
                mongo_client.yadacoin.transactions_by_rid_cache.insert(
                    {   
                        'raw': raw,
                        'rid': rid,
                        'returnheight': returnheight,
                        'selector': selector,
                        'height': latest_block['index']
                    }   
                )
        for x in mongo_client.yadacoin.transactions_by_rid_cache.find({'raw': raw, 'rid': rid, 'returnheight': returnheight, 'selector': {'$in': selectors}}):
            if 'txn' in x:
                yield x['txn']

    @classmethod
    def get_second_degree_transactions_by_rids(cls, rids, start_height):
        start_height = start_height or 0
        if not isinstance(rids, list):
            rids = [rids, ]
        transactions = []
        for block in cls.collection.find({'$and': [
            {"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}},
            {"index": {"$gt": start_height}}]
        }):
            for transaction in block.get('transactions'):
                if transaction.get('requester_rid') in rids or transaction.get('requested_rid') in rids:
                    transactions.append(transaction)
        return transactions

    @classmethod
    def get_friend_requests(cls, rids):
        if not isinstance(rids, list):
            rids = [rids, ]

        mongo_client = MongoClient('localhost')
        friend_requests_cache = mongo_client.yadacoin.friend_requests_cache.find({'requested_rid': {'$in': rids}}).sort([('height', -1)])
        latest_block = cls.get_latest_block()
        if friend_requests_cache.count():
            friend_requests_cache = friend_requests_cache[0]
            block_height = friend_requests_cache['height']
        else:
            block_height = 0
        transactions = BU.collection.aggregate([
            {
                "$match": {
                    "index": {'$gt': block_height}
                }
            },
            {
                "$match": {
                    "transactions": {"$elemMatch": {"dh_public_key": {'$ne': ''}}},
                    "transactions.requested_rid": {'$in': rids}
                }
            },
            {"$unwind": "$transactions"},
            {
                "$project": {
                    "_id": 0,
                    "txn": "$transactions",
                    "height": "$index"
                }
            },
            {
                "$match": {
                    "txn.dh_public_key": {'$ne': ''},
                    "txn.requested_rid": {'$in': rids}
                }
            },
            {
                "$sort": {"height": 1}
            }
        ])
        had_txns = False
        for x in transactions:
            had_txns = True
            print 'caching friend requests at height:', x['height']
            mongo_client.yadacoin.friend_requests_cache.update({
                'requested_rid': x['txn']['requested_rid'],
                'height': x['height'],
                'id': x['txn']['id']
            },
            {
                'requested_rid': x['txn']['requested_rid'],
                'height': x['height'],
                'id': x['txn']['id'],
                'txn': x['txn']
            },
            upsert=True)

        if not had_txns:
            for rid in rids:
                mongo_client.yadacoin.friend_requests_cache.insert({'height': latest_block['index'], 'requested_rid': rid})

        for x in mongo_client.yadacoin.friend_requests_cache.find({'requested_rid': {'$in': rids}}):
            if 'txn' in x:
                yield x['txn']

    @classmethod
    def get_sent_friend_requests(cls, rids):

        if not isinstance(rids, list):
            rids = [rids, ]

        mongo_client = MongoClient('localhost')
        sent_friend_requests_cache = mongo_client.yadacoin.sent_friend_requests_cache.find({'requester_rid': {'$in': rids}}).sort([('height', -1)])

        if sent_friend_requests_cache.count():
            sent_friend_requests_cache = sent_friend_requests_cache[0]
            block_height = sent_friend_requests_cache['height']
        else:
            block_height = 0

        transactions = BU.collection.aggregate([
            {
                "$match": {
                    "index": {'$gt': block_height}
                }
            },
            {
                "$match": {
                    "transactions": {"$elemMatch": {"dh_public_key": {'$ne': ''}}},
                    "transactions.requester_rid": {'$in': rids}
                }
            },
            {"$unwind": "$transactions"},
            {
                "$project": {
                    "_id": 0,
                    "txn": "$transactions",
                    "height": "$index"
                }
            },
            {
                "$match": {
                    "txn.dh_public_key": {'$ne': ''},
                    "txn.requester_rid": {'$in': rids}
                }
            },
            {
                "$sort": {"height": 1}
            }
        ])

        for x in transactions:
            print 'caching sent friend requests at height:', x['height']
            mongo_client.yadacoin.sent_friend_requests_cache.update({
                'requester_rid': x['txn']['requester_rid'],
                'height': x['height'],
                'id': x['txn']['id']
            },
            {
                'requester_rid': x['txn']['requester_rid'],
                'height': x['height'],
                'id': x['txn']['id'],
                'txn': x['txn']
            },
            upsert=True)

        for x in mongo_client.yadacoin.sent_friend_requests_cache.find({'requester_rid': {'$in': rids}}):
            yield x['txn']

    @classmethod
    def get_messages(cls, rids):

        if not isinstance(rids, list):
            rids = [rids, ]

        mongo_client = MongoClient('localhost')
        messages_cache = mongo_client.yadacoin.messages_cache.find({'rid': {'$in': rids}}).sort([('height', -1)])

        if messages_cache.count():
            messages_cache = messages_cache[0]
            block_height = messages_cache['height']
        else:
            block_height = 0

        transactions = BU.collection.aggregate([
            {
                "$match": {
                    "index": {'$gt': block_height}
                }
            },
            {
                "$match": {
                    "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}},
                    "transactions.dh_public_key": '',
                    "transactions.rid": {'$in': rids}
                }
            },
            {"$unwind": "$transactions"},
            {
                "$project": {
                    "_id": 0,
                    "txn": "$transactions",
                    "height": "$index"
                }
            },
            {
                "$match": {
                    "txn.relationship": {"$ne": ""},
                    "txn.dh_public_key": '',
                    "txn.rid": {'$in': rids}
                }
            },
            {
                "$sort": {"height": 1}
            }
        ])

        for x in transactions:
            print 'caching messages at height:', x['height']
            mongo_client.yadacoin.messages_cache.update({
                'rid': x['txn']['rid'],
                'height': x['height'],
                'id': x['txn']['id']
            },
            {
                'rid': x['txn']['rid'],
                'height': x['height'],
                'id': x['txn']['id'],
                'txn': x['txn']
            },
            upsert=True)

        for x in mongo_client.yadacoin.messages_cache.find({'rid': {'$in': rids}}):
            x['txn']['height'] = x['height']
            yield x['txn']

    @classmethod
    def get_posts(cls, rids):
        from crypt import Crypt

        if not isinstance(rids, list):
            rids = [rids, ]

        mongo_client = MongoClient('localhost')
        posts_cache = mongo_client.yadacoin.posts_cache.find({'rid': {'$in': rids}}).sort([('height', -1)])

        latest_block = cls.get_latest_block()

        if posts_cache.count():
            posts_cache = posts_cache[0]
            block_height = posts_cache['height']
        else:
            block_height = 0
        transactions = BU.collection.aggregate([
            {
                "$match": {
                    "index": {'$gt': block_height}
                }
            },
            {
                "$match": {
                    "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}},
                    "transactions.dh_public_key": '',
                    "transactions.rid": ''
                }
            },
            {"$unwind": "$transactions"},
            {
                "$project": {
                    "_id": 0,
                    "txn": "$transactions",
                    "height": "$index"
                }
            },
            {
                "$match": {
                    "txn.relationship": {"$ne": ""},
                    "txn.dh_public_key": '',
                    "txn.rid": ''
                }
            },
            {
                "$sort": {"height": 1}
            }
        ])

        had_txns = False
        for i, x in enumerate(transactions):
            if i == 0:
                mutual_bulletin_secrets = cls.get_mutual_bulletin_secrets(rids)
                friends = cls.get_transactions_by_rid(rids, rid=True)
                found = False
                for friend in friends:
                    found = True
                    mutual_bulletin_secrets.append(friend['relationship']['bulletin_secret'])
                if not found:
                    break
            for bs in mutual_bulletin_secrets:
                try:
                    crypt = Crypt(hashlib.sha256(bs).hexdigest())
                    decrypted = crypt.decrypt(x['txn']['relationship'])
                    data = json.loads(decrypted)
                    x['txn']['relationship'] = data
                    if 'postText' in data:
                        had_txns = True
                        print 'caching posts at height:', x['height']
                        for rid in rids:
                            mongo_client.yadacoin.posts_cache.update({
                                'rid': rid,
                                'height': x['height'],
                                'id': x['txn']['id']
                            },
                            {
                                'rid': rid,
                                'height': x['height'],
                                'id': x['txn']['id'],
                                'txn': x['txn']
                            },
                            upsert=True)
                except:
                    pass
        if not had_txns:
            for rid in rids:
                mongo_client.yadacoin.posts_cache.insert({'rid': rid, 'height': latest_block['index']})

        for x in mongo_client.yadacoin.posts_cache.find({'rid': {'$in': rids}}):
            if 'txn' in x:
                x['txn']['height'] = x['height']
                yield x['txn']

    @classmethod
    def get_mutual_rids(cls, rid):
        rids = []
        rids.extend([x['requested_rid'] for x in BU.get_sent_friend_requests(rid)])
        rids.extend([x['requester_rid'] for x in BU.get_friend_requests(rid)])
        return rids

    @classmethod
    def get_mutual_bulletin_secrets(cls, rid):
        mutual_bulletin_secrets = []
        for transaction in BU.get_transactions_by_rid(cls.get_mutual_rids(rid), rid=True):
            if 'bulletin_secret' in transaction['relationship']:
                mutual_bulletin_secrets.append(transaction['relationship']['bulletin_secret'])
        return mutual_bulletin_secrets

    @classmethod
    def generate_signature(cls, message):
        key = PrivateKey.from_hex(cls.private_key)
        signature = key.sign(message)
        return base64.b64encode(signature)

    @classmethod
    def get_transaction_by_id(cls, id, instance=False):
        from transaction import Transaction, Input, Crypt
        for block in cls.collection.find({"transactions.id": id}):
            for txn in block['transactions']:
                if txn['id'] == id:
                    if instance:
                        return Transaction.from_dict(txn)
                    else:
                        return txn

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
