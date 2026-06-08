"""agent_handlers.py — Core agent HTTP handlers (list, chat, register, discover, auth)."""
import asyncio
import datetime as _datetime
import inspect
import json
import logging as _logging
import os
import re

_log = _logging.getLogger("yadaaiagent.agent")


async def _async_none():
    """No-op coroutine used as a placeholder in asyncio.gather calls."""
    return None


from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

from yadacoin.http.base import BaseHandler

from ..booking.tools import _UI_HINT_SUFFIX, _did_web_id
from ..core.auth import _validator
from ..core.mcp_client import MCPClient
from ..github.api import _github_api_get
from .types import (
    _AGENT_TYPE_MAP,
    AGENT_TYPES,
    _brave_answers,
    _brave_web_search,
    _build_answers_context,
    _build_general_prompt_dynamic,
    _build_generic_intake_prompt,
    _build_search_context,
    _fetch_onchain_agents,
    _sanitize_messages,
)


class AgentListHandler(BaseHandler):
    """
    GET /ai-agent-auth/api/agents — return available agent types.

    The list is built dynamically:
      1. Meta types (general, agent_registration) — always present.
      2. On-chain / mempool agent registrations — grouped by agent_type.
         If the type matches a hardcoded AGENT_TYPES entry, that entry is used
         (richer metadata / intake flow).  Otherwise a generic entry is
         synthesised from the on-chain announcement.
      3. Hardcoded non-meta types with no on-chain registrations yet — also
         included so existing demos keep working.
    """

    async def get(self):
        _META_IDS = {"general", "agent_registration"}
        result = []

        # Meta types are always present
        for entry in AGENT_TYPES:
            if entry["id"] in _META_IDS:
                result.append({k: v for k, v in entry.items() if k != "systemPrompt"})

        # Fetch confirmed + mempool agent registrations
        try:
            onchain = await _fetch_onchain_agents(self.config)
        except Exception:
            onchain = []

        # Group on-chain agents by their declared agent_type
        type_to_agents: dict = {}
        for blob in onchain:
            at = blob.get("agent_type") or "general"
            if at in _META_IDS:
                continue
            type_to_agents.setdefault(at, []).append(blob)

        # node_config is only surfaced when admin_kel is configured on this node.
        _admin_kel_set = bool(getattr(self.config, "admin_kel", None))
        _ADMIN_ONLY_TYPES = {"node_config"}

        # For each discovered type: use hardcoded entry if available, else synthesise
        seen = set(_META_IDS)
        for type_id, agents_of_type in type_to_agents.items():
            if type_id in seen:
                continue
            # Skip admin-only types when admin_kel is not configured
            if type_id in _ADMIN_ONLY_TYPES and not _admin_kel_set:
                continue
            seen.add(type_id)
            hardcoded = next((a for a in AGENT_TYPES if a["id"] == type_id), None)
            if hardcoded:
                result.append(
                    {k: v for k, v in hardcoded.items() if k != "systemPrompt"}
                )
            else:
                rep = agents_of_type[0]
                result.append(
                    {
                        "id": type_id,
                        "label": rep.get("label") or type_id.replace("_", " ").title(),
                        "description": rep.get("description", ""),
                        "icon": rep.get("icon", "🤖"),
                        "authorizationType": None,
                        "fields": [],
                        "services": [type_id],
                    }
                )

        # Include hardcoded non-meta types not yet seen (no on-chain registration yet)
        for entry in AGENT_TYPES:
            if entry["id"] not in seen:
                # Skip admin-only types when admin_kel is not configured
                if entry["id"] in _ADMIN_ONLY_TYPES and not _admin_kel_set:
                    continue
                result.append({k: v for k, v in entry.items() if k != "systemPrompt"})
                seen.add(entry["id"])

        return self.render_as_json(result)


class AgentChatHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/chat

    Proxies the conversation to a configurable LLM and returns a
    structured JSON response for driving the agent UI.

    Body (JSON)
    -----------
    agent_type : str  (optional — defaults to "travel" for backwards compat)
    messages   : list[{role: "user"|"assistant", content: str}]
    llm        : {
        provider    : "ollama" | "openai" | "anthropic" | "openai_compat"
        model       : str (optional — falls back to sensible defaults)
        api_key     : str (required for openai / anthropic / openai_compat)
        ollama_host : str (ollama only, default "http://localhost:11434")
        base_url    : str (openai_compat only)
      }

    The api_key is supplied by the browser from localStorage and is never
    stored on the YadaCoin server.
    """

    # ── Default models per provider ───────────────────────────────────────────
    _DEFAULT_MODELS = {
        "ollama": "llama3.2",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-haiku-20240307",
        "openai_compat": "gpt-3.5-turbo",
        "github_models": "gpt-4.1-mini",
    }

    _GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid json body"})

        messages = body.get("messages", [])
        if not isinstance(messages, list):
            self.set_status(400)
            return self.render_as_json({"error": "messages must be a list"})

        # ── Resolve Web 2.0 sessions ─────────────────────────────────────── #
        # web2_sessions: { "github": "<nonce>", ... } supplied by the browser.
        # The nonce is an opaque server-side reference — the real OAuth token
        # never leaves the server.
        web2_sessions: dict = body.get("web2_sessions") or {}
        github_access_token = None  # type: str
        github_user = None  # type: dict
        microsoft_access_token = None  # type: str

        _gh_raw = web2_sessions.get("github") or ""
        if isinstance(_gh_raw, dict):
            github_nonce = (_gh_raw.get("nonce") or "").strip()
        else:
            github_nonce = str(_gh_raw).strip() if _gh_raw else ""
        if github_nonce:
            try:
                session_doc = (
                    await self.config.mongo.async_db.web2_oauth_sessions.find_one(
                        {
                            "nonce": github_nonce,
                            "provider": "github",
                            "status": "authorized",
                        }
                    )
                )
                if session_doc:
                    raw_token = session_doc.get("access_token", "")
                    token_iv = session_doc.get("token_iv", "")
                    enc_key_hex = (session_doc.get("token_enc_key") or "").strip()
                    if raw_token and token_iv and enc_key_hex:
                        # Wallet-mode: ciphertext stored — decrypt with stored key
                        try:
                            aesgcm = _AESGCM(bytes.fromhex(enc_key_hex))
                            github_access_token = aesgcm.decrypt(
                                bytes.fromhex(token_iv),
                                bytes.fromhex(raw_token),
                                None,
                            ).decode("utf-8")
                        except Exception:
                            pass  # decryption failed — treat as unauthenticated
                    else:
                        github_access_token = raw_token  # server-side plain token
                    # Refresh expiry on each use (sliding 30-day window)
                    await self.config.mongo.async_db.web2_oauth_sessions.update_one(
                        {"_id": session_doc["_id"]},
                        {
                            "$set": {
                                "expires_at": _datetime.datetime.utcnow()
                                + _datetime.timedelta(days=30)
                            }
                        },
                    )
            except Exception:
                pass  # treat as unauthenticated — never hard-fail

        _ms_raw = web2_sessions.get("microsoft") or ""
        if isinstance(_ms_raw, list):
            # Try each entry in order; use the first one with a live authorized session.
            _ms_nonce_candidates = [
                e.get("nonce", "").strip()
                for e in _ms_raw
                if isinstance(e, dict) and e.get("nonce", "").strip()
            ]
            _ms_nonce_candidates[0] if _ms_nonce_candidates else ""
        else:
            _ms_nonce_candidates = [_ms_raw.strip()] if _ms_raw else []
            _ms_raw.strip()
        if _ms_nonce_candidates:
            for _candidate_nonce in _ms_nonce_candidates:
                try:
                    session_doc = (
                        await self.config.mongo.async_db.web2_oauth_sessions.find_one(
                            {
                                "nonce": _candidate_nonce,
                                "provider": "microsoft",
                                "status": "authorized",
                            }
                        )
                    )
                    if not session_doc:
                        _log.debug(
                            "MS nonce %r not found in DB, trying next",
                            _candidate_nonce[:8] + "…",
                        )
                        continue
                    ms_raw_token = session_doc.get("access_token", "")
                    ms_token_iv = session_doc.get("token_iv", "")
                    ms_enc_key_hex = (session_doc.get("token_enc_key") or "").strip()
                    _log.debug(
                        "MS session found for nonce %r — has_token=%s has_iv=%s has_key=%s key_len=%s",
                        _candidate_nonce[:8] + "…",
                        bool(ms_raw_token),
                        bool(ms_token_iv),
                        bool(ms_enc_key_hex),
                        len(ms_enc_key_hex),
                    )
                    if ms_raw_token and ms_token_iv and ms_enc_key_hex:
                        try:
                            aesgcm = _AESGCM(bytes.fromhex(ms_enc_key_hex))
                            microsoft_access_token = aesgcm.decrypt(
                                bytes.fromhex(ms_token_iv),
                                bytes.fromhex(ms_raw_token),
                                None,
                            ).decode("utf-8")
                        except Exception as _dec_err:
                            _log.warning(
                                "MS token decrypt failed for nonce %r: %s | key_len=%d iv_len=%d ct_len=%d",
                                _candidate_nonce[:8] + "…",
                                _dec_err,
                                len(ms_enc_key_hex),
                                len(ms_token_iv),
                                len(ms_raw_token),
                            )
                            continue  # try next candidate
                    else:
                        microsoft_access_token = ms_raw_token
                        _log.debug(
                            "MS token using plaintext fallback for nonce %r (no iv/key in session)",
                            _candidate_nonce[:8] + "…",
                        )
                    # Slide the 30-day expiry window
                    await self.config.mongo.async_db.web2_oauth_sessions.update_one(
                        {"_id": session_doc["_id"]},
                        {
                            "$set": {
                                "expires_at": _datetime.datetime.utcnow()
                                + _datetime.timedelta(days=30)
                            }
                        },
                    )
                    break  # found a working session
                except Exception as _outer_ms_err:
                    _log.warning(
                        "MS session lookup error for nonce %r: %s",
                        _candidate_nonce[:8] + "…",
                        _outer_ms_err,
                    )
            if microsoft_access_token is None and _ms_nonce_candidates:
                _log.warning(
                    "MS: tried %d nonce(s), none yielded a valid token",
                    len(_ms_nonce_candidates),
                )

        # ── Agent loop mode ───────────────────────────────────────────────── #
        if body.get("mode") == "loop":
            llm_cfg = body.get("llm") or {}
            return await self._run_agent_loop(
                body, github_access_token, microsoft_access_token, llm_cfg
            )

        # ── Resolve agent type and its system prompt ──────────────────────── #
        agent_type_id = (body.get("agent_type") or "general").strip()
        agent_type = _AGENT_TYPE_MAP.get(agent_type_id)

        if agent_type_id == "general":
            # Dynamically inject all on-chain registered types into the prompt
            _onchain = await _fetch_onchain_agents(self.config)
            system_prompt = _build_general_prompt_dynamic(_onchain)
        elif agent_type and agent_type.get("systemPrompt"):
            # Hardcoded or plugin-registered type with a known intake prompt
            raw_prompt = agent_type["systemPrompt"]
            # Inject GitHub connectivity context for the github agent type
            if agent_type_id == "github":
                if github_access_token:
                    github_ctx = (
                        "CRITICAL — GitHub IS CONNECTED: A valid OAuth access token is confirmed. "
                        "You MUST NOT ask the user to connect GitHub. "
                        "You MUST NOT set auth_required. "
                        "Respond directly to the user's GitHub request right now.\n\n"
                    )
                else:
                    github_ctx = (
                        "CONTEXT: GitHub is NOT connected. You do NOT have a GitHub access token. "
                        'Set auth_required to {"provider": "github"} and ask the user to connect.\n\n'
                    )
                system_prompt = raw_prompt.replace("{github_context}", github_ctx)
            elif agent_type_id == "microsoft":
                if microsoft_access_token:
                    ms_ctx = (
                        "CONTEXT: Microsoft IS connected. You have full access to Microsoft Graph "
                        "on behalf of the user. Do NOT emit auth_required.\n\n"
                    )
                else:
                    ms_ctx = (
                        "CONTEXT: Microsoft is NOT connected. You do NOT have a Microsoft access token. "
                        'Set auth_required to {"provider": "microsoft"} and ask the user to connect.\n\n'
                    )
                system_prompt = raw_prompt.replace("{microsoft_context}", ms_ctx)
            else:
                system_prompt = raw_prompt.replace("{github_context}", "").replace(
                    "{microsoft_context}", ""
                )
        else:
            # Unknown type — look up on-chain agents of this type and synthesise
            _onchain = await _fetch_onchain_agents(self.config)
            _of_type = [a for a in _onchain if a.get("agent_type") == agent_type_id]
            if not _of_type:
                self.set_status(400)
                return self.render_as_json(
                    {"error": f"unknown agent_type '{agent_type_id}'"}
                )
            system_prompt = _build_generic_intake_prompt(agent_type_id, _of_type)

        # ── Read per-request LLM config sent from the browser ─────────────── #
        llm_cfg = body.get("llm") or {}
        provider = (llm_cfg.get("provider") or "ollama").lower().strip()
        model = (llm_cfg.get("model") or "").strip() or self._DEFAULT_MODELS.get(
            provider, "gpt-4o-mini"
        )
        api_key = (llm_cfg.get("api_key") or "").strip()
        ollama_host = (
            llm_cfg.get("ollama_host")
            or getattr(self.config, "ollama_host", None)
            or "http://127.0.0.1:11434"
        ).rstrip("/")
        base_url = (llm_cfg.get("base_url") or "").rstrip("/")

        # ── Brave Search context injection ────────────────────────────────────
        # Runs only for the general agent when a Brave API key is available.
        # Results are appended to the system prompt so the LLM can cite them.
        brave_api_key = (
            (body.get("brave_api_key") or "").strip()
            or os.environ.get("BRAVE_API_KEY", "")
            or getattr(self.config, "brave_api_key", "")
            or ""
        )
        brave_answers_api_key = (
            (body.get("brave_answers_api_key") or "").strip()
            or os.environ.get("BRAVE_ANSWERS_API_KEY", "")
            or getattr(self.config, "brave_answers_api_key", "")
            or ""
        )
        search_sources: list = []  # populated below if search runs
        if (
            (brave_api_key or brave_answers_api_key)
            and agent_type_id == "general"
            and messages
        ):
            last_user_msg = next(
                (
                    m.get("content", "")
                    for m in reversed(messages)
                    if m.get("role") == "user"
                ),
                "",
            ).strip()
            # Skip search for very short inputs (greetings, single words, etc.)
            if len(last_user_msg) >= 8:
                # Run Brave Answers and Brave Search in parallel for best coverage.
                # Both results are included so the LLM can compare and pick the
                # most accurate / relevant answer relative to the original query.
                _answers_coro = (
                    _brave_answers(brave_answers_api_key, last_user_msg)
                    if brave_answers_api_key
                    else _async_none()
                )
                _search_coro = (
                    _brave_web_search(brave_api_key, last_user_msg, count=5)
                    if brave_api_key
                    else _async_none()
                )
                try:
                    _answers_result, _search_result = await asyncio.gather(
                        _answers_coro, _search_coro, return_exceptions=True
                    )
                except Exception:
                    _answers_result, _search_result = None, None

                _has_answers = isinstance(_answers_result, str) and _answers_result
                _has_search = isinstance(_search_result, list) and _search_result

                if _has_answers or _has_search:
                    system_prompt += (
                        "\n\n[The following web context was retrieved for this query. "
                        "Compare both sources against the user's question and use "
                        "whichever is most accurate and relevant. Cite sources when helpful.]"
                    )
                if _has_answers:
                    system_prompt += "\n\n" + _build_answers_context(
                        _answers_result, last_user_msg
                    )
                if _has_search:
                    system_prompt += "\n\n" + _build_search_context(
                        _search_result, last_user_msg
                    )
                    search_sources = [
                        {"title": r["title"], "url": r["url"]}
                        for r in _search_result
                        if r.get("url")
                    ]

        full_messages = _sanitize_messages(
            [{"role": "system", "content": system_prompt + _UI_HINT_SUFFIX}] + messages
        )

        # When we have a confirmed OAuth token, strip any stale "please connect"
        # assistant turns from the history so they don't bias the LLM.
        if github_access_token and agent_type_id == "github":
            full_messages = [
                m
                for m in full_messages
                if not (
                    m.get("role") == "assistant"
                    and "connect" in (m.get("content") or "").lower()
                    and "github" in (m.get("content") or "").lower()
                )
            ]
        if microsoft_access_token and agent_type_id == "microsoft":
            full_messages = [
                m
                for m in full_messages
                if not (
                    m.get("role") == "assistant"
                    and "connect" in (m.get("content") or "").lower()
                    and "microsoft" in (m.get("content") or "").lower()
                )
            ]

        try:
            if provider == "ollama":
                content = await self._call_ollama(ollama_host, model, full_messages)
            elif provider == "openai":
                content = await self._call_openai_compat(
                    "https://api.openai.com/v1", model, api_key, full_messages
                )
            elif provider == "anthropic":
                content = await self._call_anthropic(model, api_key, full_messages)
            elif provider == "openai_compat":
                if not base_url:
                    self.set_status(400)
                    return self.render_as_json(
                        {"error": "base_url required for openai_compat provider"}
                    )
                content = await self._call_openai_compat(
                    base_url, model, api_key, full_messages
                )
            elif provider == "github_models":
                content = await self._call_openai_compat(
                    self._GITHUB_MODELS_BASE_URL,
                    model,
                    api_key,
                    full_messages,
                    temperature=None,
                )
            else:
                self.set_status(400)
                return self.render_as_json({"error": f"unknown provider '{provider}'"})
        except Exception as exc:
            self.set_status(502)
            return self.render_as_json(
                {"error": f"LLM unreachable ({provider}): {exc}"}
            )

        # Strip any accidental markdown code fences the model might add
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        # Some LLMs prepend natural-language text before the JSON block.
        # Scan for the first '{' and try to parse from there.
        def _extract_json(text):
            start = text.find("{")
            if start == -1:
                return None
            try:
                return json.loads(text[start:])
            except Exception:
                pass
            # Try finding the last '}' too (handles trailing garbage)
            end = text.rfind("}")
            if end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except Exception:
                    pass
            return None

        parsed = _extract_json(content)
        if parsed:
            reply = str(parsed.get("reply", ""))
            extracted = parsed.get("extracted") or {}
            complete = bool(parsed.get("complete", False))
            choices = (
                parsed.get("choices") if isinstance(parsed.get("choices"), list) else []
            )
        else:
            parsed = {}
            reply = content
            extracted = {}
            complete = False
            choices = []

        detected_agent_type = (
            parsed.get("detected_agent_type", agent_type_id)
            if isinstance(parsed, dict)
            else agent_type_id
        )

        # ── auth_required passthrough ─────────────────────────────────────────
        # If the LLM signals the frontend needs to connect a Web2 account,
        # pass that signal straight through — BUT only when the backend has
        # confirmed the session is NOT actually connected.  If we already have
        # a valid token, suppress the LLM's auth_required (it can be confused
        # by user messages like "connect github" even when already connected).
        auth_required = None
        if isinstance(parsed, dict) and isinstance(parsed.get("auth_required"), dict):
            ar = parsed["auth_required"]
            if isinstance(ar.get("provider"), str) and ar["provider"]:
                provider_name = ar["provider"]
                if provider_name == "github" and github_access_token:
                    pass  # backend has a valid token — LLM is wrong, suppress
                elif provider_name == "microsoft" and microsoft_access_token:
                    pass  # same for microsoft
                else:
                    auth_required = {"provider": provider_name}

        # ── GitHub inline actions (read-only, no approval needed) ─────────────
        # Mirror the wallet-agent pattern: the LLM sets extracted.action and
        # complete=false; the server fetches the data and returns github_data.
        github_data = None  # type: dict
        _GH_READ_ACTIONS = {
            "list_repos",
            "get_repo",
            "list_issues",
            "list_prs",
            "list_notifications",
        }
        if (
            detected_agent_type == "github"
            and github_access_token
            and isinstance(extracted, dict)
            and extracted.get("action") in _GH_READ_ACTIONS
        ):
            action = extracted["action"]
            owner = (extracted.get("owner") or "").strip()
            repo = (extracted.get("repo") or "").strip()
            state = (extracted.get("state") or "open").strip()
            visibility = (extracted.get("visibility") or "all").strip().lower()
            if visibility not in ("public", "private", "all"):
                visibility = "all"
            try:
                if action == "list_repos":
                    repo_params = {
                        "sort": "updated",
                        "per_page": 10,
                        "affiliation": "owner,collaborator",
                    }
                    if visibility != "all":
                        repo_params["visibility"] = visibility
                    data_raw = await _github_api_get(
                        github_access_token,
                        "/user/repos",
                        repo_params,
                    )
                    github_data = {
                        "type": "repos",
                        "items": [
                            {
                                "full_name": r.get("full_name", ""),
                                "description": (r.get("description") or "")[:120],
                                "stars": r.get("stargazers_count", 0),
                                "open_issues": r.get("open_issues_count", 0),
                                "language": r.get("language") or "",
                                "private": r.get("private", False),
                                "url": r.get("html_url", ""),
                                "updated_at": (r.get("updated_at") or "")[:10],
                            }
                            for r in (data_raw if isinstance(data_raw, list) else [])[
                                :10
                            ]
                        ],
                    }
                elif action == "get_repo" and owner and repo:
                    r = await _github_api_get(
                        github_access_token, f"/repos/{owner}/{repo}"
                    )
                    github_data = {
                        "type": "repo",
                        "full_name": r.get("full_name", ""),
                        "description": (r.get("description") or "")[:200],
                        "stars": r.get("stargazers_count", 0),
                        "forks": r.get("forks_count", 0),
                        "open_issues": r.get("open_issues_count", 0),
                        "language": r.get("language") or "",
                        "default_branch": r.get("default_branch", "main"),
                        "topics": r.get("topics", [])[:8],
                        "url": r.get("html_url", ""),
                    }
                elif action == "list_issues" and owner and repo:
                    data_raw = await _github_api_get(
                        github_access_token,
                        f"/repos/{owner}/{repo}/issues",
                        {"state": state, "per_page": 10, "pulls": "false"},
                    )
                    github_data = {
                        "type": "issues",
                        "repo": f"{owner}/{repo}",
                        "state": state,
                        "items": [
                            {
                                "number": i.get("number"),
                                "title": (i.get("title") or "")[:100],
                                "state": i.get("state", ""),
                                "author": (i.get("user") or {}).get("login", ""),
                                "comments": i.get("comments", 0),
                                "created_at": (i.get("created_at") or "")[:10],
                                "url": i.get("html_url", ""),
                            }
                            for i in (data_raw if isinstance(data_raw, list) else [])[
                                :10
                            ]
                            if not i.get("pull_request")  # exclude PRs from /issues
                        ],
                    }
                elif action == "list_prs" and owner and repo:
                    data_raw = await _github_api_get(
                        github_access_token,
                        f"/repos/{owner}/{repo}/pulls",
                        {"state": state, "per_page": 10},
                    )
                    github_data = {
                        "type": "prs",
                        "repo": f"{owner}/{repo}",
                        "state": state,
                        "items": [
                            {
                                "number": p.get("number"),
                                "title": (p.get("title") or "")[:100],
                                "state": p.get("state", ""),
                                "author": (p.get("user") or {}).get("login", ""),
                                "draft": p.get("draft", False),
                                "created_at": (p.get("created_at") or "")[:10],
                                "url": p.get("html_url", ""),
                            }
                            for p in (data_raw if isinstance(data_raw, list) else [])[
                                :10
                            ]
                        ],
                    }
                elif action == "list_notifications":
                    data_raw = await _github_api_get(
                        github_access_token,
                        "/notifications",
                        {"participating": "false", "per_page": 10},
                    )
                    github_data = {
                        "type": "notifications",
                        "items": [
                            {
                                "title": (n.get("subject") or {}).get("title", "")[
                                    :100
                                ],
                                "type": (n.get("subject") or {}).get("type", ""),
                                "repo": (n.get("repository") or {}).get(
                                    "full_name", ""
                                ),
                                "reason": n.get("reason", ""),
                                "unread": n.get("unread", False),
                                "updated_at": (n.get("updated_at") or "")[:10],
                            }
                            for n in (data_raw if isinstance(data_raw, list) else [])[
                                :10
                            ]
                        ],
                    }
            except Exception as _gh_exc:
                github_data = {"type": "error", "message": str(_gh_exc)[:200]}

        # ── Microsoft inline actions (read-only + send_email + summarize) ──────
        microsoft_data = None  # type: dict
        _MS_READ_ACTIONS = {
            "list_emails",
            "read_email",
            "list_events",
            "summarize_email",
            "create_todo",
        }
        _MS_WRITE_ACTIONS = {
            "send_email",
            "push_todo",
            "add_todo_task",
            "complete_todo_task",
            "delete_todo_task",
        }
        _MS_ALL_ACTIONS = _MS_READ_ACTIONS | _MS_WRITE_ACTIONS
        if (
            detected_agent_type == "microsoft"
            and microsoft_access_token
            and isinstance(extracted, dict)
            and extracted.get("action") in _MS_ALL_ACTIONS
        ):
            action = extracted["action"]
            folder = (extracted.get("folder") or "inbox").strip().lower()
            top = int(extracted.get("top") or 10)
            if top > 25:
                top = 25
            message_id = (extracted.get("message_id") or "").strip()
            try:
                if action == "list_emails":
                    folder_path = {
                        "inbox": "inbox",
                        "sentitems": "sentItems",
                        "drafts": "drafts",
                    }.get(folder, "inbox")
                    data_raw = await _msgraph_api_get(
                        microsoft_access_token,
                        f"/me/mailFolders/{folder_path}/messages",
                        {
                            "$top": top,
                            "$select": "id,subject,from,receivedDateTime,isRead,bodyPreview",
                            "$orderby": "receivedDateTime desc",
                        },
                    )
                    items = data_raw.get("value", [])
                    microsoft_data = {
                        "type": "emails",
                        "folder": folder,
                        "items": [
                            {
                                "id": m.get("id", ""),
                                "subject": (m.get("subject") or "(no subject)")[:120],
                                "from": (
                                    (m.get("from") or {}).get("emailAddress") or {}
                                ).get("address", ""),
                                "from_name": (
                                    (m.get("from") or {}).get("emailAddress") or {}
                                ).get("name", ""),
                                "received": (m.get("receivedDateTime") or "")[
                                    :16
                                ].replace("T", " "),
                                "is_read": m.get("isRead", True),
                                "preview": (m.get("bodyPreview") or "")[:150],
                            }
                            for m in items[:top]
                        ],
                    }
                elif action == "summarize_email":
                    # Fetch latest N emails with full body, then summarize via a second LLM call
                    sum_top = int(extracted.get("top") or 1)
                    if sum_top > 10:
                        sum_top = 10
                    sr = await _msgraph_api_get(
                        microsoft_access_token,
                        "/me/mailFolders/inbox/messages",
                        {
                            "$top": sum_top,
                            "$select": "id,subject,from,receivedDateTime,body",
                            "$orderby": "receivedDateTime desc",
                        },
                    )
                    sr_items = sr.get("value", [])
                    if sr_items:
                        # Build a single prompt block for all fetched emails
                        email_blocks = []
                        for idx, m in enumerate(sr_items, 1):
                            body_content = (m.get("body") or {}).get("content", "")
                            body_type = (m.get("body") or {}).get("contentType", "text")
                            if body_type == "html":
                                body_text = _re.sub(r"<[^>]+>", " ", body_content)
                                body_text = " ".join(body_text.split())[:1500]
                            else:
                                body_text = body_content[:1500]
                            em_subj = (m.get("subject") or "(no subject)")[:120]
                            em_from = (
                                (m.get("from") or {}).get("emailAddress") or {}
                            ).get("name", "") or (
                                (m.get("from") or {}).get("emailAddress") or {}
                            ).get(
                                "address", ""
                            )
                            em_date = (m.get("receivedDateTime") or "")[:10]
                            email_blocks.append(
                                f"--- Email {idx} ---\nFrom: {em_from}\nSubject: {em_subj}\nDate: {em_date}\n\n{body_text}"
                            )
                        if sum_top == 1:
                            sum_instruction = "Summarize the following email in 2-4 sentences. Highlight the key points, any requests, and action items."
                        else:
                            sum_instruction = (
                                f"Summarize each of the following {len(sr_items)} emails in 1-2 sentences. "
                                "For each, state who it is from, what it is about, and any action required. "
                                "Format as a numbered list."
                            )
                        sum_msgs = _sanitize_messages(
                            [
                                {
                                    "role": "system",
                                    "content": "You are an email assistant. "
                                    + sum_instruction,
                                },
                                {"role": "user", "content": "\n\n".join(email_blocks)},
                            ]
                        )
                        try:
                            if provider == "ollama":
                                reply = await self._call_ollama(
                                    ollama_host, model, sum_msgs
                                )
                            elif provider == "openai":
                                reply = await self._call_openai_compat(
                                    "https://api.openai.com/v1",
                                    model,
                                    api_key,
                                    sum_msgs,
                                )
                            elif provider == "anthropic":
                                reply = await self._call_anthropic(
                                    model, api_key, sum_msgs
                                )
                            elif provider in ("openai_compat", "github_models"):
                                _su = (
                                    self._GITHUB_MODELS_BASE_URL
                                    if provider == "github_models"
                                    else base_url
                                )
                                reply = await self._call_openai_compat(
                                    _su, model, api_key, sum_msgs
                                )
                        except Exception:
                            reply = f"Fetched {len(sr_items)} email(s) but could not summarize. Please try again."
                        microsoft_data = {
                            "type": "email_summary",
                            "count": len(sr_items),
                            "subjects": [
                                {
                                    "subject": (m.get("subject") or "(no subject)")[
                                        :120
                                    ],
                                    "from_name": (
                                        (m.get("from") or {}).get("emailAddress") or {}
                                    ).get("name", ""),
                                    "from": (
                                        (m.get("from") or {}).get("emailAddress") or {}
                                    ).get("address", ""),
                                    "received": (m.get("receivedDateTime") or "")[:10],
                                }
                                for m in sr_items
                            ],
                        }
                    else:
                        reply = "Your inbox appears to be empty."
                elif action == "create_todo":
                    # Fetch latest N emails, extract action items via LLM
                    todo_top = int(extracted.get("top") or 10)
                    if todo_top > 25:
                        todo_top = 25
                    tr = await _msgraph_api_get(
                        microsoft_access_token,
                        "/me/mailFolders/inbox/messages",
                        {
                            "$top": todo_top,
                            "$select": "id,subject,from,receivedDateTime,body",
                            "$orderby": "receivedDateTime desc",
                        },
                    )
                    tr_items = tr.get("value", [])
                    if tr_items:
                        todo_blocks = []
                        for idx, m in enumerate(tr_items, 1):
                            body_content = (m.get("body") or {}).get("content", "")
                            body_type = (m.get("body") or {}).get("contentType", "text")
                            if body_type == "html":
                                body_text = _re.sub(r"<[^>]+>", " ", body_content)
                                body_text = " ".join(body_text.split())[:1200]
                            else:
                                body_text = body_content[:1200]
                            em_subj = (m.get("subject") or "(no subject)")[:120]
                            em_from = (
                                (m.get("from") or {}).get("emailAddress") or {}
                            ).get("name", "") or (
                                (m.get("from") or {}).get("emailAddress") or {}
                            ).get(
                                "address", ""
                            )
                            em_date = (m.get("receivedDateTime") or "")[:10]
                            todo_blocks.append(
                                f"--- Email {idx} ---\nFrom: {em_from}\nSubject: {em_subj}\nDate: {em_date}\n\n{body_text}"
                            )
                        todo_instruction = (
                            f"You are a task extraction assistant. Review the following {len(tr_items)} emails "
                            "and extract a concise to-do list of action items the recipient needs to act on. "
                            "Group items by urgency if possible. Format as a numbered list. "
                            "Only include genuine action items — skip newsletters, automated notifications, and FYI emails."
                        )
                        todo_msgs = _sanitize_messages(
                            [
                                {"role": "system", "content": todo_instruction},
                                {"role": "user", "content": "\n\n".join(todo_blocks)},
                            ]
                        )
                        try:
                            if provider == "ollama":
                                reply = await self._call_ollama(
                                    ollama_host, model, todo_msgs
                                )
                            elif provider == "openai":
                                reply = await self._call_openai_compat(
                                    "https://api.openai.com/v1",
                                    model,
                                    api_key,
                                    todo_msgs,
                                )
                            elif provider == "anthropic":
                                reply = await self._call_anthropic(
                                    model, api_key, todo_msgs
                                )
                            elif provider in ("openai_compat", "github_models"):
                                _tu = (
                                    self._GITHUB_MODELS_BASE_URL
                                    if provider == "github_models"
                                    else base_url
                                )
                                reply = await self._call_openai_compat(
                                    _tu, model, api_key, todo_msgs
                                )
                        except Exception:
                            reply = f"Fetched {len(tr_items)} email(s) but could not extract tasks. Please try again."
                        microsoft_data = {
                            "type": "todo_list",
                            "count": len(tr_items),
                            "subjects": [
                                {
                                    "subject": (m.get("subject") or "(no subject)")[
                                        :120
                                    ],
                                    "from_name": (
                                        (m.get("from") or {}).get("emailAddress") or {}
                                    ).get("name", ""),
                                    "from": (
                                        (m.get("from") or {}).get("emailAddress") or {}
                                    ).get("address", ""),
                                    "received": (m.get("receivedDateTime") or "")[:10],
                                }
                                for m in tr_items
                            ],
                        }
                    else:
                        reply = "Your inbox appears to be empty."
                elif action == "read_email" and message_id:
                    m = await _msgraph_api_get(
                        microsoft_access_token,
                        f"/me/messages/{message_id}",
                        {
                            "$select": "id,subject,from,toRecipients,receivedDateTime,body"
                        },
                    )
                    microsoft_data = {
                        "type": "email",
                        "id": m.get("id", ""),
                        "subject": (m.get("subject") or "(no subject)")[:200],
                        "from": ((m.get("from") or {}).get("emailAddress") or {}).get(
                            "address", ""
                        ),
                        "from_name": (
                            (m.get("from") or {}).get("emailAddress") or {}
                        ).get("name", ""),
                        "received": (m.get("receivedDateTime") or "")[:16].replace(
                            "T", " "
                        ),
                        "body": (m.get("body") or {}).get("content", "")[:2000],
                        "body_type": (m.get("body") or {}).get("contentType", "text"),
                    }
                elif action == "list_events":
                    data_raw = await _msgraph_api_get(
                        microsoft_access_token,
                        "/me/calendarView",
                        {
                            "$top": top,
                            "$select": "id,subject,start,end,location,isOnlineMeeting,organizer",
                            "$orderby": "start/dateTime",
                            "startDateTime": _datetime.datetime.utcnow().strftime(
                                "%Y-%m-%dT00:00:00Z"
                            ),
                            "endDateTime": (
                                _datetime.datetime.utcnow()
                                + _datetime.timedelta(days=14)
                            ).strftime("%Y-%m-%dT00:00:00Z"),
                        },
                    )
                    items = data_raw.get("value", [])
                    microsoft_data = {
                        "type": "events",
                        "items": [
                            {
                                "id": e.get("id", ""),
                                "subject": (e.get("subject") or "(no subject)")[:120],
                                "start": (e.get("start") or {})
                                .get("dateTime", "")[:16]
                                .replace("T", " "),
                                "end": (e.get("end") or {})
                                .get("dateTime", "")[:16]
                                .replace("T", " "),
                                "location": (
                                    (e.get("location") or {}).get("displayName") or ""
                                )[:80],
                                "online": e.get("isOnlineMeeting", False),
                                "organizer": (
                                    (e.get("organizer") or {}).get("emailAddress") or {}
                                ).get("address", ""),
                            }
                            for e in items[:top]
                        ],
                    }
                elif action == "push_todo":
                    # Fetch emails, extract action items via LLM, then create tasks in Microsoft To Do
                    pt_top = int(extracted.get("top") or 10)
                    if pt_top > 25:
                        pt_top = 25
                    ptr = await _msgraph_api_get(
                        microsoft_access_token,
                        "/me/mailFolders/inbox/messages",
                        {
                            "$top": pt_top,
                            "$select": "id,subject,from,receivedDateTime,body",
                            "$orderby": "receivedDateTime desc",
                        },
                    )
                    pt_items = ptr.get("value", [])
                    if pt_items:
                        pt_blocks = []
                        for idx, m in enumerate(pt_items, 1):
                            body_content = (m.get("body") or {}).get("content", "")
                            body_type = (m.get("body") or {}).get("contentType", "text")
                            if body_type == "html":
                                body_text = _re.sub(r"<[^>]+>", " ", body_content)
                                body_text = " ".join(body_text.split())[:1200]
                            else:
                                body_text = body_content[:1200]
                            em_subj = (m.get("subject") or "(no subject)")[:120]
                            em_from = (
                                (m.get("from") or {}).get("emailAddress") or {}
                            ).get("name", "") or (
                                (m.get("from") or {}).get("emailAddress") or {}
                            ).get(
                                "address", ""
                            )
                            em_date = (m.get("receivedDateTime") or "")[:10]
                            pt_blocks.append(
                                f"--- Email {idx} ---\nFrom: {em_from}\nSubject: {em_subj}\nDate: {em_date}\n\n{body_text}"
                            )
                        pt_instruction = (
                            f"You are a task extraction assistant. Review the following {len(pt_items)} emails "
                            "and extract a concise list of action items the recipient needs to act on. "
                            "Output ONLY a JSON array of strings, where each string is one task title "
                            "(short, under 255 characters). Skip newsletters, automated notifications, and FYI emails. "
                            'Example: ["Reply to John about budget approval", "Submit expense report by Friday"]'
                        )
                        pt_msgs = _sanitize_messages(
                            [
                                {"role": "system", "content": pt_instruction},
                                {"role": "user", "content": "\n\n".join(pt_blocks)},
                            ]
                        )
                        task_titles = []
                        try:
                            if provider == "ollama":
                                raw_tasks = await self._call_ollama(
                                    ollama_host, model, pt_msgs
                                )
                            elif provider == "openai":
                                raw_tasks = await self._call_openai_compat(
                                    "https://api.openai.com/v1", model, api_key, pt_msgs
                                )
                            elif provider == "anthropic":
                                raw_tasks = await self._call_anthropic(
                                    model, api_key, pt_msgs
                                )
                            elif provider in ("openai_compat", "github_models"):
                                _pt_u = (
                                    self._GITHUB_MODELS_BASE_URL
                                    if provider == "github_models"
                                    else base_url
                                )
                                raw_tasks = await self._call_openai_compat(
                                    _pt_u, model, api_key, pt_msgs
                                )
                            else:
                                raw_tasks = "[]"
                            # Parse JSON array from LLM response
                            json_match = _re.search(r"\[.*\]", raw_tasks, _re.DOTALL)
                            if json_match:
                                task_titles = json.loads(json_match.group(0))
                                task_titles = [str(t)[:255] for t in task_titles if t]
                        except Exception:
                            task_titles = []
                        if task_titles:
                            # Get or create the default To Do task list
                            lists_resp = await _msgraph_api_get(
                                microsoft_access_token, "/me/todo/lists", {}
                            )
                            todo_lists = lists_resp.get("value", [])
                            # Prefer "Tasks" list (default), otherwise use first list
                            default_list = next(
                                (
                                    l
                                    for l in todo_lists
                                    if l.get("wellknownListName") == "defaultList"
                                ),
                                todo_lists[0] if todo_lists else None,
                            )
                            if not default_list:
                                # Create a new list if none exist
                                default_list = await _msgraph_api_post(
                                    microsoft_access_token,
                                    "/me/todo/lists",
                                    {"displayName": "Email Action Items"},
                                )
                            list_id = default_list.get("id", "")
                            created = []
                            for title in task_titles[:20]:  # max 20 tasks per run
                                try:
                                    await _msgraph_api_post(
                                        microsoft_access_token,
                                        f"/me/todo/lists/{list_id}/tasks",
                                        {"title": title},
                                    )
                                    created.append(title)
                                except Exception:
                                    pass
                            list_name = default_list.get("displayName", "Tasks")
                            reply = (
                                f"Done! Added {len(created)} task{'s' if len(created) != 1 else ''} "
                                f'to your "{list_name}" list in Microsoft To Do.'
                            )
                            microsoft_data = {
                                "type": "todo_pushed",
                                "list_name": list_name,
                                "tasks": created,
                            }
                        else:
                            reply = "No action items were found in your recent emails."
                    else:
                        reply = "Your inbox appears to be empty."
                elif action == "add_todo_task":
                    task_title = (extracted.get("task_title") or "").strip()
                    if task_title:
                        # Get default To Do list
                        lists_resp = await _msgraph_api_get(
                            microsoft_access_token, "/me/todo/lists", {}
                        )
                        todo_lists = lists_resp.get("value", [])
                        default_list = next(
                            (
                                l
                                for l in todo_lists
                                if l.get("wellknownListName") == "defaultList"
                            ),
                            todo_lists[0] if todo_lists else None,
                        )
                        if not default_list:
                            default_list = await _msgraph_api_post(
                                microsoft_access_token,
                                "/me/todo/lists",
                                {"displayName": "Tasks"},
                            )
                        list_id = default_list.get("id", "")
                        list_name = default_list.get("displayName", "Tasks")
                        await _msgraph_api_post(
                            microsoft_access_token,
                            f"/me/todo/lists/{list_id}/tasks",
                            {"title": task_title[:255]},
                        )
                        reply = (
                            f'Done! Added "{task_title}" to your "{list_name}" list.'
                        )
                        microsoft_data = {
                            "type": "task_added",
                            "list_name": list_name,
                            "task": task_title,
                        }
                    else:
                        reply = "What would you like to add to your To Do list?"
                elif action == "complete_todo_task":
                    task_title = (extracted.get("task_title") or "").strip()
                    if task_title:
                        # Search all To Do lists for a task matching the title
                        lists_resp = await _msgraph_api_get(
                            microsoft_access_token, "/me/todo/lists", {}
                        )
                        todo_lists = lists_resp.get("value", [])
                        matched_list_id = None
                        matched_list_name = None
                        matched_task_id = None
                        search_lower = task_title.lower()
                        for tl in todo_lists:
                            list_id = tl.get("id", "")
                            tasks_resp = await _msgraph_api_get(
                                microsoft_access_token,
                                f"/me/todo/lists/{list_id}/tasks",
                                {"$top": 100, "$filter": "status ne 'completed'"},
                            )
                            for task in tasks_resp.get("value", []):
                                if search_lower in (task.get("title") or "").lower():
                                    matched_list_id = list_id
                                    matched_list_name = tl.get("displayName", "Tasks")
                                    matched_task_id = task.get("id", "")
                                    task_title = task.get("title", task_title)
                                    break
                            if matched_task_id:
                                break
                        if matched_task_id:
                            await _msgraph_api_patch(
                                microsoft_access_token,
                                f"/me/todo/lists/{matched_list_id}/tasks/{matched_task_id}",
                                {"status": "completed"},
                            )
                            reply = f'Done! Marked "{task_title}" as complete in "{matched_list_name}".'
                            microsoft_data = {
                                "type": "task_completed",
                                "list_name": matched_list_name,
                                "task": task_title,
                            }
                        else:
                            reply = f'I couldn\'t find a task matching "{task_title}" in your To Do lists.'
                    else:
                        reply = "Which task would you like to mark as complete?"
                elif action == "delete_todo_task":
                    task_title = (extracted.get("task_title") or "").strip()
                    if task_title:
                        lists_resp = await _msgraph_api_get(
                            microsoft_access_token, "/me/todo/lists", {}
                        )
                        todo_lists = lists_resp.get("value", [])
                        matched_list_id = None
                        matched_list_name = None
                        matched_task_id = None
                        search_lower = task_title.lower()
                        for tl in todo_lists:
                            list_id = tl.get("id", "")
                            tasks_resp = await _msgraph_api_get(
                                microsoft_access_token,
                                f"/me/todo/lists/{list_id}/tasks",
                                {"$top": 100},
                            )
                            for task in tasks_resp.get("value", []):
                                if search_lower in (task.get("title") or "").lower():
                                    matched_list_id = list_id
                                    matched_list_name = tl.get("displayName", "Tasks")
                                    matched_task_id = task.get("id", "")
                                    task_title = task.get("title", task_title)
                                    break
                            if matched_task_id:
                                break
                        if matched_task_id:
                            await _msgraph_api_delete(
                                microsoft_access_token,
                                f"/me/todo/lists/{matched_list_id}/tasks/{matched_task_id}",
                            )
                            reply = f'Done! Deleted "{task_title}" from "{matched_list_name}".'
                            microsoft_data = {
                                "type": "task_deleted",
                                "list_name": matched_list_name,
                                "task": task_title,
                            }
                        else:
                            reply = f'I couldn\'t find a task matching "{task_title}" in your To Do lists.'
                    else:
                        reply = "Which task would you like to delete?"
                elif action == "send_email" and complete:
                    to_addr = (extracted.get("to") or "").strip()
                    subject = (extracted.get("subject") or "").strip()
                    email_body = (extracted.get("body") or "").strip()
                    if to_addr and subject and email_body:
                        await _msgraph_api_post(
                            microsoft_access_token,
                            "/me/sendMail",
                            {
                                "message": {
                                    "subject": subject,
                                    "body": {
                                        "contentType": "Text",
                                        "content": email_body,
                                    },
                                    "toRecipients": [
                                        {"emailAddress": {"address": to_addr}}
                                    ],
                                },
                                "saveToSentItems": True,
                            },
                        )
                        microsoft_data = {
                            "type": "sent",
                            "to": to_addr,
                            "subject": subject,
                        }
            except Exception as _ms_exc:
                microsoft_data = {"type": "error", "message": str(_ms_exc)[:200]}

        return self.render_as_json(
            {
                "reply": reply,
                "extracted": extracted,
                "complete": complete,
                "detected_agent_type": detected_agent_type,
                "search_sources": search_sources,
                "choices": choices,
                "auth_required": auth_required,
                "github_data": github_data,
                "microsoft_data": microsoft_data,
            }
        )

    async def _call_ollama(self, host: str, model: str, messages: list) -> str:
        client = AsyncHTTPClient()
        req = HTTPRequest(
            url=f"{host}/api/chat",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(
                {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "keep_alive": "10m",  # keep model loaded for 10 minutes after last request
                }
            ),
            connect_timeout=15.0,
            request_timeout=480.0,
        )
        resp = await client.fetch(req, raise_error=False)
        if resp.code != 200:
            msg = resp.body.decode("utf-8", errors="replace")
            raise ValueError(f"Ollama {resp.code}: {msg}")
        data = json.loads(resp.body)
        return data["message"]["content"].strip()

    @staticmethod
    def _parse_retry_after(body_bytes: bytes, max_wait: float = 10.0) -> float:
        """Return seconds to wait from a 429 body, capped at max_wait. Returns 0 if not parseable."""
        try:
            text = body_bytes.decode("utf-8", errors="replace")
            m = re.search(r"wait\s+(\d+)\s*second", text, re.IGNORECASE)
            if m:
                return min(float(m.group(1)), max_wait)
        except Exception:
            pass
        return 0.0

    async def _call_openai_compat(
        self, base_url: str, model: str, api_key: str, messages: list, temperature=0.2
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        client = AsyncHTTPClient()
        payload = {"model": model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        req = HTTPRequest(
            url=f"{base_url}/chat/completions",
            method="POST",
            headers=headers,
            body=json.dumps(payload),
            request_timeout=120.0,
        )
        for attempt in range(3):
            resp = await client.fetch(req, raise_error=False)
            if resp.code == 200:
                break
            if resp.code == 429 and attempt < 2:
                wait = self._parse_retry_after(resp.body)
                if wait > 0:
                    await asyncio.sleep(wait)
                    continue
            try:
                err = json.loads(resp.body)
                msg = err.get("error", {}).get("message") or resp.body.decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                msg = resp.body.decode("utf-8", errors="replace")
            raise ValueError(f"OpenAI {resp.code}: {msg}")
        data = json.loads(resp.body)
        return data["choices"][0]["message"]["content"].strip()

    async def _call_anthropic(self, model: str, api_key: str, messages: list) -> str:
        # Anthropic uses a separate system parameter instead of a system role message
        system_content = ""
        filtered = []
        for m in messages:
            if m.get("role") == "system":
                system_content = m.get("content", "")
            else:
                filtered.append(m)

        # Anthropic requires the conversation to start with a user message
        if not filtered or filtered[0].get("role") != "user":
            raise ValueError("Anthropic requires the first message to have role 'user'")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            # Enable prompt caching so the system prompt is cached across turns.
            # The cache_control block on the system message marks it as cacheable.
            "anthropic-beta": "prompt-caching-2024-07-31",
        }
        body: dict = {
            "model": model,
            "max_tokens": 1024,
            "messages": filtered,
        }
        if system_content:
            # Use the extended content-block format so we can attach cache_control.
            body["system"] = [
                {
                    "type": "text",
                    "text": system_content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        client = AsyncHTTPClient()
        req = HTTPRequest(
            url="https://api.anthropic.com/v1/messages",
            method="POST",
            headers=headers,
            body=json.dumps(body),
            request_timeout=120.0,
        )
        resp = await client.fetch(req, raise_error=False)
        if resp.code != 200:
            try:
                err = json.loads(resp.body)
                msg = err.get("error", {}).get("message") or resp.body.decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                msg = resp.body.decode("utf-8", errors="replace")
            raise ValueError(f"Anthropic {resp.code}: {msg}")
        data = json.loads(resp.body)
        return data["content"][0]["text"].strip()

    # ── Tool-calling helpers for ReAct loop ─────────────────────────────── #

    async def _openai_call_with_tools(
        self, base_url: str, model: str, api_key: str, messages: list, tools: list
    ) -> dict:
        """OpenAI-format tool-calling (also used for GitHub Models / compat providers).
        Returns {"reply", "tool_calls", "assistant_message"}.
        """
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }
        client = AsyncHTTPClient()
        req = HTTPRequest(
            url=f"{base_url}/chat/completions",
            method="POST",
            headers=headers,
            body=json.dumps(payload),
            request_timeout=120.0,
        )
        for attempt in range(3):
            resp = await client.fetch(req, raise_error=False)
            if resp.code == 200:
                break
            if resp.code == 429 and attempt < 2:
                wait = self._parse_retry_after(resp.body)
                if wait > 0:
                    await asyncio.sleep(wait)
                    continue
            try:
                err = json.loads(resp.body)
                msg = err.get("error", {}).get("message") or resp.body.decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                msg = resp.body.decode("utf-8", errors="replace")
            raise ValueError(f"OpenAI {resp.code}: {msg}")
        data = json.loads(resp.body)
        choice_msg = data["choices"][0]["message"]
        text = (choice_msg.get("content") or "").strip()
        raw_tool_calls = choice_msg.get("tool_calls") or []
        if not raw_tool_calls:
            return {"reply": text, "tool_calls": None, "assistant_message": None}
        tool_calls = []
        for tc in raw_tool_calls:
            fn = tc["function"]
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            tool_calls.append({"id": tc["id"], "name": fn["name"], "arguments": args})
        assistant_msg = {
            "role": "assistant",
            "content": text or None,
            "tool_calls": raw_tool_calls,
        }
        return {
            "reply": text or None,
            "tool_calls": tool_calls,
            "assistant_message": assistant_msg,
        }

    @staticmethod
    def _is_tool_schema_echo(text: str) -> bool:
        """Return True if the LLM reply looks like an echoed tool schema rather
        than a real answer.  Some models (e.g. llama3.1:8b via Ollama) emit the
        tool definitions verbatim in content when they decide not to call any tool.
        """
        t = text.strip()
        # Pattern produced by llama3.1:8b: "{function TOOL_NAME Description ..."
        if t.startswith("{function ") or "{function " in t[:80]:
            return True
        # JSON object/array that has tool-schema shape
        if t.startswith(("{", "[")):
            try:
                parsed = json.loads(t)
                if isinstance(parsed, dict) and any(
                    k in parsed for k in ("function", "parameters", "tool_calls")
                ):
                    return True
                if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                    first = parsed[0]
                    if any(k in first for k in ("function", "type", "name")):
                        return True
            except Exception:
                pass
        return False

    async def _ollama_call_with_tools(
        self, host: str, model: str, messages: list, tools: list
    ) -> dict:
        """Ollama /api/chat tool-calling (same OpenAI-style format).
        Returns {"reply", "tool_calls", "assistant_message"}.
        """
        client = AsyncHTTPClient()
        req = HTTPRequest(
            url=f"{host}/api/chat",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(
                {
                    "model": model,
                    "messages": messages,
                    "tools": tools,
                    "stream": False,
                    "keep_alive": "10m",
                }
            ),
            connect_timeout=15.0,
            request_timeout=480.0,
        )
        resp = await client.fetch(req, raise_error=False)
        if resp.code != 200:
            raise ValueError(
                f"Ollama {resp.code}: {resp.body.decode('utf-8', errors='replace')[:200]}"
            )
        data = json.loads(resp.body)
        msg = data.get("message", {})
        text = (msg.get("content") or "").strip()
        raw_tool_calls = msg.get("tool_calls") or []
        if not raw_tool_calls:
            return {"reply": text, "tool_calls": None, "assistant_message": None}
        tool_calls = []
        for i, tc in enumerate(raw_tool_calls):
            fn = tc.get("function") or {}
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            call_id = tc.get("id") or f"ollama_{fn.get('name', 'tool')}_{i}"
            tool_calls.append(
                {"id": call_id, "name": fn.get("name", ""), "arguments": args}
            )
        return {
            "reply": text or None,
            "tool_calls": tool_calls,
            "assistant_message": msg,
        }

    async def _anthropic_call_with_tools(
        self, model: str, api_key: str, messages: list, tools: list
    ) -> dict:
        """Anthropic messages API with tool_use support.
        Returns {"reply", "tool_calls", "assistant_message"}.
        """
        # Convert OpenAI tool schemas to Anthropic format
        anthropic_tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"],
            }
            for t in tools
        ]
        # Extract system message
        system_content = ""
        filtered = []
        for m in messages:
            if m.get("role") == "system":
                system_content = m.get("content", "")
            else:
                filtered.append(m)
        if not filtered or filtered[0].get("role") != "user":
            raise ValueError("Anthropic requires the first message to have role 'user'")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "prompt-caching-2024-07-31",
        }
        body: dict = {
            "model": model,
            "max_tokens": 1024,
            "messages": filtered,
            "tools": anthropic_tools,
            "tool_choice": {"type": "auto"},
        }
        if system_content:
            body["system"] = [
                {
                    "type": "text",
                    "text": system_content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        client = AsyncHTTPClient()
        req = HTTPRequest(
            url="https://api.anthropic.com/v1/messages",
            method="POST",
            headers=headers,
            body=json.dumps(body),
            request_timeout=120.0,
        )
        resp = await client.fetch(req, raise_error=False)
        if resp.code != 200:
            try:
                err = json.loads(resp.body)
                msg = err.get("error", {}).get("message") or resp.body.decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                msg = resp.body.decode("utf-8", errors="replace")
            raise ValueError(f"Anthropic {resp.code}: {msg}")
        data = json.loads(resp.body)
        content_blocks = data.get("content", [])
        text = " ".join(
            b["text"] for b in content_blocks if b.get("type") == "text"
        ).strip()
        tool_use_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]
        if not tool_use_blocks:
            return {"reply": text, "tool_calls": None, "assistant_message": None}
        tool_calls = [
            {"id": b["id"], "name": b["name"], "arguments": b.get("input") or {}}
            for b in tool_use_blocks
        ]
        assistant_msg = {"role": "assistant", "content": content_blocks}
        return {
            "reply": text or None,
            "tool_calls": tool_calls,
            "assistant_message": assistant_msg,
        }

    @staticmethod
    def _validate_reply_contacts(reply: str, messages: list) -> str:
        """Scan the reply for email addresses and remove any that weren't
        present in the tool results.  When hallucinated emails are found and
        real extracted emails exist, append a correction note so the user gets
        accurate information rather than a silently wrong answer.
        """
        import json as _json
        import re as _re

        _email_re = _re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

        # Collect every email that was actually found in tool results
        verified_emails: set = set()
        for m in messages:
            content = m.get("content")
            # Tool result messages have string content (JSON-serialised result)
            if m.get("role") == "tool" and isinstance(content, str):
                try:
                    result = _json.loads(content)
                except Exception:
                    result = {}
                # Top-level all_emails_found (programmatically extracted)
                for e in result.get("all_emails_found") or []:
                    verified_emails.add(e.lower())
                # Per-result emails_found (programmatically extracted per page)
                for r in result.get("results") or []:
                    for e in r.get("emails_found") or []:
                        verified_emails.add(e.lower())
                # For web_crawl results: the email is in the top-level result
                for e in _email_re.findall(result.get("content") or ""):
                    verified_emails.add(e.lower())
                # For brave_answers results: emails extracted from the answer text
                for e in result.get("emails_found") or []:
                    verified_emails.add(e.lower())
                # NOTE: intentionally NOT scanning the full raw JSON string —
                # doing so whitelists every email that appears on ANY crawled
                # page, including general county mailboxes that aren't the
                # answer (e.g. caomailbox@kerncounty.com on info pages).

        if not verified_emails:
            # No tool results had emails — can't validate, return as-is
            return reply

        # Find emails the LLM mentioned in its reply
        reply_emails = _email_re.findall(reply)
        if not reply_emails:
            return reply

        hallucinated = [e for e in reply_emails if e.lower() not in verified_emails]
        if not hallucinated:
            return reply

        # Build a correction: strike out hallucinated emails and append the
        # real extracted ones so the user can see both.
        corrected = reply
        for bad in hallucinated:
            corrected = corrected.replace(bad, f"~~{bad}~~")

        real_list = ", ".join(sorted(verified_emails))
        corrected += (
            f"\n\n⚠ **Correction:** The email(s) marked above were not found in "
            f"the actual page content and may be incorrect. "
            f"Emails verified from tool results: **{real_list}**"
        )
        return corrected

    @staticmethod
    def _trim_messages_to_token_budget(
        messages: list,
        max_chars: int = 18000,
        tools_chars: int = 0,
    ) -> list:
        """Trim accumulated message history so the total request body stays within
        the provider's token limit.

        ``max_chars`` is the estimated total char budget for the whole request
        (≈ 7 000 tokens at 4 chars/token for an 8 000-token cap, leaving slack
        for JSON framing and system prompt).  ``tools_chars`` is the serialised
        length of the tool-schema list that will be sent alongside the messages
        and must be subtracted from the budget.

        Strategy (applied in order until budget is met):
          1. Hard-cap ALL tool-result messages to 800 chars — large JSON blobs
             from web-scraper results are the primary cause of 413 errors.
          2. Truncate the ``content`` of tool-result messages in older rounds
             further (newest two kept at 800; older ones shrunk more).
          3. Drop entire old rounds (assistant tool-call + tool result messages)
             while always keeping the system prompt and the latest user message.
        """
        # Effective budget for messages after reserving space for tool schemas
        budget = max(max_chars - tools_chars, 4000)

        # Hard cap per tool-result message — keeps each email_web_scraper blob
        # from consuming the entire budget on its own.
        _TOOL_RESULT_HARD_CAP = 800

        def _total(msgs: list) -> int:
            total = 0
            for m in msgs:
                c = m.get("content")
                if isinstance(c, str):
                    total += len(c)
                elif isinstance(c, list):
                    for block in c:
                        if isinstance(block, dict):
                            total += len(
                                str(block.get("content") or block.get("text") or "")
                            )
                tc = m.get("tool_calls")
                if tc:
                    total += len(json.dumps(tc))
            return total

        # Work on a shallow copy so callers aren't surprised
        messages = list(messages)

        # ── Step 1: hard-cap ALL tool-result messages ───────────────────── #
        for idx, m in enumerate(messages):
            if m.get("role") != "tool":
                continue
            content = m.get("content", "")
            if isinstance(content, str) and len(content) > _TOOL_RESULT_HARD_CAP:
                messages[idx] = {
                    **m,
                    "content": content[:_TOOL_RESULT_HARD_CAP] + " …[truncated]",
                }

        if _total(messages) <= budget:
            return messages

        # ── Step 2: drop whole old ReAct rounds (assistant tool-call + results) ─ #
        while _total(messages) > budget:
            # Find the oldest assistant message that carries tool_calls
            drop_idx = None
            for i, m in enumerate(messages):
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    drop_idx = i
                    break
            if drop_idx is None:
                break
            # Drop that message plus all consecutive tool messages that follow it
            end_idx = drop_idx + 1
            while end_idx < len(messages) and messages[end_idx].get("role") == "tool":
                end_idx += 1
            messages = messages[:drop_idx] + messages[end_idx:]

        if _total(messages) <= budget:
            return messages

        # ── Step 3: drop old conversation-history user/assistant pairs ──────── #
        # History pairs appear AFTER the system prompt and BEFORE the current
        # user goal.  Find the oldest adjacent user+assistant (or user-only)
        # pair that is NOT the system prompt and NOT the last user message,
        # and drop it.
        while _total(messages) > budget and len(messages) > 3:
            # System prompt is always messages[0]; last user message must be kept.
            # Find the first non-system, non-tool, non-tool_calls message to drop.
            drop_idx = None
            for i, m in enumerate(messages):
                if i == 0:
                    continue  # keep system prompt
                if m.get("role") in ("user", "assistant") and not m.get("tool_calls"):
                    drop_idx = i
                    break
            if drop_idx is None:
                break
            # Drop it (and the immediately following assistant reply if present)
            end_idx = drop_idx + 1
            if (
                end_idx < len(messages)
                and messages[end_idx].get("role") == "assistant"
                and not messages[end_idx].get("tool_calls")
            ):
                end_idx += 1
            messages = messages[:drop_idx] + messages[end_idx:]

        return messages

    async def _llm_call_with_tools(
        self,
        provider: str,
        model: str,
        api_key: str,
        ollama_host: str,
        base_url: str,
        messages: list,
        tools: list,
    ) -> dict:
        """Dispatcher for tool-calling LLM calls across all supported providers.
        Returns {"reply", "tool_calls", "assistant_message"}.
        """
        # Compute tool schema size so the trim function can reserve that space
        _tools_chars = len(json.dumps(tools)) if tools else 0
        messages = self._trim_messages_to_token_budget(
            messages, tools_chars=_tools_chars
        )
        if provider == "anthropic":
            return await self._anthropic_call_with_tools(
                model, api_key, messages, tools
            )
        elif provider == "ollama":
            return await self._ollama_call_with_tools(
                ollama_host, model, messages, tools
            )
        elif provider == "openai":
            return await self._openai_call_with_tools(
                "https://api.openai.com/v1", model, api_key, messages, tools
            )
        elif provider == "github_models":
            return await self._openai_call_with_tools(
                self._GITHUB_MODELS_BASE_URL, model, api_key, messages, tools
            )
        elif provider == "openai_compat":
            return await self._openai_call_with_tools(
                base_url, model, api_key, messages, tools
            )
        else:
            raise ValueError(f"unknown provider '{provider}'")

    async def _llm_call(
        self,
        provider: str,
        model: str,
        api_key: str,
        ollama_host: str,
        base_url: str,
        messages: list,
    ) -> str:
        """Single convenience dispatcher for all LLM providers."""
        if provider == "ollama":
            return await self._call_ollama(ollama_host, model, messages)
        elif provider == "openai":
            return await self._call_openai_compat(
                "https://api.openai.com/v1", model, api_key, messages
            )
        elif provider == "anthropic":
            return await self._call_anthropic(model, api_key, messages)
        elif provider == "github_models":
            return await self._call_openai_compat(
                self._GITHUB_MODELS_BASE_URL, model, api_key, messages, temperature=None
            )
        elif provider == "openai_compat":
            return await self._call_openai_compat(base_url, model, api_key, messages)
        else:
            raise ValueError(f"unknown provider '{provider}'")

    @staticmethod
    def _build_loop_system_prompt(
        available_skills: dict,
        key_rotation_triggers: set,
    ) -> str:
        """Build the system prompt for the ReAct agent loop.

        Sections are assembled as a list and joined with double newlines so
        each logical rule is independently readable and easy to edit.
        """
        sections = []

        # ── Connected-tool preamble (dynamic per session) ──────────────── #
        direct_tool_rules = []
        if "sia_storage" in available_skills:
            direct_tool_rules.append(
                "SIA STORAGE — you have a LIVE connection to the user's Sia "
                "decentralized storage account.\n"
                "  • upload/store/save content  → sia_storage__upload (pass content as a string)\n"
                "  • download/retrieve/read     → sia_storage__download (pass object_id)\n"
                "  • list/show files            → sia_storage__list_objects\n"
                "  • share a file               → sia_storage__share (pass object_id)\n"
                "  • delete a file              → sia_storage__delete (pass object_id)\n"
                "NEVER use web_fetch or brave_search for Sia storage operations. "
                "NEVER claim you cannot perform storage actions — the tools are connected and ready."
            )

        if direct_tool_rules:
            sections.append(
                "CRITICAL — DIRECTLY CONNECTED TOOLS "
                "(call these directly; no web lookup needed):\n"
                + "\n".join(f"• {r}" for r in direct_tool_rules)
            )

        # ── Role ──────────────────────────────────────────────────────── #
        sections.append(
            "You are a helpful assistant with access to tools. "
            "Use the tools to accomplish the user's goal."
        )

        # ── Mandatory tool-first rule ──────────────────────────────────── #
        sections.append(
            "MANDATORY: For ANY question about facts, contact details, current "
            "information, web content, emails, phone numbers, addresses, or "
            "anything you cannot answer with absolute certainty from the current "
            "conversation alone — you MUST call a tool first. "
            "NEVER answer factual questions from memory or training data."
        )

        # ── Contact information search path ───────────────────────────── #
        sections.append(
            "FOR CONTACT INFORMATION (email, phone, address, hours):\n"
            "• If email_web_scraper is available → call email_web_scraper__find_email "
            "FIRST. It runs search + crawl and returns one evidence-backed email.\n"
            "• If unavailable or returns nothing → chain: "
            "brave_answers → brave_search (fetch_content=true) → web_crawl.\n"
            "• Prefer emails from 'emails_found'/'all_emails_found' fields "
            "(extracted verbatim from page text) over AI-generated summaries."
        )

        # ── Tool-calling discipline ────────────────────────────────────── #
        sections.append(
            "Call tools one at a time. After each result, decide whether to call "
            "another tool or give a final answer.\n"
            "• Task is ONLY to report information → write a clear final answer "
            "once you have enough tool results.\n"
            "• Task also requires an ACTION (send email, create issue, etc.) → "
            "call the action tool immediately after gathering info; do NOT write "
            "a text answer first."
        )

        # ── Anti-loop / stop conditions ────────────────────────────────── #
        sections.append(
            "CRITICAL — DO NOT RE-SEARCH: Once email_web_scraper or brave_search "
            "has returned an email (even if recommended_email is null), that IS "
            "the answer. Do NOT call those tools again for the same entity. "
            "The recommended_email / high-confidence email field is definitive. "
            "Proceed immediately to the next step."
        )
        sections.append(
            "CRITICAL — TOOL UNAVAILABLE: If a required action tool is not in "
            "your tool list, do NOT loop. Report what you found and clearly state "
            "that the required tool is unavailable."
        )

        # ── Anti-hallucination: contact info ──────────────────────────── #
        sections.append(
            "CRITICAL — NEVER HALLUCINATE CONTACT INFO: Email addresses, phone "
            "numbers, and URLs MUST come ONLY from tool results or conversation "
            "history. If a detail was NOT found in a tool result, say 'not found'. "
            "Do NOT guess or construct a plausible-looking address."
        )
        sections.append(
            "CRITICAL — EMAILS FROM TOOL RESULTS ONLY: The 'all_emails_found' and "
            "per-result 'emails_found' fields are programmatically extracted verbatim "
            "from page text. You MUST quote one of those exact strings. "
            "NEVER invent, modify, or guess an email address not in those lists. "
            "If the lists are non-empty, you MUST use one of them as the answer."
        )
        sections.append(
            "CRITICAL — MULTIPLE EMAILS: Prefer the email whose surrounding page "
            "context matches the specific department/function in the user's query. "
            "Generic inboxes (info@, contact@, caomailbox@) should only be used "
            "when no department-specific email was found. "
            "A department-page email (e.g. kernpublicworks.com for code compliance) "
            "outranks a generic county records mailbox (e.g. kerncounty.com/records)."
        )

        # ── End-to-end execution ──────────────────────────────────────── #
        sections.append(
            "CRITICAL — FOLLOW INSTRUCTIONS END-TO-END: When the request includes "
            "BOTH finding information AND performing an action, do BOTH. "
            "Do NOT stop halfway and ask for confirmation. "
            "Side-effecting actions have an automatic confirmation dialog — "
            "you do NOT need to ask permission. Simply proceed with the full task."
        )
        sections.append(
            "CRITICAL — DO NOT EDITORIALIZE: Do NOT add unsolicited commentary "
            "about whether the request is appropriate, likely to succeed, or "
            "whether the recipient can fulfil it. "
            "Draft and execute what the user asked for. "
            "The user is responsible for the content of their own request. "
            "Do NOT end your final reply with a question."
        )

        prompt = "\n\n".join(sections)

        # ── Key rotation policy (conditional) ────────────────────────── #
        if key_rotation_triggers:
            prompt += (
                "\n\nKEY ROTATION POLICY: Before calling any of these tools — "
                + ", ".join(sorted(key_rotation_triggers))
                + " — you MUST first call key_rotation__check_status. "
                "If it returns {spent: true} the current key is already used; "
                "call key_rotation__rotate before proceeding. "
                "If key_rotation__rotate fails, do NOT proceed with the "
                "triggering tool — report the error to the user instead."
            )

        return prompt

    async def _run_agent_loop(
        self,
        body: dict,
        github_access_token,
        microsoft_access_token,
        llm_cfg: dict,
    ):
        """ReAct (Reason+Act) agent loop with SSE streaming.

        The LLM is given the available skills as tools and autonomously decides
        which tools to call, sees their results, and iterates until it produces
        a final answer — no separate planning phase.

        SSE event shapes
        ----------------
        {"type": "status",      "message": str}
        {"type": "plan",        "reasoning": str, "steps": list}
        {"type": "step_start",  "step": int, "skill": str, "action": str, "description": str}
        {"type": "step_result", "step": int, "skill": str, "action": str, "output": dict}
        {"type": "confirm",     "message": str, "destructive_steps": list, "plan": dict}
        {"type": "done",        "reply": str}
        {"type": "error",       "message": str}

        Confirmation gate
        -----------------
        When the LLM requests a side-effecting tool and the client has not yet
        confirmed, the server emits a ``confirm`` event with
        ``plan.resume_messages`` (messages up to that point, including the
        assistant tool-call message) and ``plan.pending_tool_calls`` (the tool
        calls that need confirmation).  The client re-POSTs with
        ``confirmed: true`` and
        ``confirmed_plan: {resume_messages: [...], pending_tool_calls: [...]}``
        to resume execution.
        """
        from .skills import (
            build_available_skills,
            build_tool_schemas,
            execute_skill,
            route_skills,
        )

        # ── SSE helpers ───────────────────────────────────────────────────── #
        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("X-Accel-Buffering", "no")

        async def sse(data: dict):
            self.write(f"data: {json.dumps(data)}\n\n")
            await self.flush()

        # ── Resolve goal ──────────────────────────────────────────────────── #
        goal = (body.get("goal") or "").strip()
        conversation_history = [
            m
            for m in (body.get("messages") or [])
            if m.get("role") in ("user", "assistant")
            and (m.get("content") or "").strip()
        ]
        if not goal:
            for m in reversed(conversation_history):
                if m.get("role") == "user":
                    goal = (m.get("content") or "").strip()
                    break
        if not goal:
            await sse(
                {
                    "type": "error",
                    "message": "Provide a 'goal' or at least one user message.",
                }
            )
            return self.finish()

        # Strip the last user message from history if it matches the goal —
        # it will be appended explicitly below, so we don't want it twice.
        if (
            conversation_history
            and conversation_history[-1].get("role") == "user"
            and conversation_history[-1].get("content", "").strip() == goal
        ):
            conversation_history = conversation_history[:-1]

        # If the immediately preceding assistant turn said "not found" or was
        # a dead-end answer (no tool calls were made that turn), drop it so the
        # agent re-searches rather than just agreeing with itself.
        _NOT_FOUND_PHRASES = (
            "not found",
            "no email",
            "unable to find",
            "could not find",
            "i couldn't find",
            "i was unable",
            "no public email",
            "i don't have",
            "i do not have",
        )
        if conversation_history and conversation_history[-1].get("role") == "assistant":
            _last_reply = conversation_history[-1].get("content", "").lower()
            if any(p in _last_reply for p in _NOT_FOUND_PHRASES):
                conversation_history = conversation_history[:-1]

        # Cap conversation history to the 3 most recent turns (6 messages) so
        # old exchanges don't consume the LLM's token budget.
        conversation_history = conversation_history[-6:]

        # ── LLM config ────────────────────────────────────────────────────── #
        provider = (llm_cfg.get("provider") or "ollama").lower().strip()
        # ollama_browser: LLM call happens in the browser (user's local Ollama);
        # the server emits a "llm_needed" SSE event and waits for the browser to
        # re-POST with the result.  For all other processing, treat it like ollama.
        browser_llm = provider == "ollama_browser"
        model = (llm_cfg.get("model") or "").strip() or self._DEFAULT_MODELS.get(
            "ollama" if browser_llm else provider, "gpt-4o-mini"
        )
        api_key = (llm_cfg.get("api_key") or "").strip()
        ollama_host = (
            llm_cfg.get("ollama_host")
            or getattr(self.config, "ollama_host", None)
            or "http://127.0.0.1:11434"
        ).rstrip("/")
        base_url = (llm_cfg.get("base_url") or "").rstrip("/")

        # ── Build skill context ───────────────────────────────────────────── #
        brave_api_key = (
            (body.get("brave_api_key") or "").strip()
            or os.environ.get("BRAVE_API_KEY", "")
            or getattr(self.config, "brave_api_key", "")
            or ""
        )
        brave_answers_api_key = (
            (body.get("brave_answers_api_key") or "").strip()
            or os.environ.get("BRAVE_ANSWERS_API_KEY", "")
            or getattr(self.config, "brave_answers_api_key", "")
            or ""
        )
        public_key = (body.get("public_key") or "").strip()
        # second_factor is kept server-side and never surfaced as an LLM tool argument
        key_rotation_second_factor = (
            body.get("key_rotation_second_factor") or ""
        ).strip()
        sia_app_key = (body.get("sia_app_key") or "").strip()
        skill_context = {
            "config": self.config,
            "github_access_token": github_access_token,
            "microsoft_access_token": microsoft_access_token,
            "brave_api_key": brave_api_key,
            "brave_answers_api_key": brave_answers_api_key,
            "public_key": public_key,
            "key_rotation_second_factor": key_rotation_second_factor,
            "sia_app_key": sia_app_key,
            "llm_call": lambda msgs, max_tokens=800: self._llm_call(
                provider, model, api_key, ollama_host, base_url, msgs
            ),
        }
        available_skills = build_available_skills(skill_context)
        # Route to the most relevant skill subset — reduces wrong tool selection
        # (e.g. prevents brave_search firing for a Sia upload request).
        routed_skills = route_skills(goal, available_skills)

        # ── Warn about expired sessions ───────────────────────────────────── #
        _web2 = body.get("web2_sessions") or {}
        _ms_sessions = _web2.get("microsoft") or []
        if _ms_sessions and not microsoft_access_token:
            await sse(
                {
                    "type": "warning",
                    "message": (
                        "⚠ Microsoft session expired — please disconnect and reconnect "
                        "your Outlook account, then try again."
                    ),
                }
            )
        _gh_nonce = _web2.get("github") or ""
        if _gh_nonce and not github_access_token:
            await sse(
                {
                    "type": "warning",
                    "message": (
                        "⚠ GitHub session expired — please disconnect and reconnect "
                        "your GitHub account, then try again."
                    ),
                }
            )

        if not available_skills:
            await sse(
                {
                    "type": "error",
                    "message": (
                        "No skills are available. Connect GitHub or Microsoft, "
                        "or provide a Brave API key."
                    ),
                }
            )
            return self.finish()

        tools = build_tool_schemas(routed_skills)

        # ── Key-rotation trigger set ───────────────────────────────────────── #
        # Collect tools that should be gated behind a key-rotation check.
        # Sources (merged):
        #   1. SKILL_REGISTRY action flag  triggers_key_rotation: True
        #   2. body["key_rotation_triggers"] list of "skill__action" strings
        key_rotation_triggers: set = set()
        if "key_rotation" in available_skills:
            for _s_name, _s_def in routed_skills.items():
                for _a_name, _a_def in _s_def["actions"].items():
                    if _a_def.get("triggers_key_rotation"):
                        key_rotation_triggers.add(f"{_s_name}__{_a_name}")
            for _t in body.get("key_rotation_triggers") or []:
                key_rotation_triggers.add(str(_t))

        # ── System prompt ─────────────────────────────────────────────────── #
        system_prompt = self._build_loop_system_prompt(
            routed_skills, key_rotation_triggers
        )

        # ── Build initial messages (or resume from confirmation) ──────────── #
        confirmed_plan = body.get("confirmed_plan")
        resume_messages = None
        pending_tool_calls = None
        if (
            confirmed_plan
            and isinstance(confirmed_plan, dict)
            and isinstance(confirmed_plan.get("resume_messages"), list)
        ):
            resume_messages = confirmed_plan["resume_messages"]
            pending_tool_calls = confirmed_plan.get("pending_tool_calls") or []

        # For ollama_browser: resume_messages sent directly in body (after llm_needed)
        if resume_messages is None and isinstance(body.get("resume_messages"), list):
            resume_messages = body["resume_messages"]

        if resume_messages is not None:
            messages = resume_messages
        else:
            messages = [{"role": "system", "content": system_prompt}]
            for m in conversation_history:
                messages.append({"role": m["role"], "content": m["content"].strip()})
            messages.append({"role": "user", "content": goal})
            messages = _sanitize_messages(messages)

        await sse({"type": "status", "message": "Thinking..."})

        # ── ReAct loop ────────────────────────────────────────────────────── #
        MAX_ROUNDS = 10
        step_counter = 0
        _plan_emitted = resume_messages is not None  # don't re-emit plan on resume

        # For ollama_browser provider: on the very first call the browser may
        # have already supplied the LLM response so we don't need to emit
        # llm_needed before doing any work.
        _browser_llm_response = body.get("llm_response") or None

        _pre_run_step_count = 0  # tracks steps added before the ReAct loop

        # ── Auto-run brave_answers before the ReAct loop ──────────────────── #
        # Ensures brave_answers always appears as a distinct visible step in the
        # UI and its result is available to the LLM before it calls brave_search.
        # Skip when the goal is clearly a local/tool action that doesn't benefit
        # from a web search (Sia storage, wallet operations, key rotation, etc.).
        _SKIP_BA_PREFLIGHT_SKILLS = {"sia_storage", "wallet", "key_rotation"}
        _skip_ba_preflight = bool(
            _SKIP_BA_PREFLIGHT_SKILLS & set(routed_skills.keys())
            and any(
                kw in goal.lower()
                for kw in (
                    "upload",
                    "download",
                    "store",
                    "save",
                    "list files",
                    "list objects",
                    "delete file",
                    "delete object",
                    "share file",
                    "share object",
                    "sia",
                    "wallet",
                    "balance",
                    "rotate",
                    "key rotation",
                )
            )
        )
        if (
            resume_messages is None
            and not browser_llm
            and "brave_answers" in routed_skills
            and brave_answers_api_key
            and not _skip_ba_preflight
        ):
            _ba_pre_args = {"query": goal}
            _ba_pre_id = "auto_brave_answers_0"
            step_counter += 1
            await sse(
                {
                    "type": "step_start",
                    "step": step_counter,
                    "skill": "brave_answers",
                    "action": "answer",
                    "description": json.dumps(_ba_pre_args)[:200],
                }
            )
            await sse({"type": "status", "message": "Running brave_answers/answer..."})
            try:
                _ba_pre_result = await execute_skill(
                    "brave_answers", "answer", _ba_pre_args, skill_context
                )
            except Exception as _bap_exc:
                _ba_pre_result = {"ok": False, "error": str(_bap_exc)[:200]}
            await sse(
                {
                    "type": "step_result",
                    "step": step_counter,
                    "skill": "brave_answers",
                    "action": "answer",
                    "output": _ba_pre_result,
                }
            )
            _pre_run_step_count = step_counter  # remember offset for plan numbering
            if provider == "anthropic":
                messages.append(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": _ba_pre_id,
                                "name": "brave_answers__answer",
                                "input": _ba_pre_args,
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": _ba_pre_id,
                                "content": json.dumps(_ba_pre_result, default=str)[
                                    :3000
                                ],
                            }
                        ],
                    }
                )
            else:
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": _ba_pre_id,
                                "type": "function",
                                "function": {
                                    "name": "brave_answers__answer",
                                    "arguments": json.dumps(_ba_pre_args),
                                },
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": _ba_pre_id,
                        "content": json.dumps(_ba_pre_result, default=str)[:3000],
                    }
                )

        for round_num in range(MAX_ROUNDS):
            if pending_tool_calls:
                # Resuming after user confirmed a side-effecting action
                tc_list = pending_tool_calls
                pending_tool_calls = None
            else:
                # ── Obtain LLM decision ──────────────────────────────────── #
                if browser_llm:
                    if _browser_llm_response:
                        # Browser already called Ollama and sent us the result
                        llm_result = _browser_llm_response
                        _browser_llm_response = None  # consume it
                    else:
                        # Ask the browser to call Ollama and re-POST the result
                        await sse(
                            {"type": "llm_needed", "messages": messages, "tools": tools}
                        )
                        return self.finish()
                else:
                    try:
                        llm_result = await self._llm_call_with_tools(
                            provider,
                            model,
                            api_key,
                            ollama_host,
                            base_url,
                            messages,
                            tools,
                        )
                    except Exception as exc:
                        await sse(
                            {"type": "error", "message": f"LLM call failed: {exc}"}
                        )
                        return self.finish()

                reply = llm_result.get("reply")
                tc_list = llm_result.get("tool_calls") or []
                raw_assistant_msg = llm_result.get("assistant_message")

                if not tc_list:
                    # LLM gave a final answer — we're done.
                    # Some models (e.g. llama3.1:8b) echo tool schemas as content
                    # when they choose not to call any tool.  Detect this and
                    # retry once without tools to get a real conversational reply.
                    if reply and self._is_tool_schema_echo(reply):
                        reply = None
                        if browser_llm:
                            # Ask the browser to call Ollama again, this time without tools
                            await sse(
                                {
                                    "type": "llm_needed",
                                    "messages": messages,
                                    "tools": [],
                                }
                            )
                            return self.finish()
                        else:
                            try:
                                fallback = await self._llm_call_with_tools(
                                    provider,
                                    model,
                                    api_key,
                                    ollama_host,
                                    base_url,
                                    messages,
                                    [],
                                )
                                reply = fallback.get("reply")
                            except Exception:
                                pass
                    reply = self._validate_reply_contacts(
                        reply or "(no reply)", messages
                    )
                    await sse({"type": "done", "reply": reply})
                    return self.finish()

                # Append the assistant message (containing tool calls) to history
                if raw_assistant_msg:
                    messages.append(raw_assistant_msg)

                # Emit a plan event on the first round to show what will happen
                if not _plan_emitted:
                    _plan_emitted = True
                    # Pre-run steps (e.g. brave_answers) already executed before
                    # the loop — include them in the plan so the UI numbers match.
                    plan_steps = []
                    if _pre_run_step_count > 0:
                        plan_steps.append(
                            {
                                "step": 1,
                                "skill": "brave_answers",
                                "action": "answer",
                                "description": json.dumps({"query": goal})[:120],
                            }
                        )
                    for i, tc in enumerate(tc_list):
                        plan_steps.append(
                            {
                                "step": _pre_run_step_count + i + 1,
                                "skill": (
                                    tc["name"].split("__")[0]
                                    if "__" in tc["name"]
                                    else tc["name"]
                                ),
                                "action": (
                                    tc["name"].split("__", 1)[1]
                                    if "__" in tc["name"]
                                    else ""
                                ),
                                "description": json.dumps(tc.get("arguments") or {})[
                                    :120
                                ],
                            }
                        )
                    await sse(
                        {
                            "type": "plan",
                            "reasoning": reply
                            or "Calling tools to answer your question.",
                            "steps": plan_steps,
                        }
                    )

            # ── Execute each tool call ─────────────────────────────────── #
            tool_results_for_msg: list = []
            for tc in tc_list:
                tc_id = tc.get("id") or f"call_{step_counter}"
                raw_name = tc.get("name") or ""
                args = tc.get("arguments") or {}

                if "__" in raw_name:
                    skill_name, action_name = raw_name.split("__", 1)
                else:
                    skill_name = raw_name
                    action_name = ""

                action_def = (
                    available_skills.get(skill_name, {})
                    .get("actions", {})
                    .get(action_name, {})
                )
                is_side_effecting = bool(action_def.get("side_effects"))

                # ── Confirmation gate ───────────────────────────────────── #
                needs_second_factor = bool(
                    raw_name == "key_rotation__rotate"
                    and not skill_context.get("key_rotation_second_factor")
                )
                if is_side_effecting and not body.get("confirmed"):
                    await sse(
                        {
                            "type": "confirm",
                            "message": (
                                "The assistant wants to perform the following "
                                "real-world action. Please review and confirm to proceed."
                            ),
                            "needs_second_factor": needs_second_factor,
                            "destructive_steps": [
                                {
                                    "step": step_counter + 1,
                                    "skill": skill_name,
                                    "action": action_name,
                                    "description": json.dumps(args)[:200],
                                    "params": args,
                                }
                            ],
                            "plan": {
                                "resume_messages": messages,
                                "pending_tool_calls": [tc],
                            },
                        }
                    )
                    return self.finish()

                step_counter += 1
                await sse(
                    {
                        "type": "step_start",
                        "step": step_counter,
                        "skill": skill_name,
                        "action": action_name,
                        "description": json.dumps(args)[:200],
                    }
                )
                await sse(
                    {
                        "type": "status",
                        "message": f"Running {skill_name}/{action_name}...",
                    }
                )

                try:
                    result = await execute_skill(
                        skill_name, action_name, args, skill_context
                    )
                except Exception as exc:
                    result = {"ok": False, "error": str(exc)[:200]}

                await sse(
                    {
                        "type": "step_result",
                        "step": step_counter,
                        "skill": skill_name,
                        "action": action_name,
                        "output": result,
                    }
                )
                tool_results_for_msg.append(
                    {
                        "tool_call_id": tc_id,
                        "content": json.dumps(result, default=str)[:3000],
                    }
                )

            # ── Append tool results to messages (provider-specific) ──────── #
            if tool_results_for_msg:
                if provider == "anthropic":
                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": r["tool_call_id"],
                                    "content": r["content"],
                                }
                                for r in tool_results_for_msg
                            ],
                        }
                    )
                else:
                    # OpenAI / Ollama: one "tool" role message per tool call
                    for r in tool_results_for_msg:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": r["tool_call_id"],
                                "content": r["content"],
                            }
                        )

            # ── De-dup guard: if LLM re-called the same email-lookup skill ─── #
            # If the LLM has now called email_web_scraper or brave_search twice or
            # more during this session, inject a nudge so it stops re-searching
            # and proceeds to the action tool (e.g. send_email).
            if tool_results_for_msg and not browser_llm:
                _email_lookup_skills = {
                    "email_web_scraper__find_email",
                    "brave_search__search",
                }
                _last_tc_name = (tc_list[-1].get("name") or "") if tc_list else ""
                if _last_tc_name in _email_lookup_skills:
                    _lookup_calls = 0
                    for _m in messages:
                        if _m.get("role") != "assistant":
                            continue
                        # OpenAI/Ollama style
                        for _tc in _m.get("tool_calls") or []:
                            _fn = (
                                _tc.get("function", {}).get("name")
                                or _tc.get("name")
                                or ""
                            )
                            if _fn in _email_lookup_skills:
                                _lookup_calls += 1
                        # Anthropic style
                        for _c in _m.get("content") or []:
                            if isinstance(_c, dict) and _c.get("type") == "tool_use":
                                if _c.get("name") in _email_lookup_skills:
                                    _lookup_calls += 1
                    if _lookup_calls >= 1:
                        _nudge = (
                            "[SYSTEM NOTE] The email address has already been found in the "
                            "previous tool result. Do NOT call email_web_scraper or "
                            "brave_search again. Use the email from the result above and "
                            "immediately call the next required action tool "
                            "(e.g. microsoft__send_email to send the email). "
                            "If that tool is not in your tool list, stop and report what "
                            "you found — do NOT keep searching."
                        )
                        messages.append({"role": "user", "content": _nudge})

            # ── Auto-crawl after brave_search when emails conflict ─────────── #
            # If brave_search returned multiple candidate emails, automatically
            # run web_crawl on the most query-relevant URL so the LLM has direct
            # page evidence for picking the correct one.
            if "web_crawl" in available_skills and not browser_llm:
                for _auto_tc in tc_list:
                    if _auto_tc.get("name") != "brave_search__search":
                        continue
                    # Find the matching tool result
                    _auto_bs = None
                    for _auto_r in tool_results_for_msg:
                        if _auto_r.get("tool_call_id") == _auto_tc.get("id"):
                            try:
                                _auto_bs = json.loads(_auto_r["content"])
                            except Exception:
                                pass
                            break
                    if not _auto_bs:
                        break
                    _auto_emails = _auto_bs.get("all_emails_found") or []
                    if len(set(_auto_emails)) < 2:
                        break  # Only one email candidate — no conflict to resolve
                    # Score each result URL by keyword overlap with the query
                    import re as _re_rank

                    _auto_query = _auto_bs.get("query") or goal
                    _auto_qwords = set(
                        _re_rank.sub(r"[^a-z0-9 ]", "", _auto_query.lower()).split()
                    ) - {
                        "a",
                        "an",
                        "the",
                        "and",
                        "or",
                        "for",
                        "in",
                        "of",
                        "to",
                        "email",
                        "address",
                        "contact",
                        "phone",
                        "number",
                    }

                    def _auto_score(r):
                        _u = r.get("url", "").lower()
                        s = sum(1 for w in _auto_qwords if w in _u)
                        if r.get("emails_found"):
                            s += 3
                        return s

                    _auto_sorted = sorted(
                        (
                            r
                            for r in (_auto_bs.get("results") or [])
                            if r.get("url", "").startswith("http")
                        ),
                        key=_auto_score,
                        reverse=True,
                    )
                    _auto_best_url = _auto_sorted[0]["url"] if _auto_sorted else None
                    if not _auto_best_url:
                        break
                    _auto_wc_id = f"auto_web_crawl_{step_counter + 1}"
                    step_counter += 1
                    _auto_wc_args = {"url": _auto_best_url}
                    await sse(
                        {
                            "type": "step_start",
                            "step": step_counter,
                            "skill": "web_crawl",
                            "action": "fetch",
                            "description": json.dumps(_auto_wc_args)[:200],
                        }
                    )
                    await sse(
                        {
                            "type": "status",
                            "message": "Verifying page with web_crawl...",
                        }
                    )
                    try:
                        _auto_wc_result = await execute_skill(
                            "web_crawl", "fetch", _auto_wc_args, skill_context
                        )
                    except Exception as _auto_wce:
                        _auto_wc_result = {"ok": False, "error": str(_auto_wce)[:200]}
                    await sse(
                        {
                            "type": "step_result",
                            "step": step_counter,
                            "skill": "web_crawl",
                            "action": "fetch",
                            "output": _auto_wc_result,
                        }
                    )
                    if provider == "anthropic":
                        messages.append(
                            {
                                "role": "assistant",
                                "content": [
                                    {
                                        "type": "tool_use",
                                        "id": _auto_wc_id,
                                        "name": "web_crawl__fetch",
                                        "input": _auto_wc_args,
                                    }
                                ],
                            }
                        )
                        messages.append(
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": _auto_wc_id,
                                        "content": json.dumps(
                                            _auto_wc_result, default=str
                                        )[:3000],
                                    }
                                ],
                            }
                        )
                    else:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": _auto_wc_id,
                                        "type": "function",
                                        "function": {
                                            "name": "web_crawl__fetch",
                                            "arguments": json.dumps(_auto_wc_args),
                                        },
                                    }
                                ],
                            }
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": _auto_wc_id,
                                "content": json.dumps(_auto_wc_result, default=str)[
                                    :3000
                                ],
                            }
                        )
                    break  # Only crawl once per brave_search call

            if browser_llm:
                # Browser needs to call Ollama with the updated messages.
                # Emit llm_needed and end this SSE connection; the browser will
                # re-POST with llm_response + resume_messages to continue.
                await sse({"type": "llm_needed", "messages": messages, "tools": tools})
                return self.finish()

            await sse({"type": "status", "message": "Thinking..."})

        # ── Max rounds exceeded ───────────────────────────────────────────── #
        await sse(
            {
                "type": "done",
                "reply": "I was unable to complete the task within the allowed number of steps.",
            }
        )
        self.finish()

    # ── Tool-calling loops ──────────────────────────────────────────────────── #

    async def _ollama_tool_loop(
        self,
        host: str,
        model: str,
        messages: list,
        tools: list,
        tool_impl: dict,
        confirm_tool: str,
        scope: dict,
        max_rounds: int = 8,
    ):
        """Ollama /api/chat tool-calling loop. Returns (reply, confirmation|None, confirm_result|None)."""
        client = AsyncHTTPClient()
        confirmation = None
        confirm_result = None
        for _ in range(max_rounds):
            req = HTTPRequest(
                url=f"{host}/api/chat",
                method="POST",
                headers={"Content-Type": "application/json"},
                body=json.dumps(
                    {
                        "model": model,
                        "messages": messages,
                        "tools": tools,
                        "stream": False,
                    }
                ),
                request_timeout=480.0,
            )
            resp = await client.fetch(req, raise_error=False)
            if resp.code != 200:
                raise ValueError(
                    f"Ollama {resp.code}: {resp.body.decode('utf-8', errors='replace')[:200]}"
                )
            data = json.loads(resp.body)
            msg = data.get("message", {})
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                return msg.get("content", ""), confirmation, confirm_result
            messages.append(msg)
            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                args = tc["function"].get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                fn = tool_impl.get(fn_name)
                if fn is None:
                    result = {"error": f"unknown tool: {fn_name}"}
                elif inspect.iscoroutinefunction(fn):
                    result = await fn(args, scope)
                else:
                    result = fn(args, scope)
                if fn_name == confirm_tool and result.get("confirmed"):
                    confirmation = result.get("confirmation")
                    confirm_result = result
                messages.append({"role": "tool", "content": json.dumps(result)})
        return (
            "Unable to complete the booking at this time.",
            confirmation,
            confirm_result,
        )

    async def _openai_tool_loop(
        self,
        base_url: str,
        model: str,
        api_key: str,
        messages: list,
        tools: list,
        tool_impl: dict,
        confirm_tool: str,
        scope: dict,
        max_rounds: int = 8,
        temperature=0.3,
    ):
        """OpenAI-compat /chat/completions tool-calling loop. Returns (reply, confirmation|None, confirm_result|None)."""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        client = AsyncHTTPClient()
        confirmation = None
        confirm_result = None
        for _ in range(max_rounds):
            payload = {
                "model": model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
            }
            if temperature is not None:
                payload["temperature"] = temperature
            req = HTTPRequest(
                url=f"{base_url}/chat/completions",
                method="POST",
                headers=headers,
                body=json.dumps(payload),
                request_timeout=120.0,
            )
            resp = None
            for attempt in range(3):
                resp = await client.fetch(req, raise_error=False)
                if resp.code == 200:
                    break
                if resp.code == 429 and attempt < 2:
                    wait = self._parse_retry_after(resp.body)
                    if wait > 0:
                        await asyncio.sleep(wait)
                        continue
                raise ValueError(
                    f"LLM {resp.code}: {resp.body.decode('utf-8', errors='replace')[:200]}"
                )
            data = json.loads(resp.body)
            choice = data["choices"][0]
            msg = choice["message"]
            finish_reason = choice.get("finish_reason", "stop")
            if finish_reason != "tool_calls" or not msg.get("tool_calls"):
                return msg.get("content") or "", confirmation, confirm_result
            messages.append(msg)
            for tc in msg["tool_calls"]:
                fn_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"].get("arguments", "{}"))
                except Exception:
                    args = {}
                fn = tool_impl.get(fn_name)
                if fn is None:
                    result = {"error": f"unknown tool: {fn_name}"}
                elif inspect.iscoroutinefunction(fn):
                    result = await fn(args, scope)
                else:
                    result = fn(args, scope)
                if fn_name == confirm_tool and result.get("confirmed"):
                    confirmation = result.get("confirmation")
                    confirm_result = result
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result),
                    }
                )
        return (
            "Unable to complete the booking at this time.",
            confirmation,
            confirm_result,
        )

    async def _anthropic_tool_loop(
        self,
        model: str,
        api_key: str,
        messages: list,
        tools: list,
        tool_impl: dict,
        confirm_tool: str,
        scope: dict,
        system_content: str = "",
        max_rounds: int = 8,
    ):
        """Anthropic tool-use loop. Returns (reply, confirmation|None, confirm_result|None)."""
        # Convert OpenAI-format schemas → Anthropic format
        anthropic_tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"],
            }
            for t in tools
        ]
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        # Strip system messages; Anthropic takes system separately
        filtered = [m for m in messages if m.get("role") != "system"]
        confirmation = None
        confirm_result = None
        for _ in range(max_rounds):
            body: dict = {
                "model": model,
                "max_tokens": 1024,
                "tools": anthropic_tools,
                "messages": filtered,
            }
            if system_content:
                body["system"] = system_content
            req = HTTPRequest(
                url="https://api.anthropic.com/v1/messages",
                method="POST",
                headers=headers,
                body=json.dumps(body),
                request_timeout=120.0,
            )
            resp = await AsyncHTTPClient().fetch(req, raise_error=False)
            if resp.code != 200:
                raise ValueError(
                    f"Anthropic {resp.code}: {resp.body.decode('utf-8', errors='replace')[:200]}"
                )
            data = json.loads(resp.body)
            stop_reason = data.get("stop_reason")
            content_blocks = data.get("content", [])
            if stop_reason != "tool_use":
                text = "".join(
                    b.get("text", "") for b in content_blocks if b.get("type") == "text"
                )
                return text.strip(), confirmation, confirm_result
            filtered.append({"role": "assistant", "content": content_blocks})
            tool_results = []
            for block in content_blocks:
                if block.get("type") != "tool_use":
                    continue
                fn_name = block["name"]
                args = block.get("input") or {}
                fn = tool_impl.get(fn_name)
                if fn is None:
                    result = {"error": f"unknown tool: {fn_name}"}
                elif inspect.iscoroutinefunction(fn):
                    result = await fn(args, scope)
                else:
                    result = fn(args, scope)
                if fn_name == confirm_tool and result.get("confirmed"):
                    confirmation = result.get("confirmation")
                    confirm_result = result
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": json.dumps(result),
                    }
                )
            filtered.append({"role": "user", "content": tool_results})
        return (
            "Unable to complete the booking at this time.",
            confirmation,
            confirm_result,
        )

    async def _run_tool_loop(
        self,
        provider: str,
        model: str,
        api_key: str,
        ollama_host: str,
        base_url: str,
        system_prompt: str,
        messages: list,
        vendor_tools: dict,
        scope: dict,
        max_rounds: int = 8,
    ):
        """
        Dispatch to the appropriate provider tool loop.
        Returns (reply: str, confirmation: str|None, confirm_result: dict|None).
        """
        tools = vendor_tools["schemas"]
        confirm_tool = vendor_tools.get("confirm_tool", "")

        # If an MCP endpoint is configured, replace mock impl with live MCP calls.
        mcp_endpoint = vendor_tools.get("mcp_endpoint", "")
        if mcp_endpoint:
            tool_names = [t["function"]["name"] for t in tools]
            tool_impl = MCPClient.make_impl(mcp_endpoint, tool_names, confirm_tool)
        else:
            tool_impl = vendor_tools["impl"]

        full_messages = _sanitize_messages(
            [{"role": "system", "content": system_prompt}] + list(messages)
        )

        if provider == "ollama":
            return await self._ollama_tool_loop(
                ollama_host,
                model,
                full_messages,
                tools,
                tool_impl,
                confirm_tool,
                scope,
                max_rounds,
            )
        elif provider in ("openai", "openai_compat", "github_models"):
            if provider == "openai":
                base = "https://api.openai.com/v1"
            elif provider == "github_models":
                base = self._GITHUB_MODELS_BASE_URL
            else:
                base = base_url
            return await self._openai_tool_loop(
                base,
                model,
                api_key,
                full_messages,
                tools,
                tool_impl,
                confirm_tool,
                scope,
                max_rounds,
                temperature=None if provider == "github_models" else 0.3,
            )
        elif provider == "anthropic":
            filtered = [m for m in full_messages if m.get("role") != "system"]
            return await self._anthropic_tool_loop(
                model,
                api_key,
                filtered,
                tools,
                tool_impl,
                confirm_tool,
                scope,
                system_content=system_prompt,
                max_rounds=max_rounds,
            )
        else:
            raise ValueError(f"unknown provider '{provider}'")


class BookingContextHandler(BaseHandler):
    """GET /contexts/booking/v1 — serve the YadaCoin booking credential JSON-LD context."""

    async def get(self):
        from plugins.yadaaiagent.vc_support import BOOKING_V1_CONTEXT_DOC

        self.set_header("Content-Type", "application/ld+json")
        self.set_header("Access-Control-Allow-Origin", "*")
        return self.finish(json.dumps(BOOKING_V1_CONTEXT_DOC))


class WellKnownDidHandler(BaseHandler):
    """GET /.well-known/did.json — serve the node's DID document (did:web)."""

    async def get(self):
        import base58  # noqa: PLC0415

        did_id = _did_web_id(self.config)
        pub_hex = self.config.public_key
        # publicKeyMultibase: multibase base58btc (prefix 'z') of the compressed pubkey bytes
        pub_bytes = bytes.fromhex(pub_hex)
        pub_multibase = "z" + base58.b58encode(pub_bytes).decode("ascii")
        doc = {
            "@context": [
                "https://www.w3.org/ns/did/v1",
                "https://w3id.org/security/suites/secp256k1-2019/v1",
            ],
            "id": did_id,
            "verificationMethod": [
                {
                    "id": f"{did_id}#key-1",
                    "type": "EcdsaSecp256k1VerificationKey2019",
                    "controller": did_id,
                    "publicKeyMultibase": pub_multibase,
                }
            ],
            "assertionMethod": [f"{did_id}#key-1"],
        }
        self.set_header("Content-Type", "application/did+ld+json")
        self.set_header("Access-Control-Allow-Origin", "*")
        return self.finish(json.dumps(doc))


