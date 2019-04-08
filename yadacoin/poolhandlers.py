"""
Handlers required by the pool operations
"""

from yadacoin.basehandlers import BaseHandler
from yadacoin.miningpool import MiningPool
from yadacoin.blockchainutils import BU
from tornado import escape


class PoolHandler(BaseHandler):

    async def get(self):
        if not self.mp:
            self.mp = MiningPool()
            self.settings['mp'] = self.mp

        if not self.mp.block_factory:
            self.mp.refresh()

        if not hasattr(self.mp, 'gen'):
            self.mp.gen = self.mp.nonce_generator()

        self.render_as_json({
            'nonces': next(self.mp.gen),
            'target': self.mp.block_factory.block.target,
            'special_min': self.mp.block_factory.block.special_min,
            'header': self.mp.block_factory.block.header,
            'version': self.mp.block_factory.block.version,
        })


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
            block.signature = BU.generate_signature(block.hash.encode('utf-8'), self.yadacoin_config.private_key)
            try:
                block.verify()
            except Exception as e:
                print('block failed verification', str(e))
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
                # broadcast winning block
                self.mp.broadcast_block(block)
                print('block ok')
            else:
                print('share ok')
            return block.to_json()
        except Exception as e:
            print('block submit error', str(e))
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
            self.yadacoin_config.address, self.yadacoin_config.address, res.get('index'))
        else:
            return 'Pool address: <a href="https://yadacoin.io/explorer?term=%s" target="_blank">%s</a>, No history' % (
                self.yadacoin_config.address, self.yadacoin_config.address)


POOL_HANDLERS = [(r'/pool', PoolHandler), (r'/pool-submit', PoolSubmitHandler),
                 (r'/pool-explorer', PoolExplorer)]
