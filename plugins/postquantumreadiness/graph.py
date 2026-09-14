"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

LangGraph discovery pipeline:
  load → probe → evaluate → enrich → normalize → persist → assess → ok|needs_input|fail
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from plugins.postquantumreadiness.llm import enrich_findings
from plugins.postquantumreadiness.probes import parse_targets, probe_target
from plugins.postquantumreadiness.scoring import score_organization

LOG = logging.getLogger("postquantumreadiness.graph")


class _SequentialGraph:
    """Fallback runner when langgraph is not installed."""

    async def ainvoke(self, state):
        state = node_load(state)
        if state.get("error_code") and state.get("status") != "needs_input":
            return node_fail(state)
        if state.get("status") == "needs_input":
            return node_needs_input(state)

        state = node_probe(state)
        if state.get("error_code") and state.get("status") != "needs_input":
            return node_fail(state)

        state = node_evaluate(state)
        if state.get("status") == "needs_input":
            return node_needs_input(state)
        if state.get("error_code"):
            return node_fail(state)

        state = node_enrich(state)
        if state.get("status") == "needs_input":
            return node_needs_input(state)

        state = node_normalize(state)
        if state.get("error_code"):
            return node_fail(state)

        state = node_persist(state)
        if state.get("error_code"):
            return node_fail(state)

        state = node_assess(state)
        if state.get("error_code"):
            return node_fail(state)
        return node_ok(state)


def compile_graph():
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        LOG.warning("langgraph not installed; using sequential discovery pipeline")
        return _SequentialGraph()

    graph = StateGraph(dict)
    for name, fn in (
        ("load", node_load),
        ("probe", node_probe),
        ("evaluate", node_evaluate),
        ("enrich", node_enrich),
        ("normalize", node_normalize),
        ("persist", node_persist),
        ("assess", node_assess),
        ("ok", node_ok),
        ("needs_input", node_needs_input),
        ("fail", node_fail),
    ):
        graph.add_node(name, fn)

    graph.set_entry_point("load")

    def _after_load(s):
        if s.get("status") == "needs_input":
            return "needs_input"
        if s.get("error_code"):
            return "fail"
        return "probe"

    def _after_probe(s):
        if s.get("error_code") and s.get("status") != "needs_input":
            return "fail"
        return "evaluate"

    def _after_evaluate(s):
        if s.get("status") == "needs_input":
            return "needs_input"
        if s.get("error_code"):
            return "fail"
        return "enrich"

    def _after_enrich(s):
        if s.get("status") == "needs_input":
            return "needs_input"
        return "normalize"

    def _after_normalize(s):
        return "fail" if s.get("error_code") else "persist"

    def _after_persist(s):
        return "fail" if s.get("error_code") else "assess"

    def _after_assess(s):
        return "fail" if s.get("error_code") else "ok"

    graph.add_conditional_edges(
        "load",
        _after_load,
        {"needs_input": "needs_input", "fail": "fail", "probe": "probe"},
    )
    graph.add_conditional_edges(
        "probe", _after_probe, {"fail": "fail", "evaluate": "evaluate"}
    )
    graph.add_conditional_edges(
        "evaluate",
        _after_evaluate,
        {"needs_input": "needs_input", "fail": "fail", "enrich": "enrich"},
    )
    graph.add_conditional_edges(
        "enrich",
        _after_enrich,
        {"needs_input": "needs_input", "normalize": "normalize"},
    )
    graph.add_conditional_edges(
        "normalize", _after_normalize, {"fail": "fail", "persist": "persist"}
    )
    graph.add_conditional_edges(
        "persist", _after_persist, {"fail": "fail", "assess": "assess"}
    )
    graph.add_conditional_edges("assess", _after_assess, {"fail": "fail", "ok": "ok"})
    graph.add_edge("ok", END)
    graph.add_edge("needs_input", END)
    graph.add_edge("fail", END)
    return graph.compile()


