"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

Crypto readiness + KEL migration scoring.

Differentiator vs inventory-only platforms: KEL abstraction earns crypto-agility
credit even when algorithms remain classical (ECC/RSA). Apps talk to the KEL
layer; algorithms can rotate later without rewriting callers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .taxonomy import (
    compute_category_progress,
    empty_progress,
    infer_category,
    taxonomy_tree,
)

# Classical / transitional / post-quantum algorithm classes
ALG_CLASSICAL = frozenset(
    {
        "rsa",
        "rsa-1024",
        "rsa-2048",
        "rsa-3072",
        "rsa-4096",
        "ecdsa",
        "ecc",
        "secp256k1",
        "secp256r1",
        "p-256",
        "p-384",
        "p-521",
        "ed25519",
        "x25519",
        "dh",
        "dsa",
    }
)
ALG_TRANSITIONAL = frozenset(
    {
        "hybrid-mlkem-x25519",
        "hybrid-mldsa-ed25519",
        "hybrid",
        "tls-hybrid",
    }
)
ALG_PQC = frozenset(
    {
        "ml-kem",
        "ml-kem-512",
        "ml-kem-768",
        "ml-kem-1024",
        "kyber",
        "ml-dsa",
        "ml-dsa-44",
        "ml-dsa-65",
        "ml-dsa-87",
        "dilithium",
        "slh-dsa",
        "sphincs+",
        "falcon",
        "bike",
        "hqc",
    }
)

# Weak / broken — always high risk
ALG_WEAK = frozenset(
    {
        "md5",
        "sha1",
        "des",
        "3des",
        "rc4",
        "rsa-1024",
        "export",
        "null",
        "aead-none",
    }
)

# Protocol maturity
PROTO_STRONG = frozenset({"tls1.3", "tls-1.3", "https", "ssh-2", "noise", "quic"})
PROTO_OK = frozenset({"tls1.2", "tls-1.2", "ipsec"})
PROTO_WEAK = frozenset({"tls1.0", "tls1.1", "ssl3", "ssl2", "http", "ftp", "telnet"})

KEL_STATUS_NONE = "none"
KEL_STATUS_ABSTRACTED = "kel_abstracted"  # KEL layer; may still be ECC/RSA
KEL_STATUS_HYBRID = "kel_hybrid"  # KEL + dual classical/PQC path
KEL_STATUS_QUANTUM_SAFE = "kel_quantum_safe"  # KEL + PQC algorithms

KEL_STATUS_LABELS = {
    KEL_STATUS_NONE: "No KEL layer",
    KEL_STATUS_ABSTRACTED: "KEL abstracted (crypto-agile)",
    KEL_STATUS_HYBRID: "KEL hybrid classical/PQC",
    KEL_STATUS_QUANTUM_SAFE: "KEL + quantum-safe algorithms",
}

# Weights for org-level readiness (sum = 100)
WEIGHTS = {
    "discovery": 10,
    "algorithm": 25,
    "protocol": 15,
    "lifecycle": 15,
    "governance": 10,
    "kel_agility": 25,  # primary differentiator
}


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower().replace("_", "-").replace(" ", "-")


def classify_algorithm(name: str) -> str:
    n = _norm(name)
    if not n:
        return "unknown"
    if n in ALG_WEAK or any(n.startswith(w) for w in ("md5", "sha1", "des", "rc4")):
        return "weak"
    if n in ALG_PQC or any(
        x in n for x in ("ml-kem", "ml-dsa", "kyber", "dilithium", "sphincs", "falcon")
    ):
        return "pqc"
    if n in ALG_TRANSITIONAL or "hybrid" in n:
        return "transitional"
    if n in ALG_CLASSICAL or any(
        x in n
        for x in ("rsa", "ecdsa", "ecc", "ed255", "x255", "secp", "p-256", "p-384")
    ):
        return "classical"
    return "unknown"


def classify_protocol(name: str) -> str:
    n = _norm(name)
    if n in PROTO_STRONG or n.startswith("tls1.3") or n.startswith("tls-1.3"):
        return "strong"
    if n in PROTO_OK or n.startswith("tls1.2") or n.startswith("tls-1.2"):
        return "ok"
    if n in PROTO_WEAK or n.startswith("ssl") or n in ("http", "ftp"):
        return "weak"
    return "unknown"


