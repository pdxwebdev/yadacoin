import json
import hashlib
import time
from collections import OrderedDict
from logging import getLogger

from yadacoin.core.config import get_config
from yadacoin.core.identity import Identity
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.transaction import Transaction


class Peer:
    id_attribute = 'rid'
    """An individual Peer object"""
    epoch = 1602914018
    ttl = 259200

    def __init__(self, host=None, port=None, identity=None, seed=None, seed_gateway=None):
        self.host = host
        self.port = port
        self.identity = identity
        self.seed = seed
        self.seed_gateway = seed_gateway
        self.config = get_config()
        self.app_log = getLogger("tornado.application")
    
    @classmethod
    def from_dict(cls, peer, is_me=False):
        inst = cls(
            peer['host'],
            peer['port'],
            Identity.from_dict(peer['identity']),
            seed=peer.get('seed'),
            seed_gateway=peer.get('seed_gateway')
        )
        return inst
    
    @property
    def rid(self):
        if hasattr(self.config, 'peer'):
            return self.identity.generate_rid(self.config.peer.identity.username_signature)

    @classmethod
    def create_upnp_mapping(cls, config):
        from miniupnpc import UPnP
        config = get_config()
        try:
            u = UPnP(None, None, 200, 0)
            u.discover()
            config.igd = u.selectigd()
        except:
            config.igd = ""
        if config.use_pnp:
            import socket
            # deploy as an eventlet WSGI server
            try:
                server_port = config.peer_port
                eport = server_port
                r = u.getspecificportmapping(eport, 'TCP')
                if r:
                    u.deleteportmapping(eport, 'TCP')
                u.addportmapping(eport, 'TCP', u.lanaddr, server_port, 'UPnP YadaCoin Serve port %u' % eport, '')
                config.peer_host = u.externalipaddress()

                if 'web' in config.modes:
                    server_port = config.serve_port
                    eport = server_port
                    r = u.getspecificportmapping(eport, 'TCP')
                    if r:
                        u.deleteportmapping(eport, 'TCP')
                    u.addportmapping(eport, 'TCP', u.lanaddr, server_port, 'UPnP YadaCoin Serve port %u' % eport, '')
            except Exception as e:
                print(e)
                config.serve_host = config.serve_host
                config.serve_port = config.serve_port
                config.peer_host = config.peer_host
                config.peer_port = config.peer_port
                print('UPnP failed: you must forward and/or whitelist port', config.peer_port)

    @classmethod
    def type_limit(cls, peer):
        raise NotImplementedError()

    async def get_outbound_class(self):
        raise NotImplementedError()

    async def get_inbound_class(self):
        raise NotImplementedError()

    async def get_outbound_peers(self):
        raise NotImplementedError()

    async def calculate_seed_gateway(self, nonce=None):
        if self.__class__ not in [Group, ServiceProvider]:
            raise Exception('Should not calculate a seed gateway for anything other than groups or service providers')
        username_signature_hash = hashlib.sha256(self.identity.username_signature.encode()).hexdigest()
        # TODO: introduce some kind of unpredictability here. This uses the latest block hash. 
        # So we won't be able to get the new seed without the block hash
        # which is not known in advance
        seed_time = int((time.time() - self.epoch) / self.ttl) + 1
        seed_select = (int(username_signature_hash, 16) * seed_time) % len(self.config.seed_gateways)
        username_signatures = list(self.config.seed_gateways)
        first_number = seed_select
        num_reset = False
        while self.config.seed_gateways[username_signatures[seed_select]].rid in self.config.nodeClient.outbound_ignore[SeedGateway.__name__]:
            seed_select += 1
            if num_reset and seed_select >= first_number:
                break # failed to find a seed gateway
            if seed_select >= len(self.config.seed_gateways) + 1:
                if first_number > 0:
                    seed_select = 0
                

        seed_gateway = self.config.seed_gateways[list(self.config.seed_gateways)[seed_select]]
        return seed_gateway
    
    async def ensure_peers_connected(self):
        peers = await self.get_outbound_peers()
        outbound_class = await self.get_outbound_class()
        limit = self.__class__.type_limit(outbound_class)
        stream_collection = {**self.config.nodeClient.outbound_streams[outbound_class.__name__], **self.config.nodeClient.outbound_pending[outbound_class.__name__]}
        await self.connect(stream_collection, limit, peers)

    async def connect(self, stream_collection, limit, peers):
        if limit and len(stream_collection) < limit:
            for peer in set(peers) - set(stream_collection): # only connect to seed nodes
                await self.config.nodeClient.connect(peers[peer])

    def to_dict(self):
        return {
            'host': self.host,
            'port': self.port,
            'identity': self.identity.to_dict,
            'rid': self.rid,
            'seed': self.seed,
            'seed_gateway': self.seed_gateway
        }

    def to_string(self):
        return '{}:{}'.format(self.host, self.port)
    
    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)
    
    async def get_payload_txn(self, payload):
        txn = None
        if payload.get('transaction'):
            txn = Transaction.from_dict(payload.get('transaction'))
        return txn