def initial_state(
    *,
    job_id: str,
    org_id: str,
    targets: List[Any],
    options: Dict[str, Any] = None,
    store=None,
    mongo=None,
    config=None,
    answers: Dict[str, Any] = None,
    llm_settings: Dict[str, Any] = None,
) -> Dict[str, Any]:
    opts = dict(options or {})
    # Real discovery defaults — do not keep demo inventory mixed in
    opts.setdefault("clear_demo_seed", True)
    opts.setdefault("replace_prior_discovered", True)
    opts.setdefault("assess_discovered_only", True)
    return {
        "job_id": job_id,
        "org_id": org_id,
        "raw_targets": targets or [],
        "options": opts,
        "answers": dict(answers or {}),
        "llm_settings": dict(llm_settings or {}),
        "store": store,
        "mongo": mongo,
        "config": config,
        "targets": [],
        "findings": [],
        "assets": [],
        "limitations": [],
        "questions": [],
        "assessment": None,
        "phase": "start",
        "status": None,
        "error_code": None,
        "error_message": None,
        "used_llm": False,
        "result": None,
        "steps": [],
        "cleared_assets": 0,
    }


def _log(state: Dict[str, Any], phase: str, message: str, **extra):
    state["phase"] = phase
    step = {"phase": phase, "message": str(message or "")[:800], "at": int(time.time())}
    step.update({k: v for k, v in extra.items() if v is not None})
    state.setdefault("steps", []).append(step)
    store = state.get("store")
    job_id = state.get("job_id")
    if store and job_id and hasattr(store, "append_step"):
        try:
            store.append_step(job_id, step)
        except Exception:
            LOG.exception("append_step failed")
    if store and job_id and hasattr(store, "update_job"):
        try:
            fields = {"phase": phase}
            if state.get("status"):
                fields["status"] = state["status"]
            store.update_job(job_id, **fields)
        except Exception:
            pass
    LOG.info("pqr job=%s phase=%s %s", job_id, phase, message)


def _add_limitation(state: Dict[str, Any], text: str):
    lims = state.setdefault("limitations", [])
    if text and text not in lims:
        lims.append(text)


def _add_question(state: Dict[str, Any], q: Dict[str, Any]):
    qs = state.setdefault("questions", [])
    qid = q.get("id")
    if qid and any(x.get("id") == qid for x in qs):
        return
    qs.append(q)


def node_load(state: Dict[str, Any]) -> Dict[str, Any]:
    answers = state.get("answers") or {}
    # Allow resume to inject extra targets
    extra = answers.get("additional_targets") or answers.get("targets")
    raw = list(state.get("raw_targets") or [])
    if extra:
        if isinstance(extra, str):
            extra = [
                t.strip() for t in extra.replace(",", "\n").splitlines() if t.strip()
            ]
        raw.extend(extra)

    targets = parse_targets(raw)
    if not targets:
        state["status"] = "needs_input"
        state["error_code"] = "no_targets"
        state["error_message"] = "No valid discovery targets"
        _add_limitation(
            state,
            "Discovery requires reachable hostnames, host:port, or HTTPS URLs. "
            "This agent does not crawl internal networks, cloud accounts, or code repos without targets.",
        )
        _add_question(
            state,
            {
                "id": "targets",
                "prompt": "Enter one or more hosts to scan (example.com, api.example.com:443, https://app.example.com)",
                "required": True,
                "field": "additional_targets",
                "type": "textarea",
            },
        )
        _log(state, "load", "needs targets")
        return state

    max_targets = int((state.get("options") or {}).get("max_targets") or 50)
    if len(targets) > max_targets:
        _add_limitation(
            state,
            f"Only first {max_targets} of {len(targets)} targets will be scanned (max_targets limit).",
        )
    state["targets"] = targets[:max_targets]
    _log(state, "load", f"normalized {len(state['targets'])} live targets")
    return state


def node_probe(state: Dict[str, Any]) -> Dict[str, Any]:
    timeout = float((state.get("options") or {}).get("timeout") or 8)
    findings = []
    for t in state.get("targets") or []:
        _log(state, "probe", f"probing {t.get('host')}:{t.get('port')}")
        try:
            findings.append(probe_target(t, timeout=timeout))
        except Exception as exc:
            findings.append(
                {
                    "target": t,
                    "tls": {"ok": False, "error": str(exc)},
                    "http": {"ok": False, "error": str(exc)},
                    "kel": {"ok": False, "has_kel": False, "kel_status": "none"},
                    "assets": [],
                    "error": str(exc),
                }
            )
    state["findings"] = findings
    asset_n = sum(len(f.get("assets") or []) for f in findings)
    _log(
        state,
        "probe",
        f"completed {len(findings)} probes, {asset_n} rule assets from live data",
    )
    return state


