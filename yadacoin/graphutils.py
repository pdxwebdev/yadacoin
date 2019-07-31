import json
import base64
from logging import getLogger
from binascii import unhexlify
from eccsnacks.curve25519 import scalarmult
from yadacoin.transactionutils import TU
# from bitcoin.wallet import P2PKHBitcoinAddress
# from bson.son import SON
# from coincurve import PrivateKey

from yadacoin.config import get_config

# Circular reference
# from yadacoin.block import Block


class GraphUtils(object):
    # Social Graph Helper

    collection = None
    database = None

    def __init__(self):
        self.config = get_config()
        self.mongo = self.config.mongo
        self.app_log = getLogger('tornado.application')

    def get_all_usernames(self):
        return self.config.BU.get_transactions(
            wif=self.config.wif,
            both=False,
            query={'txn.relationship.their_username': {'$exists': True}},
            queryType='allUsernames'
        )

    def get_all_groups(self):
        return self.config.BU.get_transactions(
            wif=self.config.wif,
            both=False,
            query={'txn.relationship.group': {'$exists': True}},
            queryType='allUsernames'
        )

    def search_username(self, username):
        return self.config.BU.get_transactions(
            wif=self.config.wif,
            both=False,
            query={'txn.relationship.their_username': username},
            queryType='searchUsername'
        )

    def search_rid(self, rids):
        if not isinstance(rids, (list, tuple)):
            rids = [rids]
        return self.config.BU.get_transactions(
            wif=self.config.wif,
            both=False,
            query={'txn.rid': {'$in': rids}},
            queryType='searchRid'
        )

    def get_posts(self, rids):
        from yadacoin.crypt import Crypt

        if not isinstance(rids, list):
            rids = [rids, ]

        posts_cache = self.mongo.db.posts_cache.find({
            'rid': {'$in': rids}
        }).sort([('height', -1)])

        latest_block = self.config.BU.get_latest_block()

        if posts_cache.count():
            posts_cache = posts_cache[0]
            block_height = posts_cache['height']
        else:
            block_height = 0
        transactions = self.mongo.db.blocks.aggregate([
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

        fastgraph_transactions = self.mongo.db.fastgraph_transactions.find({
            "txn.relationship": {"$ne": ""},
            "txn.dh_public_key": '',
            "txn.rid": ''
        })

        transactions = [x for x in transactions] + [x for x in fastgraph_transactions]
        # transactions are all posts not yet cached by this rid
        # so we want to grab all bulletin secrets for this rid
        mutual_bulletin_secrets = self.get_mutual_bulletin_secrets(rids)
        friends = []
        for friend in self.get_transactions_by_rid(rids, self.config.bulletin_secret, rid=True):
            if 'their_bulletin_secret' in friend['relationship']:
                friends.append(friend['relationship']['their_bulletin_secret'])
        friends = list(set(friends))
        had_txns = False

        if friends:
            mutual_bulletin_secrets.extend(friends)
            for i, x in enumerate(transactions):
                res = self.mongo.db.posts_cache.find_one({
                    'rid': {'$in': rids},
                    'id': x['txn']['id']
                })
                if res:
                    continue
                for bs in mutual_bulletin_secrets:
                    try:
                        crypt = Crypt(bs)
                        decrypted = crypt.decrypt(x['txn']['relationship'])
                        try:
                            decrypted = base64.b64decode(decrypted)
                        except:
                            raise
                        data = json.loads(decrypted.decode('utf-8'))
                        x['txn']['relationship'] = data
                        if 'postText' in data:
                            had_txns = True
                            self.app_log.debug('caching posts at height: {}'.format(x.get('height', 0)))
                            for rid in rids:
                                self.mongo.db.posts_cache.update({
                                    'rid': rid,
                                    'height': x.get('height', 0),
                                    'id': x['txn']['id'],
                                    'bulletin_secret': bs
                                },
                                    {
                                        'rid': rid,
                                        'height': x.get('height', 0),
                                        'id': x['txn']['id'],
                                        'txn': x['txn'],
                                        'bulletin_secret': bs,
                                        'success': True
                                    },
                                    upsert=True)
                    except Exception as e:
                        for rid in rids:
                            self.mongo.db.posts_cache.update({
                                'rid': rid,
                                'height': x.get('height', 0),
                                'id': x['txn']['id'],
                                'bulletin_secret': bs
                            },
                                {
                                    'rid': rid,
                                    'height': x.get('height', 0),
                                    'id': x['txn']['id'],
                                    'txn': x['txn'],
                                    'bulletin_secret': bs,
                                    'success': False
                                },
                                upsert=True)
                        self.app_log.debug(e)
        if not had_txns:
            for rid in rids:
                self.mongo.db.posts_cache.insert({
                    'rid': rid,
                    'height': latest_block['index'],
                    'success': False
                })

        i = 1
        for x in self.mongo.db.fastgraph_transaction_cache.find({
            'txn.dh_public_key': '',
            'txn.relationship': {'$ne': ''},
            'txn.rid': ''
        }):
            if 'txn' in x:
                x['txn']['height'] = block_height + i
                yield x['txn']
            i += 1

        for x in self.mongo.db.posts_cache.find({'rid': {'$in': rids}, 'success': True}):
            if 'txn' in x:
                x['txn']['height'] = x['height']
                x['txn']['bulletin_secret'] = x['bulletin_secret']
                yield x['txn']

    def get_reacts(self, rids, ids):
        from yadacoin.crypt import Crypt

        if not isinstance(rids, list):
            rids = [rids, ]

        reacts_cache = self.mongo.db.reacts_cache.find({
            'rids': {'$in': rids}
        }).sort([('height', -1)])

        latest_block = self.config.BU.get_latest_block()

        if reacts_cache.count():
            reacts_cache = reacts_cache[0]
            block_height = reacts_cache['height']
        else:
            block_height = 0
        transactions = self.mongo.db.blocks.aggregate([
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

        fastgraph_transactions = self.mongo.db.fastgraph_transactions.find({
            "txn.relationship": {"$ne": ""},
            "txn.dh_public_key": '',
            "txn.rid": ''
        })

        transactions = [x for x in transactions] + [x for x in fastgraph_transactions]
        # transactions are all posts not yet cached by this rid
        # so we want to grab all bulletin secrets for this rid
        mutual_bulletin_secrets = self.get_mutual_bulletin_secrets(rids)
        friends = []
        for friend in self.get_transactions_by_rid(rids, self.config.bulletin_secret, rid=True):
            if 'their_bulletin_secret' in friend['relationship']:
                friends.append(friend['relationship']['their_bulletin_secret'])
        friends = list(set(friends))
        had_txns = False

        if friends:
            mutual_bulletin_secrets.extend(friends)
            for i, x in enumerate(transactions):
                res = self.mongo.db.reacts_cache.find_one({
                    'rid': {'$in': rids},
                    'id': x['txn']['id']
                })
                if res:
                    continue
                for bs in mutual_bulletin_secrets:
                    try:
                        crypt = Crypt(bs)
                        decrypted = crypt.decrypt(x['txn']['relationship'])
                        try:
                            decrypted = base64.b64decode(decrypted)
                        except:
                            raise
                        data = json.loads(decrypted.decode('utf-8'))
                        x['txn']['relationship'] = data
                        if 'react' in data:
                            had_txns = True
                            self.app_log.debug('caching reacts at height: {}'.format(x.get('height', 0)))
                            for rid in rids:
                                self.mongo.db.reacts_cache.update({
                                    'rid': rid,
                                    'height': x.get('height', 0),
                                    'id': x['txn']['id'],
                                    'bulletin_secret': bs
                                },
                                    {
                                        'rid': rid,
                                        'height': x.get('height', 0),
                                        'id': x['txn']['id'],
                                        'txn': x['txn'],
                                        'bulletin_secret': bs,
                                        'success': True
                                    },
                                    upsert=True)
                    except:
                        for rid in rids:
                            self.mongo.db.reacts_cache.update({
                                'rid': rid,
                                'height': x.get('height', 0),
                                'id': x['txn']['id'],
                                'bulletin_secret': bs
                            },
                                {
                                    'rid': rid,
                                    'height': x.get('height', 0),
                                    'id': x['txn']['id'],
                                    'txn': x['txn'],
                                    'bulletin_secret': bs,
                                    'success': False
                                },
                                upsert=True)
        if not had_txns:
            for rid in rids:
                self.mongo.db.reacts_cache.insert({
                    'rid': rid,
                    'height': latest_block['index'],
                    'success': False
                })

        for x in self.mongo.db.reacts_cache.find({'txn.relationship.id': {'$in': ids}, 'success': True}):
            if 'txn' in x and 'id' in x['txn']['relationship']:
                x['txn']['height'] = x['height']
                x['txn']['bulletin_secret'] = x['bulletin_secret']
                yield x['txn']

    def get_comments(self, rids, ids):
        from yadacoin.crypt import Crypt

        if not isinstance(rids, list):
            rids = [rids, ]

        comments_cache = self.mongo.db.comments_cache.find({
            'rids': {'$in': rids}
        }).sort([('height', -1)])

        latest_block = self.config.BU.get_latest_block()

        if comments_cache.count():
            comments_cache = comments_cache[0]
            block_height = comments_cache['height']
        else:
            block_height = 0
        transactions = self.mongo.db.blocks.aggregate([
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

        fastgraph_transactions = self.mongo.db.fastgraph_transactions.find({
            "txn.relationship": {"$ne": ""},
            "txn.dh_public_key": '',
            "txn.rid": ''
        })

        transactions = [x for x in transactions] + [x for x in fastgraph_transactions]
        # transactions are all posts not yet cached by this rid
        # so we want to grab all bulletin secrets for this rid
        mutual_bulletin_secrets = self.get_mutual_bulletin_secrets(rids)
        friends = []
        for friend in self.get_transactions_by_rid(rids, self.config.bulletin_secret, rid=True):
            if 'their_bulletin_secret' in friend['relationship']:
                friends.append(friend['relationship']['their_bulletin_secret'])
        friends = list(set(friends))
        had_txns = False

        if friends:
            mutual_bulletin_secrets.extend(friends)
            for i, x in enumerate(transactions):
                res = self.mongo.db.comments_cache.find_one({
                    'rid': {'$in': rids},
                    'id': x['txn']['id']
                })
                if res:
                    continue
                for bs in mutual_bulletin_secrets:
                    try:
                        crypt = Crypt(bs)
                        decrypted = crypt.decrypt(x['txn']['relationship'])
                        try:
                            decrypted = base64.b64decode(decrypted)
                        except:
                            raise
                        data = json.loads(decrypted.decode('utf-8'))
                        x['txn']['relationship'] = data
                        if 'comment' in data:
                            had_txns = True
                            self.app_log.debug('caching comments at height: {}'.format(x.get('height', 0)))
                            for rid in rids:
                                self.mongo.db.comments_cache.update({
                                    'rid': rid,
                                    'height': x.get('height', 0),
                                    'id': x['txn']['id'],
                                    'bulletin_secret': bs
                                },
                                    {
                                        'rid': rid,
                                        'height': x.get('height', 0),
                                        'id': x['txn']['id'],
                                        'txn': x['txn'],
                                        'bulletin_secret': bs,
                                        'success': True
                                    },
                                    upsert=True)
                    except:
                        for rid in rids:
                            self.mongo.db.comments_cache.update({
                                'rid': rid,
                                'height': x.get('height', 0),
                                'id': x['txn']['id'],
                                'bulletin_secret': bs
                            },
                                {
                                    'rid': rid,
                                    'height': x.get('height', 0),
                                    'id': x['txn']['id'],
                                    'txn': x['txn'],
                                    'bulletin_secret': bs,
                                    'success': False
                                },
                                upsert=True)
        if not had_txns:
            for rid in rids:
                self.mongo.db.comments_cache.insert({
                    'rid': rid,
                    'height': latest_block['index'],
                    'success': False
                })

        for x in self.mongo.db.comments_cache.find({'txn.relationship.id': {'$in': ids}, 'success': True}):
            if 'txn' in x and 'id' in x['txn']['relationship']:
                x['txn']['height'] = x['height']
                x['txn']['bulletin_secret'] = x['bulletin_secret']
                yield x['txn']

    def get_relationships(self, wif):
        # from block import Block
        # from transaction import Transaction
        from yadacoin.crypt import Crypt
        relationships = []
        for block in self.config.BU.get_blocks():
            for transaction in block.get('transactions'):
                try:
                    cipher = Crypt(wif)
                    decrypted = cipher.decrypt(transaction['relationship'])
                    relationship = json.loads(decrypted.decode('latin1'))
                    relationships.append(relationship)
                except:
                    continue
        return relationships

    def get_transaction_by_rid(self, selector, wif=None, bulletin_secret=None, rid=False, raw=False,
                               theirs=False, my=False, public_key=None):
        # from block import Block
        # from transaction import Transaction
        from yadacoin.crypt import Crypt
        if not rid:
            ds = bulletin_secret
            selectors = [
                TU.hash(ds + selector),
                TU.hash(selector + ds)
            ]
        else:
            if not isinstance(selector, list):
                selectors = [selector, ]
            else:
                selectors = selector

            
                    
        def txn_gen():
            res = self.mongo.db.blocks.find(
                {"transactions": {"$elemMatch": {"relationship": {"$ne": ""}, "rid": {"$in": selectors}}}})
            for x in res:
                yield x
        
            res = self.mongo.db.fastgraph_transactions.find(
                {"txn": {"$elemMatch": {"relationship": {"$ne": ""}, "rid": {"$in": selectors}}}})
            for x in res:
                yield x
        
        for block in txn_gen():
            for transaction in block.get('transactions'):
                if theirs and public_key == transaction['public_key']:
                    continue
                if my and public_key != transaction['public_key']:
                    continue
                if not raw:
                    try:
                        cipher = Crypt(wif)
                        decrypted = cipher.decrypt(transaction['relationship'])
                        relationship = json.loads(decrypted.decode('latin1'))
                        transaction['relationship'] = relationship
                    except:
                        continue
                if 'rid' in transaction and transaction['rid'] in selectors:
                    return transaction

    def get_transactions_by_rid(self, selector, bulletin_secret, wif=None, rid=False, raw=False,
                                returnheight=True, lt_block_height=None, requested_rid=False):
        # selectors is old code before we got an RID by sorting the bulletin secrets
        # from block import Block
        # from transaction import Transaction
        from yadacoin.crypt import Crypt

        if not rid:
            ds = bulletin_secret
            selectors = [
                TU.hash(ds + selector),
                TU.hash(selector + ds)
            ]
        else:
            if not isinstance(selector, list):
                selectors = [selector, ]
            else:
                selectors = selector

        transactions_by_rid_cache = self.mongo.db.transactions_by_rid_cache.find(
            {
                'raw': raw,
                'rid': rid,
                'bulletin_secret': bulletin_secret,
                'returnheight': returnheight,
                'selector': {'$in': selectors},
                'requested_rid': requested_rid
            }
        ).sort([('height', -1)])
        latest_block = self.config.BU.get_latest_block()

        transactions = []
        if lt_block_height:
            query = {"transactions.rid": {"$in": selectors}, "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}},
                 'index': {'$lte': lt_block_height}}
            if requested_rid:
                query["transactions.requested_rid"] = {"$in": selectors}
            blocks = self.mongo.db.blocks.find(query)
        else:
            if transactions_by_rid_cache.count():
                transactions_by_rid_cache = transactions_by_rid_cache[0]
                block_height = transactions_by_rid_cache['height']
            else:
                block_height = 0
                
            query = {"transactions.rid": {"$in": selectors}, "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}},
                 'index': {'$gt': block_height}}
            if requested_rid:
                query = {
                    "$or": [
                        {
                            "transactions.rid": {
                                "$in": selectors
                            }
                        },
                        {
                            "transactions.requested_rid": {
                                "$in": selectors
                            }
                        }
                    ],
                    "transactions": {
                        "$elemMatch": {
                            "relationship": {
                                "$ne": ""
                            }
                        }
                    },
                    'index': {
                        '$gt': block_height
                    }
                }
            else:
                query = {
                    "transactions.rid": {
                        "$in": selectors
                    },
                    "transactions": {
                        "$elemMatch": {
                            "relationship": {
                                "$ne": ""
                            }
                        }
                    },
                    'index': {
                        '$gt': block_height
                    }
                }
            blocks = self.mongo.db.blocks.find(query)

        cipher = Crypt(self.config.wif)
        for block in blocks:
            for transaction in block.get('transactions'):
                if 'relationship' in transaction and transaction['relationship']:
                    if returnheight:
                        transaction['height'] = block['index']
                    if not raw:
                        try:
                            decrypted = cipher.decrypt(transaction['relationship'])
                            relationship = json.loads(decrypted.decode('latin1'))
                            transaction['relationship'] = relationship
                        except:
                            continue
                    for selector in selectors:
                        self.app_log.debug('caching transactions_by_rid at height: {}'.format(block['index']))
                        self.mongo.db.transactions_by_rid_cache.insert(
                            {
                                'raw': raw,
                                'rid': rid,
                                'bulletin_secret': bulletin_secret,
                                'returnheight': returnheight,
                                'selector': selector,
                                'txn': transaction,
                                'height': block['index'],
                                'requested_rid': requested_rid
                            }
                        )
                    transactions.append(transaction)
        if not transactions:
            for selector in selectors:
                self.mongo.db.transactions_by_rid_cache.insert(
                    {
                        'raw': raw,
                        'rid': rid,
                        'bulletin_secret': bulletin_secret,
                        'returnheight': returnheight,
                        'selector': selector,
                        'height': latest_block['index'],
                        'requested_rid': requested_rid
                    }
                )

        for ftxn in self.mongo.db.fastgraph_transactions.find({'txn.rid': {'$in': selectors}}):
            if 'txn' in ftxn:
                yield ftxn['txn']

        last_id = ''
        for x in self.mongo.db.transactions_by_rid_cache.find({
            'raw': raw,
            'rid': rid,
            'returnheight': returnheight,
            'selector': {'$in': selectors},
            'requested_rid': requested_rid
        }).sort([('txn.id', 1)]):
            if 'txn' in x and x['txn']['id'] != last_id:
                last_id = x['txn']['id']
                yield x['txn']

    def get_second_degree_transactions_by_rids(self, rids, start_height):
        start_height = start_height or 0
        if not isinstance(rids, list):
            rids = [rids, ]
        transactions = []
        for block in self.mongo.db.blocks.find({'$and': [
            {"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}},
            {"index": {"$gt": start_height}}]
        }):
            for transaction in block.get('transactions'):
                if transaction.get('requester_rid') in rids or transaction.get('requested_rid') in rids:
                    transactions.append(transaction)
        return transactions

    def get_friend_requests(self, rids):
        if not isinstance(rids, list):
            rids = [rids, ]

        friend_requests_cache = self.mongo.db.friend_requests_cache.find({'requested_rid': {'$in': rids}}).sort(
            [('height', -1)])
        latest_block = self.config.BU.get_latest_block()
        if friend_requests_cache.count():
            friend_requests_cache = friend_requests_cache[0]
            block_height = friend_requests_cache['height']
        else:
            block_height = 0
        transactions = self.mongo.db.blocks.aggregate([
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
            self.app_log.debug('caching friend requests at height: {}'.format(x['height']))
            self.mongo.db.friend_requests_cache.update({
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
                self.mongo.db.friend_requests_cache.insert({'height': latest_block['index'], 'requested_rid': rid})

        for x in self.mongo.db.fastgraph_transactions.find({
            'txn.dh_public_key': {'$ne': ''},
            'txn.requested_rid': {'$in': rids}
        }):
            if 'txn' in x:
                yield x['txn']

        for x in self.mongo.db.friend_requests_cache.find({'requested_rid': {'$in': rids}}):
            if 'txn' in x:
                yield x['txn']

    def get_sent_friend_requests(self, rids):

        if not isinstance(rids, list):
            rids = [rids, ]

        sent_friend_requests_cache = self.mongo.db.sent_friend_requests_cache.find({'requester_rid': {'$in': rids}})\
            .sort([('height', -1)])

        if sent_friend_requests_cache.count():
            sent_friend_requests_cache = sent_friend_requests_cache[0]
            block_height = sent_friend_requests_cache['height']
        else:
            block_height = 0

        transactions = self.mongo.db.blocks.aggregate([
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
            self.app_log.debug('caching sent friend requests at height: {}'.format(x['height']))
            self.mongo.db.sent_friend_requests_cache.update({
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

        for x in self.mongo.db.fastgraph_transactions.find({
            'txn.dh_public_key': {'$ne': ''},
            'txn.requester_rid': {'$in': rids}
        }):
            if 'txn' in x:
                yield x['txn']

        for x in self.mongo.db.sent_friend_requests_cache.find({'requester_rid': {'$in': rids}}):
            yield x['txn']

    def get_messages(self, rids):
        if not isinstance(rids, list):
            rids = [rids, ]

        messages_cache = self.mongo.db.messages_cache.find({'rid': {'$in': rids}}).sort([('height', -1)])

        if messages_cache.count():
            messages_cache = messages_cache[0]
            block_height = messages_cache['height']
        else:
            block_height = 0

        transactions = self.mongo.db.blocks.aggregate([
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
            self.app_log.debug('caching messages at height: {}'.format(x['height']))
            self.mongo.db.messages_cache.update({
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

        i = 1
        for x in self.mongo.db.fastgraph_transactions.find({
            'txn.dh_public_key': '',
            'txn.relationship': {'$ne': ''},
            'txn.rid': {'$in': rids}
        }):
            if 'txn' in x:
                x['txn']['height'] = block_height + i
                yield x['txn']
            i += 1

        for x in self.mongo.db.messages_cache.find({'rid': {'$in': rids}}):
            x['txn']['height'] = x['height']
            yield x['txn']

    def get_mutual_rids(self, rid):
        # find the requested and requester rids where rid is present in those fields
        rids = set()
        rids.update([x['requested_rid'] for x in self.get_sent_friend_requests(rid)])
        rids.update([x['requester_rid'] for x in self.get_friend_requests(rid)])
        rids = list(rids)
        return rids

    def get_mutual_bulletin_secrets(self, rid, at_block_height=None):
        # Get the mutual relationships, then get the bulleting secrets for those relationships
        mutual_bulletin_secrets = set()
        rids = self.get_mutual_rids(rid)
        for transaction in self.get_transactions_by_rid(rids, self.config.bulletin_secret, rid=True):
            if 'their_bulletin_secret' in transaction['relationship']:
                mutual_bulletin_secrets.add(transaction['relationship']['their_bulletin_secret'])
        return list(mutual_bulletin_secrets)

    def get_shared_secrets_by_rid(self, rid):
        shared_secrets = []
        dh_public_keys = []
        dh_private_keys = []
        txns = self.get_transactions_by_rid(rid, self.config.bulletin_secret, rid=True)
        for txn in txns:
            if str(txn['public_key']) == str(self.config.public_key) and txn['relationship']['dh_private_key']:
                dh_private_keys.append(txn['relationship']['dh_private_key'])
        txns = self.get_transactions_by_rid(rid, self.config.bulletin_secret, rid=True, raw=True)
        for txn in txns:
            if str(txn['public_key']) != str(self.config.public_key) and txn['dh_public_key']:
                dh_public_keys.append(txn['dh_public_key'])
        for dh_public_key in dh_public_keys:
            for dh_private_key in dh_private_keys:
                shared_secrets.append(scalarmult(unhexlify(dh_private_key).decode('latin1'), unhexlify(dh_public_key).decode('latin1')).encode('latin1'))
        return shared_secrets

    def verify_message(self, rid, message, public_key, txn_id=None):
        from yadacoin.crypt import Crypt
        sent = False
        received = False
        res = self.mongo.db.verify_message_cache.find_one({
            'rid': rid,
            'message.signIn': message.decode('utf-8')
        })
        if res:
            received = True
        else:
            shared_secrets = self.get_shared_secrets_by_rid(rid)
            if txn_id:
                txns = []
                txn = [self.config.BU.get_transaction_by_id(txn_id, include_fastgraph=True)]
                if txn:
                    txns.append(txn)
            else:
                txns = [x for x in self.get_transactions_by_rid(rid, self.config.bulletin_secret, rid=True, raw=True)]
                fastgraph_transactions = self.mongo.db.fastgraph_transactions.find({"txn.rid": rid})
                if fastgraph_transactions.count() > 0:
                    txns.extend([x['txn'] for x in fastgraph_transactions])

            for txn in txns:
                for shared_secret in list(set(shared_secrets)):
                    res = self.mongo.db.verify_message_cache.find_one({
                        'rid': rid,
                        'shared_secret': shared_secret.hex(),
                        'message': message.decode('utf-8'),
                        'id': txn['id']
                    })
                    try:
                        if res and res['success']:
                            signin = res['message']
                        elif res and not res['success']:
                            continue
                        else:
                            cipher = Crypt(shared_secret.hex(), shared=True)
                            try:
                                decrypted = cipher.shared_decrypt(txn['relationship'])
                                signin = json.loads(decrypted.decode('utf-8'))
                                self.mongo.db.verify_message_cache.update({
                                    'rid': rid,
                                    'shared_secret': shared_secret.hex(),
                                    'id': txn['id']
                                },
                                {
                                    'rid': rid,
                                    'shared_secret': shared_secret.hex(),
                                    'id': txn['id'],
                                    'message': signin,
                                    'success': True
                                }
                                , upsert=True)
                            except:
                                continue
                        if u'signIn' in signin and message.decode('utf-8') == signin['signIn']:
                            if public_key != txn['public_key']:
                                received = True
                            else:
                                sent = True
                    except:
                        self.mongo.db.verify_message_cache.update({
                            'rid': rid,
                            'shared_secret': shared_secret.hex(),
                            'id': txn['id']
                        },
                        {
                            'rid': rid,
                            'shared_secret': shared_secret.hex(),
                            'id': txn['id'],
                            'message': '',
                            'success': False
                        }
                        , upsert=True)
        return sent, received
