"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

yadaaiagent — AI agent demo plugin.

Architecture:  human → KEL pre-commitment → challenge-response → external service

Flow
----
1. Operator visits /ai-agent-auth and initialises their key in localStorage.
2. They type a travel request; the agent collects destination / dates / services
   via a multi-turn chat.
3. On approval the browser:
     a. Derives the next child key client-side (second_factor stays in browser).
     b. Broadcasts a rotation transaction with a structured JSON scope committed
        in the ``relationship`` field.
     c. Receives ``prerotated_private_key`` — the one-time agent credential.
4. The browser then does a challenge-response with the travel service:
     a. GET /ai-agent-auth/api/challenge?public_key=<hex>  → {challenge}
     b. Signs ``sha256(challenge_utf8)`` with the provisioned key (client-side).
     c. POST /ai-agent-auth/api/travel  {public_key, challenge, signature, …}
5. The server:
     a. Validates the HMAC challenge.
     b. Verifies the secp256k1 signature — private key never sent to server.
     c. Builds the KEL and checks pre-commitment + revocation.
     d. Reads the authorised scope from ``relationship`` on the KEL entry.
     e. Books what it can; returns 200 (full) / 206 (partial) / 422 / 403.

Endpoints
---------
GET  /ai-agent-auth                        — demo UI
GET  /ai-agent-auth/api/challenge          — issue stateless HMAC challenge
POST /ai-agent-auth/api/travel             — mock travel booking service
"""

import base64
import hashlib
import hmac as _hmac
import json
import os
import time

import tornado.web
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import verify_signature as _verify_signature
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

from yadacoin.http.base import BaseHandler

# ── Challenge secret ──────────────────────────────────────────────────────────
# Override with YADACOIN_AGENT_SECRET env-var in production.
_CHALLENGE_SECRET = os.environ.get(
    "YADACOIN_AGENT_SECRET", "yadacoin-demo-agent-secret-2026"
).encode("utf-8")


def _make_challenge(public_key: str, window: int) -> str:
    """Return a deterministic HMAC-SHA256 hex string for (public_key, window)."""
    msg = f"{public_key}:{window}".encode("utf-8")
    return _hmac.new(_CHALLENGE_SECRET, msg, hashlib.sha256).hexdigest()


def _valid_challenge(public_key: str, challenge: str) -> bool:
    """Accept challenges from the current 30-second window or the previous one."""
    now = int(time.time())
    for w in [now // 30, now // 30 - 1]:
        if _hmac.compare_digest(challenge, _make_challenge(public_key, w)):
            return True
    return False


# ── Mock travel inventory ─────────────────────────────────────────────────────
_MOCK_INVENTORY = {
    "hotel": {"available": True},
    "flight": {"available": True},
    "car": {"available": True},
}


def _gen_confirmation(service: str, seed: str) -> str:
    pfx = {"hotel": "HTL", "flight": "FLT", "car": "CAR"}.get(service, "SVC")
    h = hashlib.sha256(f"{seed}{service}".encode()).hexdigest()[:6].upper()
    return f"{pfx}-{h}"


def _extract_scope(data: dict) -> dict:
    """Normalize scope from W3C VC 2.0 or legacy flat format.

    W3C VC 2.0 format:
      { "@context": [...], "credentialSubject": { "agentAuthorization": { ... } } }
    Legacy flat format:
      { "task": "travel_booking", "dest": ..., "services": [...] }
    """
    if "@context" in data and "credentialSubject" in data:
        auth = data.get("credentialSubject", {}).get("agentAuthorization", {})
        return {
            "dest": auth.get("destination"),
            "services": [s.lower() for s in auth.get("services", [])],
            "checkin": auth.get("checkin"),
            "checkout": auth.get("checkout"),
        }
    # Legacy flat format — normalise service list to lowercase
    services = data.get("services", [])
    return {**data, "services": [s.lower() for s in services]}


def _verify_vp_proof(vp: dict, public_key_bytes: bytes, challenge: str):
    """Verify a Verifiable Presentation's EcdsaSecp256k1 proof.

    The proof must cover SHA256(challenge_bytes + canonical_vp_sans_proof_bytes),
    where the canonical form is JSON with sorted top-level keys and no whitespace.

    Returns (ok: bool, error: str).
    """
    proof = vp.get("proof")
    if not proof:
        return False, "VP missing proof"

    if proof.get("challenge") != challenge:
        return (
            False,
            f"VP proof.challenge '{proof.get('challenge')}' does not match supplied challenge",
        )

    proof_value = proof.get("proofValue", "")
    if not proof_value:
        return False, "VP missing proof.proofValue"

    # Reconstruct VP without proof for verification (canonical, sorted keys)
    vp_sans_proof = {k: v for k, v in vp.items() if k != "proof"}
    vp_bytes = json.dumps(vp_sans_proof, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )

    challenge_bytes = challenge.encode("utf-8")
    msg_hash = hashlib.sha256(challenge_bytes + vp_bytes).digest()

    try:
        sig_bytes = base64.b64decode(proof_value)
        ok = _verify_signature(sig_bytes, msg_hash, public_key_bytes, hasher=None)
        if not ok:
            return False, "VP proof signature mismatch"
        return True, ""
    except Exception as exc:
        return False, f"VP proof verification error: {exc}"


class AgentChatHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/chat

    Proxies the conversation to a configurable LLM and returns a
    structured JSON response for driving the travel booking UI.

    Body (JSON)
    -----------
    messages : list[{role: "user"|"assistant", content: str}]
    llm      : {
        provider    : "ollama" | "openai" | "anthropic" | "openai_compat"
        model       : str (optional — falls back to sensible defaults)
        api_key     : str (required for openai / anthropic / openai_compat)
        ollama_host : str (ollama only, default "http://localhost:11434")
        base_url    : str (openai_compat only)
      }

    The api_key is supplied by the browser from localStorage and is never
    stored on the YadaCoin server.
    """

    _SYSTEM_PROMPT = (
        "You are a travel booking assistant. Your ONLY job is to collect travel details from the user.\n"
        "You CANNOT book anything, confirm any reservation, or process any payment.\n"
        "NEVER ask for credit card details, payment info, or personal identification.\n"
        "NEVER say a booking has been made or confirmed — you have no ability to do that.\n"
        "Actual booking is handled by a separate cryptographic authorization system after the user approves.\n"
        "\n"
        "ALWAYS respond with ONLY a valid JSON object — no other text, no markdown:\n"
        "{\n"
        '  "reply": "your natural conversational response",\n'
        '  "extracted": {\n'
        '    "dest": "city/destination or null",\n'
        '    "checkin": "check-in date in Month Day format (e.g. May 10) or null",\n'
        '    "checkout": "check-out date in Month Day format (e.g. May 16) or null",\n'
        '    "services": ["hotel","flight","car"] subset or null\n'
        "  },\n"
        '  "complete": false\n'
        "}\n"
        "Rules:\n"
        "- Only use service values: hotel, flight, car\n"
        '- If the user says "all" or "everything": services=["hotel","flight","car"]\n'
        "- complete MUST be false unless ALL FOUR of dest, checkin, checkout, AND services are known\n"
        "- If any of dest, checkin, checkout, services is null or unknown, set complete=false and ask for the missing field(s)\n"
        "- NEVER set complete=true unless all four values are confirmed — not before, not to be polite\n"
        '- For date ranges like "May 10-16": checkin="May 10", checkout="May 16"\n'
        "- The reply field must be plain text (no JSON, no markdown)\n"
        "- When complete=false: your reply should acknowledge what you have and ask for what is missing\n"
        "- When complete=true: summarise all four details and say the operator will now be asked to approve the booking"
    )

    # ── Default models per provider ───────────────────────────────────────────
    _DEFAULT_MODELS = {
        "ollama": "llama3.2",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-haiku-20240307",
        "openai_compat": "gpt-3.5-turbo",
    }

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

        full_messages = [{"role": "system", "content": self._SYSTEM_PROMPT}] + messages

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

        try:
            parsed = json.loads(content)
            reply = str(parsed.get("reply", ""))
            extracted = parsed.get("extracted") or {}
            complete = bool(parsed.get("complete", False))
        except Exception:
            reply = content
            extracted = {}
            complete = False

        return self.render_as_json(
            {"reply": reply, "extracted": extracted, "complete": complete}
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

    async def _call_openai_compat(
        self, base_url: str, model: str, api_key: str, messages: list
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        client = AsyncHTTPClient()
        req = HTTPRequest(
            url=f"{base_url}/chat/completions",
            method="POST",
            headers=headers,
            body=json.dumps({"model": model, "messages": messages, "temperature": 0.2}),
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


class AgentAuthAppHandler(BaseHandler):
    """GET /ai-agent-auth — serve the demo UI."""

    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")

    async def get(self):
        return self.render("index.html")


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

        now = int(time.time())
        challenge = _make_challenge(public_key, now // 30)
        return self.render_as_json(
            {
                "challenge": challenge,
                "expires_in": 30 - (now % 30),
            }
        )


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
        from yadacoin.core.keyeventlog import KeyEventLog

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
        (body.get("checkin") or "").strip()
        (body.get("checkout") or "").strip()

        if not public_key or not challenge or not signature:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "public_key, challenge, and signature are required",
                }
            )

        # ── 1. Validate challenge ──────────────────────────────────────────── #
        if not _valid_challenge(public_key, challenge):
            self.set_status(401)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "challenge expired or invalid — request a fresh one",
                }
            )

        # ── 2. Parse public key ────────────────────────────────────────────── #
        try:
            pub_key_bytes = bytes.fromhex(public_key)
            if len(pub_key_bytes) not in (33, 65):
                raise ValueError("unexpected length")
        except Exception as exc:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": f"invalid public_key: {exc}",
                    "debug_public_key_prefix": public_key[:20],
                    "debug_signature_prefix": signature[:20],
                }
            )

        address = str(P2PKHBitcoinAddress.from_pubkey(pub_key_bytes))

        # ── 3. Verify signature ────────────────────────────────────────────── #
        # Client signs sha256(challenge_utf8) with secp.sign(hash, privKey).
        # secp256k1 v2 signs the raw bytes passed to it (no second hash).
        # So we pre-hash here and verify with hasher=None (no further hashing).
        try:
            sig_bytes = base64.b64decode(signature)
        except Exception as exc:
            self.set_status(401)
            return self.render_as_json(
                {
                    "status": False,
                    "message": f"signature base64 decode failed: {exc}",
                    "debug_signature_prefix": signature[:30],
                }
            )
        try:
            msg_hash = hashlib.sha256(challenge.encode("utf-8")).digest()
            ok = _verify_signature(
                sig_bytes,
                msg_hash,
                pub_key_bytes,
                hasher=None,
            )
            if not ok:
                raise ValueError("signature mismatch")
        except Exception as exc:
            self.set_status(401)
            return self.render_as_json(
                {"status": False, "message": f"signature verification failed: {exc}"}
            )

        # ── 4. Build KEL ───────────────────────────────────────────────────── #
        try:
            kel = await KeyEventLog.build_from_public_key(public_key)
        except Exception as exc:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": f"error retrieving KEL: {exc}"}
            )

        if not kel:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        "no KEL found for this public key — "
                        "key has not been provisioned on-chain"
                    ),
                }
            )

        # ── 5. Revocation check ────────────────────────────────────────────── #
        for entry in kel:
            if getattr(entry, "public_key_hash", None) == address:
                self.set_status(403)
                return self.render_as_json(
                    {
                        "status": False,
                        "message": "this key has already been used and is revoked",
                        "address": address,
                    }
                )

        # ── 6. Pre-commitment check ────────────────────────────────────────── #
        latest = kel[-1]
        if getattr(latest, "prerotated_key_hash", None) != address:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        "public key is not the pre-committed next signer — "
                        "the KEL has advanced past this key or it was never authorised"
                    ),
                    "address": address,
                    "expected": getattr(latest, "prerotated_key_hash", None),
                }
            )

        # ── 7. Read authorised scope from relationship field ───────────────── #
        # The scope is committed in the UNCONFIRMED tx whose
        # twice_prerotated_key_hash == address (the agent key being authenticated).
        # kel[-1] is the CONFIRMING tx (relationship=""); the UNCONFIRMED tx
        # is the KEL entry that pre-committed to the agent key two hops ahead.
        scope = {}
        for entry in kel:
            tpkh = (
                getattr(entry, "twice_prerotated_key_hash", None)
                if not isinstance(entry, dict)
                else entry.get("twice_prerotated_key_hash")
            )
            if tpkh == address:
                raw_rel = (
                    getattr(entry, "relationship", None)
                    if not isinstance(entry, dict)
                    else entry.get("relationship")
                )
                if raw_rel:
                    try:
                        parsed = json.loads(
                            base64.b64decode(raw_rel).decode("utf-8", errors="replace")
                        )
                        scope = _extract_scope(parsed)
                    except Exception:
                        pass
                break

        scope_services = [s.lower() for s in scope.get("services", [])]
        scope_dest = (scope.get("dest") or "").strip().lower()

        # ── 8. Destination scope check ─────────────────────────────────────── #
        if dest and scope_dest and dest.lower() != scope_dest:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        f"destination '{dest}' is not authorised — "
                        f"scope commits to '{scope.get('dest')}'"
                    ),
                    "scope": scope,
                }
            )

        # ── 9. Mock booking ────────────────────────────────────────────────── #
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
                        "confirmation": _gen_confirmation(svc, address),
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
                "scope_used": scope,
                "authorized_address": address,
                "kel_depth": len(kel),
                "kel_txid": getattr(latest, "transaction_signature", None),
            }
        )


