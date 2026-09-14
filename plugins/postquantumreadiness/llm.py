"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

Multi-provider LLM client for discovery enrichment.
Providers use OpenAI-compatible chat/completions unless noted.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

# OpenAI-compatible base URLs (chat path = {base}/chat/completions)
PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "kilo": {
        "label": "Kilo Code Gateway",
        "base_url": "https://api.kilo.ai/api/gateway",
        "default_model": "x-ai/grok-4.5",
        "api_key_env": "KILO_API_KEY",
        "docs": "https://kilo.ai/docs/gateway",
        "compatible": "openai",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "docs": "https://platform.openai.com/docs",
        "compatible": "openai",
    },
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "api_key_env": "OPENROUTER_API_KEY",
        "docs": "https://openrouter.ai/docs",
        "compatible": "openai",
    },
    "anthropic": {
        "label": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-5",
        "api_key_env": "ANTHROPIC_API_KEY",
        "docs": "https://docs.anthropic.com",
        "compatible": "anthropic",
    },
    "ollama": {
        "label": "Ollama (local)",
        "base_url": "http://127.0.0.1:11434/v1",
        "default_model": "llama3.2",
        "api_key_env": None,
        "docs": "https://ollama.com",
        "compatible": "openai",
    },
    "custom": {
        "label": "Custom OpenAI-compatible",
        "base_url": "",
        "default_model": "gpt-4o-mini",
        "api_key_env": None,
        "docs": "",
        "compatible": "openai",
    },
}

SYSTEM_PROMPT = """You are a post-quantum crypto readiness analyst running live network discovery.
Given ONLY the raw probe findings provided (TLS certs, HTTP headers, KEL endpoint signals),
return JSON:
{
  "assets": [
    {
      "name": "string",
      "algorithm": "RSA-2048|ECDSA-secp256r1|Ed25519|ML-KEM-768|unknown|...",
      "protocol": "TLS1.3|TLS1.2|https|http|...",
      "environment": "production|staging|lab",
      "exposure": "internet|partner|internal",
      "business_criticality": "critical|high|medium|low",
      "kel_status": "none|kel_abstracted|kel_hybrid|kel_quantum_safe",
      "has_kel": true/false,
      "owner": "discovered",
      "expired": false,
      "expiring_soon": false,
      "notes": "short"
    }
  ],
  "limitations": ["what this scan could NOT see"],
  "questions": [
    {"id": "q1", "prompt": "follow-up question if blocked", "required": true}
  ],
  "reason": "short explanation"
}

Rules:
- NEVER invent hosts, algorithms, or KEL status not supported by the findings.
- Prefer concrete algorithms from TLS public keys when present.
- If KEL signals exist (prerotated_key_hash, /kel, key-rotation, yada), set
  has_kel=true and kel_status=kel_abstracted even when algorithm is still ECC/RSA.
- If a probe failed, put a limitation and optional question — do not fabricate assets.
- One primary TLS asset per successful target is enough.
"""


def _config_value(name, default=None):
    env = os.environ.get(name.upper()) if name else None
    if not env and name:
        env = os.environ.get(name)
    if env:
        return env
    try:
        from yadacoin.core.config import Config

        cfg = Config()
        if hasattr(cfg, name):
            val = getattr(cfg, name)
            if val not in (None, ""):
                return val
    except Exception:
        pass
    return default


def list_providers() -> List[Dict[str, Any]]:
    out = []
    for key, preset in PROVIDER_PRESETS.items():
        out.append(
            {
                "id": key,
                "label": preset["label"],
                "base_url": preset["base_url"],
                "default_model": preset["default_model"],
                "docs": preset.get("docs") or "",
                "compatible": preset.get("compatible") or "openai",
                "api_key_env": preset.get("api_key_env"),
            }
        )
    return out


def default_settings() -> Dict[str, Any]:
    return {
        "provider": "kilo",
        "api_key": "",
        "base_url": PROVIDER_PRESETS["kilo"]["base_url"],
        "model": "x-ai/grok-4.5",
        "enabled": True,
        "require_for_discovery": False,
    }


