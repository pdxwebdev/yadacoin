import sys
from sys import exc_info
from os import path
import json
import logging
import datetime
from traceback import format_exc
from bitcoin.wallet import P2PKHBitcoinAddress
from time import time
from urllib3.exceptions import *
from asyncio import sleep as async_sleep
from pymongo.errors import DuplicateKeyError
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.httputil import HTTPHeaders
from tornado import ioloop
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import get_config
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.block import Block, BlockFactory
from yadacoin.core.transaction import (
    InvalidTransactionException,
    InvalidTransactionSignatureException,
    MissingInputTransactionException,
    NotEnoughMoneyException
)
from yadacoin.core.latestblock import LatestBlock
from yadacoin.socket.node import NodeSocketServer
from yadacoin.core.peer import Peer


class Consensus(object):

    lowest = CHAIN.MAX_TARGET

    def __init__(self, debug=False, prevent_genesis=False):
        self.app_log = logging.getLogger("tornado.application")
        self.debug = debug
        self.config = get_config()
        self.mongo = self.config.mongo
        self.prevent_genesis = prevent_genesis
        self.latest_block = None

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
            latest_block = self.config.LatestBlock.block
            if latest_block:
                self.latest_block = await Block.from_dict(latest_block)
            else:
                if not self.prevent_genesis:
                    await self.config.BU.insert_genesis()

    def remove_pending_transactions_now_in_chain(self, block):
        #remove transactions from miner_transactions collection in the blockchain
        self.mongo.db.miner_transactions.remove({'id': {'$in': [x['id'] for x in block['block']['transactions']]}}, {'_id': 0})

    def remove_fastgraph_transactions_now_in_chain(self, block):
        self.mongo.db.fastgraph_transactions.remove({'id': {'$in': [x['id'] for x in block['block']['transactions']]}}, {'_id': 0})

    async def insert_consensus_block(self, block, peer):
        try:
            block.verify()
        except:
            return
        await self.mongo.async_db.consensus.replace_one({
            'id': block.signature,
            'peer.rid': peer.rid
        },
        {
            'block': block.to_dict(),
            'index': block.index,
            'id': block.signature,
            'peer': peer.to_dict()
        }, upsert=True)

    async def integrate_block_with_existing_chain(self, block: Block):
        """Even in case of retrace, this is the only place where we insert a new block into the block collection and update BU"""
        self.app_log.warning('integrate_block_with_existing_chain')
        # TODO: reorg the checks, to have the faster ones first.
        # Like, here we begin with checking every tx one by one, when <e did not even check index and provided hash matched previous one.
        try:
            block.verify()
        except Exception as e:
            self.app_log.warning("Integrate block error 1: {}".format(e))
            return False

        await self.config.mongo.async_db.blocks.delete_many({'index': {'$gte': block.index}})

        await block.check_transactions()                        

        if block.index == 0:
            return True
        height = block.index

        if int(block.index) > CHAIN.CHECK_TIME_FROM and int(block.time) < int(self.config.LatestBlock.block.time):
            self.config.app_log.warning('Block too far in the future. Rejecting')
            return False

        if int(block.index) > CHAIN.CHECK_TIME_FROM and (int(block.time) < (int(self.config.LatestBlock.block.time) + 600)) and block.special_min:
            self.config.app_log.warning('Block should not yet be special min. Rejecting')
            return False

        last_block = await Block.from_dict(await self.config.mongo.async_db.blocks.find_one({'index': block.index - 1}))

        if last_block.index != (block.index - 1):
            self.config.app_log.warning('Block height does not follow chain. Rejecting {}:{}'.format(last_block.index, block.index -1))
            return False

        if last_block.hash != block.prev_hash:
            self.config.app_log.warning('Block hash does not follow chain. Rejecting {}:{}'.format(last_block.hash, block.prev_hash -1))
            return False

        if height >= CHAIN.FORK_10_MIN_BLOCK:
            target = await BlockFactory.get_target_10min(height, last_block, block)
        else:
            target = await BlockFactory.get_target(height, last_block, block)

        delta_t = int(time()) - int(last_block.time)
        special_target = CHAIN.special_target(block.index, block.target, delta_t, get_config().network)
        target_block_time = CHAIN.target_block_time(self.config.network)

        if block.index >= 35200 and delta_t < 600 and block.special_min:
            self.config.app_log.warning('Special min block too soon. Rejecting')

        consecutive = False
        if last_block.index == (block.index - 1) and last_block.hash == block.prev_hash:
            consecutive = True

        passed = False
        if int(block.hash, 16) < target:
            passed = True
        
        if block.special_min and int(block.hash, 16) < special_target:
            passed = True
        
        if block.special_min and block.index < 35200:
            passed = True

        if (
            block.index >= 35200 and 
            block.index < 38600 and 
            block.special_min and
            (int(block.time) - int(last_block.time)) > target_block_time
        ):
            passed = True
        
        if passed and consecutive:
            await self.mongo.async_db.blocks.replace_one({'index': block.index}, block.to_dict(), upsert=True)
            await self.mongo.async_db.miner_transactions.delete_many({'id': {'$in': [x.transaction_signature for x in block.transactions]}})
            
            self.app_log.info("New block inserted for height: {}".format(block.index))
            
            await self.config.LatestBlock.block_checker()
            return True