def node_evaluate(state: Dict[str, Any]) -> Dict[str, Any]:
    """Inspect probe results — surface limitations or pause for questions."""
    findings = state.get("findings") or []
    answers = state.get("answers") or {}
    ok_tls = sum(1 for f in findings if (f.get("tls") or {}).get("ok"))
    ok_http = sum(1 for f in findings if (f.get("http") or {}).get("ok"))
    failed = [
        f
        for f in findings
        if not (f.get("tls") or {}).get("ok") and not (f.get("http") or {}).get("ok")
    ]

    _add_limitation(
        state,
        "External network probes only (TLS handshake, HTTP headers, optional DNS CAA, KEL path checks). "
        "No agent installed on hosts; no cloud API inventory; no source-code SBOM; no internal-only services.",
    )
    if not any((f.get("dns") or {}).get("records") for f in findings):
        if any(
            (f.get("dns") or {}).get("error") == "dnspython not installed"
            for f in findings
        ):
            _add_limitation(
                state, "DNS CAA skipped — install dnspython for CAA discovery."
            )

    for f in findings:
        t = f.get("target") or {}
        host = t.get("host")
        tls = f.get("tls") or {}
        if tls.get("ok"):
            _log(
                state,
                "evaluate",
                f"{host}: TLS {tls.get('protocol')} algo={tls.get('algorithm')} cipher={(tls.get('cipher') or {}).get('name')}",
            )
        else:
            err = tls.get("error") or f.get("error") or "unreachable"
            _add_limitation(state, f"{host}: TLS probe failed — {err}")

    if failed and ok_tls == 0 and ok_http == 0:
        state["status"] = "needs_input"
        state["error_code"] = "all_targets_unreachable"
        state["error_message"] = "All targets unreachable from this node"
        _add_question(
            state,
            {
                "id": "targets",
                "prompt": "All targets failed TLS/HTTP. Provide reachable public hosts, or confirm VPN/firewall allows this node outbound 443.",
                "required": True,
                "field": "additional_targets",
                "type": "textarea",
            },
        )
        _add_question(
            state,
            {
                "id": "network_context",
                "prompt": "Are these hosts only reachable on a private network? If yes, run discovery from a node with access or provide a jump-host URL.",
                "required": False,
                "field": "network_context",
                "type": "text",
            },
        )
        _log(state, "evaluate", "all targets unreachable — pausing")
        return state

    # Partial failures — continue but record
    if failed and (ok_tls or ok_http):
        names = ", ".join((f.get("target") or {}).get("host") or "?" for f in failed)
        _add_limitation(state, f"Partial failure — unreachable: {names}")

    # force_llm gate
    llm_settings = state.get("llm_settings") or {}
    require = bool(
        (state.get("options") or {}).get("require_llm")
        or llm_settings.get("require_for_discovery")
    )
    has_key = bool(llm_settings.get("api_key")) or (
        llm_settings.get("provider") == "ollama"
    )
    if require and not has_key and not answers.get("continue_without_llm"):
        state["status"] = "needs_input"
        state["error_code"] = "llm_required"
        state["error_message"] = "LLM API key required before continuing discovery"
        _add_question(
            state,
            {
                "id": "llm_api_key",
                "prompt": "Enter Kilo Code API key (or configure another provider in LLM settings), then resume.",
                "required": True,
                "field": "api_key",
                "type": "password",
            },
        )
        _add_question(
            state,
            {
                "id": "continue_without_llm",
                "prompt": "Or set continue_without_llm=true to proceed with rule-based probes only.",
                "required": False,
                "field": "continue_without_llm",
                "type": "boolean",
            },
        )
        _log(state, "evaluate", "LLM required — pausing")
        return state

    return state


