from block import Block


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

    def verify(self):
        last_block = None
        for block in self.blocks:
            block.verify()
            for txn in block.transactions:
                txn.verify()
            if last_block:
                if block.prev_hash != last_block.hash:
                    raise BaseException("invalid block chain: hashes are not consecutive:", last_block.index, block.index)
                if block.index - last_block.index != 1:
                    raise BaseException("invalid block chain: indexes are not consecutive:", last_block.index, block.index)
            last_block = block
