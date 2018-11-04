import json
import hashlib
import os
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
from mongo import Mongo
from config import Config


class BU(object):  # Blockchain Utilities
    collection = None
    database = None
    @classmethod
    def get_blocks(cls):
        return Mongo.db.blocks.find({}, {'_id': 0}).sort([('index', 1)])

    @classmethod
    def get_latest_blocks(cls):
        return Mongo.db.blocks.find({}, {'_id': 0}).sort([('index', -1)])

    @classmethod
    def get_latest_block(cls):
        return Mongo.db.blocks.find_one({}, {'_id': 0}, sort=[('index', -1)])

    @classmethod
    def get_block_by_index(cls, index):
        res = Mongo.db.blocks.find({'index': index}, {'_id': 0})
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
    def get_wallet_unspent_transactions(cls, address, ids=None, needed_value=None):
        res = cls.wallet_unspent_worker(address, ids, needed_value)
        for x in res:
            x['txn']['height'] = x['height']
            yield x['txn']

    @classmethod
    def wallet_unspent_worker(cls, address, ids=None, needed_value=None):
        unspent_cache = Mongo.db.unspent_cache.find({'address': address}).sort([('height', -1)])

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

        received = Mongo.db.blocks.aggregate(received_query, allowDiskUse=True)

        reverse_public_key = ''
        for x in received:
            Mongo.db.unspent_cache.update({
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
                res = Mongo.db.unspent_cache.find({'address': address, 'spent': False, 'id': {'$in': ids}})
            else:
                res = Mongo.db.unspent_cache.find({'address': address, 'spent': False})
            return res

        spent = Mongo.db.blocks.aggregate([
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
                Mongo.db.unspent_cache.update({
                    'address': address,
                    'id': i['id']
                },
                {
                    '$set': {
                        'spent': True
                    }
                })

        

        if ids:
            res = Mongo.db.unspent_cache.find({'address': address, 'spent': False, 'id': {'$in': ids}})
        else:
            res = Mongo.db.unspent_cache.find({'address': address, 'spent': False})
        return res

        

    @classmethod
    def get_transactions(cls, raw=False, skip=None):
        if not skip:
            skip = []
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        transactions = []
        for block in Mongo.db.blocks.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}}):
            for transaction in block.get('transactions'):
                try:
                    if transaction.get('id') in skip:
                        continue
                    if 'relationship' not in transaction:
                        continue
                    if not transaction['relationship']:
                        continue
                    if not raw:
                        cipher = Crypt(Config.wif)
                        decrypted = cipher.decrypt(transaction['relationship'])
                        relationship = json.loads(decrypted)
                        transaction['relationship'] = relationship
                    transaction['height'] = block['index']
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
        for block in cls.get_blocks():
            for transaction in block.get('transactions'):
                try:
                    cipher = Crypt(Config.wif)
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
        ds = Config.get_bulletin_secret()
        if not rid:
            selectors = [
                TU.hash(ds+selector),
                TU.hash(selector+ds)
            ]
        else:
            if not isinstance(selector, list):
                selectors = [selector, ]

        for block in Mongo.db.blocks.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}}):
            for transaction in block.get('transactions'):
                if transaction.get('rid') in selectors:
                    if 'relationship' in transaction:
                        if not raw:
                            try:
                                cipher = Crypt(Config.wif)
                                decrypted = cipher.decrypt(transaction['relationship'])
                                relationship = json.loads(decrypted)
                                transaction['relationship'] = relationship
                            except:
                                continue
                    return transaction

    @classmethod
    def get_transactions_by_rid(cls, selector, rid=False, raw=False, returnheight=True, bulletin_secret=None):
        #selectors is old code before we got an RID by sorting the bulletin secrets
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        ds = Config.get_bulletin_secret()

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

        transactions_by_rid_cache = Mongo.db.transactions_by_rid_cache.find(
                {
                    'raw': raw,
                    'rid': rid,
                    'bulletin_secret': bulletin_secret,
                    'returnheight': returnheight,
                    'selector': {'$in': selectors}
                }
        ).sort([('height', -1)])
        latest_block = cls.get_latest_block()
        if transactions_by_rid_cache.count():
            transactions_by_rid_cache = transactions_by_rid_cache[0]
            block_height = transactions_by_rid_cache['height']
        else:
            block_height = 0
        transactions = []
        blocks = Mongo.db.blocks.find({"transactions.rid": {"$in": selectors}, "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}, 'index': {'$gt': block_height}})
        for block in blocks:
            for transaction in block.get('transactions'):
                if 'relationship' in transaction and transaction['relationship']:
                    if returnheight:
                        transaction['height'] = block['index']
                    if not raw:
                        try:
                            cipher = Crypt(Config.wif)
                            decrypted = cipher.decrypt(transaction['relationship'])
                            relationship = json.loads(decrypted)
                            transaction['relationship'] = relationship
                        except:
                            continue
                    for selector in selectors:
                        print 'caching transactions_by_rid at height:', block['index']
                        Mongo.db.transactions_by_rid_cache.insert(
                            {
                                'raw': raw,
                                'rid': rid,
                                'bulletin_secret': bulletin_secret,
                                'returnheight': returnheight,
                                'selector': selector,
                                'txn': transaction,
                                'height': block['index']
                            }
                        )
                    transactions.append(transaction)
        if not transactions:
            for selector in selectors:
                Mongo.db.transactions_by_rid_cache.insert(
                    {   
                        'raw': raw,
                        'rid': rid,
                        'bulletin_secret': bulletin_secret,
                        'returnheight': returnheight,
                        'selector': selector,
                        'height': latest_block['index']
                    }   
                )
        for x in Mongo.db.transactions_by_rid_cache.find({'raw': raw, 'rid': rid, 'returnheight': returnheight, 'selector': {'$in': selectors}}):
            if 'txn' in x:
                yield x['txn']

    @classmethod
    def get_second_degree_transactions_by_rids(cls, rids, start_height):
        start_height = start_height or 0
        if not isinstance(rids, list):
            rids = [rids, ]
        transactions = []
        for block in Mongo.db.blocks.find({'$and': [
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

        friend_requests_cache = Mongo.db.friend_requests_cache.find({'requested_rid': {'$in': rids}}).sort([('height', -1)])
        latest_block = cls.get_latest_block()
        if friend_requests_cache.count():
            friend_requests_cache = friend_requests_cache[0]
            block_height = friend_requests_cache['height']
        else:
            block_height = 0
        transactions = Mongo.db.blocks.aggregate([
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
            Mongo.db.friend_requests_cache.update({
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
                Mongo.db.friend_requests_cache.insert({'height': latest_block['index'], 'requested_rid': rid})

        for x in Mongo.db.friend_requests_cache.find({'requested_rid': {'$in': rids}}):
            if 'txn' in x:
                yield x['txn']

    @classmethod
    def get_sent_friend_requests(cls, rids):

        if not isinstance(rids, list):
            rids = [rids, ]

        sent_friend_requests_cache = Mongo.db.sent_friend_requests_cache.find({'requester_rid': {'$in': rids}}).sort([('height', -1)])

        if sent_friend_requests_cache.count():
            sent_friend_requests_cache = sent_friend_requests_cache[0]
            block_height = sent_friend_requests_cache['height']
        else:
            block_height = 0

        transactions = Mongo.db.blocks.aggregate([
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
            Mongo.db.sent_friend_requests_cache.update({
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

        for x in Mongo.db.sent_friend_requests_cache.find({'requester_rid': {'$in': rids}}):
            yield x['txn']

    @classmethod
    def get_messages(cls, rids):

        if not isinstance(rids, list):
            rids = [rids, ]

        messages_cache = Mongo.db.messages_cache.find({'rid': {'$in': rids}}).sort([('height', -1)])

        if messages_cache.count():
            messages_cache = messages_cache[0]
            block_height = messages_cache['height']
        else:
            block_height = 0

        transactions = Mongo.db.blocks.aggregate([
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
            Mongo.db.messages_cache.update({
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

        for x in Mongo.db.messages_cache.find({'rid': {'$in': rids}}):
            x['txn']['height'] = x['height']
            yield x['txn']

    @classmethod
    def get_posts(cls, rids):
        from crypt import Crypt

        if not isinstance(rids, list):
            rids = [rids, ]

        posts_cache = Mongo.db.posts_cache.find({'rid': {'$in': rids}}).sort([('height', -1)])

        latest_block = cls.get_latest_block()

        if posts_cache.count():
            posts_cache = posts_cache[0]
            block_height = posts_cache['height']
        else:
            block_height = 0
        transactions = Mongo.db.blocks.aggregate([
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
        # transactions are all posts not yet cached by this rid
        # so we want to grab all bulletin secrets for this rid
        mutual_bulletin_secrets = cls.get_mutual_bulletin_secrets(rids)
        friends = []
        for friend in cls.get_transactions_by_rid(rids, rid=True):
            if 'bulletin_secret' in friend['relationship']:
                friends.append(friend['relationship']['bulletin_secret'])
        friends = list(set(friends))
        had_txns = False
        if friends:
            mutual_bulletin_secrets.extend(friends)
            for i, x in enumerate(transactions):
                for bs in mutual_bulletin_secrets:
                    try:
                        crypt = Crypt(hashlib.sha256(bs).hexdigest())
                        decrypted = crypt.decrypt(x['txn']['relationship'])
                        try:
                            decrypted = base64.b64decode(decrypted)
                        except:
                            continue
                        data = json.loads(decrypted)
                        x['txn']['relationship'] = data
                        if 'postText' in decrypted:
                            had_txns = True
                            print 'caching posts at height:', x['height']
                            for rid in rids:
                                Mongo.db.posts_cache.update({
                                    'rid': rid,
                                    'height': x['height'],
                                    'id': x['txn']['id'],
                                    'bulletin_secret': bs
                                },
                                {
                                    'rid': rid,
                                    'height': x['height'],
                                    'id': x['txn']['id'],
                                    'txn': x['txn'],
                                    'bulletin_secret': bs
                                },
                                upsert=True)
                    except:
                        pass
        if not had_txns:
            for rid in rids:
                Mongo.db.posts_cache.insert({'rid': rid, 'height': latest_block['index']})

        for x in Mongo.db.posts_cache.find({'rid': {'$in': rids}}):
            if 'txn' in x:
                x['txn']['height'] = x['height']
                x['txn']['bulletin_secret'] = x['bulletin_secret']
                yield x['txn']

    @classmethod
    def get_mutual_rids(cls, rid):
        # find the requested and requester rids where rid is present in those fields
        rids = set()
        rids.update([x['requested_rid'] for x in cls.get_sent_friend_requests(rid)])
        rids.update([x['requester_rid'] for x in cls.get_friend_requests(rid)])
        rids = list(rids)
        return rids

    @classmethod
    def get_mutual_bulletin_secrets(cls, rid):
        # Get the mutual relationships, then get the bulleting secrets for those relationships
        mutual_bulletin_secrets = set()
        rids = cls.get_mutual_rids(rid)
        for transaction in cls.get_transactions_by_rid(rids, rid=True):
            if 'bulletin_secret' in transaction['relationship']:
                mutual_bulletin_secrets.add(transaction['relationship']['bulletin_secret'])
        return list(mutual_bulletin_secrets)

    @classmethod
    def generate_signature(cls, message):
        key = PrivateKey.from_hex(Config.private_key)
        signature = key.sign(message)
        return base64.b64encode(signature)

    @classmethod
    def get_transaction_by_id(cls, id, instance=False):
        from transaction import Transaction, Input, Crypt
        res = Mongo.db.blocks.find({"transactions.id": id})
        if res.count():
            for block in res:
                for txn in block['transactions']:
                    if txn['id'] == id:
                        if instance:
                            return Transaction.from_dict(txn)
                        else:
                            return txn
        else:
            # fix for bug when unspent cache returns an input 
            # that has been removed from the chain
            Mongo.db.unspent_cache.remove({})
            return None
    
    @classmethod
    def get_version_for_height(cls, height):
        if int(height) <= 14484:
            return 1
        else:
            return 2

    @classmethod
    def get_block_reward(cls, block=None):
        block_rewards = [
            {"block": "0", "reward": "50"},
            {"block": "210000", "reward": "25"},
            {"block": "420000", "reward": "12.5"},
            {"block": "630000", "reward": "6.25"},
            {"block": "840000", "reward": "3.125"},
            {"block": "1050000", "reward": "1.5625"},
            {"block": "1260000", "reward": "0.78125"},
            {"block": "1470000", "reward": "0.390625"},
            {"block": "1680000", "reward": "0.1953125"},
            {"block": "1890000", "reward": "0.09765625"},
            {"block": "2100000", "reward": "0.04882812"},
            {"block": "2310000", "reward": "0.02441406"},
            {"block": "2520000", "reward": "0.01220703"},
            {"block": "2730000", "reward": "0.00610351"},
            {"block": "2940000", "reward": "0.00305175"},
            {"block": "3150000", "reward": "0.00152587"},
            {"block": "3360000", "reward": "0.00076293"},
            {"block": "3570000", "reward": "0.00038146"},
            {"block": "3780000", "reward": "0.00019073"},
            {"block": "3990000", "reward": "0.00009536"},
            {"block": "4200000", "reward": "0.00004768"},
            {"block": "4410000", "reward": "0.00002384"},
            {"block": "4620000", "reward": "0.00001192"},
            {"block": "4830000", "reward": "0.00000596"},
            {"block": "5040000", "reward": "0.00000298"},
            {"block": "5250000", "reward": "0.00000149"},
            {"block": "5460000", "reward": "0.00000074"},
            {"block": "5670000", "reward": "0.00000037"},
            {"block": "5880000", "reward": "0.00000018"},
            {"block": "6090000", "reward": "0.00000009"},
            {"block": "6300000", "reward": "0.00000004"},
            {"block": "6510000", "reward": "0.00000002"},
            {"block": "6720000", "reward": "0.00000001"},
            {"block": "6930000", "reward": "0"}
        ]

        latest_block = cls.get_latest_block()
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
            res = Mongo.db.blocks.aggregate([
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

    @classmethod
    def verify_message(cls, rid, message):
        from crypt import Crypt
        sent = False
        received = False
        txns = cls.get_transactions_by_rid(rid, rid=True, raw=True)
        shared_secrets = TU.get_shared_secrets_by_rid(rid)
        for txn in txns:
            for shared_secret in list(set(shared_secrets)):
                try:
                    cipher = Crypt(shared_secret.encode('hex'), shared=True)
                    decrypted = cipher.shared_decrypt(txn['relationship'])
                    signin = json.loads(decrypted)
                    if u'signIn' in signin and message == signin['signIn']:
                        if Config.public_key != txn['public_key']:
                            received = True
                        else:
                            sent = True
                except:
                    pass
        return sent, received
