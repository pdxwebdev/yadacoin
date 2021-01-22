import sys
sys.setrecursionlimit(1000000)
from sys import exc_info
from os import path
import json
import logging
import datetime
from traceback import format_exc
from time import time
from urllib3.exceptions import *
from asyncio import sleep as async_sleep

from asyncstdlib import anext
from bitcoin.wallet import P2PKHBitcoinAddress
from pymongo.errors import DuplicateKeyError
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.httputil import HTTPHeaders
from tornado import ioloop
from tornado.iostream import StreamClosedError

from yadacoin.core.chain import CHAIN
from yadacoin.core.config import get_config
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.block import Block
from yadacoin.core.transaction import (
    InvalidTransactionException,
    InvalidTransactionSignatureException,
    MissingInputTransactionException,
    NotEnoughMoneyException
)
from yadacoin.core.latestblock import LatestBlock
from yadacoin.tcpsocket.node import NodeSocketServer
from yadacoin.core.peer import Peer
from yadacoin.tcpsocket.base import BaseRPC


class Consensus(object):

    lowest = CHAIN.MAX_TARGET

    @classmethod
    async def init_async(
        cls,
        debug=False,
        prevent_genesis=False,
        target=None,
        special_target=None
    ):
        self = cls()
        self.app_log = logging.getLogger("tornado.application")
        self.debug = debug
        self.config = get_config()
        self.mongo = self.config.mongo
        self.prevent_genesis = prevent_genesis
        self.target = target
        self.special_target = special_target
        self.syncing = False

        if self.config.LatestBlock.block:
            self.latest_block = self.config.LatestBlock.block
        else:
            if not self.prevent_genesis:
                await self.config.BU.insert_genesis()
        return self

    async def verify_existing_blockchain(self, reset=False):
        self.app_log.info('verifying existing blockchain')
        existing_blockchain = await Blockchain.init_async(self.config.mongo.async_db.blocks.find({}).sort([('index', 1)]))
        result = await existing_blockchain.verify()
        if result['verified']:
            print('Block height: %s | time: %s' % (self.latest_block.index, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            return True
        else:
            self.app_log.critical(result)
            if reset:
                if 'last_good_block' in result:
                    self.mongo.db.blocks.remove({"index": {"$gt": result['last_good_block'].index}}, multi=True)
                else:
                    self.mongo.db.blocks.remove({"index": {"$gt": 0}}, multi=True)
                self.app_log.debug("{} {}".format(result['message'], '...truncating'))
            else:
                self.app_log.critical("{} - reset False, not truncating - DID NOT VERIFY".format(result['message']))
            self.config.BU.latest_block = None

    def remove_pending_transactions_now_in_chain(self, block):
        #remove transactions from miner_transactions collection in the blockchain
        self.mongo.db.miner_transactions.remove({'id': {'$in': [x['id'] for x in block['block']['transactions']]}}, {'_id': 0})

    def remove_fastgraph_transactions_now_in_chain(self, block):
        self.mongo.db.fastgraph_transactions.remove({'id': {'$in': [x['id'] for x in block['block']['transactions']]}}, {'_id': 0})

    async def insert_consensus_block(self, block, peer):
        self.app_log.info('inserting new consensus block for height and peer: %s %s' % (block.index, peer.to_string()))
        try:
            block.verify()
        except:
            return
        await self.mongo.async_db.consensus.delete_many({
            'index': block.index,
            'peer.rid': peer.rid
        })
        await self.mongo.async_db.consensus.insert_one({
            'block': block.to_dict(),
            'index': block.index,
            'id': block.signature,
            'peer': peer.to_dict()
        })

    async def sync_bottom_up(self):
        #bottom up syncing
        
        last_latest = self.latest_block
        self.latest_block = self.config.LatestBlock.block
        if last_latest:
            if self.latest_block.index > last_latest.index:
                self.app_log.info('Block height: %s | time: %s' % (self.latest_block.index, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        latest_consensus = await self.mongo.async_db.consensus.find_one({
            'index': self.latest_block.index + 1,
            'block.version': CHAIN.get_version_for_height(self.latest_block.index + 1),
            'ignore': {'$ne': True}
        })
        if latest_consensus:
            self.remove_pending_transactions_now_in_chain(latest_consensus)
            self.remove_fastgraph_transactions_now_in_chain(latest_consensus)
            latest_consensus = await Block.from_dict( latest_consensus['block'])
            if self.debug:
                self.app_log.info("Latest consensus_block {}".format(latest_consensus.index))

            records = await self.mongo.async_db.consensus.find({
                'index': self.latest_block.index + 1,
                'block.version': CHAIN.get_version_for_height(self.latest_block.index + 1),
                'ignore': {'$ne': True}
            }).to_list(length=100)
            for record in sorted(records, key=lambda x: int(x['block']['target'], 16)):
                try:
                    block = await Block.from_dict(record['block'])
                except:
                    continue
                blockchain = await Blockchain.init_async([block])
                if await self.integrate_blockchain_with_existing_chain(blockchain):
                    return True
        else:
            #  this path should be for syncing only. 
            #  Stack:
            #    search_network_for_new
            #    request_blocks
            #    getblocks <--- rpc request
            #    blocksresponse <--- rpc response
            #    integrate_blockchain_with_existing_chain
            return await self.search_network_for_new()

    async def search_network_for_new(self):
        if self.config.network == 'regnet':
            return False
        
        if self.syncing:
            return False

        async for peer in self.config.peer.get_sync_peers():
            if peer.synced:
                continue
            try:
                await self.request_blocks(peer)
            except StreamClosedError:
                peer.close()
            except Exception as e:
                self.config.app_log.warning(e)
    
    async def request_blocks(self, peer):
        self.config.app_log.debug('requesting {} from {}'.format(self.latest_block.index + 1, peer.peer.identity.username))
        await self.config.nodeShared().write_params(peer, 'getblocks', {
            'start_index': int(self.latest_block.index) + 1,
            'end_index': int(self.latest_block.index) + 100
        })

    async def build_local_chain(self, block: Block):

        local_blocks = self.config.mongo.async_db.blocks.find({'index': {'$gte': block.index}}).sort([('index', 1)])
        return await Blockchain.init_async(local_blocks, partial=True)

    async def build_remote_chain(self, block: Block):
        # now we just need to see how far this chain extends
        blocks = [block]
        while True:
            # get the heighest block from this chain
            local_block = await self.config.mongo.async_db.blocks.find_one({'prevHash': block.hash}, {'_id': 0})
            if local_block:
                local_block = await Block.from_dict(local_block)
                blocks.append(local_block)
            else:
                consensus_block = await self.config.mongo.async_db.consensus.find_one({'block.prevHash': block.hash}, {'_id': 0})
                if consensus_block:
                    consensus_block = await Block.from_dict(consensus_block['block'])
                    blocks.append(consensus_block)
            if not local_block and not consensus_block:
                break

        blocks.sort(key=lambda x: x.index)

        return await Blockchain.init_async(blocks, partial=True)

    async def get_previous_consensus_block_from_local(self, block):
        #table cleanup
        new_blocks = self.mongo.async_db.consensus.find({
            'block.hash': block.prev_hash,
            'block.index': (block.index - 1),
            'block.version': CHAIN.get_version_for_height((block.index - 1))
        })
        async for new_block in new_blocks:
            new_block = await Block.from_dict(new_block['block'])
            yield new_block

    async def get_previous_consensus_block_from_remote(self, block):
        # TODO: async conversion
        retry = 0
        peers = self.config.mongo.async_db.consensus.find({'block.prevHash': block.prev_hash, 'peer': {'$ne': 'me'}})
        async for peer in peers:
            #self.app_log.warning('response code: {} {}'.format(res.status_code, res.content))
            new_block = await Block.from_dict(json.loads(res.content.decode('utf-8')))
            await self.insert_consensus_block(new_block, Peer.from_string(peer['peer']))
            yield new_block
    
    async def get_previous_consensus_block(self, block, stream=None):
        async for local_block in self.get_previous_consensus_block_from_local(block):
            yield local_block
        if stream:
            await BaseRPC().write_params(
                stream,
                'getblock',
                {
                    'hash': block.prev_hash
                }
            )
    
    async def build_backward_from_block_to_fork(self, block, blocks, stream=None, depth=0):
        self.app_log.warning(block.to_dict())
        self.app_log.warning(blocks)

        retrace_block = await self.mongo.async_db.blocks.find_one({'hash': block.prev_hash})
        if retrace_block:
            return blocks

        async for retrace_consensus_block in self.get_previous_consensus_block(block, stream):
            self.app_log.warning(retrace_consensus_block.to_dict())
            result = await self.build_backward_from_block_to_fork(
                retrace_consensus_block,
                blocks.copy(),
                stream,
                depth + 1
            )
            self.app_log.warning(result)
            if isinstance(result, list):
                result.append(retrace_consensus_block)
                return result, True
        if depth == 0:
            return blocks, False
    
    async def integrate_blockchain_with_existing_chain(self, blockchain, stream=None):
        async for block in blockchain.blocks:
            try:
                result = await self.integrate_block_with_existing_chain(block)
                if result:
                    continue

                blocks, status = await self.build_backward_from_block_to_fork(block, [], stream)
                if not status:
                    for block in blocks:
                        await self.config.mongo.async_db.consensus.delete_many({'hash': block.hash})
                    return False

                blocks.append(block)
                return await self.integrate_blocks_with_existing_chain(blocks)
            except:
                return False
        return True

    async def integrate_blocks_with_existing_chain(self, blocks):
        for block in blocks:
            try:
                result = await self.integrate_block_with_existing_chain(block)
                if not result:
                    return False
            except:
                return False

    async def integrate_block_with_existing_chain(self, block: Block, extra_blocks=None):
        """Even in case of retrace, this is the only place where we insert a new block into the block collection and update BU"""
        self.app_log.warning('integrate_block_with_existing_chain')
        try:
            # TODO: reorg the checks, to have the faster ones first.
            # Like, here we begin with checking every tx one by one, when <e did not even check index and provided hash matched previous one.
            bc = await Blockchain.init_async()
            result = await bc.test_block(block)
            if not result:
                return False

            # self.mongo.db.blocks.update({'index': block.index}, block.to_dict(), upsert=True)
            # self.mongo.db.blocks.remove({'index': {"$gt": block.index}}, multi=True)
            # todo: is this useful? can we have more blocks above? No because if we had, we would have raised just above
            await self.mongo.async_db.blocks.delete_many({'index': {"$gte": block.index}})
            db_block = block.to_dict()
            db_block['updated_at'] = time()
            await self.mongo.async_db.blocks.replace_one({'index': block.index}, db_block, upsert=True)
            await self.mongo.async_db.miner_transactions.delete_many({'id': {'$in': [x.transaction_signature for x in block.transactions]}})
            self.latest_block = await Block.from_dict(await self.config.BU.get_latest_block_async(False))
            self.app_log.info("New block inserted for height: {}".format(block.index))
            latest_consensus = await self.mongo.async_db.consensus.find_one({
                'index': self.latest_block.index + 1,
                'block.version': CHAIN.get_version_for_height(self.latest_block.index + 1),
                'ignore': {'$ne': True}
            })
            if not latest_consensus:
                await self.config.LatestBlock.block_checker()  # This will trigger mining pool to generate a new block to mine
                if self.config.mp:
                    await self.config.mp.refresh()
                if not self.syncing:
                    await self.config.nodeShared().send_block(self.config.LatestBlock.block)
            return True
        except Exception as e:
            from traceback import format_exc
            self.app_log.warning("{}".format(format_exc()))
