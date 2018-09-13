import hashlib
import json
from bitcoin.wallet import P2PKHBitcoinAddress
from crypt import Crypt


class Config(object):
    @classmethod
    def from_dict(cls, config):
        cls.public_key = config['public_key']
        cls.address = str(P2PKHBitcoinAddress.from_pubkey(cls.public_key.decode('hex')))

        cls.private_key = config['private_key']
        cipher = Crypt(str(cls.private_key))
        cls.bulletin_secret = hashlib.sha256(cipher.encrypt_consistent(str(cls.private_key))).digest().encode('hex')

        cls.mongodb_host = config['mongodb_host']
        cls.database = config['database']
        cls.site_database = config['site_database']
        cls.web_server_host = config['web_server_host']
        cls.web_server_port = config['web_server_port']
        cls.serve_host = config['serve_host']
        cls.serve_port = config['serve_port']
        cls.peer = config['peer']
        cls.callbackurl = config['callbackurl']
        cls.difficulty = config['difficulty']
        cls.coinbase = config['coinbase']
        cls.fcm_key = config['fcm_key']

    @classmethod
    def to_dict(cls):
        return {
            'public_key': cls.public_key,
            'address': cls.address,
            'private_key': cls.private_key,
            'bulletin_secret': cls.bulletin_secret,
            'mongodb_host': cls.mongodb_host,
            'database': cls.database,
            'site_database': cls.site_database,
            'web_server_host': cls.web_server_host,
            'web_server_port': cls.web_server_port,
            'serve_host': cls.serve_host,
            'serve_port': cls.serve_port,
            'peer': cls.peer,
            'difficulty': cls.difficulty,
            'coinbase': cls.coinbase,
            'fcm_key': cls.fcm_key
        }

    @classmethod
    def to_json(cls):
        return json.dumps(cls.to_dict(), indent=4)