class Seed(Peer):
    id_attribute = 'rid'
    source_property = 'source_seed'
    async def get_outbound_class(self):
        return Seed

    async def get_inbound_class(self):
        return SeedGateway

    async def get_outbound_peers(self):
        return self.config.seeds

    @classmethod
    def type_limit(cls, peer):
        if peer == Seed:
            return 100000
        elif peer == SeedGateway:
            return 1
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [Seed, SeedGateway]
    
    async def get_route_peers(self, peer, payload):
        if isinstance(peer, SeedGateway):
            # this if statement allow bi-directional communication cross-seed
            if self.source_property in payload:
                # this is a response
                bridge_seed = self.config.seeds[payload[self.source_property]]
            else:
                # this must be the identity of the destination service provider
                # the message originator must provide the necissary service provider identity information
                # typically, the originator will grab all mutual service providers of the originator and the recipient of the message
                # and send "through" every service provider so the recipient will receive the message on all services

                peer = Peer.from_dict(payload.get('dest_service_provider'))
                bridge_seed_gateway = await peer.calculate_seed_gateway() # get the seed gateway
                bridge_seed = bridge_seed_gateway.seed
                payload[self.source_property] = self.config.peer.identity.username_signature
            if bridge_seed.rid in self.config.nodeServer.inbound_streams[Seed.__name__]:
                peer_stream = self.config.nodeServer.inbound_streams[Seed.__name__][bridge_seed.rid]
            elif bridge_seed.rid in self.config.nodeClient.outbound_streams[Seed.__name__]:
                peer_stream = self.config.nodeClient.outbound_streams[Seed.__name__][bridge_seed.rid]
            else:
                self.config.app_log.error('No bridge seed found. Cannot route transaction.')
            yield peer_stream
        elif isinstance(peer, Seed):
            for rid, peer_stream in self.config.nodeServer.inbound_streams[SeedGateway.__name__].items():
                yield peer_stream
            for rid, peer_stream in self.config.nodeClient.outbound_streams[Seed.__name__].items():
                yield peer_stream
    
    async def get_service_provider_request_peers(self, peer, payload):
        if isinstance(peer, SeedGateway):
            # this if statement allow bi-directional communication cross-seed
            if self.source_property in payload:
                # this is a response
                bridge_seed_from_payload = Peer.from_dict(payload[self.source_property])
                bridge_seed = self.config.seeds[bridge_seed_from_payload.identity.username_signature]
            else:
                # this must be the identity of the destination service provider
                # the message originator must provide the necissary service provider identity information
                # typically, the originator will grab all mutual service providers of the originator and the recipient of the message
                # and send "through" every service provider so the recipient will receive the message on all services

                bridge_seed_gateway = Peer.from_dict(payload.get('seed_gateway'))
                bridge_seed = self.config.seeds[
                    self.config.seed_gateways[bridge_seed_gateway.identity.username_signature].seed
                ]
                payload[self.source_property] = self.config.peer.identity.username_signature
            if bridge_seed.rid in self.config.nodeServer.inbound_streams[Seed.__name__]:
                peer_stream = self.config.nodeServer.inbound_streams[Seed.__name__][bridge_seed.rid]
            elif bridge_seed.rid in self.config.nodeClient.outbound_streams[Seed.__name__]:
                peer_stream = self.config.nodeClient.outbound_streams[Seed.__name__][bridge_seed.rid]
            else:
                self.config.app_log.error('No bridge seed found. Cannot route transaction.')
            yield peer_stream
        elif isinstance(peer, Seed):
            for rid, peer_stream in self.config.nodeServer.inbound_streams[SeedGateway.__name__].items():
                yield peer_stream

    async def get_sync_peers(self):
        for x, y in self.config.nodeServer.inbound_streams[SeedGateway.__name__].items():
            yield y

        for x, y in self.config.nodeServer.inbound_streams[Seed.__name__].items():
            yield y

        for x, y in self.config.nodeClient.outbound_streams[Seed.__name__].items():
            yield y


