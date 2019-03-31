"""
Kept for reference and compatibility, should not be used anymore once fully converted
"""

import json
import requests


class Peers(object):

    peers = []
    # peers_json = ''

    def __init__(self, config, mongo):
        self.config = config
        self.mongo = mongo
        self.my_peer = None

    def init_local(self):
        res = self.mongo.db.peers.find({'active': True, 'failed': {'$lt': 300}}, {'_id': 0})
        self.my_peer = self.mongo.db.config.find_one({'mypeer': {"$ne": ""}}).get('mypeer')
        peers = [x for x in res]
        self.peers = []  # Beware, this is a class property, not local
        try:
            for peer in peers:
                self.peers.append(
                    Peer(
                        self.config,
                        self.mongo,
                        peer['host'],
                        peer['port']
                    )
                )
        except:
            pass
        return self.to_json()

    @classmethod
    def init(cls, config, mongo, network='mainnet', my_peer=True):
        cls.peers = []
        if network == 'regnet':
            peer = mongo.db.config.find_one({'mypeer': {"$ne": ""}})
            if not peer:
                return
            # Insert ourself to have at least one peer. Not sure this is required, but allows for more tests coverage.
            cls.peers.append(
                    Peer(
                        config, mongo,
                        config.serve_host, config.serve_port,
                        peer.get('bulletin_secret')
                    )
                )
            return
        if network == 'mainnet':
            url = 'https://yadacoin.io/peers'
        elif network == 'testnet':
            url = 'http://yadacoin.io:8888/peers'

        try:
            if my_peer:
                cls.my_peer = mongo.db.config.find_one({'mypeer': {"$ne": ""}}).get('mypeer')
            res = requests.get(url)
            for peer in json.loads(res.content)['peers']:
                cls.peers.append(
                    Peer(
                        config,
                        mongo,
                        peer['host'],
                        peer['port'],
                        peer.get('bulletin_secret')
                    )
                )
        except:
            pass

    @classmethod
    def from_dict(cls, config, mongo):
        cls.peers = []
        for peer in config['peers']:
            cls.peers.append(
                Peer(
                    config,
                    mongo,
                    peer['host'],
                    peer['port'],
                    peer.get('bulletin_secret')
                )
            )

    def to_dict(self):
        peers = [x.to_dict() for x in self.peers]
        return {
            'num_peers': len(peers),
            'peers': peers
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)


class Peer(object):
    def __init__(self, config, mongo, host, port, bulletin_secret=None, is_me=False):
        self.config = config
        self.mongo = mongo
        self.host = host
        self.port = port
        self.bulletin_secret = bulletin_secret
        self.is_me = is_me

    @classmethod
    def from_string(cls, config, mongo, peerstr):
        if ":" in peerstr:
            peer = peerstr.split(':')
            return cls(config, mongo, peer[0], peer[1])
        elif peerstr == 'me':
            return cls(config, mongo, None, None, is_me=True)

    def report(self):
        try:
            if self.config.network == 'regnet':
                return
            if not self.config.post_peer:
                return
            if self.config.network == 'mainnet':
                url = 'https://yadacoin.io/peers'
            elif self.config.network == 'testnet':
                url = 'http://yadacoin.io:8888/peers'
            requests.post(
                url,
                json={'host': self.host, 'port': str(self.port), 'failed_v1': True},
                timeout=3,
                headers={'Connection':'close'}
            )
        except:
            print('failed to report bad peer')
            pass

    def is_broken(self):
        broken_test = [x for x in self.mongo.db.broken_peers.find({"peer": self.to_string()})]
        return broken_test and broken_test[0]['broken']

    def set_broken(self):
        self.mongo.db.broken_peers.update({"peer": self.to_string()}, {"peer": self.to_string(), "broken": True}, upsert=True)

    def unset_broken(self):
        self.mongo.db.broken_peers.update({"peer": self.to_string()}, {"peer": self.to_string(), "broken": False}, upsert=True)

    @classmethod
    def init_my_peer(cls, config, mongo, network):
        import socket
        from miniupnpc import UPnP
        # deploy as an eventlet WSGI server
        try:
            raise ValueError('test')
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((config.serve_host, 0))
            server_port = sock.getsockname()[1]
            sock.close()
            eport = server_port
            u = UPnP(None, None, 200, 0)
            u.discover()
            u.selectigd()
            r = u.getspecificportmapping(eport, 'TCP')
            while r is not None and eport < 65536:
                eport = eport + 1
                r = u.getspecificportmapping(eport, 'TCP')
            b = u.addportmapping(eport, 'TCP', u.lanaddr, server_port, 'UPnP YadaCoin Serve port %u' % eport, '')
            config.serve_host = '0.0.0.0'
            config.serve_port = server_port
            config.peer_host = u.externalipaddress()
            config.peer_port = server_port
        except Exception as e:
            print(e)
            config.serve_host = config.serve_host
            config.serve_port = config.serve_port
            config.peer_host = config.peer_host
            config.peer_port = config.peer_port
            print('UPnP failed: you must forward and/or whitelist port', config.peer_port)

        cls.save_my_peer(config, mongo, network)
        return cls(config, mongo, config.peer_host, config.peer_port)
    
    @classmethod
    def save_my_peer(cls, config, mongo, network):
        if config.network == 'regnet':
            return
        if not config.post_peer:
            return
        peer = config.peer_host + ":" + str(config.peer_port)
        mongo.db.config.update({'mypeer': {"$ne": ""}}, {'mypeer': peer}, upsert=True)
        if network == 'mainnet':
            url = 'https://yadacoin.io/peers'
        elif network == 'testnet':
            url = 'http://yadacoin.io:8888/peers'
        try:
            requests.post(
                url,
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
            print('ERROR: failed to get peers, exiting...')
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
