from time import time
import requests
from bitcoin.wallet import P2PKHBitcoinAddress
from logging import getLogger
from threading import Thread

from yadacoin.chain import CHAIN
from yadacoin.config import get_config
from yadacoin.block import Block, BlockFactory
from yadacoin.blockchain import Blockchain
from yadacoin.transaction import Transaction, MissingInputTransactionException, InvalidTransactionException, \
    InvalidTransactionSignatureException
from yadacoin.fastgraph import FastGraph, MissingFastGraphInputTransactionException


class MiningPool(object):
    def __init__(self):
        self.config = get_config()
        self.mongo = self.config.mongo
        self.block_factory = None
        self.app_log = getLogger("tornado.application")
        self.target_block_time = CHAIN.target_block_time(self.config.network)
        self.max_target = CHAIN.MAX_TARGET
        self.inbound = {}
        self.connected_ips = {}
        self.last_block_time = int(self.config.BU.get_latest_block()['time'])
        self.previous_block_to_mine = None  # todo
        self.last_refresh = 0

    async def block_to_mine(self):
        """Returns the block to mine"""
        if self.block_factory is None:
            await self.refresh()
        return self.block_factory.block

    async def check_block_evolved(self):
        """
        Checks if special min triggered, or if new transactions were received, for the current block.
        If so, refresh the block and triggers miners update
        """
        if await self.special_min_triggered():
            self.app_log.info("Special_min triggered")
            await self.refresh_and_signal_miners()
            # This will also refresh transactions, so we can early exit
            return
        # second case would be new transactions received in the mean time
        # TODO - event on tx
        # or enough time passed by
        if int(self.last_refresh + 60) < int(time()):
            self.app_log.info("Refresh 60")
            # Note that a refresh changes the block time, therefore it's header.
            await self.refresh_and_signal_miners()
        pass

    async def special_min_triggered(self):
        """Tells if we went past the special min trigger since our last call"""
        try:
            block_to_mine = await self.block_to_mine()
            if block_to_mine.special_min:
                # We already are special_min
                return False
            if (self.last_block_time + CHAIN.special_min_trigger(self.config.network, block_to_mine.index)) < time():
                return True
            return False
        except Exception as e:
            print(e)
            import sys, os
            self.app_log.error("Exception {} special_min_triggered".format(e))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)

    async def refresh_and_signal_miners(self):
        try:
            await self.refresh()
        except Exception as e:
            print("refresh_and_signal_miners: {}".format(e))
        # Update the miners (websockets)
        try:
            await self.config.SIO.emit('header', data=await self.block_to_mine_info(), namespace='/pool')
        except Exception as e:
            print("refresh_and_signal_miners2: {}".format(e))

    def get_status(self):
        """Returns pool status as explicit dict"""
        status = {"miners": len(self.inbound), "ips": len(self.connected_ips)}
        return status

    @property
    def free_inbound_slots(self):
        """How many free inbound slots we have"""
        return self.config.max_miners - len(self.inbound)

    def allow_ip(self, IP):
        """Returns True if that ip can connect"""
        return True  # IP not in self.connected_ips  # Allows if we're not connected already.

    def on_new_ip(self, ip):
        """We got an inbound.
        avoid initiating one connection twice if the handshake does not go fast enough."""
        self.app_log.info("miner on_new_ip:{}".format(ip))
        if ip not in self.connected_ips:
            self.connected_ips[ip] = 1
        else:
            self.connected_ips[ip] += 1

    async def on_new_inbound(self, ip:str, version, worker, address, type, sid):
        """Inbound peer provided a correct version and ip, add it to our pool"""
        self.app_log.info("miner on_new_inbound {}:{} {}".format(ip, address, worker))
        self.inbound[sid] = {"ip":ip, "version": version, "worker": worker, "address": address, "type": type}

    async def on_miner_status(self, sid, hash_rate_mhs:int, uptime:int):
        """A miner sent extra status (optional)"""
        self.inbound[sid]['mhs'] = hash_rate_mhs
        self.inbound[sid]['uptime'] = uptime
        # TODO: could be stored or averaged for pool dashboard

    async def on_miner_nonce(self, nonce: str, sid=0, address: str='') -> bool:
        """We got a nonce from a miner.
        we have to provied either a sid (websocket context, either an address (http context)"""
        # Does it match current block?
        # we can't avoid but compute the hash, since we can't trust the hash the miner could send to be honest.
        if address == '':
            try:
                address = self.inbound[sid]['address']
            except Exception as e:
                self.app_log.warning("error {} getting address sid {}".format(e, sid))
        block_to_mine = await self.block_to_mine()
        block_to_mine = block_to_mine.copy()
        previous_block_to_mine = self.previous_block_to_mine.copy() if self.previous_block_to_mine else None
        hash1 = BlockFactory.generate_hash_from_header(block_to_mine.header, nonce)
        if int(hash1, 16) > block_to_mine.target and self.config.network != 'regnet' and (block_to_mine.special_min and int(hash1, 16) > block_to_mine.special_target):
            # TODO If not, does it match previous block of same height?
            self.app_log.warning("nonce {} did not match pool diff block, hash1 was {}".format(nonce, hash1))
            if self.previous_block_to_mine is not None:
                hash2 = BlockFactory.generate_hash_from_header(previous_block_to_mine.header, nonce)
                if not hash2[:8] == '00000000':
                    self.app_log.warning("nonce {} did not match pool diff block, hash2 was {}".format(nonce, hash2))
                    return False
                # a shallow copy is required, or the block_to_mine can have changed until we verify it.
                matching_block = previous_block_to_mine
                matching_hash = hash2
                matching_block.hash = hash2
                matching_block.nonce = nonce
                self.app_log.warning("nonce {} matches pool diff, hash2 is {} header {}".format(nonce, hash2, matching_block.header))
            else:
                return False
        else:
            matching_block = block_to_mine
            matching_hash = hash1
            matching_block.hash = hash1
            matching_block.nonce = nonce
            # target = BlockFactory.get_target(height, last_block, block, self.existing_blockchain)
            self.app_log.warning("nonce {} matches pool diff, hash1 is {} header {}".format(nonce, hash1, matching_block.header))
        # TODO: store share and send block if enough
        # No need to re-verify block, should be good since we forged it and nonce passes
        # TODO: Gain time by only signing (and no need to verify after debug) if block passes net diff.
        matching_block.signature = self.config.BU.generate_signature(matching_block.hash, self.config.private_key)
        try:
            matching_block.verify()
        except Exception as e:
            self.app_log.warning("Verify error {} - hash {} header {} nonce {}".format(e, matching_block.hash, matching_block.header, matching_block.nonce))
            # print(matching_block.hash)
            
        if matching_block.special_min:
            delta_t = int(matching_block.time) - int(self.last_block_time)
            special_target = CHAIN.special_target(matching_block.index, matching_block.target,
                                                  delta_t, self.config.network)
            matching_block.special_target = special_target

        if matching_block.index >= 35200 and (int(matching_block.time) - int(self.last_block_time)) < 600 and matching_block.special_min:
            self.app_log.warning("Special min block too soon: hash {} header {} nonce {}".format(matching_block.hash, matching_block.header, matching_block.nonce))
            return False

        # print("matching", matching_block.to_dict())  # temp
        if int(matching_block.target) > int(matching_block.hash, 16):
            # broadcast winning block
            await self.broadcast_block(matching_block.to_dict())
            # Conversion to dict is important, or the object may change
            self.app_log.debug('block ok')
            self.app_log.error('^^ ^^ ^^')
        elif matching_block.special_min and (int(matching_block.special_target) > int(matching_block.hash, 16)):
            # broadcast winning block
            await self.broadcast_block(matching_block.to_dict())
            # Conversion to dict is important, or the object may change
            self.app_log.debug('block ok - special_min')
            self.app_log.error('^^ ^^ ^^')
        else:
            self.app_log.debug('share ok')
        # submit share only now, not to slow down if we had a block
        await self.mongo.async_db.shares.insert_one({
            'address': address,
            'index': matching_block.index,
            'hash': matching_hash
        })
        return True

    async def on_close_inbound(self, sid):
        # We only allow one in or out per ip
        try:
            self.app_log.info("miner on_close_inbound {}".format(sid))
            info = self.inbound.pop(sid, None)
            ip = info['ip']
            self.connected_ips[ip] -= 1
            if self.connected_ips[ip] <= 0:
                self.connected_ips.pop(ip)
        except Exception as e:
            print(e)
            pass

    async def refresh(self, block=None):
        """Refresh computes a new bloc to mine. The block is stored in self.block_factory.block and contains
        the transactions at the time of the refresh. Since tx hash is in the header, a refresh here means we have to
        trigger the events for the pools, even if the block index did not change."""
        # TODO: to be taken care of, no refresh atm between blocks
        try:
            if self.block_factory:
                current_index = self.block_factory.block.index
                backup_block = self.block_factory.block.to_dict()
                # print("backup_block header", backup_block['header'])
            else:
                current_index = 0
                backup_block = None
            self.last_refresh = int(time())
            if block is None:
                block = self.config.BU.get_latest_block()
            if block:
                block = Block.from_dict(block)
            else:
                genesis_block = BlockFactory.get_genesis_block()
                genesis_block.save()
                self.mongo.db.consensus.insert({
                    'block': genesis_block.to_dict(),
                    'peer': 'me',
                    'id': genesis_block.signature,
                    'index': 0
                    })
                block = Block.from_dict(self.config.BU().get_latest_block())
            self.index = block.index + 1
            self.last_block_time = int(block.time)
        except Exception as e:
            import sys, os
            self.app_log.error("Exception {} mp.refresh0".format(e))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            raise
        try:
            self.app_log.debug('Refreshing mp block Factory {}'.format(time()))
            if current_index != self.index:
                self.block_factory = await self.create_block(
                    await self.get_pending_transactions(),
                    self.config.public_key,
                    self.config.private_key,
                    index=self.index
                )
            self.app_log.debug('End refreshing mp block Factory {}'.format(time()))
            # TODO: centralize handling of min target
            self.set_target(int(time()))
            if not self.block_factory.block.special_min:
                self.set_target_from_last_non_special_min(block)
            self.block_factory.block.header = BlockFactory.generate_header(self.block_factory.block)
            # print('block header', self.block_factory.block.header)
            if self.block_factory.block.index == current_index:
                # If we just refreshed the same block, keep the previous one so we can validate the nonces.
                if backup_block:
                    self.previous_block_to_mine = Block.from_dict(backup_block)
                else:
                    self.previous_block_to_mine = None
                # print("previous_block header", self.previous_block_to_mine.header)
            else:
                self.previous_block_to_mine = None
        except Exception as e:
            import sys, os
            self.app_log.error("Exception {} mp.refresh".format(e))
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            raise

    async def create_block(self, transactions, public_key, private_key, index):
        return await BlockFactory.generate(
            self.config,
            transactions,
            public_key,
            private_key,
            index=index
        )


    async def block_to_mine_info(self):
        """Returns info for current block to mine"""
        if self.block_factory is None:
            await self.refresh()
        res = {
            'target': hex(int(self.block_factory.block.target))[2:].rjust(64, '0'),  # target is now in hex format
            'special_target': hex(int(self.block_factory.block.special_target))[2:].rjust(64, '0'),  # target is now in hex format
            # TODO this is the network target, maybe also send some pool target?
            'special_min': self.block_factory.block.special_min,
            'header': self.block_factory.block.header,
            'version': self.block_factory.block.version,
            'height': self.block_factory.block.index,  # This is the height of the one we are mining
            'previous_time': self.config.BU.get_latest_block()['time'],  # needed for miner to recompute the real diff
        }
        return res

    def set_target(self, to_time):
        self.app_log.debug("set_target {}".format(to_time))
        # todo: keep block target at normal target, for header and block info.
        # Only tweak target at validation time, and don't include special_min into header
        if self.block_factory.block.index >= 38600:  # TODO: use a CHAIN constant
            # print("test target", int(to_time), self.last_block_time)
            if self.block_factory.block.target == 0:
                # If the node is started when the current block is special_min, then we have a 0 target
                self.set_target_as_previous_non_special_min()
                # print('target set to', self.block_factory.block.target)
            delta_t = int(to_time) - self.last_block_time
            if delta_t \
                    > CHAIN.special_min_trigger(self.config.network, self.block_factory.block.index):
                special_target = CHAIN.special_target(self.block_factory.block.index, self.block_factory.block.target, delta_t, self.config.network)
                self.block_factory.block.special_min = True
                self.block_factory.block.special_target = special_target
                self.block_factory.block.time = int(to_time)
            else:
                self.block_factory.block.special_min = False
        elif self.block_factory.block.index < 38600:  # TODO: use a CHAIN constant
            if (int(to_time) - self.last_block_time) > self.target_block_time:
                self.block_factory.block.target = self.max_target
                self.block_factory.block.special_min = True
                self.block_factory.block.time = int(to_time)
            else:
                self.block_factory.block.special_min = False

    def set_target_as_previous_non_special_min(self):
        # TODO: move to async and above
        """TODO: this is not correct, should use a cached version of the current target somewhere, and recalc on
        new block event if we cross a boundary (% 2016 currently). Beware, at boundary we need to recalc the new diff one block ahead
        that is, if we insert block before a boundary, we have to calc the diff for the next one right away."""
        self.app_log.error("set_target_as_previous_non_special_min should not be called anymore")
        res = self.mongo.db.blocks.find_one({
            'special_min': False,
        }, {'target': 1}, sort=[('index',-1)])
        # print(res)
        if res:
            self.block_factory.block.target = int(res['target'], 16)

    def set_target_from_last_non_special_min(self, latest_block):
        i = 1
        while 1:
            res = self.mongo.db.blocks.find_one({
                'index': self.index - i,
                'special_min': False,
                'target': {'$ne': CHAIN.MAX_TARGET_HEX}  # This condition may be extraneous
            })
            if res:
                chain = [x for x in self.mongo.db.blocks.find({
                    'index': {'$gte': res['index']}
                })]
                break
            else:
                i += 1
        self.block_factory.block.target = BlockFactory.get_target(
            self.index,
            latest_block,
            self.block_factory.block,
            Blockchain(
                blocks=chain,
                partial=True
            )
        )

    def combine_transaction_lists(self):
        transactions = self.mongo.db.fastgraph_transactions.find({'$or': [{'ignore': False}, {'ignore': {'$exists': False}}]})
        for transaction in transactions:
            if 'txn' in transaction:
                yield transaction['txn']

        transactions = self.mongo.db.miner_transactions.find()
        for transaction in transactions:
            yield transaction

    async def get_pending_transactions(self):
        transaction_objs = []
        unspent_indexed = {}
        used_sigs = []
        for txn in sorted(self.combine_transaction_lists(), key=lambda i: int(i['fee']), reverse=True)[:1000]:
            try:
                if isinstance(txn, FastGraph) and hasattr(txn, 'signatures'):
                    transaction_obj = txn
                elif isinstance(txn, Transaction):
                    transaction_obj = txn
                elif isinstance(txn, dict) and 'signatures' in txn:
                    transaction_obj = FastGraph.from_dict(self.config.BU.get_latest_block()['index'], txn)
                elif isinstance(txn, dict):
                    transaction_obj = Transaction.from_dict(self.config.BU.get_latest_block()['index'], txn)
                else:
                    print('transaction unrecognizable, skipping')
                    continue
                
                transaction_obj.verify()
                
                if transaction_obj.transaction_signature in used_sigs:
                    print('duplicate transaction found and removed')
                    continue
                used_sigs.append(transaction_obj.transaction_signature)

                if not isinstance(transaction_obj, FastGraph) and transaction_obj.rid:
                    for input_id in transaction_obj.inputs:
                        input_block = self.config.BU.get_transaction_by_id(input_id.id, give_block=True)
                        if input_block and input_block['index'] > (self.config.BU.get_latest_block()['index'] - 2016):
                            continue

                #check double spend
                address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(transaction_obj.public_key)))
                if address in unspent_indexed:
                    unspent_ids = unspent_indexed[address]
                else:
                    needed_value = sum([float(x.value) for x in transaction_obj.outputs]) + float(transaction_obj.fee)
                    res = self.config.BU.get_wallet_unspent_transactions(address, needed_value=needed_value)
                    unspent_ids = [x['id'] for x in res]
                    unspent_indexed[address] = unspent_ids

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
                    print('transaction removed: input presumably spent already, not in unspent outputs', transaction_obj.transaction_signature)
                    self.mongo.db.failed_transactions.insert({'reason': 'input presumably spent already', 'txn': transaction_obj.to_dict()})
                elif failed2:
                    self.mongo.db.miner_transactions.remove({'id': transaction_obj.transaction_signature})
                    print('transaction removed: using an input used by another transaction in this block', transaction_obj.transaction_signature)
                    self.mongo.db.failed_transactions.insert({'reason': 'using an input used by another transaction in this block', 'txn': transaction_obj.to_dict()})
                else:
                    transaction_objs.append(transaction_obj)
            except MissingInputTransactionException as e:
                #print 'missing this input transaction, will try again later'
                pass
            except InvalidTransactionSignatureException as e:
                print('InvalidTransactionSignatureException: transaction removed')
                self.mongo.db.miner_transactions.remove({'id': transaction_obj.transaction_signature})
                self.mongo.db.failed_transactions.insert({'reason': 'InvalidTransactionSignatureException', 'txn': transaction_obj.to_dict()})
            except InvalidTransactionException as e:
                print('InvalidTransactionException: transaction removed')
                self.mongo.db.miner_transactions.remove({'id': transaction_obj.transaction_signature})
                self.mongo.db.failed_transactions.insert({'reason': 'InvalidTransactionException', 'txn': transaction_obj.to_dict()})
            except Exception as e:
                print(e)
                #print 'rejected transaction', txn['id']
                pass
        return transaction_objs

    @classmethod
    def pool_mine(cls, pool_peer, address, header, target, nonces, special_min, special_target):
        nonce, lhash = BlockFactory.mine(header, target, nonces, special_min, special_target)
        if nonce and lhash:
            try:
                requests.post("{pool}/pool-submit".format(pool=pool_peer), json={
                    'nonce': '{:02x}'.format(nonce),
                    'hash': lhash,
                    'address': address
                }, headers={'Connection':'close'})
            except Exception as e:
                print(e)

    def send_it(self, block_dict: dict, peer: str):
        """Quick hack for // send. TODO: To be converted to real async"""
        try:
            requests.post('http://{peer}/newblock'.format(peer=peer), json=block_dict, timeout=10, headers={'Connection':'close'})
            self.app_log.info("Sent to peer {}".format(peer))
        except Exception as e:
            self.app_log.info("Error {} sending to peer {}".format(e, peer))
            # TODO
            # peer.report()

    async def broadcast_block(self, block_data: dict):
        # Peers.init(self.config.network)
        # Peer.save_my_peer(self.config.network)
        self.app_log.info('Candidate submitted for index: {}'.format(block_data['index']))
        self.app_log.info('Transactions:')
        for x in block_data['transactions']:
            self.app_log.info(x['id'])
        if block_data.get('peer', '') == '':
            block_data['peer'] = self.config.peers.my_peer
        self.app_log.info('Send block to:')
        # TODO: convert to async // send
        # Do we need to send to other nodes than the ones we're connected to via websocket? Event will flow.
        # Then maybe a list of "root" nodes (explorer, known pools) from config, just to make sure.
        if self.config.network != 'regnet':
            for peer in self.config.force_broadcast_to:
                try:
                    # peer = self.config.peers.my_peer
                    t = Thread(target=self.send_it, args=(block_data, "{}:{}".format(peer['host'],peer['port'])))
                    t.setDaemon(True)
                    t.start()
                except Exception as e:
                    print("Error ", e)
        # TODO: why do we only insert to consensus? Why not try to insert right away?
        # TODO: this is needed until bottom-up syncing is deprecated
        self.mongo.db.consensus.insert_one({'peer': 'me', 'index': block_data['index'],
                                            'id': block_data['id'], 'block': block_data})
        await self.config.consensus.import_block({'peer': self.config.peers.my_peer, 'block': block_data})

