"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

yadaaiagent — KEL-backed AI agent platform plugin.

Architecture:  human → KEL pre-commitment → challenge-response → external service

Flow
----
1. Operator visits /ai-agent-auth and initialises their key in localStorage.
2. They select an agent type and start a conversation; the agent collects the
   required fields for that agent type via multi-turn chat.
3. On approval the browser:
     a. Derives the next child key client-side (second_factor stays in browser).
     b. Broadcasts a rotation transaction with a structured JSON scope committed
        in the ``relationship`` field.
     c. Receives ``prerotated_private_key`` — the one-time agent credential.
4. The browser then does a challenge-response with each vendor service:
     a. GET /ai-agent-auth/api/vendor/<service>/challenge?public_key=<hex>
     b. Signs SHA256(challenge_utf8 + canonical_vp_bytes) client-side.
     c. POST /ai-agent-auth/api/vendor/<service>  {public_key, challenge, vp}
5. The server independently validates each VP against the KEL.

Endpoints
---------
GET  /ai-agent-auth                                — SPA shell
GET  /ai-agent-auth/api/agents                     — list registered agent types
GET  /ai-agent-auth/api/challenge                  — stateless HMAC challenge
POST /ai-agent-auth/api/chat                       — LLM proxy (agent_type aware)
POST /ai-agent-auth/api/travel                     — legacy combined travel endpoint
GET  /ai-agent-auth/api/vendor/<svc>/challenge     — per-vendor challenge
POST /ai-agent-auth/api/vendor/<svc>               — per-vendor VP booking
"""

import asyncio
import hashlib
import inspect
import json
import os
import re

import tornado.web
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from yadacoin_agent_auth import AgentAuthValidator, AuthError, YadaCoinNodeKelProvider

from yadacoin.http.base import BaseHandler

# ── Challenge secret ──────────────────────────────────────────────────────────
# Override with YADACOIN_AGENT_SECRET env-var in production.
_CHALLENGE_SECRET = os.environ.get(
    "YADACOIN_AGENT_SECRET", "yadacoin-demo-agent-secret-2026"
).encode("utf-8")

_validator = AgentAuthValidator(
    challenge_secret=_CHALLENGE_SECRET,
    kel_provider=YadaCoinNodeKelProvider(),
)


# ── MCP client ────────────────────────────────────────────────────────────────
# Implements the MCP 2025-03-26 streamable-http transport (JSON-RPC 2.0).
# Compatible with servers created via fastmcp, the official mcp SDK, or any
# other MCP-compliant server running over HTTP.
#
# Each vendor can optionally declare:
#   "mcp_endpoint": "http://host:port/mcp"
# in _VENDOR_TOOLS.  When present, the tool impl callables are replaced
# at runtime with async wrappers that call the MCP server.


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
        self._session_id: str | None = None
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

AGENT_TYPES = [
    {
        "id": "general",
        "label": "General Chat",
        "description": "Open-ended conversation. Ask anything — no structured booking flow.",
        "icon": "💬",
        "authorizationType": None,
        "fields": [],
        "services": [],
        "systemPrompt": (
            "You are a helpful AI assistant powered by the YadaCoin KEL identity system. "
            "Answer the user's questions conversationally.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your response",\n'
            '  "extracted": {},\n'
            '  "complete": false,\n'
            '  "detected_agent_type": "general"\n'
            "}\n"
            "detected_agent_type rules — change from 'general' when the user's intent clearly fits:\n"
            '- "travel": user mentions wanting to go somewhere, visit a destination, travel, '
            "take a trip, book a flight/hotel/car, or asks about travel arrangements. "
            "Examples: 'I want to go to Mexico', 'I'm planning a trip to Paris', 'book me a flight'\n"
            '- "legal": user explicitly asks to DRAFT, REVIEW, or get help with a legal document, '
            "contract, NDA, terms of service, or privacy policy\n"
            '- "ecommerce": user explicitly asks to ORDER, BUY, or purchase a physical product\n'
            "Keep detected_agent_type as 'general' for greetings, vague questions, or topics "
            "that don't clearly fit the above.\n"
            '- "agent_registration": user wants to register or list their AI agent on the blockchain, '
            "create a new agent entry, add an agent to the on-chain registry, or asks how to make "
            "their agent discoverable. Examples: 'register my agent', 'add my AI to the blockchain', "
            "'I want to list my agent'\n"
            '- "wallet_agent": user asks about their balance, wallet funds, YDA amount, '
            "transaction history, pending transactions, sending coins, transferring YDA, "
            "or wrapping/unwrapping tokens. "
            "Examples: 'what is my balance', 'show my transactions', 'send 5 YDA to ...'\n"
            "Keep detected_agent_type as 'general' for greetings, vague questions, or topics "
            "that don't clearly fit the above.\n"
            "complete MUST always be false."
        ),
    },
    {
        "id": "travel",
        "label": "Travel Booking",
        "description": "Book flights, hotels, and car rentals with KEL-backed agent credentials.",
        "icon": "✈️",
        "routing_hint": (
            "user mentions wanting to go somewhere, visit a destination, travel, "
            "take a trip, book a flight/hotel/car, or asks about travel arrangements. "
            "Examples: 'I want to go to Mexico', 'I'm planning a trip to Paris', 'book me a flight'"
        ),
        "authorizationType": "TravelBookingAuthorization",
        "fields": [
            {"key": "destination", "label": "Destination", "type": "text"},
            {"key": "checkin", "label": "Check-in", "type": "text"},
            {"key": "checkout", "label": "Check-out", "type": "text"},
            {
                "key": "services",
                "label": "Services",
                "type": "multiselect",
                "options": ["hotel", "flight", "car"],
            },
        ],
        "services": ["hotel", "flight", "car"],
        "systemPrompt": (
            "You are a travel booking assistant. Your ONLY job is to collect travel details.\n"
            "You CANNOT book anything, confirm any reservation, or process any payment.\n"
            "NEVER ask for credit card details, payment info, or personal identification.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "destination": "city/destination or null",\n'
            '    "checkin": "check-in date (e.g. May 10) or null",\n'
            '    "checkout": "check-out date (e.g. May 16) or null",\n'
            '    "services": ["hotel","flight","car"] subset or null\n'
            "  },\n"
            '  "complete": false,\n'
            '  "detected_agent_type": "travel"\n'
            "}\n"
            "Rules:\n"
            "- Only use service values: hotel, flight, car\n"
            '- If the user says "all": services=["hotel","flight","car"]\n'
            "- complete MUST be false unless ALL FOUR fields are known\n"
            '- For date ranges like "May 10-16": checkin="May 10", checkout="May 16"\n'
            "- When complete=true: summarise all details and say the operator will approve\n"
            "- If the user clearly wants something other than travel (e.g. therapy, legal help, shopping), set detected_agent_type to 'general'"
        ),
    },
    {
        "id": "legal",
        "label": "Legal Services",
        "description": "Request legal document drafting and review with scoped agent credentials.",
        "icon": "⚖️",
        "routing_hint": (
            "user explicitly asks to DRAFT, REVIEW, or get help with a legal document, "
            "contract, NDA, terms of service, or privacy policy. "
            "Examples: 'draft me an NDA', 'review this contract', 'I need a privacy policy'"
        ),
        "authorizationType": "LegalServiceAuthorization",
        "fields": [
            {
                "key": "serviceType",
                "label": "Service Type",
                "type": "select",
                "options": [
                    "contract_review",
                    "nda_draft",
                    "terms_of_service",
                    "privacy_policy",
                ],
            },
            {"key": "jurisdiction", "label": "Jurisdiction", "type": "text"},
            {"key": "deadline", "label": "Deadline", "type": "text"},
        ],
        "services": ["legal"],
        "systemPrompt": (
            "You are a legal services intake assistant. Your ONLY job is to collect details "
            "for a legal services request. You CANNOT provide legal advice or draft documents.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "serviceType": "contract_review|nda_draft|terms_of_service|privacy_policy or null",\n'
            '    "jurisdiction": "jurisdiction/country or null",\n'
            '    "deadline": "deadline date or null"\n'
            "  },\n"
            '  "complete": false,\n'
            '  "detected_agent_type": "legal"\n'
            "}\n"
            "complete=true only when ALL THREE fields are known.\n"
            "If the user clearly wants something other than legal services, set detected_agent_type to 'general'."
        ),
    },
    {
        "id": "ecommerce",
        "label": "E-Commerce",
        "description": "Authorise an AI agent to place orders on your behalf with scoped spending limits.",
        "icon": "🛒",
        "routing_hint": (
            "user explicitly asks to ORDER, BUY, or purchase a physical product. "
            "Examples: 'order me some shoes', 'buy this item', 'I want to purchase something'"
        ),
        "authorizationType": "ECommerceAuthorization",
        "fields": [
            {"key": "items", "label": "Items", "type": "text"},
            {"key": "maxAmount", "label": "Max Spend (USD)", "type": "number"},
            {"key": "deliveryAddress", "label": "Delivery Address", "type": "text"},
        ],
        "services": ["ecommerce"],
        "systemPrompt": (
            "You are an e-commerce shopping assistant. Collect the items to purchase, "
            "maximum spend limit, and delivery address. You CANNOT place orders yourself.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "items": "comma-separated item list or null",\n'
            '    "maxAmount": number or null,\n'
            '    "deliveryAddress": "full address or null"\n'
            "  },\n"
            '  "complete": false,\n'
            '  "detected_agent_type": "ecommerce"\n'
            "}\n"
            "complete=true only when ALL THREE fields are known.\n"
            "If the user clearly wants something other than shopping/orders, set detected_agent_type to 'general'."
        ),
    },
    {
        "id": "agent_registration",
        "label": "Register AI Agent",
        "description": "Register your AI agent on the YadaCoin blockchain so others can discover it automatically.",
        "icon": "📡",
        "authorizationType": "AgentRegistration",
        "fields": [
            {"key": "label", "label": "Agent Label", "type": "text"},
            {"key": "description", "label": "Description", "type": "text"},
            {"key": "agent_type", "label": "Agent Type", "type": "text"},
            {"key": "capabilities", "label": "Capabilities", "type": "text"},
            {"key": "endpoint_url", "label": "Endpoint URL", "type": "text"},
            {"key": "icon", "label": "Icon", "type": "text"},
        ],
        "services": [],
        "systemPrompt": (
            "You are an AI agent registration assistant for YadaCoin. Your job is to collect "
            "the details needed to register an AI agent on the blockchain so others can discover it.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "label": "agent name/label or null",\n'
            '    "description": "what the agent does or null",\n'
            '    "agent_type": "general|travel|legal|ecommerce or null",\n'
            '    "capabilities": "comma-separated keyword list or null",\n'
            '    "endpoint_url": "full URL or null",\n'
            '    "icon": "single emoji or null"\n'
            "  },\n"
            '  "complete": false\n'
            "}\n"
            "Rules:\n"
            "- agent_type MUST be one of: general, travel, legal, ecommerce\n"
            "- capabilities should be a comma-separated list of intent keywords (e.g. 'travel, flight, hotel')\n"
            "- endpoint_url must be a valid URL starting with http:// or https://\n"
            "- If the user doesn't provide an icon, suggest '🤖' as default\n"
            "- complete=true only when label, agent_type, capabilities, AND endpoint_url are all known\n"
            "- When complete=true, summarise all the details clearly and tell the operator "
            "they can approve to broadcast the registration on-chain\n"
            "- If the user clearly wants something other than registering an agent, set detected_agent_type to 'general'"
        ),
    },
    {
        "id": "wallet_agent",
        "label": "Wallet Assistant",
        "description": "Check balance, view on-chain and pending transaction history, send YDA, and wrap YDA to other chains.",
        "icon": "💰",
        "routing_hint": (
            "user asks about their balance, wallet, YDA amount, funds, transactions, "
            "transaction history, pending transactions, sending coins, transferring YDA, "
            "or wrapping/unwrapping tokens. "
            "Examples: 'what is my balance', 'show my transactions', 'send 5 YDA to ...', 'wrap 10 YDA to 0x...'"
        ),
        "authorizationType": "WalletAuthorization",
        "fields": [
            {
                "key": "action",
                "label": "Action",
                "type": "select",
                "options": ["send", "balance", "history", "pending", "wrap"],
            },
            {"key": "to_address", "label": "Recipient Address", "type": "text"},
            {"key": "amount", "label": "Amount (YDA)", "type": "number"},
            {
                "key": "eth_address",
                "label": "Ethereum Address (for wrap)",
                "type": "text",
            },
        ],
        "services": ["wallet"],
        "systemPrompt": (
            "You are a YadaCoin wallet assistant. You help users check their balance, "
            "view transaction history, send YDA, and wrap YDA to other chains.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "action": "send|get_balance|get_transactions|get_pending|wrap or null",\n'
            '    "to_address": "recipient YDA address or null",\n'
            '    "amount": number or null,\n'
            '    "eth_address": "0x Ethereum address for wrap, or null"\n'
            "  },\n"
            '  "complete": false,\n'
            '  "detected_agent_type": "wallet_agent"\n'
            "}\n"
            "Rules:\n"
            "- For balance requests: set action='get_balance', complete=false — "
            "the system will fetch and display the balance automatically.\n"
            "- For transaction history requests: set action='get_transactions', complete=false.\n"
            "- For pending transactions: set action='get_pending', complete=false.\n"
            "- For wrapping YDA: set action='wrap'. Collect amount AND eth_address (0x Ethereum address). "
            "The wrap sends YDA to the bridge address with the Ethereum address in the relationship field. "
            "Ask for confirmation before setting complete=true. "
            "Set complete=true only when BOTH amount and eth_address are known AND the user has confirmed.\n"
            "- For send: collect to_address AND amount. "
            "Ask for confirmation before setting complete=true. "
            "Set complete=true only when BOTH fields are known AND the user has confirmed.\n"
            "- NEVER ask for private keys, seeds, or passwords.\n"
            "- If the user wants something other than wallet operations, "
            "set detected_agent_type to 'general'."
        ),
    },
    {
        "id": "node_config",
        "label": "Node Configuration",
        "description": "Change a setting in the active node config.json and restart the node.",
        "icon": "⚙️",
        "routing_hint": (
            "user wants to change a node setting, update a config value, modify node configuration, "
            "or asks about changing combined_address, pool settings, peer limits, or any node parameter. "
            "Examples: 'change my combined address', 'update pool_take', 'set max_miners to 50'"
        ),
        "authorizationType": "NodeConfigAuthorization",
        "fields": [
            {"key": "config_key", "label": "Setting Name", "type": "text"},
            {"key": "new_value", "label": "New Value", "type": "text"},
        ],
        "services": ["NodeConfigAuthorization"],
        "systemPrompt": (
            "You are a YadaCoin node configuration assistant. "
            "Help the user change a setting in their active node config.json. "
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "config_key": "setting name or null",\n'
            '    "new_value": "new value (as a string) or null",\n'
            '    "confirmed": false\n'
            "  },\n"
            '  "complete": false,\n'
            '  "detected_agent_type": "node_config"\n'
            "}\n"
            "Allowed settings (from README):\n"
            "- combined_address (string): Wallet address to consolidate transactions. Default: node address\n"
            "- credits_per_share (integer): Credits earned per mining share. Default: 5\n"
            "- shares_required (boolean): Require shares to use node apps. Default: false\n"
            "- pool_payout (boolean): Enable pool payouts to miners. Default: false\n"
            "- pool_take (decimal): Pool operator cut as decimal (0.01 = 1%). Default: 0.01\n"
            "- payout_frequency (integer): Blocks between payouts. Default: 6\n"
            "- max_miners (integer): Max concurrent miners. Default: 100\n"
            "- max_peers (integer): Max peers that can connect. Default: 20\n"
            "- pool_diff (integer): Pool share difficulty. Default: 100000\n"
            "- stratum_pool_port (integer): Stratum pool port. Default: 3333\n"
            "- transactions_combining_wait (integer): Seconds before combining UTXOs. Default: 3600\n"
            "- restrict_graph_api (boolean): Restrict graph API access. Default: false\n"
            "- web_jwt_expiry (integer): JWT validity in seconds. Default: 23040\n"
            "- peers_wait (integer): Seconds between peer reconnect attempts. Default: 30\n"
            "- status_wait (integer): Seconds between status prints. Default: 10\n"
            "- block_checker_wait (integer): Seconds between block height checks. Default: 1\n"
            "- message_sender_wait (integer): Seconds between message retries. Default: 40\n"
            "- pool_payer_wait (integer): Seconds between payout runs. Default: 110\n"
            "- cache_validator_wait (integer): Seconds between cache validation. Default: 3550\n"
            "- mempool_cleaner_wait (integer): Seconds between mempool cleans. Default: 1200\n"
            "- nonce_processor_wait (integer): Seconds between nonce queue checks. Default: 1\n"
            "- mongo_query_timeout (integer): Max MongoDB query time in ms. Default: 30000\n"
            "- http_request_timeout (integer): Max HTTP request time in ms. Default: 3000\n"
            "- masternode_fee_minimum (integer): Min YDA fee for masternode services. Default: 1\n"
            "- balance_min_utxo (integer): Min UTXO amount to include in balance. Default: 1\n"
            "- activate_peerjs (boolean): Activate PeerJS p2p broker. Default: false\n"
            "- extended_status (boolean): Enable extended status. Default: false\n"
            "- log_health_status (boolean): Log health status. Default: false\n"
            "- docker_debug (boolean): Log docker resource usage. Default: false\n"
            "- asyncio_debug (boolean): Log slow asyncio tasks. Default: false\n"
            "- network_seeds (list): List of seed node addresses.\n"
            "- network_service_providers (list): List of service provider node addresses.\n"
            "- network_seed_gateways (list): List of seed gateway node addresses.\n"
            "- serve_host (string): Host address the node listens on for inbound peer connections. Default: 0.0.0.0\n"
            "- serve_port (integer): Port the node listens on for inbound peer connections. Default: 8005\n"
            "- peer_host (string): Public hostname or IP this node advertises to peers. Default: node's public IP\n"
            "- peer_port (integer): Port this node advertises to peers. Default: 8004\n"
            "Rules:\n"
            "- Only allow settings from the list above. Refuse requests for private_key, seed, etc.\n"
            "- For list-type settings (network_seeds, network_service_providers, "
            "  network_seed_gateways): new_value must be a valid JSON array string containing "
            "  ALL entries for the list (not just the new item to add). If the user wants to "
            "  ADD an entry, include the new entry in the array and ask the user to confirm "
            "  it's the complete new list.\n"
            "- Ask for confirmation before setting complete=true\n"
            "- confirmed must be true (the user explicitly agreed) before complete=true\n"
            "- complete=true only when config_key, new_value, AND confirmed=true are all set\n"
            "- When complete=true, set reply to a brief message like 'Applying that change now.' "
            "  Do NOT mention key rotation, authorization, or KEL transactions in your replies.\n"
            "- If the user wants something other than config changes, set detected_agent_type to 'general'"
        ),
    },
]

# Index by id for fast lookup
_AGENT_TYPE_MAP = {a["id"]: a for a in AGENT_TYPES}


# ── On-chain agent discovery helpers ─────────────────────────────────────────


async def _fetch_onchain_agents(config) -> list:
    """Query confirmed blocks + mempool for AgentAnnouncement transactions.

    Returns a list of unique agent announcement blobs.  The most-recently-
    confirmed version of each agent_id wins; mempool entries fill in agents
    not yet included in a block.
    """
    agents: dict = {}
    try:
        cursor = (
            config.mongo.async_db.blocks.find(
                {
                    "transactions": {
                        "$elemMatch": {"relationship.agent": {"$exists": True}}
                    }
                },
                {"index": 1, "transactions": 1},
            )
            .sort("index", -1)
            .limit(500)
        )
        async for block in cursor:
            for txn in block.get("transactions", []):
                rel = txn.get("relationship")
                if not isinstance(rel, dict):
                    continue
                blob = rel.get("agent")
                if not blob or not isinstance(blob, dict):
                    continue
                aid = blob.get("agent_id", "")
                if aid and aid not in agents:
                    agents[aid] = blob

        # Mempool — fill in any agents not yet confirmed in a block
        mcursor = config.mongo.async_db.miner_transactions.find(
            {"relationship.agent": {"$exists": True}},
            {"relationship": 1},
        )
        async for txn in mcursor:
            rel = txn.get("relationship")
            if not isinstance(rel, dict):
                continue
            blob = rel.get("agent")
            if not blob or not isinstance(blob, dict):
                continue
            aid = blob.get("agent_id", "")
            if aid and aid not in agents:
                agents[aid] = blob

    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("_fetch_onchain_agents: %s", exc)

    return list(agents.values())


def _sanitize_messages(messages: list) -> list:
    """Ensure every message has a string content field.

    Some LLM APIs reject requests where content is null, a number, or a nested
    object.  Coerce anything non-string to its JSON or str() representation so
    the upstream call never fails with a type error.
    """
    sanitized = []
    for m in messages:
        content = m.get("content")
        if not isinstance(content, str):
            if content is None:
                content = ""
            elif isinstance(content, (dict, list)):
                content = json.dumps(content, separators=(",", ":"))
            else:
                content = str(content)
        sanitized.append({**m, "content": content})
    return sanitized


import re as _re

# Patterns that commonly appear in prompt-injection payloads.
# We don't try to enumerate all attacks — we remove structural markers that
# could break out of the data context and into the instruction context.
_INJECTION_PATTERNS = _re.compile(
    r"(system\s*:|user\s*:|assistant\s*:|<\s*/?\s*(s|inst|sys)\s*>|\[INST\]|\[/INST\]|"
    r"ignore\s+(previous|all|prior)\s+instructions?|"
    r"you\s+are\s+now|from\s+now\s+on\s+you|your\s+new\s+(role|instructions?)|"
    r"disregard\s+(your|the|all)|forget\s+(your|the|all|previous))",
    _re.IGNORECASE,
)


def _sanitize_onchain_str(value, max_len: int = 200) -> str:
    """Sanitize a string coming from on-chain before inserting into a prompt.

    - Collapses all whitespace/newlines to single spaces (prevents newline injection)
    - Strips known prompt-injection patterns
    - Truncates to max_len characters
    """
    if not isinstance(value, str):
        value = str(value)
    # Collapse newlines/tabs/runs of whitespace
    value = " ".join(value.split())
    # Remove injection patterns
    value = _INJECTION_PATTERNS.sub("[…]", value)
    # Truncate
    return value[:max_len]


def _build_generic_intake_prompt(agent_type_id: str, agents: list) -> str:
    """Generate a generic intake system prompt for an on-chain-only agent type."""
    rep = agents[0] if agents else {}
    label = _sanitize_onchain_str(
        rep.get("label") or agent_type_id.replace("_", " ").title(), 80
    )
    description = _sanitize_onchain_str(rep.get("description", ""), 300)
    caps = rep.get("capabilities") or []
    cap_str = (
        ", ".join(_sanitize_onchain_str(str(c), 40) for c in caps[:8]) if caps else ""
    )
    # Sanitize agent_type_id itself — only allow alphanum + underscore
    safe_type_id = _re.sub(r"[^a-z0-9_]", "_", agent_type_id.lower())[:64]
    return (
        f"You are an intake assistant for {label}. "
        + (f"{description} " if description else "")
        + "Understand what the user needs and collect their preferences "
        "ONE question at a time.\n"
        "ALWAYS respond with ONLY a valid JSON object:\n"
        "{\n"
        '  "reply": "your conversational response",\n'
        '  "extracted": {},\n'
        '  "complete": false,\n'
        f'  "detected_agent_type": "{safe_type_id}"\n'
        "}\n"
        + (f"Relevant topics: {cap_str}.\n" if cap_str else "")
        + "complete=true only when you have gathered enough information to proceed.\n"
        + "If the user clearly wants something outside this domain, set detected_agent_type to 'general'."
    )


def _build_general_prompt_dynamic(onchain_agents: list) -> str:
    """Build the general agent system prompt, injecting all known agent types.

    Hardcoded non-meta types (travel, legal, etc.) are always included.
    On-chain types not already in AGENT_TYPES are layered in automatically.
    Each AGENT_TYPES entry may provide a ``routing_hint`` string for richer
    detection rules; on-chain-only types fall back to description/capabilities.
    """
    _META_IDS = {"general", "agent_registration"}

    # Start with hardcoded non-meta types — preserve ordering
    type_entries: dict = {}  # type_id -> {label, routing_hint}
    for entry in AGENT_TYPES:
        if entry["id"] not in _META_IDS:
            hint = entry.get("routing_hint") or entry.get("description") or ""
            type_entries[entry["id"]] = {"label": entry["label"], "hint": hint}

    # Layer in on-chain types not already present
    for blob in onchain_agents:
        at = blob.get("agent_type") or "general"
        # Sanitize agent_type key — only allow alphanum + underscore
        at = _re.sub(r"[^a-z0-9_]", "_", at.lower())[:64]
        if at in _META_IDS or at in type_entries:
            continue
        caps = blob.get("capabilities") or []
        raw_hint = blob.get("description") or (
            ", ".join(str(c) for c in caps[:5]) if caps else ""
        )
        hint = _sanitize_onchain_str(raw_hint, 200)
        label = _sanitize_onchain_str(
            blob.get("label") or at.replace("_", " ").title(), 80
        )
        type_entries[at] = {"label": label, "hint": hint}

    lines = []
    for type_id, info in type_entries.items():
        line = (
            f'- "{type_id}": {info["hint"]}'
            if info["hint"]
            else f'- "{type_id}": {info["label"]}'
        )
        lines.append(line)

    types_block = "\n".join(lines) + "\n" if lines else ""
    return (
        "You are a helpful AI assistant powered by the YadaCoin KEL identity system. "
        "Answer the user's questions conversationally.\n"
        "ALWAYS respond with ONLY a valid JSON object:\n"
        "{\n"
        '  "reply": "your response",\n'
        '  "extracted": {},\n'
        '  "complete": false,\n'
        '  "detected_agent_type": "general"\n'
        "}\n"
        "detected_agent_type rules — change from 'general' when the user's intent clearly fits:\n"
        + types_block
        + '- "agent_registration": user wants to register or list their AI agent on the blockchain, '
        "create a new agent entry, add an agent to the on-chain registry, or asks how to make "
        "their agent discoverable. Examples: 'register my agent', 'add my AI to the blockchain', "
        "'I want to list my agent'\n"
        "Keep detected_agent_type as 'general' for greetings, vague questions, or topics "
        "that don't clearly fit the above.\n"
        "complete MUST always be false."
    )


# ── Vendor registry ───────────────────────────────────────────────────────────
# Maps service id → {name, available, confirmationPrefix}
# Add new services here; a VendorHandler subclass is auto-generated below.

_VENDOR_CHAT_INSTRUCTION = (
    "ALWAYS respond with ONLY a valid JSON object — no markdown, no extra text:\n"
    '{"reply": "your message to the customer", "complete": false, "exit_vendor": false}\n'
    "Set complete=true ONLY when you have received all needed answers and are "
    "ready to confirm the booking. When setting complete=true your reply must "
    "include a friendly booking confirmation message.\n"
    "Set exit_vendor=true (and complete=false) ONLY if the user clearly wants to stop "
    "this booking and switch to a completely different topic or service "
    "(e.g. therapy, travel, shopping, legal help). "
    "In that case reply with a brief acknowledgement such as "
    "'Sure, let me hand you back to the main assistant.'"
)

VENDOR_REGISTRY = {
    "flight": {
        "name": "SkyLink Airlines",
        "available": True,
        "prefix": "FLT",
        "vendorPrompt": (
            "You are the reservations agent for SkyLink Airlines. "
            "A customer has been securely verified via YadaCoin KEL identity. "
            "Collect their flight preferences ONE question at a time. "
            "Ask about: seat preference (window / middle / aisle), "
            "meal preference (standard / vegetarian / vegan / none), "
            "and extra checked baggage (yes / no). "
            "Do not ask about things already in their scope. "
            "\n" + _VENDOR_CHAT_INSTRUCTION
        ),
    },
    "hotel": {
        "name": "Grand Stay Hotels",
        "available": True,
        "prefix": "HTL",
        "vendorPrompt": (
            "You are the reservations agent for Grand Stay Hotels. "
            "A customer has been securely verified via YadaCoin KEL identity. "
            "Collect their room preferences ONE question at a time. "
            "Ask about: bed type (single king / double queen / twin beds), "
            "smoking or non-smoking room, "
            "and any special requests (early check-in, late check-out, etc.). "
            "Do not ask about things already in their scope. "
            "\n" + _VENDOR_CHAT_INSTRUCTION
        ),
    },
    "car": {
        "name": "DriveEasy Rentals",
        "available": True,
        "prefix": "CAR",
        "vendorPrompt": (
            "You are the rental agent for DriveEasy Rentals. "
            "A customer has been securely verified via YadaCoin KEL identity. "
            "Collect their rental preferences ONE question at a time. "
            "Ask about: vehicle size (economy / compact / standard / SUV / luxury), "
            "GPS add-on (yes / no), "
            "and additional driver (yes / no). "
            "Do not ask about things already in their scope. "
            "\n" + _VENDOR_CHAT_INSTRUCTION
        ),
    },
    "legal": {
        "name": "LexAI Legal",
        "available": True,
        "prefix": "LEX",
        "vendorPrompt": (
            "You are the intake agent for LexAI Legal. "
            "A customer has been securely verified via YadaCoin KEL identity. "
            "Collect intake details ONE question at a time. "
            "Ask about: governing law / jurisdiction preference, "
            "names of specific parties to include, "
            "and urgency level (standard 5 days / expedited 48 h / urgent same-day). "
            "Do not ask about things already in their scope. "
            "\n" + _VENDOR_CHAT_INSTRUCTION
        ),
    },
    "ecommerce": {
        "name": "QuickCart",
        "available": True,
        "prefix": "ORD",
        "vendorPrompt": (
            "You are the order agent for QuickCart. "
            "A customer has been securely verified via YadaCoin KEL identity. "
            "Collect order preferences ONE question at a time. "
            "Ask about: color / size / variant for each item, "
            "gift wrapping (yes / no), "
            "and delivery speed (standard / express / overnight). "
            "Do not ask about things already in their scope. "
            "\n" + _VENDOR_CHAT_INSTRUCTION
        ),
    },
}


def _gen_confirmation(service: str, seed: str) -> str:
    pfx = VENDOR_REGISTRY.get(service, {}).get("prefix", "SVC")
    h = hashlib.sha256(f"{seed}{service}".encode()).hexdigest()[:6].upper()
    return f"{pfx}-{h}"


def _did_web_id(config) -> str:
    """Derive a did:web identifier from the node's wallet_host_port."""
    from urllib.parse import urlparse

    parsed = urlparse(getattr(config, "wallet_host_port", "") or "")
    host = parsed.hostname or ""
    port = parsed.port
    if port and port not in (80, 443):
        return f"did:web:{host}%3A{port}"
    return f"did:web:{host}"