def node_enrich(state: Dict[str, Any]) -> Dict[str, Any]:
    opts = state.get("options") or {}
    answers = state.get("answers") or {}
    if opts.get("skip_llm") or answers.get("continue_without_llm"):
        state["used_llm"] = False
        _add_limitation(
            state,
            "LLM enrichment skipped — using rule-based TLS/HTTP/KEL mapping only.",
        )
        _log(state, "enrich", "LLM skipped")
        return state

    llm_settings = dict(state.get("llm_settings") or {})
    # Resume may inject api_key
    if answers.get("api_key"):
        llm_settings["api_key"] = answers["api_key"]
    if answers.get("provider"):
        llm_settings["provider"] = answers["provider"]
    if answers.get("model"):
        llm_settings["model"] = answers["model"]

    try:
        enriched = enrich_findings(state.get("findings") or [], settings=llm_settings)
        state["used_llm"] = bool(enriched.get("used_llm"))
        state["llm_assets"] = list(enriched.get("assets") or [])
        state["llm_reason"] = enriched.get("reason") or ""
        for lim in enriched.get("limitations") or []:
            _add_limitation(state, lim)
        for q in enriched.get("questions") or []:
            if isinstance(q, dict):
                _add_question(state, q)

        if not enriched.get("used_llm") and llm_settings.get("require_for_discovery"):
            if not answers.get("continue_without_llm"):
                state["status"] = "needs_input"
                state["error_code"] = "llm_unavailable"
                state["error_message"] = enriched.get("reason") or "LLM unavailable"
                _log(state, "enrich", "LLM required but unavailable — pausing")
                return state

        _log(
            state,
            "enrich",
            enriched.get("reason")
            or f"llm={state['used_llm']} assets={len(state.get('llm_assets') or [])}",
            used_llm=state["used_llm"],
            provider=enriched.get("provider"),
        )
    except Exception as exc:
        state["used_llm"] = False
        state["llm_assets"] = []
        state["llm_error"] = str(exc)[:400]
        _add_limitation(state, f"LLM enrichment failed: {exc}")
        if (state.get("llm_settings") or {}).get(
            "require_for_discovery"
        ) and not answers.get("continue_without_llm"):
            state["status"] = "needs_input"
            state["error_code"] = "llm_error"
            state["error_message"] = str(exc)[:400]
            _add_question(
                state,
                {
                    "id": "llm_api_key",
                    "prompt": f"LLM error: {exc}. Update API key/provider or set continue_without_llm=true.",
                    "required": False,
                    "field": "api_key",
                    "type": "password",
                },
            )
            _log(state, "enrich", "LLM error — pausing")
            return state
        _log(state, "enrich", f"LLM failed (continuing with rules): {exc}")
    return state


def node_normalize(state: Dict[str, Any]) -> Dict[str, Any]:
    by_id: Dict[str, Dict[str, Any]] = {}
    job_id = state.get("job_id")
    for f in state.get("findings") or []:
        host = ((f.get("target") or {}).get("host") or "").lower()
        for a in f.get("assets") or []:
            aid = a.get("id") or a.get("name")
            if not aid:
                continue
            row = dict(a)
            row.setdefault("tags", [])
            tags = [t for t in row["tags"] if t != "demo_seed"]
            for t in ("discovered", "agent", "live_scan"):
                if t not in tags:
                    tags.append(t)
            row["tags"] = tags
            row.setdefault("metadata", {})
            row["metadata"]["source"] = "pqr_discovery_agent"
            row["metadata"]["discovery_job_id"] = job_id
            row["metadata"]["host"] = host or row["metadata"].get("host")
            row["data_classification"] = row.get("data_classification") or "discovered"
            by_id[aid] = row

    for a in state.get("llm_assets") or []:
        name = (a.get("name") or "").strip()
        if not name:
            continue
        host = ""
        for f in state.get("findings") or []:
            h = (f.get("target") or {}).get("host") or ""
            if h and h in name.lower():
                host = h
                break
        if not host and state.get("findings"):
            host = (state["findings"][0].get("target") or {}).get("host") or "target"
        slug = name.lower().replace(" ", "-")[:40]
        aid = a.get("id") or f"disc-{host}-{slug}"
        base = by_id.get(aid) or {}
        merged = dict(base)
        merged.update({k: v for k, v in a.items() if v is not None and v != ""})
        merged["id"] = aid
        tags = list(merged.get("tags") or [])
        for t in ("discovered", "agent", "live_scan", "llm"):
            if t not in tags:
                tags.append(t)
        tags = [t for t in tags if t != "demo_seed"]
        merged["tags"] = tags
        merged.setdefault("metadata", {})
        merged["metadata"]["llm_enriched"] = True
        merged["metadata"]["source"] = "pqr_discovery_agent"
        merged["metadata"]["discovery_job_id"] = job_id
        merged["metadata"]["host"] = host
        by_id[aid] = merged

    assets = list(by_id.values())
    state["assets"] = assets
    if not assets:
        _add_limitation(
            state,
            "No crypto assets could be derived from successful probes. "
            "TLS may have failed or returned incomplete cert data.",
        )
        _log(state, "normalize", "no live assets")
    else:
        _log(state, "normalize", f"normalized {len(assets)} live discovered assets")
    return state


