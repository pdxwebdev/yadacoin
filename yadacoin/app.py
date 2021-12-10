"""
Async Yadacoin node poc
"""
import sys
import importlib
import pkgutil
import json
import logging
import os
import ssl
import ntpath
import binascii
import socket
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)
from datetime import datetime
from traceback import format_exc
from asyncio import sleep as async_sleep
from hashlib import sha256
from logging.handlers import RotatingFileHandler
from os import path
from sys import exit, stdout
from time import time

import webbrowser
import pyrx
from Crypto.PublicKey.ECC import EccKey
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
import tornado.ioloop
import tornado.locks
import tornado.log
from tornado.iostream import StreamClosedError
from tornado.options import define, options
from tornado.web import Application, StaticFileHandler
from concurrent.futures import ThreadPoolExecutor
from bson.objectid import ObjectId

import yadacoin.core.blockchainutils
import yadacoin.core.transactionutils
import yadacoin.core.config
from yadacoin.core.crypt import Crypt
from yadacoin.core.consensus import Consensus
from yadacoin.core.chain import CHAIN
from yadacoin.core.graphutils import GraphUtils
from yadacoin.core.mongo import Mongo
from yadacoin.core.miningpoolpayout import PoolPayer
from yadacoin.core.miningpool import MiningPool
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.peer import (
    Peer, Seed, SeedGateway, ServiceProvider, User, Miner, Peers, Group
)
from yadacoin.core.identity import Identity
from yadacoin.core.health import Health
from yadacoin.core.smtp import Email
from yadacoin.http.web import WEB_HANDLERS
from yadacoin.http.explorer import EXPLORER_HANDLERS
from yadacoin.http.graph import GRAPH_HANDLERS
from yadacoin.http.node import NODE_HANDLERS
from yadacoin.http.pool import POOL_HANDLERS
from yadacoin.http.wallet import WALLET_HANDLERS
from yadacoin.websocket.base import WEBSOCKET_HANDLERS
from yadacoin.tcpsocket.node import (
    NodeSocketServer, NodeSocketClient, NodeRPC
)
from yadacoin.websocket.base import RCPWebSocketServer
from yadacoin.tcpsocket.pool import StratumServer
from yadacoin import version
from plugins.yadacoinpool import handlers


define("debug", default=False, help="debug mode", type=bool)
define("verbose", default=False, help="verbose mode", type=bool)
define("network", default='', help="Force mainnet, testnet or regnet", type=str)
define("reset", default=False, help="If blockchain is invalid, truncate at error block", type=bool)
define("config", default='config/config.json', help="Config file location, default is 'config/config.json'", type=str)
define("verify", default=False, help="Verify chain, default False", type=bool)
define("server", default=False, help="Is server for testing", type=bool)
define("client", default=False, help="Is client for testing", type=bool)