def normalize_kel_status(raw: Optional[str], has_kel: Optional[bool] = None) -> str:
    """
    Map free-form / boolean input to canonical KEL migration status.

    has_kel=True with classical algos → kel_abstracted (enhanced agility).
    """
    s = _norm(raw)
    aliases = {
        "": KEL_STATUS_NONE,
        "none": KEL_STATUS_NONE,
        "no": KEL_STATUS_NONE,
        "false": KEL_STATUS_NONE,
        "absent": KEL_STATUS_NONE,
        "kel": KEL_STATUS_ABSTRACTED,
        "abstracted": KEL_STATUS_ABSTRACTED,
        "kel-abstracted": KEL_STATUS_ABSTRACTED,
        "kel_abstracted": KEL_STATUS_ABSTRACTED,
        "agile": KEL_STATUS_ABSTRACTED,
        "crypto-agile": KEL_STATUS_ABSTRACTED,
        "hybrid": KEL_STATUS_HYBRID,
        "kel-hybrid": KEL_STATUS_HYBRID,
        "kel_hybrid": KEL_STATUS_HYBRID,
        "pqc": KEL_STATUS_QUANTUM_SAFE,
        "quantum": KEL_STATUS_QUANTUM_SAFE,
        "quantum-safe": KEL_STATUS_QUANTUM_SAFE,
        "kel-quantum-safe": KEL_STATUS_QUANTUM_SAFE,
        "kel_quantum_safe": KEL_STATUS_QUANTUM_SAFE,
        "full": KEL_STATUS_QUANTUM_SAFE,
    }
    if s in aliases:
        status = aliases[s]
    elif "quantum" in s or "pqc" in s:
        status = KEL_STATUS_QUANTUM_SAFE
    elif "hybrid" in s:
        status = KEL_STATUS_HYBRID
    elif "kel" in s or "agil" in s:
        status = KEL_STATUS_ABSTRACTED
    else:
        status = KEL_STATUS_NONE

    if has_kel is True and status == KEL_STATUS_NONE:
        status = KEL_STATUS_ABSTRACTED
    if has_kel is False:
        status = KEL_STATUS_NONE
    return status


def score_algorithm(alg_class: str) -> Tuple[float, List[str]]:
    notes: List[str] = []
    if alg_class == "pqc":
        return 100.0, notes
    if alg_class == "transitional":
        notes.append("Hybrid classical/PQC — good bridge posture")
        return 75.0, notes
    if alg_class == "classical":
        notes.append("Classical public-key crypto is quantum-vulnerable long-term")
        return 35.0, notes
    if alg_class == "weak":
        notes.append("Weak or broken algorithm — remediate immediately")
        return 5.0, notes
    notes.append("Unknown algorithm class — inventory incomplete")
    return 20.0, notes


def score_protocol(proto_class: str) -> Tuple[float, List[str]]:
    notes: List[str] = []
    if proto_class == "strong":
        return 100.0, notes
    if proto_class == "ok":
        notes.append("Prefer TLS 1.3+ where possible")
        return 70.0, notes
    if proto_class == "weak":
        notes.append("Deprecated or cleartext protocol")
        return 15.0, notes
    return 40.0, ["Protocol not classified"]


