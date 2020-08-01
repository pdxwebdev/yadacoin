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
        total_difficulty = self.get_difficulty([x for x in raw_shares])
        shares = {}
        for share in raw_shares:
            if share['address'] not in shares:
                shares[share['address']] = {
                    'blocks': [],
                }
            shares[share['address']]['blocks'].append(share)

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
        latest_block = await Block.from_dict(await self.config.BU.get_latest_block_async())
        already_paid_height = await self.config.mongo.async_db.share_payout.find_one({}, sort=[('index', -1)])
        won_blocks = self.config.mongo.async_db.blocks.find({'transactions.outputs.to': self.config.address, 'index': {'$gt': already_paid_height.get('index', 0)}}).sort([('index', 1)])
        ready_blocks = []
        do_payout = False
        async for won_block in won_blocks:
            won_block = await Block.from_dict(won_block)
            coinbase = won_block.get_coinbase()
            if coinbase.outputs[0].to != self.config.address:
                continue
            if self.config.debug:
                self.app_log.debug(won_block.index)
            if (won_block.index + 6) <= latest_block.index:
                if len(ready_blocks) >= 6:
                    if self.config.debug:
                        self.app_log.debug('entering payout at block: {}'.format( won_block.index))
                    do_payout = True
                    break
                else:
                    if self.config.debug:
                        self.app_log.debug('block added for payout {}'.format(won_block.index))
                    ready_blocks.append(won_block)
        if do_payout:
            await self.do_payout_for_blocks(ready_blocks)


    async def already_used(self, txn):
        return await self.config.mongo.async_db.blocks.find_one({'transactions.inputs.id': txn.transaction_signature})

    async def do_payout_for_blocks(self, blocks):
        # check if we already paid out
        outputs = {}
        coinbases = []
        for block in blocks:
            if self.config.debug:
                self.app_log.debug('do_payout_for_blocks begin loop {}'.format(block.index))
            already_used = await self.already_used(block.get_coinbase())
            if already_used:
                await self.config.mongo.async_db.shares.delete_many({'index': block.index})
                return

            if self.config.debug:
                self.app_log.debug('do_payout_for_blocks passed already_used {}'.format(block.index))
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
            if self.config.debug:
                self.app_log.debug('do_payout_for_blocks passed existing {}'.format(block.index))
            try:
                shares = await self.get_share_list_for_height(block.index)
            except KeyError as e:
                self.app_log.warning(e)
                return
            except Exception as e:
                self.app_log.warning(e)
                return
            if self.config.debug:
                self.app_log.debug('do_payout_for_blocks passed get_share_list_for_height {}'.format(block.index))
            coinbase = block.get_coinbase()
            if coinbase.outputs[0].to != self.config.address:
                return
            if self.config.debug:
                self.app_log.debug('do_payout_for_blocks passed address compare {}'.format(block.index))
            pool_take = 0.01
            total_pool_take = coinbase.outputs[0].value * pool_take
            total_payout = coinbase.outputs[0].value - total_pool_take
            coinbases.append(coinbase)

            if self.config.debug:
                self.app_log.debug('do_payout_for_blocks passed coinbase calcs {}'.format(block.index))
            for address, x in shares.items():
                if self.config.debug:
                    self.app_log.debug('do_payout_for_blocks shares loop {}'.format(block.index))
                exists = await self.config.mongo.async_db.share_payout.find_one({'index': block.index, 'txn.outputs.to': address})
                if exists:
                    raise PartialPayoutException('this index has been partially paid out.')

                if self.config.debug:
                    self.app_log.debug('do_payout_for_blocks passed shares exists {}'.format(block.index))
                if address not in outputs:
                    outputs[address] = 0.0
                payout = total_payout * x['payout_share']
                outputs[address] += payout
                if self.config.debug:
                    self.app_log.debug('do_payout_for_blocks passed adding payout to outputs {}'.format(block.index))

        outputs_formatted = []
        for address, output in outputs.items():
            outputs_formatted.append({
                'to': address,
                'value': output
            })
        if self.config.debug:
            self.app_log.debug('do_payout_for_blocks done formatting outputs {}'.format([{'id': coinbase.transaction_signature for coinbase in coinbases}]))
        try:
            transaction = await TransactionFactory.construct(
                block_height=block.index,
                fee=0.0001,
                public_key=self.config.public_key,
                private_key=self.config.private_key,
                inputs=[{'id': coinbase.transaction_signature for coinbase in coinbases}],
                outputs=outputs_formatted,
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

        txn = transaction.transaction
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
