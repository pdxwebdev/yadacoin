"""
Base handler ancestor, factorize common functions
"""

import json
import logging

from tornado.web import RequestHandler

from yadacoin.core.config import get_config


class BaseHandler(RequestHandler):
    """Common ancestor for all route handlers"""

    def initialize(self):
        """Common init for every request"""
        origin = self.get_query_argument('origin', '*')
        if origin[-1] == '/':
            origin = origin[:-1]
        self.app_log = logging.getLogger("tornado.application")
        self.app_log.info(self._request_summary())
        self.config = get_config()
        self.yadacoin_vars = self.settings['yadacoin_vars']
        self.settings["page_title"] = self.settings["app_title"]
        self.set_header("Access-Control-Allow-Origin", origin)
        self.set_header('Access-Control-Allow-Credentials', "true")
        self.set_header('Access-Control-Allow-Methods', "GET, POST, OPTIONS, DELETE")
        self.set_header('Access-Control-Expose-Headers', "Content-Type")
        self.set_header('Access-Control-Allow-Headers', "Authorization, Content-Type, Depth, User-Agent, X-File-Size, X-Requested-With, X-Requested-By, If-Modified-Since, X-File-Name, Cache-Control")
        self.set_header('Access-Control-Max-Age', 600)
        self.jwt = {}

    async def prepare(self):
        if self.config.api_whitelist and self.request.remote_ip not in self.config.api_whitelist:
            self.status_code = 400
            self.render_as_json({'status': 'error', 'message': 'Not on the whitelist.'})

    # This could be static, but its easier to let it there so the template have direct access.
    def bool2str(self, a_boolean, iftrue, iffalse):
        return iftrue if a_boolean else iffalse

    def active_if(self, path: str):
        """return the 'active' string if the request uri is the one in path. Used for menu css"""
        if self.request.uri == path:
            return "active"
        return ''

    def active_if_start(self, path: str):
        """return the 'active' string if the request uri begins with the one in path. Used for menu css"""
        if self.request.uri.startswith(path):
            return "active"
        return ''

    def checked_if(self, condition:bool):
        if condition:
            return "checked"
        return ''

    def message(self, title, message, type="info"):
        """Display message template page"""
        self.render("message.html", yadacoin=self.yadacoin_vars, title=title, message=message, type=type)

    def render_as_json(self, data, indent=None):
        """Converts to json and streams out"""
        json_result = json.dumps(data, indent=indent)
        self.write(json_result)
        self.set_header('Content-Type', 'application/json')
        self.finish()
        return True

    def render_already_json(self, data, indent=None):
        """Streams out provided json"""
        json_result = json.dumps(data, indent=indent)
        self.write(json_result)
        self.set_header('Content-Type', 'application/json')
        self.finish()
        return True


    async def options(self):
        self.set_status(204)
        self.finish()
