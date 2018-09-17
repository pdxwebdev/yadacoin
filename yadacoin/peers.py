import json
import requests

from mongo import Mongo

class Peers(object):
    @classmethod
    def init_local(cls):
        Mongo.init()
        res = Mongo.db.peers.find({'active': True, 'failed': {'$lt': 30}}, {'_id': 0})
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
    def init(cls):
        cls.peers = []
        try:
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
        return {
           'peers': [x.to_dict() for x in cls.peers]
        }

class Peer(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def to_dict(self):
        return {
            'host': self.host,
            'port': self.port
        }