"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

Celery entry for the post-quantum readiness discovery agent.
"""

from __future__ import annotations

import asyncio
import logging

LOG = logging.getLogger("postquantumreadiness.tasks")


def _celery_app():
    from plugins.postquantumreadiness.celery_app import celery_app

    if celery_app is None:
        raise RuntimeError("celery is not available")
    return celery_app


def _mongo():
    from yadacoin.core.config import Config
    from yadacoin.core.mongo import Mongo

    cfg = Config()
    if getattr(cfg, "mongo", None) is None:
        cfg.mongo = Mongo()
    return cfg, cfg.mongo


class DiscoveryStoreAdapter:
    """Sync facade used inside Celery workers."""

    def __init__(self, config, mongo):
        self.config = config
        self.mongo = mongo
        from plugins.postquantumreadiness import store

        self._store = store

    def append_step(self, job_id, step):
        self._store.sync_append_job_step(self.mongo, job_id, step)

    def update_job(self, job_id, **fields):
        self._store.sync_update_job(self.mongo, job_id, **fields)

    def upsert_asset_sync(self, org_id, asset):
        return self._store.sync_upsert_asset(self.config, self.mongo, org_id, asset)

    def run_assessment_sync(self, org_id, trigger="discovery_agent"):
        return self._store.sync_run_assessment(
            self.config, self.mongo, org_id, trigger=trigger
        )

    def delete_assets(self, org_id, tags=None, hosts=None, demo_seed=False):
        return self._store.sync_delete_assets(
            self.mongo, org_id, tags=tags, hosts=hosts, demo_seed=demo_seed
        )

    def get_org_sync(self, org_id):
        return self._store.sync_get_org(self.mongo, org_id)


def _bind_task():
    app = _celery_app()
    return app.task(bind=True, name="postquantumreadiness.discover")(discover_job)


def enqueue_discovery(*, job_id, org_id, targets, options=None, answers=None):
    task = getattr(discover_job, "delay", None)
    kwargs = dict(
        job_id=job_id,
        org_id=org_id,
        targets=targets,
        options=options or {},
        answers=answers or {},
    )
    if task is None:
        bound = _bind_task()
        return bound.delay(**kwargs)
    return discover_job.delay(**kwargs)


def _apply_result(mongo, job_id, result):
    from plugins.postquantumreadiness import store

    status = result.get("status") or "failed"
    fields = {
        "status": status,
        "phase": status,
        "result": result,
        "assets_discovered": result.get("assets_discovered"),
        "used_llm": result.get("used_llm"),
        "limitations": result.get("limitations"),
        "questions": result.get("questions"),
        "error_code": result.get("error_code"),
        "error_message": result.get("error_message"),
    }
    if status == "succeeded":
        fields["error_code"] = None
        fields["error_message"] = None
    store.sync_update_job(mongo, job_id, **fields)


def discover_job(
    self, job_id=None, org_id=None, targets=None, options=None, answers=None
):
    if job_id is None and isinstance(self, str):
        job_id, org_id, targets, options, answers = (
            self,
            job_id,
            org_id,
            targets,
            options,
        )

    config, mongo = _mongo()
    from plugins.postquantumreadiness import store

    store.sync_update_job(mongo, job_id, status="running", phase="start")
    try:
        result = run_discovery(
            config,
            mongo,
            job_id=job_id,
            org_id=org_id,
            targets=targets or [],
            options=options or {},
            answers=answers or {},
        )
        _apply_result(mongo, job_id, result)
        return result
    except Exception as exc:
        LOG.exception("discovery job %s crashed", job_id)
        payload = {
            "status": "failed",
            "error_code": "crash",
            "error_message": str(exc)[:500],
        }
        store.sync_update_job(
            mongo,
            job_id,
            status="failed",
            phase="failed",
            error_code="crash",
            error_message=str(exc)[:500],
            result=payload,
        )
        return payload


def run_discovery(
    config,
    mongo,
    *,
    job_id,
    org_id,
    targets,
    options=None,
    answers=None,
    llm_settings=None,
):
    """Run discovery on a dedicated event loop (Celery worker or thread)."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            arun_discovery(
                config,
                mongo,
                job_id=job_id,
                org_id=org_id,
                targets=targets,
                options=options or {},
                answers=answers or {},
                llm_settings=llm_settings,
            )
        )
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()
        asyncio.set_event_loop(None)


async def arun_discovery(
    config,
    mongo,
    *,
    job_id,
    org_id,
    targets,
    options=None,
    answers=None,
    llm_settings=None,
):
    from plugins.postquantumreadiness import store
    from plugins.postquantumreadiness.graph import compile_graph, initial_state

    if llm_settings is None:
        llm_settings = store.sync_get_llm_settings(mongo)

    adapter = DiscoveryStoreAdapter(config, mongo)
    graph = compile_graph()
    state = initial_state(
        job_id=job_id,
        org_id=org_id,
        targets=targets,
        options=options or {},
        answers=answers or {},
        llm_settings=llm_settings,
        store=adapter,
        mongo=mongo,
        config=config,
    )
    final = await graph.ainvoke(state)
    return final.get("result") or {
        "status": "failed",
        "error_code": "no_result",
        "error_message": "graph ended without result",
    }


try:
    discover_job = _bind_task()
except Exception:
    pass
