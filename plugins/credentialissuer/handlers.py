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

from yadacoin.decorators.jwtauth import jwtauthwallet
from yadacoin.http.base import BaseHandler

from . import store
from .service import CredentialIssuerError, issue_credential


def _json_body(handler):
    if not handler.request.body:
        return {}
    try:
        return json.loads(handler.request.body.decode("utf-8"))
    except Exception:
        raise ValueError("Invalid JSON body")


@jwtauthwallet
class BaseCredentialIssuerHandler(BaseHandler):
    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")

    async def prepare(self, exceptions=None):
        await super().prepare(exceptions=exceptions)
        if self._finished:
            return
        if self.request.method == "OPTIONS":
            return
        if await self.wallet_is_unlocked():
            return
        self.set_status(401)
        path = self.request.path or ""
        if path.startswith("/credential-issuer/api/"):
            self.render_as_json({"status": False, "error": "not authorized"})
        else:
            self.render(
                "locked.html",
                yadacoin=self.yadacoin_vars,
                title="YadaCoin - Credential Issuer",
            )
            self.finish()

    def _error(self, status, message):
        self.set_status(status)
        return self.render_as_json({"status": False, "error": message})


class CredentialIssuerDashboardHandler(BaseCredentialIssuerHandler):
    async def get(self):
        if not await self.wallet_is_unlocked():
            return
        self.render(
            "dashboard.html",
            yadacoin=self.yadacoin_vars,
            title="YadaCoin - Credential Issuer",
        )


class CredentialListHandler(BaseCredentialIssuerHandler):
    async def get(self):
        try:
            limit = min(int(self.get_query_argument("limit", 100)), 500)
            skip = max(int(self.get_query_argument("skip", 0)), 0)
        except ValueError:
            return self._error(400, "limit and skip must be integers")
        items = await store.list_issued(self.config, limit=limit, skip=skip)
        return self.render_as_json(
            {"status": True, "count": len(items), "results": items}
        )

    async def post(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        try:
            record = await issue_credential(
                self.config,
                username=data.get("username") or "",
                subject_username_signature=data.get("subject_username_signature") or "",
                claim=data.get("claim") or "ageOver18",
                expires=data.get("expires"),
                witness_hex=data.get("witness_hex") or "",
            )
        except (CredentialIssuerError, ValueError) as exc:
            return self._error(400, str(exc))
        self.set_status(201)
        return self.render_as_json({"status": True, "result": record})


HANDLERS = [
    (r"/credential-issuer", CredentialIssuerDashboardHandler),
    (r"/credential-issuer/api/v1/credentials", CredentialListHandler),
]
