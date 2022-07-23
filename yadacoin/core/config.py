import binascii
import hashlib
import json
from logging import getLogger
from time import time

import base58
from bip32utils import BIP32Key
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey, PublicKey
from mnemonic import Mnemonic
from yadacoin import version

CONFIG = None


def get_config():
    return CONFIG


class Config(object):

    def __init__(self, config):
        self.start_time = int(time())
        self.modes = config.get('modes', ['node', 'web', 'pool'])
        self.root_app = config.get('root_app', '')
        self.seed = config.get('seed', '')
        self.xprv = config.get('xprv', '')
        self.username = config.get('username', '')
        self.network = config.get('network', 'mainnet')
        self.use_pnp = config.get('use_pnp', False)
        self.ssl = SSLConfig.from_dict(config.get('ssl'))
        self.origin = config.get('origin', False)
        self.max_inbound = config.get('max_inbound', 10)
        self.max_outbound = config.get('max_outbound', 10)
        self.max_miners = config.get('max_miners', -1)
        self.public_key = config['public_key']
        self.address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))

        self.private_key = config['private_key']
        self.wif = self.to_wif(self.private_key)
        self.username_signature = self.get_username_signature()

        self.mongodb_host = config['mongodb_host']
        self.database = config['database']
        self.site_database = config['site_database']
        if config['peer_host'] == '0.0.0.0' or config['peer_host'] == 'localhost':
            raise Exception("Cannot use localhost or 0.0.0.0, must specify public ipv4 address")
        if config['peer_host'] == '[my public ip]':
            raise Exception("Please configure your peer_post to your public ipv4 address")
        self.peer_host = config['peer_host']
        self.peer_port = config['peer_port']
        self.peer_type = config.get('peer_type', 'user')
        self.serve_host = config['serve_host']
        self.serve_port = config['serve_port']
        self.callbackurl = config['callbackurl']
        self.sia_api_key = config.get('sia_api_key')
        self.jwt_public_key = config.get('jwt_public_key')
        self.fcm_key = config['fcm_key']
        self.post_peer = config.get('post_peer', True)
        self.extended_status = config.get('extended_status', False)
        self.peers_seed = config.get('peers_seed', [])  # not used, superceeded by config/seed.json
        self.api_whitelist = config.get('api_whitelist', [])
        self.force_broadcast_to = config.get('force_broadcast_to', [])
        self.outgoing_blacklist =  config.get('outgoing_blacklist', [])
        # Do not try to test or connect to ourselves.
        self.outgoing_blacklist.append(self.serve_host)
        self.outgoing_blacklist.append("{}:{}".format(self.peer_host, self.peer_port))
        self.protocol_version = version
        # Config also serves as backbone storage for all singleton helpers used by the components.
        self.mongo = None
        self.consensus = None
        self.peers = None
        self.BU = None
        self.GU = None
        self.SIO = None
        self.debug = False
        self.mp = None
        self.pp = None
        self.stratum_pool_port = config.get('stratum_pool_port', 3333)
        self.wallet_host_port = config.get('wallet_host_port', 'http://localhost:{}'.format(config['serve_port']))
        self.websocket_host_port = config.get('websocket_host_port', 'ws://localhost:{}'.format(config['serve_port']))
        self.credits_per_share = config.get('credits_per_share', 5)
        self.shares_required = config.get('shares_required', False)
        self.pool_payout = config.get('pool_payout', False)
        self.pool_take = config.get('pool_take', .01)
        self.payout_frequency = config.get('payout_frequency', 6)

        self.restrict_graph_api = config.get('restrict_graph_api', False)

        self.skynet_url = config.get('skynet_url', '')
        self.skynet_api_key = config.get('skynet_api_key', '')

        self.web_jwt_expiry = config.get('web_jwt_expiry', 23040)

        self.email = EmailConfig.from_dict(config.get('email'))

        for key, val in config.items():
            if not hasattr(self, key):
                setattr(self, key, val)

    async def on_new_block(self, block):
        """Dispatcher for the new bloc event
        This is called with a block object when we insert a new one in the chain."""
        # Update BU
        # We can either invalidate, or directly set the block as cached one.
        # self.BU.invalidate_last_block()
        block_dict = block.to_dict()
        self.BU.set_latest_block(block_dict)  # Warning, this is a dict, not a Block!
        if self.mp:
            await self.mp.refresh()

    async def get_status(self):
        pool_status = 'N/A'
        if hasattr(self, 'pool_server'):
            pool_status = await self.pool_server.status()
        m, s = divmod(int(time() - self.start_time), 60)
        h, m = divmod(m, 60)
        num_peers = 0
        for y in list(self.nodeServer.inbound_streams.values()):
            num_peers += len(y)
        for y in list(self.nodeClient.outbound_streams.values()):
            num_peers += len(y)
        status = {
            'version': '.'.join([str(x) for x in self.protocol_version]),
            'network': self.network,
            'peer_type': self.peer_type,
            # 'connections':{'outgoing': -1, 'ingoing': -1, 'max': -1},
            'username': self.username,
            'peers': num_peers,
            'pool': pool_status,
            'uptime': '{:d}:{:02d}:{:02d}'.format(h, m, s),
            'height': self.LatestBlock.block.index
        }
        # TODO: add uptime in human readable format
        return status

    def get_identity(self):
        return {
          'username': self.username,
          'username_signature': self.username_signature,
          'public_key': self.public_key
        }

    @classmethod
    def generate(cls, xprv=None, prv=None, seed=None, child=None, username=None, mongodb_host=None, db_name=None):
        mnemonic = Mnemonic('english')
        # generate 12 word mnemonic seed
        if not seed and not xprv and not prv:
            seed = mnemonic.generate(256)
        private_key = None
        if seed:
            # create new wallet
            entropy = mnemonic.to_entropy(seed)
            key = BIP32Key.fromEntropy(entropy)
            private_key = key.PrivateKey().hex()
            extended_key = key.ExtendedKey()
            public_key = PublicKey.from_point(key.K.pubkey.point.x(), key.K.pubkey.point.y()).format().hex()
            address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))

        if prv:
            key = PrivateKey.from_hex(prv)
            private_key = key.to_hex()
            extended_key = ''
            public_key = key.public_key.format().hex()
            address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))

        if xprv:
            key = BIP32Key.fromExtendedKey(xprv)
            private_key = key.PrivateKey().hex()
            extended_key = key.ExtendedKey()
            public_key = PublicKey.from_point(key.K.pubkey.point.x(), key.K.pubkey.point.y()).format().hex()
            address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))

        if xprv and child:
            for x in child:
                key = key.ChildKey(int(x))
                private_key = key.PrivateKey().hex()
                public_key = PublicKey.from_point(key.K.pubkey.point.x(), key.K.pubkey.point.y()).format().hex()
                address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))

        if not private_key:
            raise Exception('No key')

        try:
            u = UPnP(None, None, 200, 0)
            u.discover()
            u.selectigd()
            peer_host = u.externalipaddress()
        except:
            try:
                import urllib.request
                peer_host = urllib.request.urlopen('https://ident.me').read().decode('utf8')
            except:
                peer_host = ''

        return cls({
            "modes": ['node', 'web', 'pool'],
            "root_app": '',
            "seed": seed or '',
            "xprv": extended_key or '',
            "private_key": private_key,
            "wif": cls.generate_wif(private_key),
            "public_key": public_key,
            "address": address,
            "api_whitelist": [],
            "serve_host": "0.0.0.0",
            "serve_port": 8001,
            "use_pnp": False,
            "ssl": SSLConfig().to_dict(),
            "origin": '',
            "sia_api_key": '',
            "post_peer": False,
            "peer_host": peer_host,
            "peer_port": 8000,
            "peer_type": "user",
            "peer": "http://localhost:8000",
            "callbackurl": "http://0.0.0.0:8001/create-relationship",
            "jwt_public_key": None,
            "fcm_key": "",
            "database": db_name or "yadacoin",
            "site_database": db_name + "site" if db_name else "yadacoinsite",
            "mongodb_host": mongodb_host or "localhost",
            "mixpanel": "",
            "username": username or '',
            "network": "mainnet",
            "wallet_host_port": 'http://localhost:8001',
            "websocket_host_port": 'ws://localhost:8001',
            "credits_per_share": 5,
            "shares_required": False,
            "pool_payout": False,
            "pool_take": .01,
            "payout_frequency": 6,
            "restrict_graph_api": False,
            "email": EmailConfig().to_dict(),
            "skynet_url": '',
            "skynet_api_key": '',
            "web_jwt_expiry": 23040
        })

    @classmethod
    def from_dict(cls, config):
        cls.modes = config.get('modes', ['node', 'web', 'pool'])
        cls.root_app = config.get('root_app', '')
        cls.seed = config.get('seed', '')
        cls.xprv = config.get('xprv', '')
        cls.username = config.get('username', '')
        cls.use_pnp = config.get('use_pnp', False)
        cls.ssl = SSLConfig.from_dict(config.get('ssl'))
        cls.origin = config.get('origin', True)
        cls.network = config.get('network', 'mainnet')
        cls.public_key = config['public_key']
        cls.address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(cls.public_key)))

        cls.private_key = config['private_key']
        cls.wif = cls.generate_wif(cls.private_key)
        cls.username_signature = TU.generate_deterministic_signature(config, config['username'], config['private_key'])

        cls.api_whitelist = config.get('api_whitelist', [])
        cls.mongodb_host = config['mongodb_host']
        cls.database = config['database']
        cls.site_database = config['site_database']
        if config['peer_host'] == '0.0.0.0' or config['peer_host'] == 'localhost':
            raise Exception("cannot use localhost or 0.0.0.0, must specify public ipv4 address")
        if config['peer_host'] == '[my public ip]':
            raise Exception("please configure your peer_post to your public ipv4 address")
        cls.peer_host = config['peer_host']
        cls.peer_port = config['peer_port']
        cls.peer_type = config.get('peer_type')
        cls.serve_host = config['serve_host']
        cls.serve_port = config['serve_port']
        cls.callbackurl = config['callbackurl']
        cls.fcm_key = config['fcm_key']
        cls.jwt_public_key = config.get('jwt_public_key')
        cls.sia_api_key = config.get('sia_api_key')
        cls.wallet_host_port = config.get('wallet_host_port')
        cls.websocket_host_port = config.get('websocket_host_port')
        cls.credits_per_share = config.get('credits_per_share', 5)
        cls.shares_required = config.get('shares_required', False)
        cls.pool_payout = config.get('pool_payout', False)
        cls.pool_take = config.get('pool_take', .01)
        cls.payout_frequency = config.get('payout_frequency', 6)

        cls.restrict_graph_api = config.get('restrict_graph_api', False)

        cls.skynet_url = config.get('skynet_url', '')
        cls.skynet_api_key = config.get('skynet_api_key', '')

        cls.web_jwt_expiry = config.get('web_jwt_expiry', 23040)

        email = config.get('email', False)
        if email:
            cls.email = EmailConfig.from_dict(email)

    @staticmethod
    def address_is_valid(address):
        try:
            base58_decoded = base58.b58decode(address).hex()
            prefix_Hash = base58_decoded[:len(base58_decoded)-8]
            checksum = base58_decoded[len(base58_decoded)-8:]
            hash = prefix_Hash

            for x in range(1,3):
                hash = hashlib.sha256(binascii.unhexlify(hash)).hexdigest()

            if(checksum == hash[:8]):
                return True
            else:
                return False
        except:
            return False

    def get_username_signature(self):
        from yadacoin.core.transactionutils import TU
        return TU.generate_deterministic_signature(self, self.username, self.private_key)

    def to_wif(self, private_key):
        private_key_static = private_key
        extended_key = "80"+private_key_static+"01"
        first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key)).hexdigest()
        second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()
        final_key = extended_key+second_sha256[:8]
        wif = base58.b58encode(binascii.unhexlify(final_key)).decode('utf-8')
        return wif

    @classmethod
    def generate_wif(cls, private_key):
        private_key_static = private_key
        extended_key = "80"+private_key_static+"01"
        first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key)).hexdigest()
        second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()
        final_key = extended_key+second_sha256[:8]
        wif = base58.b58encode(binascii.unhexlify(final_key)).decode('utf-8')
        return wif

    def to_dict(self):
        return {
            'modes': self.modes,
            'root_app': self.root_app,
            'seed': self.seed,
            'xprv': self.xprv,
            'public_key': self.public_key,
            'address': self.address,
            'private_key': self.private_key,
            'wif': self.wif,
            'username_signature': self.username_signature,
            'mongodb_host': self.mongodb_host,
            'api_whitelist': self.api_whitelist,
            'username': self.username,
            'network': self.network,
            'database': self.database,
            'site_database': self.site_database,
            'peer_host': self.peer_host,
            'peer_port': self.peer_port,
            'peer_type': self.peer_type,
            'serve_host': self.serve_host,
            'serve_port': self.serve_port,
            'use_pnp': self.use_pnp,
            'ssl': self.ssl.to_dict(),
            'origin': self.origin,
            'fcm_key': self.fcm_key,
            'sia_api_key': self.sia_api_key,
            'jwt_public_key': self.jwt_public_key,
            'callbackurl': self.callbackurl,
            'wallet_host_port': self.wallet_host_port,
            'websocket_host_port': self.websocket_host_port,
            'credits_per_share': self.credits_per_share,
            'shares_required': self.shares_required,
            'pool_payout': self.pool_payout,
            'pool_take': self.pool_take,
            'payout_frequency': self.payout_frequency,
            'restrict_graph_api': self.restrict_graph_api,
            'email': self.email.to_dict(),
            'skynet_url': self.skynet_url,
            'skynet_api_key': self.skynet_api_key,
            'web_jwt_expiry': self.web_jwt_expiry,
            'stratum_pool_port': self.stratum_pool_port
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)


