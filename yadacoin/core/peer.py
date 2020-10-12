import json
from logging import getLogger

from yadacoin.core.config import get_config
from yadacoin.core.identity import Identity


class Peer(object):
    """An individual Peer object"""

    def __init__(self, host=None, port=None, peer_type=None, identity=None):
        self.config = get_config()
        self.host = host
        self.port = port
        self.identity = identity
        self.app_log = getLogger("tornado.application")
    
    @classmethod
    def from_dict(cls, peer):
        inst = cls()
        inst.config = get_config()
        inst.host = peer['host']
        inst.port = peer['port']
        inst.identity = Identity.from_dict(peer['identity'])
        inst.app_log = getLogger("tornado.application")
        return inst

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

    def to_dict(self):
        return {
            'host': self.host,
            'port': self.port,
            'identity': self.identity.to_dict
        }

    def to_string(self):
        return '{}:{}'.format(self.host, self.port)
    
    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)


class Seed(Peer):
    @classmethod
    def type_limit(cls, peer):
        if isinstance(peer, Seed) or type(peer) == type(Seed):
            return 100000
        elif isinstance(peer, SeedGateway) or type(peer) == type(SeedGateway):
            return 1
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [Seed, SeedGateway]


class SeedGateway(Peer):
    @classmethod
    def type_limit(cls, peer):
        if isinstance(peer, Seed) or type(peer) == type(Seed):
            return 1
        elif isinstance(peer, ServiceProvider) or type(peer) == type(ServiceProvider):
            return 100000
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [Seed, ServiceProvider]


class ServiceProvider(Peer):
    @classmethod
    def type_limit(cls, peer):
        if isinstance(peer, SeedGateway) or type(peer) == type(SeedGateway):
            return 1
        elif isinstance(peer, User):
            return 100000
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [ServiceProvider, User]


class User(Peer):
    @classmethod
    def type_limit(cls, peer):
        if isinstance(peer, ServiceProvider) or type(peer) == type(ServiceProvider):
            return 1
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [ServiceProvider]
