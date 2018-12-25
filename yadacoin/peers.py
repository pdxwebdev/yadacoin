import json
import requests
import pymongo
from mongo import Mongo

class Peers(object):
    @classmethod
    def init_local(cls, config):
        mongo = Mongo(config)
        res = mongo.db.peers.find({'active': True, 'failed': {'$lt': 30}}, {'_id': 0})
        cls.my_peer = mongo.db.config.find_one({'mypeer': {"$ne": ""}}).get('mypeer')
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
    def init(cls, config, my_peer=True):
        mongo = Mongo(config)
        cls.peers = []
        try:
            if my_peer:
                cls.my_peer = mongo.db.config.find_one({'mypeer': {"$ne": ""}}).get('mypeer')
            res = requests.get('http://yadacoin.io:8888/peers')
            for peer in json.loads(res.content)['peers']:
                cls.peers.append(
                    Peer(
                        peer['host'],
                        peer['port'],
                        peer.get('bulletin_secret')
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
                    dup_check = mongo.db.consensus.find({'id': block.signature, 'peer': peer.to_string()})
                    if dup_check.count():
                        continue
                    print 'inserting...'
                    mongo.db.consensus.insert({
                        'block': block.to_dict(),
                        'index': block.to_dict().get('index'),
                        'id': block.to_dict().get('id'),
                        'peer': peer.to_string()})
                else:
                    print 'peer genesis block does not match'
            else:
                compare_for_peer = [x for x in mongo.db.consensus.find({'peer': peer.to_string(), 'index': block.index - 1}).sort('index', pymongo.DESCENDING).limit(0)]
                if compare_for_peer:
                    if block.index - 1 == compare_for_peer[0]['index'] and block.prev_hash == compare_for_peer[0]['block']['hash']:
                        dup_check = mongo.db.consensus.find({'id': block.signature, 'peer': peer.to_string()})
                        if dup_check.count():
                            continue
                        print 'inserting...'
                        mongo.db.consensus.insert({
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
                    peer['port'],
                    peer.get('bulletin_secret')
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
    def __init__(self, host, port, bulletin_secret=None, is_me=False):
        self.host = host
        self.port = port
        self.bulletin_secret = bulletin_secret
        self.is_me = is_me

    @classmethod
    def from_string(cls, peerstr):
        if ":" in peerstr:
            peer = peerstr.split(':')
            return cls(peer[0], peer[1])
        elif peerstr == 'me':
            return cls(None, None, is_me=True)

    def is_broken(self):
        broken_test = [x for x in mongo.db.broken_peers.find({"peer": self.to_string()})]
        return broken_test and broken_test[0]['broken']

    def set_broken(self):
        mongo.db.broken_peers.update({"peer": self.to_string()}, {"peer": self.to_string(), "broken": True}, upsert=True)

    def unset_broken(self):
        mongo.db.broken_peers.update({"peer": self.to_string()}, {"peer": self.to_string(), "broken": False}, upsert=True)

    @classmethod
    def init_my_peer(cls):
        import socket
        from config import Config
        from miniupnpc import UPnP
        # deploy as an eventlet WSGI server
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((config.serve_host, 0))
            server_port = sock.getsockname()[1]
            sock.close()
            eport = server_port
            u = UPnP(None, None, 200, 0)
            u.discover()
            u.selectigd()
            r = u.getspecificportmapping(eport, 'TCP')
            while r != None and eport < 65536:
                eport = eport + 1
                r = u.getspecificportmapping(eport, 'TCP')
            b = u.addportmapping(eport, 'TCP', u.lanaddr, server_port, 'UPnP YadaCoin Serve port %u' % eport, '')
            config.serve_host = '0.0.0.0'
            config.serve_port = server_port
            config.peer_host = u.externalipaddress()
            config.peer_port = server_port
        except:
            config.serve_host = config.serve_host
            config.serve_port = config.serve_port
            config.peer_host = config.peer_host
            config.peer_port = config.peer_port
            print 'UPnP failed: you must forward and/or whitelist port', config.peer_port

        cls.save_my_peer()
    
    @classmethod
    def save_my_peer(cls):
        from config import Config
        peer = config.peer_host + ":" + str(config.peer_port)
        mongo = Mongo(config)
        mongo.db.config.update({'mypeer': {"$ne": ""}}, {'mypeer': peer}, upsert=True)
        try:
            res = requests.post(
                'http://yadacoin.io:8888/peers',
                json.dumps({
                    'host': config.peer_host,
                    'port': config.peer_port,
                    'bulletin_secret': config.get_bulletin_secret()
                }),
                headers={
                    "Content-Type": "application/json"
                }
            )
        except:
            print 'ERROR: failed to get peers, exiting...'
            exit()

    def to_dict(self):
        return {
            'host': self.host,
            'port': self.port,
            'bulletin_secret': self.bulletin_secret,
            'is_me': self.is_me
        }

    def to_string(self):
        if self.is_me:
            return 'me'
        else:
            return "%s:%s" % (self.host, self.port)