class NodeApplication(Application):

    def __init__(self, test=False):

        options.parse_command_line(final=False)

        self.init_config(options)
        self.configure_logging()
        self.init_config_properties(test=test)
        if test:
            return
        if 'node' in self.config.modes:
            self.init_seeds()
            self.init_seed_gateways()
            self.init_service_providers()
            self.init_groups()
            self.init_peer()
            self.config.app_log.info("Node: {}:{}".format(self.config.peer_host, self.config.peer_port))
            if 'pool' in self.config.modes:
                self.init_pool()
        if 'web' in self.config.modes:
            if os.path.exists(path.join(path.dirname(__file__), '..', 'static')):
                static_path = path.join(path.dirname(__file__), '..', 'static')
            else:
                static_path = path.join(path.dirname(__file__), 'static') # probably running from binary

            if os.path.exists(path.join(path.join(path.dirname(__file__), '..', 'static'), 'app')):
                static_app_path = path.join(path.join(path.dirname(__file__), '..', 'static'), 'app')
            else:
                static_app_path = path.join(path.join(path.dirname(__file__), 'static'), 'app') # probably running from binary

            self.default_handlers = [
              (r"/app/(.*)", StaticFileHandler, {"path": static_app_path}),
              (r"/yadacoinstatic/(.*)", StaticFileHandler, {"path": static_path}),
            ]
            self.default_handlers.extend(handlers.HANDLERS)
            self.init_websocket()
            self.init_webui()
            self.init_plugins()
            self.init_http()
            self.init_whitelist()
            self.init_jwt()
        self.init_ioloop()

    async def background_consensus(self):
        while True:
            try:
                if self.config.consensus.block_queue.queue:
                    await tornado.gen.sleep(3)
                    continue
                await self.config.consensus.sync_bottom_up()
                await tornado.gen.sleep(3)

            except Exception as e:
                self.config.app_log.error(format_exc())

    async def background_peers(self):
        """Peers management coroutine. responsible for peers testing and outgoing connections"""
        while True:
            try:
                await self.config.peer.ensure_peers_connected()
                self.config.health.peer.last_activity = int(time())
            except:
                self.config.app_log.error(format_exc())

            await tornado.gen.sleep(3)

    async def background_status(self):
        """This background co-routine is responsible for status collection and display"""
        while True:
            try:
                status = await self.config.get_status()
                await self.config.health.check_health()
                status['health'] = self.config.health.to_dict()
                if status['health']['status']:
                    self.config.app_log.info(json.dumps(status, indent=4))
                else:
                    self.config.app_log.warning(json.dumps(status, indent=4))
                self.config.status_busy = False
            except Exception as e:
                self.config.app_log.error(format_exc())

            await tornado.gen.sleep(30)

    async def background_block_checker(self):
        """Responsible for miner updates"""
        """
        New blocks will directly trigger the correct event.
        This co-routine checks if new transactions have been received, or if special_min is triggered,
        So we can update the miners.
        """
        while True:
            try:
                last_block_height = 0
                if LatestBlock.block:
                    last_block_height = LatestBlock.block.index
                await LatestBlock.block_checker()
                if last_block_height != LatestBlock.block.index:
                    self.config.app_log.info('Latest block height: %s | time: %s' % (
                        self.config.LatestBlock.block.index,
                        datetime.fromtimestamp(
                            int(
                                self.config.LatestBlock.block.time
                            )
                        ).strftime("%Y-%m-%d %H:%M:%S")
                    ))

                self.config.health.block_checker.last_activity = int(time())
            except Exception as e:
                self.config.app_log.error(format_exc())

            await tornado.gen.sleep(1)

    async def background_message_sender(self):
        retry_attempts = {}
        while True:
            try:
                for x in list(self.config.nodeServer.retry_messages):
                    message = self.config.nodeServer.retry_messages.get(x)
                    if not message:
                        continue
                    if x not in retry_attempts:
                        retry_attempts[x] = 0
                    retry_attempts[x] += 1
                    for peer_cls in self.config.nodeServer.inbound_streams.keys():
                        if x[0] in self.config.nodeServer.inbound_streams[peer_cls]:
                            if retry_attempts[x] > 10:
                                del self.config.nodeServer.retry_messages[x]
                                await self.remove_peer(self.config.nodeServer.inbound_streams[peer_cls][x[0]])
                                continue
                            if len(x) > 3:
                                await self.config.nodeShared.write_result(self.config.nodeServer.inbound_streams[peer_cls][x[0]], x[1], message, x[3])
                            else:
                                await self.config.nodeShared.write_params(self.config.nodeServer.inbound_streams[peer_cls][x[0]], x[1], message)

                for x in list(self.config.nodeClient.retry_messages):
                    message = self.config.nodeClient.retry_messages.get(x)
                    if not message:
                        continue
                    if x not in retry_attempts:
                        retry_attempts[x] = 0
                    retry_attempts[x] += 1
                    for peer_cls in self.config.nodeClient.outbound_streams.keys():
                        if x[0] in self.config.nodeClient.outbound_streams[peer_cls]:
                            if retry_attempts[x] > 10:
                                del self.config.nodeClient.retry_messages[x]
                                await self.remove_peer(self.config.nodeClient.outbound_streams[peer_cls][x[0]])
                                continue
                            if len(x) > 3:
                                await self.config.nodeShared.write_result(self.config.nodeClient.outbound_streams[peer_cls][x[0]], x[1], message, x[3])
                            else:
                                await self.config.nodeShared.write_params(self.config.nodeClient.outbound_streams[peer_cls][x[0]], x[1], message)

                self.config.health.message_sender.last_activity = int(time())
                await tornado.gen.sleep(10)

            except Exception as e:
                self.config.app_log.error(format_exc())

    async def remove_peer(self, stream):
        stream.close()
        if not hasattr(stream, 'peer'):
            return
        id_attr = getattr(stream.peer, stream.peer.id_attribute)
        if id_attr in self.config.nodeServer.inbound_streams[stream.peer.__class__.__name__]:
            del self.config.nodeServer.inbound_streams[stream.peer.__class__.__name__][id_attr]

        if id_attr in self.config.nodeServer.inbound_pending[stream.peer.__class__.__name__]:
            del self.config.nodeServer.inbound_pending[stream.peer.__class__.__name__][id_attr]

        if id_attr in self.config.nodeClient.outbound_streams[stream.peer.__class__.__name__]:
            del self.config.nodeClient.outbound_streams[stream.peer.__class__.__name__][id_attr]

        if id_attr in self.config.nodeClient.outbound_pending[stream.peer.__class__.__name__]:
            del self.config.nodeClient.outbound_pending[stream.peer.__class__.__name__][id_attr]

    async def background_block_inserter(self):
        while True:
            try:
                await self.config.consensus.process_block_queue()
                self.config.health.block_inserter.last_activity = int(time())
            except:
                self.config.app_log.error(format_exc())

            await tornado.gen.sleep(1)

    async def background_pool_payer(self):
        """Responsible for paying miners"""
        """
        New blocks will directly trigger the correct event.
        This co-routine checks if new transactions have been received, or if special_min is triggered,
        So we can update the miners.
        """
        while True:
            try:
                if self.config.pp:
                    await self.config.pp.do_payout()

                self.config.health.pool_payer.last_activity = int(time())
            except Exception as e:
                self.config.app_log.error(format_exc())

            await tornado.gen.sleep(120)

    async def background_cache_validator(self):
        """Responsible for validating the cache and clearing it when necessary"""
        while True:
            if not hasattr(self.config, 'cache_inited'):
                self.cache_collections = [x for x in await self.config.mongo.async_db.list_collection_names({}) if x.endswith('_cache')]
                self.cache_last_times = {}
                try:
                    async for x in self.config.mongo.async_db.blocks.find({'updated_at': {'$exists': False}}):
                        await self.config.mongo.async_db.blocks.update_one({'index': x['index']}, {'$set': {'updated_at': time()}})
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
                        self.cache_last_times[cache_collection] = 0
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

                self.config.health.cache_validator.last_activity = int(time())
            except Exception as e:
                self.config.app_log.error("error in background_cache_validator")
                self.config.app_log.error(format_exc())

            await tornado.gen.sleep(30)

    async def background_mempool_cleaner(self):
        """Responsible for removing failed transactions from the mempool"""

        while True:
            try:
                await self.config.TU.clean_mempool(self.config)
                await self.config.TU.rebroadcast_mempool(self.config)
                self.config.health.mempool_cleaner.last_activity = int(time())
            except Exception as e:
                self.config.app_log.error(format_exc())

            await tornado.gen.sleep(1200)

    def configure_logging(self):
        # tornado.log.enable_pretty_logging()
        self.config.app_log = logging.getLogger("tornado.application")
        tornado.log.enable_pretty_logging(logger=self.config.app_log)
        logfile = path.abspath("yada_app.log")
        # Rotate log after reaching 512K, keep 5 old copies.
        rotateHandler = RotatingFileHandler(logfile, "a", 512 * 1024, 5)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        rotateHandler.setFormatter(formatter)
        self.config.app_log.addHandler(rotateHandler)
        self.config.app_log.setLevel(logging.INFO)
        if self.config.debug:
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

    def init_config(self, options):
        if not path.isfile(options.config):
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

        self.config.reset = options.reset
        self.config.pyrx = pyrx.PyRX()
        self.config.pyrx.get_rx_hash('header', binascii.unhexlify('4181a493b397a733b083639334bc32b407915b9a82b7917ac361816f0a1f5d4d'), 4)

    def init_consensus(self):
        tornado.ioloop.IOLoop.current().run_sync(self.config.consensus.async_init)
        if self.options.verify:
            self.config.app_log.info("Verifying existing blockchain")
            tornado.ioloop.IOLoop.current().run_sync(self.config.consensus.verify_existing_blockchain)
        else:
            self.config.app_log.info("Verification of existing blockchain skipped by config")

    def init_whitelist(self):
        api_whitelist = 'api_whitelist.json'
        api_whitelist_filename = options.config.replace(ntpath.basename(options.config), api_whitelist)
        if path.isfile(api_whitelist_filename):
            with open(api_whitelist_filename) as f:
                self.config.api_whitelist = [x['host'] for x in json.loads(f.read())]

    def init_ioloop(self):
        tornado.ioloop.IOLoop.current().set_default_executor(ThreadPoolExecutor(max_workers=1))

        if self.config.network != 'regnet' and 'node' in self.config.modes:
            tornado.ioloop.IOLoop.current().spawn_callback(self.background_consensus)

            tornado.ioloop.IOLoop.current().spawn_callback(self.background_peers)

            tornado.ioloop.IOLoop.current().spawn_callback(self.background_status)

            tornado.ioloop.IOLoop.current().spawn_callback(self.background_block_checker)

            tornado.ioloop.IOLoop.current().spawn_callback(self.background_cache_validator)

            tornado.ioloop.IOLoop.current().spawn_callback(self.background_message_sender)

            tornado.ioloop.IOLoop.current().spawn_callback(self.background_block_inserter)

            tornado.ioloop.IOLoop.current().spawn_callback(self.background_mempool_cleaner)

        if self.config.pool_payout:
            self.config.app_log.info("PoolPayout activated")
            self.config.pp = PoolPayer()

            tornado.ioloop.IOLoop.current().spawn_callback(self.background_pool_payer)
        while True:
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
            self.config.seeds = Peers.get_seeds()
        elif self.config.network == 'regnet':
            self.config.seeds = Peers.get_seeds()

    def init_seed_gateways(self):
        if self.config.network == 'mainnet':
            self.config.seed_gateways = Peers.get_seed_gateways()
        elif self.config.network == 'regnet':
            self.config.seed_gateways = Peers.get_seed_gateways()

    def init_service_providers(self):
        if self.config.network == 'mainnet':
            self.config.service_providers = Peers.get_service_providers()
        elif self.config.network == 'regnet':
            self.config.service_providers = Peers.get_service_providers()

    def init_groups(self):
        if self.config.network == 'mainnet':
            self.config.groups = Peers.get_groups()
        elif self.config.network == 'regnet':
            self.config.groups = Peers.get_groups()

    def init_websocket(self):
        self.default_handlers.extend(WEBSOCKET_HANDLERS)

    def init_webui(self):
        self.default_handlers.extend(NODE_HANDLERS)
        self.default_handlers.extend(GRAPH_HANDLERS)
        self.default_handlers.extend(EXPLORER_HANDLERS)
        self.default_handlers.extend(WALLET_HANDLERS)
        self.default_handlers.extend(WEB_HANDLERS)
        self.default_handlers.extend(POOL_HANDLERS)

    def init_plugins(self):
        for finder, name, ispkg in pkgutil.iter_modules([path.join(path.dirname(__file__), '..', 'plugins')]):
            handlers = importlib.import_module('plugins.' + name + '.handlers')
            if name == self.config.root_app:
                [self.default_handlers.insert(0, handler) for handler in handlers.HANDLERS]
            else:
                self.default_handlers.extend(handlers.HANDLERS)

    def init_http(self):
        self.config.app_log.info("API: http://{}:{}".format(self.config.serve_host, self.config.serve_port))
        if 'web' in self.config.modes:
            self.config.app_log.info("Wallet: http://{}:{}/app".format(self.config.serve_host, self.config.serve_port))
        if os.path.exists(path.join(path.dirname(__file__), '..', 'templates')):
            template_path = path.join(path.dirname(__file__), '..', 'templates')
        else:
            template_path = path.join(path.dirname(__file__), 'templates')
        settings = dict(
            app_title=u"Yadacoin Node",
            template_path=template_path,
            xsrf_cookies=False,  # TODO: sort out, depending on python client version (< 3.6) does not work with xsrf activated
            cookie_secret=sha256(self.config.private_key.encode('utf-8')).hexdigest(),
            compress_response=True,
            debug=options.debug,  # Also activates auto reload
            autoreload=False,
            serve_traceback=options.debug,
            yadacoin_vars={'node_version': version},
            yadacoin_config=self.config,
            mp=None,
            BU=yadacoin.core.blockchainutils.GLOBAL_BU,
            TU=yadacoin.core.transactionutils.TU
        )
        handlers = self.default_handlers.copy()
        super().__init__(handlers, **settings)
        self.config.application = self
        self.config.http_server = tornado.httpserver.HTTPServer(self)
        self.config.http_server.listen(self.config.serve_port, self.config.serve_host)
        if hasattr(self.config, 'ssl') and self.config.ssl.is_valid():
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile=self.config.ssl.ca_file)
            ssl_ctx.load_cert_chain(self.config.ssl.cert_file, keyfile=self.config.ssl.key_file)
            self.config.https_server = tornado.httpserver.HTTPServer(self, ssl_options=ssl_ctx)
            self.config.https_server.listen(self.config.ssl.port)
        if hasattr(self.config, 'email') and self.config.email.is_valid():
            self.config.emailer = Email()

    def init_pool(self):
        self.config.app_log.info("Pool: {}:{}".format(self.config.peer_host, self.config.stratum_pool_port))
        StratumServer.inbound_streams[Miner.__name__] = {}
        self.config.pool_server = StratumServer()
        self.config.pool_server.listen(self.config.stratum_pool_port)

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
            'peer_type': self.config.peer_type,
            'http_host': self.config.ssl.common_name or self.config.peer_host,
            'http_port': self.config.ssl.port or self.config.serve_port,
            'secure': self.config.ssl.is_valid(),
            'protocol_version': 3
        }

        if my_peer.get('peer_type') == 'seed':
            if not self.config.username_signature in self.config.seeds:
                raise Exception('You are not a valid SeedGateway. Could not find you in the list of SeedGateways')
            my_peer['seed_gateway'] = self.config.seeds[self.config.username_signature].seed_gateway
            self.config.peer = Seed.from_dict(my_peer, is_me=True)
        elif my_peer.get('peer_type') == 'seed_gateway':
            if not self.config.username_signature in self.config.seed_gateways:
                raise Exception('You are not a valid SeedGateway. Could not find you in the list of SeedGateways')
            my_peer['seed'] = self.config.seed_gateways[self.config.username_signature].seed
            self.config.peer = SeedGateway.from_dict(my_peer, is_me=True)
        elif my_peer.get('peer_type') == 'service_provider':
            self.config.peer = ServiceProvider.from_dict(my_peer, is_me=True)
        elif my_peer.get('peer_type') == 'user' or True: # default if not specified
            self.config.peer = User.from_dict(my_peer, is_me=True)

    def init_config_properties(self, test=False):
        self.config.health = Health()
        self.config.mongo = Mongo()
        self.config.http_client = AsyncHTTPClient()
        self.config.BU = yadacoin.core.blockchainutils.BlockChainUtils()
        self.config.TU = yadacoin.core.transactionutils.TU
        yadacoin.core.blockchainutils.set_BU(self.config.BU)  # To be removed
        self.config.GU = GraphUtils()
        self.config.LatestBlock = LatestBlock
        if test:
            return
        tornado.ioloop.IOLoop.current().run_sync(self.config.LatestBlock.block_checker)
        self.config.consensus = tornado.ioloop.IOLoop.current().run_sync(Consensus.init_async)
        self.config.cipher = Crypt(self.config.wif)
        if 'node' in self.config.modes:
            self.config.nodeServer = NodeSocketServer
            self.config.nodeShared = NodeRPC()
            self.config.nodeClient = NodeSocketClient()

            for x in [Seed, SeedGateway, ServiceProvider, User, Miner]:
                if x.__name__ not in self.config.nodeClient.outbound_streams:
                    self.config.nodeClient.outbound_ignore[x.__name__] = {}
                if x.__name__ not in self.config.nodeClient.outbound_streams:
                    self.config.nodeClient.outbound_pending[x.__name__] = {}
                if x.__name__ not in self.config.nodeClient.outbound_streams:
                    self.config.nodeClient.outbound_streams[x.__name__] = {}
            for x in [Seed, SeedGateway, ServiceProvider, User, Miner]:
                if x.__name__ not in self.config.nodeServer.inbound_pending:
                    self.config.nodeServer.inbound_pending[x.__name__] = {}
                if x.__name__ not in self.config.nodeServer.inbound_streams:
                    self.config.nodeServer.inbound_streams[x.__name__] = {}
            self.config.node_server_instance = self.config.nodeServer()
            self.config.node_server_instance.bind(self.config.peer_port, family=socket.AF_INET)
            self.config.node_server_instance.start(1)

        self.config.websocketServer = RCPWebSocketServer
        self.config.app_log = logging.getLogger('tornado.application')
        if 'web' in self.config.modes:
            for x in [User, Group]:
                if x.__name__ not in self.config.websocketServer.inbound_streams:
                    self.config.websocketServer.inbound_streams[x.__name__] = {}

if __name__ == "__main__":
    NodeApplication()
