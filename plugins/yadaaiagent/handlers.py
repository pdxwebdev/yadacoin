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
    "car": {"available": False, "reason": "No rental cars available for these dates"},
}


def _gen_confirmation(service: str, seed: str) -> str:
    pfx = {"hotel": "HTL", "flight": "FLT", "car": "CAR"}.get(service, "SVC")
    h = hashlib.sha256(f"{seed}{service}".encode()).hexdigest()[:6].upper()
    return f"{pfx}-{h}"


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
        scope = {}
        raw_rel = getattr(latest, "relationship", None)
        if raw_rel:
            try:
                scope = json.loads(
                    base64.b64decode(raw_rel).decode("utf-8", errors="replace")
                )
            except Exception:
                pass  # unstructured relationship — no scope restrictions

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


HANDLERS = [
    (r"/ai-agent-auth", AgentAuthAppHandler),
    (r"/ai-agent-auth/api/challenge", AgentChallengeHandler),
    (r"/ai-agent-auth/api/travel", TravelBookingHandler),
    (
        r"/aiagentauthstatic/(.*)",
        tornado.web.StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "templates")},
    ),
]
