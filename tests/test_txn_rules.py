from setup import parent_dir
from colorama import Fore, Style
import json
import requests
import yadacoin.config
import os
from eccsnacks.curve25519 import scalarmult_base
from yadacoin import *

class TestTxnRuls(object):
    max_target = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    def __init__(self):
        CHAIN.MINING_AND_TXN_REFORM_FORK = 0
        self.domain = 'https://yadacoin.io'

        config_path = parent_dir + '/config/config.json'
        with open(config_path) as f:
            config_dir = json.loads(f.read())

        self.config = Config(config_dir)
        yadacoin.config.CONFIG = self.config
        yadacoin.config.CONFIG.database = 'yadacoin_txn_rules_test'
        mongo = Mongo()
        self.config.mongo = mongo
        BU = yadacoin.blockchainutils.BlockChainUtils()
        yadacoin.blockchainutils.set_BU(BU)
        self.config.BU = BU
        self.config.GU = GU()
        consensus = Consensus()
        self.config.consensus = consensus

    def reset(self):
        self.config.mongo.db.blocks.remove({})
        self.config.mongo.db.unspent_cache.remove({})
        bf = self.mine_new_block(0, [])
        self.config.mongo.db.blocks.insert(bf.to_dict())

    def mine_new_block(self, index, transactions):
        bf = BlockFactory(
            transactions=transactions,
            public_key=self.config.public_key,
            private_key=self.config.private_key,
            index=index
        )
        nonce, block_hash = BlockFactory.mine(BlockFactory.generate_header(bf.block), self.max_target, [0, 100000])
        block = bf.block
        block.hash = block_hash
        block.nonce = nonce
        block.signature = TU.generate_signature(block.hash, self.config.private_key)
        block.verify()
        return block

    def get_block_by_height(self, i):
        res = self.config.mongo.db.blocks.find_one({'index': int(i)}, {'_id': 0})
        if res:
            return Block.from_dict(res)
        res = self.config.mongo.db.test_gap_blocks.find_one({'index': int(i)}, {'_id': 0})
        if res:
            return Block.from_dict(res)
        res = requests.get(self.domain + '/get-blocks?start_index=' + str(i) + '&end_index=' + str(i))
        block = Block.from_dict(json.loads(res.content.decode())[0])
        self.config.mongo.db.test_gap_blocks.update({'index': int(i)}, block.to_dict(), upsert=True)
        return block

    def generate_dh(self):
        a = os.urandom(32).decode('latin1')
        dh_public_key = scalarmult_base(a).encode('latin1').hex()
        dh_private_key = a.encode().hex()
        return dh_public_key, dh_private_key

    def test_relationship_from_coinbase(self):
        self.reset()
        print(Fore.BLUE + 'test_relationship_from_coinbase' + Style.RESET_ALL)
        # Test Rule 1. Coinbase transactions must only be used as inputs for relationship creation. 
        # non_relationship_txn should not be included in block
        block = self.get_block_by_height(0)
        coinbase_txn = block.transactions[0]
        self.config.mongo.db.blocks.update({'index': 0}, block.to_dict(), upsert=True)

        dh_public_key, dh_private_key = self.generate_dh()
        relationship_txn = TransactionFactory(
                block_height=1,
                bulletin_secret='MEUCIQCyl/saFzqVSVOC7+udTvFYWFZOsqk0pWh8gUG7h8v1cAIgbxGw6HyJiqlhY4vRptwx+VlCNVCfPjNEVmVzSXq/qmw=',
                username=self.config.username,
                value=1,
                fee=0.1,
                requester_rid='',
                requested_rid='',
                public_key=self.config.public_key,
                dh_public_key=dh_public_key,
                private_key=self.config.private_key,
                dh_private_key=dh_private_key,
                to='13EbNJefRc95nkLFkJvJDycXkowW4sWqSe',
                inputs=[{'id': coinbase_txn.transaction_signature}],
                outputs=[{'to': self.config.address, 'value': 1}],
                coinbase=False,
                chattext=None,
                signin=None
        )
        bf = BlockFactory(
            transactions=[relationship_txn.transaction],
            public_key=self.config.public_key,
            private_key=self.config.private_key,
            index=1
        )
        for txn in bf.transactions:
            if txn.transaction_signature == relationship_txn.transaction_signature:
                return self.output(True, 'Relationship transaction from coinbase included in block')
        return self.output(False, 'Relationship transaction from coinbase should be included in block')

    def test_non_relationship_from_coinbase(self):
        self.reset()
        print(Fore.BLUE + 'test_non_relationship_from_coinbase' + Style.RESET_ALL)
        # Test Rule 1. Coinbase transactions must only be used as inputs for relationship creation. 
        # non_relationship_txn should not be included in block
        block = self.get_block_by_height(0)
        coinbase_txn = block.transactions[0]
        self.config.mongo.db.blocks.update({'index': 0}, block.to_dict(), upsert=True)

        relationship_txn = TransactionFactory( # non-relationship transaction
                block_height=1,
                bulletin_secret='',
                username=self.config.username,
                value=1,
                fee=0.1,
                requester_rid='',
                requested_rid='',
                public_key=self.config.public_key,
                dh_public_key='',
                private_key=self.config.private_key,
                dh_private_key='',
                to='13EbNJefRc95nkLFkJvJDycXkowW4sWqSe',
                inputs=[{'id': coinbase_txn.transaction_signature}],
                outputs=[{'to': self.config.address, 'value': 1}],
                coinbase=False,
                chattext=None,
                signin=None
        )
        bf = BlockFactory(
            transactions=[relationship_txn.transaction],
            public_key=self.config.public_key,
            private_key=self.config.private_key,
            index=1
        )
        for txn in bf.transactions:
            if txn.transaction_signature == relationship_txn.transaction_signature:
                return self.output(False, 'Non-relationship transaction from coinbase should not be included in block')
        return self.output(True, 'Non-relationship transaction from coinbase excluded from block')

    def test_dup_relationship_from_coinbase(self):
        self.reset()
        print(Fore.BLUE + 'test_dup_relationship_from_coinbase' + Style.RESET_ALL)
        # Test Rule 1. Coinbase transactions must only be used as inputs for relationship creation. 
        # non_relationship_txn should not be included in block
        block = self.get_block_by_height(0)
        coinbase_txn = block.transactions[0]
        self.config.mongo.db.blocks.update({'index': 0}, block.to_dict(), upsert=True)

        relationship_txn = TransactionFactory( # non-relationship transaction
                block_height=1,
                bulletin_secret='',
                username=self.config.username,
                value=1,
                fee=0.1,
                requester_rid='',
                requested_rid='',
                public_key=self.config.public_key,
                dh_public_key='',
                private_key=self.config.private_key,
                dh_private_key='',
                to='13EbNJefRc95nkLFkJvJDycXkowW4sWqSe',
                inputs=[{'id': coinbase_txn.transaction_signature}],
                outputs=[{'to': self.config.address, 'value': 1}],
                coinbase=False,
                chattext=None,
                signin=None
        )
        bf = self.mine_new_block(1, [relationship_txn.transaction])
        for txn in bf.transactions:
            if txn.transaction_signature == relationship_txn.transaction_signature:
                return self.output(False, 'Relationship transaction from coinbase should not be included in block')
        return self.output(True, 'Relationship transaction from coinbase excluded from block')

    def test_relationship_from_relationship(self):
        self.reset()
        print(Fore.BLUE + 'test_relationship_from_relationship' + Style.RESET_ALL)
        # Test Rule 1. Coinbase transactions must only be used as inputs for relationship creation. 
        # non_relationship_txn should not be included in block
        block = self.get_block_by_height(0)
        coinbase_txn = block.transactions[0]
        self.config.mongo.db.blocks.update({'index': 0}, block.to_dict(), upsert=True)
        dh_public_key, dh_private_key = self.generate_dh()
        relationship_txn = TransactionFactory(
                block_height=1,
                bulletin_secret='MEUCIQCyl/saFzqVSVOC7+udTvFYWFZOsqk0pWh8gUG7h8v1cAIgbxGw6HyJiqlhY4vRptwx+VlCNVCfPjNEVmVzSXq/qmw=',
                username=self.config.username,
                value=1,
                fee=0.1,
                requester_rid='',
                requested_rid='',
                public_key=self.config.public_key,
                dh_public_key=dh_public_key,
                private_key=self.config.private_key,
                dh_private_key=dh_private_key,
                to='13EbNJefRc95nkLFkJvJDycXkowW4sWqSe',
                inputs=[{'id': coinbase_txn.transaction_signature}],
                outputs=[{'to': self.config.address, 'value': 1}],
                coinbase=False,
                chattext=None,
                signin=None
        )
        bf = self.mine_new_block(1, [relationship_txn.transaction])
        self.config.mongo.db.blocks.insert(bf.to_dict()) # relationship transaction containing block inserted at height 1

        relationship_txn = TransactionFactory(
                block_height=1,
                bulletin_secret='MEUCIQCyl/saFzqVSVOC7+udTvFYWFZOsqk0pWh8gUG7h8v1cAIgbxGw6HyJiqlhY4vRptwx+VlCNVCfPjNEVmVzSXq/qmw=',
                username=self.config.username,
                value=1,
                fee=0.1,
                requester_rid='',
                requested_rid='',
                public_key=self.config.public_key,
                dh_public_key=dh_public_key,
                private_key=self.config.private_key,
                dh_private_key=dh_private_key,
                to='13EbNJefRc95nkLFkJvJDycXkowW4sWqSe',
                inputs=[{'id': relationship_txn.transaction_signature}],
                outputs=[{'to': self.config.address, 'value': 1}],
                coinbase=False,
                chattext=None,
                signin=None
        )
        bf = BlockFactory(
            transactions=[relationship_txn.transaction],
            public_key=self.config.public_key,
            private_key=self.config.private_key,
            index=2
        )
        for txn in bf.transactions:
            if txn.transaction_signature == relationship_txn.transaction_signature:
                return self.output(False, 'Relationship transaction with duplicate rid from relationship transaction should be excluded in block')
        return self.output(True, 'Relationship transaction from relationship transaction excluded in block')
    
    def output(self, result, message=''):
        if result:
            if message:
                message = 'Test passed - ' + message
            else:
                message = 'Test passed - ' + message
            return Fore.GREEN + message + Style.RESET_ALL
        else:
            if message:
                message = 'Test failed - ' + message
            else:
                message = 'Test failed - ' + message
            return Fore.RED + message + Style.RESET_ALL

test = TestTxnRuls()
#coinbase txn rules
print(test.test_relationship_from_coinbase())
print(test.test_non_relationship_from_coinbase())
print(test.test_dup_relationship_from_coinbase())

#relationship txn rules
print(test.test_relationship_from_relationship())

#fastgraph txn rules
