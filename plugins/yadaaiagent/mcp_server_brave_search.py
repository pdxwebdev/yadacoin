"""
Brave Search MCP Server
=======================
Exposes Brave Search as MCP tools over the streamable-http transport.
Useful as a standalone search service for any agent that needs current
web or local business results.

Install:
    pip install "fastmcp>=2.0" httpx

Run:
    BRAVE_API_KEY=your_key python plugins/yadaaiagent/mcp_server_brave_search.py
    # or:
    BRAVE_API_KEY=your_key uvx fastmcp run plugins/yadaaiagent/mcp_server_brave_search.py \
        --transport streamable-http --port 8020

Then point the YadaCoin node at it:
    export BRAVE_SEARCH_MCP_ENDPOINT=http://localhost:8020/mcp

Get a free Brave Search API key at:
    https://brave.com/search/api/

Environment variables:
    BRAVE_API_KEY          — Brave Search API subscription token (required)
    BRAVE_SEARCH_MCP_PORT  — listening port (default: 8020)
"""

import os
from typing import Optional

import fastmcp
import httpx

mcp = fastmcp.FastMCP("brave-search")

_BRAVE_BASE = "https://api.search.brave.com/res/v1"
_DEFAULT_COUNT = 5


def _get_api_key() -> str:
    key = os.environ.get("BRAVE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "BRAVE_API_KEY environment variable is not set. "
            "Get a free key at https://brave.com/search/api/"
        )
    return key


@mcp.tool()
def web_search(
    query: str, count: Optional[int] = 5, freshness: Optional[str] = None
) -> dict:
    """
    Search the web using Brave Search and return top results.

    Args:
        query: The search query string.
        count: Number of results to return (1-20, default 5).
        freshness: Filter by recency — 'pd' (past day), 'pw' (past week),
                   'pm' (past month), 'py' (past year). Omit for all time.

    Returns a dict with a 'results' list, each item having:
        title, url, description
    """
    api_key = _get_api_key()
    count = max(1, min(20, int(count or _DEFAULT_COUNT)))

    params: dict = {
        "q": query,
        "count": count,
        "text_decorations": "false",
        "search_lang": "en",
        "safesearch": "moderate",
    }
    if freshness:
        params["freshness"] = freshness

    try:
        resp = httpx.get(
            f"{_BRAVE_BASE}/web/search",
            params=params,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("web", {}).get("results", [])
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("description", ""),
            }
            for r in raw[:count]
        ]
        return {"query": query, "results": results}
    except httpx.HTTPStatusError as exc:
        return {"error": f"Brave API returned {exc.response.status_code}"}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def local_search(
    query: str,
    location: Optional[str] = None,
    count: Optional[int] = 5,
) -> dict:
    """
    Search for local businesses and places using Brave Local Search.

    Args:
        query: The search query, e.g. 'coffee shops', 'dentist near me'.
        location: Optional location hint, e.g. 'New York, NY'.
        count: Number of results (1-20, default 5).

    Returns a dict with a 'results' list, each item having:
        name, address, phone, rating, url
    """
    api_key = _get_api_key()
    count = max(1, min(20, int(count or _DEFAULT_COUNT)))

    q = f"{query} {location}".strip() if location else query

    params: dict = {
        "q": q,
        "count": count,
        "text_decorations": "false",
        "search_lang": "en",
        "safesearch": "moderate",
        "result_filter": "locations",
    }

    try:
        resp = httpx.get(
            f"{_BRAVE_BASE}/web/search",
            params=params,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        locations = data.get("locations", {}).get("results", [])
        # Fall back to web results if no local results
        if not locations:
            web_results = data.get("web", {}).get("results", [])
            return {
                "query": q,
                "results": [
                    {
                        "name": r.get("title", ""),
                        "url": r.get("url", ""),
                        "description": r.get("description", ""),
                    }
                    for r in web_results[:count]
                ],
                "note": "No local results found; showing web results instead.",
            }
        results = [
            {
                "name": r.get("title", ""),
                "address": r.get("address", {}).get("streetAddress", ""),
                "phone": r.get("phone", ""),
                "rating": r.get("rating", {}).get("ratingValue"),
                "url": r.get("url", ""),
            }
            for r in locations[:count]
        ]
        return {"query": q, "results": results}
    except httpx.HTTPStatusError as exc:
        return {"error": f"Brave API returned {exc.response.status_code}"}
    except Exception as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    port = int(os.environ.get("BRAVE_SEARCH_MCP_PORT", "8020"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
