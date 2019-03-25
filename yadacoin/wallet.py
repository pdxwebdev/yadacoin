import hashlib
import json
import binascii
import base58
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey, PublicKey
from mnemonic import Mnemonic
from bip32utils import BIP32Key


class Wallet(object):
    def __init__(self, config):
        self.seed = config.get('seed', '')
        self.xprv = config.get('xprv', '')
        self.username = config.get('username', '')
        self.public_key = config.get('public_key')
        self.address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))

        self.private_key = config.get('private_key')
        self.wif = self.to_wif(self.private_key)
        self.bulletin_secret = self.inst_get_bulletin_secret()

        self.mongodb_host = config.get('mongodb_host')
        self.database = config.get('database')
        self.site_database = config.get('site_database')
        self.web_server_host = config.get('web_server_host')
        self.web_server_port = config.get('web_server_port')
        if config.get('peer_host') == '0.0.0.0' or config.get('peer_host') == 'localhost':
            raise Exception("cannot use localhost or 0.0.0.0, must specify public ipv4 address")
        if config.get('peer_host') == '[my public ip]':
            raise Exception("please configure your peer_post to your public ipv4 address")
        self.peer_host = config.get('peer_host')
        self.peer_port = config.get('peer_port')
        self.serve_host = config.get('serve_host')
        self.serve_port = config.get('serve_port')
        self.callbackurl = config.get('callbackurl')
        self.fcm_key = config.get('fcm_key')

    @classmethod
    def generate(cls, xprv=None, prv=None, seed=None, child=None):
        # generate 12 word mnemonic seed
        mnemonic = Mnemonic('english')
        if not seed and not xprv and not prv:
            seed = mnemonic.generate(256)
        
        private_key = None
        if seed:
            # create bitcoin wallet
            entropy = mnemonic.to_entropy(seed)
            key = BIP32Key.fromEntropy(entropy)
            private_key = key.PrivateKey().hex()
            extended_key = key.ExtendedKey()

        if prv:
            private_key = PrivateKey.from_hex(bytes.fromhex(prv)).to_hex()
            extended_key = ''

        if xprv:
            key = BIP32Key.fromExtendedKey(xprv)
            private_key = key.PrivateKey().hex()
            extended_key = key.ExtendedKey()
        
        if xprv and child:
            for x in child:
                key = key.ChildKey(int(x))
                private_key = key.PrivateKey().hex()

        if not private_key:
            raise Exception('No key')

        return cls({
            "seed": seed or '',
            "xprv": extended_key or '',
            "private_key": private_key,
            "wif": cls.to_wif(private_key),
            "public_key": PublicKey.from_point(key.K.pubkey.point.x(), key.K.pubkey.point.y()).format().hex(),
            "address": str(key.Address()),
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
        cls.seed = config.get('seed', '')
        cls.xprv = config.get('xprv', '')
        cls.username = config.get('username', '')
        cls.public_key = config.get('public_key')
        cls.address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(cls.public_key)))

        cls.private_key = config.get('private_key')
        cls.wif = cls.to_wif(cls.private_key)
        cls.bulletin_secret = cls.get_bulletin_secret()

        cls.mongodb_host = config.get('mongodb_host')
        cls.database = config.get('database')
        cls.site_database = config.get('site_database')
        cls.web_server_host = config.get('web_server_host')
        cls.web_server_port = config.get('web_server_port')
        if config.get('peer_host') == '0.0.0.0' or config.get('peer_host') == 'localhost':
            raise Exception("cannot use localhost or 0.0.0.0, must specify public ipv4 address")
        if config.get('peer_host') == '[my public ip]':
            raise Exception("please configure your peer_post to your public ipv4 address")
        cls.peer_host = config.get('peer_host')
        cls.peer_port = config.get('peer_port')
        cls.serve_host = config.get('serve_host')
        cls.serve_port = config.get('serve_port')
        cls.callbackurl = config.get('callbackurl')
        cls.fcm_key = config.get('fcm_key')

    def inst_get_bulletin_secret(self):
        from yadacoin.transactionutils import TU
        return TU.generate_deterministic_signature(self, self.username, self.private_key)

    @classmethod
    def get_bulletin_secret(cls, private_key=None, username=''):
        from yadacoin.transactionutils import TU
        return TU.generate_deterministic_signature(username, private_key)

    @classmethod
    def to_wif(cls, private_key):
        private_key_static = private_key
        extended_key = "80"+private_key_static+"01"
        first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key)).hexdigest()
        second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()
        final_key = extended_key+second_sha256[:8]
        wif = base58.b58encode(binascii.unhexlify(final_key))
        return wif

    @classmethod
    def to_dict(cls):
        return {
            'seed': cls.seed,
            'xprv': cls.xprv,
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

    def inst_to_dict(self):
        return {
            'seed': self.seed,
            'xprv': self.xprv,
            'public_key': self.public_key,
            'address': self.address,
            'private_key': self.private_key,
            'wif': self.wif,
            'bulletin_secret': self.bulletin_secret,
            'mongodb_host': self.mongodb_host,
            'username': self.username,
            'database': self.database,
            'site_database': self.site_database,
            'web_server_host': self.web_server_host,
            'web_server_port': self.web_server_port,
            'peer_host': self.peer_host,
            'peer_port': self.peer_port,
            'serve_host': self.serve_host,
            'serve_port': self.serve_port,
            'fcm_key': self.fcm_key,
            'callbackurl': self.callbackurl
        }

    @classmethod
    def to_json(cls):
        return json.dumps(cls.to_dict(), indent=4)

    def inst_to_json(self):
        return json.dumps(self.inst_to_dict(), indent=4)
