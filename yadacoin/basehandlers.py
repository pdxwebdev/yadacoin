"""
Base handler ancestor, factorize common functions
"""

import json
import logging

from tornado.web import RequestHandler


class BaseHandler(RequestHandler):
    """Common ancestor for all route handlers"""

    def initialize(self):
        """Common init for every request"""
        self.app_log = logging.getLogger("tornado.application")
        self.config = self.settings['yadacoin_config']
        self.mongo = self.settings['mongo']
        self.mp = self.config.mp
        self.peers = self.settings['peers']
        self.yadacoin_vars = self.settings['yadacoin_vars']
        self.settings["page_title"] = self.settings["app_title"]

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

    def render_as_json(self, data):
        """Converts to json and streams out"""
        json_result = json.dumps(data)
        self.write(json_result)
        self.set_header('Content-Type', 'application/json')
        self.finish()
        return True
