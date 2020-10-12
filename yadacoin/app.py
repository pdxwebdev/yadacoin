"""
Async Yadacoin node poc
"""
import sys
sys.path.append('/home/mvogel/yadacoin')
import importlib
import pkgutil
import json
import logging
import os
import ssl
import ntpath
from traceback import format_exc
from asyncio import sleep as async_sleep
from hashlib import sha256
from logging.handlers import RotatingFileHandler
from os import path
from sys import exit, stdout
from time import time
from traceback import format_exc

import webbrowser
import pyrx
from Crypto.PublicKey.ECC import EccKey
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
import socketio
import tornado.ioloop
import tornado.locks
import tornado.log
from tornado.iostream import StreamClosedError
from tornado.options import define, options
from tornado.web import Application, StaticFileHandler
from concurrent.futures import ThreadPoolExecutor

import yadacoin.core.blockchainutils
import yadacoin.core.transactionutils
import yadacoin.core.config
from yadacoin.core.crypt import Crypt
from yadacoin.core.consensus import Consensus
from yadacoin.core.chain import CHAIN
from yadacoin.core.graphutils import GraphUtils
from yadacoin.core.mongo import Mongo
from yadacoin.core.miningpoolpayout import PoolPayer
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.peer import Peer, Seed, SeedGateway, ServiceProvider, User
from yadacoin.core.identity import Identity
from yadacoin.http.web import WEB_HANDLERS
from yadacoin.http.explorer import EXPLORER_HANDLERS
from yadacoin.http.graph import GRAPH_HANDLERS
from yadacoin.http.node import NODE_HANDLERS
from yadacoin.http.pool import POOL_HANDLERS
from yadacoin.http.wallet import WALLET_HANDLERS
from yadacoin.socket.node import NodeSocketServer, NodeSocketClient
from yadacoin.socket.pool import StratumServer

__version__ = '0.1.0'

PROTOCOL_VERSION = 3