class EmailConfig():
    username = ''
    password = ''
    smtp_server = ''
    smtp_port = 587

    def is_valid(self):
        return (
            self.username and
            self.password and
            self.smtp_server and
            self.smtp_port
        )

    @staticmethod
    def from_dict(email_config):
        if not isinstance(email_config, dict):
            email_config = {}
        inst = EmailConfig()
        inst.username = email_config.get('username')
        inst.password = email_config.get('password')
        inst.smtp_server = email_config.get('smtp_server')
        inst.smtp_port = email_config.get('smtp_port')
        return inst

    def to_dict(self):
        return {
            'username': self.username,
            'password': self.password,
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port
        }


class SSLConfig():
    ca_file = ''
    cert_file = ''
    key_file = ''
    port = 443
    common_name = ''

    def is_valid(self):
        return (
            self.ca_file and
            self.key_file and
            self.cert_file and
            self.port
        )

    @staticmethod
    def from_dict(ssl_config):
        if not isinstance(ssl_config, dict):
            ssl_config = {}
        inst = SSLConfig()
        inst.ca_file = ssl_config.get('cafile')
        inst.cert_file = ssl_config.get('certfile')
        inst.key_file = ssl_config.get('keyfile')
        inst.port = ssl_config.get('port')
        inst.common_name = ssl_config.get('common_name')
        return inst

    def to_dict(self):
        return {
            'cafile': self.ca_file,
            'certfile': self.cert_file,
            'keyfile': self.key_file,
            'port': self.port
        }
