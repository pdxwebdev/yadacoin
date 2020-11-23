"""
Async Yadacoin node poc
"""
import importlib
import pkgutil
import json
import logging
import os
import ssl
import ntpath
import webbrowser
import pyrx
from traceback import format_exc
from asyncio import sleep as async_sleep
from hashlib import sha256
from logging.handlers import RotatingFileHandler
from os import path
from sys import exit, stdout
from time import time
from Crypto.PublicKey.ECC import EccKey
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
import socketio
import tornado.ioloop
import tornado.locks
import tornado.log
# from tornado.log import LogFormatter
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer
from tornado.options import define, options
from tornado.web import Application, StaticFileHandler
from concurrent.futures import ThreadPoolExecutor
from bson.objectid import ObjectId
import yadacoin.blockchainutils
import yadacoin.transactionutils
import yadacoin.config
from yadacoin.crypt import Crypt
from yadacoin.consensus import Consensus
from yadacoin.chain import CHAIN
from yadacoin.explorerhandlers import EXPLORER_HANDLERS
from yadacoin.graphhandlers import GRAPH_HANDLERS
from yadacoin.graphutils import GraphUtils
from yadacoin.mongo import Mongo
from yadacoin.nodehandlers import NODE_HANDLERS
from yadacoin.peers import Peer, Peers
from yadacoin.poolhandlers import POOL_HANDLERS
from yadacoin.miningpoolpayout import PoolPayer
from yadacoin.wallethandlers import WALLET_HANDLERS
from yadacoin.webhandlers import WEB_HANDLERS
from yadacoin.yadawebsockethandler import get_sio, ws_init
from yadacoin.transactionbroadcaster import TxnBroadcaster
from yadacoin.nsbroadcaster import NSBroadcaster
from yadacoin.stratumpool import StratumServer

__version__ = '0.0.13'

PROTOCOL_VERSION = 2

app_log = None
access_log = None
config = None


class NodeApplication(Application):

    def __init__(self, config, mongo, peers):
        static_path = path.join(path.dirname(__file__), 'static')
        self.default_handlers = [
            (r"/app/(.*)", StaticFileHandler, {"path": path.join(static_path, 'app')}),
            (r"/app2fa/(.*)", StaticFileHandler, {"path": path.join(static_path, 'app2fa')}),
            (r"/appvotestatic/(.*)", StaticFileHandler, {"path": path.join(static_path, 'appvotestatic')}),
            (r"/(apple-touch-icon\.png)", StaticFileHandler, dict(path=static_path)),
            (r"/socket.io/", socketio.get_tornado_handler(get_sio()))
        ]
        self.default_handlers.extend(NODE_HANDLERS)
        self.default_handlers.extend(GRAPH_HANDLERS)
        # TODO: use config to enable/disable specific routes
        self.default_handlers.extend(EXPLORER_HANDLERS)
        if config.max_miners > 0:
            self.default_handlers.extend(POOL_HANDLERS)
        self.default_handlers.extend(WALLET_HANDLERS)

        for finder, name, ispkg in pkgutil.iter_modules([path.join(path.dirname(__file__), 'plugins')]):
            handlers = importlib.import_module('plugins.' + name + '.handlers')
            self.default_handlers.extend(handlers.HANDLERS)

        self.default_handlers.extend(WEB_HANDLERS)
        settings = dict(
            app_title=u"Yadacoin Node",
            template_path=path.join(path.dirname(__file__), 'templates'),
            xsrf_cookies=False,  # TODO: sort out, depending on python client version (< 3.6) does not work with xsrf activated
            cookie_secret=sha256(config.private_key.encode('utf-8')).hexdigest(),
            compress_response=True,
            debug=options.debug,  # Also activates auto reload
            autoreload=False,
            serve_traceback=options.debug,
            yadacoin_vars={'node_version': __version__},
            yadacoin_config=config,
            mp = None,
            mongo=mongo,
            peers=peers,
            version= __version__,
            protocol_version=PROTOCOL_VERSION,
            BU=yadacoin.blockchainutils.GLOBAL_BU,
            TU=yadacoin.transactionutils.TU
        )
        handlers = self.default_handlers.copy()
        super().__init__(handlers, **settings)


async def background_consensus():
    if config.consensus_busy:
        return
    config.consensus_busy = True
    if config.polling <= 0:
        app_log.warning("No consensus polling")
        return
    again = True
    while again:
        again = await config.consensus.sync_bottom_up()
    config.consensus_busy = False
    app_log.warning("{} in Background_consensus".format(again))


async def background_peers():
    """Peers management coroutine. responsible for peers testing and outgoing connections"""
    try:
        if config.peers_busy:
            return
        config.peers_busy = True
        if len(config.peers.peers) <= 50:
            # no need to waste resources if we have enough peers
            # log.info('Should test peers')
            await config.peers.test_some(count=2)
        await config.peers.check_outgoing()
        config.peers_busy = False
    except Exception as e:
        app_log.error("{} in Background_peers".format(e))


