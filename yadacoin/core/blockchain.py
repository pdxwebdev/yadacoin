from time import time
from types import GeneratorType
from asyncstdlib import tee, anext, islice

from yadacoin.core.chain import CHAIN
from yadacoin.core.config import get_config
from yadacoin.core.block import Block
from yadacoin.core.transaction import (
    InvalidTransactionSignatureException,
    InvalidTransactionException,
    MissingInputTransactionException,
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
        if isinstance(blocks, list):
            self.init_blocks = self.make_gen(blocks)
        elif isinstance(blocks, Block):
            self.init_blocks = self.make_gen([blocks])
        elif not blocks:
            self.init_blocks = self.make_gen([])
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

    async def get_block(self, start, end):
        return await anext(islice(self.blocks, start, end))

    async def get_blocks(self, start, end):
        async for block in islice(self.blocks, start, end):
            if not isinstance(block, Block):
                block = await Block.from_dict(block)
            yield block

    @property
    async def is_consecutive(self):
        prev = None
        async for block in self.blocks:
            if prev and (prev.index + 1) != block.index:
                return False
            if prev and prev.hash != block.prev_hash:
                return False
            prev = block

        return True

    @property
    async def first_block(self):
        block = None
        async for block in self.blocks:
            return block

    @property
    async def final_block(self):
        block = None
        async for block in self.blocks:
            pass
        return block

    @property
    async def count(self):
        i = 0
        async for block in self.blocks:
            i += 1
        return i

    async def verify(self, progress=None):
        async for block in self.blocks:
            if not isinstance(block, Block):
                block = await Block.from_dict(block)
            result = await Blockchain.test_block(block)
            if not result:
              return {'verified': False}

        return {'verified': True}

    async def get_txns(txns):
        for x in txns:
            yield x

    async def get_inputs(inputs):
        for x in inputs:
            yield x

    @staticmethod
    async def test_block(block, extra_blocks=[], simulate_last_block=None):
        config = get_config()
        try:
            await block.verify()
        except Exception as e:
            config.app_log.warning("Integrate block error 1: {}".format(e))
            return False

        if block.index == 0:
            return True

        if simulate_last_block:
            last_block = simulate_last_block
        else:
            last_block_data = await config.mongo.async_db.blocks.find_one({'index': block.index - 1})
            if last_block_data:
                last_block = await Block.from_dict(last_block_data)
            else:
                return False

        if block.index >= CHAIN.FORK_10_MIN_BLOCK:
            target = await CHAIN.get_target_10min(last_block, block, extra_blocks)
        else:
            target = await CHAIN.get_target(block.index, last_block, block, extra_blocks)

        delta_t = int(time()) - int(last_block.time)
        special_target = CHAIN.special_target(block.index, block.target, delta_t, get_config().network)

        if block.index >= 35200 and delta_t < 600 and block.special_min:
            return False

        used_inputs = {}
        i = 0
        async for transaction in Blockchain.get_txns(block.transactions):
            if extra_blocks:
                transaction.extra_blocks = extra_blocks
            config.app_log.info('verifying txn: {} block: {}'.format(i, block.index))
            i += 1
            try:
                await transaction.verify()
            except InvalidTransactionException as e:
                config.app_log.warning(e)
                return False
            except InvalidTransactionSignatureException as e:
                config.app_log.warning(e)
                return False
            except MissingInputTransactionException as e:
                config.app_log.warning(e)
                return False
            except NotEnoughMoneyException as e:
                config.app_log.warning(e)
                return False
            except Exception as e:
                config.app_log.warning(e)
                return False

            if transaction.inputs:
                failed = False
                used_ids_in_this_txn = []
                async for x in Blockchain.get_inputs(transaction.inputs):
                    txn = await config.BU.get_transaction_by_id(x.id, instance=True)
                    if not txn:
                        txn = await transaction.find_in_extra_blocks(x)
                        if not txn:
                            failed = True
                    is_input_spent = await config.BU.is_input_spent(x.id, transaction.public_key, from_index=block.index, extra_blocks=extra_blocks)
                    if is_input_spent:
                        failed = True
                    if x.id in used_ids_in_this_txn:
                        failed = True
                    if (x.id, transaction.public_key) in used_inputs:
                        failed = True
                    used_inputs[(x.id, transaction.public_key)] = transaction
                    used_ids_in_this_txn.append(x.id)
                if failed and block.index >= CHAIN.CHECK_DOUBLE_SPEND_FROM:
                    config.app_log.warning(f'double spend detected {block.index} {transaction.public_key} {x.id}')
                    return False
                elif failed and block.index < CHAIN.CHECK_DOUBLE_SPEND_FROM:
                    continue

        if block.index >= 35200 and delta_t < 600 and block.special_min:
            config.app_log.warning(f'Failed: {block.index} >= {35200} and {delta_t} < {600} and {block.special_min}')
            return False

        if int(block.index) > CHAIN.CHECK_TIME_FROM and int(block.time) < int(last_block.time):
            config.app_log.warning(f'Failed: {int(block.index)} > {CHAIN.CHECK_TIME_FROM} and {int(block.time)} < {int(last_block.time)}')
            return False

        if last_block.index != (block.index - 1) or last_block.hash != block.prev_hash:
            config.app_log.warning(f'Failed: {last_block.index} != {(block.index - 1)} or {last_block.hash} != {block.prev_hash}')
            return False

        if int(block.index) > CHAIN.CHECK_TIME_FROM and (int(block.time) < (int(last_block.time) + 600)) and block.special_min:
            config.app_log.warning(f'Failed: {int(block.index)} > {CHAIN.CHECK_TIME_FROM} and ({int(block.time)} < ({int(last_block.time)} + {600})) and {block.special_min}')
            return False

        target_block_time = CHAIN.target_block_time(config.network)

        checks_passed = False
        if (block.index >= CHAIN.BLOCK_V5_FORK) and int(block.little_hash(), 16) < target:
            config.app_log.debug('5')
            checks_passed = True
        elif (int(block.hash, 16) < target):
            config.app_log.debug('6')
            checks_passed = True
        elif (block.special_min and int(block.hash, 16) < special_target):
            config.app_log.debug('7')
            checks_passed = True
        elif (block.special_min and block.index < 35200):
            config.app_log.debug('8')
            checks_passed = True
        elif (block.index >= 35200 and block.index < 38600 and block.special_min and (int(block.time) - int(last_block.time)) > target_block_time):
            config.app_log.debug('9')
            checks_passed = True
        elif config.network == 'regnet':
            checks_passed = True
        else:
            config.app_log.warning("Integrate block error - target too high, possible fork")

        if not checks_passed:
            return False

        return True

    async def test_inbound_blockchain(self, inbound_blockchain):
        existing_difficulty = await self.get_difficulty()
        inbound_difficulty = await inbound_blockchain.get_difficulty()
        final_existing_block = await self.final_block
        final_inbound_block = await inbound_blockchain.final_block
        if not final_existing_block:
            return True
        if (
            final_inbound_block.index >= final_existing_block.index and
            inbound_difficulty > existing_difficulty
        ):
            return True
        return False

    async def find_error_block(self):
        last_block = None
        async for block in self.blocks:
            await block.verify()
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

    @classmethod
    async def get_genesis_block(cls):
        return await Block.from_dict({
            "nonce" : 0,
            "hash" : "0dd0ec9ab91e9defe535841a4c70225e3f97b7447e5358250c2dc898b8bd3139",
            "public_key" : "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
            "id" : "MEUCIQDDicnjg9DTSnGOMLN3rq2VQC1O9ABDiXygW7QDB6SNzwIga5ri7m9FNlc8dggJ9sDg0QXUugrHwpkVKbmr3kYdGpc=",
            "merkleRoot" : "705d831ced1a8545805bbb474e6b271a28cbea5ada7f4197492e9a3825173546",
            "index" : 0,
            "target" : "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "special_min" : False,
            "version" : "1",
            "transactions" : [
                {
                    "public_key" : "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
                    "fee" : 0.0000000000000000,
                    "hash" : "71429326f00ba74c6665988bf2c0b5ed9de1d57513666633efd88f0696b3d90f",
                    "dh_public_key" : "",
                    "relationship" : "",
                    "inputs" : [],
                    "outputs" : [
                        {
                            "to" : "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4",
                            "value" : 50.0000000000000000
                        }
                    ],
                    "rid" : "",
                    "id" : "MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0="
                }
            ],
            "time" : "1537127756",
            "prevHash" : ""
        })
