import re
from block import Block

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
            self.blocks = new_block_array
        else:
            self.blocks = []

    def verify(self, progress):
        last_block = None
        for block in self.blocks:
            block.verify()
            for txn in block.transactions:
                txn.verify()
            if last_block:
                if block.prev_hash != last_block.hash:
                    raise BlockChainException("invalid block chain: hashes are not consecutive:", last_block.index, block.index)
                if block.index - last_block.index != 1:
                    raise BlockChainException("invalid block chain: indexes are not consecutive:", last_block.index, block.index)
            last_block = block
            progress(str(int(float(block.index + 1) / float(len(self.blocks)) * 100)))

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
            zeros = re.search(r'^[0]+', block.hash)
            if zeros:
                difficulty += len(zeros.group(0))
        return difficulty

    def get_highest_block_height(self):
        height = 0
        for block in self.blocks:
            if block.index > height:
                height = block.index
        return height