class SeedGateway(Peer):
    id_attribute = 'rid'
    source_property = 'source_seed_gateway'
    async def get_outbound_class(self):
        return Seed

    async def get_inbound_class(self):
        return ServiceProvider

    async def get_outbound_peers(self):
        return {self.config.seeds[self.seed].identity.username_signature: self.config.seeds[self.seed]}

    @classmethod
    def type_limit(cls, peer):
        if peer == Seed:
            return 1
        elif peer == ServiceProvider:
            return 100000
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [Seed, ServiceProvider]
    
    async def get_route_peers(self, peer, payload):
        if isinstance(peer, Seed):
            for rid, peer_stream in self.config.nodeServer.inbound_streams[ServiceProvider.__name__].items():
                yield peer_stream
        elif isinstance(peer, ServiceProvider):
            for rid, peer_stream in self.config.nodeClient.outbound_streams[Seed.__name__].items():
                yield peer_stream
    
    async def get_service_provider_request_peers(self, peer, payload):
        if isinstance(peer, Seed):
            for rid, peer_stream in self.config.nodeServer.inbound_streams[ServiceProvider.__name__].items():
                yield peer_stream
        elif isinstance(peer, ServiceProvider):
            for rid, peer_stream in self.config.nodeClient.outbound_streams[Seed.__name__].items():
                yield peer_stream

    async def get_sync_peers(self):
        for x, y in self.config.nodeServer.inbound_streams[ServiceProvider.__name__].items():
            yield y

        for x, y in self.config.nodeClient.outbound_streams[Seed.__name__].items():
            yield y


class ServiceProvider(Peer):
    id_attribute = 'rid'
    source_property = 'source_service_provider'

    async def get_outbound_class(self):
        return SeedGateway

    async def get_inbound_class(self):
        return User

    async def get_outbound_peers(self, nonce=None):
        seed_gateway = await self.calculate_seed_gateway()
        return {seed_gateway.identity.username_signature: seed_gateway}

    @classmethod
    def type_limit(cls, peer):
        if peer == SeedGateway:
            return 1
        elif peer == User:
            return 100000
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [ServiceProvider, User]
    
    async def get_route_peers(self, peer, payload):

        if isinstance(peer, User):
            for rid, peer_stream in self.config.nodeClient.outbound_streams[SeedGateway.__name__].items():
                yield peer_stream

            for rid, peer_stream in self.config.websocketServer.inbound_streams.items():
                if peer.identity.username_signature == peer_stream.peer.identity.username_signature:
                    continue
                yield peer_stream
        
        elif isinstance(peer, SeedGateway):
            txn = self.get_payload_txn(payload)
            if txn:
                txn_sum = sum([x.value for x in txn.outputs])

                if not peer and not txn_sum:
                    self.config.app_log.error('Zero sum transaction and no routing information. Cannot route transaction.')
                    return

                from_peer = None
                if payload.get('from_peer'):
                    from_peer = Identity.from_dict(payload.get('from_peer'))

                rid = None
                if txn.requester_rid in self.config.nodeServer.inbound_streams[User.__name__]:
                    rid = txn.requester_rid
                elif txn.requested_rid in self.config.nodeServer.inbound_streams[User.__name__]:
                    rid = txn.requested_rid
                elif from_peer and from_peer in self.config.nodeServer.inbound_streams[User.__name__]:
                    rid = from_peer.rid
                else:
                    self.config.app_log.error('No user found. Cannot route transaction.')

                if txn_sum:
                    self.config.mongo.async_db.miner_transactions.replace_one(
                        {
                            'id': txn.transaction_signature
                        },
                        txn.to_dict()
                    )
                    for peer_rid, peer_stream in self.config.nodeServer.inbound_streams[User.__name__].items():
                        yield peer_stream
                elif rid:
                    yield self.config.nodeServer.inbound_streams[User.__name__][rid]
    
    async def get_service_provider_request_peers(self, peer, payload):
        # check if the calculated service provider for the group is me
        if payload.get('group'):
            group = Group.from_dict(payload.get('group'))

        if isinstance(peer, User):
            for rid, peer_stream in self.config.nodeClient.outbound_streams[SeedGateway.__name__].items():
                yield peer_stream

            for rid, peer_stream in self.config.websocketServer.inbound_streams.items():
                if peer.identity.username_signature == peer_stream.peer.identity.username_signature:
                    continue
                yield peer_stream
        
        elif isinstance(peer, SeedGateway):
            for peer_rid, peer_stream in self.config.nodeServer.inbound_streams[User.__name__].items():
                yield peer_stream

            for peer_rid, peer_stream in self.config.websocketServer.inbound_streams[User.__name__].items():
                yield peer_stream

    async def get_sync_peers(self):
        for x, y in self.config.nodeServer.inbound_streams[User.__name__].items():
            yield y

        for x, y in self.config.nodeClient.outbound_streams[SeedGateway.__name__].items():
            yield y


