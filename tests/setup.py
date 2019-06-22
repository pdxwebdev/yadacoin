import sys
import os.path
import json
parent_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))
print(parent_dir)
sys.path.insert(0, parent_dir)

import yadacoin.config
from yadacoin.config import Config
from yadacoin.miningpool import MiningPool
from yadacoin.transaction import TransactionFactory
from yadacoin.mongo import Mongo
from yadacoin.graphutils import GraphUtils

with open(sys.argv[1]) as f:
    config = Config(json.loads(f.read()))
print(config)
yadacoin.config.CONFIG = config
mongo = Mongo()
config.mongo = mongo

config.BU = yadacoin.blockchainutils.BlockChainUtils()
config.TU = yadacoin.transactionutils.TU
yadacoin.blockchainutils.set_BU(config.BU)  # To be removed
config.GU = GraphUtils()
