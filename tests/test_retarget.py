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
latest_block = BU.get_latest_block()
blockchain = Blockchain(BU.get_blocks())

def get_data(i):
    res = config.mongo.db.test_gap_blocks.find_one({'index': int(i)}, {'_id': 0})
    if res:
        return Block.from_dict(res)
    res = requests.get(domain + '/get-blocks?start_index=' + i + '&end_index=' + i)
    config.mongo.db.test_gap_blocks.update({'index': block.index}, block.to_dict(), upsert=True)
    return Block.from_dict(json.loads(res.content.decode())[0])

block_data = get_data(str(int(latest_block['index'])+1))
last_block = Block.from_dict(latest_block)
last_target = 115792089237316195423570985008687907853269984665640564039457584007913129639935
while block_data:
    block = get_data(str(int(last_block.index)+1))
    if last_block.index != block.index -1:
        raise Exception('fuuuck')
    if last_block.hash != block.prev_hash:
        raise Exception('FUUUUCK')
    if block.index == 60008:
        print('here')
    target = BlockFactory.get_target(block.index, last_block, block, blockchain)
    print('{} - {:02x}'.format(block.index, target))
    if target > last_target:
        raise Exception('fucker')
    blockchain.blocks.append(block)
    last_block = block