import time
import requests
from bitcoin.wallet import P2PKHBitcoinAddress
from config import Config
from mongo import Mongo
from peers import Peers
from block import Block, BlockFactory
from blockchain import Blockchain
from blockchainutils import BU
from transaction import (
    Transaction,
    MissingInputTransactionException,
    InvalidTransactionException,
    InvalidTransactionSignatureException
)
from fastgraph import FastGraph


class MiningPool(object):
    def __init__(self, config, mongo):
        self.config = config
        self.mongo = mongo
        self.block_factory = None

    def refresh(self):
        Peers.init(self.config, self.mongo, self.config.network)
        if self.config.network == 'mainnet':
            max_block_time = 600
        elif self.config.network == 'testnet':
            max_block_time = 10
        block = BU.get_latest_block(self.config, self.mongo)
        if block:
            block = Block.from_dict(self.config, self.mongo, block)
            self.height = block.index + 1
        else:
            genesis_block = BlockFactory.get_genesis_block(self.config, self.mongo)
            genesis_block.save()
            self.mongo.db.consensus.insert({
                'block': genesis_block.to_dict(),
                'peer': 'me',
                'id': genesis_block.signature,
                'index': 0
                })
            block = Block.from_dict(self.config, self.mongo, BU.get_latest_block(self.config, self.mongo))
            self.height = block.index

        try:
            if self.height > 0:
                last_time = block.time
            special_min = False
            max_target = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
            if self.height > 0:
                time_elapsed_since_last_block = int(time.time()) - int(last_time)

                # special min case
                if time_elapsed_since_last_block > max_block_time:
                    target = max_target
                    special_min = True
            self.target = BlockFactory.get_target(self.config, self.mongo, self.height, last_time, block, Blockchain(self.config, self.mongo, [x for x in BU.get_blocks(self.config, self.mongo)]))

            self.block_factory = BlockFactory(
                config=self.config,
                mongo=self.mongo,
                transactions=self.get_pending_transactions(),
                public_key=self.config.public_key,
                private_key=self.config.private_key,
                index=self.height,
                version=BU.get_version_for_height(self.height))
            self.block_factory.block.special_min = special_min
            self.block_factory.block.target = self.target
            self.block_factory.header = BlockFactory.generate_header(self.block_factory.block)
        except Exception as e:
            raise
    
    def nonce_generator(self):
        latest_block_index = BU.get_latest_block(self.config, self.mongo)['index']
        while 1:
            next_latest_block_index = BU.get_latest_block(self.config, self.mongo)['index']
            if latest_block_index < next_latest_block_index:
                latest_block_index = next_latest_block_index
                start_nonce = 0
                self.refresh()
            else:
                try:
                    start_nonce += 1000000
                except:
                    start_nonce = 0
            self.index = latest_block_index
            yield [start_nonce, start_nonce + 1000000]

    def combine_transaction_lists(self):
        transactions = self.mongo.db.fastgraph_transactions.find()
        for transaction in transactions:
            if 'txn' in transaction:
                yield transaction['txn']

        transactions = self.mongo.db.miner_transactions.find()
        for transaction in transactions:
            yield transaction
        

    def get_pending_transactions(self):
        transaction_objs = []
        unspent_indexed = {}
        unspent_fastgraph_indexed = {}
        used_sigs = []
        for txn in self.combine_transaction_lists():
            try:
                if isinstance(txn, FastGraph) and hasattr(txn, 'signatures'):
                    transaction_obj = txn
                elif isinstance(txn, Transaction):
                    transaction_obj = txn
                elif isinstance(txn, dict) and 'signatures' in txn:
                    transaction_obj = FastGraph.from_dict(self.config, self.mongo, txn)
                elif isinstance(txn, dict):
                    transaction_obj = Transaction.from_dict(self.config, self.mongo, txn)
                else:
                    print 'transaction unrecognizable, skipping'
                    continue

                if transaction_obj.transaction_signature in used_sigs:
                    print 'duplicate transaction found and removed'
                    continue
                used_sigs.append(transaction_obj.transaction_signature)

                transaction_obj.verify()

                if not isinstance(transaction_obj, FastGraph) and transaction_obj.rid:
                    for input_id in transaction_obj.inputs:
                        input_block = BU.get_transaction_by_id(self.config, self.mongo, input_id.id, give_block=True)
                        if input_block['index'] > (BU.get_latest_block(self.config, self.mongo)['index'] - 2016):
                            continue

                #check double spend
                address = str(P2PKHBitcoinAddress.from_pubkey(transaction_obj.public_key.decode('hex')))
                if address in unspent_indexed:
                    unspent_ids = unspent_indexed[address]
                else:
                    needed_value = sum([float(x.value) for x in transaction_obj.outputs]) + float(transaction_obj.fee)
                    res = BU.get_wallet_unspent_transactions(self.config, self.mongo, address, needed_value=needed_value)
                    unspent_ids = [x['id'] for x in res]
                    unspent_indexed[address] = unspent_ids
            
                if address in unspent_fastgraph_indexed:
                    unspent_fastgraph_ids = unspent_fastgraph_indexed[address]
                else:
                    res = BU.get_wallet_unspent_fastgraph_transactions(self.config, self.mongo, address)
                    unspent_fastgraph_ids = [x['id'] for x in res]
                    unspent_fastgraph_indexed[address] = unspent_fastgraph_ids

                failed1 = False
                failed2 = False
                used_ids_in_this_txn = []

                for x in transaction_obj.inputs:
                    if x.id not in unspent_ids:
                        failed1 = True
                    if x.id in used_ids_in_this_txn:
                        failed2 = True
                    used_ids_in_this_txn.append(x.id)
                if failed1:
                    self.mongo.db.miner_transactions.remove({'id': transaction_obj.transaction_signature})
                    print 'transaction removed: input presumably spent already, not in unspent outputs', transaction_obj.transaction_signature
                    self.mongo.db.failed_transactions.insert({'reason': 'input presumably spent already', 'txn': transaction_obj.to_dict()})
                elif failed2:
                    self.mongo.db.miner_transactions.remove({'id': transaction_obj.transaction_signature})
                    print 'transaction removed: using an input used by another transaction in this block', transaction_obj.transaction_signature
                    self.mongo.db.failed_transactions.insert({'reason': 'using an input used by another transaction in this block', 'txn': transaction_obj.to_dict()})
                else:
                    transaction_objs.append(transaction_obj)
            except MissingInputTransactionException as e:
                #print 'missing this input transaction, will try again later'
                pass
            except InvalidTransactionSignatureException as e:
                print 'InvalidTransactionSignatureException: transaction removed'
                self.mongo.db.miner_transactions.remove({'id': transaction_obj.transaction_signature})
                self.mongo.db.failed_transactions.insert({'reason': 'InvalidTransactionSignatureException', 'txn': transaction_obj.to_dict()})
            except InvalidTransactionException as e:
                print 'InvalidTransactionException: transaction removed'
                self.mongo.db.miner_transactions.remove({'id': transaction_obj.transaction_signature})
                self.mongo.db.failed_transactions.insert({'reason': 'InvalidTransactionException', 'txn': transaction_obj.to_dict()})
            except Exception as e:
                print e
                #print 'rejected transaction', txn['id']
                pass
            except BaseException as e:
                print e
                #print 'rejected transaction', txn['id']
                pass
        return transaction_objs
    
    def pool_mine(self, pool_peer, address, header, target, nonces, special_min):
        nonce, lhash = BlockFactory.mine(header, target, nonces, special_min)
        if nonce and lhash:
            requests.post("http://{pool}/pool-submit".format(pool=pool_peer), json={
                'nonce': nonce,
                'hash': lhash,
                'address': address
            }, headers={'Connection':'close'})
    
    def broadcast_block(self, block):
        Peers.init(self.config, self.mongo, self.config.network)
        dup_test = self.mongo.db.consensus.find_one({
            'peer': 'me',
            'index': block.index,
            'block.version': BU.get_version_for_height(block.index)
        })
        if not dup_test:
            print '\r\nCandidate submitted for index:', block.index
            print '\r\nTransactions:'
            for x in block.transactions:
                print x.transaction_signature 
            self.mongo.db.consensus.insert({'peer': 'me', 'index': block.index, 'id': block.signature, 'block': block.to_dict()})
            print '\r\nSent block to:'
            for peer in Peers.peers:
                if peer.is_me:
                    continue
                try:
                    block_dict = block.to_dict()
                    block_dict['peer'] = Peers.my_peer
                    requests.post(
                        'http://{peer}/newblock'.format(
                            peer=peer.host + ":" + str(peer.port)
                        ),
                        json=block_dict,
                        timeout=3,
                        headers={'Connection':'close'}
                    )
                    print peer.host + ":" + str(peer.port)
                except Exception as e:
                    print e
                    try:
                        print 'reporting bad peer'
                        if self.config.network == 'mainnet':
                            url = 'https://yadacoin.io/peers'
                        elif self.config.network == 'testnet':
                            url = 'http://yadacoin.io:8888/peers'
                        requests.post(
                            url,
                            json={'host': peer.host, 'port': str(peer.port), 'failed': True},
                            timeout=3,
                            headers={'Connection':'close'}
                        )
                    except:
                        print 'failed to report bad peer'
                        pass
