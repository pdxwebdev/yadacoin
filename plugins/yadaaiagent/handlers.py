"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

yadaaiagentauth — demo plugin showing how on-chain Key Event Log (KEL)
entries plus client-side key derivation/rotation can be used as
one-time-use authentication credentials for AI agents.

Endpoints
---------
GET  /ai-agent-auth                — demo UI
POST /ai-agent-auth/api/action     — protected agent endpoint:
       Accepts a private_key + payload.  The handler derives the
       compressed public key + P2PKH address from the private key, then
       authenticates the caller iff:
         1. P2PKH(pub) equals the latest KEL entry's
            prerotated_key_hash for that key's KEL — i.e. the key is
            pre-committed as the next signer.
         2. The address has NOT already appeared as
            ``public_key_hash`` in any KEL entry (revocation check).
       The agent holds the private key so it can use it to perform
       downstream actions on behalf of the operator that provisioned
       it.
"""

import base64
import hashlib
import json
import os
import time

import tornado.web
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey as _CoincurvePrivateKey

from yadacoin.http.base import BaseHandler


class AgentAuthAppHandler(BaseHandler):
    """GET /ai-agent-auth — serve the demo UI."""

    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")

    async def get(self):
        return self.render("index.html")


class AgentActionHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/action

    Body (JSON)
    -----------
    private_key : str   hex-encoded 32-byte secp256k1 private key — the
                        one-time-use agent credential the operator
                        provisioned via /key-rotation/derived-child-key.
    payload     : str   arbitrary string (the agent's action request).
    prompt      : str   (optional) original natural-language prompt.

    The handler derives the compressed public key from ``private_key``,
    computes its P2PKH address, builds the KEL for that public key, and
    authenticates iff:
      - ``address`` has not appeared as ``public_key_hash`` in any KEL
        entry (revocation check), AND
      - ``kel[-1].prerotated_key_hash == address`` — i.e. the key is
        the pre-committed next signer.

    The endpoint then "performs" the agent's action on behalf of the
    operator using the supplied private key.  In this demo it just
    echoes a mock result — a real integration would use the private
    key to sign downstream operations (transactions, API calls, etc.).
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

        private_key_hex = (body.get("private_key") or "").strip()
        payload = body.get("payload") or ""
        prompt = body.get("prompt") or ""

        if not private_key_hex or not payload:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "private_key and payload are required",
                }
            )

        # ---------- 1. Derive public key + address from private key ---------- #
        try:
            priv_bytes = bytes.fromhex(private_key_hex)
            if len(priv_bytes) != 32:
                raise ValueError("private_key must be 32 bytes (64 hex chars)")
            pub_key_bytes = _CoincurvePrivateKey(priv_bytes).public_key.format(
                compressed=True
            )
        except Exception as exc:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": f"invalid private_key: {exc}",
                }
            )

        public_key = pub_key_bytes.hex()
        address = str(P2PKHBitcoinAddress.from_pubkey(pub_key_bytes))

        # ---------- 2. Build the KEL for this public key ---------- #
        try:
            kel = await KeyEventLog.build_from_public_key(public_key)
        except Exception as exc:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": f"error retrieving key event log: {exc}",
                    "address": address,
                }
            )

        if not kel:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        "no key event log found for this public key — "
                        "the agent key has not been provisioned on-chain"
                    ),
                    "address": address,
                }
            )

        # ---------- 3. Reject if the key has already been used ---------- #
        for entry in kel:
            if getattr(entry, "public_key_hash", None) == address:
                source = "mempool" if getattr(entry, "mempool", False) else "blockchain"
                self.set_status(403)
                return self.render_as_json(
                    {
                        "status": False,
                        "message": (
                            f"this key has already been used (revoked) — "
                            f"found as public_key_hash in {source} KEL entry "
                            f"{getattr(entry, 'transaction_signature', '')}"
                        ),
                        "address": address,
                        "kel_length": len(kel),
                    }
                )

        # ---------- 4. Verify the key is the pre-committed next signer ---------- #
        latest = kel[-1]
        if getattr(latest, "prerotated_key_hash", None) != address:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        "public key is not the pre-committed next signer in the "
                        "latest KEL entry — it is not authorized for one-time use"
                    ),
                    "address": address,
                    "expected_prerotated_key_hash": getattr(
                        latest, "prerotated_key_hash", None
                    ),
                    "kel_length": len(kel),
                }
            )

        # ---------- 5. Authenticated — perform the agent's action ---------- #
        # In a real integration the handler would now use `priv_bytes`
        # to sign operations on behalf of the operator (downstream API
        # calls, transactions, etc.).  Here we just return a mock
        # result that confirms possession of the private key.
        return self.render_as_json(
            {
                "status": True,
                "message": "agent authenticated; action performed",
                "authenticated_address": address,
                "public_key": public_key,
                "kel_length": len(kel),
                "kel_inception_txid": getattr(kel[0], "transaction_signature", None),
                "committed_via_prev_entry": {
                    "transaction_id": getattr(latest, "transaction_signature", None),
                    "public_key_hash": getattr(latest, "public_key_hash", None),
                    "prerotated_key_hash": getattr(latest, "prerotated_key_hash", None),
                    "twice_prerotated_key_hash": getattr(
                        latest, "twice_prerotated_key_hash", None
                    ),
                    "relationship": (
                        base64.b64decode(
                            getattr(latest, "relationship", "") or ""
                        ).decode("utf-8", errors="replace")
                        if getattr(latest, "relationship", None)
                        else None
                    ),
                    "source": (
                        "mempool" if getattr(latest, "mempool", False) else "blockchain"
                    ),
                },
                "agent_prompt": prompt,
                "mock_action_result": {
                    "intent": "fetch_account_summary",
                    "data": {
                        "account_id": "demo-acct-7421",
                        "balance": 12345.67,
                        "currency": "YDA",
                        "as_of": int(time.time()),
                    },
                    "note": (
                        "Mock data. The server holds your private key for "
                        "the duration of this request and could now sign "
                        "downstream operations on your behalf."
                    ),
                },
                "payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            }
        )


HANDLERS = [
    (r"/ai-agent-auth", AgentAuthAppHandler),
    (r"/ai-agent-auth/api/action", AgentActionHandler),
    (
        r"/aiagentauthstatic/(.*)",
        tornado.web.StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "templates")},
    ),
]
