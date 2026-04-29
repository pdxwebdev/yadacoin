"""
yadacoin_agent_auth.py — Server-side Python SDK for the YadaCoin KEL Agent Auth Protocol.

See: docs/kel_agent_auth_spec.md for the full protocol specification.

Installation
------------
    pip install coincurve bitcoin

    # For the built-in YadaCoin node provider:
    pip install yadacoin

    # For the REST provider (no local node required):
    pip install aiohttp

Quick start (Tornado)
---------------------
    import os
    from yadacoin_agent_auth import AgentAuthValidator, AuthError

    validator = AgentAuthValidator(
        challenge_secret=os.environ["YADACOIN_AGENT_SECRET"].encode()
    )

    class ChallengeHandler(BaseHandler):
        async def get(self):
            public_key = self.get_argument("public_key")
            self.write(validator.make_challenge(public_key))

    class BookingHandler(BaseHandler):
        async def post(self):
            body = json.loads(self.request.body)
            try:
                auth = await validator.validate(
                    public_key=body["public_key"],
                    challenge=body["challenge"],
                    signature=body["signature"],
                )
            except AuthError as exc:
                self.set_status(exc.http_status)
                return self.write({"error": str(exc)})

            scope = auth.scope        # dict from on-chain relationship field
            address = auth.address    # P2PKH address of the agent key
            kel_depth = len(auth.kel)
            # ... your service logic ...
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AuthError(Exception):
    """Raised by AgentAuthValidator.validate() on any authentication failure.

    Attributes
    ----------
    http_status : int   Suggested HTTP response code (401, 403, 400).
    """

    def __init__(self, message: str, http_status: int = 401):
        super().__init__(message)
        self.http_status = http_status


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class AuthResult:
    """Returned by AgentAuthValidator.validate() on success.

    Attributes
    ----------
    address      : P2PKH address derived from public_key.
    pub_key_bytes: Raw compressed public key bytes (33 bytes).
    kel          : Full key event log entries for this key.
    scope        : Dict parsed from the on-chain relationship field,
                   or {} if no structured scope was committed.
    kel_txid     : transaction_signature of the latest KEL entry.
    """

    address: str
    pub_key_bytes: bytes
    kel: List[Any]
    scope: Dict[str, Any] = field(default_factory=dict)
    kel_txid: Optional[str] = None


# ---------------------------------------------------------------------------
# KEL providers
# ---------------------------------------------------------------------------


@runtime_checkable
class KelProvider(Protocol):
    """Interface for resolving a Key Event Log by public key.

    Implement this protocol to use a custom blockchain backend.
    """

    async def build_from_public_key(self, public_key_hex: str) -> List[Any]:
        """Return the ordered KEL entries for *public_key_hex*, or [] if none."""
        ...


class YadaCoinNodeKelProvider:
    """Uses a locally running YadaCoin node (requires the yadacoin package)."""

    async def build_from_public_key(self, public_key_hex: str) -> List[Any]:
        from yadacoin.core.keyeventlog import KeyEventLog  # type: ignore

        return await KeyEventLog.build_from_public_key(public_key_hex)


class YadaCoinRestKelProvider:
    """Fetches the KEL from the public YadaCoin REST API.

    No local YadaCoin node is required.  Requires *aiohttp*.

    Parameters
    ----------
    base_url : Root URL of a YadaCoin node, e.g. ``"https://yadacoin.io"``.
    """

    def __init__(self, base_url: str = "https://yadacoin.io"):
        self.base_url = base_url.rstrip("/")

    async def build_from_public_key(self, public_key_hex: str) -> List[Any]:
        import aiohttp  # type: ignore

        url = f"{self.base_url}/key-rotation/kel?public_key={public_key_hex}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data if isinstance(data, list) else data.get("kel", [])


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class AgentAuthValidator:
    """Validates YadaCoin KEL Agent Auth requests.

    Parameters
    ----------
    challenge_secret : HMAC secret bytes.  Override with the
                       ``YADACOIN_AGENT_SECRET`` environment variable in
                       production.  Never use the default in production.
    kel_provider     : Object implementing KelProvider.  Defaults to
                       YadaCoinNodeKelProvider (requires local yadacoin install).
                       Use YadaCoinRestKelProvider for stand-alone deployments.
    window_seconds   : Challenge window size in seconds (default 30).
    accepted_windows : Number of past windows to accept (default 1, i.e. up to
                       2× window_seconds of tolerance).
    """

    def __init__(
        self,
        challenge_secret: bytes,
        kel_provider: Optional[KelProvider] = None,
        window_seconds: int = 30,
        accepted_windows: int = 1,
    ):
        if not challenge_secret:
            raise ValueError("challenge_secret must not be empty")
        self._secret = challenge_secret
        self._kel = kel_provider or YadaCoinNodeKelProvider()
        self._window = window_seconds
        self._accepted = accepted_windows

    # ------------------------------------------------------------------
    # Challenge helpers
    # ------------------------------------------------------------------

    def _make_challenge(self, public_key: str, window: int) -> str:
        msg = f"{public_key}:{window}".encode("utf-8")
        return _hmac.new(self._secret, msg, hashlib.sha256).hexdigest()

    def make_challenge(self, public_key: str) -> Dict[str, Any]:
        """Return a fresh challenge dict for *public_key*.

        Returns
        -------
        {"challenge": "<hex>", "expires_in": <seconds>}
        """
        if not public_key:
            raise ValueError("public_key is required")
        now = int(time.time())
        window = now // self._window
        challenge = self._make_challenge(public_key, window)
        expires_in = self._window - (now % self._window)
        return {"challenge": challenge, "expires_in": expires_in}

    def validate_challenge(self, public_key: str, challenge: str) -> bool:
        """Return True if *challenge* is valid for *public_key* right now."""
        now = int(time.time())
        current = now // self._window
        for offset in range(self._accepted + 1):
            expected = self._make_challenge(public_key, current - offset)
            if _hmac.compare_digest(challenge, expected):
                return True
        return False

    # ------------------------------------------------------------------
    # Full validation
    # ------------------------------------------------------------------

    async def validate(
        self,
        public_key: str,
        challenge: str,
        signature: str,
    ) -> AuthResult:
        """Authenticate an agent request and return an AuthResult on success.

        Performs all 6 required validation steps from the spec:
          1. Challenge validity (HMAC-SHA256, 30-second windows)
          2. secp256k1 signature verification
          3. KEL existence
          4. Revocation check
          5. Pre-commitment check
          6. Scope parsing (does NOT enforce — call enforce_scope() separately)

        Raises AuthError on any failure with an appropriate http_status.
        """
        public_key = (public_key or "").strip()
        challenge = (challenge or "").strip()
        signature = (signature or "").strip()

        if not public_key or not challenge or not signature:
            raise AuthError("public_key, challenge, and signature are required", 400)

        # Step 1 — challenge validity
        if not self.validate_challenge(public_key, challenge):
            raise AuthError("challenge expired or invalid — request a fresh one", 401)

        # Step 2 — parse public key
        try:
            pub_key_bytes = bytes.fromhex(public_key)
            if len(pub_key_bytes) not in (33, 65):
                raise ValueError("unexpected length")
        except Exception as exc:
            raise AuthError(f"invalid public_key: {exc}", 400) from exc

        try:
            from bitcoin.wallet import P2PKHBitcoinAddress  # type: ignore

            address = str(P2PKHBitcoinAddress.from_pubkey(pub_key_bytes))
        except Exception as exc:
            raise AuthError(
                f"could not derive address from public_key: {exc}", 400
            ) from exc

        # Step 2 — signature verification
        try:
            sig_bytes = base64.b64decode(signature)
        except Exception as exc:
            raise AuthError(f"signature is not valid base64: {exc}", 401) from exc

        try:
            from coincurve import verify_signature as _verify  # type: ignore

            msg_hash = hashlib.sha256(challenge.encode("utf-8")).digest()
            ok = _verify(sig_bytes, msg_hash, pub_key_bytes, hasher=None)
            if not ok:
                raise ValueError("verify_signature returned False")
        except AuthError:
            raise
        except Exception as exc:
            raise AuthError(f"signature verification failed: {exc}", 401) from exc

        # Step 3 — KEL existence
        try:
            kel = await self._kel.build_from_public_key(public_key)
        except Exception as exc:
            raise AuthError(f"KEL lookup error: {exc}", 403) from exc

        if not kel:
            raise AuthError(
                "no KEL found for this public key — key has not been provisioned on-chain",
                403,
            )

        # Step 4 — revocation check
        for entry in kel:
            pkh = (
                getattr(entry, "public_key_hash", None) or entry.get("public_key_hash")
                if isinstance(entry, dict)
                else None
            )
            if pkh == address:
                raise AuthError(
                    "this key has already been spent and is revoked",
                    403,
                )

        # Step 5 — pre-commitment check
        latest = kel[-1]
        prerotated = (
            getattr(latest, "prerotated_key_hash", None)
            if not isinstance(latest, dict)
            else latest.get("prerotated_key_hash")
        )
        if prerotated != address:
            raise AuthError(
                "public key is not the pre-committed next signer in the KEL",
                403,
            )

        # Step 6 — parse scope (does not enforce; call enforce_scope separately)
        scope: Dict[str, Any] = {}
        raw_rel = (
            getattr(latest, "relationship", None)
            if not isinstance(latest, dict)
            else latest.get("relationship")
        )
        if raw_rel:
            try:
                scope = json.loads(
                    base64.b64decode(raw_rel).decode("utf-8", errors="replace")
                )
            except Exception:
                pass  # unstructured relationship — no scope parsed

        kel_txid = (
            getattr(latest, "transaction_signature", None)
            if not isinstance(latest, dict)
            else latest.get("transaction_signature") or latest.get("id")
        )

        return AuthResult(
            address=address,
            pub_key_bytes=pub_key_bytes,
            kel=kel,
            scope=scope,
            kel_txid=kel_txid,
        )

    # ------------------------------------------------------------------
    # Scope enforcement helpers
    # ------------------------------------------------------------------

    @staticmethod
    def enforce_scope(
        auth: AuthResult,
        *,
        services: Optional[List[str]] = None,
        dest: Optional[str] = None,
    ) -> None:
        """Raise AuthError(403) if the request exceeds the committed scope.

        Parameters
        ----------
        auth     : AuthResult from validate().
        services : Services being requested (e.g. ["hotel", "flight"]).
        dest     : Destination string being requested.
        """
        scope = auth.scope
        scope_services = [s.lower() for s in scope.get("services", [])]
        scope_dest = (scope.get("dest") or "").strip().lower()

        if dest and scope_dest and dest.strip().lower() != scope_dest:
            raise AuthError(
                f"destination '{dest}' is not authorised — scope commits to '{scope.get('dest')}'",
                403,
            )

        if services and scope_services:
            for svc in services:
                if svc.lower() not in scope_services:
                    raise AuthError(
                        f"service '{svc}' is not in the authorised scope",
                        403,
                    )


# ---------------------------------------------------------------------------
# Tornado mixin (optional convenience)
# ---------------------------------------------------------------------------


class AgentAuthMixin:
    """Mixin for Tornado RequestHandlers.

    Usage
    -----
        class MyHandler(AgentAuthMixin, BaseHandler):
            _agent_validator = AgentAuthValidator(
                challenge_secret=os.environ["YADACOIN_AGENT_SECRET"].encode()
            )

            async def post(self):
                auth = await self.require_agent_auth()
                scope = auth.scope
                ...

    The mixin reads public_key, challenge, and signature from the JSON body
    and calls validator.validate().  On failure it writes the error response
    and returns None; the handler should check for None and return early.
    """

    _agent_validator: AgentAuthValidator  # set on the class

    async def require_agent_auth(self) -> Optional[AuthResult]:
        try:
            body = json.loads(self.request.body)  # type: ignore[attr-defined]
        except Exception:
            self.set_status(400)  # type: ignore[attr-defined]
            self.write({"status": False, "message": "invalid JSON body"})  # type: ignore[attr-defined]
            return None

        try:
            auth = await self._agent_validator.validate(
                public_key=body.get("public_key", ""),
                challenge=body.get("challenge", ""),
                signature=body.get("signature", ""),
            )
        except AuthError as exc:
            self.set_status(exc.http_status)  # type: ignore[attr-defined]
            self.write({"status": False, "message": str(exc)})  # type: ignore[attr-defined]
            return None

        return auth
