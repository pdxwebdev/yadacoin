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


class PoolHashRateHandler(BaseHandler):
    async def get(self):
        address = self.get_query_argument('address')
        last_share = await self.config.mongo.async_db.shares.find_one({'address': address}, {'_id': 0}, sort=[('time', -1)])
        if not last_share:
            return self.render_as_json({'result': 0})
        miner_hashrate_seconds = self.config.miner_hashrate_seconds if hasattr(self.config, 'miner_hashrate_seconds') else 600
        number_of_shares = await self.config.mongo.async_db.shares.count_documents({'address': address, 'time': { '$gt': last_share['time'] - miner_hashrate_seconds}})
        miner_hashrate = (number_of_shares * 69905) / miner_hashrate_seconds
        self.render_as_json({'miner_hashrate': int(miner_hashrate)})


class PoolScanMissedPayoutsHandler(BaseHandler):
    async def get(self):
        await self.config.pp.do_payout({'index': 0})
        self.render_as_json({'status': True})


POOL_HANDLERS = [
    (r'/shares-for-address', PoolSharesHandler),
    (r'/payouts-for-address', PoolPayoutsHandler),
    (r'/hashrate-for-address', PoolHashRateHandler),
    (r'/scan-missed-payouts', PoolScanMissedPayoutsHandler),
]