def score_kel_agility(
    kel_status: str, alg_class: str
) -> Tuple[float, List[str], Dict[str, Any]]:
    """
    Crypto-agility score from KEL adoption.

    Even ECC/RSA assets score well here if KEL abstraction is present — the
    organization can rotate algorithms without rewriting application code.
    """
    notes: List[str] = []
    detail: Dict[str, Any] = {
        "kel_status": kel_status,
        "kel_label": KEL_STATUS_LABELS.get(kel_status, kel_status),
        "algorithm_class": alg_class,
        "agility_enhanced": False,
    }

    if kel_status == KEL_STATUS_QUANTUM_SAFE:
        notes.append("KEL + quantum-safe algorithms — full crypto agility path")
        detail["agility_enhanced"] = True
        return 100.0, notes, detail

    if kel_status == KEL_STATUS_HYBRID:
        notes.append("KEL hybrid path enables controlled PQC migration")
        detail["agility_enhanced"] = True
        return 88.0, notes, detail

    if kel_status == KEL_STATUS_ABSTRACTED:
        detail["agility_enhanced"] = True
        if alg_class in ("classical", "unknown", "weak"):
            notes.append(
                "KEL abstraction layer present — crypto-agile despite classical "
                "(ECC/RSA) algorithms; algorithm swap does not require app rewrites"
            )
            # Enhanced status: classical crypto but KEL-ready
            return 72.0, notes, detail
        if alg_class == "transitional":
            notes.append("KEL + hybrid algorithms — strong migration posture")
            return 90.0, notes, detail
        notes.append("KEL abstraction with modern algorithms")
        return 85.0, notes, detail

    # No KEL
    if alg_class == "pqc":
        notes.append(
            "PQC without KEL — algorithm fixed in app code; limited future agility"
        )
        return 45.0, notes, detail
    if alg_class == "transitional":
        notes.append("Hybrid crypto without KEL — still tightly coupled to app code")
        return 35.0, notes, detail
    if alg_class == "classical":
        notes.append(
            "Classical ECC/RSA bound directly in applications — no crypto-agility layer"
        )
        return 15.0, notes, detail
    if alg_class == "weak":
        return 5.0, notes, detail
    notes.append("No KEL layer detected")
    return 10.0, notes, detail


def score_lifecycle(asset: Dict[str, Any]) -> Tuple[float, List[str]]:
    notes: List[str] = []
    score = 50.0
    rotation_days = asset.get("key_rotation_days")
    if rotation_days is None:
        notes.append("Key rotation interval not reported")
        score -= 15
    else:
        try:
            days = int(rotation_days)
            if days <= 90:
                score += 35
            elif days <= 180:
                score += 20
            elif days <= 365:
                score += 5
            else:
                score -= 20
                notes.append("Key rotation interval exceeds 1 year")
        except (TypeError, ValueError):
            score -= 10

    if asset.get("hsm_backed"):
        score += 15
    if asset.get("certificate_auto_renew"):
        score += 10
    if asset.get("expired") or asset.get("expiring_soon"):
        score -= 30
        notes.append("Certificate expired or expiring soon")

    return max(0.0, min(100.0, score)), notes


def score_governance(
    asset: Dict[str, Any], org: Optional[Dict[str, Any]] = None
) -> Tuple[float, List[str]]:
    notes: List[str] = []
    score = 40.0
    org = org or {}
    if asset.get("owner") or asset.get("owner_email"):
        score += 15
    else:
        notes.append("No asset owner assigned")
    if asset.get("data_classification"):
        score += 10
    if asset.get("in_policy") is True:
        score += 15
    elif asset.get("in_policy") is False:
        score -= 20
        notes.append("Asset violates crypto policy")
    if org.get("has_crypto_policy"):
        score += 10
    if org.get("has_quantum_roadmap"):
        score += 10
    return max(0.0, min(100.0, score)), notes


def prioritize_finding(
    asset: Dict[str, Any], dimension_scores: Dict[str, float]
) -> Dict[str, Any]:
    """Rank remediation priority from impact + effort heuristics."""
    exposure = _norm(
        asset.get("exposure") or asset.get("network_exposure") or "internal"
    )
    exposure_w = {
        "internet": 1.0,
        "public": 1.0,
        "partner": 0.75,
        "internal": 0.45,
        "airgapped": 0.2,
    }.get(exposure, 0.5)
    business = _norm(asset.get("business_criticality") or "medium")
    business_w = {"critical": 1.0, "high": 0.85, "medium": 0.55, "low": 0.3}.get(
        business, 0.55
    )

    weakest = min(dimension_scores.values()) if dimension_scores else 50.0
    risk = (100.0 - weakest) * (0.5 + 0.5 * exposure_w) * (0.4 + 0.6 * business_w)
    risk = max(0.0, min(100.0, risk))

    kel = normalize_kel_status(asset.get("kel_status"), asset.get("has_kel"))
    effort = "medium"
    if (
        kel == KEL_STATUS_NONE
        and classify_algorithm(asset.get("algorithm") or "") == "classical"
    ):
        effort = "medium"  # add KEL layer first
    if classify_algorithm(asset.get("algorithm") or "") == "weak":
        effort = "high"
    if kel in (KEL_STATUS_ABSTRACTED, KEL_STATUS_HYBRID) and classify_algorithm(
        asset.get("algorithm") or ""
    ) in ("classical", "transitional"):
        effort = "low"  # algorithm swap behind KEL is cheap

    if risk >= 75:
        severity = "critical"
    elif risk >= 55:
        severity = "high"
    elif risk >= 35:
        severity = "medium"
    else:
        severity = "low"

    return {
        "risk_score": round(risk, 1),
        "severity": severity,
        "remediation_effort": effort,
        "exposure": exposure,
        "business_criticality": business,
    }


