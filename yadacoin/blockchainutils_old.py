import json
import base64

from yadacoin.transactionutils import TU
from bitcoin.wallet import P2PKHBitcoinAddress
from bson.son import SON
from coincurve import PrivateKey


class _BU(object):  # Blockchain Utilities
    collection = None
    database = None
    @classmethod
    def get_blocks(cls, config, mongo, reverse=False):
        if reverse:
            return mongo.db.blocks.find({}, {'_id': 0}).sort([('index', -1)])
        else:
            return mongo.db.blocks.find({}, {'_id': 0}).sort([('index', 1)])

    @classmethod
    def get_latest_blocks(cls, config, mongo):
        return mongo.db.blocks.find({}, {'_id': 0}).sort([('index', -1)])

    @classmethod
    def get_latest_block(cls, config, mongo):
        return mongo.db.blocks.find_one({}, {'_id': 0}, sort=[('index', -1)])

    @classmethod
    def get_block_by_index(cls, config, mongo, index):
        res = mongo.db.blocks.find({'index': index}, {'_id': 0})
        if res.count():
            return res[0]

    @classmethod
    def get_block_objs(cls, config, mongo):
        from yadacoin.block import Block
        # from yadacoin.transaction import Transaction, Input, Crypt
        blocks = cls.get_blocks(config, mongo)
        block_objs = []
        for block in blocks:
            block_objs.append(Block.from_dict(config, mongo, block))
        return block_objs

    @classmethod
    def get_wallet_balance(cls, config, mongo, address):
        unspent_transactions = cls.get_wallet_unspent_transactions(config, mongo, address)
        unspent_fastgraph_transactions = cls.get_wallet_unspent_fastgraph_transactions(config, mongo, address)
        balance = 0
        used_ids = []
        for txn in unspent_transactions:
            for output in txn['outputs']:
                if address == output['to']:
                    used_ids.append(txn['id'])
                    balance += float(output['value'])
        for txn in unspent_fastgraph_transactions:
            if txn['id'] in used_ids:
                continue
            for output in txn['outputs']:
                if address == output['to']:
                    balance += float(output['value'])
        if balance:
            return balance
        else:
            return 0

    @classmethod
    def get_wallet_unspent_transactions(cls, config, mongo, address, ids=None, needed_value=None):
        res = cls.wallet_unspent_worker(config, mongo, address, ids, needed_value)
        for x in res:
            x['txn']['height'] = x['height']
            yield x['txn']

    @classmethod
    def wallet_unspent_worker(cls, config, mongo, address, ids=None, needed_value=None):
        unspent_cache = mongo.db.unspent_cache.find({'address': address}).sort([('height', -1)])

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

        received = mongo.db.blocks.aggregate(received_query, allowDiskUse=True)

        reverse_public_key = ''
        for x in received:
            # we ALWAYS put our own address in the outputs even if the value is zero.
            # txn is invalid if it isn't present
            mongo.db.unspent_cache.update({
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

            xaddress = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(x['public_key'])))
            if xaddress == address:
                reverse_public_key = x['public_key']

        spent = mongo.db.blocks.aggregate([
            {
                "$match": {
                    "index": {"$gt": block_height}
                }
            },
            {
                "$match": {
                    "$or": [
                        {"transactions.public_key": reverse_public_key},
                        {"transactions.inputs.public_key": reverse_public_key},
                        {"transactions.inputs.address": address}
                    ]
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
                    "$or": [
                        {"txn.public_key": reverse_public_key},
                        {"txn.inputs.public_key": reverse_public_key},
                        {"txn.inputs.address": address}
                    ]
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

        # here we're assuming block/transaction validation ensures the inputs used are valid for this address
        ids_spent_by_me = []
        for x in spent:
            for i in x['txn']['inputs']:
                mongo.db.unspent_cache.update({
                    'address': address,
                    'id': i['id']
                },
                {
                    '$set': {
                        'spent': True
                    }
                })

        if ids:
            res = mongo.db.unspent_cache.find({'address': address, 'spent': False, 'id': {'$in': ids}})
        else:
            res = mongo.db.unspent_cache.find({'address': address, 'spent': False})
        return res
    
    @classmethod
    def get_wallet_unspent_fastgraph_transactions(cls, config, mongo, address):
        result = mongo.db.fastgraph_transactions.find({'txn.outputs.to': address})
        for x in result:
            xaddress = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(x['public_key'])))
            if xaddress == address:
                reverse_public_key = x['public_key']
                spent_on_fastgraph = mongo.db.fastgraph_transactions.find({'public_key': reverse_public_key, 'txn.inputs.id': x['id']})
                spent_on_blockchain = mongo.db.blocks.find({'public_key': reverse_public_key, 'transactions.inputs.id': x['id']})
                if not spent_on_fastgraph.count() and not spent_on_blockchain.count():
                    # x['txn']['height'] = x['height'] # TODO: make height work for frastgraph transactions so we can order messages etc.
                    yield x['txn']
    
    @classmethod
    def get_wallet_spent_fastgraph_transactions(cls, config, mongo, address):
        result = mongo.db.fastgraph_transactions.find({'txn.outputs.to': address})
        for x in result:
            xaddress = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(x['public_key'])))
            if xaddress == address:
                reverse_public_key = x['public_key']
                spent_on_fastgraph = mongo.db.fastgraph_transactions.find({'public_key': reverse_public_key, 'txn.inputs.id': x['id']})
                spent_on_blockchain = mongo.db.blocks.find({'public_key': reverse_public_key, 'transactions.inputs.id': x['id']})
                if spent_on_fastgraph.count() or spent_on_blockchain.count():
                    # x['txn']['height'] = x['height'] # TODO: make height work for frastgraph transactions so we can order messages etc.
                    yield x['txn']

    @classmethod
    def get_transactions(cls, config, mongo, wif, query, queryType, raw=False, both=True, skip=None):
        if not skip:
            skip = []
        #from block import Block
        #from transaction import Transaction
        from yadacoin.crypt import Crypt

        get_transactions_cache = mongo.db.get_transactions_cache.find(
                {
                    'public_key': config.public_key,
                    'raw': raw,
                    'both': both,
                    'skip': skip,
                    'queryType': queryType
                }
        ).sort([('height', -1)])
        latest_block = cls.get_latest_block(config, mongo)
        if get_transactions_cache.count():
            get_transactions_cache = get_transactions_cache[0]
            block_height = get_transactions_cache['height']
        else:
            block_height = 0

        transactions = []
        for block in mongo.db.blocks.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}, 'index': {'$gt': block_height}}):
            for transaction in block.get('transactions'):
                try:
                    if transaction.get('id') in skip:
                        continue
                    if 'relationship' not in transaction:
                        continue
                    if not transaction['relationship']:
                        continue
                    if not raw:
                        cipher = Crypt(wif)
                        decrypted = cipher.decrypt(transaction['relationship'])
                        relationship = json.loads(decrypted)
                        transaction['relationship'] = relationship
                    transaction['height'] = block['index']
                    mongo.db.get_transactions_cache.update(
                        {
                            'public_key': config.public_key,
                            'raw': raw,
                            'both': both,
                            'skip': skip,
                            'height': latest_block['index'],
                            'queryType': queryType,
                            'id': transaction['id']
                        },
                        {
                            'public_key': config.public_key,
                            'raw': raw,
                            'both': both,
                            'skip': skip,
                            'height': latest_block['index'],
                            'txn': transaction,
                            'queryType': queryType,
                            'id': transaction['id']
                        }
                    , upsert=True)
                except:
                    if both:
                        transaction['height'] = block['index']
                        mongo.db.get_transactions_cache.update(
                            {
                                'public_key': config.public_key,
                                'raw': raw,
                                'both': both,
                                'skip': skip,
                                'height': latest_block['index'],
                                'queryType': queryType
                            },
                            {
                                'public_key': config.public_key,
                                'raw': raw,
                                'both': both,
                                'skip': skip,
                                'height': latest_block['index'],
                                'txn': transaction,
                                'queryType': queryType
                            }
                        , upsert=True)
                    continue

        if not transactions:
            mongo.db.get_transactions_cache.insert({
                'public_key': config.public_key,
                'raw': raw,
                'both': both,
                'skip': skip,
                'queryType': queryType,
                'height': latest_block['index']
            })

        fastgraph_transactions = cls.get_fastgraph_transactions(config, mongo, wif, query, queryType, raw=False, both=True, skip=None)

        for fastgraph_transaction in fastgraph_transactions:
            yield fastgraph_transaction


        search_query = {
                'public_key': config.public_key,
                'raw': raw,
                'both': both,
                'skip': skip,
                'queryType': queryType,
                'txn': {'$exists': True}
            }
        search_query.update(query)
        transactions = mongo.db.get_transactions_cache.find(search_query).sort([('height', -1)])

        for transaction in transactions:
            yield transaction['txn']
        
    
    @classmethod
    def get_fastgraph_transactions(cls, config, mongo, secret, query, queryType, raw=False, both=True, skip=None):
        from yadacoin.crypt import Crypt
        for transaction in mongo.db.fastgraph_transactions.find(query):
            if 'txn' in transaction:
                try:
                    if transaction.get('id') in skip:
                        continue
                    if 'relationship' not in transaction:
                        continue
                    if not transaction['relationship']:
                        continue
                    res = mongo.db.fastgraph_transaction_cache.find_one({
                        'txn.id': transaction.get('id'),
                    })
                    if res:
                        continue
                    if not raw:
                        cipher = Crypt(secret)
                        decrypted = cipher.decrypt(transaction['relationship'])
                        relationship = json.loads(decrypted)
                        transaction['relationship'] = relationship
                    mongo.db.fastgraph_transaction_cache.update(
                        {
                            'txn': transaction,
                        }
                    , upsert=True)
                except:
                    continue
        
        for x in mongo.db.fastgraph_transaction_cache.find({
            'txn': {'$exists': True}
        }):
            yield x['tnx']

    @classmethod
    def get_all_usernames(cls, config, mongo):
        return BU.get_transactions(
            config,
            mongo,
            wif=config.wif,
            both=False,
            query={'txn.relationship.their_username': {'$exists': True}},
            queryType='allUsernames'
        )
    
    @classmethod
    def search_username(cls, config, mongo, username):
        return BU.get_transactions(
            config,
            mongo,
            wif=config.wif,
            both=False,
            query={'txn.relationship.their_username': username},
            queryType='searchUsername'
        )
    
    @classmethod
    def search_rid(cls, config, mongo, rid):
        return BU.get_transactions(
            config,
            mongo,
            wif=config.wif,
            both=False,
            query={'txn.rid': rid},
            queryType='searchRid'
        )

    @classmethod
    def get_posts(cls, config, mongo, rids):
        from yadacoin.crypt import Crypt

        if not isinstance(rids, list):
            rids = [rids, ]

        posts_cache = mongo.db.posts_cache.find({
            'rid': {'$in': rids}
        }).sort([('height', -1)])

        latest_block = cls.get_latest_block(config, mongo)

        if posts_cache.count():
            posts_cache = posts_cache[0]
            block_height = posts_cache['height']
        else:
            block_height = 0
        transactions = mongo.db.blocks.aggregate([
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

        fastgraph_transactions = mongo.db.fastgraph_transactions.find({
            "txn.relationship": {"$ne": ""},
            "txn.dh_public_key": '',
            "txn.rid": ''
        })

        transactions = [x for x in transactions] + [x for x in fastgraph_transactions]
        # transactions are all posts not yet cached by this rid
        # so we want to grab all bulletin secrets for this rid
        mutual_bulletin_secrets = BU.get_mutual_bulletin_secrets(config, mongo, rids)
        friends = []
        for friend in BU.get_transactions_by_rid(config, mongo, rids, config.bulletin_secret, rid=True):
            if 'their_bulletin_secret' in friend['relationship']:
                friends.append(friend['relationship']['their_bulletin_secret'])
        friends = list(set(friends))
        had_txns = False

        if friends:
            mutual_bulletin_secrets.extend(friends)
            for i, x in enumerate(transactions):
                res = mongo.db.posts_cache.find_one({
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
                        data = json.loads(decrypted)
                        x['txn']['relationship'] = data
                        if 'postText' in decrypted:
                            had_txns = True
                            print('caching posts at height:', x.get('height', 0))
                            for rid in rids:
                                mongo.db.posts_cache.update({
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
                            mongo.db.posts_cache.update({
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
                        print(e)
        if not had_txns:
            for rid in rids:
                mongo.db.posts_cache.insert({
                    'rid': rid, 
                    'height': latest_block['index'],
                    'success': False
                })

        i = 1
        for x in mongo.db.fastgraph_transaction_cache.find({
            'txn.dh_public_key': '',
            'txn.relationship': {'$ne': ''},
            'txn.rid': ''
        }):
            if 'txn' in x:
                x['txn']['height'] = block_height + i
                yield x['txn']
            i += 1

        for x in mongo.db.posts_cache.find({'rid': {'$in': rids}, 'success': True}):
            if 'txn' in x:
                x['txn']['height'] = x['height']
                x['txn']['bulletin_secret'] = x['bulletin_secret']
                yield x['txn']

    @classmethod
    def get_reacts(cls, config, mongo, rids, ids):
        from yadacoin.crypt import Crypt

        if not isinstance(rids, list):
            rids = [rids, ]

        reacts_cache = mongo.db.reacts_cache.find({
            'rids': {'$in': rids}
        }).sort([('height', -1)])

        latest_block = cls.get_latest_block(config, mongo)

        if reacts_cache.count():
            reacts_cache = reacts_cache[0]
            block_height = reacts_cache['height']
        else:
            block_height = 0
        transactions = mongo.db.blocks.aggregate([
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

        fastgraph_transactions = mongo.db.fastgraph_transactions.find({
            "txn.relationship": {"$ne": ""},
            "txn.dh_public_key": '',
            "txn.rid": ''
        })

        transactions = [x for x in transactions] + [x for x in fastgraph_transactions]
        # transactions are all posts not yet cached by this rid
        # so we want to grab all bulletin secrets for this rid
        mutual_bulletin_secrets = BU.get_mutual_bulletin_secrets(config, mongo, rids)
        friends = []
        for friend in BU.get_transactions_by_rid(config, mongo, rids, config.bulletin_secret, rid=True):
            if 'their_bulletin_secret' in friend['relationship']:
                friends.append(friend['relationship']['their_bulletin_secret'])
        friends = list(set(friends))
        had_txns = False

        if friends:
            mutual_bulletin_secrets.extend(friends)
            for i, x in enumerate(transactions):
                res = mongo.db.reacts_cache.find_one({
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
                        data = json.loads(decrypted)
                        x['txn']['relationship'] = data
                        if 'react' in decrypted:
                            had_txns = True
                            print('caching reacts at height:', x.get('height', 0))
                            for rid in rids:
                                mongo.db.reacts_cache.update({
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
                            mongo.db.reacts_cache.update({
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
                mongo.db.reacts_cache.insert({
                    'rid': rid,
                    'height': latest_block['index'],
                    'success': False
                })

        for x in mongo.db.reacts_cache.find({'txn.relationship.id': {'$in': ids}, 'success': True}):
            if 'txn' in x and 'id' in x['txn']['relationship']:
                x['txn']['height'] = x['height']
                x['txn']['bulletin_secret'] = x['bulletin_secret']
                yield x['txn']

    @classmethod
    def get_comments(cls, config, mongo, rids, ids):
        from yadacoin.crypt import Crypt

        if not isinstance(rids, list):
            rids = [rids, ]

        comments_cache = mongo.db.comments_cache.find({
            'rids': {'$in': rids}
        }).sort([('height', -1)])

        latest_block = cls.get_latest_block(config, mongo)

        if comments_cache.count():
            comments_cache = comments_cache[0]
            block_height = comments_cache['height']
        else:
            block_height = 0
        transactions = mongo.db.blocks.aggregate([
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

        fastgraph_transactions = mongo.db.fastgraph_transactions.find({
            "txn.relationship": {"$ne": ""},
            "txn.dh_public_key": '',
            "txn.rid": ''
        })

        transactions = [x for x in transactions] + [x for x in fastgraph_transactions]
        # transactions are all posts not yet cached by this rid
        # so we want to grab all bulletin secrets for this rid
        mutual_bulletin_secrets = cls.get_mutual_bulletin_secrets(config, mongo, rids)
        friends = []
        for friend in cls.get_transactions_by_rid(config, mongo, rids, config.bulletin_secret, rid=True):
            if 'their_bulletin_secret' in friend['relationship']:
                friends.append(friend['relationship']['their_bulletin_secret'])
        friends = list(set(friends))
        had_txns = False

        if friends:
            mutual_bulletin_secrets.extend(friends)
            for i, x in enumerate(transactions):
                res = mongo.db.comments_cache.find_one({
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
                        data = json.loads(decrypted)
                        x['txn']['relationship'] = data
                        if 'comment' in decrypted:
                            had_txns = True
                            print('caching comments at height:', x.get('height', 0))
                            for rid in rids:
                                mongo.db.comments_cache.update({
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
                            mongo.db.comments_cache.update({
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
                mongo.db.comments_cache.insert({
                    'rid': rid, 
                    'height': latest_block['index'],
                    'success': False
                })

        for x in mongo.db.comments_cache.find({'txn.relationship.id': {'$in': ids}, 'success': True}):
            if 'txn' in x and 'id' in x['txn']['relationship']:
                x['txn']['height'] = x['height']
                x['txn']['bulletin_secret'] = x['bulletin_secret']
                yield x['txn']

    @classmethod
    def get_relationships(cls, config, mongo, wif):
        #from block import Block
        #from transaction import Transaction
        from yadacoin.crypt import Crypt
        relationships = []
        for block in cls.get_blocks(config, mongo):
            for transaction in block.get('transactions'):
                try:
                    cipher = Crypt(wif)
                    decrypted = cipher.decrypt(transaction['relationship'])
                    relationship = json.loads(decrypted)
                    relationships.append(relationship)
                except:
                    continue
        return relationships

    @classmethod
    def get_transaction_by_rid(cls, config, mongo, selector, wif=None, bulletin_secret=None, rid=False, raw=False, theirs=False, my=False, public_key=None):
        #from block import Block
        #from transaction import Transaction
        from yadacoin.crypt import Crypt
        if not rid:
            ds = bulletin_secret
            selectors = [
                TU.hash(ds+selector),
                TU.hash(selector+ds)
            ]
        else:
            if not isinstance(selector, list):
                selectors = [selector, ]
            else:
                selectors = selector

        for block in mongo.db.blocks.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}, "rid": {"$in": selectors}}}}):
            for transaction in block.get('transactions'):
                if theirs and public_key == transaction['public_key']:
                    continue
                if my and public_key != transaction['public_key']:
                    continue
                if not raw:
                    try:
                        cipher = Crypt(wif)
                        decrypted = cipher.decrypt(transaction['relationship'])
                        relationship = json.loads(decrypted)
                        transaction['relationship'] = relationship
                    except:
                        continue
                if 'rid' in transaction and transaction['rid'] in selectors:
                    return transaction

    @classmethod
    def get_transactions_by_rid(cls, config, mongo, selector, bulletin_secret, wif=None, rid=False, raw=False, returnheight=True, lt_block_height=None):
        #selectors is old code before we got an RID by sorting the bulletin secrets
        #from block import Block
        #from transaction import Transaction
        from yadacoin.crypt import Crypt

        if not rid:
            ds = bulletin_secret
            selectors = [
                TU.hash(ds+selector),
                TU.hash(selector+ds)
            ]
        else:
            if not isinstance(selector, list):
                selectors = [selector, ]
            else:
                selectors = selector

        transactions_by_rid_cache = mongo.db.transactions_by_rid_cache.find(
                {
                    'raw': raw,
                    'rid': rid,
                    'bulletin_secret': bulletin_secret,
                    'returnheight': returnheight,
                    'selector': {'$in': selectors}
                }
        ).sort([('height', -1)])
        latest_block = cls.get_latest_block(config, mongo)

        transactions = []
        if lt_block_height:
            blocks = mongo.db.blocks.find({"transactions.rid": {"$in": selectors}, "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}, 'index': {'$lte': lt_block_height}})
        else:
            if transactions_by_rid_cache.count():
                transactions_by_rid_cache = transactions_by_rid_cache[0]
                block_height = transactions_by_rid_cache['height']
            else:
                block_height = 0
            blocks = mongo.db.blocks.find({"transactions.rid": {"$in": selectors}, "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}, 'index': {'$gt': block_height}})

        for block in blocks:
            for transaction in block.get('transactions'):
                if 'relationship' in transaction and transaction['relationship']:
                    if returnheight:
                        transaction['height'] = block['index']
                    if not raw:
                        try:
                            cipher = Crypt(config.wif)
                            decrypted = cipher.decrypt(transaction['relationship'])
                            relationship = json.loads(decrypted)
                            transaction['relationship'] = relationship
                        except:
                            continue
                    for selector in selectors:
                        print('caching transactions_by_rid at height:', block['index'])
                        mongo.db.transactions_by_rid_cache.insert(
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
                mongo.db.transactions_by_rid_cache.insert(
                    {   
                        'raw': raw,
                        'rid': rid,
                        'bulletin_secret': bulletin_secret,
                        'returnheight': returnheight,
                        'selector': selector,
                        'height': latest_block['index']
                    }   
                )
        for x in mongo.db.transactions_by_rid_cache.find({'raw': raw, 'rid': rid, 'returnheight': returnheight, 'selector': {'$in': selectors}}):
            if 'txn' in x:
                yield x['txn']

    @classmethod
    def get_second_degree_transactions_by_rids(cls, config, mongo, rids, start_height):
        start_height = start_height or 0
        if not isinstance(rids, list):
            rids = [rids, ]
        transactions = []
        for block in mongo.db.blocks.find({'$and': [
            {"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}},
            {"index": {"$gt": start_height}}]
        }):
            for transaction in block.get('transactions'):
                if transaction.get('requester_rid') in rids or transaction.get('requested_rid') in rids:
                    transactions.append(transaction)
        return transactions

    @classmethod
    def get_friend_requests(cls, config, mongo, rids):
        if not isinstance(rids, list):
            rids = [rids, ]

        friend_requests_cache = mongo.db.friend_requests_cache.find({'requested_rid': {'$in': rids}}).sort([('height', -1)])
        latest_block = cls.get_latest_block(config, mongo)
        if friend_requests_cache.count():
            friend_requests_cache = friend_requests_cache[0]
            block_height = friend_requests_cache['height']
        else:
            block_height = 0
        transactions = mongo.db.blocks.aggregate([
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
            print('caching friend requests at height:', x['height'])
            mongo.db.friend_requests_cache.update({
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
                mongo.db.friend_requests_cache.insert({'height': latest_block['index'], 'requested_rid': rid})

        for x in mongo.db.fastgraph_transactions.find({
            'txn.dh_public_key': {'$ne': ''},
            'txn.requested_rid': {'$in': rids}
        }):
            if 'txn' in x:
                yield x['txn']

        for x in mongo.db.friend_requests_cache.find({'requested_rid': {'$in': rids}}):
            if 'txn' in x:
                yield x['txn']

    @classmethod
    def get_sent_friend_requests(cls, config, mongo, rids):

        if not isinstance(rids, list):
            rids = [rids, ]

        sent_friend_requests_cache = mongo.db.sent_friend_requests_cache.find({'requester_rid': {'$in': rids}}).sort([('height', -1)])

        if sent_friend_requests_cache.count():
            sent_friend_requests_cache = sent_friend_requests_cache[0]
            block_height = sent_friend_requests_cache['height']
        else:
            block_height = 0

        transactions = mongo.db.blocks.aggregate([
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
            print('caching sent friend requests at height:', x['height'])
            mongo.db.sent_friend_requests_cache.update({
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

        for x in mongo.db.fastgraph_transactions.find({
            'txn.dh_public_key': {'$ne': ''},
            'txn.requester_rid': {'$in': rids}
        }):
            if 'txn' in x:
                yield x['txn']

        for x in mongo.db.sent_friend_requests_cache.find({'requester_rid': {'$in': rids}}):
            yield x['txn']

    @classmethod
    def get_messages(cls, config, mongo, rids):

        if not isinstance(rids, list):
            rids = [rids, ]

        messages_cache = mongo.db.messages_cache.find({'rid': {'$in': rids}}).sort([('height', -1)])

        if messages_cache.count():
            messages_cache = messages_cache[0]
            block_height = messages_cache['height']
        else:
            block_height = 0

        transactions = mongo.db.blocks.aggregate([
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
            print('caching messages at height:', x['height'])
            mongo.db.messages_cache.update({
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
        for x in mongo.db.fastgraph_transactions.find({
            'txn.dh_public_key': '',
            'txn.relationship': {'$ne': ''},
            'txn.rid': {'$in': rids}
        }):
            if 'txn' in x:
                x['txn']['height'] = block_height + i
                yield x['txn']
            i += 1

        for x in mongo.db.messages_cache.find({'rid': {'$in': rids}}):
            x['txn']['height'] = x['height']
            yield x['txn']

    @classmethod
    def get_mutual_rids(cls, config, mongo, rid):
        # find the requested and requester rids where rid is present in those fields
        rids = set()
        rids.update([x['requested_rid'] for x in cls.get_sent_friend_requests(config, mongo, rid)])
        rids.update([x['requester_rid'] for x in cls.get_friend_requests(config, mongo, rid)])
        rids = list(rids)
        return rids

    @classmethod
    def get_mutual_bulletin_secrets(cls, config, mongo, rid, at_block_height=None):
        # Get the mutual relationships, then get the bulleting secrets for those relationships
        mutual_bulletin_secrets = set()
        rids = cls.get_mutual_rids(config, mongo, rid)
        for transaction in cls.get_transactions_by_rid(config, mongo, rids, config.bulletin_secret, rid=True):
            if 'bulletin_secret' in transaction['relationship']:
                mutual_bulletin_secrets.add(transaction['relationship']['bulletin_secret'])
        return list(mutual_bulletin_secrets)

    @classmethod
    def generate_signature(cls, message, private_key):
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message)
        return base64.b64encode(signature).decode("utf-8")

    @classmethod
    def get_transaction_by_id(cls, config, mongo, id, instance=False, give_block=False, include_fastgraph=False):
        from yadacoin.transaction import Transaction
        # from yadacoin.crypt import Crypt
        from yadacoin.fastgraph import FastGraph
        res = mongo.db.blocks.find({"transactions.id": id})
        res2 = mongo.db.fastgraph_transactions.find({"txn.id": id})
        if res.count():
            for block in res:
                if give_block:
                    return block
                for txn in block['transactions']:
                    if txn['id'] == id:
                        if instance:
                            return Transaction.from_dict(config, mongo, block['index'], txn)
                        else:
                            return txn
        elif res2.count() and include_fastgraph:
            if give_block:
                return None
            if instance:
                return FastGraph.from_dict(config, mongo, 0, res2[0]['txn'])
            else:
                return res2[0]['txn']
        else:
            # fix for bug when unspent cache returns an input 
            # that has been removed from the chain
            mongo.db.unspent_cache.remove({})
            return None
    
    @classmethod
    def get_version_for_height(cls, height):
        if int(height) <= 14484:
            return 1
        else:
            return 2

    @classmethod
    def get_block_reward(cls, config, mongo, block=None):
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

        latest_block = cls.get_latest_block(config, mongo)
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
    def check_double_spend(cls, config, mongo, transaction_obj):
        double_spends = []
        for txn_input in transaction_obj.inputs:
            res = mongo.db.blocks.aggregate([
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
    def verify_message(cls, config, mongo, rid, message, public_key, txn_id=None):
        from yadacoin.crypt import Crypt
        sent = False
        received = False
        res = mongo.db.verify_message_cache.find_one({
            'rid': rid,
            'message.signIn': message
        })
        if res:
            received = True
        else:
            shared_secrets = TU.get_shared_secrets_by_rid(config, mongo, rid)
            if txn_id:
                txns = [BU.get_transaction_by_id(config, mongo, txn_id)]
            else:
                txns = [x for x in BU.get_transactions_by_rid(config, mongo, rid, config.bulletin_secret, rid=True, raw=True)]
                fastgraph_transactions = mongo.db.fastgraph_transactions.find({"txn.rid": rid})
                txns.extend([x['txn'] for x in fastgraph_transactions])
            for txn in txns:
                for shared_secret in list(set(shared_secrets)):
                    res = mongo.db.verify_message_cache.find_one({
                        'rid': rid,
                        'shared_secret': shared_secret.hex(),
                        'id': txn['id']
                    })
                    try:
                        if res and res['success']:
                            decrypted = res['message']
                            signin = json.loads(decrypted)
                            received = True
                            return sent, received
                        elif res and not res['success']:
                            continue
                        else:
                            cipher = Crypt(shared_secret.hex(), shared=True)
                            decrypted = cipher.shared_decrypt(txn['relationship'])
                            signin = json.loads(decrypted)
                            mongo.db.verify_message_cache.update({
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
                        if u'signIn' in signin and message == signin['signIn']:
                            if public_key != txn['public_key']:
                                received = True
                            else:
                                sent = True
                    except:
                        mongo.db.verify_message_cache.update({
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