class AgentAuthAppHandler(BaseHandler):
    """GET /ai-agent-auth[/.*] — serve the Vue SPA shell."""

    # __file__ is backend/agent/handlers.py → go up two levels to plugin root
    _DIST = os.path.join(os.path.dirname(__file__), "..", "..", "dist")

    async def get(self):
        index = os.path.join(self._DIST, "index.html")
        if not os.path.exists(index):
            self.set_status(503)
            return self.finish(
                "<pre>SPA not built yet.\n"
                "Run:  cd plugins/yadaaiagent/ui && npm run build</pre>"
            )
        with open(index, "rb") as fh:
            self.set_header("Content-Type", "text/html; charset=utf-8")
            return self.finish(fh.read())


class AgentChallengeHandler(BaseHandler):
    """
    GET /ai-agent-auth/api/challenge?public_key=<hex>

    Returns a short-lived stateless HMAC-SHA256 challenge tied to the
    supplied public key.  Valid for the current 30-second window plus the
    previous one (up to ~60 s total).  The client must sign
    ``sha256(challenge_utf8_bytes)`` with the provisioned secp256k1 key and
    present the compact signature to the travel booking endpoint.
    """

    async def get(self):
        public_key = (self.get_argument("public_key", "") or "").strip()
        if not public_key:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "public_key query parameter required"}
            )
        return self.render_as_json(_validator.make_challenge(public_key))


