import json
from time import time
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from asyncio import sleep as async_sleep, gather
from pymongo import ASCENDING, DESCENDING


class Peers(object):
    """A Peer manager Class."""

    peers = []
    # peers_json = ''

    def __init__(self, config, mongo):
        self.config = config
        self.mongo = mongo
        self.network = config.network
        self.my_peer = None

    def init_local(self):
        raise RuntimeError("Peers, init_local is deprecated")
        return '[]'

        self.my_peer = self.mongo.db.config.find_one({'mypeer': {"$ne": ""}}).get('mypeer')
        res = self.mongo.db.peers.find({'active': True, 'failed': {'$lt': 300}}, {'_id': 0})
        try:
            self.peers = [Peer(self.config, self.mongo, peer['host'], peer['port']) for peer in res]
        except:
            pass
        return self.to_json()

    async def refresh(self):
        """Refresh the in-memory peer list from db and api. Only contains Active peers"""
        print("Async Peers refresh")
        if self.network == 'regnet':
            peer = await self.mongo.async_db.config.find_one({'mypeer': {"$ne": ""}})
            if not peer:
                return
            # Insert ourself to have at least one peer. Not sure this is required, but allows for more tests coverage.
            self.peers=[Peer(self.config, self.mongo,
                             self.config.serve_host, self.config.serve_port,
                             peer.get('bulletin_secret'))]
            return
        if self.network == 'mainnet':
            url = 'https://yadacoin.io/peers'
        elif self.network == 'testnet':
            url = 'http://yadacoin.io:8888/peers'

        res = await self.mongo.async_db.peers.find({'active': True, 'net':self.network}, {'_id': 0}).to_list(length=100)
        if len(res) <= 0:
            # Our local db gives no match, get from seed list if we did not just now
            last_seeded = await self.mongo.async_db.config.find_one({'last_seeded': {"$exists": True}})
            # print(last_seeded)
            try:
                if last_seeded and int(last_seeded['last_seeded']) + 60 * 10 > time():
                    # 10 min mini between seed requests
                    print('Too soon, waiting for seed')
                    return
            except Exception as e:
                print("Error: {} last_seeded".format(e))

            http_client = AsyncHTTPClient()
            test_after = int(time())  # new peers will be tested asap.
            try:
                response = await http_client.fetch(url)
                seeds = json.loads(response.body.decode('utf-8'))['peers']
                for peer in seeds:
                    res = await self.mongo.async_db.peers.count_documents({'host': peer['host'], 'port': peer['port']})
                    if res > 0:
                        # We know him already, so it will be tested.
                        print('Known')
                        pass
                    else:
                        await self.mongo.async_db.peers.insert_one({
                            'host': peer['host'], 'port': peer['port'], 'net':self.network,
                            'active': False, 'failed': 0, 'test_after': test_after})
                        print('Inserted')
            except Exception as e:
                print("Error: {} on url {}".format(e, url))
            await self.mongo.async_db.config.replace_one({"last_seeded": {"$exists": True}}, {"last_seeded": str(test_after)}, upsert=True)
            # self.mongo.db.config.update({'last_seeded': {"$ne": ""}}, {'last_seeded': str(test_after)}, upsert=True)

        # todo: probly more efficient not to rebuild the objects every time
        self.peers = [Peer(self.config, self.mongo, peer['host'], peer['port']) for peer in res]

    async def test_some(self, count=1):
        """Tests count peers from our base, by priority"""
        try:
            res = self.mongo.async_db.peers.find({'active': False, 'net': self.network, 'test_after': {"$lte": int(time())}}).sort('test_after', ASCENDING).limit(count)
            to_test = []
            async for a_peer in res:
                peer = Peer(self.config, self.mongo, a_peer['host'], a_peer['port'])
                # print("Testing", peer)
                to_test.append(peer.test())
            res = await gather(*to_test)
            print('res', res)
        except Exception as e:
            print("Error: {} on test_some".format(e))
        # to_list(length=100)

    @classmethod
    def from_dict(cls, config, mongo):
        raise RuntimeError("Peers, from_dict is deprecated")
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
    """An individual Peer object"""

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
        if config.use_pnp:
            import socket
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
        peer = config.peer_host + ":" + str(config.peer_port)
        mongo.db.config.update({'mypeer': {"$ne": ""}}, {'mypeer': peer, 'network': config.network}, upsert=True)
        if not config.post_peer:
            return
        """
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
        """

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

    async def test(self):
        hp =  self.to_string()
        print('test', hp)
        http_client = AsyncHTTPClient()
        request = HTTPRequest("http://{}".format(hp), connect_timeout=10, request_timeout=12)
        try:
            response = await http_client.fetch(request)
            if response.code != 200:
                raise RuntimeWarning('code {}'.format(response.code))
            # TODO: store OK
            await self.mongo.async_db.peers.update_one({'host': self.host, 'port': int(self.port)}, {'$set': {'active': True, "failed":0}})
        except Exception as e:
            print("Error: {} on url {}".format(e, hp))
            # TODO: store error and next try

            return("KO " + hp)
        return("OK " + hp)