async def background_status():
    """This background co-routine is responsible for status collection and display"""
    try:
        # status = {"peers": config.peers.get_status()}
        if config.status_busy:
            return
        config.status_busy = True
        status = config.get_status()
        # print(status)
        app_log.info(json.dumps(status))
        config.status_busy = False
    except Exception as e:
        app_log.error("{} in Background_status".format(e))


async def background_transaction_broadcast():
    """This background co-routine is responsible for disseminating transactions to the network"""
    if config.txn_broadcast_busy:
        return
    config.txn_broadcast_busy = True
    tb = TxnBroadcaster(config)
    tb2 = TxnBroadcaster(config, config.SIO.namespace_handlers['/chat'])
    try:
        # status = {"peers": config.peers.get_status()}

        async for txn in config.mongo.async_db.miner_transactions.find({}).sort([('time', -1)]).limit(20):
            await config.mongo.async_db.miner_transactions.delete_many({
                '_id': {'$ne': ObjectId(txn['_id'])},
                'id': txn['id']
            })
            await tb.txn_broadcast_job(txn, txn.get('sent_to'))
            await tb2.txn_broadcast_job(txn, txn.get('sent_to'))
        config.txn_broadcast_busy = False
    except Exception as e:
        app_log.error("{} in background_transaction_broadcast".format(e))


async def background_ns_broadcast():
    """This background co-routine is responsible for disseminating name server records to the network"""
    if config.ns_broadcast_busy:
        return
    config.ns_broadcast_busy = True
    nb = NSBroadcaster(config)
    nb2 = NSBroadcaster(config, config.SIO.namespace_handlers['/chat'])
    try:
        # status = {"peers": config.peers.get_status()}

        async for ns in config.mongo.async_db.name_server.find({}).limit(20):
            await nb.ns_broadcast_job(ns.get('txn'), ns.get('sent_to'))
            await nb2.ns_broadcast_job(ns.get('txn'), ns.get('sent_to'))
        config.ns_broadcast_busy = False
    except Exception as e:
        app_log.error("{} in background_ns_broadcast".format(e))


async def background_pool():
    """Responsible for miner updates"""
    """
    New blocks will directly trigger the correct event.
    This co-routine checks if new transactions have been received, or if special_min is triggered,
    So we can update the miners.
    """
    try:
        if config.pool_busy:
            return
        config.pool_busy = True
        await StratumServer.block_checker()
    except Exception as e:
        app_log.warning("{}".format(format_exc()))
        app_log.error("{} in background_pool".format(e))
    config.pool_busy = False


async def background_pool_payer():
    """Responsible for paying miners"""
    """
    New blocks will directly trigger the correct event.
    This co-routine checks if new transactions have been received, or if special_min is triggered,
    So we can update the miners.
    """
    try:
        if config.pool_payer_busy:
            return
        config.pool_payer_busy = True
        if config.pp:
            await config.pp.do_payout()

        config.pool_payer_busy = False
    except Exception as e:
        app_log.error("{} in background_pool_payer".format(e))

async def background_cache_validator():
    """Responsible for validating the cache and clearing it when necessary"""
    if config.cache_busy:
        return
    config.cache_busy = True
    if not hasattr(config, 'cache_inited'):
        config.cache_collections = [x for x in await config.mongo.async_db.list_collection_names({}) if x.endswith('_cache')]
        config.cache_last_times = {}
        try:
            async for x in config.mongo.async_db.blocks.find({'updated_at': {'$exists': False}}):
                config.mongo.async_db.blocks.update_one({'index': x['index']}, {'$set': {'updated_at': time()}})
            for cache_collection in config.cache_collections:
                config.cache_last_times[cache_collection] = 0
                await config.mongo.async_db[cache_collection].delete_many({'cache_time': {'$exists': False}})
            config.cache_inited = True
        except Exception as e:
            app_log.error("{} in background_cache_validator init".format(e))

    """
    We check for cache items that are not currently in the blockchain
    If not, we delete the cached item.
    """
    try:
        for cache_collection in config.cache_collections:
            if not config.cache_last_times.get(cache_collection):
                latest = await config.mongo.async_db[cache_collection].find_one({
                    'cache_time': {'$gt': config.cache_last_times[cache_collection]}
                }, sort=[('height', -1)])
                if latest:
                    config.cache_last_times[cache_collection] = latest['cache_time']
                else:
                    config.cache_last_times[cache_collection] = 0
            async for txn in config.mongo.async_db[cache_collection].find({
                'cache_time': {'$gt': config.cache_last_times[cache_collection]}
            }).sort([('height', -1)]):
                if not await config.mongo.async_db.blocks.find_one({
                    'index': txn.get('height'),
                    'hash': txn.get('block_hash')
                }) and not await config.mongo.async_db.miner_transactions.find_one({
                    'id': txn.get('id'),
                }):
                    await config.mongo.async_db[cache_collection].delete_many({
                        'height': txn.get('height')
                    })
                    break
                else:
                    if txn['cache_time'] > config.cache_last_times[cache_collection]:
                        config.cache_last_times[cache_collection] = txn['cache_time']

        config.cache_busy = False
    except Exception as e:
        app_log.error("error in background_cache_validator")
        app_log.error(format_exc())


