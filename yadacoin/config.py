import hashlib
import os
import json
import binascii
import base58
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey, PublicKey


class Config(object):
    @classmethod
    def generate(cls, mongodb_host=None):
        num = os.urandom(32).encode('hex')
        pk = PrivateKey.from_hex(num)
        cls.private_key = pk.to_hex()
        cls.from_dict({
            "private_key": cls.private_key,
            "wif": cls.to_wif(),
            "public_key": pk.public_key.format().encode('hex'),
            "address": str(P2PKHBitcoinAddress.from_pubkey(pk.public_key.format())),
            "serve_host": "0.0.0.0",
            "serve_port": 8000,
            "peer_host": "",
            "peer_port": 8000,
            "web_server_host": "0.0.0.0",
            "web_server_port": 5000,
            "peer": "http://localhost:8000",
            "callbackurl": "http://0.0.0.0:5000/create-relationship",
            "fcm_key": "",
            "database": "yadacoin",
            "site_database": "yadacoinsite",
            "mongodb_host": "localhost",
            "mixpanel": "",
            "username": ""
        })

    @classmethod
    def from_dict(cls, config):
        cls.public_key = config['public_key']
        cls.address = str(P2PKHBitcoinAddress.from_pubkey(cls.public_key.decode('hex')))

        cls.private_key = config['private_key']
        cls.username = config['username']
        cls.wif = cls.to_wif()
        cls.bulletin_secret = cls.get_bulletin_secret()

        cls.mongodb_host = config['mongodb_host']
        cls.database = config['database']
        cls.site_database = config['site_database']
        cls.web_server_host = config['web_server_host']
        cls.web_server_port = config['web_server_port']
        if config['peer_host'] == '0.0.0.0' or config['peer_host'] == 'localhost':
            raise Exception("cannot use localhost or 0.0.0.0, must specify public ipv4 address")
        if config['peer_host'] == '[my public ip]':
            raise Exception("please configure your peer_post to your public ipv4 address")
        cls.peer_host = config['peer_host']
        cls.peer_port = config['peer_port']
        cls.serve_host = config['serve_host']
        cls.serve_port = config['serve_port']
        cls.callbackurl = config['callbackurl']
        cls.fcm_key = config['fcm_key']

    @classmethod
    def get_bulletin_secret(cls):
        from transactionutils import TU
        return TU.generate_deterministic_signature(Config.username)

    @classmethod
    def to_wif(cls):
        private_key_static = cls.private_key
        extended_key = "80"+private_key_static+"01"
        first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key)).hexdigest()
        second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()
        final_key = extended_key+second_sha256[:8]
        wif = base58.b58encode(binascii.unhexlify(final_key))
        return wif

    @classmethod
    def to_dict(cls):
        return {
            'public_key': cls.public_key,
            'address': cls.address,
            'private_key': cls.private_key,
            'wif': cls.wif,
            'bulletin_secret': cls.bulletin_secret,
            'mongodb_host': cls.mongodb_host,
            'username': cls.username,
            'database': cls.database,
            'site_database': cls.site_database,
            'web_server_host': cls.web_server_host,
            'web_server_port': cls.web_server_port,
            'peer_host': cls.peer_host,
            'peer_port': cls.peer_port,
            'serve_host': cls.serve_host,
            'serve_port': cls.serve_port,
            'fcm_key': cls.fcm_key,
            'callbackurl': cls.callbackurl
        }

    @classmethod
    def to_json(cls):
        return json.dumps(cls.to_dict(), indent=4)
