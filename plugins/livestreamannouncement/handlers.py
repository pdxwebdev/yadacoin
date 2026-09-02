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
from .service import (
    LivestreamServiceError,
    accept_grant,
    create_channel,
    go_live,
    issue_challenge,
    on_publish,
    on_unpublish,
    public_live_list,
    revoke_grant,
    stop_live,
    watch,
    whitelist_channel,
)


def _json_body(handler):
    if not handler.request.body:
        return {}
    try:
        return json.loads(handler.request.body.decode("utf-8"))
    except Exception:
        raise ValueError("Invalid JSON body")


class _JsonMixin:
    def _error(self, status, message):
        self.set_status(status)
        return self.render_as_json({"status": False, "error": message})


@jwtauthwallet
class BaseLivestreamWalletHandler(BaseHandler, _JsonMixin):
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
        if path.startswith("/livestream-announcements/api/"):
            self.render_as_json({"status": False, "error": "not authorized"})
        else:
            self.render(
                "locked.html",
                yadacoin=self.yadacoin_vars,
                title="YadaCoin - Livestream",
            )
            self.finish()


class BaseLivestreamPublicHandler(BaseHandler, _JsonMixin):
    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")


class LivestreamDashboardHandler(BaseLivestreamWalletHandler):
    async def get(self):
        if not await self.wallet_is_unlocked():
            return
        self.render(
            "dashboard.html",
            yadacoin=self.yadacoin_vars,
            title="YadaCoin - Livestream",
        )


class ChannelListHandler(BaseLivestreamWalletHandler):
    async def get(self):
        try:
            limit = min(int(self.get_query_argument("limit", 100)), 500)
            skip = max(int(self.get_query_argument("skip", 0)), 0)
        except ValueError:
            return self._error(400, "limit and skip must be integers")
        channels = await store.list_channels(self.config, limit=limit, skip=skip)
        return self.render_as_json(
            {"status": True, "count": len(channels), "results": channels}
        )

    async def post(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        try:
            record = await create_channel(
                self.config,
                title=data.get("title") or "",
                description=data.get("description") or "",
                age_restricted=bool(data.get("age_restricted")),
                sp_host=data.get("sp_host") or "",
            )
        except (LivestreamServiceError, ValueError) as exc:
            return self._error(400, str(exc))
        self.set_status(201)
        return self.render_as_json({"status": True, "result": record})


class ChannelLiveHandler(BaseLivestreamWalletHandler):
    async def post(self, channel_id):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        try:
            result = await go_live(self.config, channel_id, vp=data.get("vp"))
        except LivestreamServiceError as exc:
            code = 404 if "not found" in str(exc) else 400
            return self._error(code, str(exc))
        return self.render_as_json({"status": True, "result": result})


class ChannelStopHandler(BaseLivestreamWalletHandler):
    async def post(self, channel_id):
        try:
            result = await stop_live(self.config, channel_id)
        except LivestreamServiceError as exc:
            code = 404 if "not found" in str(exc) else 400
            return self._error(code, str(exc))
        return self.render_as_json({"status": True, "result": result})


class ChannelWhitelistHandler(BaseLivestreamWalletHandler):
    async def post(self, channel_id):
        try:
            result = await whitelist_channel(self.config, channel_id)
        except LivestreamServiceError as exc:
            code = 404 if "not found" in str(exc) else 400
            return self._error(code, str(exc))
        return self.render_as_json({"status": True, "result": result})


class SettingsHandler(BaseLivestreamWalletHandler):
    async def get(self):
        settings = await store.get_settings(self.config)
        redacted = dict(settings)
        pw = redacted.get("obs_websocket_password") or ""
        redacted["obs_websocket_password_configured"] = bool(pw)
        if pw:
            redacted["obs_websocket_password"] = "********"
        return self.render_as_json({"status": True, "result": redacted})

    async def put(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        settings = await store.save_settings(self.config, data)
        return self.render_as_json({"status": True, "result": settings})


class ChallengeHandler(BaseLivestreamPublicHandler):
    async def post(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        channel_id = data.get("channel_id") or ""
        action = data.get("action") or "grant"
        result = await issue_challenge(self.config, channel_id, action=action)
        return self.render_as_json({"status": True, "result": result})


class GrantHandler(BaseLivestreamPublicHandler):
    async def post(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        try:
            result = await accept_grant(self.config, data)
        except LivestreamServiceError as exc:
            return self._error(400, str(exc))
        return self.render_as_json({"status": True, "result": result})


class GrantRevokeHandler(BaseLivestreamPublicHandler):
    async def post(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        channel_id = data.get("channel_id") or ""
        result = await revoke_grant(self.config, channel_id)
        return self.render_as_json({"status": True, "result": result})


class OnPublishHandler(BaseLivestreamPublicHandler):
    async def post(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        channel_id = (
            data.get("channel_id") or data.get("name") or data.get("stream") or ""
        )
        try:
            result = await on_publish(self.config, channel_id)
        except LivestreamServiceError as exc:
            return self._error(403, str(exc))
        return self.render_as_json({"status": True, "result": result})


class OnUnpublishHandler(BaseLivestreamPublicHandler):
    async def post(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        channel_id = (
            data.get("channel_id") or data.get("name") or data.get("stream") or ""
        )
        result = await on_unpublish(self.config, channel_id)
        return self.render_as_json({"status": True, "result": result})


class LiveListHandler(BaseLivestreamPublicHandler):
    async def get(self):
        results = await public_live_list(self.config)
        return self.render_as_json({"status": True, "results": results})


class WatchHandler(BaseLivestreamPublicHandler):
    async def post(self):
        try:
            data = _json_body(self)
        except ValueError as exc:
            return self._error(400, str(exc))
        channel_id = data.get("channel_id") or ""
        try:
            result = await watch(self.config, channel_id, vp=data.get("vp"))
        except LivestreamServiceError as exc:
            return self._error(400, str(exc))
        return self.render_as_json({"status": True, "result": result})


HANDLERS = [
    (r"/livestream-announcements", LivestreamDashboardHandler),
    (r"/livestream-announcements/api/v1/channels", ChannelListHandler),
    (r"/livestream-announcements/api/v1/channels/([^/]+)/live", ChannelLiveHandler),
    (r"/livestream-announcements/api/v1/channels/([^/]+)/stop", ChannelStopHandler),
    (
        r"/livestream-announcements/api/v1/blocked/([^/]+)/whitelist",
        ChannelWhitelistHandler,
    ),
    (r"/livestream-announcements/api/v1/settings", SettingsHandler),
    (r"/livestream-announcements/api/v1/challenge", ChallengeHandler),
    (r"/livestream-announcements/api/v1/grants", GrantHandler),
    (r"/livestream-announcements/api/v1/grants/revoke", GrantRevokeHandler),
    (r"/livestream-announcements/api/v1/on-publish", OnPublishHandler),
    (r"/livestream-announcements/api/v1/on-unpublish", OnUnpublishHandler),
    (r"/livestream-announcements/api/v1/live", LiveListHandler),
    (r"/livestream-announcements/api/v1/watch", WatchHandler),
]
