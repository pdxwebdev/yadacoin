from logging import getLogger
from socketIO_client import SocketIO, BaseNamespace

from yadacoin.chain import CHAIN
from yadacoin.config import get_config
from yadacoin.peers import Peers
from yadacoin.block import Block
# from yadacoin.blockchainutils import BU
from yadacoin.transaction import Transaction, TransactionFactory, Input, Output, NotEnoughMoneyException
from yadacoin.transactionutils import TU


class NonMatchingDifficultyException(Exception):
    pass


class PartialPayoutException(Exception):
    pass


class PoolPayer(object):

    def __init__(self):
        self.config = get_config()
        self.app_log = getLogger('tornado.application')
    
    def get_difficulty(self, blocks):
        difficulty = 0
        for block in blocks:
            target = int(block['hash'], 16)
            difficulty += CHAIN.MAX_TARGET - target
        return difficulty

    async def get_share_list_for_height(self, index):
        raw_shares = []
        async for x in self.config.mongo.async_db.shares.find({'index': index}).sort([('index', 1)]):
            raw_shares.append(x)
        if not raw_shares:
            raise Exception('no shares')
        total_difficulty = self.get_difficulty([x['block'] for x in raw_shares])

        shares = {}
        for share in raw_shares:
            if share['address'] not in shares:
                shares[share['address']] = {
                    'blocks': [],
                    'bulletin_secret': share['bulletin_secret'],
                }
            shares[share['address']]['blocks'].append(share['block'])

        add_up = 0
        for address, item in shares.items():
            test_difficulty = self.get_difficulty(item['blocks'])
            shares[address]['payout_share'] = float(test_difficulty) / float(total_difficulty)
            add_up += test_difficulty

        if add_up == total_difficulty:
            return shares
        else:
            raise NonMatchingDifficultyException()

    async def do_payout(self):
        # first check which blocks we won.
        # then determine if we have already paid out
        # they must be 6 blocks deep
        latest_block = Block.from_dict(await self.config.BU.get_latest_block_async())
        won_blocks = self.config.mongo.async_db.blocks.find({'transactions.outputs.to': self.config.address, 'index': 37467}).sort([('index', 1)])
        async for won_block in won_blocks:
            won_block = Block.from_dict(won_block)
            if self.config.debug:
                self.app_log.debug(won_block.index)
            if (won_block.index + 6) <= latest_block.index:
                await self.do_payout_for_block(won_block)
    
    async def already_used(self, txn):
        return await self.config.mongo.async_db.blocks.find_one({'transactions.inputs.id': txn.transaction_signature})

    async def do_payout_for_block(self, block):
        # check if we already paid out

        already_used = await self.already_used(block.get_coinbase())
        if already_used:
            await self.config.mongo.async_db.shares.delete_many({'index': block.index})
            return

        existing = await self.config.mongo.async_db.share_payout.find_one({'index': block.index})
        if existing:
            pending = await self.config.mongo.async_db.miner_transactions.find_one({'inputs.id': block.get_coinbase().transaction_signature})
            if pending:
                return
            else:
                # rebroadcast
                latest_block = await self.config.BU.get_latest_block_async()
                transaction = Transaction.from_dict(latest_block['index'], existing['txn'])
                await self.config.mongo.async_db.miner_transactions.insert_one(transaction.to_dict())
                await self.broadcast_transaction(transaction)
                return

        try:
            shares = await self.get_share_list_for_height(block.index)
        except KeyError as e:
            if self.config.debug:
                self.app_log.debug(e)
            return
        except Exception as e:
            if self.config.debug:
                self.app_log.debug(e)
            return

        total_reward = block.get_coinbase()
        if total_reward.outputs[0].to != self.config.address:
            return
        pool_take = 0.01
        total_pool_take = total_reward.outputs[0].value * pool_take
        total_payout = total_reward.outputs[0].value - total_pool_take

        transactions_to_transmit = []
        outputs = []
        for address, x in shares.items():
            exists = await self.config.mongo.async_db.share_payout.find_one({'index': block.index, 'txn.outputs.to': address})
            if exists:
                raise PartialPayoutException('this index has been partially paid out.')
            
            payout = total_payout * x['payout_share']
            outputs.append({'to': address, 'value': payout})

            try:
                transaction = TransactionFactory(
                    block_height=block.index,
                    fee=0.0001,
                    public_key=self.config.public_key,
                    private_key=self.config.private_key,
                    inputs=[{'id': total_reward.transaction_signature}],
                    outputs=outputs,
                    bulletin_secret=x['bulletin_secret']
                )
            except NotEnoughMoneyException as e:
                if self.config.debug:
                    self.app_log.debug("not enough money yet")
                    self.app_log.debug(e)
                return
            except Exception as e:
                if self.config.debug:
                    self.app_log.debug(e)

            try:
                transaction.transaction.verify()
            except Exception as e:
                if self.config.debug:
                    self.app_log.debug(e)
                raise
            transactions_to_transmit.append(transaction.transaction)

        for txn in transactions_to_transmit:
            if self.config.peers.peers:
                await self.config.mongo.async_db.miner_transactions.insert_one(txn.to_dict())
                await self.config.mongo.async_db.share_payout.insert_one({'index': block.index, 'txn': txn.to_dict()})
                await self.broadcast_transaction(txn)
        
    async def broadcast_transaction(self, transaction):
        for peer in self.config.peers.peers:
            if peer.host in self.config.outgoing_blacklist or not (peer.client and peer.client.connected):
                continue
            try:
                if self.config.debug:
                    self.app_log.debug('Transmitting pool payout transaction to: {}'.format(peer.to_string()))
                await peer.client.client.emit('newtransaction', data=transaction.to_dict(), namespace='/chat')
            except Exception as e:
                if self.config.debug:
                    self.app_log.debug(e)