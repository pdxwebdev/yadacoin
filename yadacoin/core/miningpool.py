from traceback import format_exc
import uuid
import random
import json
from time import time
import binascii
from logging import getLogger

from yadacoin.core.chain import CHAIN
from yadacoin.core.config import get_config
from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.transaction import (
    Transaction
)
from yadacoin.core.transactionutils import TU
from yadacoin.tcpsocket.pool import StratumServer
from yadacoin.core.job import Job
from yadacoin.core.processingqueue import BlockProcessingQueueItem


class MiningPool(object):
    @classmethod
    async def init_async(cls):
        self = cls()
        self.config = get_config()
        self.mongo = self.config.mongo
        self.app_log = getLogger("tornado.application")
        self.target_block_time = CHAIN.target_block_time(self.config.network)
        self.max_target = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        self.inbound = {}
        self.connected_ips = {}
        self.last_block_time = 0
        self.index = 0
        last_block = await self.config.LatestBlock.block.copy()
        self.refreshing = False
        if last_block:
            self.last_block_time = int(last_block.time)
            self.index = last_block.index
        self.last_refresh = 0
        self.block_factory = None
        await self.refresh()
        return self

    def get_status(self):
        """Returns pool status as explicit dict"""
        status = {"miners": len(self.inbound), "ips": len(self.connected_ips)}
        return status

    def little_hash(self, block_hash):
        little_hex = bytearray.fromhex(block_hash)
        little_hex.reverse()

        str_little = ''.join(format(x, '02x') for x in little_hex)

        return str_little

    async def process_nonce_queue(self):
        item = self.config.processing_queues.nonce_queue.pop()
        i = 0 # max loops
        while item:
            self.config.processing_queues.nonce_queue.inc_num_items_processed()
            body = item.body
            stream = item.stream
            miner = item.miner
            nonce = body['params'].get('nonce')
            job = stream.jobs[body['params']['id']]
            if type(nonce) is not str:
                result = {'error': True, 'message': 'nonce is wrong data type'}
            if len(nonce) > CHAIN.MAX_NONCE_LEN:
                result = {'error': True, 'message': 'nonce is too long'}
            data = {
                'id': body.get('id'),
                'method': body.get('method'),
                'jsonrpc': body.get('jsonrpc')
            }
            data['result'] = await self.process_nonce(
                miner,
                nonce,
                job
            )
            if not data['result']:
                data['error'] = {'message': 'Invalid hash for current block'}
            try:
                await stream.write('{}\n'.format(json.dumps(data)).encode())
            except:
                pass
            if 'error' in data:
                await StratumServer.send_job(stream)

            await StratumServer.block_checker()

            i += 1
            if i >= 1000:
                self.config.app_log.info('process_nonce_queue: max loops exceeded, exiting')
                return

            item = self.config.processing_queues.nonce_queue.pop()

    async def process_nonce(self, miner, nonce, job):
        nonce = nonce
        header = binascii.unhexlify(job.blob).decode().replace('{00}', '{nonce}')
        hash1 = self.block_factory.generate_hash_from_header(
            job.index,
            header,
            nonce
        )
        if self.block_factory.index >= CHAIN.BLOCK_V5_FORK:
            hash1_test = self.little_hash(hash1)
        else:
            hash1_test = hash1

        if (
            int(hash1_test, 16) > self.block_factory.target and
            self.config.network != 'regnet' and
            (self.block_factory.special_min and
            int(hash1, 16) > self.block_factory.special_target)
        ):
            return False
        block_candidate = await self.block_factory.copy()
        block_candidate.hash = hash1
        block_candidate.nonce = nonce

        if block_candidate.special_min:
            delta_t = int(block_candidate.time) - int(self.last_block_time)
            special_target = CHAIN.special_target(
                block_candidate.index,
                block_candidate.target,
                delta_t,
                self.config.network
            )
            block_candidate.special_target = special_target

        if (
            block_candidate.index >= 35200 and
            (int(block_candidate.time) - int(self.last_block_time)) < 600 and
            block_candidate.special_min and
            self.config.network == 'mainnet'
        ):
            self.app_log.warning("Special min block too soon: hash {} header {} nonce {}".format(
                block_candidate.hash,
                block_candidate.header,
                block_candidate.nonce
            ))
            return False

        accepted = False

        target = 0x0000FFFF00000000000000000000000000000000000000000000000000000000

        if block_candidate.index >= CHAIN.BLOCK_V5_FORK:
            test_hash = int(block_candidate.little_hash(), 16)
        else:
            test_hash = int(hash1, 16)

        if test_hash < target:
            # submit share only now, not to slow down if we had a block
            await self.mongo.async_db.shares.update_one(
                {
                    'hash': block_candidate.hash
                },
                {
                    '$set': {
                        'address': miner.address,
                        'address_only': miner.address_only,
                        'index': block_candidate.index,
                        'hash': block_candidate.hash,
                        'nonce': nonce,
                        'time': int(time())
                    }
                },
                upsert=True
            )

            accepted = True

        if block_candidate.index >= CHAIN.BLOCK_V5_FORK:
            test_hash = int(block_candidate.little_hash(), 16)
        else:
            test_hash = int(block_candidate.hash, 16)

        if (
          test_hash < int(block_candidate.target) or
          self.config.network == 'regnet'
        ):
            block_candidate.signature = self.config.BU.generate_signature(block_candidate.hash, self.config.private_key)

            if header != block_candidate.header:
                return {
                    'hash': block_candidate.hash,
                    'nonce': nonce,
                    'height': block_candidate.index,
                    'id': block_candidate.signature
                }
            try:
                await block_candidate.verify()
            except Exception as e:
                if accepted and self.config.network == 'mainnet':
                    return {
                        'hash': hash1,
                        'nonce': nonce,
                        'height': job.index,
                        'id': block_candidate.signature
                    }

                return False
            # accept winning block
            await self.accept_block(block_candidate)
            # Conversion to dict is important, or the object may change
            self.app_log.debug('block ok')

            return {
                'accepted': accepted,
                'hash': block_candidate.hash,
                'nonce': nonce,
                'height': block_candidate.index,
                'id': block_candidate.signature
            }
        elif (
          block_candidate.special_min and (int(block_candidate.special_target) > int(block_candidate.hash, 16)) or
          (
            block_candidate.index >= CHAIN.BLOCK_V5_FORK and
            block_candidate.special_min and (int(block_candidate.special_target) > int(block_candidate.little_hash(), 16))
          )
        ):
            block_candidate.signature = self.config.BU.generate_signature(block_candidate.hash, self.config.private_key)

            try:
                await block_candidate.verify()
            except Exception as e:
                if accepted:
                    return {
                        'hash': hash1,
                        'nonce': nonce,
                        'height': job.index,
                        'id': block_candidate.signature
                    }
                self.app_log.warning("Verify error {} - hash {} header {} nonce {}".format(
                    e,
                    block_candidate.hash,
                    block_candidate.header,
                    block_candidate.nonce
                ))
                return False
            # accept winning block
            await self.accept_block(block_candidate)
            # Conversion to dict is important, or the object may change
            self.app_log.debug('block ok - special_min')

            return {
                'hash': block_candidate.hash,
                'nonce': nonce,
                'height': block_candidate.index,
                'id': block_candidate.signature
            }

        if accepted:
            return {
                'hash': block_candidate.hash,
                'nonce': nonce,
                'height': block_candidate.index,
                'id': block_candidate.signature
            }

    async def refresh(self):
        """Refresh computes a new bloc to mine. The block is stored in self.block_factory and contains
        the transactions at the time of the refresh. Since tx hash is in the header, a refresh here means we have to
        trigger the events for the pools, even if the block index did not change."""
        # TODO: to be taken care of, no refresh atm between blocks
        try:
            if self.refreshing:
                return
            self.refreshing = True
            await self.config.LatestBlock.block_checker()
            if self.block_factory:
                self.last_block_time = int(self.block_factory.time)
            self.block_factory = await self.create_block(
                await self.get_pending_transactions(),
                self.config.public_key,
                self.config.private_key,
                index=self.config.LatestBlock.block.index + 1
            )
            self.block_factory.header = self.block_factory.generate_header()
            self.refreshing = False
        except Exception as e:
            self.refreshing = False
            from traceback import format_exc
            self.app_log.error("Exception {} mp.refresh".format(format_exc()))
            raise

    async def create_block(self, transactions, public_key, private_key, index):
        return await Block.generate(
            transactions,
            public_key,
            private_key,
            index=index
        )

    async def block_to_mine_info(self):
        """Returns info for current block to mine"""
        if self.block_factory is None:
            #await self.refresh()
            return {}
        res = {
            'target': '{:064x}'.format(self.block_factory.target),  # target is now in hex format
            'special_target': '{:064x}'.format(self.block_factory.special_target),  # target is now in hex format
            # TODO this is the network target, maybe also send some pool target?
            'special_min': self.block_factory.special_min,
            'header': self.block_factory.header,
            'version': self.block_factory.version,
            'height': self.block_factory.index,  # This is the height of the one we are mining
            'previous_time': self.config.LatestBlock.block.time,  # needed for miner to recompute the real diff
        }
        return res

    async def block_template(self, agent):
        """Returns info for current block to mine"""
        if self.block_factory is None:
            await self.refresh()
        if not self.block_factory.target:
            await self.set_target_from_last_non_special_min(self.config.LatestBlock.block)

        job = await self.generate_job(agent)
        return job

    async def generate_job(self, agent):
        difficulty = int(self.max_target / self.block_factory.target)
        seed_hash = '4181a493b397a733b083639334bc32b407915b9a82b7917ac361816f0a1f5d4d' #sha256(yadacoin65000)
        job_id = str(uuid.uuid4())
        extra_nonce = hex(random.randrange(1,4294967295))[2:].rjust(8, '0')
        header = self.block_factory.header.replace('{nonce}', '{00}')

        if 'XMRigCC/3' in agent or 'XMRig/3' in agent:
            target = hex(0x10000000000000001 // self.config.pool_diff)[2:].rjust(16, '0')
        elif self.config.pool_diff <= 69905:
            target = hex(0x10000000000000001 // self.config.pool_diff - 0x0000F00000000000)[2:].zfill(48)
        else:
            target = '-' + hex(0x10000000000000001 // self.config.pool_diff - 0x0000F00000000000)[3:].zfill(48)

        res = {
            'job_id': job_id,
            'difficulty': difficulty,
            'target': target,  # can only be 16 characters long
            'blob': header.encode().hex(),
            'seed_hash': seed_hash,
            'height': self.config.LatestBlock.block.index + 1,  # This is the height of the one we are mining
            'extra_nonce': extra_nonce,
            'algo': 'rx/yada'
        }
        return await Job.from_dict(res)

    async def set_target_as_previous_non_special_min(self):
        """TODO: this is not correct, should use a cached version of the current target somewhere, and recalc on
        new block event if we cross a boundary (% 2016 currently). Beware, at boundary we need to recalc the new diff one block ahead
        that is, if we insert block before a boundary, we have to calc the diff for the next one right away."""
        self.app_log.error("set_target_as_previous_non_special_min should not be called anymore")
        res = await self.mongo.async_db.blocks.find_one(
            {
                'special_min': False,
            },
            {
                'target': 1
            },
            sort=[('index',-1)]
        )

        if res:
            self.block_factory.target = int(res['target'], 16)

    async def set_target_from_last_non_special_min(self, latest_block):
        if self.index >= CHAIN.FORK_10_MIN_BLOCK:
            self.block_factory.target = await CHAIN.get_target_10min(
                latest_block,
                self.block_factory
            )
        else:
            self.block_factory.target = await CHAIN.get_target(
                self.index,
                latest_block,
                self.block_factory
            )

    async def get_inputs(self, inputs):
        for x in inputs:
            yield x

    async def get_pending_transactions(self):
        mempool_smart_contract_objs = {}
        transaction_objs = {}
        used_sigs = []
        async for txn in self.mongo.async_db.miner_transactions.find({'relationship.smart_contract': {'$exists': True}}).sort([('fee', -1), ('time', 1)]):
            transaction_obj = await self.verify_pending_transaction(txn, used_sigs)
            if not isinstance(transaction_obj, Transaction):
                continue

            if (
                transaction_obj.relationship.identity.wif in mempool_smart_contract_objs and
                int(transaction_obj.time) > int(mempool_smart_contract_objs[transaction_obj.relationship.identity.wif].time)
            ):
                continue

            mempool_smart_contract_objs[transaction_obj.relationship.identity.wif] = transaction_obj

        async for txn in self.mongo.async_db.miner_transactions.find({'relationship.smart_contract': {'$exists': False}}).sort([('fee', -1), ('time', 1)]):
            transaction_obj = await self.verify_pending_transaction(txn, used_sigs)
            if not isinstance(transaction_obj, Transaction):
                continue

            transaction_objs.setdefault(transaction_obj.requested_rid, [])
            transaction_objs[transaction_obj.requested_rid].append(transaction_obj)

        # process recurring payments
        generated_txns = []
        async for x in await TU.get_current_smart_contract_txns(self.config, self.config.LatestBlock.block.index):
            try:
                smart_contract_txn = Transaction.from_dict(x['transactions'])
            except:
                continue
            try:
                async for trigger_txn_block in await TU.get_trigger_txns(smart_contract_txn):  # process blockchain txns
                    trigger_txn = Transaction.from_dict(trigger_txn_block.get('transactions'))
                    try:
                        payout_txn = await smart_contract_txn.relationship.process(smart_contract_txn, trigger_txn, TU.get_transaction_objs_list(transaction_objs) + generated_txns)
                        if payout_txn:
                            generated_txns.append(payout_txn)
                    except:
                        pass
            except:
                pass

        # process expired contracts
        used_public_keys = []
        async for x in await TU.get_expired_smart_contract_txns(self.config, self.config.LatestBlock.block.index):
            expired_blockchain_smart_contract_obj = Transaction.from_dict(x.get('transactions'))
            if expired_blockchain_smart_contract_obj.public_key in used_public_keys:
                continue
            payout_txn = await expired_blockchain_smart_contract_obj.relationship.expire(expired_blockchain_smart_contract_obj)
            if payout_txn:
                generated_txns.append(payout_txn)
                used_public_keys.append(expired_blockchain_smart_contract_obj.public_key)

        return list(mempool_smart_contract_objs.values()) + TU.get_transaction_objs_list(transaction_objs) + generated_txns

    async def verify_pending_transaction(self, txn, used_sigs):
        try:
            if isinstance(txn, Transaction):
                transaction_obj = txn
            elif isinstance(txn, dict):
                transaction_obj = Transaction.from_dict(txn)
            else:
                self.config.app_log.warning('transaction unrecognizable, skipping')
                return

            if self.config.LatestBlock.block.index + 1 >= CHAIN.TXN_V3_FORK and transaction_obj.version < 3:
                self.config.app_log.warning('transaction version too old, skipping')
                return

            transaction_obj.contract_generated = await transaction_obj.is_contract_generated()

            await transaction_obj.verify()

            if transaction_obj.transaction_signature in used_sigs:
                self.config.app_log.warning('duplicate transaction found and removed')
                return
            used_sigs.append(transaction_obj.transaction_signature)

            failed1 = False
            failed2 = False
            used_ids_in_this_txn = []

            async for x in self.get_inputs(transaction_obj.inputs):
                is_input_spent = await self.config.BU.is_input_spent(x.id, transaction_obj.public_key)
                if is_input_spent:
                    failed1 = True
                if x.id in used_ids_in_this_txn:
                    failed2 = True
                used_ids_in_this_txn.append(x.id)
            if failed1:
                self.config.app_log.warning('transaction removed: input spent already {}'.format(transaction_obj.transaction_signature))
                await self.mongo.async_db.miner_transactions.delete_many({'id': transaction_obj.transaction_signature})
                await self.mongo.async_db.failed_transactions.insert_one({'reason': 'input spent already', 'txn': transaction_obj.to_dict()})
            elif failed2:
                self.config.app_log.warning('transaction removed: using an input used by another transaction in this block {}'.format(transaction_obj.transaction_signature))
                await self.mongo.async_db.miner_transactions.delete_many({'id': transaction_obj.transaction_signature})
                await self.mongo.async_db.failed_transactions.insert_one({'reason': 'using an input used by another transaction in this block', 'txn': transaction_obj.to_dict()})
            else:
                return transaction_obj

        except Exception as e:
            await Transaction.handle_exception(e, transaction_obj)

    async def accept_block(self, block):
        self.app_log.info('Candidate submitted for index: {}'.format(block.index))
        self.app_log.info('Transactions:')
        for x in block.transactions:
            self.app_log.info(x.transaction_signature)

        await self.config.consensus.insert_consensus_block(block, self.config.peer)

        self.config.processing_queues.block_queue.add(BlockProcessingQueueItem(Blockchain(block.to_dict())))

        await self.config.nodeShared.send_block_to_peers(block)

        await self.config.websocketServer.send_block(block)

        await self.refresh()
