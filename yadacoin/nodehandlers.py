"""
Handlers required by the core chain operations
"""
from time import time

from yadacoin.basehandlers import BaseHandler
from yadacoin.blockchainutils import BU
from yadacoin.common import ts_to_utc


class GetLatestBlockHandler(BaseHandler):

    async def get(self):
        """
        :return:
        """
        block = BU().get_latest_block()
        # Note: I'd rather use an extra field "time_human" or time_utc than having different formats for a same field name.
        block['time_utc'] = ts_to_utc(block['time'])
        self.render_as_json(block)


class GetBlocksHandler(BaseHandler):

    async def get(self):
        start_index = int(self.get_argument("start_index", 0))
        # safety, add bound on block# to fetch
        end_index = min(int(self.get_argument("end_index", 0)), start_index + 200)  # TODO: store 200 as chain param
        # global chain object with cache of current block height,
        # so we can instantly answer to pulling requests without any db request
        if start_index > self.yadacoin_config.BU.get_latest_block()['index']:
            # early exit without request
            self.render_as_json([])
        else:
            blocks = self.mongo.async_db.blocks.find({
                '$and': [
                    {'index':
                        {'$gte': start_index}

                    },
                    {'index':
                        {'$lte': end_index}
                    }
                ]
            }, {'_id': 0}).sort([('index',1)])
            self.render_as_json(await blocks.to_list(length=500))


class GetBlockHandler(BaseHandler):

    async def get(self):
        """
        :return:
        """
        hash = self.get_argument("hash", 0)
        self.render_as_json(await self.mongo.async_db.blocks.find_one({'hash': hash}, {'_id': 0}))


class GetPeersHandler(BaseHandler):

    async def get(self):
        """
        :return:
        """
        self.render_as_json(self.peers.to_dict())


class GetStatusHandler(BaseHandler):

    async def get(self):
        """
        :return:
        """
        # TODO: complete and cache
        status = self.yadacoin_config.get_status()
        self.render_as_json(status)


NODE_HANDLERS = [(r'/get-latest-block', GetLatestBlockHandler), (r'/get-blocks', GetBlocksHandler),
                 (r'/get-block', GetBlockHandler), (r'/get-peers', GetPeersHandler), (r'/get-status', GetStatusHandler)]
