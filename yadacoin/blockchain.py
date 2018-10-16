import re
from block import Block, BlockFactory

class BlockChainException(BaseException):
    pass

class Blockchain(object):
    def __init__(self, blocks=None):
        if blocks:
            new_block_array = []
            for block in blocks:
                if isinstance(block, Block):
                    new_block_array.append(block)
                else:
                    block_obj = Block.from_dict(block)
                    new_block_array.append(block_obj)
            self.blocks = sorted(new_block_array, key=lambda x: x.index)
        else:
            self.blocks = []

    def verify(self, progress=None):
        last_block = None
        for block in self.blocks:
            try:
                block.verify()
            except:
                if last_block:
                    return {'verified': False, 'last_good_block': last_block}
                else:
                    return {'verified': False}
            for txn in block.transactions:
                try:
                    txn.verify()
                except:
                    if last_block:
                        return {'verified': False, 'last_good_block': last_block}
                    else:
                        return {'verified': False}
            if last_block:
                target = BlockFactory.get_target(block.index, last_block.time, last_block, self)
                if int(block.hash, 16) > target and not block.special_min:
                    print "invalid block chain: block target is not below the previous target and not special minimum"
                    return {'verified': False, 'last_good_block': last_block}
                if block.prev_hash != last_block.hash:
                    print "invalid block chain: hashes are not consecutive:", last_block.hash, block.prev_hash, last_block.index, block.index
                    return {'verified': False, 'last_good_block': last_block}
                if block.index - last_block.index != 1:
                    print "invalid block chain: indexes are not consecutive:", last_block.index, block.index
                    return {'verified': False, 'last_good_block': last_block}
            last_block = block
            if progress:
                progress("%s%s" % (str(int(float(block.index + 1) / float(len(self.blocks)) * 100)), '%'))
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
            if block.index == 18170:
                pass
            target = int(block.hash, 16)
            difficulty += (0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff - target)
        return difficulty

    def get_highest_block_height(self):
        height = 0
        for block in self.blocks:
            if block.index > height:
                height = block.index
        return height