def resolve_settings(stored: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Merge stored settings with env/config and provider presets.
    Precedence: stored fields → env (KILO_API_KEY / OPENAI_…) → config.json → preset defaults.
    """
    base = default_settings()
    stored = dict(stored or {})
    provider = (stored.get("provider") or base["provider"] or "kilo").lower().strip()
    if provider not in PROVIDER_PRESETS:
        provider = "custom" if stored.get("base_url") else "kilo"
    preset = PROVIDER_PRESETS.get(provider) or PROVIDER_PRESETS["custom"]

    api_key = (
        (stored.get("api_key") or "").strip()
        or (
            os.environ.get(preset["api_key_env"]) if preset.get("api_key_env") else None
        )
        or _config_value("pqr_llm_api_key")
        or _config_value("kilo_api_key")
        or _config_value("KILO_API_KEY")
        or _config_value("openai_api_key")
        or _config_value("OPENAI_API_KEY")
        or ""
    )
    base_url = (
        (stored.get("base_url") or "").strip()
        or _config_value("pqr_llm_base_url")
        or preset.get("base_url")
        or ""
    ).rstrip("/")
    model = (
        (stored.get("model") or "").strip()
        or _config_value("pqr_llm_model")
        or preset.get("default_model")
        or "gpt-4o-mini"
    )
    enabled = stored.get("enabled")
    if enabled is None:
        enabled = True
    require_for_discovery = bool(stored.get("require_for_discovery", False))

    return {
        "provider": provider,
        "provider_label": preset.get("label") or provider,
        "api_key": api_key,
        "api_key_set": bool(api_key),
        "base_url": base_url,
        "model": model,
        "enabled": bool(enabled),
        "require_for_discovery": require_for_discovery,
        "compatible": preset.get("compatible") or "openai",
        "docs": preset.get("docs") or "",
    }


def public_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Strip secret material for API responses."""
    out = dict(settings)
    key = out.get("api_key") or ""
    out["api_key_set"] = bool(key)
    if key:
        out["api_key_masked"] = (key[:4] + "…" + key[-4:]) if len(key) > 8 else "••••"
    else:
        out["api_key_masked"] = ""
    out.pop("api_key", None)
    return out


def _parse_json_content(content: str) -> dict:
    if not content:
        raise ValueError("empty LLM response")
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM JSON must be an object")
    data.setdefault("assets", [])
    data.setdefault("reason", "")
    data.setdefault("limitations", [])
    data.setdefault("questions", [])
    if not isinstance(data["assets"], list):
        data["assets"] = []
    if not isinstance(data["limitations"], list):
        data["limitations"] = []
    if not isinstance(data["questions"], list):
        data["questions"] = []
    return data


def _chat_openai_compatible(
    settings: Dict[str, Any], messages: List[Dict[str, str]]
) -> str:
    base = (settings.get("base_url") or "").rstrip("/")
    if not base:
        raise ValueError("LLM base_url is empty — configure provider settings")
    url = base + "/chat/completions"
    payload = {
        "model": settings["model"],
        "temperature": 0,
        "messages": messages,
    }
    # response_format not supported by all gateways
    if settings.get("provider") in ("openai", "openrouter", "kilo", "custom"):
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings['api_key']}",
    }
    if settings.get("provider") == "openrouter":
        headers["HTTP-Referer"] = "https://yadacoin.io"
        headers["X-Title"] = "Yada Post-Quantum Readiness"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise ValueError(
            f"LLM HTTP {exc.code} ({settings.get('provider')}): {detail}"
        ) from exc
    content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
    if not content:
        raise ValueError(f"empty LLM content: {json.dumps(body)[:400]}")
    return content


