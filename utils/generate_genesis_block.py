import sys
import json
import time
from base64 import b64encode
from yadacoin import Config, BU, BlockFactory, Mongo

with open('config/config.json') as f:
    Config.from_dict(json.loads(f.read()))

Config.max_duration = 30000000
Config.grace = 10
Config.difficulty = '00000000'
Config.block_version = '1'

Mongo.init()
start = time.time()
genesis_block = BlockFactory.mine([], Config.difficulty, Config.public_key, Config.private_key, Config.max_duration, current_index=0)
end = time.time()
if (end - start) + Config.grace < Config.max_duration:
    Config.difficulty = Config.difficulty + "0"
elif (end - start) - Config.grace > Config.max_duration:
    Config.difficulty = Config.difficulty[:-1]
        

print genesis_block.to_json()

