"""
Handlers required by the pool operations
"""
import json
from yadacoin.basehandlers import BaseHandler
from yadacoin.miningpool import MiningPool
from yadacoin.miningpoolpayout import PoolPayer
from yadacoin.chain import CHAIN
from tornado import escape


class PoolHandler(BaseHandler):

    async def get(self):
        if self.config.mp is None:
            self.mp = MiningPool()
            self.config.mp = self.mp
            await self.mp.refresh()
        """
        if not self.mp.block_factory:
            # first init
            self.mp.refresh()
        self.mining_index = self.mp.block_factory.block.index
        
        block = await self.config.mongo.async_db.blocks.find_one(sort=[('index',-1)])
        # No need to run a query, this is cached in config object:
        # self.config.BU.get_latest_block()['index']:
        if self.mp.block_factory.block.index <= block['index']:
            # We're behind
            self.mp.refresh()
        """
        # Since self.mp is updated by the inner events as soon as possible, no need to refresh anything, it always has the latest block.
        self.render_as_json(await self.mp.block_to_mine_info())


class PoolSubmitHandler(BaseHandler):

    async def post(self):
        block_info = json.loads(self.request.body.decode('utf-8'))
        data = block_info["nonce"]
        address = block_info["address"]
        if type(data) is not str:
            self.render_as_json({'n':'Ko'})
            return
        if len(data) > CHAIN.MAX_NONCE_LEN:
            self.render_as_json({'n': 'Ko'})
            return
        result = await self.mp.on_miner_nonce(data, address=address)
        if result:
            self.render_as_json({'n': 'ok'})
        else:
            self.render_as_json({'n': 'ko'})


class PoolExplorer(BaseHandler):

    async def get(self):
        query = {}
        if self.get_argument("address", False):
            query['address'] = self.get_argument("address")
        if self.get_argument("index", False):
            query['index'] = self.get_argument("index")
        res = self.mongo.db.shares.find_one(query, {'_id': 0}, sort=[('index', -1)])
        if res and query:
            self.render('Pool address: <a href="https://yadacoin.io/explorer?term=%s" target="_blank">%s</a>, Latest block height share: %s'
                        % (self.config.address, self.config.address, res.get('index')))
        else:
            self.render('Pool address: <a href="https://yadacoin.io/explorer?term=%s" target="_blank">%s</a>, No history'
                        % (self.config.address, self.config.address))


POOL_HANDLERS = [(r'/pool', PoolHandler), (r'/pool-submit', PoolSubmitHandler),
                 (r'/pool-explorer', PoolExplorer)]