class Group(Peer):
    id_attribute = 'rid'

    async def get_outbound_class(self):
        return ServiceProvider

    async def get_inbound_class(self):
        return User

    async def get_outbound_peers(self, nonce=None):
        service_provider = await self.calculate_service_provider()
        return {service_provider.identity.username_signature: service_provider}

    @classmethod
    def type_limit(cls, peer):
        if peer == SeedGateway:
            return 1
        elif peer == User:
            return 1
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [ServiceProvider, User]


class User(Peer):
    id_attribute = 'rid'
    async def get_outbound_class(self):
        return ServiceProvider

    async def get_inbound_class(self):
        return User

    async def get_outbound_peers(self):
        return self.config.service_providers

    @classmethod
    def type_limit(cls, peer):
        if peer == ServiceProvider:
            return 1
        elif peer == User:
            return 100000
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [ServiceProvider]

    async def get_sync_peers(self):
        for x, y in self.config.nodeClient.outbound_streams[ServiceProvider.__name__].items():
            yield y

    async def get_route_peers(self, peer, payload):
        for x, y in self.config.nodeClient.outbound_streams[User.__name__].items():
            yield y
        for x, y in self.config.nodeServer.inbound_streams[User.__name__].items():
            yield y


class Miner(Peer):
    id_attribute = 'address'
    async def get_outbound_class(self):
        return ServiceProvider

    async def get_inbound_class(self):
        return User

    async def get_outbound_peers(self):
        return self.config.service_providers

    @classmethod
    def type_limit(cls, peer):
        if peer == ServiceProvider:
            return 1
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [ServiceProvider]


class Peers:
    
    @classmethod
    def get_seeds(cls):
        return OrderedDict({x.identity.username_signature: x for x in [
            Seed.from_dict({
                'host': '34.237.46.10',
                'port': 8000,
                'identity': {
                    "username": "",
                    "username_signature": "MEUCIQCP+rF5R4sZ7pHJCBAWHxARLg9GN4dRw+/pobJ0MPmX3gIgX0RD4OxhSS9KPJTUonYI1Tr+ZI2N9uuoToZo1RGOs2M=",
                    "public_key": "02fa9550f57055c96c7ce4c6c9cd1411856beba5c7d5a07417e980a39aa03da3dc"
                },
                "seed_gateway": "MEQCIHONdT7i8K+ZTzv3PHyPAhYkaksoh6FxEJUmPLmXZqFPAiBHOnt1CjgMtNzCGdBk/0S/oikPzJVys32bgThxXtAbgQ=="
            }),
        ]})

    @classmethod
    def get_seed_gateways(cls):
        return OrderedDict({x.identity.username_signature: x for x in [
            SeedGateway.from_dict({
                'host': '18.214.218.185',
                'port': 8000,
                'identity': {
                    "username": "",
                    "username_signature": "MEQCIHONdT7i8K+ZTzv3PHyPAhYkaksoh6FxEJUmPLmXZqFPAiBHOnt1CjgMtNzCGdBk/0S/oikPzJVys32bgThxXtAbgQ==",
                    "public_key": "03362203ee71bc15918a7992f3c76728fc4e45f4916d2c0311c37aad0f736b26b9"
                },
                "seed": "MEUCIQCP+rF5R4sZ7pHJCBAWHxARLg9GN4dRw+/pobJ0MPmX3gIgX0RD4OxhSS9KPJTUonYI1Tr+ZI2N9uuoToZo1RGOs2M="
            }),
        ]})

    @classmethod
    def get_service_providers(cls):
        return OrderedDict({x.identity.username_signature: x for x in [
            ServiceProvider.from_dict({
                'host': '3.225.228.97',
                'port': 8000,
                'identity': {
                    "username": "",
                    "username_signature": "MEQCIC7ADPLI3VPDNpQPaXAeB8gUk2LrvZDJIdEg9C12dj5PAiB61Te/sen1D++EJAcgnGLH4iq7HTZHv/FNByuvu4PrrA==",
                    "public_key": "02a9aed3a4d69013246d24e25ded69855fbd590cb75b4a90fbfdc337111681feba"
                }
            }),
        ]})
    
    @classmethod
    def get_groups(cls):
        return OrderedDict({x.identity.username_signature: x for x in [
            Group.from_dict({
                'host': None,
                'port': None,
                'identity': {
                    'username':'group',
                    'username_signature':'MEUCIQDIlC+SpeLwUI4fzV1mkEsJCG6HIvBvazHuMMNGuVKi+gIgV8r1cexwDHM3RFGkP9bURi+RmcybaKHUcco1Qu0wvxw=',
                    'public_key':'036f99ba2238167d9726af27168384d5fe00ef96b928427f3b931ed6a695aaabff',
                    'wif':'KydUVG4w2ZSQkg6DAZ4UCEbfZz9Tg4PsjJFnvHwFsfmRkqXAHN8W'
                }
            })
        ]})

