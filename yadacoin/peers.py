import json
import requests
from time import time
from random import choice
from tornado import ioloop
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from asyncio import sleep as async_sleep, gather
from pymongo import ASCENDING, DESCENDING
from logging import getLogger

from yadacoin.config import get_config
from yadacoin.yadawebsocketclient import YadaWebSocketClient


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
        self.outbound = {}  # a dict of outbound streams, keys are ips
        self.connected_ips = []  # a list of peers ip we're connected to
        # I chose to have 2 indexs and more memory footprint rather than iterating over one to get the other.
        self.probable_old_nodes = {}  # dict : keys are ip, value time when to delete from list
        self.syncing = False
        my_peer = self.mongo.db.config.find_one({'mypeer': {"$ne": ""}})
        if my_peer:
            self.my_peer = my_peer.get('mypeer')  # str
        self.app_log.debug(self.my_peer)

    def init_local(self):
        raise RuntimeError("Peers, init_local is deprecated")
        return '[]'

        self.my_peer = self.mongo.db.config.find_one({'mypeer': {"$ne": ""}}).get('mypeer')
        res = self.mongo.db.peers.find({'active': True, 'failed': {'$lt': 300}}, {'_id': 0})
        try:
            # Do not include ourselve in the list
            self.peers = [Peer(peer['host'], peer['port']) for peer in res if peer['host'] not in self.config.outgoing_blacklist]
        except:
            pass
        return self.to_json()

    def get_status(self):
        """Returns peers status as explicit dict"""
        # TODO: cache?
        status = {"inbound": len(self.inbound), "outbound": len(self.outbound)}
        if self.config.extended_status:
            # print(self.inbound)
            status['inbound_detail'] = [peer['ip'] for sid, peer in self.inbound.items()]
            status['outbound_detail'] = list(self.outbound.keys())
            status['probable_old_nodes'] = self.probable_old_nodes
            status['connected_ips'] = self.connected_ips
            # TODO: too many conversions from/to object and string
            status['peers'] = [peer.to_string() for peer in self.peers]
        return status

    @property
    def free_inbound_slots(self):
        """How many free inbound slots we have"""
        return self.config.max_inbound - len(self.inbound)

    @property
    def free_outbound_slots(self):
        """How many free outbound slots we have"""
        return self.config.max_outbound - len(self.outbound)

    def potential_outbound_peers(self):
        """List the working peers we know, we are not yet connected to"""
        now = time()
        # remove after timeout
        self.probable_old_nodes = {key: delete_at
                                   for key, delete_at in self.probable_old_nodes.items()
                                   if delete_at > now}
        return [peer for peer in self.peers
                if peer.host not in self.connected_ips
                and peer.host not in self.probable_old_nodes
                and peer.host not in self.config.outgoing_blacklist]

    def allow_ip(self, IP):
        """Returns True if that ip can connect - inbound or outbound"""
        # TODO - add blacklist
        # TODO: if verbose, say why
        print(self.connected_ips)
        return IP not in self.connected_ips  # Allows if we're not connected already.

    def on_new_ip(self, ip):
        """We got an inbound or initiate an outbound connection from/to an ip, but do not have the result yet.
        avoid initiating one connection twice if the handshake does not go fast enough."""
        self.app_log.info("on_new_ip:{}".format(ip))
        if ip not in self.connected_ips:
            self.connected_ips.append(ip)

    def on_lost_ip(self, ip):
        """Remove an ip that was not registered as outgoing or ingoing yet"""
        self.app_log.info("on_lost_ip:{}".format(ip))
        self.connected_ips.remove(ip)

    async def on_new_inbound(self, ip:str, port:int, version, sid):
        """Inbound peer provided a correct version and ip, add it to our pool"""
        self.app_log.info("on_new_inbound {}:{} {}".format(ip, port, version))
        if ip not in self.connected_ips:
            self.connected_ips.append(ip)
        # TODO: maybe version is not to be stored, then we could only store ip:port as string to avoid dict overhead.
        self.inbound[sid] = {"ip":ip, "port":port, "version": version}
        # maybe it's an ip we don't have yet, add it
        await self.on_new_peer_list([{'host': ip, 'port': port}])

    async def on_close_inbound(self, sid, ip=''):
        # If the peer was fully connected, then it'in inbound.
        # If not, we have no full info, but an ip optional field.
        self.app_log.info("on_close_inbound {} - ip {}".format(sid, ip))
        info = self.inbound.pop(sid, None)
        try:
            stored_ip = info['ip']
            self.connected_ips.remove(stored_ip)
        except:
            pass
        if ip:
            self.connected_ips.remove(ip)

    def on_new_outbound(self, ip, port, client):
        """Outbound peer connection was successful, add it to our pool"""
        self.app_log.info("on_new_outbound {}:{}".format(ip, port))
        if ip not in self.connected_ips:
            self.connected_ips.append(ip)
        self.outbound[ip] = {"ip":ip, "port":port, "client": client}

    def on_close_outbound(self, ip):
        # We only allow one in or out per ip
        self.app_log.info("on_close_outbound {}".format(ip))
        self.outbound.pop(ip, None)
        self.connected_ips.remove(ip)

    async def check_outgoing(self):
        """Called by a background task.
        Counts the current active outgoing connections, and tries to connect to more if needed"""
        if len(self.peers) < 2:
            await self.refresh()
        if self.free_outbound_slots <= 0:
            return
        targets = self.potential_outbound_peers()
        if len(targets) <= 0:
            return
        peer = choice(targets)  # random peer from the available - and tested - pool
        # Try to connect. We create a background co-routine that will handle the client side.
        ioloop.IOLoop.instance().add_callback(self.background_peer, peer)

    async def background_peer(self, peer):
        self.app_log.debug("Peers background_peer {}".format(peer.to_dict()))
        # lock that ip
        self.on_new_ip(peer.host)
        client = None
        try:
            peer.client = YadaWebSocketClient(peer)
            # This will run until disconnect
            await peer.client.start()
        except Exception as e:
            self.app_log.warning("Error: {} on background_peer {}".format(e, peer.host))
        finally:
            # If we get here with no outbound record, then it was an old node.
            #if peer.host not in self.outbound:
            if peer.client and peer.client.probable_old:
                # add it to a temp "do not try ws soon" list
                self.app_log.debug("Peer {} added to probable_old_nodes".format(peer.host))
                self.probable_old_nodes[peer.host] = int(time()) + 3600  # try again in 1 hour
            self.on_close_outbound(peer.host)

    async def on_block_insert(self, block_data: dict):
        """This is what triggers the event to all connected ws peers, in or outgoing"""
        # outgoing
        self.app_log.debug("Block Insert event index {}".format(block_data['index']))
        # Update the miners (/pool http route) is done via latest_block => move to event to MiningPool stored by config
        if self.config.mp:
            await self.config.mp.refresh(block_data)
            # Update the miners (websockets)
            await self.config.SIO.emit('header', data=await self.config.mp.block_to_mine_info(), namespace='/pool')
        # TODO: start all async at once then await gather to spare some delay
        for ip, outgoing in self.outbound.items():
            try:
                await outgoing['client'].emit("latest_block", data=block_data, namespace="/chat")
            except Exception as e:
                self.app_log.warning("Error {} notifying outgoing {}".format(e, ip))
        # ingoing
        try:
            await self.config.SIO.emit("latest_block", data=block_data, namespace="/chat")
        except Exception as e:
            self.app_log.warning("Error {} notifying ws clients".format(e))

    async def refresh(self):
        """Refresh the in-memory peer list from db and api. Only contains Active peers"""
        self.app_log.info("Async Peers refresh")
        if self.network == 'regnet':
            peer = await self.mongo.async_db.config.find_one({
                # 'mypeer': {"$ne": ""},
                'mypeer': {'$exists': True}
            })
            if not peer:
                return
            # Insert ourself to have at least one peer. Not sure this is required, but allows for more tests coverage.
            self.peers=[Peer(self.config.serve_host, self.config.serve_port,
                             peer.get('bulletin_secret'))]
            return
        url = 'https://yadacoin.io/peers'  # Default value
        if self.network == 'testnet':
            url = 'https://yadacoin.io:444/peers'

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

            test_after = int(time())  # new peers will be tested asap.
            if len(self.config.peers_seed):
                # add from our config file
                await self.on_new_peer_list(self.config.peers_seed, test_after)
            else:
                self.app_log.warning("No seed.json with config?")
                # or from central yadacoin.io if none
                http_client = AsyncHTTPClient()
                try:
                    response = await http_client.fetch(url)
                    seeds = json.loads(response.body.decode('utf-8'))['get-peers']
                    if len(seeds['peers']) <= 0:
                        self.app_log.warning("No peers on main yadacoin.io node")
                    await self.on_new_peer_list(seeds['peers'], test_after)
                except Exception as e:
                    self.app_log.warning("Error: {} on url {}".format(e, url))
            await self.mongo.async_db.config.replace_one({"last_seeded": {"$exists": True}}, {"last_seeded": str(test_after)}, upsert=True)
            # self.mongo.db.config.update({'last_seeded': {"$ne": ""}}, {'last_seeded': str(test_after)}, upsert=True)

        # todo: probly more efficient not to rebuild the objects every time
        self.peers = [Peer(peer['host'], peer['port']) for peer in res]
        self.app_log.debug("Peers count {}".format(len(self.peers)))

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

    async def increment_failed(self, peer):
        res = await self.mongo.async_db.peers.find_one({'host': peer.host, 'port': int(peer.port)})
        failed = res.get('failed', 0) + 1
        factor = failed
        if failed > 20:
            factor = 240  # at most, test every 4 hours
        elif failed > 10:
            factor = 6 * factor
        elif failed > 5:
            factor = 2 * factor
        test_after = int(time()) + factor * 60  #
        await self.mongo.async_db.peers.update_one({'host': peer.host, 'port': int(peer.port)},
                                                   {'$set': {'active': False, "test_after": test_after,
                                                             "failed": failed}})
        # remove from in memory list
        self.peers = [apeer for apeer in self.peers if apeer.host != peer.host]

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
    __slots__ = ('config', 'mongo', 'host', 'port', 'bulletin_secret', 'is_me', 'app_log', 'stream', 'inbound', 'sid', 'client')

    def __init__(self, host, port, bulletin_secret=None, is_me=False, stream=None, inbound=False, sid=None):
        self.config = get_config()
        self.mongo = self.config.mongo
        self.client = None
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
                url = 'https://yadacoin.io:444/peers'
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
        peer = config.peer_host + ":" + str(config.peer_port)
        config.mongo.db.config.update({'mypeer': {"$ne": ""}}, {'mypeer': peer, 'network': config.network}, upsert=True)
        
        if config.network == 'regnet':
            return
        if not config.post_peer:
            return
        if config.debug:
            # Do not report debug nodes
            return
        url = 'https://yadacoin.io/peers'  # default url
        if network == 'testnet':
            url = 'https://yadacoin.io:444/peers'
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
        url = "http://{}/get-latest-block".format(hp)
        request = HTTPRequest(url, connect_timeout=10, request_timeout=12)
        # TODO: move to get-status
        try:
            response = await http_client.fetch(request)
            if response.code != 200:
                raise RuntimeWarning('code {}'.format(response.code))
            # TODO: we got the status, we could run more logic here (depending on peer count, version, uptime, height)
            await self.mongo.async_db.peers.update_one({'host': self.host, 'port': int(self.port)}, {'$set': {'active': True, "failed":0}})
            #  get peers from that node and merge.
            http_client = AsyncHTTPClient()
            test_after = int(time()) + 30  # 2nd layer peers will be tested after 1st layer
            # This "get peers from url" is used twice, could be factorized.
            # But could be deprecated soon with websockets.
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
            print("Error: {} on test url {}".format(e, url))
            # store error and next try - factorized code. not sure test() should be in peer itself, rather peers.
            await self.config.peers.increment_failed(self)
            """
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
            """
            return False
        return True
