import json
import base64

# from yadacoin.transactionutils import TU
from bitcoin.wallet import P2PKHBitcoinAddress
from bson.son import SON
from coincurve import PrivateKey
from logging import getLogger

from yadacoin.chain import CHAIN
from yadacoin.config import get_config
# Circular reference
#from yadacoin.block import Block
from time import sleep

GLOBAL_BU = None


def BU():
    return GLOBAL_BU


def set_BU(BU):
    global GLOBAL_BU
    GLOBAL_BU = BU


class BlockChainUtils(object):
    # Blockchain Utilities
    
    collection = None
    database = None
        
    def __init__(self):
        self.config = get_config()
        self.mongo = self.config.mongo
        self.latest_block = None
        self.app_log = getLogger('tornado.application')

    def invalidate_latest_block(self):
        self.latest_block = None

    def get_blocks(self, reverse=False):
        if reverse:
            return self.mongo.db.blocks.find({}, {'_id': 0}).sort([('index', -1)])
        else:
            return self.mongo.db.blocks.find({}, {'_id': 0}).sort([('index', 1)])

    def get_latest_blocks(self):
        return self.mongo.db.blocks.find({}, {'_id': 0}).sort([('index', -1)])

    def get_latest_block(self) -> dict:
        # cached - WARNING : this is a json doc, NOT a block
        if not self.latest_block is None:
            return self.latest_block
        self.latest_block = self.mongo.db.blocks.find_one({}, {'_id': 0}, sort=[('index', -1)])
        self.app_log.debug("last block " + str(self.latest_block))
        return self.latest_block

    def set_latest_block(self, block: dict):
        self.latest_block = block

    async def get_latest_block_async(self) -> dict:
        # cached, async version
        if not self.latest_block is None:
            return self.latest_block
        self.latest_block = await self.mongo.async_db.blocks.find_one({}, {'_id': 0}, sort=[('index', -1)])
        self.app_log.debug("last block async " + self.latest_block)
        return self.latest_block

    def get_block_by_index(self, index):
        res = self.mongo.db.blocks.find({'index': index}, {'_id': 0})
        if res.count():
            return res[0]

    def get_block_objs(self):
        from yadacoin.block import Block
        # from yadacoin.transaction import Transaction, Input, Crypt
        blocks = self.get_blocks()
        block_objs = [Block.from_dict(block) for block in blocks]
        return block_objs

    def get_wallet_balance(self, address):
        # TODO: factorize in an async mongo.method?
        unspent_transactions = self.get_wallet_unspent_transactions(address)
        unspent_fastgraph_transactions = self.get_wallet_unspent_fastgraph_transactions(address)
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

    def get_wallet_unspent_transactions(self, address, ids=None, needed_value=None):
        res = self.wallet_unspent_worker(address, ids, needed_value)
        for x in res:
            x['txn']['height'] = x['height']
            yield x['txn']

    def wallet_unspent_worker(self, address, ids=None, needed_value=None):
        unspent_cache = self.mongo.db.unspent_cache.find({'address': address}).sort([('height', -1)])

        if unspent_cache.count():
            unspent_cache = unspent_cache[0]
            block_height = unspent_cache['height']
        else:
            block_height = 0

        received_query = [
            {
                "$match": {
                    "index": {'$gte': block_height}
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

        received = self.mongo.db.blocks.aggregate(received_query, allowDiskUse=True)

        reverse_public_key = ''
        for x in received:
            # we ALWAYS put our own address in the outputs even if the value is zero.
            # txn is invalid if it isn't present
            self.mongo.db.unspent_cache.update({
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
        
        if reverse_public_key == '':
            received_query = [
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
                }
            ]
            for x in self.mongo.db.blocks.aggregate(received_query, allowDiskUse=True):
                xaddress = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(x['public_key'])))

                if xaddress == address:
                    reverse_public_key = x['public_key']
                    break

        spent = self.mongo.db.blocks.aggregate([
            {
                "$match": {
                    "index": {'$gte': block_height}
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

        spent_fastgraph = self.mongo.db.fastgraph_transactions.aggregate([
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
        for x in spent:
            for i in x['txn']['inputs']:
                self.mongo.db.unspent_cache.update({
                    'address': address,
                    'id': i['id']
                },
                {
                    '$set': {
                        'spent': True
                    }
                },
                multi=True) # TODO: using multi because there is a bug currently that allows double spends on-chain

        for x in spent_fastgraph:
            for i in x['txn']['inputs']:
                self.mongo.db.unspent_cache.update({
                    'address': address,
                    'id': i['id']
                },
                {
                    '$set': {
                        'spent': True
                    }
                },
                multi=True) # TODO: using multi because there is a bug currently that allows double spends on-chain

        if ids:
            res = self.mongo.db.unspent_cache.find({'address': address, 'spent': False, 'id': {'$in': ids}})
        else:
            res = self.mongo.db.unspent_cache.find({'address': address, 'spent': False})
        return res

    def get_wallet_unspent_fastgraph_transactions(self, address):
        result = [x for x in self.mongo.db.fastgraph_transactions.find({'txn.outputs.to': address})]
        reverse_public_key = None
        for x in result:
            xaddress = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(x['public_key'])))
            if xaddress == address:
                reverse_public_key = x['public_key']
                break
        if not reverse_public_key:
            for x in result:
                yield x['txn']
            return
        for x in result:
            spent_on_fastgraph = self.mongo.db.fastgraph_transactions.find({'public_key': reverse_public_key, 'txn.inputs.id': x['id']})
            spent_on_blockchain = self.mongo.db.blocks.find({'public_key': reverse_public_key, 'transactions.inputs.id': x['id']})
            if not spent_on_fastgraph.count() and not spent_on_blockchain.count():
                # x['txn']['height'] = x['height'] # TODO: make height work for frastgraph transactions so we can order messages etc.
                yield x['txn']

    def get_wallet_spent_fastgraph_transactions(self, address):
        result = self.mongo.db.fastgraph_transactions.find({'txn.outputs.to': address})
        for x in result:
            xaddress = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(x['public_key'])))
            if xaddress == address:
                reverse_public_key = x['public_key']
                spent_on_fastgraph = self.mongo.db.fastgraph_transactions.find({'public_key': reverse_public_key, 'txn.inputs.id': x['id']})
                spent_on_blockchain = self.mongo.db.blocks.find({'public_key': reverse_public_key, 'transactions.inputs.id': x['id']})
                if spent_on_fastgraph.count() or spent_on_blockchain.count():
                    # x['txn']['height'] = x['height'] # TODO: make height work for frastgraph transactions so we can order messages etc.
                    yield x['txn']

    def get_transactions(self, wif, query, queryType, raw=False, both=True, skip=None):
        if not skip:
            skip = []
        #from block import Block
        #from transaction import Transaction
        from yadacoin.crypt import Crypt

        get_transactions_cache = self.mongo.db.get_transactions_cache.find(
                {
                    'public_key': self.config.public_key,
                    'raw': raw,
                    'both': both,
                    'skip': skip,
                    'queryType': queryType
                }
        ).sort([('height', -1)])
        latest_block = self.get_latest_block()
        if get_transactions_cache.count():
            get_transactions_cache = get_transactions_cache[0]
            block_height = get_transactions_cache['height']
        else:
            block_height = 0

        cipher = Crypt(wif)
        transactions = []
        for block in self.mongo.db.blocks.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}, 'index': {'$gt': block_height}}):
            for transaction in block.get('transactions'):
                try:
                    if transaction.get('id') in skip:
                        continue
                    if 'relationship' not in transaction:
                        continue
                    if not transaction['relationship']:
                        continue
                    if not raw:
                        decrypted = cipher.decrypt(transaction['relationship'])
                        relationship = json.loads(decrypted.decode('latin1'))
                        transaction['relationship'] = relationship
                    transaction['height'] = block['index']
                    self.mongo.db.get_transactions_cache.update(
                        {
                            'public_key': self.config.public_key,
                            'raw': raw,
                            'both': both,
                            'skip': skip,
                            'height': latest_block['index'],
                            'queryType': queryType,
                            'id': transaction['id']
                        },
                        {
                            'public_key': self.config.public_key,
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
                    self.app_log.debug('failed decrypt. block: {}'.format(block['index']))
                    if both:
                        transaction['height'] = block['index']
                        self.mongo.db.get_transactions_cache.update(
                            {
                                'public_key': self.config.public_key,
                                'raw': raw,
                                'both': both,
                                'skip': skip,
                                'height': latest_block['index'],
                                'queryType': queryType
                            },
                            {
                                'public_key': self.config.public_key,
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
            self.mongo.db.get_transactions_cache.insert({
                'public_key': self.config.public_key,
                'raw': raw,
                'both': both,
                'skip': skip,
                'queryType': queryType,
                'height': latest_block['index']
            })

        fastgraph_transactions = self.get_fastgraph_transactions(wif, query, queryType, raw=False, both=True, skip=None)

        for fastgraph_transaction in fastgraph_transactions:
            yield fastgraph_transaction


        search_query = {
                'public_key': self.config.public_key,
                'raw': raw,
                'both': both,
                'skip': skip,
                'queryType': queryType,
                'txn': {'$exists': True}
            }
        search_query.update(query)
        transactions = self.mongo.db.get_transactions_cache.find(search_query).sort([('height', -1)])

        for transaction in transactions:
            yield transaction['txn']
        

    def get_fastgraph_transactions(self, secret, query, queryType, raw=False, both=True, skip=None):
        from yadacoin.crypt import Crypt
        cipher = Crypt(secret)
        for transaction in self.mongo.db.fastgraph_transactions.find(query):
            if 'txn' in transaction:
                try:
                    if transaction.get('id') in skip:
                        continue
                    if 'relationship' not in transaction:
                        continue
                    if not transaction['relationship']:
                        continue
                    res = self.mongo.db.fastgraph_transaction_cache.find_one({
                        'txn.id': transaction.get('id'),
                    })
                    if res:
                        continue
                    if not raw:
                        decrypted = cipher.decrypt(transaction['relationship'])
                        relationship = json.loads(decrypted.decode('latin1'))
                        transaction['relationship'] = relationship
                    self.mongo.db.fastgraph_transaction_cache.update(
                        {
                            'txn': transaction,
                        }
                    , upsert=True)
                except:
                    continue
        
        for x in self.mongo.db.fastgraph_transaction_cache.find({
            'txn': {'$exists': True}
        }):
            yield x['tnx']

    def generate_signature(self, message, private_key):
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message.encode("utf-8"))
        return base64.b64encode(signature).decode("utf-8")

    def get_transaction_by_id(self, id, instance=False, give_block=False, include_fastgraph=False):
        from yadacoin.transaction import Transaction
        # from yadacoin.crypt import Crypt
        from yadacoin.fastgraph import FastGraph
        res = self.mongo.db.blocks.find({"transactions.id": id})
        res2 = self.mongo.db.fastgraph_transactions.find({"txn.id": id})
        if res.count():
            for block in res:
                if give_block:
                    return block
                for txn in block['transactions']:
                    if txn['id'] == id:
                        if instance:
                            try:
                                return FastGraph.from_dict(block['index'], txn)
                            except:
                                return Transaction.from_dict(block['index'], txn)
                        else:
                            return txn
        elif res2.count() and include_fastgraph:
            if give_block:
                return None
            if instance:
                return FastGraph.from_dict(0, res2[0]['txn'])
            else:
                return res2[0]['txn']
        else:
            # fix for bug when unspent cache returns an input 
            # that has been removed from the chain
            self.mongo.db.unspent_cache.remove({})
            return None

    def get_version_for_height_DEPRECATED(self, height:int):
        # TODO: move to CHAIN
        if int(height) <= 14484:
            return 1
        elif int(height) <= CHAIN.POW_FORK_V2:
            return 2
        else:
            return 3

    def get_block_reward_DEPRECATED(self, block=None):
        # TODO: move to CHAIN
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

        latest_block = self.get_latest_block()
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

    def check_double_spend(self, transaction_obj):
        double_spends = []
        for txn_input in transaction_obj.inputs:
            res = self.mongo.db.blocks.aggregate([
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

