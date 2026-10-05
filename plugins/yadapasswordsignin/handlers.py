"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import json
import os
import re
from urllib.parse import urlencode

from yadacoin.http.base import BaseHandler

SIGNIN_PATH = "/yada-password/signin"

_KEYNAME_RE = re.compile(r"^operator-[A-Za-z0-9._@:%+-]{1,200}$")

PURPOSES = {
    "operator": {
        "header": "Operator",
        "title": "YadaCoin - Sign in with Yada Password",
        "blurb": (
            "Operator actions use this node's key event log. Paste this node's "
            "seed and second factor into the browser extension or mobile app. "
            "Rotations sync through the chain and mempool. This page never "
            "asks for those secrets."
        ),
        "next": "/",
    },
    "file-announcements": {
        "header": "File Announcements",
        "title": "YadaCoin - File Announcements",
        "blurb": (
            "File announcements rotate this node's key event log. Paste this "
            "node's seed and second factor into the browser extension or "
            "mobile app. Rotations sync through the chain and mempool. This "
            "page never asks for those secrets."
        ),
        "next": "/file-announcements",
    },
    "credential-issuer": {
        "header": "Credential Issuer",
        "title": "YadaCoin - Credential Issuer",
        "blurb": (
            "Issuing credentials broadcasts a KEL-backed CredentialAnnouncement. "
            "Paste this node's seed and second factor into the browser "
            "extension or mobile app. Rotations sync through the chain and "
            "mempool. This page never asks for those secrets."
        ),
        "next": "/credential-issuer",
    },
    "livestream": {
        "header": "Livestream",
        "title": "YadaCoin - Livestream",
        "blurb": (
            "Livestream channel create, Go Live, Stop, and whitelist sign with "
            "this node's KEL. Paste this node's seed and second factor into "
            "the browser extension or mobile app. Rotations sync through the "
            "chain and mempool. This page never asks for those secrets."
        ),
        "next": "/livestream-announcements",
    },
    "wallet": {
        "header": "Wallet",
        "title": "YadaCoin - Operator sign-in",
        "blurb": (
            "Control this node's treasury without importing the node seed. "
            "Paste this node's seed and second factor into the browser "
            "extension or mobile app. Rotations sync through the chain and "
            "mempool. This page never asks for those secrets."
        ),
        "next": "/app",
    },
}


def safe_next(value):
    """Same-origin relative path only. Reject open redirects."""
    if not value or not isinstance(value, str):
        return ""
    value = value.strip()
    if not value.startswith("/") or value.startswith("//") or value.startswith("/\\"):
        return ""
    if any(ch in value for ch in ("\\", "<", ">", "\n", "\r")):
        return ""
    if "://" in value:
        return ""
    return value


def safe_keyname(value):
    if not value or not isinstance(value, str):
        return ""
    value = value.strip()
    if not _KEYNAME_RE.match(value):
        return ""
    return value


def signin_location(purpose, next_path=None, keyname=""):
    spec = PURPOSES.get(purpose) or PURPOSES["operator"]
    purpose_key = purpose if purpose in PURPOSES else "operator"
    nxt = safe_next(next_path) or spec["next"]
    params = {"purpose": purpose_key, "next": nxt}
    key = safe_keyname(keyname)
    if key:
        params["keyname"] = key
    return SIGNIN_PATH + "?" + urlencode(params)


def redirect_to_signin(handler, purpose, next_path=None, keyname=""):
    if next_path is None:
        next_path = getattr(getattr(handler, "request", None), "uri", "") or ""
    handler.redirect(signin_location(purpose, next_path, keyname))


class YadaPasswordSigninHandler(BaseHandler):
    """GET /yada-password/signin — shared operator sign-in page."""

    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")

    async def get(self):
        purpose = self.get_query_argument("purpose", "operator")
        spec = PURPOSES.get(purpose) or PURPOSES["operator"]
        nxt = safe_next(self.get_query_argument("next", "")) or spec["next"]
        keyname = safe_keyname(self.get_query_argument("keyname", ""))
        self.render(
            "signin.html",
            yadacoin=self.yadacoin_vars,
            title=spec["title"],
            header=spec["header"],
            blurb=spec["blurb"],
            next_json=json.dumps(nxt),
            keyname_json=json.dumps(keyname),
        )


HANDLERS = [
    (SIGNIN_PATH, YadaPasswordSigninHandler),
]