def _chat_anthropic(settings: Dict[str, Any], system: str, user: str) -> str:
    url = (settings.get("base_url") or "https://api.anthropic.com/v1").rstrip("/")
    if not url.endswith("/messages"):
        url = url + "/messages"
    payload = {
        "model": settings["model"],
        "max_tokens": 4096,
        "temperature": 0,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": settings["api_key"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise ValueError(f"Anthropic HTTP {exc.code}: {detail}") from exc
    parts = body.get("content") or []
    text = "".join(p.get("text") or "" for p in parts if isinstance(p, dict))
    if not text:
        raise ValueError(f"empty Anthropic content: {json.dumps(body)[:400]}")
    return text


def chat_completion(settings: Dict[str, Any], system: str, user: str) -> str:
    settings = resolve_settings(settings)
    if settings.get("provider") == "ollama":
        # Ollama often needs no key
        settings = dict(settings)
        settings["api_key"] = settings.get("api_key") or "ollama"
    elif not settings.get("api_key"):
        raise ValueError(
            f"No API key configured for provider '{settings.get('provider')}'. "
            "Save a key under LLM settings (Kilo Code API key supported)."
        )
    if not settings.get("enabled", True):
        raise ValueError("LLM is disabled in settings")

    if (
        settings.get("compatible") == "anthropic"
        or settings.get("provider") == "anthropic"
    ):
        return _chat_anthropic(settings, system, user)
    return _chat_openai_compatible(
        settings,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )


def test_connection(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    s = resolve_settings(settings)
    try:
        content = chat_completion(
            s,
            system='Reply with JSON only: {"ok": true}',
            user='Respond with {"ok": true, "provider": "'
            + s.get("provider", "")
            + '"}',
        )
        parsed = _parse_json_content(content)
        return {
            "ok": True,
            "provider": s.get("provider"),
            "model": s.get("model"),
            "base_url": s.get("base_url"),
            "sample": parsed,
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": s.get("provider"),
            "model": s.get("model"),
            "base_url": s.get("base_url"),
            "error": str(exc)[:500],
        }


def enrich_findings(
    findings: List[Dict[str, Any]],
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    LLM pass over live probe findings.
    Returns {assets, reason, limitations, questions, used_llm, provider}.
    """
    resolved = resolve_settings(settings)
    if not resolved.get("enabled", True):
        return {
            "assets": [],
            "reason": "LLM disabled in settings",
            "limitations": ["LLM enrichment disabled"],
            "questions": [],
            "used_llm": False,
            "provider": resolved.get("provider"),
        }
    if not resolved.get("api_key") and resolved.get("provider") != "ollama":
        return {
            "assets": [],
            "reason": "no llm api key configured",
            "limitations": [
                "No LLM API key — only rule-based TLS/HTTP/KEL probes ran. "
                "Configure Kilo Code (or another provider) under LLM settings for deeper analysis."
            ],
            "questions": [
                {
                    "id": "llm_api_key",
                    "prompt": "Paste your Kilo Code API key (or switch provider) to enable AI enrichment of discovery findings.",
                    "required": False,
                    "field": "api_key",
                }
            ],
            "used_llm": False,
            "provider": resolved.get("provider"),
        }

    compact = []
    for f in findings[:25]:
        compact.append(
            {
                "target": f.get("target"),
                "tls": {
                    k: (f.get("tls") or {}).get(k)
                    for k in (
                        "ok",
                        "algorithm",
                        "protocol",
                        "tls_version",
                        "cipher",
                        "subject",
                        "issuer",
                        "expired",
                        "expiring_soon",
                        "error",
                    )
                },
                "http": {
                    k: (f.get("http") or {}).get(k)
                    for k in (
                        "ok",
                        "status",
                        "hsts",
                        "server",
                        "security_headers",
                        "title",
                        "error",
                    )
                },
                "kel": {
                    k: (f.get("kel") or {}).get(k)
                    for k in ("has_kel", "kel_status", "signals", "paths_hit")
                },
                "dns": {
                    k: (f.get("dns") or {}).get(k) for k in ("ok", "records", "error")
                },
                "rule_assets": f.get("assets") or [],
                "error": f.get("error"),
            }
        )

    user = json.dumps(
        {
            "findings": compact,
            "instruction": (
                "Normalize ONLY from these live probe results. "
                "Do not reuse demo or sample inventory. "
                "Preserve KEL-enhanced status for classical ECC/RSA when KEL signals exist."
            ),
        }
    )
    content = chat_completion(resolved, SYSTEM_PROMPT, user)
    data = _parse_json_content(content)
    data["used_llm"] = True
    data["provider"] = resolved.get("provider")
    data["model"] = resolved.get("model")
    return data