def node_persist(state: Dict[str, Any]) -> Dict[str, Any]:
    store = state.get("store")
    org_id = state.get("org_id")
    state.get("mongo")
    assets = state.get("assets") or []
    opts = state.get("options") or {}
    if not store or not org_id:
        state["error_code"] = "persist_config"
        state["error_message"] = "store/org_id missing"
        return state

    try:
        cleared = 0
        if opts.get("clear_demo_seed") and hasattr(store, "delete_assets"):
            cleared += int(store.delete_assets(org_id, demo_seed=True) or 0)
        hosts = list(
            {
                ((f.get("target") or {}).get("host") or "").lower()
                for f in (state.get("findings") or [])
                if (f.get("target") or {}).get("host")
            }
        )
        if opts.get("replace_prior_discovered") and hasattr(store, "delete_assets"):
            cleared += int(
                store.delete_assets(
                    org_id,
                    tags=["discovered", "live_scan", "agent"],
                    hosts=hosts or None,
                )
                or 0
            )
        state["cleared_assets"] = cleared
        if cleared:
            _log(state, "persist", f"cleared {cleared} prior demo/discovered assets")

        saved = []
        for a in assets:
            row = store.upsert_asset_sync(org_id, a)
            saved.append(row.get("id") if isinstance(row, dict) else a.get("id"))
        state["saved_asset_ids"] = saved
        _log(state, "persist", f"upserted {len(saved)} live assets")
    except Exception as exc:
        state["error_code"] = "persist_failed"
        state["error_message"] = str(exc)[:400]
        _log(state, "persist", state["error_message"])
    return state


def node_assess(state: Dict[str, Any]) -> Dict[str, Any]:
    store = state.get("store")
    org_id = state.get("org_id")
    opts = state.get("options") or {}
    assets = state.get("assets") or []
    if not store or not org_id:
        return state
    try:
        if opts.get("skip_assess"):
            _log(state, "assess", "assessment skipped")
            return state

        if opts.get("assess_discovered_only") and assets:
            org = {}
            if hasattr(store, "get_org_sync"):
                org = store.get_org_sync(org_id) or {}
            summary = score_organization(org, assets)
            state["assessment"] = {
                "id": None,
                "scope": "discovered_only",
                "overall": summary.get("overall"),
                "status_band": summary.get("status_band"),
                "kel_migration": summary.get("kel_migration"),
                "asset_count": summary.get("asset_count"),
                "scored_assets": summary.get("scored_assets"),
                "priority_findings": summary.get("priority_findings"),
            }
            # Still write full org assessment after inventory update
            if hasattr(store, "run_assessment_sync"):
                full = store.run_assessment_sync(org_id, trigger="discovery_agent")
                state["assessment"]["org_assessment_id"] = full.get("id")
                state["assessment"]["org_overall"] = (full.get("summary") or {}).get(
                    "overall"
                )
            _log(
                state,
                "assess",
                f"discovered-only overall={state['assessment'].get('overall')}",
            )
        elif hasattr(store, "run_assessment_sync"):
            assessment = store.run_assessment_sync(org_id, trigger="discovery_agent")
            state["assessment"] = {
                "id": assessment.get("id"),
                "scope": "organization",
                "overall": (assessment.get("summary") or {}).get("overall"),
                "status_band": (assessment.get("summary") or {}).get("status_band"),
                "kel_migration": (assessment.get("summary") or {}).get("kel_migration"),
            }
            _log(state, "assess", f"org overall={state['assessment'].get('overall')}")
    except Exception as exc:
        state["assess_error"] = str(exc)[:400]
        _add_limitation(state, f"Assessment error: {exc}")
        _log(state, "assess", f"assessment error (non-fatal): {exc}")
    return state


