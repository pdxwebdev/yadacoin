import json
import requests

class Peers(object):
    @classmethod
    def init(cls):
        res = requests.get('https://yadacoin.io/peers')
        cls.peers = json.loads(res.content)['peers']

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

    def to_dict(cls):
        return {
           'peers': cls.peers
        }

class Peer(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port