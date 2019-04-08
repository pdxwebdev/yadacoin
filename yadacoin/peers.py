import json
import requests
from time import time
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from asyncio import sleep as async_sleep, gather
from pymongo import ASCENDING, DESCENDING
from logging import getLogger

from yadacoin.config import get_config


class Peers(object):
    """A Peer manager Class."""

    peers = []
    # peers_json = ''

    def __init__(self):
        self.config = get_config()
        self.mongo = self.config.mongo
        self.network = self.config.network
        self.my_peer = None
        self.app_log = getLogger("tornado.application")
        self.inbound = {}  # a dict of inbound streams, keys are sids
        self.outbound = {}  # a dict of outbound streams, keys are sids
        self.connected_ips = []  # a list of peers ip we're connected to

    def init_local(self):
        raise RuntimeError("Peers, init_local is deprecated")
        return '[]'

        self.my_peer = self.mongo.db.config.find_one({'mypeer': {"$ne": ""}}).get('mypeer')
        res = self.mongo.db.peers.find({'active': True, 'failed': {'$lt': 300}}, {'_id': 0})
        try:
            self.peers = [Peer(peer['host'], peer['port']) for peer in res]
        except:
            pass
        return self.to_json()

    def get_status(self):
        """Returns peers status as explicit dict"""
        # TODO: cache?
        status = {"inbound": len(self.inbound), "outbound": len(self.outbound)}
        return status

    @property
    def free_inbound_slots(self):
        """How many free inbound slots we have"""
        return self.config.max_inbound - len(self.inbound)

    def allow_ip(self, IP):
        """Returns True if that ip can connect - inbound or outbound"""
        # TODO - add blacklist
        # TODO: if verbose, say why
        return IP not in self.connected_ips  # Allows if we're not connected already.

    def on_new_ip(self, ip):
        """We got an inbound or initiate an outbound connection from/to an ip, buit do not have the result yet.
        avoid initiating one connection twice if the handshake does not go fast enough."""
        self.app_log.info("on_new_ip:{}".format(ip))
        if ip not in self.connected_ips:
            self.connected_ips.append(ip)

    async def on_new_inbound(self, ip:str, port:int, version, sid):
        """Inbound peer provided a correct version and ip, add it to our pool"""
        self.app_log.info("on_new_inbound {}:{} {}".format(ip, port, version))
        if ip not in self.connected_ips:
            self.connected_ips.append(ip)
        # TODO: maybe version is not to be stored, then we could only store ip:port as string to avoid dict overhead.
        self.inbound[sid] = {"ip":ip, "port":port, "version": version}
        # maybe it's an ip we don't have yet, add it
        await self.on_new_peer_list([{'host': ip, 'port': port}])

    async def on_close_inbound(self, sid):
        # We only allow one in or out per ip
        self.app_log.info("on_close_inbound {}".format(sid))
        info = self.inbound.pop(sid, None)
        ip = info['ip']
        self.connected_ips.remove(ip)

    def on_new_outbound(self, ip, port, version, sid):
        """Outbound peer connection was sucessful, add it to our pool"""
        self.app_log.info("on_new_outbound {}:{} {}".format(ip, port, version))
        if ip not in self.connected_ips:
            self.connected_ips.append(ip)
        # TODO: maybe version is not to be stored, then we could only store ip:port as string to avoid dict overhead.
        self.outbound[sid] = {"ip":ip, "port":port, "version": version}

    def on_close_outbound(self, sid):
        # We only allow one in or out per ip
        self.app_log.info("on_close_outbound {}".format(sid))
        info = self.outbound.pop(sid, None)
        ip = info['ip']
        self.connected_ips.remove(ip)

    async def refresh(self):
        """Refresh the in-memory peer list from db and api. Only contains Active peers"""
        self.app_log.info("Async Peers refresh")
        if self.network == 'regnet':
            peer = await self.mongo.async_db.config.find_one({'mypeer': {"$ne": ""}})
            if not peer:
                return
            # Insert ourself to have at least one peer. Not sure this is required, but allows for more tests coverage.
            self.peers=[Peer(self.config.serve_host, self.config.serve_port,
                             peer.get('bulletin_secret'))]
            return
        url = 'https://yadacoin.io/peers'  # Default value
        if self.network == 'testnet':
            url = 'http://yadacoin.io:8888/peers'

        res = await self.mongo.async_db.peers.find({'active': True, 'net':self.network}, {'_id': 0}).to_list(length=100)
        if len(res) <= 0:
            # Our local db gives no match, get from seed list if we did not just now
            last_seeded = await self.mongo.async_db.config.find_one({'last_seeded': {"$exists": True}})
            # print(last_seeded)
            try:
                if last_seeded and int(last_seeded['last_seeded']) + 60 * 10 > time():
                    # 10 min mini between seed requests
                    self.app_log.info('Too soon, waiting for seed...')
                    return
            except Exception as e:
                self.app_log.error("Error: {} last_seeded".format(e))

            http_client = AsyncHTTPClient()
            test_after = int(time())  # new peers will be tested asap.
            try:
                response = await http_client.fetch(url)
                seeds = json.loads(response.body.decode('utf-8'))['peers']
                await self.on_new_peer_list(seeds, test_after)
            except Exception as e:
                self.app_log.warning("Error: {} on url {}".format(e, url))
            await self.mongo.async_db.config.replace_one({"last_seeded": {"$exists": True}}, {"last_seeded": str(test_after)}, upsert=True)
            # self.mongo.db.config.update({'last_seeded': {"$ne": ""}}, {'last_seeded': str(test_after)}, upsert=True)

        # todo: probly more efficient not to rebuild the objects every time
        self.peers = [Peer(peer['host'], peer['port']) for peer in res]

    async def on_new_peer_list(self, peer_list: list, test_after=None):
        """Process an external peer list, and saves the new ones"""
        if test_after is None:
            test_after = int(time())  # new peers will be tested asap.
        for peer in peer_list:
            res = await self.mongo.async_db.peers.count_documents({'host': peer['host'], 'port': peer['port']})
            if res > 0:
                # We know him already, so it will be tested.
               self.app_log.debug('Known peer {}:{}'.format(peer['host'], peer['port']))
            else:
                await self.mongo.async_db.peers.insert_one({
                    'host': peer['host'], 'port': peer['port'], 'net': self.network,
                    'active': False, 'failed': 0, 'test_after': test_after})
                # print('Inserted')
                self.app_log.debug("Inserted new peer {}:{}".format(peer['host'], peer['port']))

    async def test_some(self, count=1):
        """Tests count peers from our base, by priority"""
        try:
            res = self.mongo.async_db.peers.find({'active': False, 'net': self.network, 'test_after': {"$lte": int(time())}}).sort('test_after', ASCENDING).limit(count)
            to_test = []
            async for a_peer in res:
                peer = Peer(a_peer['host'], a_peer['port'])
                # print("Testing", peer)
                to_test.append(peer.test())
            res = await gather(*to_test)
            # print('res', res)
        except Exception as e:
            self.app_log.warning("Error: {} on test_some".format(e))
        # to_list(length=100)

    @classmethod
    def from_dict(cls):
        raise RuntimeError("Peers, from_dict is deprecated")
        """
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
        """

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

    # slots allow to lower ram usage for objects with many instances
    __slots__ = ('config', 'mongo', 'host', 'port', 'bulletin_secret', 'is_me', 'app_log', 'stream', 'inbound', 'sid')

    def __init__(self, host, port, bulletin_secret=None, is_me=False, stream=None, inbound=False, sid=None):
        self.config = get_config()
        self.mongo = self.config.mongo
        self.host = host
        self.port = port
        self.bulletin_secret = bulletin_secret
        self.is_me = is_me
        self.app_log = getLogger("tornado.application")
        self.stream = stream  # for async http
        self.inbound = inbound  # Is this an inbound connection? If it is, we can't rely on the port.
        self.sid = sid  # This is the websocket session id

    @classmethod
    def from_string(cls, peerstr):
        if ":" in peerstr:
            peer = peerstr.split(':')
            return cls(peer[0], peer[1])
        elif peerstr == 'me':
            return cls(None, None, is_me=True)

    def report(self):
        raise RuntimeError("Peers, report is deprecated")
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
        raise RuntimeError("Peers, is_broken is deprecated")
        broken_test = [x for x in self.mongo.db.broken_peers.find({"peer": self.to_string()})]
        return broken_test and broken_test[0]['broken']

    def set_broken(self):
        raise RuntimeError("Peers, set_broken is deprecated")
        self.mongo.db.broken_peers.update({"peer": self.to_string()}, {"peer": self.to_string(), "broken": True}, upsert=True)

    def unset_broken(self):
        raise RuntimeError("Peers, unset_broken is deprecated")
        self.mongo.db.broken_peers.update({"peer": self.to_string()}, {"peer": self.to_string(), "broken": False}, upsert=True)

    @classmethod
    def init_my_peer(cls, network):
        config = get_config()
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

        cls.save_my_peer(network)
        return cls(config.peer_host, config.peer_port)
    
    @classmethod
    def save_my_peer(cls, network):
        config = get_config()
        if config.network == 'regnet':
            return
        peer = config.peer_host + ":" + str(config.peer_port)
        config.mongo.db.config.update({'mypeer': {"$ne": ""}}, {'mypeer': peer, 'network': config.network}, upsert=True)
        if not config.post_peer:
            return
        if config.debug:
            # Do not report debug nodes
            return
        url = 'https://yadacoin.io/peers'  # default url
        if network == 'testnet':
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
        except:  # TODO: catch specific exception
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

    async def test(self):
        hp = self.to_string()
        print('test', hp)
        http_client = AsyncHTTPClient()
        request = HTTPRequest("http://{}".format(hp), connect_timeout=10, request_timeout=12)
        try:
            response = await http_client.fetch(request)
            if response.code != 200:
                raise RuntimeWarning('code {}'.format(response.code))
            await self.mongo.async_db.peers.update_one({'host': self.host, 'port': int(self.port)}, {'$set': {'active': True, "failed":0}})
            #  get peers from that node and merge.
            http_client = AsyncHTTPClient()
            test_after = int(time()) + 30  # 2nd layer peers will be tested after 1st layer
            # This "get peers from url" is used twice, could be factorized. But could be deprecated soon with websockets.
            url = "http://{}/get-peers".format(hp)
            try:
                response = await http_client.fetch(url)
                if response.code != 200:
                    # Not available or too old a version, just ignore.
                    return
                seeds = json.loads(response.body.decode('utf-8'))['peers']
                await self.config.peers.on_new_peer_list(seeds, test_after)
            except Exception as e:
                self.app_log.warning("Error: {} on url {}".format(e, url))
        except Exception as e:
            # print("Error: {} on url {}".format(e, hp))
            # store error and next try
            res = await self.mongo.async_db.peers.find_one({'host': self.host, 'port': int(self.port)})
            failed = res['failed'] + 1
            factor = failed
            if failed > 20:
                factor = 240  # at most, test every 4 hours
            elif failed > 10:
                factor = 6 * factor
            elif failed > 5:
                factor = 2 * factor
            test_after = int(time()) + factor * 60  #
            await self.mongo.async_db.peers.update_one({'host': self.host, 'port': int(self.port)},
                                                       {'$set': {'active': False, "test_after": test_after,
                                                                 "failed": failed}})
            return False
        return True