def _findings_public(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for f in findings or []:
        tls = f.get("tls") or {}
        http = f.get("http") or {}
        kel = f.get("kel") or {}
        out.append(
            {
                "host": (f.get("target") or {}).get("host"),
                "port": (f.get("target") or {}).get("port"),
                "url": (f.get("target") or {}).get("url"),
                "tls": {
                    "ok": tls.get("ok"),
                    "algorithm": tls.get("algorithm"),
                    "protocol": tls.get("protocol"),
                    "cipher": tls.get("cipher"),
                    "subject": tls.get("subject"),
                    "issuer": tls.get("issuer"),
                    "expired": tls.get("expired"),
                    "expiring_soon": tls.get("expiring_soon"),
                    "error": tls.get("error"),
                },
                "http": {
                    "ok": http.get("ok"),
                    "status": http.get("status"),
                    "hsts": http.get("hsts"),
                    "server": http.get("server"),
                    "title": http.get("title"),
                    "error": http.get("error"),
                },
                "kel": {
                    "has_kel": kel.get("has_kel"),
                    "kel_status": kel.get("kel_status"),
                    "signals": kel.get("signals"),
                },
                "rule_asset_count": len(f.get("assets") or []),
            }
        )
    return out


def node_ok(state: Dict[str, Any]) -> Dict[str, Any]:
    assets = state.get("assets") or []
    state["result"] = {
        "status": "succeeded",
        "org_id": state.get("org_id"),
        "targets": len(state.get("targets") or []),
        "findings": _findings_public(state.get("findings") or []),
        "findings_count": len(state.get("findings") or []),
        "assets_discovered": len(assets),
        "discovered_assets": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "algorithm": a.get("algorithm"),
                "protocol": a.get("protocol"),
                "kel_status": a.get("kel_status"),
                "has_kel": a.get("has_kel"),
                "host": (a.get("metadata") or {}).get("host"),
                "tags": a.get("tags"),
            }
            for a in assets
        ],
        "saved_asset_ids": state.get("saved_asset_ids") or [],
        "cleared_assets": state.get("cleared_assets") or 0,
        "used_llm": bool(state.get("used_llm")),
        "assessment": state.get("assessment"),
        "limitations": state.get("limitations") or [],
        "questions": state.get("questions") or [],
        "kel_hits": [
            {
                "host": (f.get("target") or {}).get("host"),
                "has_kel": (f.get("kel") or {}).get("has_kel"),
                "signals": (f.get("kel") or {}).get("signals"),
            }
            for f in (state.get("findings") or [])
            if (f.get("kel") or {}).get("has_kel")
        ],
        "source": "live_network_discovery",
    }
    _log(state, "succeeded", f"live-discovered {len(assets)} assets")
    return state


def node_needs_input(state: Dict[str, Any]) -> Dict[str, Any]:
    state["status"] = "needs_input"
    state["result"] = {
        "status": "needs_input",
        "org_id": state.get("org_id"),
        "error_code": state.get("error_code"),
        "error_message": state.get("error_message"),
        "limitations": state.get("limitations") or [],
        "questions": state.get("questions") or [],
        "findings": _findings_public(state.get("findings") or []),
        "findings_count": len(state.get("findings") or []),
        "assets_discovered": len(state.get("assets") or []),
        "discovered_assets": state.get("assets") or [],
        "used_llm": bool(state.get("used_llm")),
        "source": "live_network_discovery",
        "resume_hint": (
            f"POST /post-quantum-readiness/api/v1/orgs/{state.get('org_id')}/discover/"
            f"{state.get('job_id')}/resume with {{\"answers\": {{...}}}}"
        ),
    }
    _log(state, "needs_input", state.get("error_message") or "waiting for user input")
    return state


def node_fail(state: Dict[str, Any]) -> Dict[str, Any]:
    state["result"] = {
        "status": "failed",
        "error_code": state.get("error_code") or "unknown",
        "error_message": state.get("error_message") or "discovery failed",
        "org_id": state.get("org_id"),
        "limitations": state.get("limitations") or [],
        "questions": state.get("questions") or [],
        "findings": _findings_public(state.get("findings") or []),
        "assets_discovered": len(state.get("assets") or []),
        "source": "live_network_discovery",
    }
    _log(state, "failed", state["result"]["error_message"])
    return state
