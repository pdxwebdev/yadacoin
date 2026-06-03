"""backend/agent/skills.py — Skill registry and executor for the agent planning loop."""
import datetime as _dt
import re as _re

from tornado.httpclient import AsyncHTTPClient, HTTPRequest

from ..github.api import _github_api_get, _github_api_post
from ..microsoft.api import _msgraph_api_get, _msgraph_api_post
from .types import _brave_web_search

# ── Skill registry ─────────────────────────────────────────────────────────── #
# Each entry documents what the skill can do for the planner LLM.
# "requires" maps to a context key that must be non-empty for the skill to appear.

SKILL_REGISTRY = {
    "brave_search": {
        "description": "Search the web for current information, news, and facts using Brave Search",
        "requires": "brave_api_key",
        "actions": {
            "search": {
                "description": "Perform a web search and return top results",
                "params": {
                    "query": "string (required) — what to search for",
                    "count": "integer (optional, 1-10, default 5) — number of results",
                },
                "returns": "List of {title, url, snippet} web results",
            }
        },
    },
    "web_fetch": {
        "description": "Fetch and read the text content of any public web URL",
        "requires": None,
        "actions": {
            "fetch": {
                "description": "Fetch a web page and return its cleaned text content",
                "params": {
                    "url": "string (required) — the URL to fetch",
                },
                "returns": "Text content of the page (up to 4000 characters)",
            }
        },
    },
    "github": {
        "description": "Interact with GitHub: repositories, issues, pull requests, and notifications",
        "requires": "github_access_token",
        "actions": {
            "list_repos": {
                "description": "List the authenticated user's GitHub repositories",
                "params": {
                    "visibility": "string (optional) public|private|all — filter by visibility",
                },
                "returns": "List of {full_name, description, stars, open_issues, language, url}",
            },
            "list_issues": {
                "description": "List issues in a specific repository",
                "params": {
                    "owner": "string (required) — repository owner login",
                    "repo": "string (required) — repository name",
                    "state": "string (optional) open|closed|all — default open",
                },
                "returns": "List of {number, title, state, author, comments, created_at, url}",
            },
            "list_prs": {
                "description": "List pull requests in a specific repository",
                "params": {
                    "owner": "string (required) — repository owner login",
                    "repo": "string (required) — repository name",
                    "state": "string (optional) open|closed|all — default open",
                },
                "returns": "List of {number, title, state, author, draft, url}",
            },
            "create_issue": {
                "description": "Create a new GitHub issue (requires user confirmation in plan)",
                "params": {
                    "owner": "string (required) — repository owner login",
                    "repo": "string (required) — repository name",
                    "title": "string (required) — issue title",
                    "body": "string (optional) — issue body/description",
                },
                "returns": "{number, title, url} of the created issue",
            },
            "list_commits": {
                "description": "List recent commits for a repository, optionally filtered by author",
                "params": {
                    "owner": "string (required) — repository owner login",
                    "repo": "string (required) — repository name",
                    "author": "string (optional) — GitHub login to filter by (use 'me' for the authenticated user)",
                    "count": "integer (optional, 1-20, default 10) — number of commits to return",
                },
                "returns": "List of {sha, message, author, date, url}",
            },
            "get_authenticated_user": {
                "description": "Get the login (username) and name of the authenticated GitHub user",
                "params": {},
                "returns": "{login, name, email} of the authenticated user",
            },
        },
    },
    "microsoft": {
        "description": "Access Microsoft 365 / Outlook email and upcoming calendar events",
        "requires": "microsoft_access_token",
        "actions": {
            "list_emails": {
                "description": "List recent emails from inbox or another folder",
                "params": {
                    "folder": "string (optional) inbox|sentitems|drafts — default inbox",
                    "top": "integer (optional, 1-25, default 10) — number of emails",
                },
                "returns": "List of {subject, from, received, is_read, preview}",
            },
            "send_email": {
                "description": "Send an email via Outlook",
                "params": {
                    "to": "string (required) — recipient email address",
                    "subject": "string (required) — email subject",
                    "body": "string (required) — email body (plain text)",
                },
                "returns": "Confirmation that the email was sent",
            },
            "list_events": {
                "description": "List upcoming calendar events for the next N days",
                "params": {
                    "days": "integer (optional, default 7) — how many days ahead to look",
                },
                "returns": "List of {subject, start, end, location, organizer}",
            },
        },
    },
    "wallet": {
        "description": "YadaCoin wallet operations — check balance and transaction history",
        "requires": "public_key",
        "actions": {
            "get_balance": {
                "description": "Get the current YDA balance for the wallet",
                "params": {},
                "returns": "{address, balance} with balance in YDA",
            },
            "get_transactions": {
                "description": "Get recent on-chain transaction history (sent and received)",
                "params": {
                    "direction": "string (optional) all|sent|received — default all",
                },
                "returns": "List of transactions with direction, amount, and timestamp",
            },
        },
    },
    "generate_text": {
        "description": "Use the AI to generate, summarize, or rewrite text based on provided data",
        "requires": None,
        "actions": {
            "summarize": {
                "description": "Summarize or rewrite provided data into human-readable prose",
                "params": {
                    "instruction": "string (required) — what to write, e.g. 'Write a 2-paragraph summary of these commits'",
                    "data": "any (required) — the data to summarize (can be a $stepN reference)",
                },
                "returns": "{text} containing the generated prose",
            },
        },
    },
}


