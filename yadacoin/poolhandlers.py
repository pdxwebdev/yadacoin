"""
Handlers required by the pool operations
"""
import json
from yadacoin.basehandlers import BaseHandler
from yadacoin.miningpool import MiningPool
from yadacoin.miningpoolpayout import PoolPayer
from yadacoin.block import Block
from yadacoin.chain import CHAIN
from tornado import escape


class PoolHandler(BaseHandler):

    async def get(self):
        if self.config.mp is None:
            self.config.mp = MiningPool()
            #await self.config.mp.refresh()
        """
        if not self.config.mp.block_factory:
            # first init
            self.config.mp.refresh()
        self.mining_index = self.config.mp.block_factory.block.index
        
        block = await self.config.mongo.async_db.blocks.find_one(sort=[('index',-1)])
        # No need to run a query, this is cached in config object:
        # self.config.BU.get_latest_block()['index']:
        if self.config.mp.block_factory.block.index <= block['index']:
            # We're behind
            self.config.mp.refresh()
        """
        # Since self.config.mp is updated by the inner events as soon as possible, no need to refresh anything, it always has the latest block.
        self.render_as_json(await self.config.mp.block_to_mine_info())


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
        result = await self.config.mp.on_miner_nonce(data, address=address)
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


class JSONRPC(BaseHandler):
    async def post(self):
        body = json.loads(self.request.body.decode())
        if body.get('method') == 'getblocktemplate':
            if self.config.mp is None:
                self.config.mp = MiningPool()
            self.render_as_json({
                'id': body.get('id'),
                'method': body.get('method'),
                'jsonrpc': body.get('jsonrpc'),
                'result': await self.config.mp.block_template()
            })
        elif body.get('method') == 'submitblock':
            nonce = body.get('params')[0][145:153]
            address = body.get('params')[1]
            if type(nonce) is not str:
                return self.render_as_json({
                    'id': body.get('id'),
                    'method': body.get('method'),
                    'jsonrpc': body.get('jsonrpc'),
                    'result': {'n':'Ko'}
                })
            if len(nonce) > CHAIN.MAX_NONCE_LEN:
                return self.render_as_json({
                    'id': body.get('id'),
                    'method': body.get('method'),
                    'jsonrpc': body.get('jsonrpc'),
                    'result': {'n':'Ko'}
                })
            result = await self.config.mp.on_miner_nonce(nonce, address=address)
            if result:
                return self.render_as_json({
                    'id': body.get('id'),
                    'method': body.get('method'),
                    'jsonrpc': body.get('jsonrpc'),
                    'result': {'n':'ok'}
                })
            else:
                return self.render_as_json({
                    'id': body.get('id'),
                    'method': body.get('method'),
                    'jsonrpc': body.get('jsonrpc'),
                    'result': {'n':'ko'}
                })


POOL_HANDLERS = [
    (r'/json_rpc', JSONRPC),
    (r'/pool', PoolHandler),
    (r'/pool-submit', PoolSubmitHandler),
    (r'/pool-explorer', PoolExplorer)
]
