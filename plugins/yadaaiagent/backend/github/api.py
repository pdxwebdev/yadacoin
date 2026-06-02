"""github_api.py — Authenticated GitHub REST API async helpers."""
import json
import urllib.parse as _oauthparse

from tornado.httpclient import AsyncHTTPClient, HTTPRequest


async def _github_api_get(access_token: str, path: str, params=None) -> dict:
    """Make an authenticated GET request to the GitHub REST API."""
    client = AsyncHTTPClient()
    url = f"https://api.github.com{path}"
    if params:
        url += "?" + _oauthparse.urlencode(params)
    req = HTTPRequest(
        url=url,
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "YadaCoin-AI-Agent/1.0",
        },
        request_timeout=15.0,
    )
    resp = await client.fetch(req, raise_error=False)
    body = resp.body.decode("utf-8", errors="replace")
    if resp.code not in (200, 201, 204):
        raise ValueError(f"GitHub API {resp.code}: {body[:200]}")
    return json.loads(body) if body.strip() else {}


async def _github_api_post(access_token: str, path: str, payload: dict) -> dict:
    """Make an authenticated POST request to the GitHub REST API."""
    client = AsyncHTTPClient()
    req = HTTPRequest(
        url=f"https://api.github.com{path}",
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "YadaCoin-AI-Agent/1.0",
        },
        body=json.dumps(payload),
        request_timeout=15.0,
    )
    resp = await client.fetch(req, raise_error=False)
    body = resp.body.decode("utf-8", errors="replace")
    if resp.code not in (200, 201, 204):
        raise ValueError(f"GitHub API {resp.code}: {body[:200]}")
    return json.loads(body) if body.strip() else {}
