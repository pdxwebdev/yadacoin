import sys
import json
import time
from base64 import b64encode
from yadacoin import Config, BU, BlockFactory, Mongo

with open('config/config.json') as f:
    Config.from_dict(json.loads(f.read()))
iteration = 0
Config.max_duration = 100000000
Config.grace = 10
Config.block_version = '1'
Mongo.init()
start = time.time()
genesis_block = BlockFactory.mine(
    [],
    Config.public_key,
    Config.private_key,
    Config.max_duration
)
end = time.time()
        
print genesis_block.to_json()

