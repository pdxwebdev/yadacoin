import sys
import json
from pymongo import MongoClient
from blockchain import Blockchain
from blockchainutils import BU
from transactionutils import TU
from transaction import Transaction
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from bson.son import SON

def output(percent):
    sys.stdout.write(str(percent))  # write the next character
    sys.stdout.flush() # flush stdout buffer (actual character display)
    sys.stdout.write(''.join(['\b' for i in range(len(percent))])) # erase the last written char
    if float(percent) >= 100:
        print "\n\n\nDone!"

with open('config.json') as f:
    config = json.loads(f.read())

public_key = config.get('public_key')
my_address = str(P2PKHBitcoinAddress.from_pubkey(public_key.decode('hex')))
private_key = config.get('private_key')
TU.private_key = private_key
BU.private_key = private_key

con = MongoClient('localhost')
db = con.yadacoin
col = db.blocks
BU.collection = col
blocks = BU.get_blocks()
blockchain = Blockchain(blocks)
blockchain.verify(output)

res = col.aggregate([
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
for x in res:
    if x['public_key'] in double_spends:
        if x['input_id'] in double_spends[x['public_key']]:
            print "we have a double spend", x
        else:
            double_spends[x['public_key']][x['input_id']] = x
    else:
        double_spends[x['public_key']] = {}
        double_spends[x['public_key']][x['input_id']] = x
print "double spends", json.dumps(double_spends, indent=4)
