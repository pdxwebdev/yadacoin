from yadacoin.chain import CHAIN
from yadacoin.config import get_config
from yadacoin.block import Block, BlockFactory
from yadacoin.transaction import InvalidTransactionException, MissingInputTransactionException


class BlockChainException(Exception):
    pass


class Blockchain(object):
    @classmethod
    async def init_async(cls, blocks=None, partial=False):
        self = cls()
        self.config = get_config()
        self.mongo = self.config.mongo
        self.blocks = blocks
        self.partial = partial
        if not self.blocks:
            return # allow nothing
        return self

    async def verify(self, progress=None):
        async def get_transactions(txns):
            for txn in txns:
                yield txn
        last_block = None
        async for block in self.blocks:
            if not isinstance(block, Block):
                block = await Block.from_dict(block)
            if last_block and last_block.index and (block.index - last_block.index) != 1:
                raise Exception('Either incomplete blockchain or unordered. block {} vs last {}'.format(block.index, last_block.index))
            try:
                block.verify()
            except Exception as e:
                print("verify1", e)
                if last_block:
                    return {'verified': False, 'last_good_block': last_block, 'message': e}
                else:
                    return {'verified': False, 'message': e}
            async for txn in get_transactions(block.transactions):
                try:
                    await txn.verify()
                except InvalidTransactionException as e:
                    print("verify2", e)
                    if last_block:
                        return {'verified': False, 'last_good_block': last_block, 'message': e}
                    else:
                        return {'verified': False, 'message': e}
                except MissingInputTransactionException as e:
                    print("verify3", e)
                    if last_block:
                        return {'verified': False, 'last_good_block': last_block, 'message': e}
                    else:
                        return {'verified': False, 'message': e}
                except Exception as e:
                    print("verify4", e)
                    if last_block:
                        return {'verified': False, 'last_good_block': last_block, 'message': e}
                    else:
                        return {'verified': False, 'message': e}
            if last_block:
                if block.index >= CHAIN.FORK_10_MIN_BLOCK:
                    target = await BlockFactory.get_target_10min(block.index, last_block, block)
                else:
                    target = await BlockFactory.get_target(block.index, last_block, block)
                if int(block.hash, 16) > target and not block.special_min:
                    return {'verified': False, 'last_good_block': last_block, 'message': "invalid block chain: block target is not below the previous target and not special minimum"}
                if block.index >= 35200 and (int(block.time) - int(last_block.time)) < 600 and block.special_min:
                    return {'verified': False, 'last_good_block': last_block, 'message': "invalid block chain: block index is greater than or equal to 35200 and less than 10 minutes has passed since the last block"}
                if block.prev_hash != last_block.hash:
                    return {'verified': False, 'last_good_block': last_block, 'message': "invalid block chain: hashes are not consecutive: %s %s %s %s" % (last_block.hash, block.prev_hash, last_block.index, block.index)}
                if block.index - last_block.index != 1:
                    return {'verified': False, 'last_good_block': last_block, 'message': "invalid block chain: indexes are not consecutive: %s %s" % (last_block.index, block.index)}
            last_block = block
            if progress:
                progress("%s%s %s" % (str(int(float(block.index + 1) / float(len(self.blocks)) * 100)), '%', block.index))
        return {'verified': True}

    async def find_error_block(self):
        last_block = None
        for block in self.blocks:
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
