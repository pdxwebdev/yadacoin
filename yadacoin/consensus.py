import sys
from sys import exc_info
from os import path
import json
import logging
import requests
import datetime
from time import time
from asyncio import sleep as async_sleep
from pymongo.errors import DuplicateKeyError
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
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
        latest_block = self.config.BU.get_latest_block()
        if latest_block:
            self.latest_block = Block.from_dict(latest_block)
        else:
            if not self.prevent_genesis:
                self.insert_genesis()

        self.existing_blockchain = Blockchain(self.config.BU.get_blocks())
        # print("len", len(self.existing_blockchain.blocks))

    def output(self, string):
        sys.stdout.write(string)  # write the next character
        sys.stdout.flush()                # flush stdout buffer (actual character display)
        sys.stdout.write(''.join(['\b' for i in range(len(string))])) # erase the last written char

    def log(self, message):
        # TODO: deprecate, use app_log
        print(message)

    def insert_genesis(self):
        #insert genesis if it doesn't exist
        genesis_block = BlockFactory.get_genesis_block()
        genesis_block.save()
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

    def verify_existing_blockchain(self, reset=False):
        self.app_log.info('verifying existing blockchain')
        result = self.existing_blockchain.verify(self.output)
        if result['verified']:
            print('Block height: %s | time: %s' % (self.latest_block.index, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            return True
        else:
            self.app_log.debug(result)
            if 'last_good_block' in result:
                self.mongo.db.blocks.remove({"index": {"$gt": result['last_good_block'].index}}, multi=True)
            else:
                self.mongo.db.blocks.remove({"index": {"$gt": 0}}, multi=True)
            self.app_log.debug("{} {}".format(result['message'], '...truncating'))
            self.config.BU.latest_block = None
            latest_block = self.config.BU.get_latest_block()
            if latest_block:
                self.latest_block = Block.from_dict(latest_block)
            else:
                if not self.prevent_genesis:
                    self.insert_genesis()
            self.existing_blockchain = Blockchain(self.config.BU.get_blocks())

    def remove_pending_transactions_now_in_chain(self):
        #remove transactions from miner_transactions collection in the blockchain
        data = self.mongo.db.miner_transactions.find({}, {'_id': 0})
        for txn in data:
            res = self.mongo.db.blocks.find({"transactions.id": txn['id']})
            if res.count():
                self.mongo.db.miner_transactions.remove({'id': txn['id']})

    def remove_fastgraph_transactions_now_in_chain(self):
        data = self.mongo.db.fastgraph_transactions.find({}, {'_id': 0})
        for txn in data:
            res = self.mongo.db.blocks.find({"transactions.id": txn['id']})
            if res.count():
                self.mongo.db.fastgraph_transactions.remove({'id': txn['id']})

    def get_latest_consensus_blocks(self):
        for x in self.mongo.db.consensus.find({}, {'_id': 0}).sort([('index', -1)]):
            if CHAIN.get_version_for_height(x['block']['index']) == int(x['block']['version']):
                yield x

    def get_latest_consensus_block(self):
        latests = self.get_latest_consensus_blocks()
        for latest in latests:
            if int(latest['block']['version']) == CHAIN.get_version_for_height(latest['block']['index']):
                return Block.from_dict( latest['block'])

    def get_consensus_blocks_by_index(self, index):
        return self.mongo.db.consensus.find({'index': index, 'block.prevHash': {'$ne': ''}, 'block.version': CHAIN.get_version_for_height(index)}, {'_id': 0})

    def get_consensus_block_by_index(self, index):
        return self.get_consensus_blocks_by_index(index).limit(1)[0]

    def rank_consensus_blocks(self):
        # rank is based on target, total chain difficulty, and chain validity
        records = self.get_consensus_blocks_by_index(self.latest_block.index + 1)
        lowest = self.lowest

        ranks = []
        for record in records:
            peer = Peer.from_string( record['peer'])
            block = Block.from_dict( record['block'])
            target = int(record['block']['hash'], 16)
            if target < lowest:
                ranks.append({
                    'target': target,
                    'block': block,
                    'peer': peer
                })
        return sorted(ranks, key=lambda x: x['target'])

    async def get_next_consensus_block_from_local(self, block):
        #table cleanup
        new_block = await self.mongo.async_db.consensus.find_one({
            'block.prevHash': block.hash,
            'block.index': (block.index + 1),
            'block.version': CHAIN.get_version_for_height((block.index + 1))
        })
        if new_block:
            new_block = Block.from_dict( new_block['block'])
            if int(new_block.version) == CHAIN.get_version_for_height(new_block.index):
                return new_block
            else:
                return None
        return None

    async def get_previous_consensus_block_from_local(self, block, peer):
        #table cleanup
        new_block = await self.mongo.async_db.consensus.find_one({
            'block.hash': block.prev_hash,
            'block.index': (block.index - 1),
            'block.version': CHAIN.get_version_for_height((block.index - 1)),
            'ignore': {'$ne': True}
        })
        if new_block:
            new_block = Block.from_dict(new_block['block'])
            if int(new_block.version) == CHAIN.get_version_for_height(new_block.index):
                return new_block
            else:
                return None
        return None

    def get_previous_consensus_block_from_remote(self, block, peer):
        # TODO: async conversion
        retry = 0
        while True:
            try:
                url = 'http://' + peer.to_string() + '/get-block?hash=' + block.prev_hash
                if self.debug:
                    print('getting block', url)
                res = requests.get(url, timeout=1, headers={'Connection':'close'})
            except:
                if retry == 1:
                    raise BadPeerException()
                else:
                    retry += 1
                    continue
            try:
                if self.debug:
                    print('response code: ', res.status_code)
                new_block = Block.from_dict(json.loads(res.content.decode('utf-8')))
                if int(new_block.version) == CHAIN.get_version_for_height(new_block.index):
                    return new_block
                else:
                    return None
            except:
                return None

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

    async def sync_bottom_up(self):
        try:
            #bottom up syncing
            last_latest = self.latest_block
            self.latest_block = Block.from_dict(await self.config.BU.get_latest_block_async())
            if self.latest_block.index > last_latest.index:
                self.app_log.info('Block height: %s | time: %s' % (self.latest_block.index, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.remove_pending_transactions_now_in_chain()
            self.remove_fastgraph_transactions_now_in_chain()

            latest_consensus = await self.mongo.async_db.consensus.find_one({
                'index': self.latest_block.index + 1,
                'block.version': CHAIN.get_version_for_height(self.latest_block.index + 1),
                'ignore': {'$ne': True}
            })
            if latest_consensus:
                latest_consensus = Block.from_dict( latest_consensus['block'])
                if self.debug:
                    self.app_log.info("Latest consensus_block {}".format(latest_consensus.index))

                records = await self.mongo.async_db.consensus.find({
                    'index': self.latest_block.index + 1,
                    'block.version': CHAIN.get_version_for_height(self.latest_block.index + 1),
                    'ignore': {'$ne': True}
                }).to_list(length=100)
                for record in sorted(records, key=lambda x: int(x['block']['target'], 16)):
                    await self.import_block(record)

                last_latest = self.latest_block
                self.latest_block = Block.from_dict(await self.config.BU.get_latest_block_async())
                if self.latest_block.index > last_latest.index:
                    self.app_log.info('Block height: %s | time: %s' % (self.latest_block.index, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                latest_consensus_now = await self.mongo.async_db.consensus.find_one({
                    'index': self.latest_block.index + 1,
                    'block.version': CHAIN.get_version_for_height(self.latest_block.index + 1),
                    'ignore': {'$ne': True}
                })

                if latest_consensus_now and latest_consensus.index == latest_consensus_now['index']:
                    await self.search_network_for_new()
                    return True
            else:
                await self.search_network_for_new()
                return True
        except Exception as e:
            exc_type, exc_obj, exc_tb = exc_info()
            fname = path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.app_log.warning("{} {} {}".format(exc_type, fname, exc_tb.tb_lineno))
            raise

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
                await async_sleep(20)
            if len(self.peers.peers) < 1:
                self.app_log.info("No peer to connect to yet")
                await async_sleep(10)
                return
            polling_peers = [peer.to_string() for peer in self.peers.peers]
        # TODO: use an aio lock
        self.app_log.debug('requesting {} ...'.format(self.latest_block.index + 1))
        http_client = AsyncHTTPClient()

        # for peer in self.peers.peers:
        for peer_string in polling_peers:
            self.peers.syncing = True
            try:
                self.app_log.debug('requesting {} from {}'.format(self.latest_block.index + 1, peer_string))
                peer = Peer.from_string(peer_string)
                try:
                    url = 'http://{peer}/get-blocks?start_index={start_index}&end_index={end_index}'\
                        .format(peer=peer_string,
                                start_index=int(self.latest_block.index) +1,
                                end_index=int(self.latest_block.index) + 100)
                    request = HTTPRequest(url, connect_timeout=3,request_timeout=5)
                    response = await http_client.fetch(request)
                    if response.code != 200:
                        continue
                    # result = requests.get(url, timeout=2)
                except HTTPError as e:
                    self.app_log.warning('Error requesting from {} ...'.format(peer_string))
                    # add to failed peers
                    await self.peers.increment_failed(peer)
                    continue
                except ConnectTimeoutError as e:
                    self.app_log.warning('Timeout requesting from {} ...'.format(peer_string))
                    # add to failed peers
                    await self.peers.increment_failed(peer)
                    continue
                except Exception as e:
                    self.app_log.error('error {} requesting from {} ...'.format(e, peer_string))
                    await self.peers.increment_failed(peer)
                    continue
                try:
                    blocks = json.loads(response.body.decode('utf-8'))
                    # blocks = json.loads(result.content)
                except ValueError:
                    continue
                inserted = False
                for block in blocks:
                    # print("looking for ", self.existing_blockchain.blocks[-1].index + 1)
                    block = Block.from_dict(block)
                    if block.index == (self.existing_blockchain.blocks[-1].index + 1):
                        await self.insert_consensus_block(block, peer)
                        # print("consensus ok", block.index)
                        res = await self.import_block({'peer': peer_string, 'block': block.to_dict(),
                                                       'extra_blocks': blocks},
                                                      trigger_event=False)
                        # print("import ", block.index, res)
                        if res:
                            self.latest_block = block
                            inserted = True
                        else:
                            # 2 cases: bad block, or retrace.
                            if self.existing_blockchain.blocks[-1].index == self.latest_block.index:
                                # bad block, nothing moved, early exit
                                self.app_log.debug('Bad block {}'.format(block.index))
                            else:
                                # retraced, sync
                                self.latest_block = Block.from_dict(await self.config.BU.get_latest_block_async())
                                self.app_log.debug('retraced up to {}'.format(self.latest_block.index))
                                inserted = True
                            # in both case, no need to process further blocks
                            break
                    else:
                        break
                        #print("pass", block.index)
                if inserted:
                    await self.trigger_update_event()
                    # await self.peers.on_block_insert(self.latest_block.to_dict())
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

    async def import_block(self, block_data: dict, trigger_event=True) -> bool:
        """Block_data contains peer and block keys. Tries to import that block, retrace if necessary
        sends True if that block was inserted, False if it fails or if a retrace was needed.

        This is the central entry point for inserting a block, that will modify the local chain and trigger the event,
        unless we asked not to, because we're in a batch insert context"""
        try:
            block = Block.from_dict(block_data['block'])
            peer = Peer.from_string(block_data['peer'])
            if 'extra_blocks' in block_data:
                extra_blocks = None
                # extra_blocks = [Block.from_dict( x) for x in block_data['extra_blocks']]  # Not used later on, just ram and resources usage
            else:
                extra_blocks = None
            self.app_log.debug("Latest block was {} {} {} {}".format(self.latest_block.hash, block.prev_hash, self.latest_block.index, (block.index - 1)))
            if int(block.index) > CHAIN.CHECK_TIME_FROM and int(block.time) < int(self.latest_block.time):
                self.app_log.warning("New block {} can't be at a sooner time than previous one. Rejecting".format(block.index))
                await self.mongo.async_db.consensus.update_one(
                    {
                        'peer': peer.to_string(),
                        'index': block.index,
                        'id': block.signature
                    },
                    {'$set': {'ignore': True}}
                )
                return False
            if int(block.index) > CHAIN.CHECK_TIME_FROM and (int(block.time) < (int(self.latest_block.time) + 600)) and block.special_min:
                self.app_log.warning("New special min block {} too soon. Rejecting".format(block.index))
                await self.mongo.async_db.consensus.update_one(
                    {
                        'peer': peer.to_string(),
                        'index': block.index,
                        'id': block.signature
                    },
                    {'$set': {'ignore': True}}
                )
                return False
            try:
                result = await self.integrate_block_with_existing_chain(block, extra_blocks)
                if result is False:
                    # TODO: factorize
                    await self.mongo.async_db.consensus.update_one(
                        {
                            'peer': peer.to_string(),
                            'index': block.index,
                            'id': block.signature
                        },
                        {'$set': {'ignore': True}}
                    )
                elif trigger_event:
                    await self.trigger_update_event(block_data['block'])
                return result
            except DuplicateKeyError as e:
                await self.mongo.async_db.consensus.update_one(
                    {
                        'peer': peer.to_string(),
                        'index': block.index,
                        'id': block.signature
                    },
                    {'$set': {'ignore': True}}
                )
            except AboveTargetException as e:
                await self.mongo.async_db.consensus.update_one(
                    {
                        'peer': peer.to_string(),
                        'index': block.index,
                        'id': block.signature
                    },
                    {'$set': {'ignore': True}}
                )
            except ForkException as e:
                await self.retrace(block, peer)
                if trigger_event:
                    await self.trigger_update_event()
                return False
            except IndexError as e:
                await self.retrace(block, peer)
                if trigger_event:
                    await self.trigger_update_event()
                return False
            except Exception as e:
                print("348", e)
                exc_type, exc_obj, exc_tb = exc_info()
                fname = path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                self.app_log.warning("{} {} {}".format(exc_type, fname, exc_tb.tb_lineno))
                await self.mongo.async_db.consensus.update_one(
                    {
                        'peer': peer.to_string(),
                        'index': block.index,
                        'id': block.signature
                    },
                    {'$set': {'ignore': True}}
                )
        except Exception as e:
            exc_type, exc_obj, exc_tb = exc_info()
            fname = path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.app_log.warning("{} {} {}".format(exc_type, fname, exc_tb.tb_lineno))
            if trigger_event:
                await self.trigger_update_event()
            return False
        if trigger_event:
            await self.trigger_update_event()
        return True

    async def process_next_block(self, block_data: dict, peer, trigger_event=True) -> bool:
        """This is the common entry point for all new possible blocks to enter consensus and chain"""
        block_object = Block.from_dict(block_data)
        if block_object.in_the_future():
            # Most important
            self.app_log.warning('Block in the future for height %s  from peer: %s' % (block_object.index, peer.to_string()))
            return False
        # TODO: there is no check before inserting into consensus (previous hash, nor diff, nor valid tx)
        await self.insert_consensus_block(block_object, peer)
        self.app_log.debug("Consensus ok {}".format(block_object.index))
        res = await self.import_block({'peer': peer.to_string(), 'block': block_data},
                                      trigger_event=trigger_event)
        self.app_log.debug("Import_block {} {}".format(block_object.index, res))
        return res

    async def integrate_block_with_existing_chain(self, block: Block, extra_blocks=None):
        """Even in case of retrace, this is the only place where we insert a new block into the block collection and update BU"""
        try:
            # TODO: reorg the checks, to have the faster ones first.
            # Like, here we begin with checking every tx one by one, when <e did not even check index and provided hash matched previous one.
            try:
                block.verify()
            except Exception as e:
                print("Integrate block error 1", e)
                return False

            for transaction in block.transactions:
                try:
                    if extra_blocks:
                        transaction.extra_blocks = extra_blocks
                    transaction.verify()
                except InvalidTransactionException as e:
                    print(e)
                    return False
                except InvalidTransactionSignatureException as e:
                    print(e)
                    return False
                except MissingInputTransactionException as e:
                    print(e)
                    return False
                except NotEnoughMoneyException as e:
                    print(e)
                    return False
                except Exception as e:
                    print(e)
                    return False
            if block.index == 0:
                return True
            height = block.index
            last_block = self.existing_blockchain.blocks[block.index - 1]
            if last_block.index != (block.index - 1) or last_block.hash != block.prev_hash:
                print("Integrate block error 2")
                raise ForkException()
            if not last_block:
                print("Integrate block error 3")
                raise ForkException()

            target = BlockFactory.get_target(height, last_block, block, self.existing_blockchain)
            delta_t = int(time()) - int(last_block.time)
            special_target = CHAIN.special_target(block.index, block.target, delta_t, get_config().network)
            target_block_time = CHAIN.target_block_time(self.config.network)

            if block.index >= 35200 and delta_t < 600 and block.special_min:
                raise Exception('Special min block too soon')

            # TODO: use a CHAIN constant for pow blocks limits
            if ((int(block.hash, 16) < target) or
                (block.special_min and int(block.hash, 16) < special_target) or
                (block.special_min and block.index < 35200) or
                (block.index >= 35200 and block.index < 38600 and block.special_min and
                (int(block.time) - int(last_block.time)) > target_block_time)):

                if last_block.index == (block.index - 1) and last_block.hash == block.prev_hash:
                    # self.mongo.db.blocks.update({'index': block.index}, block.to_dict(), upsert=True)
                    # self.mongo.db.blocks.remove({'index': {"$gt": block.index}}, multi=True)
                    # todo: is this useful? can we have more blocks above? No because if we had, we would have raised just above
                    await self.mongo.async_db.block.delete_many({'index': {"$gte": block.index}})
                    await self.mongo.async_db.blocks.replace_one({'index': block.index}, block.to_dict(), upsert=True)
                    # TODO: why do we need to keep that one in memory?
                    try:
                        self.existing_blockchain.blocks[block.index] = block
                        del self.existing_blockchain.blocks[block.index+1:]
                    except:
                        self.existing_blockchain.blocks.append(block)
                    if self.debug:
                        self.app_log.info("New block inserted for height: {}".format(block.index))
                    await self.config.on_new_block(block)  # This will propagate to BU
                    return True
                else:
                    print("Integrate block error 4")
                    raise ForkException()
            else:
                print("Integrate block error 5")
                raise AboveTargetException()
            return False  # unreachable code
        except Exception as e:
            exc_type, exc_obj, exc_tb = exc_info()
            fname = path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.app_log.warning("integrate_block_with_existing_chain {} {} {}".format(exc_type, fname, exc_tb.tb_lineno))
            raise
    
    def get_difficulty(self, blocks):
        """Computes a list of blocks difficulty. This is the sum of the distance to the highest possible target"""
        difficulty = 0
        for block in blocks:
            target = int(block.hash, 16)
            difficulty += (CHAIN.MAX_TARGET - target)
        return difficulty

    async def retrace(self, block, peer):
        """We got a non compatible block. Retrace other chains to find a common ancestor and evaluate chains."""
        # TODO: more async conversion TBD here. Low priority since not called often atm.
        # TODO: cleanup print and logging
        # TODO: limit possible retrace blocks vs max(known chains) - store in chain config
        try:
            self.app_log.info("Retracing...")
            blocks = [block]
            while 1:
                if self.debug:
                    self.app_log.info("{} : {}".format(block.hash, block.index))
                # get the previous block from either the consensus collection in mongo
                # or attempt to get the block from the remote peer
                previous_consensus_block = await self.get_previous_consensus_block_from_local(block, peer)
                if previous_consensus_block:
                        block = previous_consensus_block
                        blocks.append(block)
                else:
                    if peer.is_me:
                        self.mongo.db.consensus.update({'peer': peer.to_string(), 'index': {'$gte': block.index}}, {'$set': {'ignore': True}}, multi=True)
                        return
                    try:
                        previous_consensus_block = self.get_previous_consensus_block_from_remote(block, peer)
                    except BadPeerException as e:
                        self.mongo.db.consensus.update({'peer': peer.to_string(), 'index': {'$gte': block.index}}, {'$set': {'ignore': True}}, multi=True)
                    except:
                        pass
                    if previous_consensus_block and previous_consensus_block.index + 1 == block.index:
                        block = previous_consensus_block
                        blocks.append(block)
                        try:
                            await self.insert_consensus_block(block, peer)
                        except Exception as e:
                            if self.debug:
                                self.app_log.warning("Exception retrace insert_consensus_block: {}".format(e))  # we should do something here to keep it from looping on this failed block
                    else:
                        # identify missing and prune
                        # if the pruned chain is still longer, we'll take it
                        if previous_consensus_block:
                            block = previous_consensus_block
                            blocks = [block]
                        else:
                            return
                if self.debug:
                    self.app_log.info('attempting sync at {}, len {}'.format(block.prev_hash, len(self.existing_blockchain.blocks)))
                # if they do have it, query our consensus collection for prevHash of that block, repeat 1 and 2 until index 1
                if self.existing_blockchain.blocks[block.index - 1].hash == block.prev_hash:
                    prev_blocks_check = self.existing_blockchain.blocks[block.index - 1]
                    if self.debug:
                        self.app_log.debug("Previous block {}: {}".format(prev_blocks_check.hash, prev_blocks_check.index))
                    blocks = sorted(blocks, key=lambda x: x.index)
                    block_for_next = blocks[-1]
                    while 1:
                        next_block = await self.get_next_consensus_block_from_local(block_for_next)
                        if next_block:
                            blocks.append(next_block)
                            block_for_next = next_block
                        else:
                            break

                    # self.peers.init(self.config.network)

                    self.app_log.debug('requesting {} ...'.format(block_for_next.index + 1))
                    for apeer in self.peers.peers:
                        # TODO: there was a "while 1:" there, that got the retrace stuck with only 1 peer and no escape route.
                        # recheck the logic.
                        try:
                            # if self.debug:
                            #     self.app_log.debug('requesting {} from {}'.format(block_for_next.index + 1, apeer.to_string()))
                            result = requests.get('http://{peer}/get-blocks?start_index={start_index}&end_index={end_index}'.format(
                                peer=apeer.to_string(),
                                start_index=block_for_next.index + 1,
                                end_index=block_for_next.index + 100
                            ), timeout=1)
                            remote_blocks = [Block.from_dict( x) for x in json.loads(result.content)]
                            break_out = False
                            for remote_block in remote_blocks:
                                if remote_block.prev_hash == block_for_next.hash:
                                    blocks.append(remote_block)
                                    block_for_next = remote_block
                                else:
                                    break_out = True
                                    break
                            if break_out:
                                break
                        except Exception as e:
                            if self.debug:
                                print(e)
                            break

                    # if we have it in our blockchain, then we've hit the fork point
                    # now we have to loop through the current block array and build a blockchain
                    # then we compare the block height and difficulty of the two chains
                    # replace our current chain if necessary by removing them from the database
                    # then looping though our new chain, inserting the new blocks
                    def subchain_gen(existing_blocks, addon_blocks, gen_block):
                        for x in existing_blocks[:addon_blocks[0].index]:
                            if x.index < gen_block.index:
                                yield x
                        for x in addon_blocks:
                            yield x

                    # If the block height is equal, we throw out the inbound chain, it muse be greater
                    # If the block height is lower, we throw it out
                    # if the block height is heigher, we compare the difficulty of the entire chain

                    existing_difficulty = self.get_difficulty(self.existing_blockchain.blocks)

                    inbound_difficulty = self.get_difficulty(subchain_gen(self.existing_blockchain.blocks, blocks, block))

                    if (blocks[-1].index >= self.existing_blockchain.blocks[-1].index
                        and inbound_difficulty >= existing_difficulty):
                        for block in blocks:
                            try:
                                if block.index == 0:
                                    continue
                                await self.integrate_block_with_existing_chain(block)
                                if self.debug:
                                    self.app_log.debug('inserted {}'.format(block.index))
                            except ForkException as e:
                                back_one_block = block
                                while 1:
                                    back_one_block = self.mongo.db.consensus.find_one({'block.hash': back_one_block.prev_hash})
                                    if back_one_block:
                                        back_one_block = Block.from_dict( back_one_block['block'])
                                        try:
                                            result = self.integrate_block_with_existing_chain(back_one_block)
                                            if result:
                                                await self.integrate_block_with_existing_chain(block)
                                                break
                                        except ForkException as e:
                                            pass
                                    else:
                                        return
                            except AboveTargetException as e:
                                return
                            except IndexError as e:
                                return
                        self.app_log.info("Retrace result: replaced chain with incoming")
                        return
                    else:
                        if not peer.is_me:
                            if self.debug:
                                self.app_log.info("Incoming chain lost {} {} {} {}"
                                                  .format(inbound_difficulty, existing_difficulty, blocks[-1].index,
                                                          self.existing_blockchain.blocks[-1].index)
                                                  )
                            for block in blocks:
                                self.mongo.db.consensus.update({'block.hash': block.hash}, {'$set': {'ignore': True}}, multi=True)
                        return
                # lets go down the hash path to see where prevHash is in our blockchain, hopefully before the genesis block
                # we need some way of making sure we have all previous blocks until we hit a block with prevHash in our main blockchain
                #there is no else, we just loop again
                # if we get to index 1 and prev hash doesn't match the genesis, throw out the chain and black list the peer
                # if we get a fork point, prevHash is found in our consensus or genesis, then we compare the current
                # blockchain against the proposed chain.

                # TODO: Here, compare vs current known consensus height, and limit to consensus height - CHAIN.MAX_RETRACE_DEPTH
                if block.index == 0:
                    self.app_log.info("Retrace result: zero index reached")
                    return
            self.app_log.info("Retrace result: doesn't follow any known chain")  # throwing out the block for now
            return
        except Exception as e:
            exc_type, exc_obj, exc_tb = exc_info()
            fname = path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.app_log.warning("{} {} {}".format(exc_type, fname, exc_tb.tb_lineno))
            raise