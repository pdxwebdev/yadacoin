"""
Handlers required by the explorer operations
"""

import base64
import re

from yadacoin.basehandlers import BaseHandler
from yadacoin.blockchainutils import BU
from yadacoin.common import changetime, abstract_block


class ExplorerSearchHandler(BaseHandler):

    async def get(self):
        term = self.get_argument("term", False)
        if not term:
            self.render_as_json({})
            return

        try:
            res = self.mongo.db.blocks.find({'index': int(term)}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_height',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass
        try:
            res = self.mongo.db.blocks.find({'public_key': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_height',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass
        try:
            res = self.mongo.db.blocks.find({'transactions.public_key': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_height',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass
        try:
            re.search(r'[A-Fa-f0-9]{64}', term).group(0)
            res = self.mongo.db.blocks.find({'hash': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_hash',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass

        try:
            base64.b64decode(term)
            res = self.mongo.db.blocks.find({'id': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_id',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass

        try:
            re.search(r'[A-Fa-f0-9]{64}', term).group(0)
            res = self.mongo.db.blocks.find({'transactions.hash': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'txn_hash',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass

        try:
            re.search(r'[A-Fa-f0-9]{64}', term).group(0)
            res = self.mongo.db.blocks.find({'transactions.rid': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'txn_rid',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass

        try:
            base64.b64decode(term)
            res = self.mongo.db.blocks.find({'transactions.id': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'txn_id',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass

        try:
            re.search(r'[A-Fa-f0-9]+', term).group(0)
            res = self.mongo.db.blocks.find({'transactions.outputs.to': term}, {'_id': 0}).sort('index', -1).limit(10)
            if res.count():
                balance = BU().get_wallet_balance(term)
                return self.render_as_json({
                    'balance': "{0:.8f}".format(balance),
                    'resultType': 'txn_outputs_to',
                    'result': [changetime(x) for x in res]
                })
        except:
            return self.render_as_json({})

        return self.render_as_json({})


class ExplorerLatestHandler(BaseHandler):

    async def get(self):
        """Returns abstract of the latest 10 blocks"""
        res = self.mongo.async_db.blocks.find({}, {'_id': 0}).sort('index', -1).limit(10)
        res = await res.to_list(length=10)
        print(res[0])
        return self.render_as_json({
            'resultType': 'blocks',
            'result': [abstract_block(x) for x in res]
        })


class ExplorerLast50(BaseHandler):

    async def get(self):
        """Returns abstract of the latest 50 blocks miners"""
        latest = self.config.BU.get_latest_block()
        pipeline = [
                    {
                       '$match' : { 'index' : {'$gte': latest['index'] - 50} }
                    },
                    {
                        '$project':
                        {
                            'outputs': 1,
                            'transaction': {'$arrayElemAt': ["$transactions",-1] }
                        }
                    },
                    {
                        '$project':
                        {
                            'outputs': 1,
                            'output': {'$arrayElemAt': ["$transaction.outputs",0] }
                        }
                    }
                    ,
                    {
                        '$project':
                        {
                            'outputs': 1,
                            'to':"$output.to"
                        }
                    },
                    {
                        '$group': {
                            '_id': "$to",
                            'count': {
                                '$sum': 1
                            }
                        }
                    }
                    ,
                    {
                        '$sort': {"count": -1}
                    }
                   ]

        miners = []
        async for doc in self.mongo.async_db.blocks.aggregate(pipeline):
            miners.append(doc)

        return self.render_as_json(miners)


EXPLORER_HANDLERS = [(r'/explorer-search', ExplorerSearchHandler),
                     (r'/explorer-latest', ExplorerLatestHandler),
                     (r'/explorer-last50', ExplorerLast50)]
