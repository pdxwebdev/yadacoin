"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

Mongo persistence for crypto readiness orgs, assets, assessments, snapshots.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Optional

from .scoring import demo_seed_assets, score_asset, score_organization


def _now() -> int:
    return int(time.time())


def _nid() -> str:
    return uuid.uuid4().hex[:16]


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or f"org-{_nid()}"


JOBS = "post_quantum_readiness_jobs"
LLM_SETTINGS = "post_quantum_readiness_llm_settings"
SETTINGS_DOC_ID = "default"


def _llm_secrets_path() -> str:
    """Filesystem fallback so API keys survive even if site_db write fails."""
    import os

    for candidate in (
        os.environ.get("PQR_LLM_SECRETS_PATH"),
        os.path.join(os.getcwd(), "config", "pqr_llm_secrets.json"),
        os.path.join(os.getcwd(), "pqr_llm_secrets.json"),
        os.path.join(os.path.dirname(__file__), "pqr_llm_secrets.json"),
    ):
        if candidate:
            return candidate
    return os.path.join(os.getcwd(), "pqr_llm_secrets.json")


def _read_llm_secrets_file() -> Dict[str, Any]:
    import json
    import os

    path = _llm_secrets_path()
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _write_llm_secrets_file(doc: Dict[str, Any]) -> str:
    import json
    import os

    path = _llm_secrets_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    # never write empty key over existing file key unless explicitly cleared
    payload = {
        "id": SETTINGS_DOC_ID,
        "provider": doc.get("provider"),
        "api_key": doc.get("api_key") or "",
        "base_url": doc.get("base_url") or "",
        "model": doc.get("model") or "",
        "enabled": doc.get("enabled", True),
        "require_for_discovery": doc.get("require_for_discovery", False),
        "updated_at": doc.get("updated_at") or _now(),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    return path


def site_db(config):
    return config.mongo.async_site_db


def sync_site_db(mongo):
    if hasattr(mongo, "site_db") and mongo.site_db is not None:
        return mongo.site_db
    return mongo.async_site_db


def mongo_from_config(config):
    return getattr(config, "mongo", config)


async def ensure_indexes(config) -> None:
    site = site_db(config)
    await site.post_quantum_readiness_orgs.create_index("id", unique=True)
    await site.post_quantum_readiness_orgs.create_index("slug", unique=True)
    await site.post_quantum_readiness_assets.create_index(
        [("org_id", 1), ("id", 1)], unique=True
    )
    await site.post_quantum_readiness_assets.create_index("org_id")
    await site.post_quantum_readiness_assessments.create_index(
        [("org_id", 1), ("created_at", -1)]
    )
    await site.post_quantum_readiness_snapshots.create_index(
        [("org_id", 1), ("created_at", -1)]
    )
    await site[JOBS].create_index("job_id", unique=True)
    await site[JOBS].create_index([("org_id", 1), ("created_at", -1)])
    await site[JOBS].create_index([("status", 1), ("created_at", -1)])
    await site[LLM_SETTINGS].create_index("id", unique=True)
    await site.post_quantum_readiness_assets.create_index([("org_id", 1), ("tags", 1)])
    await site.post_quantum_readiness_assets.create_index(
        [("org_id", 1), ("metadata.host", 1)]
    )


async def create_org(
    config, payload: Dict[str, Any], seed_demo: bool = False
) -> Dict[str, Any]:
    site = site_db(config)
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")

    org_id = payload.get("id") or _nid()
    slug = payload.get("slug") or _slugify(name)
    existing = await site.post_quantum_readiness_orgs.find_one(
        {"$or": [{"id": org_id}, {"slug": slug}]}, {"_id": 0}
    )
    if existing:
        raise ValueError("organization id or slug already exists")

    org = {
        "id": org_id,
        "slug": slug,
        "name": name,
        "industry": payload.get("industry") or "",
        "size": payload.get("size") or "",
        "contact_email": payload.get("contact_email") or "",
        "has_crypto_policy": bool(payload.get("has_crypto_policy", False)),
        "has_quantum_roadmap": bool(payload.get("has_quantum_roadmap", False)),
        "notes": payload.get("notes") or "",
        "created_at": _now(),
        "updated_at": _now(),
    }
    await site.post_quantum_readiness_orgs.insert_one(dict(org))

    if seed_demo or payload.get("seed_demo"):
        for asset in demo_seed_assets(org_id):
            asset["created_at"] = _now()
            asset["updated_at"] = _now()
            await site.post_quantum_readiness_assets.insert_one(dict(asset))
        await run_assessment(config, org_id, trigger="seed_demo")

    return org


async def list_orgs(config, limit: int = 100) -> List[Dict[str, Any]]:
    site = site_db(config)
    return (
        await site.post_quantum_readiness_orgs.find({}, {"_id": 0})
        .sort([("updated_at", -1)])
        .to_list(length=min(limit, 500))
    )


async def get_org(config, org_key: str) -> Optional[Dict[str, Any]]:
    site = site_db(config)
    org = await site.post_quantum_readiness_orgs.find_one(
        {"$or": [{"id": org_key}, {"slug": org_key}]}, {"_id": 0}
    )
    return org


async def update_org(config, org_key: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    org = await get_org(config, org_key)
    if not org:
        raise ValueError("organization not found")
    allowed = {
        "name",
        "industry",
        "size",
        "contact_email",
        "has_crypto_policy",
        "has_quantum_roadmap",
        "notes",
    }
    updates = {k: patch[k] for k in allowed if k in patch}
    if "name" in updates and updates["name"]:
        updates["name"] = str(updates["name"]).strip()
    if "has_crypto_policy" in updates:
        updates["has_crypto_policy"] = bool(updates["has_crypto_policy"])
    if "has_quantum_roadmap" in updates:
        updates["has_quantum_roadmap"] = bool(updates["has_quantum_roadmap"])
    updates["updated_at"] = _now()
    site = site_db(config)
    await site.post_quantum_readiness_orgs.update_one(
        {"id": org["id"]}, {"$set": updates}
    )
    return await get_org(config, org["id"])


async def delete_org(config, org_key: str) -> bool:
    org = await get_org(config, org_key)
    if not org:
        return False
    site = site_db(config)
    oid = org["id"]
    await site.post_quantum_readiness_assets.delete_many({"org_id": oid})
    await site.post_quantum_readiness_assessments.delete_many({"org_id": oid})
    await site.post_quantum_readiness_snapshots.delete_many({"org_id": oid})
    await site.post_quantum_readiness_orgs.delete_one({"id": oid})
    return True


def _normalize_asset(
    org_id: str, payload: Dict[str, Any], existing: Optional[Dict] = None
) -> Dict[str, Any]:
    base = dict(existing or {})
    base.update({k: v for k, v in payload.items() if v is not None})
    asset_id = base.get("id") or _nid()
    name = (base.get("name") or "").strip()
    if not name:
        raise ValueError("asset name is required")
    has_kel = base.get("has_kel")
    if has_kel is not None:
        has_kel = bool(has_kel)
    out = {
        "id": asset_id,
        "org_id": org_id,
        "name": name,
        "description": base.get("description") or "",
        "algorithm": base.get("algorithm") or "",
        "public_key_algorithm": base.get("public_key_algorithm")
        or base.get("algorithm")
        or "",
        "protocol": base.get("protocol") or "",
        "transport": base.get("transport") or base.get("protocol") or "",
        "environment": base.get("environment") or "production",
        "exposure": base.get("exposure") or "internal",
        "business_criticality": base.get("business_criticality") or "medium",
        "kel_status": base.get("kel_status")
        or ("kel_abstracted" if has_kel else "none"),
        "has_kel": has_kel if has_kel is not None else False,
        "owner": base.get("owner") or "",
        "owner_email": base.get("owner_email") or "",
        "key_rotation_days": base.get("key_rotation_days"),
        "hsm_backed": bool(base.get("hsm_backed", False)),
        "certificate_auto_renew": bool(base.get("certificate_auto_renew", False)),
        "expired": bool(base.get("expired", False)),
        "expiring_soon": bool(base.get("expiring_soon", False)),
        "in_policy": base.get("in_policy"),
        "data_classification": base.get("data_classification") or "",
        "category": base.get("category") or base.get("category_id") or "",
        "subcategory": base.get("subcategory") or base.get("subcategory_id") or "",
        "tags": base.get("tags") or [],
        "metadata": base.get("metadata") or {},
        "created_at": base.get("created_at") or _now(),
        "updated_at": _now(),
    }
    if not out.get("category") or not out.get("subcategory"):
        from .taxonomy import infer_category

        cat, sub, src = infer_category(out)
        out["category"] = out.get("category") or cat
        out["subcategory"] = out.get("subcategory") or sub
        out["category_source"] = src
    else:
        out["category_source"] = base.get("category_source") or "explicit"
    return out


async def upsert_asset(config, org_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    org = await get_org(config, org_key)
    if not org:
        raise ValueError("organization not found")
    site = site_db(config)
    existing = None
    if payload.get("id"):
        existing = await site.post_quantum_readiness_assets.find_one(
            {"org_id": org["id"], "id": payload["id"]}, {"_id": 0}
        )
    asset = _normalize_asset(org["id"], payload, existing)
    await site.post_quantum_readiness_assets.update_one(
        {"org_id": org["id"], "id": asset["id"]},
        {"$set": asset},
        upsert=True,
    )
    await site.post_quantum_readiness_orgs.update_one(
        {"id": org["id"]}, {"$set": {"updated_at": _now()}}
    )
    return asset


async def bulk_upsert_assets(
    config, org_key: str, assets: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    out = []
    for row in assets:
        out.append(await upsert_asset(config, org_key, row))
    return out


async def list_assets(config, org_key: str, limit: int = 500) -> List[Dict[str, Any]]:
    org = await get_org(config, org_key)
    if not org:
        raise ValueError("organization not found")
    site = site_db(config)
    return (
        await site.post_quantum_readiness_assets.find({"org_id": org["id"]}, {"_id": 0})
        .sort([("name", 1)])
        .to_list(length=min(limit, 2000))
    )


async def get_asset(config, org_key: str, asset_id: str) -> Optional[Dict[str, Any]]:
    org = await get_org(config, org_key)
    if not org:
        return None
    site = site_db(config)
    return await site.post_quantum_readiness_assets.find_one(
        {"org_id": org["id"], "id": asset_id}, {"_id": 0}
    )


async def delete_asset(config, org_key: str, asset_id: str) -> bool:
    org = await get_org(config, org_key)
    if not org:
        return False
    site = site_db(config)
    res = await site.post_quantum_readiness_assets.delete_one(
        {"org_id": org["id"], "id": asset_id}
    )
    return res.deleted_count > 0


async def score_single_asset(config, org_key: str, asset_id: str) -> Dict[str, Any]:
    org = await get_org(config, org_key)
    if not org:
        raise ValueError("organization not found")
    asset = await get_asset(config, org_key, asset_id)
    if not asset:
        raise ValueError("asset not found")
    return {"asset": asset, "score": score_asset(asset, org)}


async def run_assessment(
    config, org_key: str, trigger: str = "manual"
) -> Dict[str, Any]:
    org = await get_org(config, org_key)
    if not org:
        raise ValueError("organization not found")
    assets = await list_assets(config, org["id"])
    summary = score_organization(org, assets)

    # Per-asset detail for storage
    details = []
    for a in assets:
        details.append(
            {"asset_id": a["id"], "name": a.get("name"), **score_asset(a, org)}
        )

    assessment = {
        "id": _nid(),
        "org_id": org["id"],
        "trigger": trigger,
        "created_at": _now(),
        "summary": {
            "overall": summary["overall"],
            "status_band": summary["status_band"],
            "asset_count": summary["asset_count"],
            "dimensions": summary["dimensions"],
            "kel_migration": summary["kel_migration"],
            "priority_findings": summary["priority_findings"],
            "scored_assets": summary["scored_assets"],
        },
        "asset_scores": details,
    }

    site = site_db(config)
    await site.post_quantum_readiness_assessments.insert_one(dict(assessment))

    snapshot = {
        "id": _nid(),
        "org_id": org["id"],
        "created_at": _now(),
        "overall": summary["overall"],
        "status_band": summary["status_band"],
        "kel_percent": summary["kel_migration"]["percent_with_kel"],
        "agility_enhanced_percent": summary["kel_migration"][
            "percent_agility_enhanced"
        ],
        "quantum_safe_percent": summary["kel_migration"]["percent_quantum_safe"],
        "migration_stage": summary["kel_migration"]["migration_stage"],
        "dimensions": summary["dimensions"],
        "assessment_id": assessment["id"],
    }
    await site.post_quantum_readiness_snapshots.insert_one(dict(snapshot))
    await site.post_quantum_readiness_orgs.update_one(
        {"id": org["id"]},
        {
            "$set": {
                "updated_at": _now(),
                "latest_overall": summary["overall"],
                "latest_status_band": summary["status_band"],
                "latest_kel_percent": summary["kel_migration"]["percent_with_kel"],
                "latest_assessment_id": assessment["id"],
            }
        },
    )

    assessment.pop("_id", None)
    return assessment


async def latest_assessment(config, org_key: str) -> Optional[Dict[str, Any]]:
    org = await get_org(config, org_key)
    if not org:
        return None
    site = site_db(config)
    return await site.post_quantum_readiness_assessments.find_one(
        {"org_id": org["id"]},
        {"_id": 0},
        sort=[("created_at", -1)],
    )


async def list_assessments(
    config, org_key: str, limit: int = 20
) -> List[Dict[str, Any]]:
    org = await get_org(config, org_key)
    if not org:
        raise ValueError("organization not found")
    site = site_db(config)
    return (
        await site.post_quantum_readiness_assessments.find(
            {"org_id": org["id"]},
            {"_id": 0, "asset_scores": 0},
        )
        .sort([("created_at", -1)])
        .to_list(length=min(limit, 100))
    )


async def list_snapshots(config, org_key: str, limit: int = 90) -> List[Dict[str, Any]]:
    org = await get_org(config, org_key)
    if not org:
        raise ValueError("organization not found")
    site = site_db(config)
    rows = (
        await site.post_quantum_readiness_snapshots.find(
            {"org_id": org["id"]}, {"_id": 0}
        )
        .sort([("created_at", 1)])
        .to_list(length=min(limit, 365))
    )
    return rows


async def dashboard(config, org_key: str) -> Dict[str, Any]:
    from .taxonomy import taxonomy_tree

    org = await get_org(config, org_key)
    if not org:
        raise ValueError("organization not found")
    assets = await list_assets(config, org["id"])
    assessment = await latest_assessment(config, org["id"])
    snapshots = await list_snapshots(config, org["id"], limit=90)

    # Always recompute live scores so taxonomy/category_progress stay current
    # (stored assessments from older builds may lack these fields).
    summary = score_organization(org, assets)
    if assessment:
        summary["latest_assessment_id"] = assessment.get("id")
        summary["latest_assessment_at"] = assessment.get("created_at")
        # Keep historical overall if user wants — but prefer live for UI
        stored = assessment.get("summary") or {}
        summary["stored_overall"] = stored.get("overall")

    summary["taxonomy"] = taxonomy_tree()

    return {
        "org": org,
        "summary": summary,
        "assets": assets,
        "latest_assessment": assessment,
        "snapshots": snapshots,
        "product": {
            "name": "Post-Quantum Readiness",
            "tagline": "From cryptography chaos to KEL-powered quantum readiness",
            "differentiator": (
                "Tracks migration to the KEL abstraction layer. Classical ECC/RSA "
                "systems earn enhanced crypto-agility status once wrapped in KEL — "
                "before quantum-safe algorithms are selected."
            ),
        },
    }


async def ensure_demo_org(config) -> Dict[str, Any]:
    """Idempotent demo tenant for empty deployments."""
    site = site_db(config)
    existing = await site.post_quantum_readiness_orgs.find_one(
        {"slug": "acme-financial"}, {"_id": 0}
    )
    if existing:
        return existing
    return await create_org(
        config,
        {
            "name": "Acme Financial",
            "slug": "acme-financial",
            "industry": "financial_services",
            "size": "enterprise",
            "contact_email": "ciso@acme.example",
            "has_crypto_policy": True,
            "has_quantum_roadmap": True,
            "notes": "Demo organization for crypto readiness + KEL migration",
            "seed_demo": True,
        },
        seed_demo=True,
    )


# ── Discovery jobs ────────────────────────────────────────────────────────────


def new_job_id() -> str:
    return uuid.uuid4().hex


def public_job(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    out = dict(doc)
    out.pop("_id", None)
    return out


async def create_discovery_job(
    config,
    *,
    job_id: str,
    org_id: str,
    targets: List[Any],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    doc = {
        "job_id": job_id,
        "org_id": org_id,
        "targets": targets,
        "options": options or {},
        "status": "queued",
        "phase": "queued",
        "error_code": None,
        "error_message": None,
        "steps": [],
        "result": None,
        "assets_discovered": None,
        "used_llm": False,
        "celery_task_id": None,
        "created_at": _now(),
        "updated_at": _now(),
        "finished_at": None,
    }
    await site_db(config)[JOBS].insert_one(dict(doc))
    return public_job(doc)


async def get_discovery_job(config, job_id: str) -> Optional[Dict[str, Any]]:
    return public_job(
        await site_db(config)[JOBS].find_one({"job_id": job_id}, {"_id": 0})
    )


async def list_discovery_jobs(
    config, org_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    rows = (
        await site_db(config)[JOBS]
        .find({"org_id": org_id}, {"_id": 0})
        .sort([("created_at", -1)])
        .to_list(length=min(limit, 200))
    )
    return rows


async def update_discovery_job(
    config, job_id: str, **fields
) -> Optional[Dict[str, Any]]:
    fields["updated_at"] = _now()
    if fields.get("status") in ("succeeded", "failed"):
        fields.setdefault("finished_at", _now())
    await site_db(config)[JOBS].update_one({"job_id": job_id}, {"$set": fields})
    return await get_discovery_job(config, job_id)


def sync_update_job(mongo, job_id: str, **fields) -> None:
    fields["updated_at"] = _now()
    if fields.get("status") in ("succeeded", "failed"):
        fields.setdefault("finished_at", _now())
    sync_site_db(mongo)[JOBS].update_one({"job_id": job_id}, {"$set": fields})


def sync_append_job_step(mongo, job_id: str, step: Dict[str, Any]) -> None:
    step = dict(step)
    step.setdefault("at", _now())
    sync_site_db(mongo)[JOBS].update_one(
        {"job_id": job_id},
        {"$push": {"steps": step}, "$set": {"updated_at": _now()}},
    )


def sync_get_org(mongo, org_key: str) -> Optional[Dict[str, Any]]:
    db = sync_site_db(mongo)
    return db.post_quantum_readiness_orgs.find_one(
        {"$or": [{"id": org_key}, {"slug": org_key}]}, {"_id": 0}
    )


def sync_upsert_asset(
    config, mongo, org_key: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    org = sync_get_org(mongo, org_key)
    if not org:
        raise ValueError("organization not found")
    db = sync_site_db(mongo)
    existing = None
    if payload.get("id"):
        existing = db.post_quantum_readiness_assets.find_one(
            {"org_id": org["id"], "id": payload["id"]}, {"_id": 0}
        )
    asset = _normalize_asset(org["id"], payload, existing)
    db.post_quantum_readiness_assets.update_one(
        {"org_id": org["id"], "id": asset["id"]},
        {"$set": asset},
        upsert=True,
    )
    db.post_quantum_readiness_orgs.update_one(
        {"id": org["id"]}, {"$set": {"updated_at": _now()}}
    )
    return asset


def sync_list_assets(mongo, org_id: str, limit: int = 2000) -> List[Dict[str, Any]]:
    return list(
        sync_site_db(mongo)
        .post_quantum_readiness_assets.find({"org_id": org_id}, {"_id": 0})
        .sort([("name", 1)])
        .limit(min(limit, 2000))
    )


def _merge_llm_docs(*docs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Prefer non-empty api_key / fields from first docs that have them."""
    merged: Dict[str, Any] = {}
    for doc in docs:
        if not doc:
            continue
        for k, v in doc.items():
            if k == "_id":
                continue
            if k == "api_key":
                if v and str(v).strip() and not merged.get("api_key"):
                    merged["api_key"] = str(v).strip()
                continue
            if v in (None, ""):
                continue
            if k not in merged or merged[k] in (None, ""):
                merged[k] = v
    return merged


async def _load_llm_doc(config) -> Dict[str, Any]:
    mongo_doc = None
    try:
        mongo_doc = await site_db(config)[LLM_SETTINGS].find_one(
            {"id": SETTINGS_DOC_ID}, {"_id": 0}
        )
    except Exception:
        mongo_doc = None
    file_doc = _read_llm_secrets_file()
    return _merge_llm_docs(mongo_doc, file_doc)


async def get_llm_settings(config) -> Dict[str, Any]:
    from .llm import public_settings, resolve_settings

    doc = await _load_llm_doc(config)
    resolved = resolve_settings(doc)
    return public_settings(resolved)


async def get_llm_settings_raw(config) -> Dict[str, Any]:
    """Full settings including api_key for server-side LLM calls."""
    from .llm import resolve_settings

    doc = await _load_llm_doc(config)
    return resolve_settings(doc)


def sync_get_llm_settings(mongo) -> Dict[str, Any]:
    from .llm import resolve_settings

    mongo_doc = None
    try:
        mongo_doc = sync_site_db(mongo)[LLM_SETTINGS].find_one(
            {"id": SETTINGS_DOC_ID}, {"_id": 0}
        )
    except Exception:
        mongo_doc = None
    file_doc = _read_llm_secrets_file()
    return resolve_settings(_merge_llm_docs(mongo_doc, file_doc))


async def save_llm_settings(config, payload: Dict[str, Any]) -> Dict[str, Any]:
    from .llm import PROVIDER_PRESETS, public_settings, resolve_settings

    existing = await _load_llm_doc(config)
    provider = (
        (payload.get("provider") or existing.get("provider") or "kilo").lower().strip()
    )
    preset = PROVIDER_PRESETS.get(provider) or PROVIDER_PRESETS["custom"]

    # Accept several client field names
    raw_key = payload.get("api_key")
    if raw_key is None:
        raw_key = payload.get("kilo_api_key") or payload.get("key")
    if raw_key is None or str(raw_key).strip() == "":
        api_key = (existing.get("api_key") or "").strip()
    else:
        api_key = str(raw_key).strip()
        # ignore masked placeholders
        if (
            api_key.startswith("••••")
            or api_key.startswith("****")
            or api_key == existing.get("api_key_masked")
        ):
            api_key = (existing.get("api_key") or "").strip()

    base_url = payload.get("base_url")
    if base_url is None or str(base_url).strip() == "":
        base_url = existing.get("base_url") or preset.get("base_url") or ""
    else:
        base_url = str(base_url).strip().rstrip("/")

    model = payload.get("model")
    if model is None or str(model).strip() == "":
        model = existing.get("model") or preset.get("default_model") or "x-ai/grok-4.5"
    else:
        model = str(model).strip()

    clear_key = bool(payload.get("clear_api_key"))
    if clear_key:
        api_key = ""

    doc = {
        "id": SETTINGS_DOC_ID,
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "enabled": bool(payload["enabled"])
        if "enabled" in payload
        else existing.get("enabled", True),
        "require_for_discovery": bool(
            payload["require_for_discovery"]
            if "require_for_discovery" in payload
            else existing.get("require_for_discovery", False)
        ),
        "updated_at": _now(),
        "created_at": existing.get("created_at") or _now(),
    }

    mongo_ok = False
    mongo_error = None
    try:
        result = await site_db(config)[LLM_SETTINGS].replace_one(
            {"id": SETTINGS_DOC_ID}, doc, upsert=True
        )
        # verify round-trip
        check = await site_db(config)[LLM_SETTINGS].find_one(
            {"id": SETTINGS_DOC_ID}, {"_id": 0}
        )
        mongo_ok = bool(check) and (
            clear_key or not api_key or bool((check or {}).get("api_key"))
        )
        if not mongo_ok:
            mongo_error = "mongo write did not persist api_key"
    except Exception as exc:
        mongo_error = str(exc)[:300]

    file_path = ""
    try:
        file_path = _write_llm_secrets_file(doc)
    except Exception as exc:
        if not mongo_ok:
            raise ValueError(
                f"failed to save LLM settings (mongo: {mongo_error}; file: {exc})"
            ) from exc

    resolved = resolve_settings(doc)
    public = public_settings(resolved)
    public["saved"] = True
    public["mongo_ok"] = mongo_ok
    public["file_path"] = file_path
    if mongo_error and not mongo_ok:
        public["mongo_error"] = mongo_error
    if not public.get("api_key_set") and api_key:
        # should not happen — surface clearly
        raise ValueError("api_key was provided but not marked set after save")
    return public


async def delete_assets_by_filter(
    config,
    org_key: str,
    *,
    tags: Optional[List[str]] = None,
    hosts: Optional[List[str]] = None,
    demo_seed: bool = False,
) -> int:
    org = await get_org(config, org_key)
    if not org:
        raise ValueError("organization not found")
    return sync_delete_assets(
        config.mongo,
        org["id"],
        tags=tags,
        hosts=hosts,
        demo_seed=demo_seed,
    )


def sync_delete_assets(
    mongo,
    org_id: str,
    *,
    tags: Optional[List[str]] = None,
    hosts: Optional[List[str]] = None,
    demo_seed: bool = False,
) -> int:
    """Delete matching assets. OR across provided criteria."""
    query: Dict[str, Any] = {"org_id": org_id}
    or_clauses: List[Dict[str, Any]] = []
    if tags:
        or_clauses.append({"tags": {"$in": list(tags)}})
    if hosts:
        or_clauses.append({"metadata.host": {"$in": [h.lower() for h in hosts]}})
    if demo_seed:
        or_clauses.append({"tags": "demo_seed"})
        or_clauses.append({"metadata.source": "demo_seed"})
        or_clauses.append({"id": {"$regex": f"^{re.escape(org_id)}-asset-"}})
    if not or_clauses:
        return 0
    query["$or"] = or_clauses
    res = sync_site_db(mongo).post_quantum_readiness_assets.delete_many(query)
    return int(res.deleted_count or 0)


def sync_run_assessment(
    config, mongo, org_key: str, trigger: str = "discovery_agent"
) -> Dict[str, Any]:
    org = sync_get_org(mongo, org_key)
    if not org:
        raise ValueError("organization not found")
    assets = sync_list_assets(mongo, org["id"])
    summary = score_organization(org, assets)
    details = [
        {"asset_id": a["id"], "name": a.get("name"), **score_asset(a, org)}
        for a in assets
    ]
    assessment = {
        "id": _nid(),
        "org_id": org["id"],
        "trigger": trigger,
        "created_at": _now(),
        "summary": {
            "overall": summary["overall"],
            "status_band": summary["status_band"],
            "asset_count": summary["asset_count"],
            "dimensions": summary["dimensions"],
            "kel_migration": summary["kel_migration"],
            "priority_findings": summary["priority_findings"],
            "scored_assets": summary["scored_assets"],
        },
        "asset_scores": details,
    }
    db = sync_site_db(mongo)
    db.post_quantum_readiness_assessments.insert_one(dict(assessment))
    snapshot = {
        "id": _nid(),
        "org_id": org["id"],
        "created_at": _now(),
        "overall": summary["overall"],
        "status_band": summary["status_band"],
        "kel_percent": summary["kel_migration"]["percent_with_kel"],
        "agility_enhanced_percent": summary["kel_migration"][
            "percent_agility_enhanced"
        ],
        "quantum_safe_percent": summary["kel_migration"]["percent_quantum_safe"],
        "migration_stage": summary["kel_migration"]["migration_stage"],
        "dimensions": summary["dimensions"],
        "assessment_id": assessment["id"],
    }
    db.post_quantum_readiness_snapshots.insert_one(dict(snapshot))
    db.post_quantum_readiness_orgs.update_one(
        {"id": org["id"]},
        {
            "$set": {
                "updated_at": _now(),
                "latest_overall": summary["overall"],
                "latest_status_band": summary["status_band"],
                "latest_kel_percent": summary["kel_migration"]["percent_with_kel"],
                "latest_assessment_id": assessment["id"],
            }
        },
    )
    assessment.pop("_id", None)
    return assessment
