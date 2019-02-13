import sys
import json
import requests
from mongo import Mongo
from peers import Peers, Peer
from blockchainutils import BU
from blockchain import Blockchain
from block import Block, BlockFactory
from exceptions import Exception

class BadPeerException(Exception):
    pass

class AboveTargetException(Exception):
    pass

class ForkException(Exception):
    pass

class Consensus(object):
    lowest = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    def __init__(self, config, mongo):
        self.config = config
        self.mongo = mongo
        latest_block = BU.get_latest_block(self.config, self.mongo)
        if latest_block:
            self.latest_block = Block.from_dict(self.config, self.mongo, latest_block)
        else:
            self.insert_genesis()
        
        self.cache_existing_blockchain()
    
    def cache_existing_blockchain(self):
        self.existing_blockchain = Blockchain(self.config, self.mongo, BU.get_blocks(self.config, self.mongo))

    def output(self, string):
        sys.stdout.write(string)  # write the next character
        sys.stdout.flush()                # flush stdout buffer (actual character display)
        sys.stdout.write(''.join(['\b' for i in range(len(string))])) # erase the last written char

    def log(self, message):
        print message

    def insert_genesis(self):
        #insert genesis if it doesn't exist
        genesis_block = BlockFactory.get_genesis_block(self.config, self.mongo)
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

    def verify_existing_blockchain(self):
        self.log('verifying existing blockchain')
        result = self.existing_blockchain.verify(self.output)
        if not result['verified']:
            self.mongo.db.blocks.remove({"index": {"$gt": result['last_good_block'].index}}, multi=True)

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
            if BU.get_version_for_height(x['block']['index']) == int(x['block']['version']):
                yield x

    def get_latest_consensus_block(self):
        latests = self.get_latest_consensus_blocks()
        for latest in latests:
            if int(latest['block']['version']) == BU.get_version_for_height(latest['block']['index']):
                return Block.from_dict(self.config, self.mongo, latest['block'])

    def get_consensus_blocks_by_index(self, index):
        return self.mongo.db.consensus.find({'index': index, 'block.prevHash': {'$ne': ''}, 'block.version': BU.get_version_for_height(index)}, {'_id': 0})

    def get_consensus_block_by_index(self, index):
        return self.get_consensus_blocks_by_index(index).limit(1)[0]

    def rank_consenesus_blocks(self):
        # rank is based on target, total chain difficulty, and chain validity
        records = self.get_consensus_blocks_by_index(self.latest_block.index + 1)
        lowest = self.lowest

        ranks = []
        for record in records:
            peer = Peer.from_string(self.config, self.mongo, record['peer'])
            block = Block.from_dict(self.config, self.mongo, record['block'])
            target = int(record['block']['hash'], 16)
            if target < lowest:
                ranks.append({
                    'target': target,
                    'block': block,
                    'peer': peer
                })
        return sorted(ranks, key=lambda x: x['target'])

    def get_next_consensus_block_from_local(self, block):
        #table cleanup
        new_block = self.mongo.db.consensus.find_one({
            'block.prevHash': block.hash,
            'block.index': (block.index + 1),
            'block.version': BU.get_version_for_height((block.index + 1)),
            'ignore': {'$ne': True}
        })
        if new_block:
            new_block = Block.from_dict(self.config, self.mongo, new_block['block'])
            if int(new_block.version) == BU.get_version_for_height(new_block.index):
                return new_block
            else:
                return None
        return None

    def get_previous_consensus_block_from_local(self, block, peer):
        #table cleanup
        new_block = self.mongo.db.consensus.find_one({
            'block.hash': block.prev_hash,
            'block.index': (block.index - 1),
            'block.version': BU.get_version_for_height((block.index - 1)),
            'ignore': {'$ne': True}
        })
        if new_block:
            new_block = Block.from_dict(self.config, self.mongo, new_block['block'])
            if int(new_block.version) == BU.get_version_for_height(new_block.index):
                return new_block
            else:
                return None
        return None

    def get_previous_consensus_block_from_remote(self, block, peer):
        retry = 0
        while True:
            try:
                url = 'http://' + peer.to_string() + '/get-block?hash=' + block.prev_hash
                print 'getting block', url
                res = requests.get(url, timeout=1, headers={'Connection':'close'})
            except:
                if retry == 50:
                    raise BadPeerException()
                else:
                    retry += 1
                    continue
            try:
                print 'response code: ', res.status_code
                new_block = Block.from_dict(self.config, self.mongo, json.loads(res.content))
                if int(new_block.version) == BU.get_version_for_height(new_block.index):
                    return new_block
                else:
                    return None
            except:
                return None

    def insert_consensus_block(self, block, peer):
        print 'inserting new consensus block for height and peer: %s %s' % (block.index, peer.to_string())
        failed_prev_check = self.mongo.db.consensus.find_one({
            'id': block.to_dict().get('id')
        })
        if failed_prev_check:
            raise Exception('cannot insert previously failed block')
        self.mongo.db.consensus.update({
            'id': block.to_dict().get('id'),
            'peer': peer.to_string()
        },
        {
            'block': block.to_dict(),
            'index': block.to_dict().get('index'),
            'id': block.to_dict().get('id'),
            'peer': peer.to_string()
        }, upsert=True)

    def sync_bottom_up(self):
        #bottom up syncing

        self.latest_block = Block.from_dict(self.config, self.mongo, BU.get_latest_block(self.config, self.mongo))
        self.remove_pending_transactions_now_in_chain()
        self.remove_fastgraph_transactions_now_in_chain()

        latest_consensus = self.mongo.db.consensus.find_one({
            'index': self.latest_block.index + 1,
            'block.version': BU.get_version_for_height(self.latest_block.index + 1),
            'ignore': {'$ne': True}
        })
        if latest_consensus:
            latest_consensus = Block.from_dict(self.config, self.mongo, latest_consensus['block'])
            print latest_consensus.index, "latest consensus_block"

            records = self.mongo.db.consensus.find({'index': self.latest_block.index + 1, 'block.version': BU.get_version_for_height(self.latest_block.index + 1), 'ignore': {'$ne': True}})
            for record in sorted(records, key=lambda x: int(x['block']['target'], 16)):
                result = self.import_block(record)
            
        else:
            Peers.init(self.config, self.mongo, self.config.network)
            found_new = False
            for peer in Peers.peers:
                try:
                    print 'requesting %s from %s' % (self.latest_block.index + 1, peer.to_string()) 
                    result = requests.get('http://{peer}/get-blocks?start_index={start_index}&end_index={end_index}'.format(
                        peer=peer.to_string(),
                        start_index=self.latest_block.index + 1,
                        end_index=self.latest_block.index + 1
                    ), timeout=1)
                    block = Block.from_dict(self.config, self.mongo, json.loads(result.content)[0])
                    if block.index == (self.latest_block.index + 1):
                        self.insert_consensus_block(block, peer)
                    found_new = True
                except Exception as e:
                    print e

            if found_new:
                return False
            else:
                self.log('up to date, height: ' + str(self.latest_block.index))
                return True

    def import_block(self, block_data):
        block = Block.from_dict(self.config, self.mongo, block_data['block'])
        peer = Peer.from_string(self.config, self.mongo, block_data['peer'])
        print self.latest_block.hash, block.prev_hash, self.latest_block.index, (block.index - 1)
        try:
            result = self.integrate_block_with_existing_chain(block)
            if result is False:
                self.mongo.db.consensus.update(
                    {
                        'peer': peer.to_string(),
                        'index': block.index,
                        'id': block.signature
                    },
                    {'$set': {'ignore': True}}
                )
            return result
        except AboveTargetException as e:
            self.mongo.db.consensus.update(
                {
                    'peer': peer.to_string(),
                    'index': block.index,
                    'id': block.signature
                },
                {'$set': {'ignore': True}}
            )
        except ForkException as e:
            self.retrace(block, peer)
        except IndexError as e:
            self.retrace(block, peer)

    def integrate_block_with_existing_chain(self, block):
        if block.index == 0:
            return True
        height = block.index
        last_block = self.existing_blockchain.blocks[block.index - 1]
        if not last_block:
            raise ForkException()
        last_time = last_block.time
        target = BlockFactory.get_target(self.config, self.mongo, height, last_time, last_block, self.existing_blockchain)
        if (int(block.hash, 16) < target) or block.special_min:
            if last_block.index == (block.index - 1) and last_block.hash == block.prev_hash:
                dup = self.mongo.db.blocks.find_one({'index': block.index, 'hash': block.hash})
                if not dup:
                    self.mongo.db.blocks.update({'index': block.index}, block.to_dict(), upsert=True)
                    try:
                        self.existing_blockchain.blocks[block.index] = block
                    except:
                        self.existing_blockchain.blocks.append(block)
                    print "New block inserted for height: ", block.index
                    return True
                else:
                    self.existing_blockchain.blocks[block.index] = block
                    return True
            else:
                raise ForkException()
        else:
            raise AboveTargetException()
        return False

    def retrace(self, block, peer):
        self.log("retracing...")
        blocks = []
        blocks.append(block)
        while 1:
            self.log(block.hash)
            self.log(block.index)
            # get the previous block from either the consensus collection in mongo
            # or attempt to get the block from the remote peer
            previous_consensus_block = self.get_previous_consensus_block_from_local(block, peer)
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
                        self.insert_consensus_block(block, peer)
                    except Exception as e:
                        print e # we should do something here to keep it from looping on this failed block
                else:
                    # identify missing and prune
                    # if the pruned chain is still longer, we'll take it
                    if previous_consensus_block:
                        block = previous_consensus_block
                        blocks = [block]
                    else:
                        return

            print 'attempting sync at', block.prev_hash
            # if they do have it, query our consensus collection for prevHash of that block, repeat 1 and 2 until index 1
            if self.existing_blockchain.blocks[block.index - 1].hash == block.prev_hash:
                prev_blocks_check = self.existing_blockchain.blocks[block.index - 1]
                print prev_blocks_check.hash, prev_blocks_check.index
                blocks = sorted(blocks[:], key=lambda x: x.index)
                block_for_next = blocks[-1]
                while 1:
                    next_block = self.get_next_consensus_block_from_local(block_for_next)
                    if next_block:
                        blocks.append(next_block)
                        block_for_next = next_block
                    else:
                        break

                Peers.init(self.config, self.mongo, self.config.network)

                for peer in Peers.peers:
                    while 1:
                        try:
                            print 'requesting %s from %s' % (self.latest_block.index + 1, peer.to_string()) 
                            result = requests.get('http://{peer}/get-blocks?start_index={start_index}&end_index={end_index}'.format(
                                peer=peer.to_string(),
                                start_index=block_for_next.index + 1,
                                end_index=block_for_next.index + 100
                            ), timeout=1)
                            remote_blocks = [Block.from_dict(self.config, self.mongo, x) for x in json.loads(result.content)]
                            for remote_block in remote_blocks:
                                if remote_block.hash == block_for_next.prev_hash + 1:
                                    blocks.append(remote_block)
                                    block_for_next = remote_block
                        except Exception as e:
                            print e
                            break

                # if we have it in our blockchain, then we've hit the fork point
                # now we have to loop through the current block array and build a blockchain
                # then we compare the block height and difficulty of the two chains
                # replace our current chain if necessary by removing them from the database
                # then looping though our new chain, inserting the new blocks
                def subchain_gen(blocks, addon_blocks, block):
                    for x in self.mongo.db.blocks.find({'index': {'$lt': block.index}}).sort([('index', 1)]):
                        x = Block.from_dict(self.config, self.mongo, x)
                        if x.index < block.index:
                            yield x
                    for x in addon_blocks:
                        yield x
                    
                blockchain = Blockchain(self.config, self.mongo, subchain_gen(self.existing_blockchain.blocks, blocks, block))

                # If the block height is equal, we throw out the inbound chain, it muse be greater
                # If the block height is lower, we throw it out
                # if the block height is heigher, we compare the difficulty of the entire chain

                inbound_difficulty = blockchain.get_difficulty()

                existing_difficulty = self.existing_blockchain.get_difficulty()

                if (blockchain.get_highest_block_height() >= self.existing_blockchain.get_highest_block_height() 
                    and inbound_difficulty >= existing_difficulty):
                    for block in sorted(blockchain.blocks[self.existing_blockchain.get_highest_block_height()+1:], key=lambda x: x.index):
                        try:
                            if block.index == 0:
                                continue
                            self.integrate_block_with_existing_chain(block)
                            print 'inserted ', block.index
                        except ForkException as e:
                            back_one_block = block
                            while 1:
                                back_one_block = self.mongo.db.consensus.find_one({'block.hash': back_one_block.prev_hash})
                                if back_one_block:
                                    back_one_block = Block.from_dict(self.config, self.mongo, back_one_block['block'])
                                    try:
                                        result = self.integrate_block_with_existing_chain(back_one_block)
                                        if result:
                                            self.integrate_block_with_existing_chain(block)
                                            break
                                    except ForkException as e:
                                        pass
                                else:
                                    return
                        except AboveTargetException as e:
                            return
                        except IndexError as e:
                            return
                    print "Replaced chain with incoming"
                    return
                else:
                    if not peer.is_me:
                        print "Incoming chain lost", blockchain.get_difficulty(), self.existing_blockchain.get_difficulty(), blockchain.get_highest_block_height(), self.existing_blockchain.get_highest_block_height()
                        for block in blocks:
                            self.mongo.db.consensus.update({'block.hash': block.hash}, {'$set': {'ignore': True}}, multi=True)
                    return
            # lets go down the hash path to see where prevHash is in our blockchain, hopefully before the genesis block
            # we need some way of making sure we have all previous blocks until we hit a block with prevHash in our main blockchain
            #there is no else, we just loop again
            # if we get to index 1 and prev hash doesn't match the genesis, throw out the chain and black list the peer
            # if we get a fork point, prevHash is found in our consensus or genesis, then we compare the current
            # blockchain against the proposed chain. 
            if block.index == 0:
                print "zero index reached"
                return
        print "doesn't follow any known chain" # throwing out the block for now
        return