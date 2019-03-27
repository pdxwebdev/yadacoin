"""
Handlers required by the core chain operations
"""

import json
from yadacoin.basehandlers import BaseHandler
from yadacoin.blockchainutils import BU
from datetime import datetime


class GetLatestBlockHandler(BaseHandler):

    async def get(self):
        """
        :return:
        """
        block = BU.get_latest_block(self.yadacoin_config, self.mongo)
        # Note: I'd rather use an extra field "time_human" than having different formats for a same field name.
        self.render_as_json(self.changetime(block))

    def changetime(self, block):
        block['time'] = datetime.utcfromtimestamp(int(block['time'])).strftime('%Y-%m-%dT%H:%M:%S UTC')
        return block


class GetBlocksHandler(BaseHandler):

    async def get(self):
        start_index = int(self.get_argument("start_index", 0))
        end_index = int(self.get_argument("end_index", 0))
        # TODO: safety, add bound on block# to fetch
        blocks = [x for x in self.mongo.db.blocks.find({
            '$and': [
                {'index':
                    {'$gte': start_index}

                },
                {'index':
                    {'$lte': end_index}
                }
            ]
        }, {'_id': 0}).sort([('index',1)])]

        self.render_as_json(blocks)


class GetBlockHandler(BaseHandler):

    async def get(self):
        """
        :return:
        """
        hash = self.get_argument("hash", 0)
        self.render_as_json(self.mongo.db.blocks.find_one({'hash': hash}, {'_id': 0}))


CORE_HANDLERS = [(r'/get-latest-block', GetLatestBlockHandler), (r'/get-blocks', GetBlocksHandler),
                 (r'/get-block', GetBlockHandler)]
