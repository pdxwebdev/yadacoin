"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

Crypto readiness SaaS — discover, prioritize, remediate, govern + KEL migration.
"""

from __future__ import annotations

import json
import os

import tornado.web

from yadacoin.http.base import BaseHandler

from . import store
from .scoring import score_asset


class BasePostQuantumReadinessHandler(BaseHandler):
    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")

    def _json_body(self) -> dict:
        if not self.request.body:
            return {}
        try:
            return json.loads(self.request.body.decode("utf-8"))
        except Exception:
            raise ValueError("Invalid JSON body")

    def _err(self, status: int, message: str):
        self.set_status(status)
        return self.render_as_json({"error": message, "status": False})

    def _ok(self, payload):
        if isinstance(payload, dict):
            out = dict(payload)
            out.setdefault("status", True)
            return self.render_as_json(out)
        return self.render_as_json({"status": True, "data": payload})


class HomeHandler(BasePostQuantumReadinessHandler):
    async def get(self):
        self.render(
            "index.html",
            yadacoin=self.yadacoin_vars,
            title="Post-Quantum Readiness — Organizational Readiness",
        )


class OrgsHandler(BasePostQuantumReadinessHandler):
    async def get(self):
        try:
            limit = min(int(self.get_query_argument("limit", "100")), 500)
        except ValueError:
            return self._err(400, "limit must be an integer")
        orgs = await store.list_orgs(self.config, limit=limit)
        return self._ok({"orgs": orgs, "count": len(orgs)})

    async def post(self):
        try:
            body = self._json_body()
            org = await store.create_org(
                self.config, body, seed_demo=bool(body.get("seed_demo"))
            )
        except ValueError as exc:
            return self._err(400, str(exc))
        except Exception as exc:
            return self._err(500, str(exc))
        self.set_status(201)
        return self._ok({"org": org})


class OrgHandler(BasePostQuantumReadinessHandler):
    async def get(self, org_key):
        org = await store.get_org(self.config, org_key)
        if not org:
            return self._err(404, "organization not found")
        return self._ok({"org": org})

    async def put(self, org_key):
        try:
            body = self._json_body()
            org = await store.update_org(self.config, org_key, body)
        except ValueError as exc:
            code = 404 if "not found" in str(exc) else 400
            return self._err(code, str(exc))
        return self._ok({"org": org})

    async def delete(self, org_key):
        ok = await store.delete_org(self.config, org_key)
        if not ok:
            return self._err(404, "organization not found")
        return self._ok({"deleted": True})


class AssetsHandler(BasePostQuantumReadinessHandler):
    async def get(self, org_key):
        try:
            assets = await store.list_assets(self.config, org_key)
        except ValueError as exc:
            return self._err(404, str(exc))
        return self._ok({"assets": assets, "count": len(assets)})

    async def post(self, org_key):
        try:
            body = self._json_body()
            if isinstance(body.get("assets"), list):
                assets = await store.bulk_upsert_assets(
                    self.config, org_key, body["assets"]
                )
                return self._ok({"assets": assets, "count": len(assets)})
            asset = await store.upsert_asset(self.config, org_key, body)
            self.set_status(201)
            return self._ok({"asset": asset})
        except ValueError as exc:
            code = 404 if "not found" in str(exc) else 400
            return self._err(code, str(exc))


class AssetHandler(BasePostQuantumReadinessHandler):
    async def get(self, org_key, asset_id):
        asset = await store.get_asset(self.config, org_key, asset_id)
        if not asset:
            return self._err(404, "asset not found")
        org = await store.get_org(self.config, org_key)
        return self._ok({"asset": asset, "score": score_asset(asset, org or {})})

    async def put(self, org_key, asset_id):
        try:
            body = self._json_body()
            body["id"] = asset_id
            asset = await store.upsert_asset(self.config, org_key, body)
        except ValueError as exc:
            code = 404 if "not found" in str(exc) else 400
            return self._err(code, str(exc))
        return self._ok({"asset": asset})

    async def delete(self, org_key, asset_id):
        ok = await store.delete_asset(self.config, org_key, asset_id)
        if not ok:
            return self._err(404, "asset not found")
        return self._ok({"deleted": True})


class AssessHandler(BasePostQuantumReadinessHandler):
    async def post(self, org_key):
        try:
            body = self._json_body()
            trigger = body.get("trigger") or "manual"
            assessment = await store.run_assessment(
                self.config, org_key, trigger=trigger
            )
        except ValueError as exc:
            return self._err(404, str(exc))
        self.set_status(201)
        return self._ok({"assessment": assessment})

    async def get(self, org_key):
        try:
            limit = min(int(self.get_query_argument("limit", "20")), 100)
            rows = await store.list_assessments(self.config, org_key, limit=limit)
        except ValueError as exc:
            return self._err(404, str(exc))
        return self._ok({"assessments": rows, "count": len(rows)})


class LatestAssessmentHandler(BasePostQuantumReadinessHandler):
    async def get(self, org_key):
        row = await store.latest_assessment(self.config, org_key)
        if not row:
            return self._err(404, "no assessment yet — POST /assess to run one")
        return self._ok({"assessment": row})


class DashboardHandler(BasePostQuantumReadinessHandler):
    async def get(self, org_key):
        try:
            data = await store.dashboard(self.config, org_key)
        except ValueError as exc:
            return self._err(404, str(exc))
        return self._ok(data)


class SnapshotsHandler(BasePostQuantumReadinessHandler):
    async def get(self, org_key):
        try:
            limit = min(int(self.get_query_argument("limit", "90")), 365)
            rows = await store.list_snapshots(self.config, org_key, limit=limit)
        except ValueError as exc:
            return self._err(404, str(exc))
        return self._ok({"snapshots": rows, "count": len(rows)})


class ScorePreviewHandler(BasePostQuantumReadinessHandler):
    """Score a single asset payload without persisting (API-first discovery tools)."""

    async def post(self):
        try:
            body = self._json_body()
            org = body.get("org") or {}
            asset = body.get("asset") or body
            result = score_asset(asset, org)
        except Exception as exc:
            return self._err(400, str(exc))
        return self._ok({"score": result, "asset": asset})


class DemoHandler(BasePostQuantumReadinessHandler):
    async def post(self):
        try:
            org = await store.ensure_demo_org(self.config)
            data = await store.dashboard(self.config, org["id"])
        except Exception as exc:
            return self._err(500, str(exc))
        return self._ok(data)


class MigrationHandler(BasePostQuantumReadinessHandler):
    """KEL migration tracker only — percent KEL, enhanced classical, PQC."""

    async def get(self, org_key):
        try:
            data = await store.dashboard(self.config, org_key)
        except ValueError as exc:
            return self._err(404, str(exc))
        summary = data.get("summary") or {}
        return self._ok(
            {
                "org": data.get("org"),
                "kel_migration": summary.get("kel_migration"),
                "category_progress": summary.get("category_progress"),
                "scored_assets": summary.get("scored_assets")
                or (summary.get("summary") or {}).get("scored_assets"),
                "overall": summary.get("overall"),
                "status_band": summary.get("status_band"),
            }
        )


class TaxonomyHandler(BasePostQuantumReadinessHandler):
    """Full catalog of PQ-unsafe crypto categories and subcategories."""

    async def get(self):
        from .taxonomy import taxonomy_tree

        tree = taxonomy_tree()
        return self._ok(
            {
                "taxonomy": tree,
                "category_count": len(tree),
                "subcategory_count": sum(len(c["subcategories"]) for c in tree),
            }
        )


class CategoryProgressHandler(BasePostQuantumReadinessHandler):
    async def get(self, org_key):
        try:
            data = await store.dashboard(self.config, org_key)
        except ValueError as exc:
            return self._err(404, str(exc))
        summary = data.get("summary") or {}
        return self._ok(
            {
                "org": data.get("org"),
                "category_progress": summary.get("category_progress"),
                "taxonomy": summary.get("taxonomy"),
                "overall": summary.get("overall"),
                "status_band": summary.get("status_band"),
            }
        )


class DiscoverJobsHandler(BasePostQuantumReadinessHandler):
    """
    POST {targets: ["host", "https://x", "host:8443"], options?: {...}, sync?: false}
    Enqueues Celery LangGraph discovery (TLS/HTTP/DNS/KEL). sync=true runs inline.
    """

    async def get(self, org_key):
        org = await store.get_org(self.config, org_key)
        if not org:
            return self._err(404, "organization not found")
        try:
            limit = min(int(self.get_query_argument("limit", "50")), 200)
        except ValueError:
            return self._err(400, "limit must be an integer")
        jobs = await store.list_discovery_jobs(self.config, org["id"], limit=limit)
        return self._ok({"jobs": jobs, "count": len(jobs)})

    async def post(self, org_key):
        org = await store.get_org(self.config, org_key)
        if not org:
            return self._err(404, "organization not found")
        try:
            body = self._json_body()
        except ValueError as exc:
            return self._err(400, str(exc))

        targets = body.get("targets") or body.get("hosts") or []
        if isinstance(targets, str):
            targets = [
                t.strip() for t in targets.replace(",", "\n").splitlines() if t.strip()
            ]
        if not targets:
            return self._err(400, "targets required (hosts, host:port, or URLs)")

        options = body.get("options") or {}
        for key in (
            "skip_llm",
            "skip_assess",
            "timeout",
            "max_targets",
            "clear_demo_seed",
            "replace_prior_discovered",
            "assess_discovered_only",
            "require_llm",
        ):
            if key in body and key not in options:
                options[key] = body[key]
        options.setdefault("clear_demo_seed", True)
        options.setdefault("replace_prior_discovered", True)
        options.setdefault("assess_discovered_only", True)

        job_id = store.new_job_id()
        job = await store.create_discovery_job(
            self.config,
            job_id=job_id,
            org_id=org["id"],
            targets=targets,
            options=options,
        )

        run_sync = bool(body.get("sync"))
        if run_sync:
            try:
                import asyncio

                from plugins.postquantumreadiness.tasks import run_discovery

                llm_settings = await store.get_llm_settings_raw(self.config)
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: run_discovery(
                        self.config,
                        self.config.mongo,
                        job_id=job_id,
                        org_id=org["id"],
                        targets=targets,
                        options=options,
                        llm_settings=llm_settings,
                    ),
                )
                await store.update_discovery_job(
                    self.config,
                    job_id,
                    status=result.get("status") or "failed",
                    phase=result.get("status") or "failed",
                    result=result,
                    assets_discovered=result.get("assets_discovered"),
                    used_llm=result.get("used_llm"),
                    limitations=result.get("limitations"),
                    questions=result.get("questions"),
                    error_code=result.get("error_code"),
                    error_message=result.get("error_message"),
                )
                job = await store.get_discovery_job(self.config, job_id)
                return self._ok({"job": job, "result": result, "mode": "sync"})
            except Exception as exc:
                await store.update_discovery_job(
                    self.config,
                    job_id,
                    status="failed",
                    phase="failed",
                    error_code="sync_error",
                    error_message=str(exc)[:500],
                )
                return self._err(500, str(exc))

        try:
            from plugins.postquantumreadiness.tasks import enqueue_discovery

            async_result = enqueue_discovery(
                job_id=job_id,
                org_id=org["id"],
                targets=targets,
                options=options,
            )
            task_id = getattr(async_result, "id", None)
            await store.update_discovery_job(
                self.config, job_id, celery_task_id=task_id
            )
            job = await store.get_discovery_job(self.config, job_id)
        except Exception as exc:
            await store.update_discovery_job(
                self.config,
                job_id,
                status="failed",
                phase="enqueue",
                error_code="enqueue_failed",
                error_message=f"failed to enqueue celery job: {exc}",
            )
            self.set_status(503)
            return self._ok(
                {
                    "status": False,
                    "error": f"failed to enqueue celery job: {exc}",
                    "job_id": job_id,
                    "hint": "Start worker: python -m plugins.postquantumreadiness "
                    "or POST with sync=true",
                }
            )
        self.set_status(202)
        return self._ok({"job": job, "mode": "celery"})


class DiscoverJobHandler(BasePostQuantumReadinessHandler):
    async def get(self, org_key, job_id):
        org = await store.get_org(self.config, org_key)
        if not org:
            return self._err(404, "organization not found")
        job = await store.get_discovery_job(self.config, job_id)
        if not job or job.get("org_id") != org["id"]:
            return self._err(404, "job not found")
        return self._ok({"job": job})


class DiscoverResumeHandler(BasePostQuantumReadinessHandler):
    """Resume a needs_input job after the user answers questions / provides keys."""

    async def post(self, org_key, job_id):
        org = await store.get_org(self.config, org_key)
        if not org:
            return self._err(404, "organization not found")
        job = await store.get_discovery_job(self.config, job_id)
        if not job or job.get("org_id") != org["id"]:
            return self._err(404, "job not found")
        try:
            body = self._json_body()
        except ValueError as exc:
            return self._err(400, str(exc))

        answers = body.get("answers") or body
        # Persist API key into LLM settings if provided
        if answers.get("api_key") or answers.get("provider") or answers.get("model"):
            patch = {}
            if answers.get("api_key"):
                patch["api_key"] = answers["api_key"]
            if answers.get("provider"):
                patch["provider"] = answers["provider"]
            if answers.get("model"):
                patch["model"] = answers["model"]
            if answers.get("base_url"):
                patch["base_url"] = answers["base_url"]
            try:
                await store.save_llm_settings(self.config, patch)
            except Exception as exc:
                return self._err(400, f"failed to save llm settings: {exc}")

        targets = list(job.get("targets") or [])
        extra = answers.get("additional_targets") or answers.get("targets")
        if extra:
            if isinstance(extra, str):
                extra = [
                    t.strip()
                    for t in extra.replace(",", "\n").splitlines()
                    if t.strip()
                ]
            targets.extend(extra)

        options = dict(job.get("options") or {})
        options.update(body.get("options") or {})

        try:
            import asyncio

            from plugins.postquantumreadiness.tasks import run_discovery

            llm_settings = await store.get_llm_settings_raw(self.config)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: run_discovery(
                    self.config,
                    self.config.mongo,
                    job_id=job_id,
                    org_id=org["id"],
                    targets=targets,
                    options=options,
                    answers=answers,
                    llm_settings=llm_settings,
                ),
            )
            await store.update_discovery_job(
                self.config,
                job_id,
                status=result.get("status") or "failed",
                phase=result.get("status") or "failed",
                result=result,
                targets=targets,
                assets_discovered=result.get("assets_discovered"),
                used_llm=result.get("used_llm"),
                limitations=result.get("limitations"),
                questions=result.get("questions"),
                error_code=result.get("error_code"),
                error_message=result.get("error_message"),
            )
            job = await store.get_discovery_job(self.config, job_id)
            return self._ok({"job": job, "result": result, "mode": "resume"})
        except Exception as exc:
            return self._err(500, str(exc))


class LlmSettingsHandler(BasePostQuantumReadinessHandler):
    async def options(self):
        self.set_status(204)

    async def get(self):
        from .llm import list_providers

        settings = await store.get_llm_settings(self.config)
        return self._ok({"settings": settings, "providers": list_providers()})

    async def put(self):
        return await self._save()

    async def post(self):
        """
        POST {action: "save", ...} → persist settings (preferred over PUT)
        POST {action: "test", ...} or legacy body → test connection
        """
        try:
            body = self._json_body()
        except ValueError as exc:
            return self._err(400, str(exc))

        action = (body.get("action") or "").lower().strip()
        if action in ("save", "update", "set") or body.get("save") is True:
            return await self._save(body)

        if action in ("test", "ping") or body.get("test") is True:
            return await self._test(body)

        # Legacy: if api_key present without action, save (user intent is persist)
        if body.get("api_key") or body.get("kilo_api_key"):
            if body.get("test_only"):
                return await self._test(body)
            return await self._save(body)

        # Default legacy POST = test with optional overrides, else saved settings
        return await self._test(body)

    async def _save(self, body=None):
        try:
            if body is None:
                body = self._json_body()
            settings = await store.save_llm_settings(self.config, body)
        except ValueError as exc:
            return self._err(400, str(exc))
        except Exception as exc:
            return self._err(500, str(exc))
        return self._ok({"settings": settings, "saved": True})

    async def _test(self, body=None):
        from .llm import test_connection

        body = body or {}
        try:
            if body.get("api_key") or body.get("provider") or body.get("base_url"):
                # Merge with saved so partial test bodies still work
                raw = await store.get_llm_settings_raw(self.config)
                merged = dict(raw)
                for k in ("provider", "api_key", "base_url", "model", "enabled"):
                    if body.get(k) not in (None, ""):
                        merged[k] = body[k]
                result = test_connection(merged)
            else:
                raw = await store.get_llm_settings_raw(self.config)
                result = test_connection(raw)
        except Exception as exc:
            return self._err(500, str(exc))
        return self._ok({"test": result})


class ClearDemoAssetsHandler(BasePostQuantumReadinessHandler):
    async def post(self, org_key):
        try:
            n = await store.delete_assets_by_filter(
                self.config, org_key, demo_seed=True, tags=["demo_seed"]
            )
        except ValueError as exc:
            return self._err(404, str(exc))
        return self._ok({"deleted": n})


HANDLERS = [
    (r"/post-quantum-readiness/?", HomeHandler),
    (r"/post-quantum-readiness/api/v1/orgs/?", OrgsHandler),
    (r"/post-quantum-readiness/api/v1/orgs/([^/]+)/?", OrgHandler),
    (r"/post-quantum-readiness/api/v1/orgs/([^/]+)/assets/?", AssetsHandler),
    (r"/post-quantum-readiness/api/v1/orgs/([^/]+)/assets/([^/]+)/?", AssetHandler),
    (r"/post-quantum-readiness/api/v1/orgs/([^/]+)/assess/?", AssessHandler),
    (
        r"/post-quantum-readiness/api/v1/orgs/([^/]+)/assessment/latest/?",
        LatestAssessmentHandler,
    ),
    (r"/post-quantum-readiness/api/v1/orgs/([^/]+)/dashboard/?", DashboardHandler),
    (r"/post-quantum-readiness/api/v1/orgs/([^/]+)/snapshots/?", SnapshotsHandler),
    (r"/post-quantum-readiness/api/v1/orgs/([^/]+)/migration/?", MigrationHandler),
    (
        r"/post-quantum-readiness/api/v1/orgs/([^/]+)/categories/?",
        CategoryProgressHandler,
    ),
    (r"/post-quantum-readiness/api/v1/taxonomy/?", TaxonomyHandler),
    (r"/post-quantum-readiness/api/v1/orgs/([^/]+)/discover/?", DiscoverJobsHandler),
    (
        r"/post-quantum-readiness/api/v1/orgs/([^/]+)/discover/([^/]+)/resume/?",
        DiscoverResumeHandler,
    ),
    (
        r"/post-quantum-readiness/api/v1/orgs/([^/]+)/discover/([^/]+)/?",
        DiscoverJobHandler,
    ),
    (
        r"/post-quantum-readiness/api/v1/orgs/([^/]+)/clear-demo/?",
        ClearDemoAssetsHandler,
    ),
    (r"/post-quantum-readiness/api/v1/llm-settings/?", LlmSettingsHandler),
    (r"/post-quantum-readiness/api/v1/score-preview/?", ScorePreviewHandler),
    (r"/post-quantum-readiness/api/v1/demo/?", DemoHandler),
    (
        r"/post-quantum-readiness/static/(.*)",
        tornado.web.StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "templates")},
    ),
]
