"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Handlers required by the web operations
"""

from yadacoin.http.base import BaseHandler


class HomeHandler(BaseHandler):
    async def get(self):
        """
        Serve the main node dashboard, or redirect to the pool dashboard
        when peer_type is 'pool'.
        """
        if getattr(self.config, "peer_type", None) == "pool":
            return self.redirect("/pool")
        self.render("dashboard.html")


class AppHandler(BaseHandler):
    async def get(self):
        """
        :return:
        """
        self.render("app.html")


WEB_HANDLERS = [
    (r"/", HomeHandler),
    (r"/node-dashboard", HomeHandler),
    (r"/app", AppHandler),
]
