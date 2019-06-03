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
        self.configs = {}
        self.generate_config('service_provider')
        self.generate_config('user_1')
        self.generate_config('user_2')

    def generate_config(self, name):
        self.configs[name] = Config.generate()
        self.switch_config(name)

    def switch_config(self, name):
        yadacoin.config.CONFIG = self.configs[name]
        yadacoin.config.CONFIG.database = 'yadacoin_txn_rules_test_{}'.format(name)
        mongo = Mongo()
        self.configs[name].mongo = mongo
        BU = yadacoin.blockchainutils.BlockChainUtils()
        yadacoin.blockchainutils.set_BU(BU)
        self.configs[name].BU = BU
        self.configs[name].GU = GU()
        consensus = Consensus()
        self.configs[name].consensus = consensus

    def reset(self):
        for name in self.configs:
            self.configs[name].mongo.db.blocks.remove({})
            self.configs[name].mongo.db.unspent_cache.remove({})
            self.configs[name].mongo.db.transactions_by_rid_cache.remove({})
            self.configs[name].BU.latest_block = None

    def mine_new_block(self, transactions):
        self.switch_config('service_provider')
        latest_block = self.configs['service_provider'].BU.latest_block
        if latest_block:
            index = latest_block['index'] + 1
        else:
            index = 0

        bf = BlockFactory(
            transactions=transactions,
            public_key=self.configs['service_provider'].public_key,
            private_key=self.configs['service_provider'].private_key,
            index=index
        )
        nonce, block_hash = BlockFactory.mine(BlockFactory.generate_header(bf.block), self.max_target, [0, 100000])
        block = bf.block
        block.hash = block_hash
        block.nonce = nonce
        block.signature = TU.generate_signature(block.hash, self.configs['service_provider'].private_key)
        block.verify()

        for name in self.configs:
            self.configs[name].mongo.db.blocks.insert(block.to_dict()) # relationship transaction containing block inserted at height 1
            self.configs[name].consensus.existing_blockchain.blocks.append(block) # keep our in-memory blockchain up-to-date
            self.configs[name].BU.latest_block = block.to_dict()
        return block

    def generate_dh(self):
        a = os.urandom(32).decode('latin1')
        dh_public_key = scalarmult_base(a).encode('latin1').hex()
        dh_private_key = a.encode().hex()
        return dh_public_key, dh_private_key
    
    def generate_transaction(
        self,
        from_config,
        to_config,
        txn_type,
        inputs=[],
        requested_rid='',
        requester_rid='',
        value=1
    ):
        self.switch_config(from_config)
        if txn_type == 'register':
            dh_public_key, dh_private_key = self.generate_dh()
            bulletin_secret = self.configs[to_config].bulletin_secret
        elif txn_type == 'create_relationship':
            dh_public_key, dh_private_key = self.generate_dh()
            bulletin_secret = self.configs[to_config].bulletin_secret
        else:
            dh_public_key, dh_private_key = '', ''
            bulletin_secret = ''
        return TransactionFactory(
            block_height=1,
            bulletin_secret=bulletin_secret,
            username=self.configs[from_config].username,
            value=1,
            fee=0.1,
            requester_rid=requester_rid,
            requested_rid=requested_rid,
            public_key=self.configs[from_config].public_key,
            dh_public_key=dh_public_key,
            private_key=self.configs[from_config].private_key,
            dh_private_key=dh_private_key,
            to=self.configs[to_config].address,
            inputs=inputs,
            outputs=[{'to': self.configs[to_config].address, 'value': value}],
            coinbase=False,
            chattext=None,
            signin=None
        ).transaction
    
    def send_from_serivce_provider_to_user_1(self, input_txn):

        # SERVICE PROVIDER <-> USER 1 SEND
        # ==========================================
        # send txn from service provider
        txn = self.generate_transaction(
            'service_provider',
            'user_1',
            '',
            [{'id': input_txn.transaction_signature}],
            value=2
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def relationship_serivce_provider_to_user_1(self, input_txn):

        # SERVICE PROVIDER <-> USER 1 RELATIONSHIP
        # ==========================================
        # relationship txn from service provider
        txn = self.generate_transaction(
            'service_provider',
            'user_1',
            'register',
            [{'id': input_txn.transaction_signature}],
            value=2
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def relationship_user_1_to_serivce_provider(self, input_txn):

        # SERVICE PROVIDER <-> USER 1 RELATIONSHIP
        # ==========================================
        # relationship txn from user 1
        txn = self.generate_transaction(
            'user_1',
            'service_provider',
            'register',
            [{'id': input_txn.transaction_signature}]
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def relationship_serivce_provider_to_user_2(self, input_txn):

        # SERVICE PROVIDER <-> USER 2 RELATIONSHIP
        # ==========================================
        # relationship txn from service provider
        txn = self.generate_transaction(
            'service_provider',
            'user_2',
            'register',
            [{'id': input_txn.transaction_signature}],
            value=2
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def relationship_user_2_to_serivce_provider(self, input_txn):

        # SERVICE PROVIDER <-> USER 2 RELATIONSHIP
        # ==========================================
        # relationship txn from user 1
        txn = self.generate_transaction(
            'user_2',
            'service_provider',
            'register',
            [{'id': input_txn.transaction_signature}]
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def relationship_user_1_to_user_2(self, input_txn):

        # USER 1 <-> USER 2 RELATIONSHIP
        # ==========================================
        # relationship txn from user 1
        txn = self.generate_transaction(
            'user_1',
            'user_2',
            'create_relationship',
            [{'id': input_txn.transaction_signature}],
            value=2
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def relationship_user_2_to_user_1(self, input_txn):

        # USER 1 <-> USER 2 RELATIONSHIP
        # ==========================================
        # relationship txn from user 2
        txn = self.generate_transaction(
            'user_2',
            'user_1',
            'create_relationship',
            [{'id': input_txn.transaction_signature}]
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def register_user_1(self, input_txn):
        block1, txn1 = self.relationship_serivce_provider_to_user_1(input_txn)
        block2, txn2 = self.relationship_user_1_to_serivce_provider(txn1)
        return {
            'block_1': block1,
            'block_2': block2,
            'txn_1': txn1,
            'txn_2': txn2
        }
    
    def register_user_2(self, input_txn):
        block1, txn1 = self.relationship_serivce_provider_to_user_2(input_txn)
        block2, txn2 = self.relationship_user_2_to_serivce_provider(txn1)
        return {
            'block_1': block1,
            'block_2': block2,
            'txn_1': txn1,
            'txn_2': txn2
        }
    
    def user_1_to_user_2_relationship(self, input_txn):
        block1, txn1 = self.relationship_user_1_to_user_2(input_txn)
        block2, txn2 = self.relationship_user_2_to_user_1(txn1)
        return {
            'block_1': block1,
            'block_2': block2,
            'txn_1': txn1,
            'txn_2': txn2
        }

    def test_relationship_from_coinbase(self):
        self.switch_config('service_provider')
        self.reset()
        print(Fore.BLUE + 'test_relationship_from_coinbase' + Style.RESET_ALL)
        # Test Rule 1. Coinbase transactions must only be used as inputs for relationship creation. 
        # non_relationship_txn should not be included in block
        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        result = self.register_user_1(coinbase_txn)
        for txn in result['block_2'].transactions:
            if txn.transaction_signature == result['txn_2'].transaction_signature:
                return self.output(True, 'Relationship transaction from coinbase included in block')
        return self.output(False, 'Relationship transaction from coinbase should be included in block')

    def test_non_relationship_from_coinbase(self):
        self.switch_config('service_provider')
        self.reset()
        print(Fore.BLUE + 'test_non_relationship_from_coinbase' + Style.RESET_ALL)
        # Test Rule 1. Coinbase transactions must only be used as inputs for relationship creation. 
        # non_relationship_txn should not be included in block
        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        block, res_txn = self.send_from_serivce_provider_to_user_1(coinbase_txn)
        for txn in block.transactions:
            if txn.transaction_signature == res_txn.transaction_signature:
                return self.output(False, 'Non-relationship transaction from coinbase should not be included in block')
        return self.output(True, 'Non-relationship transaction from coinbase excluded from block')

    def test_dup_relationship_from_coinbase(self):
        self.switch_config('service_provider')
        self.reset()
        print(Fore.BLUE + 'test_dup_relationship_from_coinbase' + Style.RESET_ALL)
        # Test Rule 2. Coinbase transactions cannot create duplicate relationships 
        # unless previous relationship transaction is completely spent. 
        # In this test, we do not spend the duplicate relationship transaction first 
        # and then deny the second relationship transaction.

        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        result = self.register_user_1(coinbase_txn)
        result = self.register_user_1(result['txn_2'])
        for txn in block.transactions:
            if txn.transaction_signature == res_txn.transaction_signature:
                return self.output(False, 'Duplicate relationship transaction from unspent relationship should not be included in block')
        return self.output(True, 'Duplicate relationship transaction from unspent relationship excluded from block')

    def test_spent_dup_relationship_from_coinbase(self):
        self.reset()
        print(Fore.BLUE + 'test_dup_relationship_from_coinbase' + Style.RESET_ALL)
        # Test Rule 2. Coinbase transactions cannot create duplicate relationships 
        # unless previous relationship transaction is completely spent. 
        # In this test, we spend the duplicate relationship transaction first 
        # and then allow the second relationship transaction.
        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        dh_public_key, dh_private_key = self.generate_dh()
        relationship_txn = TransactionFactory(
                block_height=1,
                bulletin_secret='MEUCIQCyl/saFzqVSVOC7+udTvFYWFZOsqk0pWh8gUG7h8v1cAIgbxGw6HyJiqlhY4vRptwx+VlCNVCfPjNEVmVzSXq/qmw=',
                username=self.configs['service_provider'].username,
                value=1,
                fee=0.1,
                requester_rid='',
                requested_rid='',
                public_key=self.configs['service_provider'].public_key,
                dh_public_key=dh_public_key,
                private_key=self.configs['service_provider'].private_key,
                dh_private_key=dh_private_key,
                to='13EbNJefRc95nkLFkJvJDycXkowW4sWqSe',
                inputs=[{'id': coinbase_txn.transaction_signature}],
                outputs=[{'to': '13EbNJefRc95nkLFkJvJDycXkowW4sWqSe', 'value': 1}],
                coinbase=False,
                chattext=None,
                signin=None
        )
        bf = self.mine_new_block([relationship_txn.transaction])

        # now we spend the first relationship transaction
        relationship_txn2 = TransactionFactory(
                block_height=1,
                bulletin_secret='',
                username=self.configs['service_provider'].username,
                value=1,
                fee=0.1,
                requester_rid='',
                requested_rid='',
                public_key=self.configs['service_provider'].public_key,
                dh_public_key='',
                private_key=self.configs['service_provider'].private_key,
                dh_private_key='',
                to='13EbNJefRc95nkLFkJvJDycXkowW4sWqSe',
                inputs=[{'id': relationship_txn.transaction_signature}],
                outputs=[{'to': '13EbNJefRc95nkLFkJvJDycXkowW4sWqSe', 'value': 1}],
                coinbase=False,
                chattext=None,
                signin=None
        )
        fgtx = FastGraph.from_dict(2, relationship_txn2.transaction.to_dict())
        fgtx.signatures.append(FastGraphSignature(TU.generate_signature(fgtx.hash, self.config.private_key)))
        bf2 = self.mine_new_block([fgtx])

        coinbase_txn3 = [x for x in bf2.transactions if not x.inputs][0]
        relationship_txn3 = TransactionFactory( # now we build the duplicate transaction
                block_height=1,
                bulletin_secret='MEUCIQCyl/saFzqVSVOC7+udTvFYWFZOsqk0pWh8gUG7h8v1cAIgbxGw6HyJiqlhY4vRptwx+VlCNVCfPjNEVmVzSXq/qmw=',
                username=self.configs['service_provider'].username,
                value=1,
                fee=0.1,
                requester_rid='',
                requested_rid='',
                public_key=self.configs['service_provider'].public_key,
                dh_public_key=dh_public_key,
                private_key=self.configs['service_provider'].private_key,
                dh_private_key=dh_private_key,
                to='13EbNJefRc95nkLFkJvJDycXkowW4sWqSe',
                inputs=[{'id': coinbase_txn3.transaction_signature}],
                outputs=[{'to': '13EbNJefRc95nkLFkJvJDycXkowW4sWqSe', 'value': 1}],
                coinbase=False,
                chattext=None,
                signin=None
        )
        bf3 = self.mine_new_block([relationship_txn3.transaction])
        for txn in bf3.transactions:
            if txn.transaction_signature == relationship_txn3.transaction_signature:
                return self.output(True, 'Duplicate relationship transaction from spent relationship included in block')
        return self.output(True, 'Duplicate relationship transaction from spent relationship should be excluded from block')

    def test_relationship_from_relationship(self):
        self.reset()
        print(Fore.BLUE + 'test_relationship_from_relationship' + Style.RESET_ALL)
        # Test Rule 1. Coinbase transactions must only be used as inputs for relationship creation. 
        # non_relationship_txn should not be included in block
        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        dh_public_key, dh_private_key = self.generate_dh()
        relationship_txn = TransactionFactory(
                block_height=1,
                bulletin_secret='MEUCIQCyl/saFzqVSVOC7+udTvFYWFZOsqk0pWh8gUG7h8v1cAIgbxGw6HyJiqlhY4vRptwx+VlCNVCfPjNEVmVzSXq/qmw=',
                username=self.configs['service_provider'].username,
                value=1,
                fee=0.1,
                requester_rid='',
                requested_rid='',
                public_key=self.configs['service_provider'].public_key,
                dh_public_key=dh_public_key,
                private_key=self.configs['service_provider'].private_key,
                dh_private_key=dh_private_key,
                to='13EbNJefRc95nkLFkJvJDycXkowW4sWqSe',
                inputs=[{'id': coinbase_txn.transaction_signature}],
                outputs=[{'to': '13EbNJefRc95nkLFkJvJDycXkowW4sWqSe', 'value': 1}],
                coinbase=False,
                chattext=None,
                signin=None
        )
        bf = self.mine_new_block([relationship_txn.transaction])

        relationship_txn2 = TransactionFactory(
                block_height=1,
                bulletin_secret='MEUCIQCyl/saFzqVSVOC7+udTvFYWFZOsqk0pWh8gUG7h8v1cAIgbxGw6HyJiqlhY4vRptwx+VlCNVCfPjNEVmVzSXq/qmw=',
                username=self.configs['service_provider'].username,
                value=1,
                fee=0.1,
                requester_rid='',
                requested_rid='',
                public_key=self.configs['service_provider'].public_key,
                dh_public_key=dh_public_key,
                private_key=self.configs['service_provider'].private_key,
                dh_private_key=dh_private_key,
                to='13EbNJefRc95nkLFkJvJDycXkowW4sWqSe',
                inputs=[{'id': relationship_txn.transaction_signature}],
                outputs=[{'to': '13EbNJefRc95nkLFkJvJDycXkowW4sWqSe', 'value': 1}],
                coinbase=False,
                chattext=None,
                signin=None
        )
        bf = self.mine_new_block([relationship_txn2.transaction])
        for txn in bf.transactions:
            if txn.transaction_signature == relationship_txn2.transaction_signature:
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
print(test.test_spent_dup_relationship_from_coinbase())

#relationship txn rules
print(test.test_relationship_from_relationship())

#fastgraph txn rules
