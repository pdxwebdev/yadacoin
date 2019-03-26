"""
Async Yadacoin node poc
"""

from os import path
# import tornado.web
from tornado.web import Application, RequestHandler, StaticFileHandler
from tornado.options import define, options
import tornado.ioloop
import tornado.locks

from yadacoin.basehandlers import BaseHandler


__version__ = '0.0.1'

define("debug", default=False, help="debug mode", type=bool)
define("verbose", default=False, help="verbose mode", type=bool)
# TODO: get from config file
define("port", default=8000, help="run on the given port", type=int)
define("listen", default="127.0.0.1", help="On which address to listen, locked by default to localhost for tests", type=str)


class NodeApplication(Application):

    def __init__(self):
        static_path = path.join(path.dirname(__file__), 'static')
        self.default_handlers = [
            (r"/", HomeHandler),
            (r"/(apple-touch-icon\.png)", StaticFileHandler,
             dict(path=static_path))
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
            yadacoin_vars = {'node_version': __version__},
            yadacoin_config={},
        )
        handlers = self.default_handlers.copy()
        super().__init__(handlers, **settings)


class HomeHandler(BaseHandler):

    async def get(self):
        """
        :return:
        """
        self.render("index.html", yadacoin=self.yadacoin_vars)


async def main():
    tornado.options.parse_command_line()
    app = NodeApplication()
    app.listen(options.port, options.listen)
    # The server will simply run until interrupted
    # with Ctrl-C, but if you want to shut down more gracefully,
    # call shutdown_event.set().
    shutdown_event = tornado.locks.Event()
    await shutdown_event.wait()


if __name__ == "__main__":
        tornado.ioloop.IOLoop.current().run_sync(main)
