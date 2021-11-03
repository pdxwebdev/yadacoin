import json
import base64
import bson
from time import time
from logging import getLogger
from binascii import unhexlify
from eccsnacks.curve25519 import scalarmult
from yadacoin.core.transactionutils import TU
from yadacoin.core.crypt import Crypt
# from bitcoin.wallet import P2PKHBitcoinAddress
# from bson.son import SON
# from coincurve import PrivateKey

from yadacoin.core.config import get_config
from yadacoin.core.transaction import Transaction

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

    async def get_all_usernames(self):
        return self.config.BU.get_transactions(
            wif=self.config.wif,
            both=False,
            query={'txn.relationship.their_username': {'$exists': True}},
            queryType='allUsernames'
        )

    async def get_all_groups(self):
        return self.config.BU.get_transactions(
            wif=self.config.wif,
            both=False,
            query={'txn.relationship.group': {'$exists': True}},
            queryType='allUsernames'
        )

    async def search_username(self, username):
        return self.config.BU.get_transactions(
            wif=self.config.wif,
            both=False,
            query={'txn.relationship.their_username': username},
            queryType='searchUsername'
        )

    async def search_ns_username(self, ns_username, ns_requested_rid=None, id_type=None):

        regx = bson.regex.Regex('^{}'.format(ns_username), 'i')
        query = {
            '$or': [
                {'txn.relationship.their_username': regx},
                {'txn.relationship.my_username': regx}
            ]
        }
        if ns_requested_rid:
            query['txn.requested_rid'] = ns_requested_rid
        if id_type:
            query['txn.relationship.{}'.format(id_type)] = True
        return await self.config.mongo.async_db.name_server.find(query, {'_id': 0}).to_list(100)

    async def search_ns_requested_rid(self, ns_requested_rid, ns_username=None, id_type=None):

        query = {
            'txn.requested_rid': ns_requested_rid
        }
        if ns_username:
            regx = bson.regex.Regex('^{}'.format(ns_username), 'i')
            query['txn.relationship.their_username'] = regx
        if id_type:
            query['txn.relationship.{}'.format(id_type)] = True
        return await self.config.mongo.async_db.name_server.find(query, {'_id': 0}).to_list(100)

    async def search_ns_requester_rid(self, ns_requester_rid, ns_username=None, id_type=None):

        query = {
            'txn.requester_rid': ns_requester_rid
        }
        if ns_username:
            regx = bson.regex.Regex('^{}'.format(ns_username), 'i')
            query['txn.relationship.their_username'] = regx
        if id_type:
            query['txn.relationship.{}'.format(id_type)] = True
        return await self.config.mongo.async_db.name_server.find(query, {'_id': 0}).to_list(100)

    async def search_rid(self, rids):
        if not isinstance(rids, (list, tuple)):
            rids = [rids]
        return self.config.BU.get_transactions(
            wif=self.config.wif,
            both=False,
            query={'txn.rid': {'$in': rids}},
            queryType='searchRid'
        )

    def get_posts(self, rids):
        from yadacoin.core.crypt import Crypt

        if not isinstance(rids, list):
            rids = [rids, ]

        posts_cache = self.mongo.db.posts_cache.find({
            'rid': {'$in': rids}
        }).sort([('height', -1)])

        latest_block = self.config.LatestBlock.block

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
        mutual_username_signatures = self.get_mutual_username_signatures(rids)
        friends = []
        for friend in self.get_transactions_by_rid(rids, self.config.username_signature, rid=True):
            if 'their_username_signature' in friend['relationship']:
                friends.append(friend['relationship']['their_username_signature'])
        friends = list(set(friends))
        had_txns = False

        if friends:
            mutual_username_signatures.extend(friends)
            for i, x in enumerate(transactions):
                res = self.mongo.db.posts_cache.find_one({
                    'rid': {'$in': rids},
                    'id': x['txn']['id']
                })
                if res:
                    continue
                for bs in mutual_username_signatures:
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
                                    'username_signature': bs
                                },
                                {
                                    'rid': rid,
                                    'height': x.get('height', 0),
                                    'id': x['txn']['id'],
                                    'txn': x['txn'],
                                    'username_signature': bs,
                                    'success': True,
                                    'cache_time': time()
                                },
                                upsert=True)
                    except Exception as e:
                        for rid in rids:
                            self.mongo.db.posts_cache.update({
                                'rid': rid,
                                'height': x.get('height', 0),
                                'id': x['txn']['id'],
                                'username_signature': bs
                            },
                            {
                                'rid': rid,
                                'height': x.get('height', 0),
                                'id': x['txn']['id'],
                                'txn': x['txn'],
                                'username_signature': bs,
                                'success': False,
                                'cache_time': time()
                            },
                            upsert=True)
                        self.app_log.debug(e)
        if not had_txns:
            for rid in rids:
                self.mongo.db.posts_cache.insert({
                    'rid': rid,
                    'height': latest_block.index,
                    'success': False,
                    'cache_time': time()
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
                x['txn']['username_signature'] = x['username_signature']
                yield x['txn']

    def get_reacts(self, rids, ids):
        from yadacoin.core.crypt import Crypt

        if not isinstance(rids, list):
            rids = [rids, ]

        reacts_cache = self.mongo.db.reacts_cache.find({
            'rids': {'$in': rids}
        }).sort([('height', -1)])

        latest_block = self.config.LatestBlock.block

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
        mutual_username_signatures = self.get_mutual_username_signatures(rids)
        friends = []
        for friend in self.get_transactions_by_rid(rids, self.config.username_signature, rid=True):
            if 'their_username_signature' in friend['relationship']:
                friends.append(friend['relationship']['their_username_signature'])
        friends = list(set(friends))
        had_txns = False

        if friends:
            mutual_username_signatures.extend(friends)
            for i, x in enumerate(transactions):
                res = self.mongo.db.reacts_cache.find_one({
                    'rid': {'$in': rids},
                    'id': x['txn']['id']
                })
                if res:
                    continue
                for bs in mutual_username_signatures:
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
                                    'username_signature': bs
                                },
                                {
                                    'rid': rid,
                                    'height': x.get('height', 0),
                                    'id': x['txn']['id'],
                                    'txn': x['txn'],
                                    'username_signature': bs,
                                    'success': True,
                                    'cache_time': time()
                                },
                                upsert=True)
                    except:
                        for rid in rids:
                            self.mongo.db.reacts_cache.update({
                                'rid': rid,
                                'height': x.get('height', 0),
                                'id': x['txn']['id'],
                                'username_signature': bs
                            },
                            {
                                'rid': rid,
                                'height': x.get('height', 0),
                                'id': x['txn']['id'],
                                'txn': x['txn'],
                                'username_signature': bs,
                                'success': False,
                                'cache_time': time()
                            },
                            upsert=True)
        if not had_txns:
            for rid in rids:
                self.mongo.db.reacts_cache.insert({
                    'rid': rid,
                    'height': latest_block.index,
                    'success': False,
                    'cache_time': time()
                })

        for x in self.mongo.db.reacts_cache.find({'txn.relationship.id': {'$in': ids}, 'success': True}):
            if 'txn' in x and 'id' in x['txn']['relationship']:
                x['txn']['height'] = x['height']
                x['txn']['username_signature'] = x['username_signature']
                yield x['txn']

    def get_comments(self, rids, ids):
        from yadacoin.core.crypt import Crypt

        if not isinstance(rids, list):
            rids = [rids, ]

        comments_cache = self.mongo.db.comments_cache.find({
            'rids': {'$in': rids}
        }).sort([('height', -1)])

        latest_block = self.config.LatestBlock.block

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
        mutual_username_signatures = self.get_mutual_username_signatures(rids)
        friends = []
        for friend in self.get_transactions_by_rid(rids, self.config.username_signature, rid=True):
            if 'their_username_signature' in friend['relationship']:
                friends.append(friend['relationship']['their_username_signature'])
        friends = list(set(friends))
        had_txns = False

        if friends:
            mutual_username_signatures.extend(friends)
            for i, x in enumerate(transactions):
                res = self.mongo.db.comments_cache.find_one({
                    'rid': {'$in': rids},
                    'id': x['txn']['id']
                })
                if res:
                    continue
                for bs in mutual_username_signatures:
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
                                    'username_signature': bs
                                },
                                {
                                    'rid': rid,
                                    'height': x.get('height', 0),
                                    'id': x['txn']['id'],
                                    'txn': x['txn'],
                                    'username_signature': bs,
                                    'success': True,
                                    'cache_time': time()
                                },
                                upsert=True)
                    except:
                        for rid in rids:
                            self.mongo.db.comments_cache.update({
                                'rid': rid,
                                'height': x.get('height', 0),
                                'id': x['txn']['id'],
                                'username_signature': bs
                            },
                            {
                                'rid': rid,
                                'height': x.get('height', 0),
                                'id': x['txn']['id'],
                                'txn': x['txn'],
                                'username_signature': bs,
                                'success': False,
                                'cache_time': time()
                            },
                            upsert=True)
        if not had_txns:
            for rid in rids:
                self.mongo.db.comments_cache.insert({
                    'rid': rid,
                    'height': latest_block.index,
                    'success': False,
                    'cache_time': time()
                })

        for x in self.mongo.db.comments_cache.find({'txn.relationship.id': {'$in': ids}, 'success': True}):
            if 'txn' in x and 'id' in x['txn']['relationship']:
                x['txn']['height'] = x['height']
                x['txn']['username_signature'] = x['username_signature']
                yield x['txn']

    def get_relationships(self, wif):
        # from block import Block
        # from transaction import Transaction
        from yadacoin.core.crypt import Crypt
        relationships = []
        cipher = None
        for block in self.config.BU.get_blocks():
            for transaction in block.get('transactions'):
                try:
                    if not cipher:
                        cipher = Crypt(wif)
                    decrypted = cipher.decrypt(transaction['relationship'])
                    relationship = json.loads(decrypted.decode('latin1'))
                    relationships.append(relationship)
                except:
                    continue
        return relationships

    def get_transaction_by_rid(self, selector, wif=None, username_signature=None, rid=False, raw=False,
                               theirs=False, my=False, public_key=None):
        # from block import Block
        # from transaction import Transaction
        from yadacoin.core.crypt import Crypt
        if not rid:
            ds = username_signature
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
        cipher = None
        for block in txn_gen():
            for transaction in block.get('transactions'):
                if theirs and public_key == transaction['public_key']:
                    continue
                if my and public_key != transaction['public_key']:
                    continue
                if not raw:
                    try:
                        if not cipher:
                            cipher = Crypt(wif)
                        decrypted = cipher.decrypt(transaction['relationship'])
                        relationship = json.loads(decrypted.decode('latin1'))
                        transaction['relationship'] = relationship
                    except:
                        continue
                if 'rid' in transaction and transaction['rid'] in selectors:
                    return transaction

    async def get_transactions_by_rid_v2(
        self,
        rid=False,
        requested_rid=False,
        requester_rid=False
    ):
        if rid:
            query = {'rid': rid}
            blocks_query = {'transactions.rid': rid}
        elif requested_rid:
            query = {'requested_rid': requested_rid}
            blocks_query = {'transactions.requested_rid': requested_rid}
        elif requester_rid:
            query = {'requester_rid': requester_rid}
            blocks_query = {'transactions.requester_rid': requester_rid}
        async for txn in self.config.mongo.async_db.miner_transactions.find(query, {'_id': 0}):
            yield txn
        async for block in self.config.mongo.async_db.blocks.find(blocks_query, {'_id': 0}):
            for txn in block.get('transactions'):
                if (
                    (rid and rid == txn.get('rid')) or
                    (requested_rid and requested_rid == txn.get('requested_rid')) or
                    (requester_rid and requester_rid == txn.get('requester_rid'))
                ):
                    yield txn



    def get_transactions_by_rid(
        self,
        selector,
        username_signature,
        wif=None,
        rid=False,
        raw=False,
        returnheight=True,
        lt_block_height=None,
        requested_rid=False,
        requester_rid=False,
        inc_mempool=False,
        shared_decrypt=False
    ):
        # selectors is old code before we got an RID by sorting the bulletin secrets
        # from block import Block
        # from transaction import Transaction

        if not rid:
            ds = username_signature
            selectors = [
                TU.hash(ds + selector),
                TU.hash(selector + ds)
            ]
        else:
            if not isinstance(selector, list):
                selectors = [selector, ]
            else:
                selectors = selector

        cipher = None
        for selector in selectors:
            for txn in self.get_transactions_by_rid_worker(selector, username_signature, wif, rid, raw,
                                returnheight, lt_block_height, requested_rid):
                yield txn
            if inc_mempool:
                if requested_rid:
                    query = {
                        'relationship': {'$ne': ''},
                        'requested_rid': requested_rid
                    }
                else:
                    query = {
                        'relationship': {'$ne': ''},
                        'rid': selector
                    }
                res = self.config.mongo.db.miner_transactions.find(query, {
                    '_id': 0
                }).sort([('time', -1)])
                for txn in res:
                    res1 = self.config.mongo.db.miner_transactions_cache.find_one({
                        'id': txn['id'],
                        'username_signature': username_signature,
                        'selector': selector
                    }, {
                        '_id': 0
                    })
                    if res1:
                        if res1.get('success'):
                            yield res1
                        continue
                    if not raw:
                        try:
                            if not cipher:
                                if wif and wif != self.config.wif:
                                    cipher = Crypt(wif)
                                else:
                                    cipher = self.config.cipher
                            txn['username_signature'] = username_signature
                            txn['selector'] = selector
                            if shared_decrypt:
                                decrypted = cipher.shared_decrypt(txn['relationship'])
                            else:
                                decrypted = cipher.decrypt(txn['relationship'])
                            relationship = json.loads(decrypted.decode('latin1'))
                            txn['relationship'] = relationship
                            txn['success'] = True
                            self.mongo.db.miner_transactions_cache.update({
                                'id': txn['id']
                            },
                            {
                                '$set': txn
                            }, upsert=True)
                        except:
                            txn['success'] = False
                            self.mongo.db.miner_transactions_cache.update({
                                'id': txn['id']
                            },
                            {
                                '$set': txn
                            }, upsert=True)
                            continue
                    yield txn

    def get_transactions_by_rid_worker(self, selector, username_signature, wif=None, rid=False, raw=False,
                                returnheight=True, lt_block_height=None, requested_rid=False, shared_decrypt=False):
        from yadacoin.core.crypt import Crypt

        transactions_by_rid_cache = self.mongo.db.transactions_by_rid_cache.find(
            {
                'raw': raw,
                'rid': rid,
                'username_signature': username_signature,
                'returnheight': returnheight,
                'selector': selector,
                'requested_rid': requested_rid
            }
        ).sort([('height', -1)])
        latest_block = self.config.LatestBlock.block

        transactions = []
        if lt_block_height:
            query = {"transactions.rid": selector, "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}},
                 'index': {'$lte': lt_block_height}}
            if requested_rid:
                query["transactions.requested_rid"] = selector
            blocks = self.mongo.db.blocks.find(query)
        else:
            if transactions_by_rid_cache.count():
                transactions_by_rid_cache = transactions_by_rid_cache[0]
                block_height = transactions_by_rid_cache['height']
            else:
                block_height = 0

            query = {"transactions.rid": selector, "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}},
                 'index': {'$gt': block_height}}
            if requested_rid:
                query = {
                    "$or": [
                        {
                            "transactions.rid": selector
                        },
                        {
                            "transactions.requested_rid": selector
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
                    "transactions.rid": selector,
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

        cipher = None
        for block in blocks:
            for transaction in block.get('transactions'):
                if transaction.get('relationship') and (transaction.get('rid') == selector or transaction.get('requested_rid') == selector):
                    if returnheight:
                        transaction['height'] = block['index']
                    if not raw:
                        try:
                            if not cipher:
                                if wif and wif != self.config.wif:
                                    cipher = Crypt(wif)
                                else:
                                    cipher = self.config.wif
                            if shared_decrypt:
                                decrypted = cipher.shared_decrypt(transaction['relationship'])
                            else:
                                decrypted = cipher.decrypt(transaction['relationship'])
                            relationship = json.loads(decrypted.decode('latin1'))
                            transaction['relationship'] = relationship
                        except:
                            continue
                    self.app_log.debug('caching transactions_by_rid at height: {}'.format(block['index']))
                    self.mongo.db.transactions_by_rid_cache.insert(
                        {
                            'raw': raw,
                            'rid': rid,
                            'username_signature': username_signature,
                            'returnheight': returnheight,
                            'selector': selector,
                            'txn': transaction,
                            'height': block['index'],
                            'block_hash': block['hash'],
                            'requested_rid': requested_rid,
                            'cache_time': time()
                        }
                    )
                    transactions.append(transaction)
        if not transactions:
            self.mongo.db.transactions_by_rid_cache.insert(
                {
                    'raw': raw,
                    'rid': rid,
                    'username_signature': username_signature,
                    'returnheight': returnheight,
                    'selector': selector,
                    'height': latest_block.index,
                    'block_hash': latest_block.hash,
                    'requested_rid': requested_rid,
                    'cache_time': time()
                }
            )

        for ftxn in self.mongo.db.fastgraph_transactions.find({'txn.rid': selector}):
            if 'txn' in ftxn:
                yield ftxn['txn']

        last_id = ''
        for x in self.mongo.db.transactions_by_rid_cache.find({
            'raw': raw,
            'rid': rid,
            'returnheight': returnheight,
            'selector': selector,
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
        latest_block = self.config.LatestBlock.block
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
                    "height": "$index",
                    "block_hash": "$hash",
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
                'block_hash': x['block_hash'],
                'id': x['txn']['id'],
                'txn': x['txn'],
                'cache_time': time()
            },
            upsert=True)

        if not had_txns:
            for rid in rids:
                self.mongo.db.friend_requests_cache.insert({
                    'height': latest_block.index,
                    'block_hash': latest_block.hash,
                    'requested_rid': rid,
                    'cache_time': time()
                })

        for x in self.mongo.db.fastgraph_transactions.find({
            'txn.dh_public_key': {'$ne': ''},
            'txn.requested_rid': {'$in': rids}
        }):
            if 'txn' in x:
                yield x['txn']

        for x in self.mongo.db.friend_requests_cache.find({'txn': {'$exists': True}, 'requested_rid': {'$in': rids}}):
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
                    "height": "$index",
                    "block_hash": "$hash"
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
                'block_hash': x['block_hash'],
                'id': x['txn']['id'],
                'txn': x['txn'],
                'cache_time': time()
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

    def get_collection(self, rids=[]):
        if not isinstance(rids, list):
            rids = [rids, ]

        messages_cache = self.mongo.db.messages_cache.find({'rid': {'$in': rids}}).sort([('height', -1)])

        if messages_cache.count():
            messages_cache = messages_cache[0]
            block_height = messages_cache['height']
        else:
            block_height = 0

        if rids:
            match1 = {
                'transactions': {'$elemMatch': {'relationship': {'$ne': ''}}},
                '$or': [
                    {'transactions.rid': {'$in': rids}},
                    {'transactions.requester_rid': {'$in': rids}},
                    {'transactions.requested_rid': {'$in': rids}}
                ]
            }
            match2 = {
                'txn.relationship': {'$ne': ''},
                '$or': [
                    {'txn.rid': {'$in': rids}},
                    {'txn.requester_rid': {'$in': rids}},
                    {'txn.requested_rid': {'$in': rids}}
                ]
            }
        else:
            match1 = {
                'transactions': {'$elemMatch': {'relationship': {'$ne': ''}}},
                '$or': [
                    {'transactions.rid': {'$ne': ''}},
                    {'transactions.requester_rid': {'$ne': ''}},
                    {'transactions.requested_rid': {'$ne': ''}}
                ]
            }
            match2 = {
                'txn.relationship': {'$ne': ''},
                '$or': [
                    {'txn.rid': {'$ne': ''}},
                    {'txn.requester_rid': {'$ne': ''}},
                    {'txn.requested_rid': {'$ne': ''}}
                ]
            }

        transactions = self.mongo.db.blocks.aggregate([
            {
                '$match': {
                    'index': {'$gt': block_height}
                }
            },
            {
                '$match': match1
            },
            {'$unwind': '$transactions'},
            {
                '$project': {
                    '_id': 0,
                    'txn': '$transactions',
                    'height': '$index',
                    'block_hash': '$hash'
                }
            },
            {
                '$match': match2
            },
            {
                '$sort': {'height': 1}
            }
        ])

        for x in transactions:
            self.app_log.debug('caching messages at height: {}'.format(x['height']))
            self.mongo.db.messages_cache.update({
                'rid': x['txn'].get('rid'),
                'requester_rid': x['txn'].get('requester_rid'),
                'requested_rid': x['txn'].get('requested_rid'),
                'height': x['height'],
                'id': x['txn']['id']
            },
            {
                '$set': {
                    'rid': x['txn'].get('rid'),
                    'requester_rid': x['txn'].get('requester_rid'),
                    'requested_rid': x['txn'].get('requested_rid'),
                    'height': x['height'],
                    'block_hash': x['block_hash'],
                    'id': x['txn']['id'],
                    'txn': x['txn'],
                    'cache_time': time()
                }
            },
            upsert=True)

        if rids:
            query = {
                '$or': [
                    {'rid': {'$in': rids}},
                    {'requester_rid': {'$in': rids}},
                    {'requested_rid': {'$in': rids}}
                ]
            }
        else:
            query = {}

        for x in self.mongo.db.messages_cache.find(query):
            x['txn']['height'] = x['height']
            yield x['txn']

    def get_mutual_rids(self, rid):
        # find the requested and requester rids where rid is present in those fields
        rids = set()
        rids.update([x['requested_rid'] for x in self.get_sent_friend_requests(rid)])
        rids.update([x['requester_rid'] for x in self.get_friend_requests(rid)])
        rids = list(rids)
        return rids

    def get_mutual_username_signatures(self, rid, at_block_height=None):
        # Get the mutual relationships, then get the bulleting secrets for those relationships
        mutual_username_signatures = set()
        rids = self.get_mutual_rids(rid)
        for transaction in self.get_transactions_by_rid(rids, self.config.username_signature, rid=True):
            if 'their_username_signature' in transaction['relationship']:
                mutual_username_signatures.add(transaction['relationship']['their_username_signature'])
        return list(mutual_username_signatures)

    def get_shared_secrets_by_rid(self, rid):
        shared_secrets = []
        dh_public_keys = []
        dh_private_keys = []
        txns = self.get_transactions_by_rid(rid, self.config.username_signature, rid=True, inc_mempool=True)
        for txn in txns:
            if str(txn['public_key']) == str(self.config.public_key) and txn['relationship']['dh_private_key']:
                dh_private_keys.append(txn['relationship']['dh_private_key'])
        txns = self.get_transactions_by_rid(rid, self.config.username_signature, rid=True, raw=True, inc_mempool=True)
        for txn in txns:
            if str(txn['public_key']) != str(self.config.public_key) and txn['dh_public_key']:
                dh_public_keys.append(txn['dh_public_key'])
        for dh_public_key in dh_public_keys:
            for dh_private_key in dh_private_keys:
                shared_secrets.append(scalarmult(unhexlify(dh_private_key).decode('latin1'), unhexlify(dh_public_key).decode('latin1')).encode('latin1'))
        return shared_secrets

    async def verify_message(self, rid, message, public_key, txn_id, txn=None):
        from yadacoin.core.crypt import Crypt
        sent = False
        received = False
        res = self.mongo.db.verify_message_cache.find_one({
            'rid': rid,
            'message.signIn': message
        })
        if res:
            received = True
        else:
            shared_secrets = self.get_shared_secrets_by_rid(rid)
            if txn:
                if isinstance(txn, Transaction):
                    await txn.verify()
                else:
                    txn = Transaction.from_dict(txn)
                    await txn.verify()
            else:
                txn = self.config.BU.get_transaction_by_id(txn_id, inc_mempool=True)
                txn = Transaction.from_dict(txn)
                await txn.verify()
            cipher = None
            for shared_secret in list(set(shared_secrets)):
                res = self.mongo.db.verify_message_cache.find_one({
                    'rid': rid,
                    'shared_secret': shared_secret.hex(),
                    'message': message,
                    'id': txn.transaction_signature
                })
                try:
                    if res and res['success']:
                        signin = res['message']
                    elif res and not res['success']:
                        continue
                    else:
                        cipher = Crypt(shared_secret.hex(), shared=True)
                        try:
                            decrypted = cipher.shared_decrypt(txn.relationship)
                            signin = json.loads(decrypted.decode('utf-8'))
                            self.mongo.db.verify_message_cache.update({
                                'rid': rid,
                                'shared_secret': shared_secret.hex(),
                                'id': txn.transaction_signature
                            },
                            {
                                'rid': rid,
                                'shared_secret': shared_secret.hex(),
                                'id': txn.transaction_signature,
                                'message': signin,
                                'success': True,
                                'cache_time': time()
                            }
                            , upsert=True)
                        except:
                            continue
                    if u'signIn' in signin and message == signin['signIn']:
                        if public_key != txn.public_key:
                            received = True
                        else:
                            sent = True
                except:
                    self.mongo.db.verify_message_cache.update({
                        'rid': rid,
                        'shared_secret': shared_secret.hex(),
                        'id': txn.transaction_signature
                    },
                    {
                        'rid': rid,
                        'shared_secret': shared_secret.hex(),
                        'id': txn.transaction_signature,
                        'message': '',
                        'success': False,
                        'cache_time': time()
                    }
                    , upsert=True)
        return sent, received
