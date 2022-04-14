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
from yadacoin.tcpsocket.pool import StratumServer


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
        self.block_queue = ProcessingQueue()

        if self.config.LatestBlock.block:
            self.latest_block = self.config.LatestBlock.block
        else:
            if not self.prevent_genesis:
                await self.config.BU.insert_genesis()
                self.latest_block = self.config.LatestBlock.block
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

    async def process_block_queue(self):
        item = await self.block_queue.pop()

        if not item:
            return

        first_block = await item.blockchain.first_block
        final_block = await item.blockchain.final_block

        first_existing = await self.mongo.async_db.blocks.find_one({
            'hash': first_block.hash,
        })

        final_existing = await self.mongo.async_db.blocks.find_one({
            'hash': final_block.hash,
        })

        if first_existing and final_existing:
            return

        count = await item.blockchain.count

        if count < 1:
            return
        elif count == 1:
            await self.integrate_block_with_existing_chain(await item.blockchain.first_block, item.stream)
        else:
            await self.integrate_blocks_with_existing_chain(item.blockchain, item.stream)

    def remove_pending_transactions_now_in_chain(self, block):
        #remove transactions from miner_transactions collection in the blockchain
        self.mongo.db.miner_transactions.remove({'id': {'$in': [x['id'] for x in block['block']['transactions']]}}, {'_id': 0})

    def remove_fastgraph_transactions_now_in_chain(self, block):
        self.mongo.db.fastgraph_transactions.remove({'id': {'$in': [x['id'] for x in block['block']['transactions']]}}, {'_id': 0})

    async def insert_consensus_block(self, block, peer):
        existing = await self.mongo.async_db.consensus.find_one({
            'index': block.index,
            'peer.rid': peer.rid,
            'id': block.signature,
        })
        if existing:
            return False
        try:
            await block.verify()
        except:
            return False
        self.app_log.info('inserting new consensus block for height and peer: %s %s' % (block.index, peer.to_string()))
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
        return True

    async def sync_bottom_up(self):
        #bottom up syncing

        last_latest = self.latest_block
        self.latest_block = self.config.LatestBlock.block
        if last_latest:
            if self.latest_block.index > last_latest.index:
                self.app_log.info('Block height: %s | time: %s' % (self.latest_block.index, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.config.health.consensus.last_activity = time()
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
                stream = await self.config.peer.get_peer_by_id(record['peer']['rid'])
                if stream and hasattr(stream, 'peer') and stream.peer.authenticated:
                    await self.block_queue.add(ProcessingQueueItem(await Blockchain.init_async(block), stream))

            return True
        else:
            #  this path is for syncing only.
            #  Stack:
            #    search_network_for_new
            #    request_blocks
            #    getblocks <--- rpc request
            #    blocksresponse <--- rpc response
            #    process_block_queue
            return await self.search_network_for_new()

    async def search_network_for_new(self):
        if self.config.network == 'regnet':
            return False

        if self.syncing:
            return False

        async for peer in self.config.peer.get_sync_peers():
            if peer.synced or peer.message_queue.get('getblocks'):
                continue
            try:
                peer.syncing = True
                await self.request_blocks(peer)
            except StreamClosedError:
                peer.close()
            except Exception as e:
                self.config.app_log.warning(e)
            self.config.health.consensus.last_activity = time()

    async def request_blocks(self, peer):
        await self.config.nodeShared.write_params(peer, 'getblocks', {
            'start_index': int(self.config.LatestBlock.block.index) + 1,
            'end_index': int(self.config.LatestBlock.block.index) + 100
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
                block = local_block
                blocks.append(local_block)
            else:
                consensus_block = await self.config.mongo.async_db.consensus.find_one({'block.prevHash': block.hash}, {'_id': 0})
                if consensus_block:
                    consensus_block = await Block.from_dict(consensus_block['block'])
                    block = consensus_block
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

    async def get_previous_consensus_block(self, block, stream=None):
        had_results = False
        async for local_block in self.get_previous_consensus_block_from_local(block):
            had_results = True
            yield local_block
        if stream and not had_results:
            await self.config.nodeShared.write_params(
                stream,
                'getblock',
                {
                    'hash': block.prev_hash,
                    'index': block.index - 1
                }
            )

    async def build_backward_from_block_to_fork(self, block, blocks, stream=None, depth=0):
        self.app_log.debug(block.to_dict())

        retrace_block = await self.mongo.async_db.blocks.find_one({
            'hash': block.prev_hash,
            'time': {'$lt': block.time}
        })
        if retrace_block:
            return blocks, True

        retrace_consensus_block = [x async for x in self.get_previous_consensus_block(block, stream)]
        if not retrace_consensus_block:
            return blocks, False

        retrace_consensus_block = retrace_consensus_block[0]

        if blocks is None:
            blocks = []

        backward_blocks, status = await self.build_backward_from_block_to_fork(
            retrace_consensus_block,
            json.loads(json.dumps([x for x in blocks])),
            stream,
            depth + 1
        )
        backward_blocks.append(retrace_consensus_block)
        return backward_blocks, status

    async def integrate_block_with_existing_chain(self, block: Block, stream):
        self.app_log.debug('integrate_block_with_existing_chain')
        backward_blocks, status = await self.build_backward_from_block_to_fork(block, [], stream)

        if not status:
            return

        forward_blocks_chain = await self.build_remote_chain(block) #contains block

        inbound_blockchain = await Blockchain.init_async(sorted(backward_blocks + [x async for x in forward_blocks_chain.blocks], key=lambda x: x.index))

        if not await inbound_blockchain.is_consecutive:
            return False

        await self.integrate_blocks_with_existing_chain(inbound_blockchain, stream)

    async def integrate_blocks_with_existing_chain(self, blockchain, stream):
        self.app_log.debug('integrate_blocks_with_existing_chain')

        extra_blocks = [x async for x in blockchain.blocks]
        prev_block = None
        i = 0
        async for block in blockchain.blocks:
            if self.config.network == 'regnet':
                break
            if not await Blockchain.test_block(block, extra_blocks=extra_blocks, simulate_last_block=prev_block):
                good_blocks = [x async for x in blockchain.get_blocks(0, i)]
                if good_blocks:
                    blockchain = await Blockchain.init_async(good_blocks, True)
                    break
                else:
                    return
            prev_block = block
            i += 1

        first_block = await blockchain.first_block

        existing_blockchain = await Blockchain.init_async(
            self.config.mongo.async_db.blocks.find({
                'index': {
                    '$gte': first_block.index
                }
            }),
            partial=True
        )

        if not await existing_blockchain.test_inbound_blockchain(blockchain):
            final_block = await blockchain.final_block
            if stream:
                await self.config.nodeShared.write_params(
                    stream,
                    'getblock',
                    {
                        'index': final_block.index + 1
                    }
                )
            return

        async for block in blockchain.blocks:
            if not await Blockchain.test_block(block) and self.config.network == 'mainnet':
                return
            await self.insert_block(block, stream)

        if stream:
            stream.syncing = False

    async def insert_block(self, block, stream):
        self.app_log.debug('insert_block')
        try:
            await self.mongo.async_db.blocks.delete_many({'index': {"$gte": block.index}})

            db_block = block.to_dict()

            db_block['updated_at'] = time()

            await self.mongo.async_db.blocks.replace_one({'index': block.index}, db_block, upsert=True)

            await self.mongo.async_db.miner_transactions.delete_many({'id': {'$in': [x.transaction_signature for x in block.transactions]}})

            await self.config.LatestBlock.update_latest_block()

            self.app_log.info("New block inserted for height: {}".format(block.index))

            latest_consensus = await self.mongo.async_db.consensus.find_one({
                'index': block.index + 1,
                'block.version': CHAIN.get_version_for_height(block.index + 1),
                'ignore': {'$ne': True}
            })

            if not latest_consensus:
                await self.config.LatestBlock.block_checker()  # This will trigger mining pool to generate a new block to mine
                if not self.syncing:
                    if stream and stream.syncing:
                        return True
                    await self.config.nodeShared.send_block(self.config.LatestBlock.block)
                    await self.config.websocketServer.send_block(self.config.LatestBlock.block)

            if self.config.mp:
                if self.syncing:
                    return True
                try:
                    await self.config.mp.refresh()
                except Exception as e:
                    self.app_log.warning("{}".format(format_exc()))

                try:
                    await StratumServer.block_checker()
                except Exception as e:
                    self.app_log.warning("{}".format(format_exc()))

            return True
        except Exception as e:
            from traceback import format_exc
            self.app_log.warning("{}".format(format_exc()))


class ProcessingQueueItem:
    def __init__(self, blockchain: Blockchain, stream=None):
        self.blockchain = blockchain
        self.stream = stream


class ProcessingQueue:
    def __init__(self):
        self.queue = {}
        self.last_popped = ()

    async def add(self, item: ProcessingQueueItem):
        first_block = await item.blockchain.first_block
        final_block = await item.blockchain.final_block
        if (first_block.hash, final_block.hash) == self.last_popped:
            return
        self.queue.setdefault((first_block.hash, final_block.hash), item)

    async def pop(self):
        if not self.queue:
            return None
        key, item = self.queue.popitem()
        first_block = await item.blockchain.first_block
        final_block = await item.blockchain.final_block
        self.last_popped = (first_block.hash, final_block.hash)
        return item