def remediation_plan(
    asset: Dict[str, Any], scores: Dict[str, Any]
) -> List[Dict[str, str]]:
    steps: List[Dict[str, str]] = []
    kel = scores.get("kel_detail", {}).get("kel_status") or normalize_kel_status(
        asset.get("kel_status"), asset.get("has_kel")
    )
    alg_class = scores.get("algorithm_class") or classify_algorithm(
        asset.get("algorithm") or ""
    )

    if alg_class == "weak":
        steps.append(
            {
                "priority": "P0",
                "action": "Replace weak algorithm immediately",
                "detail": f"Retire {asset.get('algorithm') or 'weak crypto'} on {asset.get('name') or asset.get('id')}",
            }
        )

    if kel == KEL_STATUS_NONE:
        steps.append(
            {
                "priority": "P1",
                "action": "Introduce KEL abstraction layer",
                "detail": (
                    "Wrap signing/encryption behind the KEL-based crypto-agility layer. "
                    "Applications keep working on ECC/RSA today while gaining the ability "
                    "to rotate algorithms without code changes."
                ),
            }
        )
    elif kel == KEL_STATUS_ABSTRACTED and alg_class == "classical":
        steps.append(
            {
                "priority": "P2",
                "action": "Plan PQC algorithm cutover behind KEL",
                "detail": (
                    "KEL layer already provides enhanced crypto agility. Schedule hybrid "
                    "then pure-PQC algorithm rotation; no application rewrite required."
                ),
            }
        )
    elif kel == KEL_STATUS_HYBRID:
        steps.append(
            {
                "priority": "P2",
                "action": "Complete migration to quantum-safe algorithms",
                "detail": "Retire classical half of hybrid suite once PQC interoperability is validated.",
            }
        )

    proto = classify_protocol(asset.get("protocol") or "")
    if proto == "weak":
        steps.append(
            {
                "priority": "P0",
                "action": "Upgrade or disable weak protocol",
                "detail": f"Replace {asset.get('protocol')} with TLS 1.3+ or equivalent.",
            }
        )
    elif proto == "ok":
        steps.append(
            {
                "priority": "P3",
                "action": "Prefer TLS 1.3",
                "detail": "Raise minimum protocol version where clients allow.",
            }
        )

    if not asset.get("owner"):
        steps.append(
            {
                "priority": "P2",
                "action": "Assign crypto asset owner",
                "detail": "Governance requires a named owner for policy and rotation SLAs.",
            }
        )

    rot = asset.get("key_rotation_days")
    if rot is None or (isinstance(rot, (int, float)) and int(rot) > 365):
        steps.append(
            {
                "priority": "P2",
                "action": "Enforce key rotation policy",
                "detail": "Target ≤90 days for high-value keys; KEL makes rotation operationally cheap.",
            }
        )

    if not steps:
        steps.append(
            {
                "priority": "P3",
                "action": "Maintain continuous monitoring",
                "detail": "Re-scan inventory and KEL migration metrics on a fixed cadence.",
            }
        )
    return steps


