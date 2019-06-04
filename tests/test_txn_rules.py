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
        self.fees = 0.0
        self.friend_reqeust_cost = 1
        self.friend_accept_cost = 1

    def generate_config(self, name):
        self.configs[name] = Config.generate()
        self.configs[name].debug = True
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
        self.configs[name].TU = TU
        consensus = Consensus(prevent_genesis=True)
        self.configs[name].consensus = consensus

    def reset(self):
        for name in self.configs:
            self.configs[name].mongo.db.blocks.remove({})
            self.configs[name].mongo.db.consensus.remove({})
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
        value=1,
        no_relationship=False
    ):
        self.switch_config(from_config)
        if txn_type == 'register':
            dh_public_key, dh_private_key = self.generate_dh()
            bulletin_secret = self.configs[to_config].bulletin_secret
        elif txn_type == 'create_relationship':
            dh_public_key, dh_private_key = self.generate_dh()
            bulletin_secret = self.configs[to_config].bulletin_secret
        elif txn_type == 'fastgraph_send':
            dh_public_key, dh_private_key = '', ''
            bulletin_secret = self.configs[to_config].bulletin_secret
        else:
            dh_public_key, dh_private_key = '', ''
            bulletin_secret = ''
        return TransactionFactory(
            block_height=1,
            bulletin_secret=bulletin_secret,
            username=self.configs[from_config].username,
            value=1,
            fee=self.fees,
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
            signin=None,
            no_relationship=no_relationship
        ).transaction
    
    def send_from_serivce_provider_to_user_1(self, input_txn, value=1):

        # SERVICE PROVIDER <-> USER 1 SEND
        # ==========================================
        # send txn from service provider
        txn = self.generate_transaction(
            'service_provider',
            'user_1',
            '',
            [{'id': input_txn.transaction_signature}],
            value=value
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def send_from_serivce_provider_to_user_2(self, input_txn, value=1):

        # SERVICE PROVIDER <-> USER 2 SEND
        # ==========================================
        # send txn from service provider
        txn = self.generate_transaction(
            'service_provider',
            'user_2',
            '',
            [{'id': input_txn.transaction_signature}],
            value=value
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def fastgraph_send_to_user_1(self, input_txn, value=1):

        # SERVICE PROVIDER <-> USER 1 SEND
        # ==========================================
        # send txn from service provider
        txn = self.generate_transaction(
            'service_provider',
            'user_1',
            'fastgraph_send',
            [{'id': input_txn.transaction_signature}],
            value=value,
            no_relationship=True
        )
        fg = FastGraph.from_dict(0, txn.to_dict())
        fg.signatures = [
            FastGraphSignature(TU.generate_signature(txn.hash, self.configs['user_1'].private_key))
        ]

        block = self.mine_new_block([fg])
        return block, fg
    
    def relationship_serivce_provider_to_user_1(self, input_txn, value=1):

        # SERVICE PROVIDER <-> USER 1 RELATIONSHIP
        # ==========================================
        # relationship txn from service provider
        txn = self.generate_transaction(
            'service_provider',
            'user_1',
            'register',
            [{'id': input_txn.transaction_signature}],
            value=value
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def relationship_user_1_to_serivce_provider(self, input_txn, value=1):

        # SERVICE PROVIDER <-> USER 1 RELATIONSHIP
        # ==========================================
        # relationship txn from user 1
        txn = self.generate_transaction(
            'user_1',
            'service_provider',
            'register',
            [{'id': input_txn.transaction_signature}],
            value=value
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def relationship_serivce_provider_to_user_2(self, input_txn, value=1):

        # SERVICE PROVIDER <-> USER 2 RELATIONSHIP
        # ==========================================
        # relationship txn from service provider
        txn = self.generate_transaction(
            'service_provider',
            'user_2',
            'register',
            [{'id': input_txn.transaction_signature}],
            value=value
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def relationship_user_2_to_serivce_provider(self, input_txn, value=1):

        # SERVICE PROVIDER <-> USER 2 RELATIONSHIP
        # ==========================================
        # relationship txn from user 1
        txn = self.generate_transaction(
            'user_2',
            'service_provider',
            'register',
            [{'id': input_txn.transaction_signature}],
            value=value
        )

        block = self.mine_new_block([txn])
        return block, txn
    
    def relationship_user_1_to_user_2(
        self,
        input_txn,
        user_1_rid,
        user_2_rid,
        value=1
    ):

        # USER 1 <-> USER 2 RELATIONSHIP
        # ==========================================
        # relationship txn from user 1
        txn = self.generate_transaction(
            'user_1',
            'user_2',
            'create_relationship',
            [{'id': input_txn.transaction_signature}],
            requested_rid=user_1_rid,
            requester_rid=user_2_rid,
            value=value
        )
        fg = FastGraph.from_dict(0, txn.to_dict())
        fg.signatures = [
            FastGraphSignature(TU.generate_signature(txn.hash, self.configs['service_provider'].private_key))
        ]

        block = self.mine_new_block([fg])
        return block, txn
    
    def relationship_user_2_to_user_1(
        self,
        input_txn,
        user_1_rid,
        user_2_rid,
        value=1
    ):

        # USER 1 <-> USER 2 RELATIONSHIP
        # ==========================================
        # relationship txn from user 2
        txn = self.generate_transaction(
            'user_2',
            'user_1',
            'create_relationship',
            [{'id': input_txn.transaction_signature}],
            requested_rid=user_1_rid,
            requester_rid=user_2_rid,
            value=value
        )
        fg = FastGraph.from_dict(0, txn.to_dict())
        fg.signatures = [
            FastGraphSignature(TU.generate_signature(txn.hash, self.configs['service_provider'].private_key))
        ]

        block = self.mine_new_block([fg])
        return block, txn

    def register_user_1(self, input_txn, value=1):
        block1, txn1 = self.relationship_serivce_provider_to_user_1(input_txn, value=self.friend_reqeust_cost)
        block2, txn2 = self.relationship_user_1_to_serivce_provider(txn1, value=self.friend_accept_cost)
        return {
            'block_1': block1,
            'block_2': block2,
            'txn_1': txn1,
            'txn_2': txn2
        }

    def register_user_2(self, input_txn, value=1):
        block1, txn1 = self.relationship_serivce_provider_to_user_2(input_txn, value=self.friend_reqeust_cost)
        block2, txn2 = self.relationship_user_2_to_serivce_provider(txn1, value=self.friend_accept_cost)
        return {
            'block_1': block1,
            'block_2': block2,
            'txn_1': txn1,
            'txn_2': txn2
        }

    def fastgraph_user_1_to_user_2_relationship(
        self,
        input_txn,
        user_1_rid,
        user_2_rid,
        value=1
    ):
        block1, txn1 = self.relationship_user_1_to_user_2(
            input_txn,
            user_1_rid,
            user_2_rid,
            value=value
        )
        block2, txn2 = self.relationship_user_2_to_user_1(
            txn1,
            user_1_rid,
            user_2_rid,
            value=value
        )
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

        try:
            result = self.register_user_1(coinbase_txn, value=2)
            return self.output(True, 'Relationship transaction from coinbase included in block')
        except CoinbaseRule1 as e:
            return self.output(False, 'Relationship transaction from coinbase should be included in block')
        except Exception as e:
            return self.output(False, 'Uncaught exception: {}'.format(e))

    def test_non_relationship_from_coinbase(self):
        self.switch_config('service_provider')
        self.reset()
        print(Fore.BLUE + 'test_non_relationship_from_coinbase' + Style.RESET_ALL)
        # Test Rule 1. Coinbase transactions must only be used as inputs for relationship creation. 
        # non_relationship_txn should not be included in block
        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        try:
            block, res_txn = self.send_from_serivce_provider_to_user_1(coinbase_txn, value=2)
            return self.output(False, 'Non-relationship transaction from coinbase should not be included in block')
        except CoinbaseRule1 as e:
            return self.output(True, 'Non-relationship transaction from coinbase excluded from block')
        except Exception as e:
            return self.output(False, 'Uncaught exception: {}'.format(e))

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

        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        try:
            block, res_txn = self.relationship_serivce_provider_to_user_1(coinbase_txn)
            return self.output(False, 'Duplicate relationship transaction from unspent relationship should not be included in block')
        except CoinbaseRule2 as e:
            return self.output(True, 'Duplicate relationship transaction from unspent relationship excluded from block')
        except Exception as e:
            return self.output(False, 'Uncaught exception: {}'.format(e))

    def test_spent_dup_relationship_from_coinbase(self):
        self.reset()
        print(Fore.BLUE + 'test_spent_dup_relationship_from_coinbase' + Style.RESET_ALL)
        # Test Rule 2. Coinbase transactions cannot create duplicate relationships 
        # unless previous relationship transaction is completely spent. 
        # In this test, we spend the duplicate relationship transaction first 
        # and then allow the second relationship transaction.

        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        result = self.register_user_1(coinbase_txn)
        block, res_txn = self.relationship_serivce_provider_to_user_2(result['txn_2']) # in this test, we spend the relationship completely

        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        try:
            block, res_txn = self.relationship_serivce_provider_to_user_1(coinbase_txn)
            return self.output(True, 'Duplicate relationship transaction from spent relationship included in block')
        except CoinbaseRule2 as e:
            return self.output(False, 'Duplicate relationship transaction from spent relationship should be included in block')
        except Exception as e:
            return self.output(False, 'Uncaught exception: {}'.format(e))

    def test_non_relationship_from_relationship(self):
        self.reset()
        print(Fore.BLUE + 'test_non_relationship_from_relationship' + Style.RESET_ALL)
        # Test Rule 1. Relationship transactions must only be used as inputs for relationship creation or fastgraph. 
        # non_relationship_txn should not be included in block

        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        try:
            result = self.register_user_1(coinbase_txn)
            block, res_txn = self.send_from_serivce_provider_to_user_1(result['txn_1']) # in this test, we spend the relationship completely
            return self.output(False, 'Non-relationship transaction with input from relationship should be excluded from block')
        except RelationshipRule1 as e:
            return self.output(True, 'Non-relationship transaction with input from relationship excluded from block')
        except Exception as e:
            return self.output(False, 'Uncaught exception: {}'.format(e))
            

    def test_relationship_from_relationship_different_public_key_input(self):
        self.reset()
        print(Fore.BLUE + 'test_non_relationship_from_relationship_different_public_key_input' + Style.RESET_ALL)
        # Test Rule 2. Relationship transactions with the same public_key cannot be used as inputs for relationship transactions

        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        try:
            result = self.register_user_1(coinbase_txn)
            block, res_txn = self.relationship_serivce_provider_to_user_2(result['txn_2']) # spend the relationship
            return self.output(True, 'Relationship transaction with input from different public_key included in block')
        except RelationshipRule2 as e:
            return self.output(False, 'Relationship transaction transaction with input from different public_key should be excluded from block')
        except Exception as e:
            return self.output(False, 'Uncaught exception: {}'.format(e))

    def test_relationship_from_relationship_same_public_key_input(self):
        self.reset()
        print(Fore.BLUE + 'test_relationship_from_relationship_remainder' + Style.RESET_ALL)
        # Test Rule 2. Relationship transactions with the same public_key cannot be used as inputs for relationship transactions

        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        try:
            result = self.register_user_1(coinbase_txn)
            block, res_txn = self.relationship_serivce_provider_to_user_2(result['txn_1']) # spend the relationship
            return self.output(False, 'Relationship transaction transaction with input from same public_key should be excluded from block')
        except RelationshipRule2 as e:
            return self.output(True, 'Relationship transaction with input from same public_key excluded from block')
        except Exception as e:
            return self.output(False, 'Uncaught exception: {}'.format(e))

    def test_fastgraph_from_relationship(self):
        self.reset()
        print(Fore.BLUE + 'test_fastgraph_from_relationship' + Style.RESET_ALL)
        # Test Rule 1. FastGraph transactions can only be created from relationship or other fastgraph transactions

        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        result2 = self.register_user_2(coinbase_txn)
        result1 = self.register_user_1(result2['txn_2'])

        try:
            block, txn = self.fastgraph_send_to_user_1(result1['txn_2'])
            return self.output(True, 'FastGraph transaction transaction with relationship transaction input included in block')
        except InvalidTransactionException as e:
            return self.output(True, 'FastGraph transaction transaction with relationship transaction input should be included in block')
        except Exception as e:
            return self.output(False, 'Uncaught exception: {}'.format(e))

    def test_fastgraph_from_fastgraph(self):
        self.reset()
        print(Fore.BLUE + 'test_fastgraph_from_fastgraph' + Style.RESET_ALL)
        # Test Rule 1. FastGraph transactions can only be created from relationship or other fastgraph transactions

        block = self.mine_new_block([])
        coinbase_txn = block.transactions[0]

        result2 = self.register_user_2(coinbase_txn)
        result1 = self.register_user_1(result2['txn_2'])
        block, txn = self.fastgraph_send_to_user_1(result1['txn_2'])

        try:
            result = self.fastgraph_user_1_to_user_2_relationship(
                txn,
                result1['txn_2'].rid,
                result2['txn_2'].rid,
            )
            return self.output(True, 'FastGraph transaction transaction with FastGraph transaction input included in block')
        except InvalidTransactionException as e:
            return self.output(True, 'FastGraph transaction transaction with FastGraph transaction input should be included in block')
        except Exception as e:
            return self.output(False, 'Uncaught exception: {}'.format(e))
        
    
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
print(test.test_non_relationship_from_relationship())
print(test.test_relationship_from_relationship_different_public_key_input())
print(test.test_relationship_from_relationship_same_public_key_input())

#fastgraph txn rules
print(test.test_fastgraph_from_relationship())
print(test.test_fastgraph_from_fastgraph())
