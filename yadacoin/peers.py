import json
import requests
import pymongo
from mongo import Mongo

class Peers(object):
    @classmethod
    def init_local(cls):
        Mongo.init()
        res = Mongo.db.peers.find({'active': True, 'failed': {'$lt': 30}}, {'_id': 0})
        cls.my_peer = Mongo.db.config.find_one({'mypeer': {"$ne": ""}}).get('mypeer')
        peers = [x for x in res]
        cls.peers = []
        try:
            for peer in peers:
                cls.peers.append(
                    Peer(
                        peer['host'],
                        peer['port']
                    )
                )
        except:
            pass
        return json.dumps({'peers': peers})

    @classmethod
    def init(cls, my_peer=True):
        cls.peers = []
        try:
            if my_peer:
                cls.my_peer = Mongo.db.config.find_one({'mypeer': {"$ne": ""}}).get('mypeer')
            res = requests.get('https://yadacoin.io/peers')
            for peer in json.loads(res.content)['peers']:
                cls.peers.append(
                    Peer(
                        peer['host'],
                        peer['port']
                    )
                )
        except:
            pass

    @classmethod
    def get_blocks(cls, peer, start, end):
        from block import Block
        print 'http://%s:%s/get-blocks?start_index=%s&end_index=%s' % (peer.host, peer.port, start, end)
        try:
            res = requests.get('http://%s:%s/get-blocks?start_index=%s&end_index=%s' % (peer.host, peer.port, start, end))
        except:
            return []
        if res.content:
            return [Block.from_dict(block) for block in json.loads(res.content)]
        else:
            return []

    @classmethod
    def populate_peers(cls):
        for peer in cls.peers:
            cls.populate_peer(peer)

    @classmethod
    def populate_peer(cls, peer):
        i = 0
        while 1:
            try:
                print peer.to_string()
                blocks = cls.get_blocks(peer, i, i + 1000)
                if blocks:
                    cls.insert_peer_blocks(blocks, peer)
                else:
                    break
                print 'working'
            except:
                print 'error'
                raise
            i += 1000

    @classmethod
    def insert_peer_blocks(cls, blocks, peer):
        from block import Block, BlockFactory
        for block in blocks:
            if block.index == 0:
                if block.hash == BlockFactory.get_genesis_block().hash:
                    print 'peer genesis block matches'
                    dup_check = Mongo.db.consensus.find({'id': block.signature, 'peer': peer.to_string()})
                    if dup_check.count():
                        continue
                    print 'inserting...'
                    Mongo.db.consensus.insert({
                        'block': block.to_dict(),
                        'index': block.to_dict().get('index'),
                        'id': block.to_dict().get('id'),
                        'peer': peer.to_string()})
                else:
                    print 'peer genesis block does not match'
            else:
                compare_for_peer = [x for x in Mongo.db.consensus.find({'peer': peer.to_string(), 'index': block.index - 1}).sort('index', pymongo.DESCENDING).limit(0)]
                if compare_for_peer:
                    if block.index - 1 == compare_for_peer[0]['index'] and block.prev_hash == compare_for_peer[0]['block']['hash']:
                        dup_check = Mongo.db.consensus.find({'id': block.signature, 'peer': peer.to_string()})
                        if dup_check.count():
                            continue
                        print 'inserting...'
                        Mongo.db.consensus.insert({
                            'block': block.to_dict(),
                            'index': block.to_dict().get('index'),
                            'id': block.to_dict().get('id'),
                            'peer': peer.to_string()})
                    else:
                        print 'does not follow chain', block.index - 1, compare_for_peer[0]['index'], block.prev_hash, compare_for_peer[0]['block']['hash']
                        peer.set_broken()
                        break


    @classmethod
    def from_dict(cls, config):
        cls.peers = []
        for peer in config['peers']:
            cls.peers.append(
                Peer(
                    peer['host'],
                    peer['port']
                )
            )

    @classmethod
    def to_dict(cls):
        peers = [x.to_dict() for x in cls.peers]
        return {
            'num_peers': len(peers),
            'peers': peers
        }

class Peer(object):
    def __init__(self, host, port, is_me=False):
        self.host = host
        self.port = port
        self.is_me = is_me

    @classmethod
    def from_string(cls, peerstr):
        if ":" in peerstr:
            peer = peerstr.split(':')
            return cls(peer[0], peer[1])
        elif peerstr == 'me':
            return cls(None, None, is_me=True)

    def is_broken(self):
        broken_test = [x for x in Mongo.db.broken_peers.find({"peer": self.to_string()})]
        return broken_test and broken_test[0]['broken']

    def set_broken(self):
        Mongo.db.broken_peers.update({"peer": self.to_string()}, {"peer": self.to_string(), "broken": True}, upsert=True)

    def unset_broken(self):
        Mongo.db.broken_peers.update({"peer": self.to_string()}, {"peer": self.to_string(), "broken": False}, upsert=True)

    def to_dict(self):
        return {
            'host': self.host,
            'port': self.port,
            'is_me': self.is_me
        }

    def to_string(self):
        if self.is_me:
            return 'me'
        else:
            return "%s:%s" % (self.host, self.port)