# ── Per-vendor VP-based handlers ──────────────────────────────────────────────


class VendorBaseHandler(BaseHandler):
    """
    Base class for individual vendor booking endpoints.

    Each vendor is a fully independent service.  The agent authenticates by
    presenting a W3C Verifiable Presentation (VP) that wraps the on-chain VC.
    The VP proof must cover SHA256(challenge_bytes + canonical_vp_sans_proof_bytes)
    so the signature binds both the challenge and the presented credential.

    Body (JSON)
    -----------
    public_key : hex compressed secp256k1 public key (agent key = VP holder)
    challenge  : hex challenge from GET /api/vendor/<service>/challenge
    vp         : W3C VP object  {type, holder, verifiableCredential, proof}

    Auth steps (each vendor runs independently)
    -------------------------------------------
    1. Validate HMAC challenge (stateless, 30-second windows).
    2. Parse + validate VP structure; confirm holder == did:yadacoin:<public_key>.
    3. Verify VP proof signature.
    4. Extract VC from VP; read scope from credentialSubject.agentAuthorization.
    5. Build KEL; run revocation + pre-commitment checks.
    6. Cross-check VP scope against on-chain scope (VP cannot exceed KEL scope).
    7. Confirm this vendor's service is authorized in scope; book if available.
    """

    vendor_service: str = ""
    vendor_name: str = ""

    async def post(self):
        from yadacoin.core.keyeventlog import KeyEventLog

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

        # ── 1. Validate challenge ──────────────────────────────────────────── #
        if not _valid_challenge(public_key, challenge):
            self.set_status(401)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "challenge expired or invalid — request a fresh one",
                }
            )

        # ── 2. Parse public key ────────────────────────────────────────────── #
        try:
            pub_key_bytes = bytes.fromhex(public_key)
            if len(pub_key_bytes) not in (33, 65):
                raise ValueError("unexpected length")
        except Exception as exc:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": f"invalid public_key: {exc}"}
            )

        address = str(P2PKHBitcoinAddress.from_pubkey(pub_key_bytes))

        # ── 3. Validate VP structure ───────────────────────────────────────── #
        vp_types = vp.get("type", [])
        if "VerifiablePresentation" not in vp_types:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "vp.type must include 'VerifiablePresentation'",
                }
            )

        expected_holder = f"did:yadacoin:{public_key}"
        if vp.get("holder") != expected_holder:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        f"VP holder '{vp.get('holder')}' does not match "
                        f"supplied public_key"
                    ),
                }
            )

        # ── 4. Verify VP proof ─────────────────────────────────────────────── #
        ok, err = _verify_vp_proof(vp, pub_key_bytes, challenge)
        if not ok:
            self.set_status(401)
            return self.render_as_json(
                {"status": False, "message": f"VP proof invalid: {err}"}
            )

        # ── 5. Extract VC from VP and read presented scope ─────────────────── #
        vc_list = vp.get("verifiableCredential", [])
        if not vc_list:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "VP contains no verifiableCredential"}
            )

        vc = vc_list[0] if isinstance(vc_list, list) else vc_list
        vp_scope = _extract_scope(vc)

        # ── 6. Build KEL ───────────────────────────────────────────────────── #
        try:
            kel = await KeyEventLog.build_from_public_key(public_key)
        except Exception as exc:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": f"error retrieving KEL: {exc}"}
            )

        if not kel:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        "no KEL found for this public key — "
                        "key has not been provisioned on-chain"
                    ),
                }
            )

        # ── 7. Read on-chain scope + credentialStatus ─────────────────────── #
        # Read the VC from the KEL first so that credentialStatus.mode is known
        # before the revocation check (step 8).
        on_chain_scope = {}
        kel_status_mode = "rotation"  # default; "temporal" skips revocation check
        for entry in kel:
            tpkh = (
                getattr(entry, "twice_prerotated_key_hash", None)
                if not isinstance(entry, dict)
                else entry.get("twice_prerotated_key_hash")
            )
            if tpkh == address:
                raw_rel = (
                    getattr(entry, "relationship", None)
                    if not isinstance(entry, dict)
                    else entry.get("relationship")
                )
                if raw_rel:
                    try:
                        parsed = json.loads(
                            base64.b64decode(raw_rel).decode("utf-8", errors="replace")
                        )
                        on_chain_scope = _extract_scope(parsed)
                        cred_status = parsed.get("credentialStatus", {})
                        if isinstance(cred_status, dict):
                            kel_status_mode = cred_status.get(
                                "mode", "rotation"
                            ).lower()
                    except Exception:
                        pass
                break

        # ── 8. Revocation check (mode-aware) ──────────────────────────────── #
        # rotation: credential is one-time-use; reject if key has already rotated.
        # temporal: credential survives holder key rotation; skip this check and
        #           instead rely on step 9 to confirm the key is the current active
        #           key per the KEL.
        if kel_status_mode == "rotation":
            for entry in kel:
                if getattr(entry, "public_key_hash", None) == address:
                    self.set_status(403)
                    return self.render_as_json(
                        {
                            "status": False,
                            "message": "this key has already been used and is revoked",
                        }
                    )

        # ── 9. Pre-commitment check ────────────────────────────────────────── #
        # For both modes: the submitted public_key must be the current pre-committed
        # next signer per the KEL.  In temporal mode this confirms the holder is
        # presenting with their *current* active key even if prior keys have rotated.
        latest = kel[-1]
        if getattr(latest, "prerotated_key_hash", None) != address:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        "public key is not the pre-committed next signer — "
                        "the KEL has advanced past this key or it was never authorised"
                    ),
                }
            )

        on_chain_services = [s.lower() for s in on_chain_scope.get("services", [])]

        # ── 10. Scope checks ───────────────────────────────────────────────── #
        # On-chain scope is the authority ceiling — VP cannot exceed it.
        if on_chain_services and self.vendor_service not in on_chain_services:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        f"'{self.vendor_service}' is not in the on-chain "
                        f"authorised scope"
                    ),
                    "authorized_services": on_chain_services,
                }
            )

        vp_services = [s.lower() for s in vp_scope.get("services", [])]
        if vp_services and self.vendor_service not in vp_services:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        f"'{self.vendor_service}' is not in the presented VP scope"
                    ),
                }
            )

        # ── 11. Book ──────────────────────────────────────────────────────── #
        inv = _MOCK_INVENTORY.get(self.vendor_service, {})
        if not inv.get("available", False):
            self.set_status(422)
            return self.render_as_json(
                {
                    "status": False,
                    "service": self.vendor_service,
                    "message": f"No {self.vendor_service} available at this time",
                }
            )

        confirmation = _gen_confirmation(self.vendor_service, address)
        return self.render_as_json(
            {
                "status": True,
                "service": self.vendor_service,
                "vendor": self.vendor_name,
                "confirmation": confirmation,
                "authorized_address": address,
                "kel_depth": len(kel),
                "kel_txid": getattr(latest, "transaction_signature", None),
            }
        )