# ── Legacy mock inventory for the /api/travel combined endpoint ───────────────
class AgentRegisterHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/agents/register

    Registers an AI agent on the blockchain so it can be discovered by other
    nodes searching for agents that match a given intent.

    The transaction uses the node's identity key (same as NodeAnnouncement).
    The relationship field is stored as {"agent": <AgentAnnouncement.to_dict()>}.

    Body (JSON)
    -----------
    label          : str   — human-readable agent name
    description    : str   — what the agent does
    capabilities   : list  — intent keywords e.g. ["travel", "flight", "hotel"]
    endpoint_url   : str   — base URL where this agent is accessible
    agent_type     : str   — optional, defaults to "general"
    icon           : str   — optional emoji/icon
    version        : str   — optional semver, default "1.0"

    Returns
    -------
    {
        "status": "success",
        "agent_id": "...",
        "transaction_signature": "...",
        "agent": { ...announcement dict... }
    }
    """

    async def post(self):
        from datetime import datetime, timezone

        from yadacoin.core.agentannouncement import AgentAnnouncement
        from yadacoin.core.chain import CHAIN
        from yadacoin.core.transaction import (
            InvalidTransactionException,
            InvalidTransactionSignatureException,
            MissingInputTransactionException,
            Transaction,
        )
        from yadacoin.core.transactionutils import TU

        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid json body"})

        label = (body.get("label") or "").strip()
        description = (body.get("description") or "").strip()
        capabilities = body.get("capabilities") or []
        endpoint_url = (body.get("endpoint_url") or "").strip()
        agent_type = (body.get("agent_type") or "general").strip()
        icon = (body.get("icon") or "🤖").strip()
        version = (body.get("version") or "1.0").strip()

        if not label:
            self.set_status(400)
            return self.render_as_json({"error": "label is required"})
        if not endpoint_url:
            self.set_status(400)
            return self.render_as_json({"error": "endpoint_url is required"})
        if not isinstance(capabilities, list):
            self.set_status(400)
            return self.render_as_json({"error": "capabilities must be a list"})

        # Require node configuration (provides the signing identity)
        if not hasattr(self.config, "peer") or not self.config.peer:
            self.set_status(400)
            return self.render_as_json(
                {
                    "error": "Node not configured. Agent registration requires a running node identity."
                }
            )
        peer = self.config.peer
        if not peer.identity:
            self.set_status(400)
            return self.render_as_json({"error": "Node identity not configured."})

        current_height = self.config.LatestBlock.block.index
        if current_height < CHAIN.AGENT_REGISTRY_FORK:
            self.set_status(400)
            return self.render_as_json(
                {
                    "error": (
                        f"Agent registration not active until block height "
                        f"{CHAIN.AGENT_REGISTRY_FORK}. Current: {current_height}"
                    )
                }
            )

        # Deterministic agent_id: sha256(public_key + label)[:16]
        agent_id = hashlib.sha256(
            (peer.identity.public_key + label).encode()
        ).hexdigest()[:16]

        identity_dict = {
            "public_key": peer.identity.public_key,
            "username": peer.identity.username or "",
            "username_signature": peer.identity.username_signature or "",
        }

        try:
            announcement = AgentAnnouncement(
                identity=identity_dict,
                agent_id=agent_id,
                label=label,
                description=description,
                capabilities=capabilities,
                endpoint_url=endpoint_url,
                agent_type=agent_type,
                icon=icon,
                version=version,
            )
        except ValueError as exc:
            self.set_status(400)
            return self.render_as_json({"error": str(exc)})

        announcement_str = announcement.to_string()
        relationship_hash = hashlib.sha256(announcement_str.encode()).digest().hex()

        txn = Transaction(
            txn_time=int(datetime.now(timezone.utc).timestamp()),
            public_key=peer.identity.public_key,
            relationship={"agent": announcement.to_dict()},
            relationship_hash=relationship_hash,
            outputs=[],
            inputs=[],
            fee=0.0,
            version=7,
        )

        try:
            txn.hash = await txn.generate_hash()
            txn.transaction_signature = TU.generate_signature_with_private_key(
                self.config.private_key, txn.hash
            )
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json(
                {"error": f"Failed to sign agent registration: {exc}"}
            )

        from yadacoin.core.keyeventlog import (
            DoesNotSpendEntirelyToPrerotatedKeyHashException,
            KELException,
        )

        try:
            await txn.verify(
                check_input_spent=True,
                check_max_inputs=current_height > CHAIN.CHECK_MAX_INPUTS_FORK,
                check_masternode_fee=current_height >= CHAIN.CHECK_MASTERNODE_FEE_FORK,
                check_kel=current_height >= CHAIN.CHECK_KEL_FORK,
                check_dynamic_nodes=current_height >= CHAIN.DYNAMIC_NODES_FORK,
                check_agent_registration=current_height >= CHAIN.AGENT_REGISTRY_FORK,
                mempool=True,
            )
        except (
            InvalidTransactionException,
            InvalidTransactionSignatureException,
        ) as exc:
            self.set_status(400)
            return self.render_as_json(
                {"error": f"Invalid agent registration transaction: {exc}"}
            )
        except (DoesNotSpendEntirelyToPrerotatedKeyHashException, KELException) as exc:
            self.set_status(400)
            return self.render_as_json({"error": f"Key event log error: {exc}"})
        except MissingInputTransactionException:
            pass  # Inputs not confirmed yet — still insert

        try:
            await self.config.mongo.async_db.miner_transactions.replace_one(
                {"id": txn.transaction_signature}, txn.to_dict(), upsert=True
            )
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json(
                {"error": f"Failed to broadcast agent registration: {exc}"}
            )

        # Broadcast to peers if in node mode
        if "node" in self.config.modes:
            try:
                async for peer_stream in self.config.peer.get_sync_peers():
                    await self.config.nodeShared.write_params(
                        peer_stream, "newtxn", {"transaction": txn.to_dict()}
                    )
            except Exception as exc:
                self.app_log.warning(
                    f"Error broadcasting agent registration to peers: {exc}"
                )

        return self.render_as_json(
            {
                "status": "success",
                "agent_id": agent_id,
                "transaction_signature": txn.transaction_signature,
                "agent": announcement.to_dict(),
            }
        )


class AgentDiscoverHandler(BaseHandler):
    """
    GET /ai-agent-auth/api/agents/discover?intent=<text>

    Searches the blockchain for registered agents whose capabilities match
    the supplied intent string.  Optionally filter by agent_type.

    Query parameters
    ----------------
    intent      : str  — free-form intent text (e.g. "book a flight to Paris")
    agent_type  : str  — optional filter by agent_type id
    limit       : int  — max results to return (default 20)

    Returns
    -------
    {"agents": [ { agent_id, label, description, capabilities,
                   endpoint_url, agent_type, icon, version,
                   identity, transaction_id, block_height } ]}
    """

    async def get(self):
        intent = (self.get_argument("intent", "") or "").lower().strip()
        agent_type_filter = (self.get_argument("agent_type", "") or "").strip()
        try:
            limit = min(int(self.get_argument("limit", "20")), 100)
        except (ValueError, TypeError):
            limit = 20

        # Tokenise intent into keywords
        intent_keywords = set(intent.split()) if intent else set()

        try:
            cursor = (
                self.config.mongo.async_db.blocks.find(
                    {
                        "transactions": {
                            "$elemMatch": {"relationship.agent": {"$exists": True}}
                        }
                    },
                    {"index": 1, "transactions": 1},
                )
                .sort("index", -1)
                .limit(500)
            )  # scan most recent 500 agent-bearing blocks

            agents = []
            seen_ids = set()

            async for block in cursor:
                block_height = block.get("index", 0)
                for txn in block.get("transactions", []):
                    rel = txn.get("relationship")
                    if not isinstance(rel, dict):
                        continue
                    agent_blob = rel.get("agent")
                    if not agent_blob or not isinstance(agent_blob, dict):
                        continue

                    agent_id = agent_blob.get("agent_id", "")
                    if agent_id in seen_ids:
                        continue  # keep only the most recent registration per agent_id
                    seen_ids.add(agent_id)

                    # agent_type filter
                    if (
                        agent_type_filter
                        and agent_blob.get("agent_type") != agent_type_filter
                    ):
                        continue

                    # intent matching: score by how many capability keywords overlap
                    capabilities = agent_blob.get("capabilities") or []
                    cap_set = {c.lower() for c in capabilities}

                    if intent_keywords:
                        # Label and description words also count
                        label_words = set(
                            (agent_blob.get("label") or "").lower().split()
                        )
                        desc_words = set(
                            (agent_blob.get("description") or "").lower().split()
                        )
                        searchable = cap_set | label_words | desc_words
                        score = len(intent_keywords & searchable)
                        if score == 0:
                            continue
                    else:
                        score = 0

                    agents.append(
                        {
                            "agent_id": agent_id,
                            "label": agent_blob.get("label", ""),
                            "description": agent_blob.get("description", ""),
                            "capabilities": capabilities,
                            "endpoint_url": agent_blob.get("endpoint_url", ""),
                            "agent_type": agent_blob.get("agent_type", "general"),
                            "icon": agent_blob.get("icon", "🤖"),
                            "version": agent_blob.get("version", "1.0"),
                            "identity": agent_blob.get("identity", {}),
                            "transaction_id": txn.get("id", ""),
                            "block_height": block_height,
                            "_score": score,
                        }
                    )

                    if len(agents) >= limit * 3:  # over-fetch to allow sorting
                        break

            # Sort by relevance score (desc), then block height (desc)
            agents.sort(key=lambda a: (-a["_score"], -a["block_height"]))
            for a in agents:
                del a["_score"]
            agents = agents[:limit]

        except Exception as exc:
            self.app_log.error(f"AgentDiscoverHandler error: {exc}")
            self.set_status(500)
            return self.render_as_json({"error": f"Discovery failed: {exc}"})

        return self.render_as_json({"agents": agents, "total": len(agents)})


# ── Node config apply handler ─────────────────────────────────────────────────

# Settings that may be changed via chat. Excludes keys that touch identity,
# cryptographic material, or network addressing.
_CONFIG_WRITEABLE: dict = {
    "combined_address": str,
    "credits_per_share": (int, float),
    "shares_required": bool,
    "pool_payout": bool,
    "pool_take": float,
    "payout_frequency": int,
    "max_miners": int,
    "max_peers": int,
    "pool_diff": int,
    "stratum_pool_port": int,
    "transactions_combining_wait": int,
    "restrict_graph_api": bool,
    "web_jwt_expiry": int,
    "peers_wait": int,
    "status_wait": int,
    "txn_queue_processor_wait": int,
    "block_queue_processor_wait": int,
    "block_checker_wait": int,
    "message_sender_wait": int,
    "pool_payer_wait": int,
    "cache_validator_wait": int,
    "mempool_cleaner_wait": int,
    "mempool_sender_wait": int,
    "nonce_processor_wait": int,
    "mongo_query_timeout": int,
    "http_request_timeout": int,
    "masternode_fee_minimum": int,
    "balance_min_utxo": int,
    "activate_peerjs": bool,
    "extended_status": bool,
    "log_health_status": bool,
    "docker_debug": bool,
    "asyncio_debug": bool,
    "asyncio_debug_duration": float,
    "network_seeds": list,
    "network_service_providers": list,
    "network_seed_gateways": list,
    "serve_host": str,
    "serve_port": int,
    "peer_host": str,
    "peer_port": int,
}
