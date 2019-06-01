from setup import parent_dir
import json
import requests
import yadacoin.config
from yadacoin import *

domain = 'https://yadacoin.io'

config_path = parent_dir + '/config/config.json'
with open(config_path) as f:
    config_dir = json.loads(f.read())

config = Config(config_dir)
yadacoin.config.CONFIG = config
mongo = Mongo()
config.mongo = mongo
BU = yadacoin.blockchainutils.BlockChainUtils()
yadacoin.blockchainutils.set_BU(BU)
config.BU = BU
latest_block = config.mongo.db.blocks.find_one({'index': 0}, {'_id': 0})
blockchain = Blockchain(BU.get_blocks())
max_block_time = 600
target_block_time = max_block_time

def get_data(i):
    res = config.mongo.db.blocks.find_one({'index': int(i)}, {'_id': 0})
    if res:
        return Block.from_dict(res)
    res = config.mongo.db.test_gap_blocks.find_one({'index': int(i)}, {'_id': 0})
    if res:
        return Block.from_dict(res)
    res = requests.get(domain + '/get-blocks?start_index=' + i + '&end_index=' + i)
    config.mongo.db.test_gap_blocks.update({'index': block.index}, block.to_dict(), upsert=True)
    return Block.from_dict(json.loads(res.content.decode())[0])

block_data = get_data(str(int(latest_block['index'])+1))
last_block = Block.from_dict(latest_block)
max_target = 115792089237316195423570985008687907853269984665640564039457584007913129639935
last_target = max_target
while block_data:
    block = get_data(str(int(last_block.index)+1))
    if last_block.index != block.index -1:
        raise Exception('Invalid blockchain')
    if last_block.hash != block.prev_hash:
        raise Exception('Invalid blockchain')
    if block.index == 60008:
        print('Hit block 60008, error should be caught now.')
    target = BlockFactory.get_target(block.index, last_block, block, blockchain)
    print('{} - {:02x}'.format(block.index, target))
    if block.index >= 38600 and (int(block.time) - int(last_block.time)) > max_block_time:
        if not block.special_min:
            print('Error caught: over max block time but no special min flag set.')
        if ((int(block.hash, 16) < target) or #current consensus condition
            (block.special_min and block.index < 35200) or
            (block.index >= 35200 and block.index < 38600 and block.special_min and
            (int(block.time) - int(last_block.time)) > target_block_time)):
            if not block.special_min:
                print('Should NOT get here. Test is invalid. Problem NOT resolved')
                break
        else:
            print('Here because block is not accepted by consensus. Therefore every block thereafter is not valid.')
            break
    if target > last_target:
        raise Exception('fucker')
    try:
        blockchain.blocks[block.index]
    except:
        blockchain.blocks.append(block)
    last_block = block