def build_available_skills(context: dict) -> dict:
    """Return a filtered copy of SKILL_REGISTRY including only skills whose
    requirements are satisfied by the given context dict."""
    available = {}
    for skill_name, skill_def in SKILL_REGISTRY.items():
        req = skill_def.get("requires")
        if req is None or context.get(req):
            available[skill_name] = skill_def
    return available


def build_planner_prompt(available_skills: dict) -> str:
    """Build the system prompt for the planner LLM call."""
    lines = []
    for skill_name, skill_def in available_skills.items():
        lines.append(f"\n### {skill_name}")
        lines.append(skill_def["description"])
        for action_name, action_def in skill_def["actions"].items():
            lines.append(f"\n  Action: {action_name}")
            lines.append(f"  Description: {action_def['description']}")
            if action_def.get("params"):
                lines.append("  Parameters:")
                for p_name, p_desc in action_def["params"].items():
                    lines.append(f"    - {p_name}: {p_desc}")
            lines.append(f"  Returns: {action_def['returns']}")

    skills_text = "\n".join(lines)
    return (
        "You are an AI task planner. Given a user goal and a set of available skills, "
        "create a precise, minimal step-by-step execution plan.\n\n"
        f"Available skills:\n{skills_text}\n\n"
        "Rules:\n"
        "- Use ONLY the skills and actions listed above.\n"
        "- Order steps so that steps depending on earlier results come after them.\n"
        '- When a param value depends on a previous step\'s output, use "$stepN" as a '
        'placeholder (e.g. "$step1" = full output of step 1, '
        '"$step1.results[0].url" = first result\'s URL from step 1).\n'
        "- Use the fewest steps needed. 1-3 steps is ideal for most goals.\n"
        "- Never add steps just to display data — the system handles presentation.\n"
        "- NEVER use brave_search or web_fetch to look up data that a connected skill "
        "(github, microsoft, wallet) can fetch directly via its API.\n"
        "- For multi-step plans that fetch data and then email it: use generate_text/summarize "
        "as an intermediate step to convert raw data into prose, then pass $stepN.text as the email body.\n"
        "- To get commits by the authenticated user, ALWAYS use github/get_authenticated_user first "
        "to obtain their login. Then call github/list_commits with "
        'owner="$step1.login" AND author="$step1.login". '
        "Never assume an owner from the repo name alone — the owner must come from step 1.\n"
        "Return ONLY a valid JSON object:\n"
        "{\n"
        '  "reasoning": "brief explanation of your approach",\n'
        '  "steps": [\n'
        "    {\n"
        '      "step": 1,\n'
        '      "skill": "skill_name",\n'
        '      "action": "action_name",\n'
        '      "params": {"param_name": "value"},\n'
        '      "description": "one-line description of what this step does"\n'
        "    }\n"
        "  ]\n"
        "}"
    )


