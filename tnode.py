"""
Async Yadacoin node poc
"""

import json
import logging
from os import path
from tornado.web import Application, StaticFileHandler
from tornado.options import define, options
from logging.handlers import RotatingFileHandler
from tornado.log import LogFormatter
import tornado.log
import tornado.ioloop
import tornado.locks
from sys import exit, stdout
from asyncio import sleep as async_sleep
import socketio

import yadacoin.yadawebsockethandler
from yadacoin.config import Config
from yadacoin.explorerhandlers import EXPLORER_HANDLERS
from yadacoin.graphhandlers import GRAPH_HANDLERS
from yadacoin.nodehandlers import NODE_HANDLERS
from yadacoin.poolhandlers import POOL_HANDLERS
from yadacoin.wallethandlers import WALLET_HANDLERS
from yadacoin.webhandlers import WEB_HANDLERS
from yadacoin.yadawebsockethandler import SIO
from yadacoin.consensus import Consensus
from yadacoin.mongo import Mongo
from yadacoin.peers import Peer, Peers


__version__ = '0.0.7'


app_log = None
access_log = None


class NodeApplication(Application):

    def __init__(self, config, mongo, peers):
        static_path = path.join(path.dirname(__file__), 'static')
        self.default_handlers = [
            (r"/(apple-touch-icon\.png)", StaticFileHandler, dict(path=static_path)),
            (r"/socket.io/", socketio.get_tornado_handler(SIO))
        ]
        self.default_handlers.extend(NODE_HANDLERS)
        self.default_handlers.extend(GRAPH_HANDLERS)
        # TODO: use config to enable/disable specific routes
        self.default_handlers.extend(EXPLORER_HANDLERS)
        self.default_handlers.extend(POOL_HANDLERS)
        self.default_handlers.extend(WALLET_HANDLERS)
        self.default_handlers.extend(WEB_HANDLERS)

        settings = dict(
            app_title=u"Yadacoin Node",
            template_path=path.join(path.dirname(__file__), 'templates'),
            static_path=path.join(path.dirname(__file__), static_path),
            xsrf_cookies=True,
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            compress_response=True,
            debug=options.debug,  # Also activates auto reload
            serve_traceback=options.debug,
            yadacoin_vars={'node_version': __version__},
            yadacoin_config=config,
            mp = None,
            mongo=mongo,
            peers=peers
        )
        yadacoin.yadawebsockethandler.WS_CONFIG = config
        yadacoin.yadawebsockethandler.WS_MONGO = mongo
        handlers = self.default_handlers.copy()
        super().__init__(handlers, **settings)


async def background_consensus(consensus):
    while True:
        try:
            wait = await consensus.sync_bottom_up()
            if wait:
                await async_sleep(1)
        except Exception as e:
            app_log.error("{} in Background_consensus".format(e))


async def background_peers_testing(peers: Peers):
    while True:
        try:
            await async_sleep(10)
            if len(peers.peers) > 50:
                # Enough peers, no need to waste resources
                continue
            # log.info('Should test peers')
            await peers.test_some(count=2)
        except Exception as e:
            app_log.error("{} in Background_consensus".format(e))


def configure_logging():
    global app_log, access_log
    ch = logging.StreamHandler(stdout)
    ch.setLevel(logging.INFO)
    # tornado.log.enable_pretty_logging()
    app_log = logging.getLogger("tornado.application")
    tornado.log.enable_pretty_logging(logger=logging.getLogger("tornado.application"))
    # app_log.addHandler(ch)
    logfile = path.abspath("yada_app.log")
    # Rotate log after reaching 512K, keep 5 old copies.
    rotateHandler = RotatingFileHandler(logfile, "a", 512 * 1024, 5)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    rotateHandler.setFormatter(formatter)
    app_log.addHandler(rotateHandler)

    access_log = logging.getLogger("tornado.access")
    tornado.log.enable_pretty_logging()
    logfile2 = path.abspath("yada_access.log")
    rotateHandler2 = RotatingFileHandler(logfile2, "a", 512 * 1024, 5)
    formatter2 = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    rotateHandler2.setFormatter(formatter2)
    access_log.addHandler(rotateHandler2)

    app_log.propagate = False


async def main():
    define("debug", default=False, help="debug mode", type=bool)
    define("verbose", default=False, help="verbose mode", type=bool)
    define("network", default='mainnet', help="mainnet, testnet or regnet", type=str)
    define("reset", default=False, help="If blockchain is invalid, truncate at error block", type=bool)
    define("config", default='config/config.json', help="Config file location, default is 'config/config.json'",
           type=str)
    define("verify", default=True, help="Verify chain, default True", type=bool)

    options.parse_command_line()

    configure_logging()

    if not path.isfile(options.config):
        app_log.error("no config file found at '{}'".format(options.config))
        exit()

    with open(options.config) as f:
        config = Config(json.loads(f.read()))

    mongo = Mongo(config)

    peers = Peers(config, mongo)
    consensus = Consensus(config, mongo, options.debug, peers)
    if options.verify:
        app_log.info("Verifying existing blockchain".format(config.serve_host, config.serve_port))
        consensus.verify_existing_blockchain(reset=options.reset)

    tornado.ioloop.IOLoop.instance().add_callback(background_consensus, consensus)
    tornado.ioloop.IOLoop.instance().add_callback(background_peers_testing, peers)

    my_peer = Peer.init_my_peer(config, mongo, config.network)
    config.callbackurl = 'http://%s/create-relationship' % my_peer.to_string()
    app_log.info("API: http://{}".format(my_peer.to_string()))

    app = NodeApplication(config, mongo, peers)
    app_log.info("Starting server on {}:{}".format(config.serve_host, config.serve_port))
    app.listen(config.serve_port, config.serve_host)
    # The server will simply run until interrupted
    # with Ctrl-C, but if you want to shut down more gracefully,
    # call shutdown_event.set().
    shutdown_event = tornado.locks.Event()
    await shutdown_event.wait()


if __name__ == "__main__":
        tornado.ioloop.IOLoop.current().run_sync(main)
