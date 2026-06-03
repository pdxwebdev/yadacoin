"""oauth_handlers.py — OAuth 2.0 Device Authorization Grant handlers (RFC 8628)."""
import datetime as _datetime
import hashlib as _hashlib
import json
import os
import secrets as _secrets
import urllib.parse as _oauthparse

from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

from yadacoin.http.base import BaseHandler

from ..core.auth import _OAUTH_PROVIDERS


def _compact_to_der(sig64: bytes) -> bytes:
    """Convert a 64-byte compact (R‖S) secp256k1 signature to DER encoding."""
    r = sig64[:32].lstrip(b"\x00") or b"\x00"
    s = sig64[32:].lstrip(b"\x00") or b"\x00"
    if r[0] & 0x80:
        r = b"\x00" + r
    if s[0] & 0x80:
        s = b"\x00" + s
    body = b"\x02" + bytes([len(r)]) + r + b"\x02" + bytes([len(s)]) + s
    return b"\x30" + bytes([len(body)]) + body


def _verify_secp256k1(pubkey_hex: str, message_hex: str, sig_hex: str) -> bool:
    """Verify a compact secp256k1 ECDSA signature.

    The frontend uses noble/secp256k1 v3 with prehash=true (the default), so it
    SHA-256 hashes the raw message bytes before signing.  The signature is the
    64-byte compact (R‖S) representation, hex-encoded.

    coincurve.verify_signature expects DER-encoded signatures, so we convert.

    Args:
        pubkey_hex:  Compressed public key (33 bytes, 66 hex chars).
        message_hex: Raw message bytes as hex (NOT the hash).
        sig_hex:     Compact 64-byte ECDSA signature as hex.

    Returns:
        True if the signature is valid, False otherwise.
    """
    try:
        from coincurve import verify_signature as _cc_verify  # type: ignore

        compact_sig = bytes.fromhex(sig_hex)
        if len(compact_sig) != 64:
            return False
        der_sig = _compact_to_der(compact_sig)
        msg_hash = _hashlib.sha256(bytes.fromhex(message_hex)).digest()
        pub_bytes = bytes.fromhex(pubkey_hex)
        return bool(_cc_verify(der_sig, msg_hash, pub_bytes, hasher=None))
    except Exception:
        return False


class OAuthDeviceStartHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/oauth/<provider>/device/start

    Initiates the Device Authorization Grant flow.  Calls the provider's
    device authorization endpoint, stores the device_code in MongoDB (keyed
    by an opaque session_nonce), and returns the user-facing code + URL to
    the browser.  No client_secret or callback URL required.
    """

    async def post(self, provider: str):
        provider = provider.lower().strip()
        cfg = _OAUTH_PROVIDERS.get(provider)
        if not cfg:
            self.set_status(404)
            return self.render_as_json({"error": f"unknown provider '{provider}'"})

        # Parse body early so we can read the browser-supplied client_id
        try:
            req_body = json.loads(self.request.body) if self.request.body else {}
        except Exception:
            req_body = {}

        # Browser-supplied client_id (from the user's Skills settings) takes
        # precedence; fall back to the server config value.
        browser_client_id = (req_body.get("client_id") or "").strip()
        server_client_id = (getattr(self.config, cfg["config_key"], "") or "").strip()
        client_id = browser_client_id or server_client_id
        if not client_id:
            self.set_status(503)
            return self.render_as_json(
                {
                    "error": f"{provider} OAuth not configured. "
                    f"Set your Client ID in Settings → Skills, or ask the node "
                    f"operator to set '{cfg['config_key']}' in config.json."
                }
            )
        cfg = dict(cfg, client_id=client_id)

        try:
            device_data = await self._start_device_flow(cfg)
        except Exception as exc:
            self.set_status(502)
            return self.render_as_json({"error": f"Device flow init failed: {exc}"})

        # Normalize field name differences across providers
        # (Google uses 'verification_url'; RFC 8628 standard is 'verification_uri')
        verification_uri = (
            device_data.get("verification_uri")
            or device_data.get("verification_url")
            or "https://github.com/login/device"
        )
        expires_in = int(device_data.get("expires_in", 300))

        # Optional token encryption key supplied by the browser (hex-encoded
        # sha256 of the provisioned key from the connect rotation). When present
        # the poll handler will encrypt the access_token before storing it so
        # no plaintext token ever persists in the database.
        token_enc_key = (req_body.get("token_enc_key") or "").strip()
        # Validate: must be a 64-char hex string (32-byte sha256) or empty
        if token_enc_key and (
            len(token_enc_key) != 64
            or not all(c in "0123456789abcdefABCDEF" for c in token_enc_key)
        ):
            token_enc_key = ""

        session_nonce = _secrets.token_urlsafe(32)
        try:
            session_doc = {
                "nonce": session_nonce,
                "provider": provider,
                "status": "pending",
                "device_code": device_data["device_code"],
                "expires_at": _datetime.datetime.utcnow()
                + _datetime.timedelta(seconds=expires_in),
            }
            if token_enc_key:
                session_doc["token_enc_key"] = token_enc_key
            # Store the resolved client_id so the poll handler uses the same app
            session_doc["client_id"] = client_id
            await self.config.mongo.async_db.web2_oauth_sessions.insert_one(session_doc)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error(
                "OAuthDeviceStartHandler: DB insert failed: %s", exc
            )
            self.set_status(500)
            return self.render_as_json({"error": "session store unavailable"})

        return self.render_as_json(
            {
                "session_nonce": session_nonce,
                "user_code": device_data.get("user_code", ""),
                "verification_uri": verification_uri,
                "expires_in": expires_in,
                "interval": int(device_data.get("interval", 5)),
            }
        )

    async def _start_device_flow(self, cfg: dict) -> dict:
        client = AsyncHTTPClient()
        req = HTTPRequest(
            url=cfg["device_auth_url"],
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            body=_oauthparse.urlencode(
                {
                    "client_id": cfg["client_id"],
                    "scope": cfg.get("scope", ""),
                }
            ),
            request_timeout=15.0,
        )
        resp = await client.fetch(req, raise_error=False)
        body_str = resp.body.decode("utf-8", errors="replace")
        if resp.code not in (200, 201):
            raise ValueError(f"HTTP {resp.code}: {body_str[:200]}")
        data = json.loads(body_str)
        if "error" in data:
            raise ValueError(data.get("error_description") or data["error"])
        if not data.get("device_code"):
            raise ValueError("No device_code in provider response")
        return data


class OAuthDevicePollHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/oauth/<provider>/device/poll
    Body: {"session_nonce": "<nonce>"}

    Called by the browser every `interval` seconds while the user is
    completing the device authorization on the provider's website.
    Returns {"status": "pending"|"authorized"|"slow_down"|"error"}.

    On "authorized", the access_token is stored in MongoDB under the same
    nonce so it can be resolved by AgentChatHandler when the client passes
    web2_sessions: {provider: nonce} in /api/chat requests.
    """

    async def post(self, provider: str):
        provider = provider.lower().strip()
        cfg = _OAUTH_PROVIDERS.get(provider)
        if not cfg:
            self.set_status(404)
            return self.render_as_json({"error": f"unknown provider '{provider}'"})
        client_id = (getattr(self.config, cfg["config_key"], "") or "").strip()
        cfg = dict(cfg, client_id=client_id)

        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid JSON body"})

        nonce = (body.get("session_nonce") or "").strip()
        if not nonce:
            self.set_status(400)
            return self.render_as_json({"error": "session_nonce required"})

        try:
            session_doc = await self.config.mongo.async_db.web2_oauth_sessions.find_one(
                {"nonce": nonce, "provider": provider}
            )
        except Exception:
            self.set_status(500)
            return self.render_as_json({"error": "session store error"})

        if not session_doc:
            self.set_status(404)
            return self.render_as_json({"error": "session not found or expired"})

        if session_doc.get("status") == "authorized":
            return self.render_as_json({"status": "authorized"})

        device_code = session_doc.get("device_code", "")
        if not device_code:
            self.set_status(500)
            return self.render_as_json({"error": "corrupt session: no device_code"})

        # Use client_id stored at start time (may have been supplied by the browser)
        if session_doc.get("client_id"):
            cfg = dict(cfg, client_id=session_doc["client_id"])

        try:
            token_data = await self._poll_token(cfg, device_code)
        except Exception as exc:
            return self.render_as_json({"status": "error", "message": str(exc)})

        error_code = token_data.get("error", "")
        if error_code == "authorization_pending":
            return self.render_as_json({"status": "pending"})
        if error_code == "slow_down":
            return self.render_as_json({"status": "slow_down"})
        if error_code in ("expired_token", "access_denied"):
            return self.render_as_json(
                {
                    "status": "error",
                    "message": f"Authorization {error_code.replace('_', ' ')}",
                }
            )
        if error_code:
            return self.render_as_json(
                {
                    "status": "error",
                    "message": token_data.get("error_description", error_code),
                }
            )

        access_token = token_data.get("access_token", "")
        if not access_token:
            return self.render_as_json(
                {"status": "error", "message": "No access_token in provider response"}
            )

        # ── Fetch profile while we still have the plaintext token ─────────
        # This is cached in the session doc so the /me endpoint can return
        # the account label even after the token is encrypted.
        display_name = ""
        identifier = ""
        try:
            _profile_client = AsyncHTTPClient()
            if provider == "microsoft":
                _pr = await _profile_client.fetch(
                    HTTPRequest(
                        url="https://graph.microsoft.com/v1.0/me",
                        method="GET",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Accept": "application/json",
                        },
                        request_timeout=8.0,
                    ),
                    raise_error=False,
                )
                if _pr.code == 200:
                    _me = json.loads(_pr.body)
                    identifier = _me.get("mail") or _me.get("userPrincipalName") or ""
                    display_name = _me.get("displayName") or identifier
            elif provider == "github":
                _pr = await _profile_client.fetch(
                    HTTPRequest(
                        url="https://api.github.com/user",
                        method="GET",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Accept": "application/vnd.github+json",
                            "User-Agent": "YadaCoin",
                        },
                        request_timeout=8.0,
                    ),
                    raise_error=False,
                )
                if _pr.code == 200:
                    _user = json.loads(_pr.body)
                    identifier = _user.get("login") or ""
                    display_name = _user.get("name") or identifier
        except Exception:
            pass  # profile fetch is best-effort; label falls back to empty

        # ── Wallet-mode encryption ─────────────────────────────────────────
        # If the browser supplied a token_enc_key at device/start time it is
        # stored in session_doc.  Encrypt the plaintext token with AES-256-GCM
        # so that no plaintext token is ever persisted in MongoDB.  The
        # ciphertext + IV are also returned to the client so it can store them
        # locally (matching the Microsoft localStorage format).
        token_enc_key_hex = (session_doc.get("token_enc_key") or "").strip()
        encrypted_access_token = ""
        token_iv_hex = ""
        stored_token = access_token  # default: plaintext
        if token_enc_key_hex:
            try:
                key_bytes = bytes.fromhex(token_enc_key_hex)
                aesgcm = _AESGCM(key_bytes)
                iv_bytes = os.urandom(12)
                ct_bytes = aesgcm.encrypt(iv_bytes, access_token.encode("utf-8"), None)
                encrypted_access_token = ct_bytes.hex()
                token_iv_hex = iv_bytes.hex()
                stored_token = encrypted_access_token  # store ciphertext only
            except Exception:
                pass  # fall back to plaintext storage on any crypto error

        try:
            set_fields = {
                "access_token": stored_token,
                "refresh_token": token_data.get("refresh_token", ""),
                "token_scope": token_data.get("scope", ""),
                "status": "authorized",
                "authorized_at": _datetime.datetime.utcnow(),
                "expires_at": _datetime.datetime.utcnow()
                + _datetime.timedelta(days=30),
            }
            if token_iv_hex:
                set_fields["token_iv"] = token_iv_hex
            if display_name:
                set_fields["display_name"] = display_name
            if identifier:
                set_fields["identifier"] = identifier
            await self.config.mongo.async_db.web2_oauth_sessions.update_one(
                {"_id": session_doc["_id"]},
                {"$set": set_fields, "$unset": {"device_code": ""}},
            )
        except Exception as exc:
            return self.render_as_json(
                {"status": "error", "message": f"Failed to store token: {exc}"}
            )

        result = {"status": "authorized"}
        if encrypted_access_token:
            result["encrypted_access_token"] = encrypted_access_token
            result["iv"] = token_iv_hex
        return self.render_as_json(result)

    async def _poll_token(self, cfg: dict, device_code: str) -> dict:
        client = AsyncHTTPClient()
        payload = {
            "client_id": cfg["client_id"],
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }
        if cfg.get("client_secret"):
            payload["client_secret"] = cfg["client_secret"]
        req = HTTPRequest(
            url=cfg["token_url"],
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            body=_oauthparse.urlencode(payload),
            request_timeout=15.0,
        )
        resp = await client.fetch(req, raise_error=False)
        body_str = resp.body.decode("utf-8", errors="replace")
        # 400 is valid — it carries authorization_pending / slow_down error codes
        if resp.code not in (200, 400):
            raise ValueError(f"HTTP {resp.code}: {body_str[:200]}")
        return json.loads(body_str)