def _resolve_path(obj, path: str):
    """Resolve a dot/bracket path like 'items[0].url' against obj."""
    tokens = _re.split(r"\.|\[(\d+)\]", path)
    current = obj
    for token in tokens:
        if token is None or token == "":
            continue
        if isinstance(current, dict):
            current = current.get(token)
        elif isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def resolve_param_refs(params: dict, step_results: dict) -> dict:
    """Substitute $stepN or $stepN.path references in param string values.

    Handles two forms:
      - Whole-value: "$step1.commits" → replaced with the resolved object
      - Inline:      "Summary of $step1.commits" → resolved value serialised
                     as compact JSON and interpolated into the string
    """
    if not step_results or not params:
        return params

    import json as _json

    # Regex for a single $stepN or $stepN.some.path reference
    _ref_re = _re.compile(r"\$step(\d+)(?:\.([A-Za-z0-9_.[\]]+))?")

    def _replace_inline(text: str) -> object:
        # If the entire string is a single reference, return the raw object
        m = _re.fullmatch(r"\$step(\d+)(?:\.(.+))?", text)
        if m:
            step_num = int(m.group(1))
            path = m.group(2)
            step_out = step_results.get(step_num)
            if step_out is not None:
                return _resolve_path(step_out, path) if path else step_out
            return text

        # Otherwise substitute each reference inline as a JSON-serialised string
        def _sub(match):
            step_num = int(match.group(1))
            path = match.group(2)
            step_out = step_results.get(step_num)
            if step_out is None:
                return match.group(0)
            val = _resolve_path(step_out, path) if path else step_out
            if isinstance(val, str):
                return val
            return _json.dumps(val, ensure_ascii=False)

        return _ref_re.sub(_sub, text)

    resolved = {}
    for k, v in params.items():
        if isinstance(v, str):
            v = _replace_inline(v)
        resolved[k] = v
    return resolved


