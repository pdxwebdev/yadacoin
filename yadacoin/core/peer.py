import json
from collections import OrderedDict
from logging import getLogger

from yadacoin.core.config import get_config
from yadacoin.core.identity import Identity


class Peer(object):
    """An individual Peer object"""

    def __init__(self, host=None, port=None, identity=None, is_me=False):
        self.host = host
        self.port = port
        self.identity = identity
        self.config = get_config()
        if is_me:
            self.rid = None
        else:
            self.rid = self.identity.generate_rid(self.config.peer.identity.username_signature)
        self.app_log = getLogger("tornado.application")
    
    @classmethod
    def from_dict(cls, peer, is_me=False):
        inst = cls(
            peer['host'],
            peer['port'],
            Identity.from_dict(peer['identity']),
            is_me
        )
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
            'identity': self.identity.to_dict,
            'rid': self.rid
        }

    def to_string(self):
        return '{}:{}'.format(self.host, self.port)
    
    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)


class Seed(Peer):
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


class SeedGateway(Peer):
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


class ServiceProvider(Peer):
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


class User(Peer):
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
                'host': '71.193.201.21',
                'port': 8000,
                'identity': {
                    "username": "seed_A",
                    "username_signature": "MEUCIQC3slOHQ0AgPSyFeas/mxMrmJuF5+itfpxSFAERAjyr4wIgCBMuSOEJnisJ7//Y019vYhIWCWvzvCnfXZRxfbrt2SM=",
                    "public_key": "0286707b29746a434ead4ab94af2d7758d4ae8aaa12fdad9ab42ce3952a8ef798f"
                }
            }),
            Seed.from_dict({
                'host': '71.193.201.21',
                'port': 8004,
                'identity': {
                    "username": "seed_B",
                    "username_signature": "MEQCIBn3IO/QP6UerU5u0XqkTdK0iJpA7apayQgxqgT3E29yAiAljkzDzGucZXSKgjklsuDm9HhjZ70VMjpa21eObQIS7A==",
                    "public_key": "03ef7653e994341268b81a33f35dbfa22cbd240b454a0995ecdd8713cd624a7251"
                }
            })
        ]})

    @classmethod
    def get_seed_gateways(cls):
        return OrderedDict({x.identity.username_signature: x for x in [
            SeedGateway.from_dict({
                'host': '71.193.201.21',
                'port': 8001,
                'identity': {
                    "username": "seed_gateway_A",
                    "username_signature": "MEQCIEvShxHewQt9u/4+WlcjSubCfsjOmvq8bRoU6t/LGmdLAiAQyr5op3AZj58NzRDthvq7bEouwHhEzis5ZYKlE6D0HA==",
                    "public_key": "03e8b4651a1e794998c265545facbab520131cdddaea3da304a36279b1d334dfb1"
                }
            }),
            SeedGateway.from_dict({
                'host': '71.193.201.21',
                'port': 8005,
                'identity': {
                    "username": "seed_gateway_B",
                    "username_signature": "MEUCIQCGY5xwZgT5v7iNSpO7b6FFQne8h6RzPf1UAQr2yptHGgIgE6UaVTjyHYozwpona00Ydagkb5oCAiyPv008YL9a5hA=",
                    "public_key": "0308b55c62b0bdce1a696ff21fd94a044ef882328b520341a65d617e8be6964361"
                }
            })
        ]})

    @classmethod
    def get_service_providers(cls):
        return OrderedDict({x.identity.username_signature: x for x in [
            ServiceProvider.from_dict({
                'host': '71.193.201.21',
                'port': 8002,
                'identity': {
                    "username": "service_provider_A",
                    "username_signature": "MEUCIQCIzIDpRwBJgU0fjTh6FZhpIrLz/WNTLIZwK2Ifx7HjtQIgfYYOPFy7ypU+KYeYzkCa9OWwbwPIt9Hk0cV8Q6pcXog=",
                    "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7"
                }
            }),
            ServiceProvider.from_dict({
                'host': '71.193.201.21',
                'port': 8006,
                'identity': {
                    "username": "service_provider_B",
                    "username_signature": "MEQCIF1jg+YOY3r7vR2pF1mLLdnUo/Va9wAQ2X6d6w9fVgLQAiBUyAmw88iMzK/nQ1AK5ZnJqifgXWCH4bid/dlGOJq8EA==",
                    "public_key": "0341f797e55ca256505594e722e2a8c2ed9484d2de12492e704e1d019cef6cf647"
                }
            })
        ]})