def configure_logging():
    global app_log, access_log
    ch = logging.StreamHandler(stdout)
    ch.setLevel(logging.INFO)
    if options.debug:
        ch.setLevel(logging.DEBUG)
    # tornado.log.enable_pretty_logging()
    app_log = logging.getLogger("tornado.application")
    tornado.log.enable_pretty_logging(logger=app_log)
    # app_log.addHandler(ch)
    logfile = path.abspath("yada_app.log")
    # Rotate log after reaching 512K, keep 5 old copies.
    rotateHandler = RotatingFileHandler(logfile, "a", 512 * 1024, 5)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    rotateHandler.setFormatter(formatter)
    app_log.addHandler(rotateHandler)
    if options.debug:
        app_log.setLevel(logging.DEBUG)

    access_log = logging.getLogger("tornado.access")
    tornado.log.enable_pretty_logging()
    logfile2 = path.abspath("yada_access.log")
    rotateHandler2 = RotatingFileHandler(logfile2, "a", 512 * 1024, 5)
    formatter2 = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    rotateHandler2.setFormatter(formatter2)
    access_log.addHandler(rotateHandler2)
    """
    asyncio_log = logging.getLogger("asyncio")
    tornado.log.enable_pretty_logging()
    logfile3 = path.abspath("yada_asyncio.log")
    rotateHandler3 = RotatingFileHandler(logfile3, "a", 512 * 1024, 5)
    formatter3 = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    rotateHandler3.setFormatter(formatter3)
    access_log.addHandler(rotateHandler3)
    """

    app_log.propagate = False
    access_log.propagate = False
    # This logguer config is quite a mess, but works well enough for the time being.
    logging.getLogger("engineio").propagate = False
    logging.getLogger("socketio").propagate = False
    logging.getLogger("asyncio").propagate = False
    logging.basicConfig(level=logging.DEBUG)