async def execute_skill(skill: str, action: str, params: dict, context: dict) -> dict:
    """Execute a single skill action.

    Returns a dict with "ok" (bool) and skill-specific output keys.
    On failure returns {"ok": False, "error": "..."}.
    """
    params = params or {}

    # ── brave_search ──────────────────────────────────────────────────────── #
    if skill == "brave_search":
        if action == "search":
            api_key = context.get("brave_api_key", "")
            if not api_key:
                return {"ok": False, "error": "Brave API key not configured"}
            query = str(params.get("query", ""))
            count = min(int(params.get("count") or 5), 10)
            results = await _brave_web_search(api_key, query, count=count)
            return {"ok": True, "query": query, "results": results}

    # ── web_fetch ─────────────────────────────────────────────────────────── #
    elif skill == "web_fetch":
        if action == "fetch":
            url = str(params.get("url", ""))
            if not url.startswith(("http://", "https://")):
                return {"ok": False, "error": "url must start with http:// or https://"}
            try:
                client = AsyncHTTPClient()
                req = HTTPRequest(
                    url,
                    method="GET",
                    headers={"User-Agent": "YadaAgent/1.0"},
                    request_timeout=15.0,
                    follow_redirects=True,
                    max_redirects=5,
                )
                resp = await client.fetch(req, raise_error=False)
                if resp.code != 200:
                    return {"ok": False, "error": f"HTTP {resp.code}"}
                raw = resp.body.decode("utf-8", errors="replace")
                text = _re.sub(r"<[^>]+>", " ", raw)
                text = _re.sub(r"\s+", " ", text).strip()[:4000]
                return {"ok": True, "url": url, "content": text}
            except Exception as exc:
                return {"ok": False, "error": str(exc)[:200]}

    # ── github ────────────────────────────────────────────────────────────── #
    elif skill == "github":
        token = context.get("github_access_token", "")
        if not token:
            return {"ok": False, "error": "GitHub not connected"}

        if action == "list_repos":
            visibility = (params.get("visibility") or "all").lower()
            if visibility not in ("public", "private", "all"):
                visibility = "all"
            req_params = {
                "sort": "updated",
                "per_page": 10,
                "affiliation": "owner,collaborator",
            }
            if visibility != "all":
                req_params["visibility"] = visibility
            raw = await _github_api_get(token, "/user/repos", req_params)
            items = [
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
                for r in (raw if isinstance(raw, list) else [])[:10]
            ]
            return {"ok": True, "repos": items}

        elif action == "list_issues":
            owner = str(params.get("owner", ""))
            repo = str(params.get("repo", ""))
            state = str(params.get("state") or "open")
            if not owner or not repo:
                return {"ok": False, "error": "owner and repo are required"}
            raw = await _github_api_get(
                token,
                f"/repos/{owner}/{repo}/issues",
                {"state": state, "per_page": 10},
            )
            items = [
                {
                    "number": i.get("number"),
                    "title": (i.get("title") or "")[:100],
                    "state": i.get("state", ""),
                    "author": (i.get("user") or {}).get("login", ""),
                    "comments": i.get("comments", 0),
                    "created_at": (i.get("created_at") or "")[:10],
                    "url": i.get("html_url", ""),
                }
                for i in (raw if isinstance(raw, list) else [])[:10]
                if not i.get("pull_request")
            ]
            return {"ok": True, "repo": f"{owner}/{repo}", "issues": items}

        elif action == "list_prs":
            owner = str(params.get("owner", ""))
            repo = str(params.get("repo", ""))
            state = str(params.get("state") or "open")
            if not owner or not repo:
                return {"ok": False, "error": "owner and repo are required"}
            raw = await _github_api_get(
                token,
                f"/repos/{owner}/{repo}/pulls",
                {"state": state, "per_page": 10},
            )
            items = [
                {
                    "number": p.get("number"),
                    "title": (p.get("title") or "")[:100],
                    "state": p.get("state", ""),
                    "author": (p.get("user") or {}).get("login", ""),
                    "draft": p.get("draft", False),
                    "url": p.get("html_url", ""),
                }
                for p in (raw if isinstance(raw, list) else [])[:10]
            ]
            return {"ok": True, "repo": f"{owner}/{repo}", "prs": items}

        elif action == "create_issue":
            owner = str(params.get("owner", ""))
            repo = str(params.get("repo", ""))
            title = str(params.get("title", ""))
            body = str(params.get("body") or "")
            if not owner or not repo or not title:
                return {"ok": False, "error": "owner, repo, and title are required"}
            result = await _github_api_post(
                token,
                f"/repos/{owner}/{repo}/issues",
                {"title": title, "body": body},
            )
            return {
                "ok": True,
                "created": {
                    "number": result.get("number"),
                    "title": result.get("title", ""),
                    "url": result.get("html_url", ""),
                },
            }

        elif action == "get_authenticated_user":
            raw = await _github_api_get(token, "/user", {})
            return {
                "ok": True,
                "login": raw.get("login", ""),
                "name": raw.get("name") or "",
                "email": raw.get("email") or "",
            }

        elif action == "list_commits":
            owner = str(params.get("owner", ""))
            repo = str(params.get("repo", ""))
            author_param = str(params.get("author") or "")
            count = min(int(params.get("count") or 10), 20)
            if not owner or not repo:
                return {"ok": False, "error": "owner and repo are required"}
            # Resolve 'me' to the authenticated user's login
            if author_param.lower() == "me":
                user_raw = await _github_api_get(token, "/user", {})
                author_param = user_raw.get("login", "")
            req_params = {"per_page": count}
            if author_param:
                req_params["author"] = author_param
            raw = await _github_api_get(
                token, f"/repos/{owner}/{repo}/commits", req_params
            )
            items = [
                {
                    "sha": (c.get("sha") or "")[:7],
                    "message": (c.get("commit") or {})
                    .get("message", "")
                    .split("\n")[0][:120],
                    "author": ((c.get("commit") or {}).get("author") or {}).get(
                        "name", ""
                    ),
                    "date": ((c.get("commit") or {}).get("author") or {}).get(
                        "date", ""
                    )[:10],
                    "url": (c.get("html_url") or ""),
                }
                for c in (raw if isinstance(raw, list) else [])[:count]
            ]
            return {"ok": True, "repo": f"{owner}/{repo}", "commits": items}

    # ── microsoft ─────────────────────────────────────────────────────────── #
    elif skill == "microsoft":
        token = context.get("microsoft_access_token", "")
        if not token:
            return {"ok": False, "error": "Microsoft not connected"}

        if action == "list_emails":
            folder_map = {
                "inbox": "inbox",
                "sentitems": "sentItems",
                "drafts": "drafts",
            }
            folder_key = folder_map.get(
                (params.get("folder") or "inbox").lower(), "inbox"
            )
            top = min(int(params.get("top") or 10), 25)
            raw = await _msgraph_api_get(
                token,
                f"/me/mailFolders/{folder_key}/messages",
                {
                    "$top": top,
                    "$select": "id,subject,from,receivedDateTime,isRead,bodyPreview",
                    "$orderby": "receivedDateTime desc",
                },
            )
            items = [
                {
                    "subject": (m.get("subject") or "(no subject)")[:120],
                    "from": ((m.get("from") or {}).get("emailAddress") or {}).get(
                        "address", ""
                    ),
                    "from_name": ((m.get("from") or {}).get("emailAddress") or {}).get(
                        "name", ""
                    ),
                    "received": (m.get("receivedDateTime") or "")[:16].replace(
                        "T", " "
                    ),
                    "is_read": m.get("isRead", True),
                    "preview": (m.get("bodyPreview") or "")[:150],
                }
                for m in raw.get("value", [])[:top]
            ]
            return {"ok": True, "folder": folder_key, "emails": items}

        elif action == "send_email":
            to = str(params.get("to", ""))
            subject = str(params.get("subject", ""))
            body = str(params.get("body", ""))
            if not to or not subject or not body:
                return {"ok": False, "error": "to, subject, and body are required"}
            await _msgraph_api_post(
                token,
                "/me/sendMail",
                {
                    "message": {
                        "subject": subject,
                        "body": {"contentType": "Text", "content": body},
                        "toRecipients": [{"emailAddress": {"address": to}}],
                    },
                    "saveToSentItems": True,
                },
            )
            return {"ok": True, "sent_to": to, "subject": subject}

        elif action == "list_events":
            days = int(params.get("days") or 7)
            now = _dt.datetime.utcnow()
            end = now + _dt.timedelta(days=days)
            raw = await _msgraph_api_get(
                token,
                "/me/calendarView",
                {
                    "startDateTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "endDateTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "$top": 15,
                    "$select": "subject,start,end,location,organizer",
                    "$orderby": "start/dateTime",
                },
            )
            items = [
                {
                    "subject": (e.get("subject") or "")[:100],
                    "start": (e.get("start") or {})
                    .get("dateTime", "")[:16]
                    .replace("T", " "),
                    "end": (e.get("end") or {})
                    .get("dateTime", "")[:16]
                    .replace("T", " "),
                    "location": ((e.get("location") or {}).get("displayName") or "")[
                        :80
                    ],
                    "organizer": (
                        (e.get("organizer") or {}).get("emailAddress") or {}
                    ).get("name", ""),
                }
                for e in raw.get("value", [])[:15]
            ]
            return {"ok": True, "events": items}

    # ── wallet ────────────────────────────────────────────────────────────── #
    elif skill == "wallet":
        public_key = context.get("public_key", "")
        if not public_key:
            return {"ok": False, "error": "public_key not provided"}
        try:
            from bitcoin.wallet import P2PKHBitcoinAddress

            address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
        except Exception as exc:
            return {"ok": False, "error": f"invalid public_key: {exc}"}
        config = context.get("config")
        if config is None:
            return {"ok": False, "error": "config not available"}

        if action == "get_balance":
            try:
                balance = await config.BU.get_wallet_balance(address)
                return {"ok": True, "address": address, "balance": f"{balance:.8f} YDA"}
            except Exception as exc:
                return {"ok": False, "error": str(exc)[:200]}

        elif action == "get_transactions":
            direction = str(params.get("direction") or "all").lower()
            if direction not in ("all", "sent", "received"):
                direction = "all"
            results = []
            try:
                if direction in ("all", "sent"):
                    sent_q = [
                        {
                            "$match": {
                                "transactions.inputs.0": {"$exists": True},
                                "transactions.public_key": public_key,
                            }
                        },
                        {"$unwind": "$transactions"},
                        {
                            "$match": {
                                "transactions.inputs.0": {"$exists": True},
                                "transactions.public_key": public_key,
                            }
                        },
                        {"$sort": {"transactions.time": -1}},
                        {"$limit": 10},
                    ]
                    async for doc in config.mongo.async_db.blocks.aggregate(sent_q):
                        tx = doc["transactions"]
                        total_out = sum(
                            o.get("value", 0) for o in (tx.get("outputs") or [])
                        )
                        results.append(
                            {
                                "direction": "sent",
                                "amount": f"{total_out:.8f}",
                                "time": tx.get("time"),
                            }
                        )
                if direction in ("all", "received"):
                    recv_q = [
                        {"$match": {"transactions.outputs.to": address}},
                        {"$unwind": "$transactions"},
                        {
                            "$match": {
                                "transactions.outputs.to": address,
                                "transactions.public_key": {"$ne": public_key},
                            }
                        },
                        {"$sort": {"transactions.time": -1}},
                        {"$limit": 10},
                    ]
                    async for doc in config.mongo.async_db.blocks.aggregate(recv_q):
                        tx = doc["transactions"]
                        total_in = sum(
                            o.get("value", 0)
                            for o in (tx.get("outputs") or [])
                            if o.get("to") == address
                        )
                        results.append(
                            {
                                "direction": "received",
                                "amount": f"{total_in:.8f}",
                                "time": tx.get("time"),
                            }
                        )
            except Exception as exc:
                return {"ok": False, "error": str(exc)[:200]}
            return {"ok": True, "address": address, "transactions": results}

    elif skill == "generate_text":
        if action == "summarize":
            import json as _json

            instruction = str(
                params.get("instruction") or "Summarize the following data."
            )
            data = params.get("data", "")
            if not isinstance(data, str):
                data = _json.dumps(data, ensure_ascii=False)
            llm_caller = context.get("llm_call")
            if llm_caller is None:
                return {"ok": False, "error": "LLM not available"}
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful writing assistant. Respond with only the requested text, no extra commentary.",
                },
                {"role": "user", "content": f"{instruction}\n\nData:\n{data}"},
            ]
            try:
                text = await llm_caller(messages, max_tokens=800)
                return {"ok": True, "text": text}
            except Exception as exc:
                return {"ok": False, "error": str(exc)[:200]}

    return {"ok": False, "error": f"Unknown skill/action: {skill}/{action}"}
