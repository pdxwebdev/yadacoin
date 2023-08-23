import json
import time

from yadacoin import Block, Config, Mongo

with open("config/config.json") as f:
    config = Config.from_dict(json.loads(f.read()))
iteration = 0
config.max_duration = 100000000
config.grace = 10
config.block_version = "1"
mongo = Mongo(config)
start = time.time()
genesis_block = Block.mine(
    [], config.public_key, config.private_key, config.max_duration
)
end = time.time()

print(genesis_block.to_json())
