import json
from pymongo import MongoClient

mongo_client = MongoClient('localhost')
blocks = mongo_client.testyadacoin1.blocks.find({})
peers = {}
for block in blocks:
	cons = mongo_client.testyadacoin1.consensus.find({'block.hash': block['hash']})
	peers.setdefault(cons[0]['peer'], 0)
	peers[cons[0]['peer']] += 1
print json.dumps(peers, indent=4)