def main():
    global config

    define("debug", default=False, help="debug mode", type=bool)
    define("verbose", default=False, help="verbose mode", type=bool)
    define("network", default='', help="Force mainnet, testnet or regnet", type=str)
    define("reset", default=False, help="If blockchain is invalid, truncate at error block", type=bool)
    define("config", default='config/config.json', help="Config file location, default is 'config/config.json'",
           type=str)
    define("verify", default=True, help="Verify chain, default True", type=bool)
    define("webonly", default=False, help="Web only (ignores node processes for faster init when restarting server frequently), default False", type=bool)
    define("disable-web", default=False, help="Disable web server", type=bool)

    options.parse_command_line(final=False)
    configure_logging()

    if not path.isfile(options.config):
        app_log.error("no config file found at '{}'. Generating new...".format(options.config))
        config = yadacoin.config.Config.generate()
        try:
            os.makedirs(os.path.dirname(options.config))
        except:
            pass
        with open(options.config, 'w') as f:
            config.force_polling = [{"host": "34.237.46.10","port": 80 }]
            f.write(config.to_json())

    with open(options.config) as f:
        config = yadacoin.config.Config(json.loads(f.read()))
        # Sets the global var for all objects
        yadacoin.config.CONFIG = config
        config.debug = options.debug
        # force network, command line one takes precedence
        if options.network != '':
            config.network = options.network
        config.protocol_version = PROTOCOL_VERSION
    if not config.peer_host:
        app_log.error("peer_host cannot be blank in config. Set it to you public ip address")
        return exit()
    

    jwt_key = EccKey(curve='p256', d=int(config.private_key, 16))
    config.jwt_secret_key = jwt_key.export_key(format='PEM')
    config.jwt_public_key = config.jwt_public_key or jwt_key.public_key().export_key(format='PEM')
    config.jwt_options = {
        'verify_signature': True,
        'verify_exp': True,
        'verify_nbf': False,
        'verify_iat': True,
        'verify_aud': False
    }

    config.cipher = Crypt(config.wif)

    config.pyrx = pyrx.PyRX()
    import binascii
    config.pyrx.get_rx_hash('header', binascii.unhexlify('4181a493b397a733b083639334bc32b407915b9a82b7917ac361816f0a1f5d4d'), 4)
    config.reset = options.reset

    config.disable_web = options.disable_web

    api_whitelist = 'api_whitelist.json'
    api_whitelist_filename = options.config.replace(ntpath.basename(options.config), api_whitelist)
    if path.isfile(api_whitelist_filename):
        with open(api_whitelist_filename) as f:
            config.api_whitelist = [x['host'] for x in json.loads(f.read())]
    # get seed.json from same dir as config.
    if config.network != 'regnet':
        if config.network == 'mainnet':
            seed_filename = 'seed.json'
        elif config.network == 'testnet':
            seed_filename = 'seed_testnet.json'
        peers_seed_filename = options.config.replace(ntpath.basename(options.config), seed_filename)
        if path.isfile(peers_seed_filename):
            with open(peers_seed_filename) as f:
                config.peers_seed = json.loads(f.read())
        else:
            try:
                os.makedirs(os.path.dirname(peers_seed_filename))
            except:
                pass
            with open(peers_seed_filename, 'w') as f:
                f.write(json.dumps([
                    {"host": "34.237.46.10","port": 80 },
                    {"host": "51.15.86.249","port": 8000 },
                    {"host": "178.32.96.27","port": 8000 },
                    {"host": "188.165.250.78","port": 8000 },
                    {"host": "116.203.24.126","port": 8000 }
                ], indent=4))
            with open(peers_seed_filename) as f:
                config.peers_seed = json.loads(f.read())

    mongo = Mongo()
    config.mongo = mongo
    peers = Peers()
    config.peers = peers

    config.http_client = AsyncHTTPClient()

    if not options.webonly:
        config.BU = yadacoin.blockchainutils.BlockChainUtils()
        config.TU = yadacoin.transactionutils.TU
        yadacoin.blockchainutils.set_BU(config.BU)  # To be removed
        config.GU = GraphUtils()

        config.consensus = None

        tornado.ioloop.IOLoop.current().set_default_executor(ThreadPoolExecutor(max_workers=1))

        if config.max_miners > 0:
            app_log.info("MiningPool activated, max miners {}".format(config.max_miners))
            tornado.ioloop.PeriodicCallback(background_pool, 3000).start()
            config.pool_busy = False
            server = StratumServer()
            server.listen(config.stratum_pool_port)
        else:
            app_log.info("MiningPool disabled by config")

        ws_init()
        config.SIO = get_sio()

        tornado.ioloop.PeriodicCallback(background_consensus, 30000).start()
        config.consensus_busy = False
        if config.network != 'regnet':
            tornado.ioloop.PeriodicCallback(background_peers, 30000).start()
            config.peers_busy = False
            tornado.ioloop.PeriodicCallback(background_transaction_broadcast, 10000).start()
            config.txn_broadcast_busy = False
            tornado.ioloop.PeriodicCallback(background_ns_broadcast, 120000).start()
            config.ns_broadcast_busy = False
        tornado.ioloop.PeriodicCallback(background_status, 30000).start()
        config.status_busy = False
        tornado.ioloop.PeriodicCallback(background_cache_validator, 30000).start()
        config.cache_busy = False
        if config.pool_payout:
            app_log.info("PoolPayout activated")
            pp = PoolPayer()
            config.pp = pp
            tornado.ioloop.PeriodicCallback(background_pool_payer, 120000).start()
            config.pool_payer_busy = False

    my_peer = Peer.init_my_peer(config.network)
    if not config.disable_web:
        app_log.info("API: http://{}".format(my_peer.to_string()))
        app = NodeApplication(config, mongo, peers)
        app_log.info("Starting server on {}:{}".format(config.serve_host, config.serve_port))
        app.listen(config.serve_port, config.serve_host)
        if config.ssl:
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile=config.ssl.get('cafile'))
            ssl_ctx.load_cert_chain(config.ssl.get('certfile'), keyfile=config.ssl.get('keyfile'))
            http_server = tornado.httpserver.HTTPServer(app, ssl_options=ssl_ctx)
            http_server.listen(config.ssl['port'])
            webbrowser.open("http://{}/appvote/identity".format(my_peer.to_string()))

    config.consensus = Consensus(config.debug, config.peers)
    if options.verify:
        app_log.info("Verifying existing blockchain")
        tornado.ioloop.IOLoop.current().run_sync(config.consensus.async_init)
        tornado.ioloop.IOLoop.current().run_sync(config.consensus.verify_existing_blockchain)
    else:
        app_log.info("Verification of existing blockchain skipped by config")

    # The server will simply run until interrupted
    # with Ctrl-C, but if you want to shut down more gracefully,
    # call shutdown_event.set().
    tornado.ioloop.IOLoop.current().start()
    # shutdown_event = tornado.locks.Event()
    # await shutdown_event.wait()


if __name__ == "__main__":
    main()