def _gen_booking_credential(
    service: str,
    holder_address: str,
    scope: dict,
    confirmation: str,
    vendor_name: str,
    booking_details=None,
    config=None,
) -> dict:
    """Return a signed W3C VC 2.0 Verifiable Credential for a completed booking."""
    import datetime

    from plugins.yadaaiagent.vc_support import BOOKING_V1_CONTEXT_URL, sign_credential

    subject = {
        "id": f"did:yadakel:{holder_address}",
        "service": service,
        "vendor": vendor_name,
        "confirmation": confirmation,
        "scope": scope,
    }
    if booking_details:
        # Strip internal fields; keep the human-readable booking data
        skip = {"confirmed", "confirmation"}
        subject["bookingDetails"] = {
            k: v for k, v in booking_details.items() if k not in skip
        }

    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Use did:web when config is present (resolvable); fall back to did:yadakel
    if config is not None:
        issuer_did = _did_web_id(config)
    else:
        issuer_did = f"did:yadakel:{service}"

    credential = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            BOOKING_V1_CONTEXT_URL,
        ],
        "id": f"urn:yadakel:booking:{confirmation}",
        "type": ["VerifiableCredential", "BookingConfirmationCredential"],
        "issuer": {
            "id": issuer_did,
            "name": vendor_name,
        },
        "validFrom": now,
        "credentialSubject": subject,
    }

    if config is not None:
        try:
            credential["proof"] = {
                "type": "DataIntegrityProof",
                "cryptosuite": "ecdsa-secp256k1-2019",
                "created": now,
                "verificationMethod": f"{issuer_did}#key-1",
                "proofPurpose": "assertionMethod",
            }
            credential = sign_credential(credential, config.private_key)
        except Exception:
            credential.pop("proof", None)  # remove incomplete proof on failure

    return credential


