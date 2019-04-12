"""
Handlers required by the pool operations
"""

from yadacoin.basehandlers import BaseHandler
from yadacoin.miningpool import MiningPool
from tornado import escape


class PoolHandler(BaseHandler):

    async def get(self):
        if self.config.mp is None:
            self.mp = MiningPool()
            self.config.mp = self.mp
            self.mp.refresh()
        """
        if not self.mp.block_factory:
            # first init
            self.mp.refresh()
        self.mining_index = self.mp.block_factory.block.index

        if self.mining_index <= self.config.BU.get_latest_block()['index']:
            # We're behind
            self.mp.refresh()
        """
        self.render_as_json(self.mp.block_to_mine_info())


class PoolSubmitHandler(BaseHandler):

    async def post(self):
        try:
            pass
            block = self.mp.block_factory.block
            block.target = self.mp.block_factory.block.target
            block.version = self.mp.block_factory.block.version
            block.special_min = self.mp.block_factory.block.special_min
            block.hash = self.get_query_arguments("hash")
            block.nonce = self.get_query_arguments("nonce")
            block.signature = self.config.BU.generate_signature(block.hash.encode('utf-8'), self.config.private_key)
            try:
                block.verify()
            except Exception as e:
                self.app_log.warning('Block failed verification {}'.format(e))
                self.mongo.db.log.insert({
                    'error': 'block failed verification',
                    'block': block.to_dict(),
                    'request': escape.json_decode(self.request.body)
                })
                return '', 400

            # submit share
            self.mongo.db.shares.update({
                'address': self.get_query_arguments("address"),
                'index': block.index,
                'hash': block.hash
            },
            {
                'address': self.get_query_arguments("address"),
                'index': block.index,
                'hash': block.hash,
                'block': block.to_dict()
            }, upsert=True)

            if int(block.target) > int(block.hash, 16) or block.special_min:
                # TODO: quickly insert into our own chain first.
                # broadcast winning block
                self.mp.broadcast_block(block)
                self.app_log.info('Block ok')
            else:
                self.app_log.warning('Share ok')
            return block.to_json()
        except Exception as e:
            self.app_log.warning('Block submit error {}'.format(e))
            return 'error', 400


class PoolExplorer(BaseHandler):

    async def get(self):
        query = {}
        if self.get_argument("address", False):
            query['address'] = self.get_argument("address")
        if self.get_argument("index", False):
            query['index'] = self.get_argument("index")
        res = self.mongo.db.shares.find_one(query, {'_id': 0}, sort=[('index', -1)])
        if res and query:
            return 'Pool address: <a href="https://yadacoin.io/explorer?term=%s" target="_blank">%s</a>, Latest block height share: %s' % (
                self.config.address, self.config.address, res.get('index'))
        else:
            return 'Pool address: <a href="https://yadacoin.io/explorer?term=%s" target="_blank">%s</a>, No history' % (
                self.config.address, self.config.address)


POOL_HANDLERS = [(r'/pool', PoolHandler), (r'/pool-submit', PoolSubmitHandler),
                 (r'/pool-explorer', PoolExplorer)]