"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import os

import tornado.web

from yadacoin.http.base import BaseHandler

DIST = os.path.join(os.path.dirname(__file__), "dist")
INDEX = os.path.join(DIST, "index.html")
LOGO_PATH = "/yadacoinstatic/yadalogo192.png"


def public_origin(handler) -> str:
    req = handler.request
    headers = getattr(req, "headers", None) or {}
    proto = (getattr(req, "protocol", None) or "http").lower()
    forwarded = str(headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
    if forwarded:
        proto = forwarded.lower()
    host = str(headers.get("X-Forwarded-Host") or getattr(req, "host", "") or "")
    host = host.split(",")[0].strip()
    return f"{proto}://{host}" if host else ""


def explorer_page(handler) -> bytes:
    with open(INDEX, "rb") as handle:
        html = handle.read().decode("utf-8")
    origin = public_origin(handler)
    logo = f"{origin}{LOGO_PATH}" if origin else LOGO_PATH
    page = f"{origin}/explorer" if origin else "/explorer"
    html = (
        html.replace("__LOGO__", logo)
        .replace("__PAGE__", page)
        .replace("__ORIGIN__", origin)
    )
    return html.encode("utf-8")


class ChainExplorerHandler(BaseHandler):
    async def get(self):
        if not os.path.exists(INDEX):
            self.set_status(503)
            self.set_header("Content-Type", "text/html; charset=utf-8")
            self.finish(
                "<pre>Chain explorer is not built.\n"
                "cd plugins/chainexplorer/ui && npm install && npm run build</pre>"
            )
            return
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.finish(explorer_page(self))


HANDLERS = [
    (
        r"/chain-explorer/assets/(.*)",
        tornado.web.StaticFileHandler,
        {"path": os.path.join(DIST, "assets")},
    ),
    (r"/chain-explorer/?", ChainExplorerHandler),
]
