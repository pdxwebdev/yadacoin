"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import inspect
import json
import os
import shutil
import sys
import threading

from tornado.ioloop import IOLoop

from node_dashboard.job import ReloadJob, job_state_path, read_job_state
from node_dashboard.restore import connect_client, restore_tool
from node_dashboard.settings import (
    BOOTSTRAP_URL,
    CONFIRM_PHRASE,
    redact_text,
    resolve_target,
    target_from_config,
    tcp_open,
)
from plugins.yadapasswordsignin.handlers import redirect_to_signin
from yadacoin.core.config import Config
from yadacoin.http.base import BaseHandler

SIGNIN_PURPOSE = "operator"

STATIC_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "node_dashboard", "static")
)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ASSETS = {
    "index.html": "text/html; charset=utf-8",
    "app.css": "text/css; charset=utf-8",
    "app.js": "application/javascript; charset=utf-8",
}


class SavedJob(object):
    def __init__(self, payload):
        self.status = payload.get("status")
        self._payload = payload

    def public(self):
        return self._payload


def client_job(payload):
    if not payload:
        return None
    result = dict(payload.get("result") or {})
    handoff = result.get("handoff")
    if isinstance(handoff, dict):
        handoff = dict(handoff)
        target = handoff.get("target")
        if isinstance(target, dict):
            target = dict(target)
            target.pop("password", None)
            handoff["target"] = target
        result["handoff"] = handoff
        payload = dict(payload)
        payload["result"] = result
    return payload


