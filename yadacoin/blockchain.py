from yadacoin.chain import CHAIN
from yadacoin.config import get_config
from yadacoin.block import Block, BlockFactory
from yadacoin.transaction import InvalidTransactionException, MissingInputTransactionException


class BlockChainException(Exception):
    pass


class Blockchain(object):

    def __init__(self, blocks=None, partial=False):
        self.config = get_config()
        self.mongo = self.config.mongo
        self.blocks = []
        last_index = None
        for block in blocks:
            if not isinstance(block, Block):
                block = Block.from_dict(block)
            
            if last_index and (block.index - last_index) != 1:
                raise Exception('Either incomplete blockchain or unordered. block {} vs last {}'.format(block.index, last_index))
                # In that case: (most often, dup buried block), check if block n+1 exists then remove the wrong block(s)
                # see when inserting/replacing block how the dup insert occurs.

            self.blocks.append(block)
            last_index = block.index
        self.partial = partial
        if not self.blocks:
            return # allow nothing
        if self.blocks and self.blocks[0].index != 0 and not self.partial:
            raise Exception('Blocks do not start with zero index. Either incomplete blockchain or unordered.')

    def verify(self, progress=None):
        last_block = None
        for block in self.blocks:
            try:
                block.verify()
            except Exception as e:
                print("verify1", e)
                if last_block:
                    return {'verified': False, 'last_good_block': last_block, 'message': e}
                else:
                    return {'verified': False, 'message': e}
            for txn in block.transactions:
                try:
                    txn.verify()
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
                target = BlockFactory.get_target(block.index, last_block, block, self)
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

    def find_error_block(self):
        last_block = None
        for block in self.blocks:
            block.verify()
            for txn in block.transactions:
                txn.verify()
            if last_block:
                if int(block.index) - int(last_block.index) > 1:
                    return last_block.index + 1
                if block.prev_hash != last_block.hash:
                    return last_block.index
            last_block = block

    def get_difficulty(self):
        difficulty = 0
        for block in self.blocks:
            target = int(block.hash, 16)
            difficulty += CHAIN.MAX_TARGET - target
        return difficulty

    def get_highest_block_height(self):
        height = 0
        for block in self.blocks:
            if block.index > height:
                height = block.index
        return height
