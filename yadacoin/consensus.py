import sys
from sys import exc_info
from os import path
import json
import logging
import requests
import datetime
from bitcoin.wallet import P2PKHBitcoinAddress
from time import time
from asyncio import sleep as async_sleep
from pymongo.errors import DuplicateKeyError
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.httputil import HTTPHeaders
from tornado import ioloop
from yadacoin.chain import CHAIN
from yadacoin.config import get_config
from yadacoin.peers import Peers, Peer
from yadacoin.blockchain import Blockchain
from yadacoin.block import Block, BlockFactory
from yadacoin.transaction import InvalidTransactionException, InvalidTransactionSignatureException, \
    MissingInputTransactionException, NotEnoughMoneyException
from urllib3.exceptions import *


class BadPeerException(Exception):
    pass


class AboveTargetException(Exception):
    pass


class ForkException(Exception):
    pass


class Consensus(object):

    lowest = CHAIN.MAX_TARGET

    def __init__(self, debug=False, peers=None, prevent_genesis=False):
        self.app_log = logging.getLogger("tornado.application")
        self.debug = debug
        self.config = get_config()
        self.mongo = self.config.mongo
        self.prevent_genesis = prevent_genesis
        if peers:
            self.peers = peers
        else:
            self.peers = Peers()
    
    async def async_init(self):
        latest_block = self.config.BU.get_latest_block()
        if latest_block:
            self.latest_block = await Block.from_dict(latest_block)
        else:
            if not self.prevent_genesis:
                await self.insert_genesis()

    def output(self, string):
        sys.stdout.write(string)  # write the next character
        sys.stdout.flush()                # flush stdout buffer (actual character display)
        sys.stdout.write(''.join(['\b' for i in range(len(string))])) # erase the last written char

    def log(self, message):
        # TODO: deprecate, use app_log
        print(message)

    async def insert_genesis(self):
        #insert genesis if it doesn't exist
        genesis_block = await BlockFactory.get_genesis_block()
        await genesis_block.save()
        self.mongo.db.consensus.update({
            'block': genesis_block.to_dict(),
            'peer': 'me',
            'id': genesis_block.signature,
            'index': 0
        },
        {
            'block': genesis_block.to_dict(),
            'peer': 'me',
            'id': genesis_block.signature,
            'index': 0
        },
        upsert=True)
        self.latest_block = genesis_block

    async def verify_existing_blockchain(self, reset=False):
        self.app_log.info('verifying existing blockchain')
        existing_blockchain = await Blockchain.init_async(self.config.mongo.async_db.blocks.find({}).sort([('index', 1)]))
        result = await existing_blockchain.verify()
        if result['verified']:
            print('Block height: %s | time: %s' % (self.latest_block.index, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            return True
        else:
            self.app_log.critical(result)
            if reset:
                if 'last_good_block' in result:
                    self.mongo.db.blocks.remove({"index": {"$gt": result['last_good_block'].index}}, multi=True)
                else:
                    self.mongo.db.blocks.remove({"index": {"$gt": 0}}, multi=True)
                self.app_log.debug("{} {}".format(result['message'], '...truncating'))
            else:
                self.app_log.critical("{} - reset False, not truncating - DID NOT VERIFY".format(result['message']))
            self.config.BU.latest_block = None
            latest_block = self.config.BU.get_latest_block()
            if latest_block:
                self.latest_block = await Block.from_dict(latest_block)
            else:
                if not self.prevent_genesis:
                    await self.insert_genesis()

    def remove_pending_transactions_now_in_chain(self, block):
        #remove transactions from miner_transactions collection in the blockchain
        self.mongo.db.miner_transactions.remove({'id': {'$in': [x['id'] for x in block['block']['transactions']]}}, {'_id': 0})

    def remove_fastgraph_transactions_now_in_chain(self, block):
        self.mongo.db.fastgraph_transactions.remove({'id': {'$in': [x['id'] for x in block['block']['transactions']]}}, {'_id': 0})

    def get_consensus_blocks_by_index(self, index):
        return self.mongo.db.consensus.find({'index': index, 'block.prevHash': {'$ne': ''}, 'block.version': CHAIN.get_version_for_height(index)}, {'_id': 0})

    def get_consensus_block_by_index(self, index):
        return self.get_consensus_blocks_by_index(index).limit(1)[0]

    async def get_next_consensus_block_from_local(self, block):
        #table cleanup
        new_block = await self.mongo.async_db.consensus.find_one({
            'block.prevHash': block.hash,
            'block.index': (block.index + 1),
            'block.version': CHAIN.get_version_for_height((block.index + 1))
        })
        if new_block:
            new_block = await Block.from_dict( new_block['block'])
            if int(new_block.version) == CHAIN.get_version_for_height(new_block.index):
                return new_block
            else:
                return None
        return None

    async def get_previous_consensus_block_from_local(self, block):
        #table cleanup
        new_blocks = self.mongo.async_db.consensus.find({
            'block.hash': block.prev_hash,
            'block.index': (block.index - 1),
            'block.version': CHAIN.get_version_for_height((block.index - 1))
        })
        async for new_block in new_blocks:
            new_block = await Block.from_dict(new_block['block'])

            # if peer has a fork in their own chain, we need to choose 
            # whatever path has a link to the blockchain
            new_new_block = await self.mongo.async_db.consensus.find_one({
                'block.hash': new_block.prev_hash,
                'block.index': (new_block.index - 1),
                'block.version': CHAIN.get_version_for_height((new_block.index - 1))
            })

            yield new_block

    async def get_previous_consensus_block_from_remote(self, block):
        # TODO: async conversion
        retry = 0
        peers = self.config.mongo.async_db.consensus.find({'block.prevHash': block.prev_hash, 'peer': {'$ne': 'me'}})
        async for peer in peers:
            try:
                url = 'http://' + peer['peer'] + '/get-block?hash=' + block.prev_hash
                self.app_log.warning('getting block {} {}'.format(url, block.prev_hash))
                res = requests.get(url, timeout=1, headers={'Connection':'close'})
            except:
                if retry == 1:
                    raise BadPeerException()
                else:
                    retry += 1
                    continue
            #self.app_log.warning('response code: {} {}'.format(res.status_code, res.content))
            new_block = await Block.from_dict(json.loads(res.content.decode('utf-8')))
            yield new_block

    async def insert_consensus_block(self, block, peer):
        if self.debug:
            self.app_log.info('inserting new consensus block for height and peer: %s %s' % (block.index, peer.to_string()))

        await self.mongo.async_db.consensus.replace_one({
            'id': block.to_dict().get('id'),
            'peer': peer.to_string()
        },
        {
            'block': block.to_dict(),
            'index': block.to_dict().get('index'),
            'id': block.to_dict().get('id'),
            'peer': peer.to_string()
        }, upsert=True)
    
    async def test_block(self, block):
        try:
            block.verify()
        except Exception as e:
            self.app_log.warning("Integrate block error 1: {}".format(e))
            return False

        async def get_txns(txns):
            for x in txns:
                yield x

        async def get_inputs(inputs):
            for x in inputs:
                yield x
        
        if block.index == 0:
            return True

        last_block = await Block.from_dict(await self.config.mongo.async_db.blocks.find_one({'index': block.index - 1}))

        if block.index >= CHAIN.FORK_10_MIN_BLOCK:
            target = await BlockFactory.get_target_10min(block.index, last_block, block)
        else:
            target = await BlockFactory.get_target(block.index, last_block, block)

        delta_t = int(time()) - int(last_block.time)
        special_target = CHAIN.special_target(block.index, block.target, delta_t, get_config().network)

        if block.index >= 35200 and delta_t < 600 and block.special_min:
            return False

        used_inputs = {}
        i = 0
        async for transaction in get_txns(block.transactions):
            self.app_log.warning('verifying txn: {} block: {}'.format(i, block.index))
            i += 1
            try:
                await transaction.verify()
            except InvalidTransactionException as e:
                self.app_log.warning(e)
                return False
            except InvalidTransactionSignatureException as e:
                self.app_log.warning(e)
                return False
            except MissingInputTransactionException as e:
                self.app_log.warning(e)
            except NotEnoughMoneyException as e:
                self.app_log.warning(e)
                return False
            except Exception as e:
                self.app_log.warning(e)
                return False

            if transaction.inputs:
                failed = False
                used_ids_in_this_txn = []
                async for x in get_inputs(transaction.inputs):
                    if self.config.BU.is_input_spent(x.id, transaction.public_key):
                        failed = True
                    if x.id in used_ids_in_this_txn:
                        failed = True
                    if (x.id, transaction.public_key) in used_inputs:
                        failed = True
                    used_inputs[(x.id, transaction.public_key)] = transaction
                    used_ids_in_this_txn.append(x.id)
                if failed and block.index >= CHAIN.CHECK_DOUBLE_SPEND_FROM:
                    return False
                elif failed and block.index < CHAIN.CHECK_DOUBLE_SPEND_FROM:
                    continue

        if block.index >= 35200 and delta_t < 600 and block.special_min:
            return False

        if int(block.index) > CHAIN.CHECK_TIME_FROM and int(block.time) < int(last_block.time):
            return False            

        if last_block.index != (block.index - 1) or last_block.hash != block.prev_hash:
            return False

        if int(block.index) > CHAIN.CHECK_TIME_FROM and (int(block.time) < (int(last_block.time) + 600)) and block.special_min:
            return False

        if block.index >= 35200 and delta_t < 600 and block.special_min:
            return False

        target_block_time = CHAIN.target_block_time(self.config.network)

        checks_passed = False
        if (int(block.hash, 16) < target):
            checks_passed = True
        elif (block.special_min and int(block.hash, 16) < special_target):
            checks_passed = True
        elif (block.special_min and block.index < 35200):
            checks_passed = True
        elif (block.index >= 35200 and block.index < 38600 and block.special_min and (int(block.time) - int(last_block.time)) > target_block_time):
            checks_passed = True
        else:
            self.app_log.warning("Integrate block error - index and time error")

        if not checks_passed:
            return False

        return True
    
    async def get_previous_consensus_block(self, block):
        async for local_block in self.get_previous_consensus_block_from_local(block):
            yield local_block
        async for remote_block in self.get_previous_consensus_block_from_remote(block):
            yield remote_block
    
    async def build_backward_from_block_to_fork(self, block, blocks):

        retrace_block = await self.mongo.async_db.blocks.find_one({'hash': block.prev_hash})
        if retrace_block:
            blocks = blocks.copy()
            return blocks

        async for retrace_consensus_block in self.get_previous_consensus_block(block):
            result = await self.build_backward_from_block_to_fork(retrace_consensus_block, blocks)
            if isinstance(result, list):
                result.append(retrace_consensus_block)
                return result
    
    async def integrate_blocks_with_existing_chain(self, blocks):
        for block in blocks:
            try:
                result = await self.integrate_block_with_existing_chain(block)
                if not result:
                    return False
            except:
                return False

    async def integrate_block_with_existing_chain(self, block: Block, extra_blocks=None):
        """Even in case of retrace, this is the only place where we insert a new block into the block collection and update BU"""
        self.app_log.warning('integrate_block_with_existing_chain')
        try:
            # TODO: reorg the checks, to have the faster ones first.
            # Like, here we begin with checking every tx one by one, when <e did not even check index and provided hash matched previous one.
            result = await self.test_block(block)
            if not result:
                return False

            # self.mongo.db.blocks.update({'index': block.index}, block.to_dict(), upsert=True)
            # self.mongo.db.blocks.remove({'index': {"$gt": block.index}}, multi=True)
            # todo: is this useful? can we have more blocks above? No because if we had, we would have raised just above
            await self.mongo.async_db.blocks.delete_many({'index': {"$gte": block.index}})
            db_block = block.to_dict()
            db_block['updated_at'] = time()
            await self.mongo.async_db.blocks.replace_one({'index': block.index}, db_block, upsert=True)
            await self.mongo.async_db.miner_transactions.delete_many({'id': {'$in': [x.transaction_signature for x in block.transactions]}})
            self.latest_block = await Block.from_dict(await self.config.BU.get_latest_block_async(False))
            self.app_log.info("New block inserted for height: {}".format(block.index))
            latest_consensus = await self.mongo.async_db.consensus.find_one({
                'index': self.latest_block.index + 1,
                'block.version': CHAIN.get_version_for_height(self.latest_block.index + 1),
                'ignore': {'$ne': True}
            })
            if not latest_consensus:
                await self.config.on_new_block(block)  # This will trigger mining pool to generate a new block to mine
            return True
        except Exception as e:
            if self.config.debug:
                from traceback import format_exc
                self.app_log.warning("{}".format(format_exc()))
            raise

    async def sync_bottom_up(self):
            #bottom up syncing
            last_latest = self.latest_block
            self.latest_block = await Block.from_dict(await self.config.BU.get_latest_block_async())
            if self.latest_block.index > last_latest.index:
                self.app_log.info('Block height: %s | time: %s' % (self.latest_block.index, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            latest_consensus = await self.mongo.async_db.consensus.find_one({
                'index': self.latest_block.index + 1,
                'block.version': CHAIN.get_version_for_height(self.latest_block.index + 1),
                'ignore': {'$ne': True}
            })
            if latest_consensus:
                self.remove_pending_transactions_now_in_chain(latest_consensus)
                self.remove_fastgraph_transactions_now_in_chain(latest_consensus)
                latest_consensus = await Block.from_dict( latest_consensus['block'])
                if self.debug:
                    self.app_log.info("Latest consensus_block {}".format(latest_consensus.index))

                records = await self.mongo.async_db.consensus.find({
                    'index': self.latest_block.index + 1,
                    'block.version': CHAIN.get_version_for_height(self.latest_block.index + 1),
                    'ignore': {'$ne': True}
                }).to_list(length=100)
                for record in sorted(records, key=lambda x: int(x['block']['target'], 16)):
                    try:
                        block = await Block.from_dict(record['block'])
                    except:
                        continue

                    if await self.integrate_block_with_existing_chain(block):
                        return True

                    blocks = await self.build_backward_from_block_to_fork(block, [])
                    if not blocks:
                        return False
                    existing_blockchain = await Blockchain.init_async(self.config.mongo.async_db.blocks.find({'index': {'$gte': blocks[0].index}}), partial=True)
                    existing_difficulty = await existing_blockchain.get_difficulty()
                    inbound_blockchain = await Blockchain.init_async(blocks, partial=True)
                    inbound_difficulty = await inbound_blockchain.get_difficulty()
                    latest_block = await Block.from_dict(await self.config.BU.get_latest_block_async())
                    if (
                        blocks[-1].index >= latest_block.index and
                        inbound_difficulty > existing_difficulty
                    ):
                        await self.integrate_blocks_with_existing_chain(blocks)
            else:
                return await self.search_network_for_new()
    
    async def request_blocks(self, peer_string):
        self.app_log.debug('requesting {} from {}'.format(self.latest_block.index + 1, peer_string))
        peer = Peer.from_string(peer_string)
        try:
            url = 'http://{peer}/get-blocks?start_index={start_index}&end_index={end_index}'\
                .format(peer=peer_string,
                        start_index=int(self.latest_block.index) +1,
                        end_index=int(self.latest_block.index) + 100)
            h = HTTPHeaders({"Connection": "close"})
            request = HTTPRequest(url, headers=h, connect_timeout=3,request_timeout=5)
            response = await self.config.http_client.fetch(request)
            if response.code != 200:
                return
            # result = requests.get(url, timeout=2)
        except HTTPError as e:
            self.app_log.warning('Error requesting from {} ...'.format(peer_string))
            # add to failed peers
            await self.peers.increment_failed(peer)
            return
        except ConnectTimeoutError as e:
            self.app_log.warning('Timeout requesting from {} ...'.format(peer_string))
            # add to failed peers
            await self.peers.increment_failed(peer)
            return
        except Exception as e:
            self.app_log.error('error {} requesting from {} ...'.format(e, peer_string))
            await self.peers.increment_failed(peer)
            return
        try:
            blocks = json.loads(response.body.decode('utf-8'))
            if not isinstance(blocks, list):
                raise ValueError("wrong get-blocks response, probably not whitelisted")
            # blocks = json.loads(result.content)
        except ValueError:
            return
        for i, block in enumerate(blocks):
            blocks[i] = await Block.from_dict(block)
            try:
                blocks[i].verify()
            except:
                return
        for block in blocks:
            await self.insert_consensus_block(block, peer)
        return True

    async def search_network_for_new(self):
        # Peers.init( self.config.network)
        if self.config.network == 'regnet':
            return
        if self.peers.syncing:
            self.app_log.debug("Already syncing, ignoring search_network_for_new")

        if len(self.config.force_polling):
            # This is a temp hack until everyone updated
            polling_peers = ["{}:{}".format(peer['host'], peer['port']) for peer in self.config.force_polling]
        else:
            if len(self.peers.peers) < 2:
                await self.peers.refresh()
            if len(self.peers.peers) < 1:
                self.app_log.info("No peer to connect to yet")
                return
            polling_peers = [peer.to_string() for peer in self.peers.peers]
        # TODO: use an aio lock
        self.app_log.debug('requesting {} ...'.format(self.latest_block.index + 1))


        # for peer in self.peers.peers:
        for peer_string in polling_peers:
            if '0.0.0.0' in peer_string: continue
            self.peers.syncing = True
            try:
                await self.request_blocks(peer_string)
            except Exception as e:
                if self.debug:
                    self.app_log.warning(e)
            finally:
                self.peers.syncing = False

    async def trigger_update_event(self, block: dict=None):
        """Update BU latest block info if unknown, then trigger the event to all connected peers"""
        if block is None:
            block = await self.config.BU.get_latest_block_async()
        await self.peers.on_block_insert(block)  # This will propagate to everyone

    async def process_next_block(self, block_data: dict, peer, trigger_event=True) -> bool:
        """This is the common entry point for all new possible blocks to enter consensus and chain"""
        block_object = await Block.from_dict(block_data)
        if block_object.in_the_future():
            # Most important
            self.app_log.warning('Block in the future for height %s  from peer: %s' % (block_object.index, peer.to_string()))
            return False
        # TODO: there is no check before inserting into consensus (previous hash, nor diff, nor valid tx)
        await self.insert_consensus_block(block_object, peer)
        self.app_log.debug("Consensus ok {}".format(block_object.index))
        return True