# ── Vendor MCP tool registry ──────────────────────────────────────────────────
# Each entry: schemas (OpenAI function-calling format, compatible with Anthropic
# and Ollama with tool-capable models) + mock impl callables.
# Swap impl callables for real MCP server calls / external API requests.


def _flight_check_seats(args: dict, scope: dict) -> dict:
    cabin = args.get("cabin_class", "economy").lower()
    options = {
        "economy": [
            {"code": "23A", "type": "window", "extra_usd": 0},
            {"code": "23B", "type": "middle", "extra_usd": 0},
            {"code": "23C", "type": "aisle", "extra_usd": 0},
        ],
        "business": [
            {"code": "4A", "type": "window", "extra_usd": 50},
            {"code": "4D", "type": "aisle", "extra_usd": 50},
        ],
    }
    return {"cabin": cabin, "available_seats": options.get(cabin, options["economy"])}


def _flight_confirm(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("seat_code", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("flight", holder),
        "seat": args.get("seat_code"),
        "meal": args.get("meal_preference", "standard"),
        "extra_baggage": args.get("extra_baggage", False),
        "destination": scope.get("destination"),
        "dates": f"{scope.get('checkin')} → {scope.get('checkout')}",
    }


def _hotel_check_rooms(args: dict, scope: dict) -> dict:
    room_type = args.get("room_type", "king").lower()
    catalog = {
        "king": [
            {"id": "301", "type": "king", "floor": 3, "rate_usd": 189, "view": "city"},
            {
                "id": "512",
                "type": "king",
                "floor": 5,
                "rate_usd": 219,
                "view": "garden",
            },
        ],
        "queen": [
            {
                "id": "201",
                "type": "double queen",
                "floor": 2,
                "rate_usd": 159,
                "view": "pool",
            },
            {
                "id": "408",
                "type": "double queen",
                "floor": 4,
                "rate_usd": 179,
                "view": "city",
            },
        ],
        "twin": [
            {
                "id": "105",
                "type": "twin",
                "floor": 1,
                "rate_usd": 139,
                "view": "garden",
            },
        ],
    }
    return {"available_rooms": catalog.get(room_type, catalog["king"])}


def _hotel_confirm(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("room_id", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("hotel", holder),
        "room_id": args.get("room_id"),
        "smoking": args.get("smoking", False),
        "special_requests": args.get("special_requests") or "none",
        "checkin": scope.get("checkin"),
        "checkout": scope.get("checkout"),
    }


def _car_check_vehicles(args: dict, scope: dict) -> dict:
    size = args.get("vehicle_size", "standard").lower()
    fleet = {
        "economy": [{"id": "eco-01", "model": "Toyota Corolla", "rate_usd": 45}],
        "compact": [{"id": "cmp-01", "model": "Honda Civic", "rate_usd": 55}],
        "standard": [{"id": "std-01", "model": "Toyota Camry", "rate_usd": 70}],
        "suv": [{"id": "suv-01", "model": "Ford Explorer", "rate_usd": 95}],
        "luxury": [{"id": "lux-01", "model": "BMW 5 Series", "rate_usd": 150}],
    }
    return {"available_vehicles": fleet.get(size, fleet["standard"])}


def _car_confirm(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("vehicle_id", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("car", holder),
        "vehicle_id": args.get("vehicle_id"),
        "gps": args.get("gps", False),
        "extra_driver": args.get("extra_driver", False),
        "pickup": scope.get("checkin"),
    }


def _legal_check_templates(args: dict, scope: dict) -> dict:
    svc = args.get("service_type") or scope.get("serviceType", "contract_review")
    catalog = {
        "contract_review": [
            {"id": "std-review-v2", "name": "Standard Review", "hours": 4},
            {"id": "exp-review-v1", "name": "Expedited Review", "hours": 2},
        ],
        "nda_draft": [
            {"id": "mutual-nda-v3", "name": "Mutual NDA", "hours": 3},
            {"id": "oneway-nda-v2", "name": "One-way NDA", "hours": 2},
        ],
        "terms_of_service": [{"id": "saas-tos-v4", "name": "SaaS ToS", "hours": 6}],
        "privacy_policy": [
            {"id": "gdpr-pp-v3", "name": "GDPR Privacy Policy", "hours": 5}
        ],
    }
    return {"templates": catalog.get(svc, []), "service_type": svc}


def _legal_confirm(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("template_id", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("legal", holder),
        "template_id": args.get("template_id"),
        "urgency": args.get("urgency", "standard"),
        "parties": args.get("parties") or [],
    }


def _ecommerce_check_variants(args: dict, scope: dict) -> dict:
    item = (args.get("item_name") or "item")[:4].upper()
    return {
        "item": args.get("item_name"),
        "variants": [
            {"sku": f"{item}-S-BLK", "size": "S", "color": "black", "stock": 5},
            {"sku": f"{item}-M-BLK", "size": "M", "color": "black", "stock": 12},
            {"sku": f"{item}-M-WHT", "size": "M", "color": "white", "stock": 8},
            {"sku": f"{item}-L-BLK", "size": "L", "color": "black", "stock": 3},
        ],
    }


def _ecommerce_confirm(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("sku", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("ecommerce", holder),
        "sku": args.get("sku"),
        "gift_wrap": args.get("gift_wrap", False),
        "delivery_speed": args.get("delivery_speed", "standard"),
        "delivery_address": scope.get("deliveryAddress"),
    }


_VENDOR_TOOLS = {
    "flight": {
        "confirm_tool": "confirm_flight_booking",
        "schemas": [
            {
                "type": "function",
                "function": {
                    "name": "check_seat_options",
                    "description": "Check available seats on the booked flight.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cabin_class": {
                                "type": "string",
                                "enum": ["economy", "business"],
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confirm_flight_booking",
                    "description": "Confirm the booking once all preferences are collected.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "seat_code": {"type": "string"},
                            "meal_preference": {
                                "type": "string",
                                "enum": ["standard", "vegetarian", "vegan", "none"],
                            },
                            "extra_baggage": {"type": "boolean"},
                        },
                        "required": ["seat_code", "meal_preference", "extra_baggage"],
                    },
                },
            },
        ],
        "impl": {
            "check_seat_options": _flight_check_seats,
            "confirm_flight_booking": _flight_confirm,
        },
    },
    "hotel": {
        "confirm_tool": "confirm_hotel_booking",
        "schemas": [
            {
                "type": "function",
                "function": {
                    "name": "check_room_options",
                    "description": "Check available rooms for the customer's bed type preference.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "room_type": {
                                "type": "string",
                                "enum": ["king", "queen", "twin"],
                            }
                        },
                        "required": ["room_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confirm_hotel_booking",
                    "description": "Confirm the booking once all preferences are collected.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "room_id": {"type": "string"},
                            "smoking": {"type": "boolean"},
                            "special_requests": {"type": "string"},
                        },
                        "required": ["room_id", "smoking"],
                    },
                },
            },
        ],
        "impl": {
            "check_room_options": _hotel_check_rooms,
            "confirm_hotel_booking": _hotel_confirm,
        },
    },
    "car": {
        "confirm_tool": "confirm_car_rental",
        "schemas": [
            {
                "type": "function",
                "function": {
                    "name": "check_vehicle_options",
                    "description": "Check available rental vehicles of the requested size.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vehicle_size": {
                                "type": "string",
                                "enum": [
                                    "economy",
                                    "compact",
                                    "standard",
                                    "suv",
                                    "luxury",
                                ],
                            }
                        },
                        "required": ["vehicle_size"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confirm_car_rental",
                    "description": "Confirm the rental once all preferences are collected.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vehicle_id": {"type": "string"},
                            "gps": {"type": "boolean"},
                            "extra_driver": {"type": "boolean"},
                        },
                        "required": ["vehicle_id", "gps", "extra_driver"],
                    },
                },
            },
        ],
        "impl": {
            "check_vehicle_options": _car_check_vehicles,
            "confirm_car_rental": _car_confirm,
        },
    },
    "legal": {
        "confirm_tool": "confirm_legal_order",
        "schemas": [
            {
                "type": "function",
                "function": {
                    "name": "check_document_templates",
                    "description": "Retrieve available document templates for the service type.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_type": {
                                "type": "string",
                                "enum": [
                                    "contract_review",
                                    "nda_draft",
                                    "terms_of_service",
                                    "privacy_policy",
                                ],
                            }
                        },
                        "required": ["service_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confirm_legal_order",
                    "description": "Confirm the legal service order once all details are gathered.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "template_id": {"type": "string"},
                            "urgency": {
                                "type": "string",
                                "enum": ["standard", "expedited", "urgent"],
                            },
                            "parties": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["template_id", "urgency"],
                    },
                },
            },
        ],
        "impl": {
            "check_document_templates": _legal_check_templates,
            "confirm_legal_order": _legal_confirm,
        },
    },
    "ecommerce": {
        "confirm_tool": "confirm_order",
        "schemas": [
            {
                "type": "function",
                "function": {
                    "name": "check_item_variants",
                    "description": "Look up available variants (size, color, SKU) for an item.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_name": {"type": "string"},
                        },
                        "required": ["item_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confirm_order",
                    "description": "Place the order once variant and delivery preferences are confirmed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sku": {"type": "string"},
                            "gift_wrap": {"type": "boolean"},
                            "delivery_speed": {
                                "type": "string",
                                "enum": ["standard", "express", "overnight"],
                            },
                        },
                        "required": ["sku", "gift_wrap", "delivery_speed"],
                    },
                },
            },
        ],
        "impl": {
            "check_item_variants": _ecommerce_check_variants,
            "confirm_order": _ecommerce_confirm,
        },
    },
}


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

        # For each discovered type: use hardcoded entry if available, else synthesise
        seen = set(_META_IDS)
        for type_id, agents_of_type in type_to_agents.items():
            if type_id in seen:
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

        # ── Resolve agent type and its system prompt ──────────────────────── #
        agent_type_id = (body.get("agent_type") or "general").strip()
        agent_type = _AGENT_TYPE_MAP.get(agent_type_id)

        if agent_type_id == "general":
            # Dynamically inject all on-chain registered types into the prompt
            _onchain = await _fetch_onchain_agents(self.config)
            system_prompt = _build_general_prompt_dynamic(_onchain)
        elif agent_type and agent_type.get("systemPrompt"):
            # Hardcoded or plugin-registered type with a known intake prompt
            system_prompt = agent_type["systemPrompt"]
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
            or "http://localhost:11434"
        ).rstrip("/")
        base_url = (llm_cfg.get("base_url") or "").rstrip("/")

        full_messages = _sanitize_messages(
            [{"role": "system", "content": system_prompt}] + messages
        )

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
        else:
            parsed = {}
            reply = content
            extracted = {}
            complete = False

        detected_agent_type = (
            parsed.get("detected_agent_type", agent_type_id)
            if isinstance(parsed, dict)
            else agent_type_id
        )
        return self.render_as_json(
            {
                "reply": reply,
                "extracted": extracted,
                "complete": complete,
                "detected_agent_type": detected_agent_type,
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

    _DIST = os.path.join(os.path.dirname(__file__), "dist")

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
_MOCK_INVENTORY = {
    svc: {"available": info.get("available", True)}
    for svc, info in VENDOR_REGISTRY.items()
}


class TravelBookingHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/travel

    Mock travel-booking service that authenticates the caller via a
    KEL-backed challenge-response.  The private key is NEVER sent to this
    server — the caller signs the challenge client-side and submits only the
    public key + signature.

    Body (JSON)
    -----------
    public_key  : hex compressed secp256k1 public key (the provisioned agent key)
    challenge   : hex string received from GET /api/challenge
    signature   : hex compact secp256k1 signature of sha256(challenge_utf8)
    services    : list[str]   e.g. ["hotel", "flight", "car"]
    dest        : str         destination
    checkin     : str         check-in date
    checkout    : str         check-out date

    Auth flow
    ---------
    1. Validate HMAC challenge (stateless, 30-second windows).
    2. Verify secp256k1 signature against public_key.
    3. Build KEL for public_key.
    4. Revocation check: public_key address must NOT appear as public_key_hash
       in any existing KEL entry.
    5. Pre-commitment check: kel[-1].prerotated_key_hash must equal address.
    6. Read authorised scope from ``relationship`` field of the latest KEL entry.
    7. Book each requested service if it is within scope and available.

    HTTP status codes
    -----------------
    200  All requested services booked successfully.
    206  Partial: some services booked, others unavailable or out of stock.
    401  Challenge expired/invalid or signature verification failed.
    403  KEL pre-commitment mismatch, revoked key, or scope violation.
    422  Request understood but nothing could be fulfilled (all unavailable).
    """

    async def post(self):
        pass

        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "invalid json body"}
            )

        public_key = (body.get("public_key") or "").strip()
        challenge = (body.get("challenge") or "").strip()
        signature = (body.get("signature") or "").strip()
        services = [s.lower() for s in (body.get("services") or [])]
        dest = (body.get("dest") or "").strip()

        # ── Authenticate: challenge, sig, KEL, revocation, pre-commitment ─── #
        try:
            auth = await _validator.validate(public_key, challenge, signature)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json({"status": False, "message": str(exc)})

        # ── Destination scope check ────────────────────────────────────────── #
        try:
            AgentAuthValidator.enforce_scope(auth, dest=dest)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json(
                {"status": False, "message": str(exc), "scope": auth.scope}
            )

        scope_services = [s.lower() for s in auth.scope.get("services", [])]

        # ── Mock booking ────────────────────────────────────────────────────── #
        completed = []
        failed = []

        for svc in services:
            inv = _MOCK_INVENTORY.get(svc)
            if scope_services and svc not in scope_services:
                failed.append(
                    {
                        "service": svc,
                        "reason": "not_authorized",
                        "message": f"'{svc}' is not in the authorised scope",
                    }
                )
            elif inv is None:
                failed.append(
                    {
                        "service": svc,
                        "reason": "unknown_service",
                        "message": f"'{svc}' is not a service this provider offers",
                    }
                )
            elif not inv["available"]:
                failed.append(
                    {
                        "service": svc,
                        "reason": "no_availability",
                        "message": inv.get("reason", f"No {svc} available"),
                    }
                )
            else:
                completed.append(
                    {
                        "service": svc,
                        "confirmation": _gen_confirmation(svc, auth.address),
                    }
                )

        n_ok = len(completed)
        n_fail = len(failed)

        if n_ok == 0:
            scope_fail_count = sum(1 for f in failed if f["reason"] == "not_authorized")
            if scope_fail_count == n_fail:
                self.set_status(403)
            else:
                self.set_status(422)
        elif n_fail > 0:
            self.set_status(206)
        else:
            self.set_status(200)

        return self.render_as_json(
            {
                "status": n_ok > 0,
                "completed": completed,
                "failed": failed,
                "scope_used": auth.scope,
                "authorized_address": auth.address,
                "kel_depth": len(auth.kel),
                "kel_txid": auth.kel_txid,
            }
        )


# ── Per-vendor VP-based handlers ──────────────────────────────────────────────


class VendorBaseHandler(BaseHandler):
    """
    Base class for individual vendor booking endpoints.

    Subclasses set ``vendor_service`` to one of the keys in VENDOR_REGISTRY.
    All auth, scope checking, and booking logic is handled here.

    Body (JSON)
    -----------
    public_key : hex compressed secp256k1 public key
    challenge  : hex string from GET /api/vendor/<service>/challenge
    vp         : W3C VP object  {type, holder, verifiableCredential, proof}
    """

    vendor_service: str = ""

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "invalid json body"}
            )

        public_key = (body.get("public_key") or "").strip()
        challenge = (body.get("challenge") or "").strip()
        vp = body.get("vp")

        if not public_key or not challenge or not vp:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "public_key, challenge, and vp are required",
                }
            )

        try:
            auth = await _validator.validate_vp(public_key, challenge, vp)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json({"status": False, "message": str(exc)})

        try:
            AgentAuthValidator.enforce_scope(auth, services=[self.vendor_service])
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json(
                {"status": False, "message": str(exc), "scope": auth.scope}
            )

        vendor = VENDOR_REGISTRY.get(self.vendor_service, {})
        if not vendor.get("available", False):
            self.set_status(422)
            return self.render_as_json(
                {
                    "status": False,
                    "service": self.vendor_service,
                    "message": f"No {self.vendor_service} available at this time",
                }
            )

        confirmation = _gen_confirmation(self.vendor_service, auth.address)
        return self.render_as_json(
            {
                "status": True,
                "service": self.vendor_service,
                "vendor": vendor.get("name", self.vendor_service),
                "confirmation": confirmation,
                "authorized_address": auth.address,
                "kel_depth": len(auth.kel),
                "kel_txid": auth.kel_txid,
                "payment_method": auth.scope.get("paymentMethod") or {},
            }
        )


class VendorChatBaseHandler(AgentChatHandler):
    """
    POST /ai-agent-auth/api/vendor/<svc>/chat

    LLM-powered vendor follow-up conversation.  After the VP has been validated
    the vendor's LLM asks the customer clarifying questions (bed type, seat
    preference, etc.) before issuing a confirmation.

    Body (JSON)
    -----------
    public_key : hex compressed secp256k1 public key
    challenge  : hex string from GET /api/vendor/<service>/challenge
    vp         : W3C VP object (signed)
    messages   : list[{role, content}]  — conversation history (no system msg)
    llm        : same LLM config block as /api/chat
    """

    vendor_service: str = ""

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "invalid json body"}
            )

        public_key = (body.get("public_key") or "").strip()
        challenge = (body.get("challenge") or "").strip()
        vp = body.get("vp")
        messages = body.get("messages") or []
        llm_cfg = body.get("llm") or {}

        if not public_key or not challenge or not vp:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "public_key, challenge, and vp are required",
                }
            )

        try:
            auth = await _validator.validate_vp(public_key, challenge, vp)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json({"status": False, "message": str(exc)})

        try:
            AgentAuthValidator.enforce_scope(auth, services=[self.vendor_service])
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json(
                {"status": False, "message": str(exc), "scope": auth.scope}
            )

        vendor = VENDOR_REGISTRY.get(self.vendor_service, {})
        if not vendor.get("available", False):
            self.set_status(422)
            return self.render_as_json(
                {
                    "status": False,
                    "service": self.vendor_service,
                    "message": f"No {self.vendor_service} available at this time",
                }
            )

        # LLM config
        provider = (llm_cfg.get("provider") or "ollama").lower().strip()
        model = (llm_cfg.get("model") or "").strip() or self._DEFAULT_MODELS.get(
            provider, "gpt-4o-mini"
        )
        api_key = (llm_cfg.get("api_key") or "").strip()
        ollama_host = (
            llm_cfg.get("ollama_host")
            or getattr(self.config, "ollama_host", None)
            or "http://localhost:11434"
        ).rstrip("/")
        base_url = (llm_cfg.get("base_url") or "").rstrip("/")

        vendor_tools = _VENDOR_TOOLS.get(self.vendor_service)

        if vendor_tools:
            # ── MCP tool-calling mode ──────────────────────────────────────── #
            scope_ctx = json.dumps(auth.scope, separators=(",", ":"))
            system_prompt = (
                f"You are the reservations agent for {vendor['name']}. "
                f"The customer has been verified via YadaCoin KEL identity. "
                f"Use the available tools to look up options and confirm the booking. "
                f"Ask ONE question at a time. Be warm and professional. "
                f"Customer's authorized scope: {scope_ctx}"
            )
            try:
                reply, confirmation, confirm_result = await self._run_tool_loop(
                    provider,
                    model,
                    api_key,
                    ollama_host,
                    base_url,
                    system_prompt,
                    messages,
                    vendor_tools,
                    auth.scope,
                )
            except Exception as exc:
                self.set_status(502)
                return self.render_as_json(
                    {"status": False, "message": f"LLM unreachable ({provider}): {exc}"}
                )
            complete = confirmation is not None
        else:
            # ── JSON fallback mode ─────────────────────────────────────────── #
            confirm_result = None
            scope_ctx = json.dumps(auth.scope, separators=(",", ":"))
            base_prompt = vendor.get(
                "vendorPrompt",
                (
                    "You are a booking agent. Collect preferences ONE question at a time. "
                    'ALWAYS respond with ONLY valid JSON: {"reply": "...", "complete": false}'
                ),
            )
            system_prompt = f"{base_prompt}\n\nCustomer's authorized scope: {scope_ctx}"
            full_messages = _sanitize_messages(
                [{"role": "system", "content": system_prompt}] + messages
            )
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
                    return self.render_as_json(
                        {"error": f"unknown provider '{provider}'"}
                    )
            except Exception as exc:
                self.set_status(502)
                return self.render_as_json(
                    {"status": False, "message": f"LLM unreachable ({provider}): {exc}"}
                )
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            try:
                parsed = json.loads(content)
                reply = str(parsed.get("reply", ""))
                complete = bool(parsed.get("complete", False))
                exit_vendor = bool(parsed.get("exit_vendor", False))
            except Exception:
                reply = content
                complete = False
                exit_vendor = False
            confirmation = (
                _gen_confirmation(self.vendor_service, auth.address)
                if complete
                else None
            )

        # MCP tool-loop path does not expose exit_vendor
        if vendor_tools:
            exit_vendor = False

        result = {
            "status": True,
            "reply": reply,
            "complete": complete,
            "exit_vendor": exit_vendor,
            "service": self.vendor_service,
            "vendor": vendor.get("name", self.vendor_service),
        }
        if confirmation:
            result["confirmation"] = confirmation
            result["credential"] = _gen_booking_credential(
                self.vendor_service,
                auth.address,
                auth.scope,
                confirmation,
                vendor.get("name", self.vendor_service),
                booking_details=confirm_result,
                config=self.config,
            )

        return self.render_as_json(result)


# ── Agent registration + discovery handlers ──────────────────────────────────


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


def _coerce_config_value(key: str, raw):
    """Coerce a raw (possibly string) value to the expected type for key."""
    target = _CONFIG_WRITEABLE[key]
    # Normalise tuple targets to the first concrete type for coercion.
    primary = target[0] if isinstance(target, tuple) else target

    if primary is bool:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            if raw.lower() in ("true", "1", "yes", "on"):
                return True
            if raw.lower() in ("false", "0", "no", "off"):
                return False
        raise ValueError(f"Cannot coerce {raw!r} to bool for '{key}'")

    if primary is float:
        return float(raw)

    if primary is int:
        return int(float(raw))  # handles "3.0" → 3

    if primary is list:
        if isinstance(raw, list):
            return raw
        if isinstance(raw, str):
            # Accept JSON array strings or comma-separated values
            stripped = raw.strip()
            if stripped.startswith("["):
                import json as _json

                return _json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        raise ValueError(f"Cannot coerce {raw!r} to list for '{key}'")

    # str
    return str(raw)


class NodeConfigApplyHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/node-config/apply

    Apply a single config change to the active config.json file and
    schedule a graceful node restart so the change takes effect.

    Requires a valid KEL-backed VP (key rotation / second-factor authorization)
    with authorizationType == "NodeConfigAuthorization" in the scope.  The
    flow mirrors the vendor VP endpoints:
      1. GET /ai-agent-auth/api/challenge?public_key=<hex>  → challenge token
      2. Browser derives next child key, broadcasts a rotation transaction
         with scope = {authorizationType: "NodeConfigAuthorization",
                       config_key: "<key>", config_value: "<value>"}
      3. POST here with {public_key, challenge, vp, key, value}

    Body (JSON)
    -----------
    public_key : hex compressed secp256k1 public key (the prerotated agent key)
    challenge  : hex string from GET /api/challenge
    vp         : W3C VP object {type, holder, verifiableCredential, proof}
    key        : str — the config setting name (must be in _CONFIG_WRITEABLE)
    value      : any — the new value (will be type-coerced)

    Response (JSON)
    ---------------
    {"status": "ok", "key": ..., "value": ..., "restarting": true}
    """

    async def post(self):
        import os
        import signal
        import tempfile

        import tornado.ioloop

        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid json body"})

        public_key = (body.get("public_key") or "").strip()
        challenge = (body.get("challenge") or "").strip()
        vp = body.get("vp")
        key = (body.get("key") or "").strip()
        raw_value = body.get("value")

        # ── Basic field validation ──────────────────────────────────────────
        if not public_key or not challenge or not vp:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "public_key, challenge, and vp are required",
                }
            )

        if not key:
            self.set_status(400)
            return self.render_as_json({"error": "key is required"})

        if key not in _CONFIG_WRITEABLE:
            self.set_status(400)
            return self.render_as_json(
                {
                    "error": f"'{key}' is not a settable config option via chat. "
                    "See the allowed list in the node_config agent."
                }
            )

        if raw_value is None:
            self.set_status(400)
            return self.render_as_json({"error": "value is required"})

        try:
            coerced = _coerce_config_value(key, raw_value)
        except (ValueError, TypeError) as exc:
            self.set_status(400)
            return self.render_as_json({"error": f"Invalid value: {exc}"})

        # ── KEL / VP validation (second-factor / key rotation) ─────────────
        try:
            auth = await _validator.validate_vp(public_key, challenge, vp)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json({"status": False, "message": str(exc)})

        try:
            AgentAuthValidator.enforce_scope(auth, services=["NodeConfigAuthorization"])
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json(
                {"status": False, "message": str(exc), "scope": auth.scope}
            )

        # ── Locate the config file ──────────────────────────────────────────
        config_path = getattr(self.config, "config_path", None)
        if not config_path:
            config_path = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), "..", "..", "config", "config.json"
                )
            )

        if not os.path.isfile(config_path):
            self.set_status(500)
            return self.render_as_json(
                {"error": f"Config file not found at {config_path}"}
            )

        # ── Read → patch → write atomically ────────────────────────────────
        try:
            with open(config_path, "r") as fh:
                cfg_dict = json.load(fh)
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json({"error": f"Failed to read config: {exc}"})

        cfg_dict[key] = coerced

        config_dir = os.path.dirname(config_path)
        try:
            fd, tmp_path = tempfile.mkstemp(dir=config_dir, suffix=".tmp")
            with os.fdopen(fd, "w") as fh:
                json.dump(cfg_dict, fh, indent=4)
            os.replace(tmp_path, config_path)
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json({"error": f"Failed to write config: {exc}"})

        # ── Update the in-memory Config singleton ───────────────────────────
        try:
            setattr(self.config, key, coerced)
        except Exception:
            pass  # best-effort; restart will reload from disk anyway

        # ── Respond, then schedule graceful restart ─────────────────────────
        self.render_as_json(
            {
                "status": "ok",
                "key": key,
                "value": coerced,
                "restarting": True,
                "authorized_address": auth.address,
                "kel_depth": len(auth.kel),
                "kel_txid": auth.kel_txid,
                "message": (
                    f"Config updated: {key} = {coerced!r}. "
                    "Node is restarting to apply the change."
                ),
            }
        )

        def _do_restart():
            os.kill(os.getpid(), signal.SIGTERM)

        tornado.ioloop.IOLoop.current().call_later(2, _do_restart)


