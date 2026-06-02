"""msgraph_api.py — Authenticated Microsoft Graph REST API async helpers."""
import json
import urllib.parse as _oauthparse

from tornado.httpclient import AsyncHTTPClient, HTTPRequest


async def _msgraph_api_get(access_token: str, path: str, params=None) -> dict:
    """Make an authenticated GET request to the Microsoft Graph REST API."""
    client = AsyncHTTPClient()
    url = f"https://graph.microsoft.com/v1.0{path}"
    if params:
        url += "?" + _oauthparse.urlencode(params)
    req = HTTPRequest(
        url=url,
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        request_timeout=15.0,
    )
    resp = await client.fetch(req, raise_error=False)
    body = resp.body.decode("utf-8", errors="replace")
    if resp.code not in (200, 201, 204):
        raise ValueError(f"Graph API {resp.code}: {body[:200]}")
    return json.loads(body) if body.strip() else {}


async def _msgraph_api_post(access_token: str, path: str, payload: dict) -> dict:
    """Make an authenticated POST request to the Microsoft Graph REST API."""
    client = AsyncHTTPClient()
    req = HTTPRequest(
        url=f"https://graph.microsoft.com/v1.0{path}",
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        body=json.dumps(payload),
        request_timeout=15.0,
    )
    resp = await client.fetch(req, raise_error=False)
    body = resp.body.decode("utf-8", errors="replace")
    if resp.code not in (200, 201, 202, 204):
        raise ValueError(f"Graph API {resp.code}: {body[:200]}")
    return json.loads(body) if body.strip() else {}


async def _msgraph_api_delete(access_token: str, path: str) -> None:
    """Make an authenticated DELETE request to the Microsoft Graph REST API."""
    client = AsyncHTTPClient()
    req = HTTPRequest(
        url=f"https://graph.microsoft.com/v1.0{path}",
        method="DELETE",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        allow_nonstandard_methods=True,
        body=b"",
        request_timeout=15.0,
    )
    resp = await client.fetch(req, raise_error=False)
    if resp.code not in (200, 201, 202, 204):
        body = resp.body.decode("utf-8", errors="replace")
        raise ValueError(f"Graph API {resp.code}: {body[:200]}")


async def _msgraph_api_patch(access_token: str, path: str, payload: dict) -> dict:
    """Make an authenticated PATCH request to the Microsoft Graph REST API."""
    client = AsyncHTTPClient()
    req = HTTPRequest(
        url=f"https://graph.microsoft.com/v1.0{path}",
        method="PATCH",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        body=json.dumps(payload),
        request_timeout=15.0,
    )
    resp = await client.fetch(req, raise_error=False)
    body = resp.body.decode("utf-8", errors="replace")
    if resp.code not in (200, 201, 202, 204):
        raise ValueError(f"Graph API {resp.code}: {body[:200]}")
    return json.loads(body) if body.strip() else {}


# ── MCP client ────────────────────────────────────────────────────────────────
# Implements the MCP 2025-03-26 streamable-http transport (JSON-RPC 2.0).
# Compatible with servers created via fastmcp, the official mcp SDK, or any
# other MCP-compliant server running over HTTP.
#
# Each vendor can optionally declare:
#   "mcp_endpoint": "http://host:port/mcp"
# in _VENDOR_TOOLS.  When present, the tool impl callables are replaced
# at runtime with async wrappers that call the MCP server.