class OperatorState(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.job = None
        saved = read_job_state(job_state_path(REPO_ROOT))
        if saved and saved.get("status") in ("failed", "succeeded"):
            self.job = SavedJob(saved)

    def start(
        self, target, on_stop, node_host, node_port, on_quiesce=None, on_resume=None
    ):
        with self.lock:
            if self.job is not None and self.job.status == "running":
                return None
            job = ReloadJob(
                REPO_ROOT,
                "",
                lambda event: None,
                target=target,
                on_stop=on_stop,
                on_quiesce=on_quiesce,
                on_resume=on_resume,
                node_host=node_host,
                node_port=node_port,
            )
            self.job = job
        threading.Thread(target=job.run, name="bootstrap-reload", daemon=True).start()
        return job


STATE = OperatorState()


def live_target():
    config = Config()
    return resolve_target(
        target_from_config(
            {
                "mongodb_host": config.mongodb_host,
                "database": config.database,
                "mongodb_username": getattr(config, "mongodb_username", "") or "",
                "mongodb_password": getattr(config, "mongodb_password", "") or "",
            }
        )
    )


def status_payload():
    config = Config()
    payload = {
        "bootstrap_url": BOOTSTRAP_URL,
        "started_at": config.start_time,
        "tools": {
            "mongorestore": shutil.which("mongorestore"),
            "docker": shutil.which("docker"),
            "mode": restore_tool(),
        },
        "mongo": {"ok": False, "error": None},
    }
    try:
        target = live_target()
    except Exception as exc:
        payload["mongo"]["error"] = str(exc)
        return payload
    payload["mongo"].update(target.public())
    if not tcp_open(target.connect_host, target.port, timeout=1.5):
        payload["mongo"]["ok"] = False
        payload["mongo"]["error"] = (
            "MongoDB is not accepting connections at {}:{}"
        ).format(target.connect_host, target.port)
        return payload
    client = None
    try:
        client = connect_client(target, timeout_ms=2000)
        db = client[target.database]
        latest = db.blocks.find_one(sort=[("index", -1)], projection={"index": 1})
        payload["mongo"].update(
            {
                "ok": True,
                "blocks": db.blocks.estimated_document_count(),
                "consensus": db.consensus.estimated_document_count(),
                "height": None if not latest else latest.get("index"),
                "error": None,
            }
        )
    except Exception as exc:
        payload["mongo"]["ok"] = False
        payload["mongo"]["error"] = redact_text(str(exc), target.secrets())
    finally:
        if client is not None:
            client.close()
    return payload


def restart_process():
    os.execv(sys.executable, [sys.executable] + sys.argv)


def schedule_restart(loop=None):
    loop = loop or IOLoop.current()

    def later():
        loop.call_later(1.5, restart_process)

    loop.add_callback(later)


def call_on_loop(loop, fn):
    done = threading.Event()
    box = {}

    def finish(fut):
        try:
            box["result"] = fut.result()
        except Exception as exc:
            box["error"] = exc
        done.set()

    def run():
        try:
            result = fn()
            if inspect.iscoroutine(result):
                asyncio.ensure_future(result).add_done_callback(finish)
                return
            box["result"] = result
        except Exception as exc:
            box["error"] = exc
        done.set()

    loop.add_callback(run)
    done.wait()
    if "error" in box:
        raise box["error"]
    return box.get("result")


def maintenance_callbacks(loop, app):
    def quiesce():
        call_on_loop(loop, app.enter_maintenance)

    def resume():
        call_on_loop(loop, app.leave_maintenance)

    return quiesce, resume


def send_asset(handler, name):
    if name not in ASSETS:
        handler.set_status(404)
        handler.finish()
        return
    path = os.path.join(STATIC_DIR, name)
    with open(path, "rb") as handle:
        body = handle.read()
    handler.set_header("Content-Type", ASSETS[name])
    handler.set_header("Cache-Control", "no-cache")
    handler.write(body)


class OperatorHandler(BaseHandler):
    async def prepare(self, exceptions=None):
        await super().prepare(exceptions=exceptions)
        if self._finished:
            return
        if self.request.method == "OPTIONS":
            return
        if await self.wallet_is_unlocked():
            return
        path = self.request.path or ""
        if path.startswith("/operator/api/"):
            self.set_status(401)
            self.render_as_json({"status": False, "error": "not authorized"})
            return
        redirect_to_signin(self, SIGNIN_PURPOSE)


class OperatorPageHandler(OperatorHandler):
    async def get(self):
        send_asset(self, "index.html")


class OperatorAssetHandler(OperatorHandler):
    async def get(self, name):
        send_asset(self, name)


class OperatorHealthHandler(OperatorHandler):
    async def get(self):
        config = Config()
        self.set_header("Cache-Control", "no-store")
        self.write(
            {
                "ok": True,
                "started_at": config.start_time,
                "boot_id": str(config.operator_session_epoch),
            }
        )


class OperatorStatusHandler(OperatorHandler):
    async def get(self):
        payload = await IOLoop.current().run_in_executor(None, status_payload)
        self.set_header("Cache-Control", "no-store")
        self.write(payload)


class OperatorJobHandler(OperatorHandler):
    async def get(self):
        job = STATE.job.public() if STATE.job is not None else None
        self.set_header("Cache-Control", "no-store")
        self.write({"job": client_job(job)})


class OperatorReloadHandler(OperatorHandler):
    async def post(self):
        if "application/json" not in self.request.headers.get("Content-Type", ""):
            self.set_status(415)
            self.write({"error": "Content-Type must be application/json"})
            return
        try:
            payload = json.loads(self.request.body.decode("utf-8") or "{}")
        except ValueError:
            self.set_status(400)
            self.write({"error": "Invalid JSON"})
            return
        if not isinstance(payload, dict) or payload.get("confirm") != CONFIRM_PHRASE:
            self.set_status(400)
            self.write({"error": "Type reload to confirm the reload"})
            return
        try:
            target = await IOLoop.current().run_in_executor(None, live_target)
        except Exception as exc:
            self.set_status(400)
            self.write({"error": str(exc)})
            return
        config = Config()
        loop = IOLoop.current()
        quiesce, resume = maintenance_callbacks(loop, config.application)
        job = STATE.start(
            target,
            None,
            getattr(config, "serve_host", None) or "127.0.0.1",
            getattr(config, "serve_port", None),
            on_quiesce=quiesce,
            on_resume=resume,
        )
        if job is None:
            self.set_status(409)
            self.write({"error": "A reload is already running"})
            return
        self.set_status(202)
        self.write({"job": client_job(job.public())})


OPERATOR_HANDLERS = [
    (r"/operator/api/status", OperatorStatusHandler),
    (r"/operator/api/job", OperatorJobHandler),
    (r"/operator/api/health", OperatorHealthHandler),
    (r"/operator/api/reload", OperatorReloadHandler),
    (r"/operator/(app\.(?:css|js))", OperatorAssetHandler),
    (r"/operator/?", OperatorPageHandler),
]
