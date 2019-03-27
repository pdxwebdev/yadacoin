"""
Async Yadacoin node poc
"""

import json
import logging
from os import path
# import tornado.web
from tornado.web import Application, RequestHandler, StaticFileHandler
from tornado.options import define, options
import tornado.ioloop
import tornado.locks
from sys import exit
from asyncio import sleep as async_sleep

from yadacoin.config import Config
from yadacoin.basehandlers import BaseHandler
from yadacoin.corehandlers import GetLatestBlockHandler, GetBlocksHandler, GetBlockHandler
from yadacoin.consensus import Consensus
from yadacoin.mongo import Mongo


__version__ = '0.0.4'

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
            (r"/", HomeHandler),
            (r'/get-latest-block', GetLatestBlockHandler),
            (r'/get-blocks', GetBlocksHandler),
            (r'/get-block', GetBlockHandler),
            (r"/(apple-touch-icon\.png)", StaticFileHandler, dict(path=static_path))
        ]

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
            mongo=mongo
        )
        handlers = self.default_handlers.copy()
        super().__init__(handlers, **settings)


class HomeHandler(BaseHandler):

    async def get(self):
        """
        :return:
        """
        self.render("index.html", yadacoin=self.yadacoin_vars)


async def background_consensus(consensus):
    while True:
        wait = consensus.sync_bottom_up()
        if wait:
            await async_sleep(1)


async def main():
    tornado.options.parse_command_line()
    if path.isfile(options.config):
        with open(options.config) as f:
            config = Config(json.loads(f.read()))
    else:
        print("no config file found at '%s'" % options.config)
        exit()

    mongo = Mongo(config)

    consensus = Consensus(config, mongo, options.debug)
    if config.verify:
        logging.getLogger("tornado.application").info("Verifying existing blockchain".format(config.serve_host, config.serve_port))
        consensus.verify_existing_blockchain(reset=options.reset)
    tornado.ioloop.IOLoop.instance().add_callback(background_consensus, consensus)

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