class FlightVendorHandler(VendorBaseHandler):
    """POST /ai-agent-auth/api/vendor/flight — mock flight booking vendor."""

    vendor_service = "flight"
    vendor_name = "SkyLink Airlines"


class HotelVendorHandler(VendorBaseHandler):
    """POST /ai-agent-auth/api/vendor/hotel — mock hotel booking vendor."""

    vendor_service = "hotel"
    vendor_name = "Grand Stay Hotels"


class CarVendorHandler(VendorBaseHandler):
    """POST /ai-agent-auth/api/vendor/car — mock car rental vendor."""

    vendor_service = "car"
    vendor_name = "DriveEasy Rentals"


HANDLERS = [
    (r"/ai-agent-auth", AgentAuthAppHandler),
    (r"/ai-agent-auth/api/chat", AgentChatHandler),
    (r"/ai-agent-auth/api/challenge", AgentChallengeHandler),
    (
        r"/ai-agent-auth/api/travel",
        TravelBookingHandler,
    ),  # legacy — single combined endpoint
    # Per-vendor endpoints: each vendor issues its own challenge and verifies a VP
    (r"/ai-agent-auth/api/vendor/flight/challenge", AgentChallengeHandler),
    (r"/ai-agent-auth/api/vendor/hotel/challenge", AgentChallengeHandler),
    (r"/ai-agent-auth/api/vendor/car/challenge", AgentChallengeHandler),
    (r"/ai-agent-auth/api/vendor/flight", FlightVendorHandler),
    (r"/ai-agent-auth/api/vendor/hotel", HotelVendorHandler),
    (r"/ai-agent-auth/api/vendor/car", CarVendorHandler),
    (
        r"/aiagentauthstatic/(.*)",
        tornado.web.StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "templates")},
    ),
]
