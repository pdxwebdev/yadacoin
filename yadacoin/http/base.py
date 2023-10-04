"""
Base handler ancestor, factorize common functions
"""

import json
import logging

from bson import json_util
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler

from yadacoin.core.config import Config
from yadacoin.enums.modes import MODES


class BaseHandler(RequestHandler):
    """Common ancestor for all route handlers"""

    def initialize(self):
        self.timed_out = False
        """Common init for every request"""
        origin = self.get_query_argument("origin", "*")
        if origin[-1] == "/":
            origin = origin[:-1]
        self.app_log = logging.getLogger("tornado.application")
        self.app_log.info(self._request_summary())
        self.config = Config()
        self.yadacoin_vars = self.settings["yadacoin_vars"]
        self.settings["page_title"] = self.settings["app_title"]
        self.set_header("Access-Control-Allow-Origin", origin)
        self.set_header("Access-Control-Allow-Credentials", "true")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.set_header("Access-Control-Expose-Headers", "Content-Type")
        self.set_header(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, Depth, User-Agent, X-File-Size, X-Requested-With, X-Requested-By, If-Modified-Since, X-File-Name, Cache-Control",
        )
        self.set_header("Access-Control-Max-Age", 600)
        self.jwt = {}

    async def prepare(self, exceptions=None):
        if (
            self.config.api_whitelist
            and self.request.remote_ip not in self.config.api_whitelist
        ):
            self.status_code = 400
            self.render_as_json({"status": "error", "message": "Not on the whitelist."})

        if exceptions is None:
            exceptions = []

        self.timeout_seconds = (
            self.config.http_request_timeout
        )  # Default timeout for all handlers

        loop = IOLoop.current()

        def on_timeout():
            self.timed_out = True
            self.set_status(503)  # 408 Request Timeout

        self.timeout_handle = loop.add_timeout(
            loop.time() + self.timeout_seconds, on_timeout
        )
        if (
            self.request.protocol == "http"
            and MODES.SSL.value in self.config.modes
            and self.config.ssl.is_valid()
            and self.request.path not in exceptions
        ):
            self.redirect(
                "https://" + self.request.host + self.request.uri, permanent=False
            )

        # if 'Authorization' in self.request.headers:
        #     try:
        #         data = json.loads(base64.b64decode(self.request.headers['Authorization']))
        #         alias = Identity.from_dict(data['identity'])
        #         rid = alias.generate_rid(self.config.username_signature)
        #         if self.request.uri.endswith('proxy-challenge'):
        #             return
        #         if rid not in self.config.challenges:
        #             self.set_status(403)
        #             self.write('not authorized')
        #             return self.finish()
        #         challenge = self.config.challenges[rid]
        #         mobile = self.config.websocketServer.inbound_streams[User.__name__][rid].peer.identity
        #         result = verify_signature(base64.b64decode(data['challenge']['signature']), challenge['message'].encode('utf-8'), bytes.fromhex(mobile.public_key))
        #         if not result:
        #             self.set_status(403)
        #             self.write('not authorized')
        #             return self.finish()
        #     except:
        #         i=0

    def finish(self, *args, **kwargs):
        if self.timed_out:
            return super().finish()
        IOLoop.current().remove_timeout(self.timeout_handle)
        super().finish(*args, **kwargs)

    # This could be static, but its easier to let it there so the template have direct access.
    def bool2str(self, a_boolean, iftrue, iffalse):
        return iftrue if a_boolean else iffalse

    def active_if(self, path: str):
        """return the 'active' string if the request uri is the one in path. Used for menu css"""
        if self.request.uri == path:
            return "active"
        return ""

    def active_if_start(self, path: str):
        """return the 'active' string if the request uri begins with the one in path. Used for menu css"""
        if self.request.uri.startswith(path):
            return "active"
        return ""

    def checked_if(self, condition: bool):
        if condition:
            return "checked"
        return ""

    def message(self, title, message, type="info"):
        """Display message template page"""
        self.render(
            "message.html",
            yadacoin=self.yadacoin_vars,
            title=title,
            message=message,
            type=type,
        )

    def render_as_json(self, data, indent=None):
        """Converts to json and streams out"""
        self.set_header("Content-Type", "application/json")
        if self.timed_out:
            json_result = json.dumps(
                {"status": False, "message": "Request timed out"}, indent=indent
            )
            self.write(json_result)
            return self.finish()
        IOLoop.current().remove_timeout(self.timeout_handle)
        json_result = json.dumps(data, indent=indent, default=json_util.default)
        self.write(json_result)
        self.finish()
        return True

    def render_already_json(self, data, indent=None):
        """Streams out provided json"""
        json_result = json.dumps(data, indent=indent)
        self.write(json_result)
        self.set_header("Content-Type", "application/json")
        self.finish()
        return True

    async def options(self):
        self.set_status(204)
        self.finish()
