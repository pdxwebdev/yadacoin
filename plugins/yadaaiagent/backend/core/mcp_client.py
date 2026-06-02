"""mcp_client.py — MCP 2025-03-26 streamable-http transport client."""
import json

from tornado.httpclient import AsyncHTTPClient, HTTPRequest


class MCPClient:
    """
    Lightweight async MCP client for the streamable-http transport.
    Uses Tornado's AsyncHTTPClient so it works inside Tornado's IOLoop.

    Usage:
        async with MCPClient("http://localhost:8010/mcp") as client:
            result = await client.call_tool("check_availability", {"day": "monday"})
    """

    def __init__(self, endpoint: str, timeout: float = 30.0):
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self._session_id = None  # type: str
        self._http = AsyncHTTPClient()

    async def __aenter__(self):
        await self._initialize()
        return self

    async def __aexit__(self, *_):
        pass  # HTTP transport is stateless; nothing to close

    async def _rpc(self, method: str, params: dict, req_id: int = 1) -> dict:
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params,
            }
        )
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        req = HTTPRequest(
            url=self.endpoint,
            method="POST",
            headers=headers,
            body=body,
            request_timeout=self.timeout,
        )
        resp = await self._http.fetch(req, raise_error=False)
        if resp.code not in (200, 202):
            raise RuntimeError(
                f"MCP server returned HTTP {resp.code}: "
                f"{resp.body.decode('utf-8', errors='replace')[:200]}"
            )

        # Capture session id if the server issued one
        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            self._session_id = sid

        # Handle SSE envelope (text/event-stream with a single JSON-RPC event)
        ct = resp.headers.get("Content-Type", "")
        raw = resp.body.decode("utf-8", errors="replace").strip()
        if "text/event-stream" in ct:
            # Parse: "data: {...}\n\n"
            for line in raw.splitlines():
                if line.startswith("data:"):
                    raw = line[5:].strip()
                    break

        return json.loads(raw)

    async def _initialize(self):
        """Send MCP initialize handshake."""
        resp = await self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "yadacoin-agent", "version": "1.0"},
            },
        )
        if "error" in resp:
            raise RuntimeError(f"MCP initialize failed: {resp['error']}")
        # Send initialized notification (fire-and-forget — ignore response)
        try:
            notify_body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                }
            )
            headers = {"Content-Type": "application/json"}
            if self._session_id:
                headers["Mcp-Session-Id"] = self._session_id
            await self._http.fetch(
                HTTPRequest(
                    url=self.endpoint,
                    method="POST",
                    headers=headers,
                    body=notify_body,
                    request_timeout=5.0,
                ),
                raise_error=False,
            )
        except Exception:
            pass

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Call a named tool on the MCP server. Returns the tool result dict."""
        resp = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        if "error" in resp:
            return {"error": resp["error"].get("message", str(resp["error"]))}
        result = resp.get("result", {})
        # MCP result: {"content": [{"type": "text", "text": "..."}]}
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            try:
                return json.loads(content[0]["text"])
            except Exception:
                return {"text": content[0]["text"]}
        return result

    @staticmethod
    def make_impl(endpoint: str, tool_names: list[str], confirm_tool: str) -> dict:
        """
        Build a tool_impl dict whose callables are async functions that call
        the MCP server at `endpoint`.  Drop-in replacement for a mock impl dict.
        """

        def _make_caller(name: str):
            async def _caller(args: dict, scope: dict) -> dict:
                async with MCPClient(endpoint) as client:
                    result = await client.call_tool(name, args)
                    # If this is the confirm tool, ensure 'confirmed' key exists
                    if name == confirm_tool and "confirmation" in result:
                        result.setdefault("confirmed", True)
                    return result

            _caller.__name__ = name
            return _caller

        return {name: _make_caller(name) for name in tool_names}


# ── Agent type registry ───────────────────────────────────────────────────────
# Each entry describes an agent type available in the UI.
# Keys used by the SPA: id, label, description, authorizationType, fields, services
#
# fields: list of {key, label, type} — the scope fields the agent collects.
# services: list of vendor service ids that can fulfil this agent type's requests.
