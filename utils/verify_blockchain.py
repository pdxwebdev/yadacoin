import sys
import json
from pymongo import MongoClient
from yadacoin import Transaction, TU, BU, Blockchain, Config, Mongo
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from bson.son import SON

def output(percent):
    sys.stdout.write(str(percent))  # write the next character
    sys.stdout.flush() # flush stdout buffer (actual character display)
    sys.stdout.write(''.join(['\b' for i in range(len(percent))])) # erase the last written char
    if float(percent) >= 100:
        print "\n\n\nDone!"

with open('config/config.json') as f:
    config = json.loads(f.read())
    config = Config.from_dict(config)

mongo = Mongo(config)
blocks = BU.get_blocks(config, mongo)
blockchain = Blockchain(blocks)
blockchain.verify(output)


res = mongo.db.blocks.aggregate([
    {"$unwind": "$transactions" },
    {
        "$project": {
            "_id": 0,
            "txn": "$transactions"
        }
    },
    {"$unwind": "$txn.inputs" },
    {
        "$project": {
            "_id": 0,
            "input_id": "$txn.inputs.id",
            "public_key": "$txn.public_key"
        }
    },
    {"$sort": SON([("count", -1), ("input_id", -1)])}
])
double_spends = {}
real_double_spends = []
for x in res:
    if x['public_key'] in double_spends:
        if x['input_id'] in double_spends[x['public_key']]:
            real_double_spends.append((x['public_key'], x['input_id']))
        else:
            double_spends[x['public_key']][x['input_id']] = 1
    else:
        double_spends[x['public_key']] = {}
        double_spends[x['public_key']][x['input_id']] = 1
print real_double_spends
print 'no double spends!'