class NodeApplication(Application):

    def __init__(self):

        define("debug", default=False, help="debug mode", type=bool)
        define("verbose", default=False, help="verbose mode", type=bool)
        define("network", default='', help="Force mainnet, testnet or regnet", type=str)
        define("reset", default=False, help="If blockchain is invalid, truncate at error block", type=bool)
        define("config", default='config/config.json', help="Config file location, default is 'config/config.json'", type=str)
        define("verify", default=True, help="Verify chain, default True", type=bool)
        define("server", default=False, help="Is server for testing", type=bool)
        define("client", default=False, help="Is client for testing", type=bool)

        options.parse_command_line(final=False)
        
        self.init_config(options)
        self.configure_logging()
        self.init_config_properties()
        self.init_seeds()
        self.init_seed_gateways()
        self.init_service_providers()
        if self.config.mode == 'pool':
            self.init_pool()
        elif self.config.mode == 'web':
            self.init_http()
            self.init_whitelist()
        elif self.config.mode == 'node':
            self.init_peer()
            self.init_ioloop()            

    async def background_consensus(self):
        if not self.config.consensus:
            self.config.consensus = Consensus(self.config.debug, self.config.peers)
            if options.verify:
                self.config.app_log.info("Verifying existing blockchain")
                await self.config.consensus.verify_existing_blockchain(reset=self.config.reset)
            else:
                self.config.app_log.warning("Verification of existing blockchain skipped by config")

        try:
            if self.consensus_busy:
                return
            self.consensus_busy = True
            again = True
            while again:
                again = await self.config.consensus.sync_bottom_up()
            self.consensus_busy = False
        except Exception as e:
            self.config.app_log.error(format_exc())

    async def background_peers(self):
        """Peers management coroutine. responsible for peers testing and outgoing connections"""
        try:
            peers = None
            if isinstance(self.config.peer, Seed):
                peers = self.config.seeds
                limit = self.config.peer.__class__.type_limit(Seed)
            elif isinstance(self.config.peer, SeedGateway):
                peers = self.config.seeds
                limit = self.config.peer.__class__.type_limit(Seed)
            elif isinstance(self.config.peer, ServiceProvider):
                peers = self.config.seed_gateways
                limit = self.config.peer.__class__.type_limit(SeedGateway)
            elif isinstance(self.config.peer, User):
                peers = self.config.service_providers
                limit = self.config.peer.__class__.type_limit(User)

            if limit and limit > len(self.config.nodeServer.sockets):
                for peer in set(peers) - set(self.config.nodeServer.sockets): # only connect to seed nodes
                    await self.config.nodeClient.connect(peers[peer])

        except Exception as e:
            self.config.app_log.error(format_exc())

    async def background_status(self):
        """This background co-routine is responsible for status collection and display"""
        try:
            # status = {"peers": config.peers.get_status()}
            if self.config.status_busy:
                return
            self.config.status_busy = True
            status = self.config.get_status()
            # print(status)
            self.config.app_log.info(json.dumps(status))
            self.config.status_busy = False
        except Exception as e:
            self.config.app_log.error(format_exc())

    async def background_block_checker(self):
        """Responsible for miner updates"""
        """
        New blocks will directly trigger the correct event.
        This co-routine checks if new transactions have been received, or if special_min is triggered,
        So we can update the miners.
        """
        try:
            if self.config.block_checker_busy:
                return
            self.config.block_checker_busy = True
            await LatestBlock.block_checker()

            self.config.block_checker_busy = False
        except Exception as e:
            self.config.app_log.error(format_exc())

    async def background_pool_payer(self):
        """Responsible for paying miners"""
        """
        New blocks will directly trigger the correct event.
        This co-routine checks if new transactions have been received, or if special_min is triggered,
        So we can update the miners.
        """
        try:
            if self.pool_payer_busy:
                return
            self.pool_payer_busy = True
            if self.config.pp:
                await self.config.pp.do_payout()

            self.pool_payer_busy = False
        except Exception as e:
            self.config.app_log.error(format_exc())

    async def background_cache_validator(self):
        """Responsible for validating the cache and clearing it when necessary"""
        if self.cache_busy:
            return
        self.cache_busy = True
        if not hasattr(self.config, 'cache_inited'):
            self.cache_collections = [x for x in await self.config.mongo.async_db.list_collection_names({}) if x.endswith('_cache')]
            self.cache_last_times = {}
            try:
                async for x in self.config.mongo.async_db.blocks.find({'updated_at': {'$exists': False}}):
                    self.config.mongo.async_db.blocks.update_one({'index': x['index']}, {'$set': {'updated_at': time()}})
                for cache_collection in self.cache_collections:
                    self.cache_last_times[cache_collection] = 0
                    await self.config.mongo.async_db[cache_collection].delete_many({'cache_time': {'$exists': False}})
                self.config.cache_inited = True
            except Exception as e:
                self.config.app_log.error(format_exc())

        """
        We check for cache items that are not currently in the blockchain
        If not, we delete the cached item.
        """
        try:
            for cache_collection in self.cache_collections:
                if not self.cache_last_times.get(cache_collection):
                    latest = await self.config.mongo.async_db[cache_collection].find_one({
                        'cache_time': {'$gt': self.cache_last_times[cache_collection]}
                    }, sort=[('height', -1)])
                    if latest:
                        self.cache_last_times[cache_collection] = latest['cache_time']
                    else:
                        self.cache_last_times[cache_collection] = 0
                async for txn in self.config.mongo.async_db[cache_collection].find({
                    'cache_time': {'$gt': self.cache_last_times[cache_collection]}
                }).sort([('height', -1)]):
                    if not await self.config.mongo.async_db.blocks.find_one({
                        'index': txn.get('height'),
                        'hash': txn.get('block_hash')
                    }) and not await self.config.mongo.async_db.miner_transactions.find_one({
                        'id': txn.get('id'),
                    }):
                        await self.config.mongo.async_db[cache_collection].delete_many({
                            'height': txn.get('height')
                        })
                        break
                    else:
                        if txn['cache_time'] > self.cache_last_times[cache_collection]:
                            self.cache_last_times[cache_collection] = txn['cache_time']

            self.cache_busy = False
        except Exception as e:
            self.config.app_log.error("error in background_cache_validator")
            self.config.app_log.error(format_exc())

    def configure_logging(self):
        ch = logging.StreamHandler(stdout)
        ch.setLevel(logging.INFO)
        if options.debug:
            ch.setLevel(logging.DEBUG)
        # tornado.log.enable_pretty_logging()
        self.config.app_log = logging.getLogger("tornado.application")
        tornado.log.enable_pretty_logging(logger=self.config.app_log)
        # app_log.addHandler(ch)
        logfile = path.abspath("yada_app.log")
        # Rotate log after reaching 512K, keep 5 old copies.
        rotateHandler = RotatingFileHandler(logfile, "a", 512 * 1024, 5)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        rotateHandler.setFormatter(formatter)
        self.config.app_log.addHandler(rotateHandler)
        if options.debug:
            self.config.app_log.setLevel(logging.DEBUG)

        self.access_log = logging.getLogger("tornado.access")
        tornado.log.enable_pretty_logging()
        logfile2 = path.abspath("yada_access.log")
        rotateHandler2 = RotatingFileHandler(logfile2, "a", 512 * 1024, 5)
        formatter2 = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        rotateHandler2.setFormatter(formatter2)
        self.access_log.addHandler(rotateHandler2)

        self.config.app_log.propagate = False
        self.access_log.propagate = False
        # This logguer config is quite a mess, but works well enough for the time being.
        logging.getLogger("engineio").propagate = False
        logging.getLogger("socketio").propagate = False

    def init_config(self, options):
        if not path.isfile(options.config):
            get_logger().error("no config file found at '{}'. Generating new...".format(options.config))
            self.config = yadacoin.core.config.Config.generate()
            try:
                os.makedirs(os.path.dirname(options.config))
            except:
                pass
            with open(options.config, 'w') as f:
                f.write(self.config.to_json())

        with open(options.config) as f:
            self.config = yadacoin.core.config.Config(json.loads(f.read()))
            # Sets the global var for all objects
            yadacoin.core.config.CONFIG = self.config
            self.config.debug = options.debug
            # force network, command line one takes precedence
            if options.network != '':
                self.config.network = options.network
            self.config.protocol_version = PROTOCOL_VERSION

        self.config.reset = options.reset

    def init_whitelist(self):
        api_whitelist = 'api_whitelist.json'
        api_whitelist_filename = options.config.replace(ntpath.basename(options.config), api_whitelist)
        if path.isfile(api_whitelist_filename):
            with open(api_whitelist_filename) as f:
                self.config.api_whitelist = [x['host'] for x in json.loads(f.read())]

    def init_ioloop(self):
        tornado.ioloop.IOLoop.current().set_default_executor(ThreadPoolExecutor(max_workers=1))

        tornado.ioloop.PeriodicCallback(self.background_consensus, 30000).start()
        self.consensus_busy = False

        if self.config.network != 'regnet':
            tornado.ioloop.PeriodicCallback(self.background_peers, 3000).start()
            self.config.peers_busy = False

        tornado.ioloop.PeriodicCallback(self.background_status, 30000).start()
        self.config.status_busy = False

        tornado.ioloop.PeriodicCallback(self.background_block_checker, 1000).start()
        self.config.block_checker_busy = False

        tornado.ioloop.PeriodicCallback(self.background_cache_validator, 30000).start()
        self.cache_busy = False

        if self.config.pool_payout:
            self.config.app_log.info("PoolPayout activated")
            self.config.pp = PoolPayer()

            tornado.ioloop.PeriodicCallback(self.background_pool_payer, 120000).start()
            self.pool_payer_busy = False

        tornado.ioloop.IOLoop.current().start()

    def init_jwt(self):
        jwt_key = EccKey(curve='p256', d=int(self.config.private_key, 16))
        self.config.jwt_secret_key = jwt_key.export_key(format='PEM')
        self.config.jwt_public_key = self.config.jwt_public_key or jwt_key.public_key().export_key(format='PEM')
        self.config.jwt_options = {
            'verify_signature': True,
            'verify_exp': True,
            'verify_nbf': False,
            'verify_iat': True,
            'verify_aud': False
        }

    def init_seeds(self):
        if self.config.network == 'mainnet':

            seed_peer = Seed.from_dict({
                'host': '71.193.201.21',
                'port': 8000,
                'identity': {
                    "username": "seed_A",
                    "username_signature": "MEUCIQC3slOHQ0AgPSyFeas/mxMrmJuF5+itfpxSFAERAjyr4wIgCBMuSOEJnisJ7//Y019vYhIWCWvzvCnfXZRxfbrt2SM=",
                    "public_key": "0286707b29746a434ead4ab94af2d7758d4ae8aaa12fdad9ab42ce3952a8ef798f"
                }
            })

            self.config.seeds = {
                seed_peer.identity.username_signature: seed_peer
            }
        elif self.config.network == 'regnet':

            seed_peer = Seed.from_dict({
                'host': '71.193.201.21',
                'port': 8000,
                'identity': {
                    "username": "seed_A",
                    "username_signature": "MEUCIQC3slOHQ0AgPSyFeas/mxMrmJuF5+itfpxSFAERAjyr4wIgCBMuSOEJnisJ7//Y019vYhIWCWvzvCnfXZRxfbrt2SM=",
                    "public_key": "0286707b29746a434ead4ab94af2d7758d4ae8aaa12fdad9ab42ce3952a8ef798f"
                }
            })

            self.config.seeds = {
                seed_peer.identity.username_signature: seed_peer
            }

    def init_seed_gateways(self):
        if self.config.network == 'mainnet':

            seed_gateway_peer = SeedGateway.from_dict({
                'host': '71.193.201.21',
                'port': 8001,
                'identity': {
                    "username": "seed_gateway_A",
                    "username_signature": "MEQCIEvShxHewQt9u/4+WlcjSubCfsjOmvq8bRoU6t/LGmdLAiAQyr5op3AZj58NzRDthvq7bEouwHhEzis5ZYKlE6D0HA==",
                    "public_key": "03e8b4651a1e794998c265545facbab520131cdddaea3da304a36279b1d334dfb1"
                }
            })

            self.config.seed_gateways = {
                seed_gateway_peer.identity.username_signature: seed_gateway_peer
            }
        elif self.config.network == 'regnet':

            seed_gateway_peer = SeedGateway.from_dict({
                'host': '71.193.201.21',
                'port': 8001,
                'identity': {
                    "username": "seed_gateway_A",
                    "username_signature": "MEQCIEvShxHewQt9u/4+WlcjSubCfsjOmvq8bRoU6t/LGmdLAiAQyr5op3AZj58NzRDthvq7bEouwHhEzis5ZYKlE6D0HA==",
                    "public_key": "03e8b4651a1e794998c265545facbab520131cdddaea3da304a36279b1d334dfb1"
                }
            })

            self.config.seed_gateways = {
                seed_gateway_peer.identity.username_signature: seed_gateway_peer
            }

    def init_service_providers(self):
        if self.config.network == 'mainnet':

            service_provider_peer = ServiceProvider.from_dict({
                'host': '71.193.201.21',
                'port': 8002,
                'identity': {
                    "username": "service_provider_A",
                    "username_signature": "MEUCIQCIzIDpRwBJgU0fjTh6FZhpIrLz/WNTLIZwK2Ifx7HjtQIgfYYOPFy7ypU+KYeYzkCa9OWwbwPIt9Hk0cV8Q6pcXog=",
                    "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7"
                }
            })

            self.config.service_providers = {
                service_provider_peer.identity.username_signature: service_provider_peer
            }
        elif self.config.network == 'regnet':

            service_provider_peer = ServiceProvider.from_dict({
                'host': '71.193.201.21',
                'port': 8002,
                'identity': {
                    "username": "service_provider_A",
                    "username_signature": "MEUCIQCIzIDpRwBJgU0fjTh6FZhpIrLz/WNTLIZwK2Ifx7HjtQIgfYYOPFy7ypU+KYeYzkCa9OWwbwPIt9Hk0cV8Q6pcXog=",
                    "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7"
                }
            })

            self.config.service_providers = {
                service_provider_peer.identity.username_signature: service_provider_peer
            }

    def init_http(self):
        self.config.app_log.info("API: http://{}".format(self.config.peer.to_string()))
        self.config.app_log.info("Starting server on {}:{}".format(self.config.serve_host, self.config.serve_port))
        core_handlers_enabled = False
        plugins_enabled = False
        self.default_handlers = []
        if core_handlers_enabled:
            static_path = path.join(path.dirname(__file__), 'static')
            self.default_handlers.extend([
                (r"/app/(.*)", StaticFileHandler, {"path": path.join(static_path, 'app')}),
                (r"/app2fa/(.*)", StaticFileHandler, {"path": path.join(static_path, 'app2fa')}),
                (r"/(apple-touch-icon\.png)", StaticFileHandler, dict(path=static_path)),
            ])
            self.default_handlers.extend(NODE_HANDLERS)
            self.default_handlers.extend(GRAPH_HANDLERS)
            self.default_handlers.extend(EXPLORER_HANDLERS)
            self.default_handlers.extend(WALLET_HANDLERS)
            self.default_handlers.extend(WEB_HANDLERS)

        if plugins_enabled:
            for finder, name, ispkg in pkgutil.iter_modules([path.join(path.dirname(__file__), 'plugins')]):
                handlers = importlib.import_module('plugins.' + name + '.handlers')
                self.default_handlers.extend(handlers.HANDLERS)
        
            self.default_handlers.insert(0, handlers.HANDLERS[0])  # replace / root handler

        settings = dict(
            app_title=u"Yadacoin Node",
            template_path=path.join(path.dirname(__file__), 'templates'),
            xsrf_cookies=False,  # TODO: sort out, depending on python client version (< 3.6) does not work with xsrf activated
            cookie_secret=sha256(self.config.private_key.encode('utf-8')).hexdigest(),
            compress_response=True,
            debug=options.debug,  # Also activates auto reload
            autoreload=False,
            serve_traceback=options.debug,
            yadacoin_vars={'node_version': __version__},
            yadacoin_config=self.config,
            mp=None,
            version=__version__,
            protocol_version=PROTOCOL_VERSION,
            BU=yadacoin.core.blockchainutils.GLOBAL_BU,
            TU=yadacoin.core.transactionutils.TU
        )
        handlers = self.default_handlers.copy()
        self.app = super().__init__(handlers, **settings)
        self.listen(self.config.serve_port, self.config.serve_host)
        if self.config.ssl:
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile=self.config.ssl.get('cafile'))
            ssl_ctx.load_cert_chain(self.config.ssl.get('certfile'), keyfile=self.config.ssl.get('keyfile'))
            http_server = tornado.httpserver.HTTPServer(self.app, ssl_options=ssl_ctx)
            http_server.listen(self.config.ssl['port'])
            webbrowser.open("http://{}/appvote/identity".format(self.config.peer.to_string()))

    def init_pool(self):
        if self.config.max_miners > 0:
            self.config.app_log.info("MiningPool activated, max miners {}".format(self.config.max_miners))
            server = StratumServer()
            server.listen(self.config.stratum_pool_port)

    def init_peer(self):
        Peer.create_upnp_mapping(self.config)
        
        my_peer = {
            'host': self.config.peer_host,
            'port': self.config.peer_port,
            'identity': {
                "username": self.config.username,
                "username_signature": self.config.username_signature,
                "public_key": self.config.public_key
            },
            'peer_type': self.config.peer_type
        }

        if my_peer.get('peer_type') == 'seed':
            self.config.peer = Seed.from_dict(my_peer)
        elif my_peer.get('peer_type') == 'seed_gateway':
            self.config.peer = SeedGateway.from_dict(my_peer)
        elif my_peer.get('peer_type') == 'service_provider':
            self.config.peer = ServiceProvider.from_dict(my_peer)
        elif my_peer.get('peer_type') == 'user' or True: # default if not specified
            self.config.peer = User.from_dict(my_peer)

    def init_config_properties(self):
        self.config.mongo = Mongo()
        self.config.http_client = AsyncHTTPClient()
        self.config.BU = yadacoin.core.blockchainutils.BlockChainUtils()
        self.config.TU = yadacoin.core.transactionutils.TU
        yadacoin.core.blockchainutils.set_BU(self.config.BU)  # To be removed
        self.config.GU = GraphUtils()
        self.config.consensus = None
        self.config.cipher = Crypt(self.config.wif)
        self.config.pyrx = pyrx.PyRX()
        self.config.nodeServer = NodeSocketServer
        self.config.nodeClient = NodeSocketClient(
            self.config.nodeServer.sockets,
            self.config.nodeServer.pending
        )
        self.config.LatestBlock = LatestBlock
        self.config.app_log = logging.getLogger('tornado.application')
        if self.config.peer_type != 'user':
            self.config.nodeServer().listen(self.config.peer_port)

if __name__ == "__main__":
    NodeApplication()
