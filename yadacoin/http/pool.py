"""
Handlers required by the pool operations
"""
import json

from tornado import escape
from coincurve import PrivateKey, PublicKey

from yadacoin.core.miningpool import MiningPool
from yadacoin.core.miningpoolpayout import PoolPayer
from yadacoin.core.transactionutils import TU
from yadacoin.core.block import Block
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.http.base import BaseHandler


class PoolSharesHandler(BaseHandler):
    async def get(self):
        address = self.get_query_argument('address')
        results = await self.config.mongo.async_db.shares.find({'address': address}, {'_id': 0}).sort([('index', -1)]).to_list(100)
        self.render_as_json({'results': results})


class PoolPayoutsHandler(BaseHandler):
    async def get(self):
        address = self.get_query_argument('address')
        results = await self.config.mongo.async_db.share_payout.find({'txn.outputs.to': address}, {'_id': 0}).sort([('index', -1)]).to_list(100)
        self.render_as_json({'results': results})


POOL_HANDLERS = [
    (r'/shares-for-address', PoolSharesHandler),
    (r'/payouts-for-address', PoolPayoutsHandler),
]
