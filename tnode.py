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
from asyncio import sleep as async_sleep
from hashlib import sha256
from logging.handlers import RotatingFileHandler
from os import path
from sys import exit, stdout
from time import time

import socketio
import tornado.ioloop
import tornado.locks
import tornado.log
# from tornado.log import LogFormatter
from tornado.options import define, options
from tornado.web import Application, StaticFileHandler

import yadacoin.blockchainutils
import yadacoin.transactionutils
import yadacoin.config
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

try:
    from plugins.yadacoinweb.handlers import HANDLERS as YCW_HANDLERS
except:
    pass

__version__ = '0.0.13'

PROTOCOL_VERSION = 2

app_log = None
access_log = None
config = None


class NodeApplication(Application):

    def __init__(self, config, mongo, peers):
        static_path = path.join(path.dirname(__file__), 'static')
        self.default_handlers = [
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
        
        try:
            self.default_handlers.extend(YCW_HANDLERS)
        except:
            pass

        self.default_handlers.extend(WEB_HANDLERS)
        settings = dict(
            app_title=u"Yadacoin Node",
            template_path=path.join(path.dirname(__file__), 'templates'),
            xsrf_cookies=False,  # TODO: sort out, depending on python client version (< 3.6) does not work with xsrf activated
            cookie_secret=sha256(config.private_key.encode('utf-8')).hexdigest(),
            compress_response=True,
            debug=options.debug,  # Also activates auto reload
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


async def background_consensus(consensus):
    if config.polling <= 0:
        app_log.error("No consensus polling")
        return
    await async_sleep(5)
    while True:
        try:
            wait = await consensus.sync_bottom_up()
            if wait:
                await async_sleep(config.polling)
        except Exception as e:
            app_log.error("{} in Background_consensus".format(e))


async def background_peers(peers: Peers):
    """Peers management coroutine. responsible for peers testing and outgoing connections"""
    while True:
        try:
            await async_sleep(10)  # Could be a config item
            if len(peers.peers) <= 50:
                # no need to waste resources if we have enough peers
                # log.info('Should test peers')
                await peers.test_some(count=2)
            await peers.check_outgoing()
        except Exception as e:
            app_log.error("{} in Background_peers".format(e))


async def background_status():
    """This background co-routine is responsible for status collection and display"""
    while True:
        try:
            await async_sleep(30)
            # status = {"peers": config.peers.get_status()}
            status = config.get_status()
            # print(status)
            app_log.info(json.dumps(status))
        except Exception as e:
            app_log.error("{} in Background_status".format(e))


async def background_transaction_broadcast():
    """This background co-routine is responsible for status collection and display"""
    tb = TxnBroadcaster(config)
    tb2 = TxnBroadcaster(config, config.SIO.namespace_handlers['/chat'])
    while True:
        try:
            await async_sleep(30)
            # status = {"peers": config.peers.get_status()}

            async for txn in config.mongo.async_db.miner_transactions.find({}):
                await tb.txn_broadcast_job(txn, txn.get('sent_to'))
                await tb2.txn_broadcast_job(txn, txn.get('sent_to'))
        except Exception as e:
            app_log.error("{} in background_transaction_broadcast".format(e))


async def background_pool():
    """Responsible for miner updates"""
    while True:
        """
        New blocks will directly trigger the correct event.
        This co-routine checks if new transactions have been received, or if special_min is triggered,
        So we can update the miners.
        """
        try:
            await async_sleep(10)
            if config.mp:
                await config.mp.check_block_evolved()

        except Exception as e:
            app_log.error("{} in background_pool".format(e))


async def background_pool_payer():
    """Responsible for paying miners"""
    while True:
        """
        New blocks will directly trigger the correct event.
        This co-routine checks if new transactions have been received, or if special_min is triggered,
        So we can update the miners.
        """
        try:
            await async_sleep(10)
            if config.pp:
                await config.pp.do_payout()

        except Exception as e:
            app_log.error("{} in background_pool_payer".format(e))


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

    app_log.propagate = False
    access_log.propagate = False
    # This logguer config is quite a mess, but works well enough for the time being.
    logging.getLogger("engineio").propagate = False
    logging.getLogger("socketio").propagate = False


async def main():
    global config

    define("debug", default=False, help="debug mode", type=bool)
    define("verbose", default=False, help="verbose mode", type=bool)
    define("network", default='', help="Force mainnet, testnet or regnet", type=str)
    define("reset", default=False, help="If blockchain is invalid, truncate at error block", type=bool)
    define("config", default='config/config.json', help="Config file location, default is 'config/config.json'",
           type=str)
    define("verify", default=True, help="Verify chain, default True", type=bool)
    define("webonly", default=False, help="Web only (ignores node processes for faster init when restarting server frequently), default False", type=bool)

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

    config.jwt_secret_key = "my_secret_key"
    config.jwt_options = {
        'verify_signature': True,
        'verify_exp': True,
        'verify_nbf': False,
        'verify_iat': True,
        'verify_aud': False
    }

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

    if not options.webonly:
        config.BU = yadacoin.blockchainutils.BlockChainUtils()
        config.TU = yadacoin.transactionutils.TU
        yadacoin.blockchainutils.set_BU(config.BU)  # To be removed
        config.GU = GraphUtils()

        consensus = Consensus(options.debug, peers)
        if options.verify:
            app_log.info("Verifying existing blockchain")
            consensus.verify_existing_blockchain(reset=options.reset)
        else:
            app_log.info("Verification of existing blockchain skipped by config")
        config.consensus = consensus

        if config.max_miners > 0:
            app_log.info("MiningPool activated, max miners {}".format(config.max_miners))
        else:
            app_log.info("MiningPool disabled by config")

        ws_init()
        config.SIO = get_sio()

        tornado.ioloop.IOLoop.instance().add_callback(background_consensus, consensus)
        tornado.ioloop.IOLoop.instance().add_callback(background_peers, peers)
        tornado.ioloop.IOLoop.instance().add_callback(background_status)
        tornado.ioloop.IOLoop.instance().add_callback(background_pool)
        tornado.ioloop.IOLoop.instance().add_callback(background_transaction_broadcast)
        if config.pool_payout:
            app_log.info("PoolPayout activated")
            pp = PoolPayer()
            config.pp = pp
            tornado.ioloop.IOLoop.instance().add_callback(background_pool_payer)

    my_peer = Peer.init_my_peer(config.network)
    app_log.info("API: http://{}".format(my_peer.to_string()))

    app = NodeApplication(config, mongo, peers)

    app_log.info("Starting server on {}:{}".format(config.serve_host, config.serve_port))
    app.listen(config.serve_port, config.serve_host)
    if config.ssl:
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile=config.ssl.get('cafile'))
        ssl_ctx.load_cert_chain(config.ssl.get('certfile'), keyfile=config.ssl.get('keyfile'))
        http_server = tornado.httpserver.HTTPServer(app, ssl_options=ssl_ctx)
        http_server.listen(config.ssl['port'])
    webbrowser.open("http://{}/app".format(my_peer.to_string()))
    # The server will simply run until interrupted
    # with Ctrl-C, but if you want to shut down more gracefully,
    # call shutdown_event.set().
    shutdown_event = tornado.locks.Event()
    await shutdown_event.wait()


if __name__ == "__main__":
        tornado.ioloop.IOLoop.current().run_sync(main)
