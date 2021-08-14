"""
Handlers required by the explorer operations
"""

import base64
import re

from yadacoin.http.base import BaseHandler
from yadacoin.core.common import changetime, abstract_block


class ExplorerSearchHandler(BaseHandler):

    async def get(self):
        term = self.get_argument("term", False)
        if not term:
            self.render_as_json({})
            return

        try:
            res = self.config.mongo.db.blocks.find({'index': int(term)}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_height',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass
        try:
            res = self.config.mongo.db.blocks.find({'public_key': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_height',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass
        try:
            res = self.config.mongo.db.blocks.find({'transactions.public_key': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_height',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass
        try:
            re.search(r'[A-Fa-f0-9]{64}', term).group(0)
            res = self.config.mongo.db.blocks.find({'hash': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_hash',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass

        try:
            base64.b64decode(term.replace(' ', '+'))
            res = self.config.mongo.db.blocks.find({'id': term.replace(' ', '+')}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_id',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass

        try:
            re.search(r'[A-Fa-f0-9]{64}', term).group(0)
            res = self.config.mongo.db.blocks.find({'transactions.hash': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'txn_hash',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass

        try:
            re.search(r'[A-Fa-f0-9]{64}', term).group(0)
            res = self.config.mongo.db.blocks.find({'transactions.rid': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'txn_rid',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass

        try:
            base64.b64decode(term.replace(' ', '+'))
            res = self.config.mongo.db.blocks.find({
                '$or': [
                    {'transactions.id': term.replace(' ', '+')},
                    {'transactions.inputs.id': term.replace(' ', '+')}
                ]},
                {'_id': 0}
            )
            if res.count():
                return self.render_as_json({
                    'resultType': 'txn_id',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass

        try:
            re.search(r'[A-Fa-f0-9]+', term).group(0)
            res = self.config.mongo.db.blocks.find({'transactions.outputs.to': term}, {'_id': 0}).sort('index', -1).limit(10)
            if res.count():
                balance = await self.config.BU.get_wallet_balance(term)
                return self.render_as_json({
                    'balance': "{0:.8f}".format(balance),
                    'resultType': 'txn_outputs_to',
                    'result': [changetime(x) for x in res]
                })
        except Exception as e:
            self.app_log.debug(e)
            return self.render_as_json({})

        try:
            base64.b64decode(term.replace(' ', '+'))
            res = self.config.mongo.db.miner_transactions.find({'id': term.replace(' ', '+')}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'mempool_id',
                    'result': [changetime(x) for x in res]
                })
        except:
            return self.render_as_json({})

        try:
            re.search(r'[A-Fa-f0-9]{64}', term).group(0)
            res = self.config.mongo.db.miner_transactions.find({'hash': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'mempool_hash',
                    'result': [changetime(x) for x in res]
                })
        except:
            return self.render_as_json({})

        try:
            re.search(r'[A-Fa-f0-9]+', term).group(0)
            res = self.config.mongo.db.miner_transactions.find({'outputs.to': term}, {'_id': 0}).sort('index', -1).limit(10)
            if res.count():
                return self.render_as_json({
                    'resultType': 'mempool_outputs_to',
                    'result': [changetime(x) for x in res]
                })
        except:
            return self.render_as_json({})

        try:
            res = self.config.mongo.db.miner_transactions.find({'public_key': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'mempool_public_key',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass

        try:
            res = self.config.mongo.db.miner_transactions.find({'rid': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'mempool_rid',
                    'result': [changetime(x) for x in res]
                })
        except:
            pass

        return self.render_as_json({})


class ExplorerGetBalance(BaseHandler):

    async def get(self):
        address = self.get_argument("address", False)
        if not address:
            self.render_as_json({})
            return
        balance = await self.config.BU.get_wallet_balance(address)
        return self.render_as_json({
            'balance': "{0:.8f}".format(balance)
        })


class ExplorerLatestHandler(BaseHandler):

    async def get(self):
        """Returns abstract of the latest 10 blocks"""
        res = self.config.mongo.async_db.blocks.find({}, {'_id': 0}).sort('index', -1).limit(10)
        res = await res.to_list(length=10)
        print(res[0])
        return self.render_as_json({
            'resultType': 'blocks',
            'result': [changetime(x) for x in res]
        })


class ExplorerLast50(BaseHandler):

    async def get(self):
        """Returns abstract of the latest 50 blocks miners"""
        latest = self.config.LatestBlock.block
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
        async for doc in self.config.mongo.async_db.blocks.aggregate(pipeline):
            miners.append(doc)

        return self.render_as_json(miners)


EXPLORER_HANDLERS = [(r'/explorer-search', ExplorerSearchHandler),
                     (r'/explorer-get-balance', ExplorerGetBalance),
                     (r'/explorer-latest', ExplorerLatestHandler),
                     (r'/explorer-last50', ExplorerLast50),]
