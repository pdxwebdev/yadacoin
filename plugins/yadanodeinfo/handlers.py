import os

import tornado

from yadacoin.http.base import BaseHandler


class BaseWebHandler(BaseHandler):
    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "build")


class AppHandler(BaseWebHandler):
    async def get(self):
        return self.render("index.html")


HANDLERS = [
    (r"/node-info", AppHandler),
    (
        r"/nodeinfostatic/(.*)",
        tornado.web.StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "build")},
    ),
]
