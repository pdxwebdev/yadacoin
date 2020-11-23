from logging import getLogger
from time import time

from asyncstdlib import tee

from yadacoin.chain import CHAIN
from yadacoin.config import get_config
from yadacoin.block import Block, BlockFactory
from yadacoin.transaction import (
  InvalidTransactionException,
  MissingInputTransactionException,
  InvalidTransactionSignatureException,
  NotEnoughMoneyException
)


class BlockChainException(Exception):
    pass


class Blockchain(object):
    @classmethod
    async def init_async(cls, blocks=None, partial=False):
        self = cls()
        self.config = get_config()
        self.mongo = self.config.mongo
        self.app_log = getLogger('tornado.application')
        if isinstance(blocks, list):
            self.init_blocks = self.make_gen(blocks)
        else:
            self.init_blocks = blocks
        self.partial = partial
        if not self.blocks:
            return # allow nothing
        return self
    
    async def make_gen(self, blocks):
        for block in blocks:
            yield block
    
    @property
    async def blocks(self):
        self.init_blocks, blocks = tee(self.init_blocks)
        async for block in blocks:
            if not isinstance(block, Block):
                block = await Block.from_dict(block)
            yield block

    async def verify(self, progress=None):
        async for block in self.blocks:
            if not isinstance(block, Block):
                block = await Block.from_dict(block)
            result = await self.test_block(block)
            if not result:
              return {'verified': False}

        return {'verified': True}

    async def test_block(self, block):
        try:
            block.verify()
        except Exception as e:
            self.app_log.warning("Integrate block error 1: {}".format(e))
            return False

        async def get_txns(txns):
            for x in txns:
                yield x

        async def get_inputs(inputs):
            for x in inputs:
                yield x

        if block.index == 0:
            return True

        last_block = await Block.from_dict(await self.config.mongo.async_db.blocks.find_one({'index': block.index - 1}))

        if block.index >= CHAIN.FORK_10_MIN_BLOCK:
            target = await BlockFactory.get_target_10min(block.index, last_block, block)
        else:
            target = await BlockFactory.get_target(block.index, last_block, block)

        delta_t = int(time()) - int(last_block.time)
        special_target = CHAIN.special_target(block.index, block.target, delta_t, get_config().network)

        if block.index >= 35200 and delta_t < 600 and block.special_min:
            return False

        used_inputs = {}
        i = 0
        async for transaction in get_txns(block.transactions):
            self.app_log.warning('verifying txn: {} block: {}'.format(i, block.index))
            i += 1
            try:
                await transaction.verify()
            except InvalidTransactionException as e:
                self.app_log.warning(e)
                return False
            except InvalidTransactionSignatureException as e:
                self.app_log.warning(e)
                return False
            except MissingInputTransactionException as e:
                self.app_log.warning(e)
            except NotEnoughMoneyException as e:
                self.app_log.warning(e)
                return False
            except Exception as e:
                self.app_log.warning(e)
                return False

            if transaction.inputs:
                failed = False
                used_ids_in_this_txn = []
                async for x in get_inputs(transaction.inputs):
                    if self.config.BU.is_input_spent(x.id, transaction.public_key, from_index=block.index):
                        failed = True
                    if x.id in used_ids_in_this_txn:
                        failed = True
                    if (x.id, transaction.public_key) in used_inputs:
                        failed = True
                    used_inputs[(x.id, transaction.public_key)] = transaction
                    used_ids_in_this_txn.append(x.id)
                if failed and block.index >= CHAIN.CHECK_DOUBLE_SPEND_FROM:
                    return False
                elif failed and block.index < CHAIN.CHECK_DOUBLE_SPEND_FROM:
                    continue

        if block.index >= 35200 and delta_t < 600 and block.special_min:
            self.app_log.warning('1')
            return False

        if int(block.index) > CHAIN.CHECK_TIME_FROM and int(block.time) < int(last_block.time):
            self.app_log.warning('2')
            return False

        if last_block.index != (block.index - 1) or last_block.hash != block.prev_hash:
            self.app_log.warning('3')
            return False

        if int(block.index) > CHAIN.CHECK_TIME_FROM and (int(block.time) < (int(last_block.time) + 600)) and block.special_min:
            self.app_log.warning('4')
            return False

        if block.index >= 35200 and delta_t < 600 and block.special_min:
            self.app_log.warning('5')
            return False

        target_block_time = CHAIN.target_block_time(self.config.network)

        checks_passed = False
        if (int(block.hash, 16) < target):
            self.app_log.warning('6')
            checks_passed = True
        elif (block.special_min and int(block.hash, 16) < special_target):
            self.app_log.warning('7')
            checks_passed = True
        elif (block.special_min and block.index < 35200):
            self.app_log.warning('8')
            checks_passed = True
        elif (block.index >= 35200 and block.index < 38600 and block.special_min and (int(block.time) - int(last_block.time)) > target_block_time):
            self.app_log.warning('9')
            checks_passed = True
        else:
            self.app_log.warning("Integrate block error - index and time error")

        if not checks_passed:
            return False

        return True

    async def find_error_block(self):
        last_block = None
        async for block in self.blocks:
            block.verify()
            for txn in block.transactions:
                await txn.verify()
            if last_block:
                if int(block.index) - int(last_block.index) > 1:
                    return last_block.index + 1
                if block.prev_hash != last_block.hash:
                    return last_block.index
            last_block = block

    async def get_difficulty(self):
        difficulty = 0
        async for block in self.blocks:
            if not isinstance(block, Block):
                block = await Block.from_dict(block)
            target = int(block.hash, 16)
            difficulty += CHAIN.MAX_TARGET - target
        return difficulty

    def get_highest_block_height(self):
        height = 0
        for block in self.blocks:
            if block.index > height:
                height = block.index
        return height
