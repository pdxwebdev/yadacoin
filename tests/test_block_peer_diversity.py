from pymongo import MongoClient

mongo_client = MongoClient('localhost')
blocks = mongo_client.testyadacoin1.blocks.find({})
for block in blocks:
	cons = mongo_client.testyadacoin1.consensus.find({'id': block['id']})
	print cons[0]['peer']