# ── Wallet Agent API handlers ─────────────────────────────────────────────────


class WalletInfoHandler(BaseHandler):
    """
    GET /ai-agent-auth/api/wallet/info?public_key=<hex>

    Returns balance and address for the given public key.
    Read-only — no authentication required.
    """

    async def get(self):
        from bitcoin.wallet import P2PKHBitcoinAddress

        public_key = (self.get_argument("public_key", "") or "").strip()
        if not public_key:
            self.set_status(400)
            return self.render_as_json({"error": "public_key is required"})
        try:
            address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid public_key"})
        try:
            balance = await self.config.BU.get_wallet_balance(address)
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json({"error": f"balance lookup failed: {exc}"})
        return self.render_as_json(
            {
                "address": address,
                "public_key": public_key,
                "balance": "{0:.8f}".format(balance),
            }
        )


class WalletTransactionsHandler(BaseHandler):
    """
    GET /ai-agent-auth/api/wallet/transactions?public_key=<hex>&direction=all|sent|received&page=1

    Returns confirmed on-chain transactions (sent and/or received).
    Read-only — no authentication required.
    """

    async def get(self):
        from bitcoin.wallet import P2PKHBitcoinAddress

        public_key = (self.get_argument("public_key", "") or "").strip()
        direction = (self.get_argument("direction", "all") or "all").strip().lower()
        page = max(int(self.get_argument("page", "1") or "1"), 1) - 1
        if not public_key:
            self.set_status(400)
            return self.render_as_json({"error": "public_key is required"})
        try:
            address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid public_key"})

        results = []
        try:
            if direction in ("all", "sent"):
                sent_q = [
                    {
                        "$match": {
                            "transactions.inputs.0": {"$exists": True},
                            "transactions.public_key": public_key,
                            "transactions.outputs.value": {"$gt": 0},
                        }
                    },
                    {"$unwind": "$transactions"},
                    {
                        "$match": {
                            "transactions.inputs.0": {"$exists": True},
                            "transactions.public_key": public_key,
                            "transactions.outputs.value": {"$gt": 0},
                        }
                    },
                    {"$sort": {"transactions.time": -1}},
                    {"$skip": page * 10},
                    {"$limit": 10},
                ]
                async for doc in self.config.mongo.async_db.blocks.aggregate(sent_q):
                    txn = doc["transactions"]
                    txn["_direction"] = "sent"
                    results.append(txn)

            if direction in ("all", "received"):
                recv_q = [
                    {
                        "$match": {
                            "transactions.outputs.to": address,
                            "transactions.outputs.value": {"$gt": 0},
                        }
                    },
                    {"$unwind": "$transactions"},
                    {
                        "$match": {
                            "transactions.outputs.to": address,
                            "transactions.outputs.value": {"$gt": 0},
                            "transactions.public_key": {"$ne": public_key},
                        }
                    },
                    {"$sort": {"transactions.time": -1}},
                    {"$skip": page * 10},
                    {"$limit": 10},
                ]
                async for doc in self.config.mongo.async_db.blocks.aggregate(recv_q):
                    txn = doc["transactions"]
                    txn["_direction"] = "received"
                    results.append(txn)
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json({"error": f"query failed: {exc}"})

        # Sort merged results newest-first
        results.sort(key=lambda t: t.get("time", 0), reverse=True)
        return self.render_as_json({"transactions": results[:10], "page": page + 1})


class WalletSendHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/wallet/send

    Send or wrap a YDA transaction, authorised via a KEL-backed VP.

    Body (JSON)
    -----------
    public_key : hex compressed secp256k1 key (the prerotated agent key)
    challenge  : hex string from GET /ai-agent-auth/api/challenge
    vp         : W3C VP object {type, holder, verifiableCredential, proof}
    to_address : recipient YadaCoin address (ignored for wrap — bridge address used)
    amount     : float — YDA amount to send/wrap
    fee        : float — optional transaction fee (default 0.0)
    eth_address: str  — Ethereum 0x address (required for wrap; omit for plain send)

    Response (JSON)
    ---------------
    {"status": "ok", "transaction_id": "...", "to": ..., "amount": ..., "fee": ...}
    """

    WRAP_BRIDGE_ADDRESS = "16U1gAmHazqqEkbRE9KFPShAperjJreMRA"

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid json body"})

        public_key = (body.get("public_key") or "").strip()
        challenge = (body.get("challenge") or "").strip()
        vp = body.get("vp")
        eth_address = (body.get("eth_address") or "").strip()
        amount = body.get("amount")
        fee = float(body.get("fee", 0.0))

        # Wrap: to_address is always the bridge; relationship is the ETH address
        is_wrap = bool(eth_address)
        if is_wrap:
            to_address = self.WRAP_BRIDGE_ADDRESS
            if not eth_address.startswith("0x") or len(eth_address) != 42:
                self.set_status(400)
                return self.render_as_json(
                    {
                        "error": "eth_address must be a valid 0x Ethereum address (42 chars)"
                    }
                )
        else:
            to_address = (body.get("to_address") or "").strip()

        if not public_key or not challenge or not vp:
            self.set_status(400)
            return self.render_as_json(
                {"error": "public_key, challenge, and vp are required"}
            )
        if not to_address:
            self.set_status(400)
            return self.render_as_json(
                {"error": "to_address or eth_address is required"}
            )
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError("amount must be positive")
        except (TypeError, ValueError) as exc:
            self.set_status(400)
            return self.render_as_json({"error": f"invalid amount: {exc}"})

        # ── KEL / VP validation ─────────────────────────────────────────────
        try:
            auth = await _validator.validate_vp(public_key, challenge, vp)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json({"status": False, "message": str(exc)})

        try:
            AgentAuthValidator.enforce_scope(auth, services=["WalletAuthorization"])
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json(
                {"status": False, "message": str(exc), "scope": auth.scope}
            )

        # Verify the VP scope matches what the user approved in chat
        scope = auth.scope or {}
        scope_to = (scope.get("to_address") or "").strip()
        scope_amt = scope.get("amount")
        scope_eth = (scope.get("eth_address") or "").strip()
        if scope_to and scope_to != to_address:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        f"Scope mismatch: VP authorised send to '{scope_to}' "
                        f"but request targets '{to_address}'"
                    ),
                }
            )
        if scope_eth and scope_eth != eth_address:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        f"Scope mismatch: VP authorised wrap to '{scope_eth}' "
                        f"but request specifies '{eth_address}'"
                    ),
                }
            )
        if scope_amt is not None:
            try:
                if abs(float(scope_amt) - amount) > 1e-8:
                    raise ValueError(
                        f"VP authorised {scope_amt} YDA but request sends {amount} YDA"
                    )
            except (TypeError, ValueError) as exc:
                self.set_status(403)
                return self.render_as_json({"status": False, "message": str(exc)})

        # ── Build and submit the transaction (same pipeline as GraphTransactionHandler) ─
        from yadacoin.core.transaction import (
            NotEnoughMoneyException,
            TooManyInputsException,
            Transaction,
        )

        try:
            transaction = await Transaction.generate(
                fee=fee,
                public_key=self.config.public_key,
                private_key=self.config.private_key,
                inputs=[],
                outputs=[{"to": to_address, "value": amount}],
                relationship=eth_address if is_wrap else "",
            )
        except NotEnoughMoneyException:
            self.set_status(400)
            return self.render_as_json({"error": "not enough funds"})
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json(
                {"error": f"transaction generation failed: {exc}"}
            )

        try:
            await transaction.verify(
                check_input_spent=True,
                check_masternode_fee=True,
                check_max_inputs=True,
                check_kel=True,
                mempool=True,
            )
        except TooManyInputsException as exc:
            self.set_status(400)
            return self.render_as_json({"error": f"too many inputs: {exc}"})
        except Exception as exc:
            self.set_status(400)
            return self.render_as_json({"error": f"transaction invalid: {exc}"})

        await self.config.mongo.async_db.miner_transactions.insert_one(
            transaction.to_dict()
        )
        if "node" in self.config.modes:
            async for peer_stream in self.config.peer.get_sync_peers():
                await self.config.nodeShared.write_params(
                    peer_stream, "newtxn", {"transaction": transaction.to_dict()}
                )
                if peer_stream.peer.protocol_version > 1:
                    self.config.nodeClient.retry_messages[
                        (
                            peer_stream.peer.rid,
                            "newtxn",
                            transaction.transaction_signature,
                        )
                    ] = {"transaction": transaction.to_dict()}

        return self.render_as_json(
            {
                "status": "ok",
                "transaction_id": transaction.transaction_signature,
                "to": to_address,
                "amount": amount,
                "fee": fee,
                "authorized_address": auth.address,
                "kel_depth": len(auth.kel),
                "kel_txid": auth.kel_txid,
            }
        )


# ── Dynamically generate a VendorHandler subclass for every registered service ─
# Adding a new entry to VENDOR_REGISTRY automatically creates its handler.

_VENDOR_HANDLERS: dict = {}
_VENDOR_CHAT_HANDLERS: dict = {}
for _svc_id in VENDOR_REGISTRY:
    _VENDOR_HANDLERS[_svc_id] = type(
        f"{_svc_id.capitalize()}VendorHandler",
        (VendorBaseHandler,),
        {"vendor_service": _svc_id},
    )
    _VENDOR_CHAT_HANDLERS[_svc_id] = type(
        f"{_svc_id.capitalize()}VendorChatHandler",
        (VendorChatBaseHandler,),
        {"vendor_service": _svc_id},
    )

# Named aliases for backwards compat
FlightVendorHandler = _VENDOR_HANDLERS["flight"]
HotelVendorHandler = _VENDOR_HANDLERS["hotel"]
CarVendorHandler = _VENDOR_HANDLERS["car"]


# ── Route table ───────────────────────────────────────────────────────────────
# Vendor challenge + booking routes are generated from VENDOR_REGISTRY.

_vendor_routes = []
for _svc_id, _handler in _VENDOR_HANDLERS.items():
    _vendor_routes += [
        (rf"/ai-agent-auth/api/vendor/{_svc_id}/challenge", AgentChallengeHandler),
        (rf"/ai-agent-auth/api/vendor/{_svc_id}/chat", _VENDOR_CHAT_HANDLERS[_svc_id]),
        (rf"/ai-agent-auth/api/vendor/{_svc_id}", _handler),
    ]

HANDLERS = [
    (r"/.well-known/did.json", WellKnownDidHandler),
    (r"/contexts/booking/v1", BookingContextHandler),
    # SPA shell — catch-all for client-side routes (must be last)
    (
        r"/ai-agent-auth/assets/(.*)",
        tornado.web.StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "dist", "assets")},
    ),
    (r"/ai-agent-auth", AgentAuthAppHandler),
    (r"/ai-agent-auth/", AgentAuthAppHandler),
    (r"/ai-agent-auth/api/agents/register", AgentRegisterHandler),
    (r"/ai-agent-auth/api/agents/discover", AgentDiscoverHandler),
    (r"/ai-agent-auth/api/agents", AgentListHandler),
    (r"/ai-agent-auth/api/chat", AgentChatHandler),
    (r"/ai-agent-auth/api/challenge", AgentChallengeHandler),
    (r"/ai-agent-auth/api/node-config/apply", NodeConfigApplyHandler),
    (r"/ai-agent-auth/api/wallet/info", WalletInfoHandler),
    (r"/ai-agent-auth/api/wallet/send", WalletSendHandler),
    (r"/ai-agent-auth/api/travel", TravelBookingHandler),  # legacy endpoint
    *_vendor_routes,
]
