"""backend/agent/skills.py — Skill registry and executor for the agent planning loop."""
import datetime as _dt
import re as _re

from tornado.httpclient import AsyncHTTPClient, HTTPRequest

from ..github.api import _github_api_get, _github_api_post
from ..microsoft.api import _msgraph_api_get, _msgraph_api_post
from .types import _brave_answers, _brave_web_search

# ── Skill registry ─────────────────────────────────────────────────────────── #
# Each entry documents what the skill can do for the planner LLM.
# "requires" maps to a context key that must be non-empty for the skill to appear.

SKILL_REGISTRY = {
    "brave_answers": {
        "description": "Get a direct AI-generated answer/summary from Brave for a query — higher confidence than web search results",
        "requires": "brave_answers_api_key",
        "actions": {
            "answer": {
                "description": "Ask a question and get a concise summarized answer directly from Brave",
                "params": {
                    "query": "string (required) — the question or topic to get an answer for",
                },
                "returns": "A plain-text answer/summary string, or null if unavailable",
            }
        },
    },
    "brave_search": {
        "description": "Search the web for current information, news, and facts using Brave Search",
        "requires": "brave_api_key",
        "actions": {
            "search": {
                "description": "Perform a web search and return top results",
                "params": {
                    "query": "string (required) — what to search for",
                    "count": "integer (optional, 1-20, default 10) — number of results",
                    "country": "string (optional, ISO 3166-1 alpha-2, default 'us') — bias results toward this country, e.g. 'us', 'ca', 'gb'",
                    "fetch_content": "boolean (optional, default false) — if true, fetches and includes the full text content of each result page; use when you need actual page text, e.g. to find email addresses or contact details",
                },
                "returns": "List of {title, url, snippet} web results; each result also has 'content' when fetch_content=true",
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
                "side_effects": True,
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
                "side_effects": True,
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
    "key_rotation": {
        "description": (
            "YadaCoin Key Event Log (KEL) operations. "
            "check_status verifies whether the current address is still active (not yet spent). "
            "rotate advances the KEL to the next pre-committed key, proving identity on-chain. "
            "The second_factor is supplied server-side and must NOT be passed as a tool argument."
        ),
        "requires": "public_key",
        "actions": {
            "check_status": {
                "description": (
                    "Check whether the current YadaCoin address has already submitted a "
                    "key-rotation transaction ('spent'). Returns {address, spent, source}. "
                    "Call this before any sensitive or authenticated action when key rotation "
                    "is required."
                ),
                "params": {},
                "side_effects": False,
            },
            "rotate": {
                "description": (
                    "Perform a YadaCoin key rotation — broadcast a signed transaction that "
                    "advances the Key Event Log to the next pre-committed key. "
                    "The second_factor is supplied server-side; do NOT include it in arguments. "
                    "Returns {ok, new_address, new_public_key, txid}."
                ),
                "params": {
                    "relationship": (
                        "string (optional). Non-empty value creates an UNCONFIRMED+CONFIRMING "
                        "key-event pair for agent authorization."
                    ),
                    "outputs": (
                        "array (optional). Additional transaction outputs to include, e.g. "
                        '[{"to": "1Abc...", "value": 1.5}]. Use this to send YDA coins '
                        "as part of the rotation. Any output not going to the prerotated address "
                        "automatically triggers a confirming transaction."
                    ),
                },
                "side_effects": True,
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


def build_tool_schemas(available_skills: dict) -> list:
    """Convert available skills to OpenAI-format tool schemas for ReAct tool-calling.

    Tool names use the format ``skill__action`` (double underscore separator)
    so they can be unambiguously split back into (skill, action) at call time.
    Tool names must match ``^[a-zA-Z0-9_-]{1,64}$``.
    """
    tools = []
    for skill_name, skill_def in available_skills.items():
        for action_name, action_def in skill_def["actions"].items():
            fn_name = f"{skill_name}__{action_name}"
            props: dict = {}
            required: list = []
            for p_name, p_desc in (action_def.get("params") or {}).items():
                desc_lower = p_desc.lower()
                if "integer" in desc_lower or "int," in desc_lower:
                    p_type = "integer"
                    props[p_name] = {"type": p_type, "description": p_desc}
                elif (
                    "boolean" in desc_lower
                    or "bool," in desc_lower
                    or "true|false" in desc_lower
                ):
                    p_type = "boolean"
                    props[p_name] = {"type": p_type, "description": p_desc}
                elif "array" in desc_lower:
                    props[p_name] = {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": p_desc,
                    }
                else:
                    props[p_name] = {"type": "string", "description": p_desc}
                if "required" in p_desc.lower():
                    required.append(p_name)
            side_note = (
                " ⚠ This action has real-world side effects and requires user confirmation."
                if action_def.get("side_effects")
                else ""
            )
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "description": action_def["description"] + side_note,
                        "parameters": {
                            "type": "object",
                            "properties": props,
                            "required": required,
                        },
                    },
                }
            )
    return tools


def build_planner_prompt(available_skills: dict) -> str:
    """Build the system prompt for the planner LLM call."""
    lines = []
    for skill_name, skill_def in available_skills.items():
        lines.append(f"\n### {skill_name}")
        lines.append(skill_def["description"])
        for action_name, action_def in skill_def["actions"].items():
            lines.append(f"\n  Action: {action_name}")
            lines.append(f"  Description: {action_def['description']}")
            if action_def.get("side_effects"):
                lines.append(
                    "  ⚠ side_effects: true — system will pause for user confirmation before this action runs"
                )
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
        "- If 'brave_answers' is available, prefer it over 'brave_search' for direct "
        "factual or informational questions (e.g. 'what is X', 'list Y', 'how does Z work'). "
        "brave_answers returns a concise AI-generated summary in a single step. "
        "Use 'brave_search' instead when you need source URLs, multiple results to compare, "
        "contact details/email addresses, or when brave_answers returns no result. "
        "You may follow a brave_answers step with a brave_search step if the answer needs "
        "supporting sources or more detail.\n"
        "- brave_search does NOT support 'site:' query operators — they return zero results. "
        "NEVER use 'site:example.com' in a query. Instead, use descriptive natural language "
        "and let the search find the right pages.\n"
        "- When looking for an email address or contact info: "
        "(a) if you already know the exact URL, use web_fetch/fetch directly on that page; "
        "(b) otherwise use brave_search/search with fetch_content=true so you get full page text in one step — "
        "do NOT do a search then separately call web_fetch; the content is already in the results. "
        "When searching for a specific department or function (e.g. code violations, permits, billing), "
        "include the exact function name in the search query rather than using a generic 'contact' query. "
        "Official government and institutional websites are often blocked by WAF/CDN filters that prevent "
        "automated fetching; when fetch_content returns blocked=true or empty content for a URL, rely on "
        "the 'description' snippet and 'emails_found' fields — the search engine may have the email in "
        "its cached snippet even when the live page is inaccessible. "
        "Third-party reference sites (e.g. citizen portals, service directories, agency listings) are "
        "usually NOT WAF-blocked and often list the same contact details as the official site. "
        "To surface these third-party pages, include terms like 'directory', 'agency', or the "
        "specific department name in your query alongside the organisation name. "
        "When multiple results are returned, prefer results whose URL path contains words matching "
        "the specific department or function rather than a generic home or contact page. "
        "Always check every result's 'emails_found' list before concluding no email was found. "
        "Pages often contain multiple email addresses; always identify the one whose "
        "surrounding text matches the specific function requested, not just the first email found.\n"
        "- For multi-step plans that fetch data and then email it: use generate_text/summarize "
        "as an intermediate step to convert raw data into prose, then pass $stepN.text as the email body.\n"
        "- To get commits by the authenticated user, ALWAYS use github/get_authenticated_user first "
        "to obtain their login. Then call github/list_commits with "
        'owner="$step1.login" AND author="$step1.login". '
        "Never assume an owner from the repo name alone — the owner must come from step 1.\n"
        "- The 'skill' field in each step MUST exactly match one of the top-level skill names "
        "shown in the skill list above (e.g. 'github', 'microsoft', 'generate_text', 'wallet'). "
        "NEVER use an action name as the skill name. For example, to send email use "
        "skill='microsoft' action='send_email', NOT skill='send_email' action='send_email'.\n"
        "- IMPORTANT: Some actions are marked as side-effecting (e.g. microsoft/send_email, github/create_issue). "
        "The system will automatically pause before executing those steps and show the user a "
        "confirmation dialog — you do NOT need to ask for confirmation in your plan or in text. "
        "Always include the full end-to-end plan with all steps, including side-effecting ones. "
        "Never end a plan with a question or omit a step because you think you should ask first.\n"
        "- To send YDA coins to an address, use key_rotation/rotate with an 'outputs' parameter "
        'containing [{"to": "<address>", "value": <amount>}]. '
        "There is no separate 'send' action — sending is always done as part of a key rotation. "
        "Always call key_rotation/check_status first to confirm the address is active before rotating.\n"
        "- If the conversation history already contains everything needed to answer the current goal "
        "(e.g. the user is reformatting, filtering, or summarizing a previous result), return an "
        "EMPTY steps list. The synthesizer will answer directly from history. Example: "
        '{"reasoning": "answer already in history", "steps": []}\n'
        "- NEVER return empty steps when the goal asks for email addresses, phone numbers, or "
        "contact details for entities NOT already confirmed in the conversation history or "
        "pre-fetched context. If the goal names multiple counties/organisations and their "
        "contact info is not ALL explicitly present, plan brave_search steps to look them up. "
        "Partially-known data is NOT sufficient — plan steps for ALL missing items.\n"
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

    # ── brave_answers ─────────────────────────────────────────────────────── #
    if skill == "brave_answers":
        if action == "answer":
            api_key = context.get("brave_answers_api_key", "")
            if not api_key:
                return {"ok": False, "error": "Brave Answers API key not configured"}
            query = str(params.get("query", ""))
            if not query:
                return {"ok": False, "error": "query parameter is required"}
            answer = await _brave_answers(api_key, query)
            if answer is None:
                return {
                    "ok": True,
                    "answer": None,
                    "note": "No summary available for this query",
                }
            return {"ok": True, "answer": answer}

    # ── brave_search ──────────────────────────────────────────────────────── #
    if skill == "brave_search":
        if action == "search":
            api_key = context.get("brave_api_key", "")
            if not api_key:
                return {"ok": False, "error": "Brave API key not configured"}
            query = str(params.get("query", ""))
            count = min(int(params.get("count") or 10), 20)
            country = str(params.get("country") or "us")
            fetch_content = bool(params.get("fetch_content", False))
            results = await _brave_web_search(
                api_key, query, count=count, country=country
            )
            if fetch_content and results:
                fetch_client = AsyncHTTPClient()
                for r in results:
                    url = r.get("url", "")
                    if not url.startswith(("http://", "https://")):
                        r["content"] = ""
                        continue
                    try:
                        freq = HTTPRequest(
                            url,
                            method="GET",
                            headers={
                                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                                "Accept-Language": "en-US,en;q=0.9",
                                "Accept-Encoding": "gzip, deflate, br",
                                "Cache-Control": "no-cache",
                                "Pragma": "no-cache",
                                "Upgrade-Insecure-Requests": "1",
                                "Sec-Fetch-Dest": "document",
                                "Sec-Fetch-Mode": "navigate",
                                "Sec-Fetch-Site": "none",
                                "Sec-Fetch-User": "?1",
                                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                                "sec-ch-ua-mobile": "?0",
                                "sec-ch-ua-platform": '"macOS"',
                            },
                            request_timeout=10.0,
                            follow_redirects=True,
                            max_redirects=5,
                            decompress_response=True,
                        )
                        fresp = await fetch_client.fetch(freq, raise_error=False)
                        r["fetch_status"] = fresp.code
                        if fresp.code == 403 or fresp.code == 503:
                            # WAF/CDN block — mark as blocked so the LLM falls
                            # back to the description snippet and emails_found.
                            r["content"] = ""
                            r["blocked"] = True
                        elif fresp.body:
                            raw = fresp.body.decode("utf-8", errors="replace")
                            text = _re.sub(r"<[^>]+>", " ", raw)
                            text = _re.sub(r"\s+", " ", text).strip()[:8000]
                            r["content"] = text if text else ""
                        else:
                            r["content"] = ""
                    except Exception as _fe:
                        r["content"] = ""
                        r["fetch_error"] = str(_fe)[:120]

                # Programmatically extract all email addresses from both the
                # description snippet and page content for every result.
                # This gives the synthesis LLM a clean list to work from
                # rather than requiring it to scan raw text blobs.
                _email_re = _re.compile(
                    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
                )
                for r in results:
                    found = []
                    for field in ("description", "content"):
                        found.extend(_email_re.findall(r.get(field) or ""))
                    # deduplicate while preserving order
                    seen = set()
                    deduped = []
                    for e in found:
                        el = e.lower()
                        if el not in seen:
                            seen.add(el)
                            deduped.append(e)
                    if deduped:
                        r["emails_found"] = deduped

                # Re-sort results to prefer URLs whose path contains query keywords.
                # This counteracts search engines returning off-topic pages (e.g. a
                # legal notices / contracts page) ahead of the specific department page.
                _stopwords = {
                    "a",
                    "an",
                    "the",
                    "and",
                    "or",
                    "for",
                    "to",
                    "in",
                    "on",
                    "of",
                    "with",
                    "find",
                    "search",
                    "website",
                    "page",
                    "contact",
                    "us",
                    "how",
                    "what",
                    "where",
                    "is",
                    "are",
                    "send",
                    "get",
                    "me",
                }
                _query_words = [
                    w.lower()
                    for w in _re.split(r"\W+", query)
                    if len(w) > 2 and w.lower() not in _stopwords
                ]

                def _url_score(r):
                    try:
                        from urllib.parse import urlparse

                        path = urlparse(r.get("url", "")).path.lower()
                        keyword_hits = sum(1 for w in _query_words if w in path)
                        # Strongly prefer unblocked results — a blocked page with a
                        # great URL is useless; an unblocked third-party page that
                        # mentions the same contact details is far more valuable.
                        blocked_penalty = -100 if r.get("blocked") else 0
                        # Bonus for results that already have emails extracted
                        email_bonus = 50 if r.get("emails_found") else 0
                        return keyword_hits + blocked_penalty + email_bonus
                    except Exception:
                        return 0

                if len(results) > 1:
                    results.sort(key=_url_score, reverse=True)
            else:
                # Even without fetch_content, extract emails from description snippets.
                _email_re = _re.compile(
                    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
                )
                for r in results:
                    found = _email_re.findall(r.get("description") or "")
                    seen = set()
                    deduped = []
                    for e in found:
                        el = e.lower()
                        if el not in seen:
                            seen.add(el)
                            deduped.append(e)
                    if deduped:
                        r["emails_found"] = deduped

            # Aggregate all emails across all results into a top-level field
            # so the synthesis LLM cannot miss them regardless of result ordering.
            _all_emails: list = []
            _seen_all: set = set()
            for r in results:
                for e in r.get("emails_found") or []:
                    if e.lower() not in _seen_all:
                        _seen_all.add(e.lower())
                        _all_emails.append(e)

            result_payload: dict = {"ok": True, "query": query, "results": results}
            if _all_emails:
                result_payload["all_emails_found"] = _all_emails
            return result_payload

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
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                        "Upgrade-Insecure-Requests": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"macOS"',
                    },
                    request_timeout=15.0,
                    follow_redirects=True,
                    max_redirects=5,
                    decompress_response=True,
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

    # ── key_rotation ──────────────────────────────────────────────────────── #
    elif skill == "key_rotation":
        import json as _json

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

        if action == "check_status":
            try:
                # Check mempool first
                mempool_hit = await config.mongo.async_db.miner_transactions.find_one(
                    {"public_key_hash": address},
                    {"_id": 0, "id": 1, "prerotated_key_hash": 1},
                )
                if mempool_hit:
                    return {
                        "ok": True,
                        "address": address,
                        "spent": True,
                        "source": "mempool",
                        "txid": mempool_hit.get("id", ""),
                    }
                # Check confirmed blockchain
                chain_hit = await config.mongo.async_db.blocks.find_one(
                    {"transactions": {"$elemMatch": {"public_key_hash": address}}},
                    {"_id": 0, "transactions.$": 1},
                )
                if chain_hit:
                    txns = chain_hit.get("transactions", [])
                    txn = txns[0] if txns else {}
                    return {
                        "ok": True,
                        "address": address,
                        "spent": True,
                        "source": "blockchain",
                        "txid": txn.get("id", ""),
                    }
                return {"ok": True, "address": address, "spent": False, "source": None}
            except Exception as exc:
                return {"ok": False, "error": str(exc)[:200]}

        elif action == "rotate":
            second_factor = context.get("key_rotation_second_factor", "")
            if not second_factor:
                return {
                    "ok": False,
                    "error": (
                        "second_factor not configured — provide it in the agent request body "
                        "as 'key_rotation_second_factor'."
                    ),
                }
            relationship = str(params.get("relationship") or "")
            # Call the rotation logic directly (avoids loopback HTTP call)
            try:
                import hashlib as _hashlib
                import time as _time

                from bip32utils import BIP32Key as _BIP32Key
                from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH
                from coincurve import PrivateKey as _CCP
                from mnemonic import Mnemonic as _Mnemonic

                from plugins.keyrotation.handlers import derive_secure_path
                from yadacoin.core.keyeventlog import KeyEventLog
                from yadacoin.core.transaction import Transaction
                from yadacoin.core.transactionutils import TU

                seed = getattr(config, "seed", "") or ""
                if not seed:
                    return {"ok": False, "error": "seed not configured in config.json"}

                _mn = _Mnemonic("english")
                _entropy = _mn.to_entropy(seed)
                _bip32_root = _BIP32Key.fromEntropy(_entropy)
                _root_priv = _bip32_root.PrivateKey()
                _root_cc = _bip32_root.ChainCode()

                # Build KEL including mempool entries to determine current depth.
                # public_key is the CURRENT signer (K_n); the pre-committed next
                # signer (K_{n+1}) is latest.prerotated_key_hash.
                kel = await KeyEventLog.build_from_public_key(public_key)
                if not kel:
                    return {
                        "ok": False,
                        "error": "no key event log found for public_key",
                    }

                latest = kel[-1]

                # Derive K_{n+1} (the pre-committed next signer) from root + second_factor.
                # Walk len(kel) steps: root → K0 → K1 → … → K_{n+1}
                _n = len(kel)
                _cur = derive_secure_path(_root_priv, _root_cc, second_factor)  # K0
                for _i in range(_n):
                    _cur = derive_secure_path(
                        _cur["private_key"], _cur["chain_code"], second_factor
                    )
                # _cur is now K_{n+1} — verify second factor by checking its address
                _next_priv_obj = _CCP(_cur["private_key"])
                _next_pub_bytes = _next_priv_obj.public_key.format(compressed=True)
                _next_pub_hex = _next_pub_bytes.hex()
                address = str(_P2PKH.from_pubkey(_next_pub_bytes))  # K_{n+1}'s address
                if address != latest.prerotated_key_hash:
                    return {"ok": False, "error": "second factor is incorrect"}

                # _cur = K_{n+1} (signs the rotation txn)
                # Derive K_{n+2} (child) and K_{n+3} (grandchild)
                _child = derive_secure_path(
                    _cur["private_key"], _cur["chain_code"], second_factor
                )
                _child_priv = _CCP(_child["private_key"])
                _child_pub_bytes = _child_priv.public_key.format(compressed=True)
                _child_pub_hex = _child_pub_bytes.hex()
                _child_address = str(_P2PKH.from_pubkey(_child_pub_bytes))

                _grandchild = derive_secure_path(
                    _child["private_key"], _child["chain_code"], second_factor
                )
                _gc_priv = _CCP(_grandchild["private_key"])
                _gc_pub_bytes = _gc_priv.public_key.format(compressed=True)
                _gc_pub_bytes.hex()
                _gc_address = str(_P2PKH.from_pubkey(_gc_pub_bytes))

                # public_key for the transaction = K_{n+1}'s pubkey (the signer)
                # prev_public_key_hash = K_n's address (the current signer = latest.public_key_hash)
                public_key = _next_pub_hex
                _prev_public_key_hash = latest.public_key_hash
                _rel_hash = (
                    _hashlib.sha256(relationship.encode()).digest().hex()
                    if relationship
                    else ""
                )
                _now = int(_time.time())

                # Build full outputs list: rotation output + any custom outputs from params
                _custom_outputs = [
                    {"to": str(o.get("to", "")), "value": float(o.get("value", 0))}
                    for o in (params.get("outputs") or [])
                ]
                _all_outputs = [{"to": _child_address, "value": 0.0}] + _custom_outputs

                # Confirming txn needed if relationship is set OR any output goes
                # to an address other than this txn's own prerotated_key_hash (_child_address).
                _output_outside_kel = any(
                    str(o.get("to", "")) != _child_address for o in _all_outputs
                )
                _needs_confirming = bool(relationship) or _output_outside_kel

                txn = Transaction(
                    txn_time=_now,
                    public_key=public_key,
                    outputs=_all_outputs,
                    inputs=[],
                    fee=0.0,
                    masternode_fee=0.0,
                    version=7,
                    prerotated_key_hash=_child_address,
                    twice_prerotated_key_hash=_gc_address,
                    public_key_hash=address,
                    prev_public_key_hash=_prev_public_key_hash,
                    relationship=relationship,
                    relationship_hash=_rel_hash,
                    rid="",
                    dh_public_key="",
                )
                txn.hash = await txn.generate_hash()
                txn.transaction_signature = TU.generate_signature_with_private_key(
                    _cur["private_key"].hex(), txn.hash
                )
                await config.mongo.async_db.miner_transactions.replace_one(
                    {"id": txn.transaction_signature}, txn.to_dict(), upsert=True
                )

                # Build confirming txn if relationship set OR outputs include an external address
                confirming_txn = None
                if _needs_confirming:
                    _ggc = derive_secure_path(
                        _grandchild["private_key"],
                        _grandchild["chain_code"],
                        second_factor,
                    )
                    _ggc_pub_bytes = _CCP(_ggc["private_key"]).public_key.format(
                        compressed=True
                    )
                    _ggc_address = str(_P2PKH.from_pubkey(_ggc_pub_bytes))

                    confirming_txn = Transaction(
                        txn_time=_now,
                        public_key=_child_pub_hex,
                        outputs=[{"to": _gc_address, "value": 0.0}],
                        inputs=[],
                        fee=0.0,
                        masternode_fee=0.0,
                        version=7,
                        prerotated_key_hash=_gc_address,
                        twice_prerotated_key_hash=_ggc_address,
                        public_key_hash=_child_address,
                        prev_public_key_hash=address,
                        relationship="",
                        relationship_hash="",
                        rid="",
                        dh_public_key="",
                    )
                    confirming_txn.hash = await confirming_txn.generate_hash()
                    confirming_txn.transaction_signature = (
                        TU.generate_signature_with_private_key(
                            _child["private_key"].hex(), confirming_txn.hash
                        )
                    )
                    await config.mongo.async_db.miner_transactions.replace_one(
                        {"id": confirming_txn.transaction_signature},
                        confirming_txn.to_dict(),
                        upsert=True,
                    )

                return {
                    "ok": True,
                    "new_address": _child_address,
                    "new_public_key": _child_pub_hex,
                    "txid": txn.transaction_signature,
                    **(
                        {"confirming_txid": confirming_txn.transaction_signature}
                        if confirming_txn
                        else {}
                    ),
                }
            except Exception as exc:
                return {"ok": False, "error": str(exc)[:300]}

    return {"ok": False, "error": f"Unknown skill/action: {skill}/{action}"}
