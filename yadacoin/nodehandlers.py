"""
Handlers required by the core chain operations
"""

import json
from time import time
from tornado import escape

from yadacoin.basehandlers import BaseHandler
from yadacoin.blockchainutils import BU
from yadacoin.common import ts_to_utc
from yadacoin.chain import CHAIN


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
        # TODO: dup code between http route and websocket handlers. move to a .mongo method?
        start_index = int(self.get_argument("start_index", 0))
        # safety, add bound on block# to fetch
        end_index = min(int(self.get_argument("end_index", 0)), start_index + CHAIN.MAX_BLOCKS_PER_MESSAGE)
        # global chain object with cache of current block height,
        # so we can instantly answer to pulling requests without any db request
        if start_index > self.config.BU.get_latest_block()['index']:
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
            self.render_as_json(await blocks.to_list(length=CHAIN.MAX_BLOCKS_PER_MESSAGE))


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
        status = self.config.get_status()
        self.render_as_json(status)


class NewBlockHandler(BaseHandler):

    async def post(self):
        """
        A peer does notify us of a new block. This is deprecated, since the new code uses events via websocket to notify of a new block.
        Still, can be used to force notification to important nodes, pools...
        """
        from yadacoin.peers import Peer
        try:
            block_data = escape.json_decode(self.request.body)
            peer_string =  block_data.get('peer')

            if block_data['index'] == 0:
                return
            if int(block_data['version']) != BU().get_version_for_height(block_data['index']):
                print('rejected old version %s from %s' % (block_data['version'], peer_string))
                return
            # Dup code with websocket handler
            self.app_log.info('Post new block: {} {}'.format(peer_string, json.dumps(block_data)))
            # TODO: handle a dict here to store the consensus state
            if not self.peers.syncing:
                self.app_log.debug("Trying to sync on latest block from {}".format(peer_string))
                my_index = self.config.BU.get_latest_block()['index']
                # This is mostly to keep in sync with fast moving blocks from whitelisted peers and pools.
                # ignore if this does not fit.
                if block_data['index'] == my_index + 1:
                    self.app_log.debug("Next index, trying to merge from {}".format(peer_string))
                    peer = Peer.from_string(peer_string)
                    if await self.config.consensus.process_next_block(block_data, peer):
                        pass
                        # if ok, block was inserted and event triggered by import block
                        # await self.peers.on_block_insert(data)
                elif block_data['index'] > my_index + 1:
                    self.app_log.warning("Missing blocks between {} and {} , can't catch up from http route for {}"
                                         .format(my_index, block_data['index'], peer_string))
                    # data = {"start_index": my_index + 1, "end_index": my_index + 1 + CHAIN.MAX_BLOCKS_PER_MESSAGE}
                    # await self.emit('get_blocks', data=data, room=sid)
                else:
                    # Remove later on
                    self.app_log.debug("Old or same index, ignoring {} from {}".format(block_data['index'], peer_string))

        except:
            print('ERROR: failed to get peers, exiting...')


NODE_HANDLERS = [(r'/get-latest-block', GetLatestBlockHandler),
                 (r'/get-blocks', GetBlocksHandler),
                 (r'/get-block', GetBlockHandler),
                 (r'/get-peers', GetPeersHandler),
                 (r'/newblock', NewBlockHandler),
                 (r'/get-status', GetStatusHandler)]