class OAuthMeHandler(BaseHandler):
    """
    GET /ai-agent-auth/api/oauth/<provider>/me?nonce=<nonce>

    Returns basic profile info for an authorized session so the frontend
    can label the account (e.g. "matt@work.com") without exposing the token.
    Response: { "display_name": "...", "identifier": "..." }
    """

    async def get(self, provider: str):
        provider = provider.lower().strip()
        nonce = (self.get_argument("nonce", "") or "").strip()
        if not nonce:
            self.set_status(400)
            return self.render_as_json({"error": "nonce required"})

        try:
            session_doc = await self.config.mongo.async_db.web2_oauth_sessions.find_one(
                {"nonce": nonce, "provider": provider, "status": "authorized"}
            )
        except Exception:
            self.set_status(500)
            return self.render_as_json({"error": "session store error"})

        if not session_doc:
            self.set_status(404)
            return self.render_as_json({"error": "session not found or not authorized"})

        # Return cached profile if it was fetched at poll time (encrypted-token flow).
        cached_display_name = session_doc.get("display_name", "")
        cached_identifier = session_doc.get("identifier", "")
        if cached_display_name or cached_identifier:
            return self.render_as_json(
                {"display_name": cached_display_name, "identifier": cached_identifier}
            )

        # Legacy: session has plaintext access_token — fetch live from provider.
        access_token = session_doc.get("access_token", "")
        if not access_token:
            return self.render_as_json({"display_name": "", "identifier": ""})

        client = AsyncHTTPClient()
        try:
            if provider == "microsoft":
                resp = await client.fetch(
                    HTTPRequest(
                        url="https://graph.microsoft.com/v1.0/me",
                        method="GET",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Accept": "application/json",
                        },
                        request_timeout=10.0,
                    ),
                    raise_error=False,
                )
                if resp.code == 200:
                    me = json.loads(resp.body)
                    identifier = me.get("mail") or me.get("userPrincipalName") or ""
                    display_name = me.get("displayName") or identifier
                    return self.render_as_json(
                        {"display_name": display_name, "identifier": identifier}
                    )
            elif provider == "github":
                resp = await client.fetch(
                    HTTPRequest(
                        url="https://api.github.com/user",
                        method="GET",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Accept": "application/vnd.github+json",
                            "User-Agent": "YadaCoin",
                        },
                        request_timeout=10.0,
                    ),
                    raise_error=False,
                )
                if resp.code == 200:
                    user = json.loads(resp.body)
                    login = user.get("login") or ""
                    name = user.get("name") or login
                    return self.render_as_json(
                        {"display_name": name, "identifier": login}
                    )
        except Exception:
            pass
        return self.render_as_json({"display_name": "", "identifier": ""})


class OAuthSessionBindHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/oauth/<provider>/session/bind

    Called by the browser after device authorization is complete, when the
    user has a YadaCoin wallet loaded.  Records the current KEL public key in
    the session document so that subsequent write actions can require a valid
    one-time-use KEL signature (enforced in AgentChatHandler).

    Body: {
      "nonce": "<session nonce>",
      "kel_pubkey_hex": "<compressed secp256k1 public key, 66 hex chars>",
      "kel_sig_hex":    "<compact R‖S signature, 128 hex chars>",
      "kel_message_hex": "<hex-encoded bind message>",
      "kel_next_digest": "<sha256(K_next.pubkey bytes), hex>",
      "kel_twice_next_digest": "<sha256(K_next_next.pubkey bytes), hex>"
    }

    The bind message expected format: hex(UTF-8(nonce + ":bind"))
    Signature must be valid for kel_pubkey_hex over sha256(message_bytes).
    """

    async def post(self, provider: str):
        provider = provider.lower().strip()

        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid JSON body"})

        nonce = (body.get("nonce") or "").strip()
        kel_pubkey_hex = (body.get("kel_pubkey_hex") or "").strip()
        kel_sig_hex = (body.get("kel_sig_hex") or "").strip()
        kel_message_hex = (body.get("kel_message_hex") or "").strip()
        kel_next_digest = (body.get("kel_next_digest") or "").strip()
        kel_twice_next_digest = (body.get("kel_twice_next_digest") or "").strip()

        if not all(
            [
                nonce,
                kel_pubkey_hex,
                kel_sig_hex,
                kel_message_hex,
                kel_next_digest,
                kel_twice_next_digest,
            ]
        ):
            self.set_status(400)
            return self.render_as_json({"error": "missing required fields"})

        # Verify basic format constraints
        try:
            if len(bytes.fromhex(kel_pubkey_hex)) != 33:
                raise ValueError("pubkey must be 33 bytes compressed")
            if len(bytes.fromhex(kel_sig_hex)) != 64:
                raise ValueError("sig must be 64 bytes compact R‖S")
        except (ValueError, TypeError) as exc:
            self.set_status(400)
            return self.render_as_json({"error": f"invalid hex fields: {exc}"})

        # Confirm the session exists and is authorized
        try:
            session_doc = await self.config.mongo.async_db.web2_oauth_sessions.find_one(
                {"nonce": nonce, "provider": provider, "status": "authorized"}
            )
        except Exception:
            self.set_status(500)
            return self.render_as_json({"error": "session store error"})

        if not session_doc:
            self.set_status(404)
            return self.render_as_json({"error": "session not found or not authorized"})

        # Verify the bind signature
        try:
            message_bytes = bytes.fromhex(kel_message_hex)
            expected_msg = (nonce + ":bind").encode("utf-8")
            if message_bytes != expected_msg:
                self.set_status(400)
                return self.render_as_json(
                    {"error": "kel_message_hex does not match expected bind message"}
                )
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid kel_message_hex"})

        if not _verify_secp256k1(kel_pubkey_hex, kel_message_hex, kel_sig_hex):
            self.set_status(403)
            return self.render_as_json({"error": "KEL signature verification failed"})

        # Store the KEL state in the session document
        try:
            await self.config.mongo.async_db.web2_oauth_sessions.update_one(
                {"_id": session_doc["_id"]},
                {
                    "$set": {
                        "kel_active_pubkey_hex": kel_pubkey_hex,
                        "kel_next_digest": kel_next_digest,
                        "kel_twice_next_digest": kel_twice_next_digest,
                        "kel_bound_at": _datetime.datetime.utcnow(),
                    }
                },
            )
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json({"error": f"failed to store KEL state: {exc}"})

        return self.render_as_json({"status": "bound"})


class RekeySessionsHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/rekey-sessions

    Two modes, selected by the request body:

    CLIENT WALLET MODE — browser handled all crypto; just persist the result:
      Body:  { "rekeyed": [{ "nonce", "encrypted_token", "iv" }, ...] }
      Response: { "stored": ["<nonce>", ...] }

    SERVER WALLET MODE — server decrypts with stored token_enc_key and
    re-encrypts with the new key, keeping token_enc_key current in MongoDB:
      Body:  { "new_token_enc_key": "<32-byte hex>", "nonces": ["<nonce>", ...] }
      Response: { "rekeyed": [{ "nonce", "encrypted_token", "iv" }, ...] }
    """

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid json body"})

        # ── Client wallet mode ────────────────────────────────────────────────
        rekeyed_in = body.get("rekeyed")
        if isinstance(rekeyed_in, list):
            stored = []
            for item in rekeyed_in:
                if not isinstance(item, dict):
                    continue
                nonce = (item.get("nonce") or "").strip()
                enc = (item.get("encrypted_token") or "").strip()
                iv = (item.get("iv") or "").strip()
                if not nonce or not enc or not iv:
                    continue
                try:
                    await self.config.mongo.async_db.web2_oauth_sessions.update_one(
                        {"nonce": nonce, "status": "authorized"},
                        {
                            "$set": {
                                "encrypted_access_token": enc,
                                "token_enc_iv": iv,
                            }
                        },
                    )
                    stored.append(nonce)
                except Exception:
                    pass
            return self.render_as_json({"stored": stored})

        # ── Server wallet mode ────────────────────────────────────────────────
        new_key_hex = (body.get("new_token_enc_key") or "").strip()
        nonces = body.get("nonces") or []
        if not new_key_hex or not isinstance(nonces, list) or not nonces:
            self.set_status(400)
            return self.render_as_json(
                {"error": "provide either rekeyed[] or new_token_enc_key+nonces"}
            )
        try:
            new_key = bytes.fromhex(new_key_hex)
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid new_token_enc_key hex"})
        if len(new_key) != 32:
            self.set_status(400)
            return self.render_as_json({"error": "new_token_enc_key must be 32 bytes"})

        rekeyed = []
        for nonce in nonces:
            if not isinstance(nonce, str) or not nonce.strip():
                continue
            try:
                doc = await self.config.mongo.async_db.web2_oauth_sessions.find_one(
                    {"nonce": nonce.strip(), "status": "authorized"}
                )
                if not doc:
                    continue
                enc_hex = doc.get("encrypted_access_token") or ""
                iv_hex = doc.get("token_enc_iv") or ""
                cur_key_hex = doc.get("token_enc_key") or ""
                if not enc_hex or not iv_hex or not cur_key_hex:
                    continue
                # Decrypt with the stored current key
                cur_key = bytes.fromhex(cur_key_hex)
                plaintext = _AESGCM(cur_key).decrypt(
                    bytes.fromhex(iv_hex), bytes.fromhex(enc_hex), None
                )
                # Re-encrypt with the new key and a fresh IV
                new_iv = os.urandom(12)
                new_ct = _AESGCM(new_key).encrypt(new_iv, plaintext, None)
                new_enc_hex = new_ct.hex()
                new_iv_hex = new_iv.hex()
                # Persist — also update token_enc_key so future rotations chain correctly
                await self.config.mongo.async_db.web2_oauth_sessions.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "encrypted_access_token": new_enc_hex,
                            "token_enc_iv": new_iv_hex,
                            "token_enc_key": new_key_hex,
                        }
                    },
                )
                rekeyed.append(
                    {
                        "nonce": nonce.strip(),
                        "encrypted_token": new_enc_hex,
                        "iv": new_iv_hex,
                    }
                )
            except Exception:
                continue

        return self.render_as_json({"rekeyed": rekeyed})
