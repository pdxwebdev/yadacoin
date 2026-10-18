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

import os

from plugins.yadapasswordsignin.handlers import redirect_to_signin
from yadacoin.http.base import BaseHandler

SCROLLER_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "plugins",
        "fileannouncement",
        "demos",
        "yadascrollerdemo",
    )
)


class HomeHandler(BaseHandler):
    async def get(self):
        """
        Serve the feed at /, or the node dashboard at /node-dashboard.
        Pool nodes still redirect to /pool. Setup still wins over both.
        """
        from plugins.operator.setup import onboarding_pending

        if onboarding_pending(self.config):
            self.redirect("/operator/setup/workflow")
            return
        if getattr(self.config, "setup_required", False):
            return self.redirect("/operator/setup")
        if getattr(self.config, "peer_type", None) == "pool":
            return self.redirect("/pool")
        if self.request.path.rstrip("/") == "/node-dashboard":
            self.render("dashboard.html")
            return
        from plugins.fileannouncement.handlers import write_scroller_index

        write_scroller_index(self)


class AppHandler(BaseHandler):
    async def get(self):
        """
        Wallet. Operator sign-in is the shared Yada Password page.
        """
        if self.get_query_argument("operator_signin", "") == "1":
            return redirect_to_signin(
                self,
                "wallet",
                next_path="/app",
                keyname=self.get_query_argument("keyname", ""),
            )
        self.render("app.html")


class ScrollerAssetHandler(BaseHandler):
    async def get(self, name):
        name = os.path.basename(name or "")
        if name not in ("styles.css", "app.js"):
            self.set_status(404)
            self.finish("not found")
            return
        full = os.path.join(SCROLLER_DIR, name)
        if not os.path.isfile(full):
            self.set_status(404)
            self.finish("not found")
            return
        kind = "text/css" if name.endswith(".css") else "application/javascript"
        self.set_header("Content-Type", kind + "; charset=UTF-8")
        self.set_header("Cache-Control", "no-store")
        self.set_header("X-Content-Type-Options", "nosniff")
        with open(full, "rb") as fh:
            self.write(fh.read())
        self.finish()


WEB_HANDLERS = [
    (r"/", HomeHandler),
    (r"/node-dashboard", HomeHandler),
    (r"/app", AppHandler),
    (
        r"/file-announcements/demo/yadascroller/(styles\.css|app\.js)",
        ScrollerAssetHandler,
    ),
]
