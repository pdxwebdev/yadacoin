"""
Async Yadacoin node poc
"""

import json
import logging
from os import path
from tornado.web import Application, StaticFileHandler
from tornado.options import define, options
import tornado.ioloop
import tornado.locks
from sys import exit
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


__version__ = '0.0.6'

define("debug", default=False, help="debug mode", type=bool)
define("verbose", default=False, help="verbose mode", type=bool)
define("network", default='mainnet', help="mainnet, testnet or regnet", type=str)
define("reset", default=False, help="If blockchain is invalid, truncate at error block", type=bool)
define("config", default='config/config.json', help="Config file location, default is 'config/config.json'", type=str)
define("verify", default=True, help="Verify chain, default True", type=bool)


class NodeApplication(Application):

    def __init__(self, config, mongo):
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
            mongo=mongo  # TODO: add peers?
        )
        yadacoin.yadawebsockethandler.WS_CONFIG = config
        yadacoin.yadawebsockethandler.WS_MONGO = mongo
        handlers = self.default_handlers.copy()
        super().__init__(handlers, **settings)


async def background_consensus(consensus):
    log = logging.getLogger("tornado.application")
    while True:
        try:
            wait = await consensus.sync_bottom_up()
            if wait:
                await async_sleep(1)
        except Exception as e:
            log.error("{} in Background_consensus".format(e))


async def background_peers_testing(peers: Peers):
    log = logging.getLogger("tornado.application")
    while True:
        try:
            await async_sleep(10)
            if len(peers.peers) > 50:
                # Enough peers, no need to waste resources
                continue
            log.info('Should test one peer')
            await peers.test_some(count=3)
        except Exception as e:
            log.error("{} in Background_consensus".format(e))


async def main():
    tornado.options.parse_command_line()
    if path.isfile(options.config):
        with open(options.config) as f:
            config = Config(json.loads(f.read()))
    else:
        print("no config file found at '%s'" % options.config)
        exit()

    mongo = Mongo(config)

    peers = Peers(config, mongo)
    consensus = Consensus(config, mongo, options.debug, peers)
    if options.verify:
        logging.getLogger("tornado.application").info("Verifying existing blockchain".format(config.serve_host, config.serve_port))
        consensus.verify_existing_blockchain(reset=options.reset)

    tornado.ioloop.IOLoop.instance().add_callback(background_consensus, consensus)
    tornado.ioloop.IOLoop.instance().add_callback(background_peers_testing, peers)

    my_peer = Peer.init_my_peer(config, mongo, config.network)
    config.callbackurl = 'http://%s/create-relationship' % my_peer.to_string()
    print("http://{}".format(my_peer.to_string()))

    app = NodeApplication(config, mongo)
    logging.getLogger("tornado.application").info("Starting server on {}:{}".format(config.serve_host, config.serve_port))
    app.listen(config.serve_port, config.serve_host)
    # The server will simply run until interrupted
    # with Ctrl-C, but if you want to shut down more gracefully,
    # call shutdown_event.set().
    shutdown_event = tornado.locks.Event()
    await shutdown_event.wait()


if __name__ == "__main__":
        tornado.ioloop.IOLoop.current().run_sync(main)