def score_asset(
    asset: Dict[str, Any], org: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    alg = asset.get("algorithm") or asset.get("public_key_algorithm") or ""
    proto = asset.get("protocol") or asset.get("transport") or ""
    alg_class = classify_algorithm(alg)
    proto_class = classify_protocol(proto)
    kel_status = normalize_kel_status(asset.get("kel_status"), asset.get("has_kel"))

    # If algorithm is already PQC and KEL present but status still abstracted, promote
    if kel_status == KEL_STATUS_ABSTRACTED and alg_class == "pqc":
        kel_status = KEL_STATUS_QUANTUM_SAFE
    if kel_status == KEL_STATUS_ABSTRACTED and alg_class == "transitional":
        kel_status = KEL_STATUS_HYBRID

    alg_score, alg_notes = score_algorithm(alg_class)
    proto_score, proto_notes = score_protocol(proto_class)
    kel_score, kel_notes, kel_detail = score_kel_agility(kel_status, alg_class)
    life_score, life_notes = score_lifecycle(asset)
    gov_score, gov_notes = score_governance(asset, org)

    # Discovery completeness for this asset record
    required_fields = ("name", "algorithm", "protocol", "environment", "owner")
    present = sum(1 for f in required_fields if asset.get(f))
    discovery_score = round(100.0 * present / len(required_fields), 1)

    dimensions = {
        "discovery": discovery_score,
        "algorithm": alg_score,
        "protocol": proto_score,
        "lifecycle": life_score,
        "governance": gov_score,
        "kel_agility": kel_score,
    }

    overall = 0.0
    for key, weight in WEIGHTS.items():
        overall += dimensions[key] * (weight / 100.0)
    overall = round(overall, 1)

    priority = prioritize_finding(asset, dimensions)
    cat_id, sub_id, cat_source = infer_category(asset)
    # Ensure asset dict carries classification for org rollups
    asset.setdefault("category", cat_id)
    asset.setdefault("subcategory", sub_id)

    payload = {
        "overall": overall,
        "dimensions": {k: round(v, 1) for k, v in dimensions.items()},
        "weights": WEIGHTS,
        "algorithm_class": alg_class,
        "protocol_class": proto_class,
        "category": cat_id,
        "subcategory": sub_id,
        "category_source": cat_source,
        "kel_status": kel_status,
        "kel_label": KEL_STATUS_LABELS.get(kel_status, kel_status),
        "kel_detail": kel_detail,
        "agility_enhanced": bool(kel_detail.get("agility_enhanced")),
        "notes": alg_notes + proto_notes + kel_notes + life_notes + gov_notes,
        "priority": priority,
        "remediation": remediation_plan(
            asset,
            {
                "kel_detail": kel_detail,
                "algorithm_class": alg_class,
            },
        ),
        "status_band": _band(overall),
    }
    return payload


def _band(score: float) -> str:
    if score >= 85:
        return "ready"
    if score >= 70:
        return "enhanced"  # typically KEL-abstracted classical
    if score >= 50:
        return "transitioning"
    if score >= 30:
        return "at_risk"
    return "critical"


def score_organization(
    org: Dict[str, Any], assets: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Aggregate asset scores + org policy into org readiness + KEL migration metrics."""
    if not assets:
        return {
            "overall": 0.0,
            "status_band": "critical",
            "asset_count": 0,
            "dimensions": {k: 0.0 for k in WEIGHTS},
            "kel_migration": _empty_kel_migration(),
            "category_progress": empty_progress(),
            "taxonomy": taxonomy_tree(),
            "priority_findings": [],
            "notes": ["No crypto assets inventoried — discovery incomplete"],
        }

    scored: List[Dict[str, Any]] = []
    for a in assets:
        cat_id, sub_id, cat_source = infer_category(a)
        a = dict(a)
        a["category"] = a.get("category") or cat_id
        a["subcategory"] = a.get("subcategory") or sub_id
        a["category_source"] = cat_source
        s = score_asset(a, org)
        scored.append({"asset": a, "score": s})

    # Weighted average by business criticality
    crit_w = {"critical": 1.5, "high": 1.2, "medium": 1.0, "low": 0.7}
    total_w = 0.0
    acc = 0.0
    dim_acc = {k: 0.0 for k in WEIGHTS}
    for item in scored:
        a = item["asset"]
        s = item["score"]
        w = crit_w.get(_norm(a.get("business_criticality") or "medium"), 1.0)
        total_w += w
        acc += s["overall"] * w
        for k, v in s["dimensions"].items():
            dim_acc[k] += v * w

    overall = round(acc / total_w, 1) if total_w else 0.0
    dimensions = (
        {k: round(v / total_w, 1) for k, v in dim_acc.items()} if total_w else dim_acc
    )

    # Org-level discovery bonus/penalty
    if org.get("has_crypto_policy"):
        dimensions["governance"] = min(100.0, dimensions["governance"] + 5)
    if org.get("has_quantum_roadmap"):
        dimensions["governance"] = min(100.0, dimensions["governance"] + 5)

    # Coverage of taxonomy slots influences discovery dimension slightly
    category_progress = compute_category_progress(scored)
    cov = (category_progress.get("totals") or {}).get("coverage_percent") or 0.0
    dimensions["discovery"] = round(
        min(100.0, dimensions.get("discovery", 0) * 0.7 + cov * 0.3), 1
    )
    # Recompute overall with adjusted discovery
    overall = 0.0
    for key, weight in WEIGHTS.items():
        overall += dimensions[key] * (weight / 100.0)
    overall = round(overall, 1)

    kel_migration = compute_kel_migration(scored)
    findings = sorted(
        (
            {
                "asset_id": (i["asset"].get("id") or i["asset"].get("name")),
                "name": i["asset"].get("name"),
                "category": i["asset"].get("category"),
                "subcategory": i["asset"].get("subcategory"),
                "overall": i["score"]["overall"],
                "kel_status": i["score"]["kel_status"],
                "agility_enhanced": i["score"]["agility_enhanced"],
                "priority": i["score"]["priority"],
                "top_action": (i["score"]["remediation"] or [{}])[0],
            }
            for i in scored
        ),
        key=lambda x: -x["priority"]["risk_score"],
    )

    return {
        "overall": overall,
        "status_band": _band(overall),
        "asset_count": len(assets),
        "dimensions": dimensions,
        "weights": WEIGHTS,
        "kel_migration": kel_migration,
        "category_progress": category_progress,
        "taxonomy": taxonomy_tree(),
        "priority_findings": findings[:25],
        "scored_assets": [
            {
                "id": i["asset"].get("id"),
                "name": i["asset"].get("name"),
                "category": i["asset"].get("category"),
                "subcategory": i["asset"].get("subcategory"),
                "overall": i["score"]["overall"],
                "status_band": i["score"]["status_band"],
                "kel_status": i["score"]["kel_status"],
                "kel_label": i["score"]["kel_label"],
                "agility_enhanced": i["score"]["agility_enhanced"],
                "algorithm_class": i["score"]["algorithm_class"],
                "dimensions": i["score"]["dimensions"],
            }
            for i in scored
        ],
    }


def _empty_kel_migration() -> Dict[str, Any]:
    return {
        "percent_with_kel": 0.0,
        "percent_agility_enhanced": 0.0,
        "percent_quantum_safe": 0.0,
        "counts": {
            KEL_STATUS_NONE: 0,
            KEL_STATUS_ABSTRACTED: 0,
            KEL_STATUS_HYBRID: 0,
            KEL_STATUS_QUANTUM_SAFE: 0,
        },
        "classical_with_kel": 0,
        "classical_without_kel": 0,
        "migration_stage": "not_started",
        "narrative": "No assets to evaluate.",
    }


def compute_kel_migration(scored: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {
        KEL_STATUS_NONE: 0,
        KEL_STATUS_ABSTRACTED: 0,
        KEL_STATUS_HYBRID: 0,
        KEL_STATUS_QUANTUM_SAFE: 0,
    }
    classical_with = 0
    classical_without = 0
    enhanced = 0
    n = len(scored) or 1

    for item in scored:
        s = item["score"]
        st = s["kel_status"]
        counts[st] = counts.get(st, 0) + 1
        if s.get("agility_enhanced"):
            enhanced += 1
        if s.get("algorithm_class") == "classical":
            if st == KEL_STATUS_NONE:
                classical_without += 1
            else:
                classical_with += 1

    with_kel = n - counts[KEL_STATUS_NONE]
    pct_kel = round(100.0 * with_kel / n, 1)
    pct_enh = round(100.0 * enhanced / n, 1)
    pct_qs = round(100.0 * counts[KEL_STATUS_QUANTUM_SAFE] / n, 1)

    if pct_qs >= 80:
        stage = "quantum_safe"
    elif (
        pct_kel >= 70
        and (counts[KEL_STATUS_HYBRID] + counts[KEL_STATUS_QUANTUM_SAFE]) > 0
    ):
        stage = "hybrid_rollout"
    elif pct_kel >= 40:
        stage = "kel_abstraction"
    elif pct_kel > 0:
        stage = "pilot"
    else:
        stage = "not_started"

    narrative = (
        f"{pct_kel}% of assets use the KEL abstraction layer. "
        f"{classical_with} classical (ECC/RSA) assets already show enhanced "
        f"crypto-agility status via KEL; {classical_without} remain tightly coupled. "
        f"{pct_qs}% run quantum-safe algorithms on KEL."
    )

    return {
        "percent_with_kel": pct_kel,
        "percent_agility_enhanced": pct_enh,
        "percent_quantum_safe": pct_qs,
        "counts": counts,
        "classical_with_kel": classical_with,
        "classical_without_kel": classical_without,
        "migration_stage": stage,
        "narrative": narrative,
    }


def demo_seed_assets(org_id: str) -> List[Dict[str, Any]]:
    """Sample inventory illustrating KEL-enhanced classical vs bare classical."""
    base = [
        {
            "name": "Customer TLS edge",
            "algorithm": "ECDSA",
            "protocol": "TLS1.3",
            "environment": "production",
            "exposure": "internet",
            "business_criticality": "critical",
            "kel_status": "none",
            "has_kel": False,
            "owner": "platform-sre",
            "key_rotation_days": 365,
            "hsm_backed": True,
            "in_policy": True,
            "data_classification": "pii",
        },
        {
            "name": "Payment signing service",
            "algorithm": "RSA-2048",
            "protocol": "TLS1.2",
            "environment": "production",
            "exposure": "partner",
            "business_criticality": "critical",
            "kel_status": "kel_abstracted",
            "has_kel": True,
            "owner": "payments",
            "key_rotation_days": 90,
            "hsm_backed": True,
            "in_policy": True,
            "data_classification": "pci",
        },
        {
            "name": "Internal service mesh mTLS",
            "algorithm": "Ed25519",
            "protocol": "TLS1.3",
            "environment": "production",
            "exposure": "internal",
            "business_criticality": "high",
            "kel_status": "kel_abstracted",
            "has_kel": True,
            "owner": "mesh-team",
            "key_rotation_days": 30,
            "certificate_auto_renew": True,
            "in_policy": True,
        },
        {
            "name": "Legacy VPN concentrator",
            "algorithm": "RSA-1024",
            "protocol": "TLS1.0",
            "environment": "production",
            "exposure": "partner",
            "business_criticality": "medium",
            "kel_status": "none",
            "has_kel": False,
            "owner": "",
            "key_rotation_days": 730,
            "in_policy": False,
        },
        {
            "name": "Document archive at-rest",
            "algorithm": "AES-256-GCM",
            "protocol": "https",
            "environment": "production",
            "exposure": "internal",
            "business_criticality": "high",
            "kel_status": "none",
            "has_kel": False,
            "owner": "data-platform",
            "key_rotation_days": 180,
            # symmetric alone — still score via lifecycle; mark algorithm classical path N/A
            "public_key_algorithm": "RSA-2048",
            "algorithm": "RSA-2048",
        },
        {
            "name": "Identity KEL root",
            "algorithm": "secp256k1",
            "protocol": "https",
            "environment": "production",
            "exposure": "internet",
            "business_criticality": "critical",
            "kel_status": "kel_abstracted",
            "has_kel": True,
            "owner": "identity",
            "key_rotation_days": 90,
            "hsm_backed": True,
            "in_policy": True,
            "data_classification": "identity",
        },
        {
            "name": "Pilot PQC API gateway",
            "algorithm": "hybrid-mlkem-x25519",
            "protocol": "TLS1.3",
            "environment": "staging",
            "exposure": "internal",
            "business_criticality": "medium",
            "kel_status": "kel_hybrid",
            "has_kel": True,
            "owner": "security-eng",
            "key_rotation_days": 60,
            "in_policy": True,
        },
        {
            "name": "Future-ready signing HSM",
            "algorithm": "ML-DSA-65",
            "protocol": "TLS1.3",
            "environment": "lab",
            "exposure": "airgapped",
            "business_criticality": "low",
            "kel_status": "kel_quantum_safe",
            "has_kel": True,
            "owner": "crypto-lab",
            "key_rotation_days": 30,
            "hsm_backed": True,
            "in_policy": True,
        },
    ]
    out = []
    for i, a in enumerate(base):
        row = dict(a)
        row["id"] = f"{org_id}-asset-{i+1:03d}"
        row["org_id"] = org_id
        row["tags"] = list(row.get("tags") or []) + ["demo_seed"]
        row["data_classification"] = row.get("data_classification") or "demo"
        row.setdefault("metadata", {})
        row["metadata"]["source"] = "demo_seed"
        out.append(row)
    return out
