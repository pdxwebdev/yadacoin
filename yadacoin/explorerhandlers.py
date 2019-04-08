"""
Handlers required by the explorer operations
"""

import base64
import re
from datetime import datetime

from yadacoin.basehandlers import BaseHandler
from yadacoin.blockchainutils import BU


class ExplorerSearchHandler(BaseHandler):

    async def get(self):
        term = self.get_argument("term", False)
        if not term:
            self.render_as_json({})
            return

        try:
            res = self.mongo.db.blocks.find({'index': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_height',
                    'result': [self.changetime(x) for x in res]
                })
        except:
            pass
        try:
            res = self.mongo.db.blocks.find({'public_key': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_height',
                    'result': [self.changetime(x) for x in res]
                })
        except:
            pass
        try:
            res = self.mongo.db.blocks.find({'transactions.public_key': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_height',
                    'result': [self.changetime(x) for x in res]
                })
        except:
            pass
        try:
            re.search(r'[A-Fa-f0-9]{64}', term).group(0)
            res = self.mongo.db.blocks.find({'hash': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_hash',
                    'result': [self.changetime(x) for x in res]
                })
        except:
            pass

        try:
            base64.b64decode(term)
            res = self.mongo.db.blocks.find({'id': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'block_id',
                    'result': [self.changetime(x) for x in res]
                })
        except:
            pass

        try:
            re.search(r'[A-Fa-f0-9]{64}', term).group(0)
            res = self.mongo.db.blocks.find({'transactions.hash': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'txn_hash',
                    'result': [self.changetime(x) for x in res]
                })
        except:
            pass

        try:
            re.search(r'[A-Fa-f0-9]{64}', term).group(0)
            res = self.mongo.db.blocks.find({'transactions.rid': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'txn_rid',
                    'result': [self.changetime(x) for x in res]
                })
        except:
            pass

        try:
            base64.b64decode(term)
            res = self.mongo.db.blocks.find({'transactions.id': term}, {'_id': 0})
            if res.count():
                return self.render_as_json({
                    'resultType': 'txn_id',
                    'result': [self.changetime(x) for x in res]
                })
        except:
            pass

        try:
            re.search(r'[A-Fa-f0-9]+', term).group(0)
            res = self.mongo.db.blocks.find({'transactions.outputs.to': term}, {'_id': 0}).sort('index', -1).limit(10)
            if res.count():
                balance = BU.get_wallet_balance(term)
                return self.render_as_json({
                    'balance': "{0:.8f}".format(balance),
                    'resultType': 'txn_outputs_to',
                    'result': [self.changetime(x) for x in res]
                })
        except:
            return self.render_as_json({})

        return self.render_as_json({})

    def changetime(self, block):
        block['time'] = datetime.utcfromtimestamp(int(block['time'])).strftime('%Y-%m-%dT%H:%M:%S UTC')
        return block


EXPLORER_HANDLERS = [(r'/explorer-search', ExplorerSearchHandler)]
