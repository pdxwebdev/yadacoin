from socketIO_client import SocketIO, BaseNamespace
from exceptions import Exception
from blockchain import Blockchain
from mongo import Mongo
from config import Config
from peers import Peers
from block import Block
from blockchainutils import BU
from transaction import Transaction, TransactionFactory, Input, Output, NotEnoughMoneyException
from transactionutils import TU


class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

class NonMatchingDifficultyException(Exception):
    pass

class PartialPayoutException(Exception):
    pass

class PoolPayer(object):
    def get_share_list_for_height(self, index):
        raw_shares = [x for x in Mongo.db.shares.find({'index': index})]
        test = Blockchain([x['block'] for x in raw_shares])
        total_difficulty = test.get_difficulty()

        shares = {}
        for share in raw_shares:
            if share['address'] not in shares:
                shares[share['address']] = {
                    'blocks': []
                }
            shares[share['address']]['blocks'].append(share['block'])

        add_up = 0
        for address, item in shares.iteritems():
            test = Blockchain(item['blocks'])
            test_difficulty = test.get_difficulty()
            shares[address]['payout_share'] = float(test_difficulty) / float(total_difficulty)
            add_up += test_difficulty

        if add_up == total_difficulty:
            return shares
        else:
            raise NonMatchingDifficultyException()

    def do_payout(self):
        Mongo.init()
        Peers.init()
        # first check which blocks we won.
        # then determine if we have already paid out
        # they must be 6 blocks deep
        latest_block = Block.from_dict(BU.get_latest_block())
        won_blocks = Mongo.db.blocks.find({'transactions.outputs.to': Config.address}).sort([('index', 1)])
        for won_block in won_blocks:
            won_block = Block.from_dict(won_block)
            if (won_block.index + 6) <= latest_block.index:
                self.do_payout_for_block(won_block)
    
    def already_used(self, txn):
        return Mongo.db.blocks.find_one({'transactions.inputs.id': txn.transaction_signature})

    def do_payout_for_block(self, block):
        # check if we already paid out

        already_used = self.already_used(block.get_coinbase())
        if already_used:
            return

        existing = Mongo.db.share_payout.find_one({'index': block.index})
        if existing:
            pending = Mongo.db.miner_transactions.find_one({'inputs.id': block.get_coinbase().transaction_signature})
            if pending:
                return
            else:
                # rebroadcast
                transaction = Transaction.from_dict(existing['txn'])
                TU.save(transaction)
                self.broadcast_transaction(transaction)
                return

        try:
            shares = self.get_share_list_for_height(block.index)
        except:
            return

        total_reward = block.get_coinbase()
        if total_reward.outputs[0].to != Config.address:
            return
        pool_take = 0.01
        total_pool_take = total_reward.outputs[0].value * pool_take
        total_payout = total_reward.outputs[0].value - total_pool_take

        outputs = []
        for address, x in shares.iteritems():
            exists = Mongo.db.share_payout.find_one({'index': block.index, 'txn.outputs.to': address})
            if exists:
                raise PartialPayoutException('this index has been partially paid out.')
            
            payout = total_payout * x['payout_share']
            outputs.append(Output(to=address, value=payout))

        try:
            transaction = TransactionFactory(
                fee=0.0001,
                public_key=Config.public_key,
                private_key=Config.private_key,
                inputs=[Input(total_reward.transaction_signature)],
                outputs=outputs
            )
        except NotEnoughMoneyException as e:
            print "not enough money yet"
            return
        except Exception as e:
            print e

        try:
            transaction.transaction.verify()
        except:
            raise
            print 'faucet transaction failed'

        TU.save(transaction.transaction)
        Mongo.db.share_payout.insert({'index': block.index, 'txn': transaction.transaction.to_dict()})

        self.broadcast_transaction(transaction.transaction)
        
    def broadcast_transaction(self, transaction):
        for peer in Peers.peers:
            try:
                print peer.to_string()
                socketIO = SocketIO(peer.host, peer.port, wait_for_connection=False)
                chat_namespace = socketIO.define(ChatNamespace, '/chat')
                chat_namespace.emit('newtransaction', transaction.to_dict())
                socketIO.disconnect()
            except Exception as e:
                print e