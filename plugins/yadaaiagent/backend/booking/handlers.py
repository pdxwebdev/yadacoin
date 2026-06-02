"""booking_handlers.py — Travel, vendor, and booking HTTP handlers."""
import json

from yadacoin_agent_auth import AgentAuthValidator, AuthError

from yadacoin.http.base import BaseHandler

from ..agent.handlers import AgentChallengeHandler, AgentChatHandler
from ..core.auth import _validator
from .tools import (
    _UI_HINT_SUFFIX,
    _VENDOR_TOOLS,
    VENDOR_REGISTRY,
    _gen_booking_credential,
    _gen_confirmation,
)

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

        v_choices = []

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
            system_prompt = f"{base_prompt}\n\nCustomer's authorized scope: {scope_ctx}\n{_UI_HINT_SUFFIX}"
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
                v_choices = (
                    parsed.get("choices")
                    if isinstance(parsed.get("choices"), list)
                    else []
                )
            except Exception:
                reply = content
                complete = False
                exit_vendor = False
                v_choices = []
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
            "choices": v_choices,
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


# ── Location-recovery hints (deprecated) ─────────────────────────────────────
# Encrypted hint labels are now embedded directly in the on-chain
# {"recovery": ...} announcement (see RecoveryAnnouncement.hints_iv /
# .hints_ct).  The previous server-side `location_recovery_hints` Mongo
# collection has been removed; the LocationHintsHandler endpoint is gone.
# Recovery clients now fetch hints via /api/find-recovery-tip?lookup_id=<hex>
# and decrypt them locally with a key derived from the user's Recovery Code.


# ── Recovery-tip lookup ────────────────────────────────────────────────────────
# Given a witnessHash (the public commitment-of-commitment that the user
# announced on-chain at setup time), find the announcing transaction's KEL
# and return its current tip pkh + tip pubkey. The recovery client needs the
# tip pkh to populate `prev_public_key_hash` on the new recovers-inception so
# that consensus can verify the delegator KEL.
#
# This is a pure on-chain scan — no per-user state is stored server-side.
