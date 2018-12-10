import time
import requests
from bitcoin.wallet import P2PKHBitcoinAddress
from config import Config
from mongo import Mongo
from peers import Peers
from block import Block, BlockFactory
from blockchain import Blockchain
from blockchainutils import BU
from transaction import Transaction, MissingInputTransactionException, \
    InvalidTransactionException, \
    InvalidTransactionSignatureException


class MiningPool(object):
    @classmethod
    def pool_init(cls, config):
        Config.from_dict(config)
        Mongo.init()
        Peers.init()
        max_block_time = 600
        block = BU.get_latest_block()
        if block:
            block = Block.from_dict(block)
            cls.height = block.index + 1
        else:
            genesis_block = BlockFactory.get_genesis_block()
            genesis_block.save()
            Mongo.db.consensus.insert({
                'block': genesis_block.to_dict(),
                'peer': 'me',
                'id': genesis_block.signature,
                'index': 0
                })
            block = Block.from_dict(BU.get_latest_block())
            cls.height = block.index

        try:
            if cls.height > 0:
                last_time = block.time
            special_min = False
            max_target = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
            if cls.height > 0:
                time_elapsed_since_last_block = int(time.time()) - int(last_time)

                # special min case
                if time_elapsed_since_last_block > max_block_time:
                    target = max_target
                    special_min = True
            cls.target = BlockFactory.get_target(cls.height, last_time, block, Blockchain([x for x in BU.get_blocks()]))

            cls.block_factory = BlockFactory(
                transactions=MiningPool.get_pending_transactions(),
                public_key=Config.public_key,
                private_key=Config.private_key,
                index=cls.height,
                version=BU.get_version_for_height(cls.height))
            cls.block_factory.block.special_min = special_min
            cls.block_factory.block.target = cls.target
            cls.block_factory.header = BlockFactory.generate_header(cls.block_factory.block)
        except Exception as e:
            raise
    
    @classmethod
    def nonce_generator(cls):
        Mongo.init()
        latest_block_index = BU.get_latest_block()['index']
        while 1:
            next_latest_block_index = BU.get_latest_block()['index']
            if latest_block_index < next_latest_block_index:
                latest_block_index = next_latest_block_index
                start_nonce = 0
                cls.pool_init(Config.to_dict())
            else:
                try:
                    start_nonce += 1000000
                except:
                    start_nonce = 0
            MiningPool.index = latest_block_index
            yield [start_nonce, start_nonce + 1000000]

    @classmethod
    def get_pending_transactions(cls):
        transactions = Mongo.db.miner_transactions.find()
        transaction_objs = []
        unspent_indexed = {}
        for txn in transactions:
            try:
                transaction = Transaction.from_dict(txn)
                transaction.verify()
                #check double spend
                address = str(P2PKHBitcoinAddress.from_pubkey(transaction.public_key.decode('hex')))
                if address in unspent_indexed:
                    unspent_ids = unspent_indexed[address]
                else:
                    needed_value = sum([float(x.value) for x in transaction.outputs]) + float(transaction.fee)
                    res = BU.get_wallet_unspent_transactions(address, needed_value=needed_value)
                    unspent_ids = [x['id'] for x in res]
                    unspent_indexed[address] = unspent_ids
                failed1 = False
                failed2 = False
                used_ids_in_this_txn = []

                for x in transaction.inputs:
                    if x.id not in unspent_ids:
                        failed1 = True
                    if x.id in used_ids_in_this_txn:
                        failed2 = True
                    used_ids_in_this_txn.append(x.id)
                if failed1:
                    Mongo.db.miner_transactions.remove({'id': transaction.transaction_signature})
                    print 'transaction removed: input presumably spent already, not in unspent outputs', transaction.transaction_signature
                    Mongo.db.failed_transactions.insert({'reason': 'input presumably spent already', 'txn': transaction.to_dict()})
                elif failed2:
                    Mongo.db.miner_transactions.remove({'id': transaction.transaction_signature})
                    print 'transaction removed: using an input used by another transaction in this block', transaction.transaction_signature
                    Mongo.db.failed_transactions.insert({'reason': 'using an input used by another transaction in this block', 'txn': transaction.to_dict()})
                else:
                    transaction_objs.append(transaction)
            except MissingInputTransactionException as e:
                #print 'missing this input transaction, will try again later'
                pass
            except InvalidTransactionSignatureException as e:
                print 'InvalidTransactionSignatureException: transaction removed'
                Mongo.db.miner_transactions.remove({'id': transaction.transaction_signature})
                Mongo.db.failed_transactions.insert({'reason': 'InvalidTransactionSignatureException', 'txn': transaction.to_dict()})
            except InvalidTransactionException as e:
                print 'InvalidTransactionException: transaction removed'
                Mongo.db.miner_transactions.remove({'id': transaction.transaction_signature})
                Mongo.db.failed_transactions.insert({'reason': 'InvalidTransactionException', 'txn': transaction.to_dict()})
            except Exception as e:
                #print e
                #print 'rejected transaction', txn['id']
                pass
            except BaseException as e:
                #print e
                #print 'rejected transaction', txn['id']
                pass
        return transaction_objs
    
    @classmethod
    def pool_mine(cls, pool_peer, address, header, target, nonces, special_min):
        nonce, lhash = BlockFactory.mine(header, target, nonces, special_min)
        if nonce and lhash:
            requests.post("http://{pool}/pool-submit".format(pool=pool_peer), json={
                'nonce': nonce,
                'hash': lhash,
                'address': address
            }, headers={'Connection':'close'})
    
    @classmethod
    def broadcast_block(cls, block):
        Peers.init()
        dup_test = Mongo.db.consensus.find_one({
            'peer': 'me',
            'index': block.index,
            'block.version': BU.get_version_for_height(block.index)
        })
        if not dup_test:
            print '\r\nCandidate submitted for index:', block.index
            print '\r\nTransactions:'
            for x in block.transactions:
                print x.transaction_signature 
            Mongo.db.consensus.insert({'peer': 'me', 'index': block.index, 'id': block.signature, 'block': block.to_dict()})
            print '\r\nSent block to:'
            for peer in Peers.peers:
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
                        requests.post(
                            Peers.url,
                            json={'host': peer.host, 'port': str(peer.port), 'failed': True},
                            timeout=3,
                            headers={'Connection':'close'}
                        )
                    except:
                        print 'failed to report bad peer'
                        pass
