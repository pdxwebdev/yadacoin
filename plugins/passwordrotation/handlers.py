"""
Password rotation plugin — client-owned KEL password manager support.

The browser extension owns BIP39 seed + second_factor. It builds and signs:
  - main-KEL inception (IdentityAnnouncement) via POST /transaction
  - per-site BranchAnnouncement dual-commits via POST /transaction
  - per-site off-chain ratchet steps with password dual-commit hashes

This plugin only:
  - accepts pre-signed off-chain ratchet entries (never holds user seed)
  - serves tip / chain reads for a branch_peer
  - serves optional theme.json
"""

import base64
import json
import os
import time

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import verify_signature
from tornado.web import StaticFileHandler

from yadacoin.http.base import BaseHandler

PASSWORD_RELATIONSHIP_KEY = "password"
ADMIN_SESSION_MAX_AGE = 120


def request_origin(handler) -> str:
    proto = (handler.request.protocol or "http").lower()
    host = (handler.request.host or "").lower()
    return f"{proto}://{host}"


def is_admin_branch_peer(handler, branch_peer: str) -> bool:
    peer = (branch_peer or "").strip().lower().rstrip("/")
    origin = request_origin(handler).rstrip("/")
    if not peer or not origin:
        return False
    return peer == origin


def _pkh_from_pubhex(pub_hex: str) -> str:
    if not pub_hex:
        return ""
    return str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(pub_hex)))


async def node_inception_pkh(config) -> str:
    """P2PKH of this node's KEL inception (K0). Empty if unknown."""
    mgr = getattr(config, "kel_manager", None)
    k0 = getattr(mgr, "_k0", None) if mgr is not None else None
    if isinstance(k0, dict) and k0.get("private_key"):
        try:
            from coincurve import PrivateKey as CoincurvePrivateKey

            pub = CoincurvePrivateKey(k0["private_key"]).public_key.format(
                compressed=True
            )
            return str(P2PKHBitcoinAddress.from_pubkey(pub))
        except Exception:
            pass
    username = getattr(config, "username", "") or ""
    if username.strip():
        try:
            from yadacoin.core.identityannouncement import IdentityAnnouncement

            identity = await IdentityAnnouncement.get_by_username(username)
            if identity:
                pkh = _pkh_from_pubhex(identity.get("public_key") or "")
                if pkh:
                    return pkh
                txn = identity.get("txn") or {}
                pkh = txn.get("public_key_hash") or ""
                if pkh:
                    return pkh
        except Exception:
            pass
    inception = getattr(config, "inception", None)
    if inception is not None:
        pkh = getattr(inception, "public_key_hash", None) or ""
        if pkh:
            return pkh
        try:
            return _pkh_from_pubhex(getattr(inception, "public_key", "") or "")
        except Exception:
            pass
    return ""


async def vault_matches_node(handler, claimed_inception_pkh: str):
    """Return None if the vault KEL is this node, else (status, message)."""
    node_pkh = await node_inception_pkh(handler.config)
    if not node_pkh:
        return 403, "node KEL identity is not initialized"
    claimed = (claimed_inception_pkh or "").strip()
    if not claimed or claimed != node_pkh:
        return 403, "vault identity does not match this node"
    return None


from plugins.passwordrotation.phc import is_password_hash
from plugins.passwordrotation.phc import verify_password as _verify_password


def _parse_password_rel(relationship):
    if relationship is None or relationship == "":
        return None
    raw = relationship
    if isinstance(raw, dict):
        pw = raw.get(PASSWORD_RELATIONSHIP_KEY)
    elif isinstance(raw, str):
        try:
            obj = json.loads(raw)
        except Exception:
            try:
                obj = json.loads(base64.b64decode(raw).decode("utf-8"))
            except Exception:
                return None
        if not isinstance(obj, dict):
            return None
        pw = obj.get(PASSWORD_RELATIONSHIP_KEY)
    else:
        return None
    if not isinstance(pw, dict):
        return None
    pre = (pw.get("prerotated_password_hash") or "").strip()
    twice = (pw.get("twice_prerotated_password_hash") or "").strip()
    if not pre or not twice or pre == twice:
        return None
    if not is_password_hash(pre) or not is_password_hash(twice):
        return None

    return {
        "prerotated_password_hash": pre,
        "twice_prerotated_password_hash": twice,
    }


def _verify_txn_sig(txn: dict) -> bool:
    """Verify transaction_signature over txn hash (coincurve / noble compatible)."""
    try:
        pub_hex = txn.get("public_key") or ""
        tx_hash = txn.get("hash") or ""
        sig_b64 = txn.get("id") or txn.get("transaction_signature") or ""
        if not pub_hex or not tx_hash or not sig_b64:
            return False
        sig = base64.b64decode(sig_b64)
        pub = bytes.fromhex(pub_hex)
        # coincurve verify_signature expects message bytes; node signs sha256(utf8(hash))
        # Node signs sha256(utf8(tx_hash)); coincurve default hasher is sha256.
        return bool(verify_signature(sig, tx_hash.encode("utf-8"), pub))
    except Exception:
        return False


def _addr_from_pub(pub_hex: str) -> str:
    pub = bytes.fromhex(pub_hex)
    return str(P2PKHBitcoinAddress.from_pubkey(pub))


async def _accept_offchain_step(handler, body, *, require_password=None):
    """Validate and persist one client-signed off-chain ratchet step.

    If *require_password* is a non-empty string, the tip must already carry a
    password dual-commit and hash(require_password) must equal tip.pre, and the
    new txn must advance the password dual-commit (pre == tip.twice).

    When the previous tip already has a password dual-commit and
    *require_password* is None, the caller must still supply body["password"]
    so the ratchet cannot advance without knowledge of the current password
    (except counter-0 root / first bootstrap step with no prior password).
    """
    branch_peer = (body.get("branch_peer") or "").strip()
    txn = body.get("txn")
    try:
        counter = int(body.get("counter"))
    except Exception:
        counter = None

    if not branch_peer or not isinstance(txn, dict) or counter is None or counter < 0:
        return 400, {
            "status": False,
            "message": "branch_peer, counter, and txn are required",
        }

    if is_admin_branch_peer(handler, branch_peer):
        claimed = body.get("inception_public_key_hash") or ""
        mismatch = await vault_matches_node(handler, claimed)
        if mismatch:
            return mismatch[0], {"status": False, "message": mismatch[1]}

    if not _verify_txn_sig(txn):
        return 400, {"status": False, "message": "invalid transaction signature"}

    pub = txn.get("public_key") or ""
    try:
        pkh = txn.get("public_key_hash") or _addr_from_pub(pub)
    except Exception:
        return 400, {"status": False, "message": "invalid public_key"}

    if txn.get("public_key_hash") and txn["public_key_hash"] != pkh:
        return 400, {
            "status": False,
            "message": "public_key_hash does not match public_key",
        }

    pw = _parse_password_rel(txn.get("relationship"))

    prev = await handler.config.mongo.async_db.key_event_log.find_one(
        {"branch_peer": branch_peer},
        sort=[("counter", -1)],
    )

    if prev is None:
        if counter != 0:
            return 400, {
                "status": False,
                "message": "first off-chain entry for a branch must use counter 0",
            }
        if require_password is not None:
            return 400, {
                "status": False,
                "message": "cannot sign in — branch not initialized",
            }
    else:
        if counter != int(prev.get("counter", -1)) + 1:
            return 400, {
                "status": False,
                "message": f"expected counter {int(prev.get('counter', -1)) + 1}",
            }
        if prev.get("prerotated_key_hash") and pkh != prev.get("prerotated_key_hash"):
            return 400, {
                "status": False,
                "message": "public_key_hash must equal previous prerotated_key_hash",
            }

        prev_pw = prev.get("password") or _parse_password_rel(
            (prev.get("txn") or {}).get("relationship")
        )

        # Password dual-commit is only enforced on /verify.
        # /offchain is KEL key-hash ratchet; the relying app verifies passwords.
        if (
            require_password is not None
            and prev_pw
            and prev_pw.get("prerotated_password_hash")
        ):
            supplied = (
                require_password
                if require_password is not None
                else (body.get("password") or "")
            )
            if not supplied:
                return 400, {
                    "status": False,
                    "message": (
                        "password required to advance ratchet — "
                        "use POST /password-rotation/verify (sign-in + rotate)"
                    ),
                }
            try:
                pw_ok = _verify_password(supplied, prev_pw["prerotated_password_hash"])
            except RuntimeError as exc:
                return 500, {"status": False, "message": str(exc)}
            if not pw_ok:
                return 401, {"status": False, "message": "invalid password"}
            if not pw:
                return 400, {
                    "status": False,
                    "message": "rotation txn must carry a new password dual-commit",
                }
            tip_twice = prev_pw.get("twice_prerotated_password_hash") or ""
            if pw["prerotated_password_hash"] != tip_twice:
                return 400, {
                    "status": False,
                    "message": (
                        "password prerotated hash must equal tip "
                        "twice_prerotated_password_hash (rotation continuity)"
                    ),
                }
            if pw["prerotated_password_hash"] == pw["twice_prerotated_password_hash"]:
                return 400, {
                    "status": False,
                    "message": "new password hashes must differ",
                }
        elif pw and prev_pw:
            tip_twice = (prev_pw or {}).get("twice_prerotated_password_hash")
            if tip_twice and pw["prerotated_password_hash"] != tip_twice:
                return 400, {
                    "status": False,
                    "message": "password prerotated hash must equal tip twice hash",
                }

    branch_inception = (
        (prev or {}).get("branch_inception_public_key_hash")
        or body.get("branch_inception_public_key_hash")
        or pkh
    )
    main_inception = (
        body.get("inception_public_key_hash")
        or (prev or {}).get("inception_public_key_hash")
        or ""
    )

    doc = {
        "counter": counter,
        "branch_peer": branch_peer,
        "branch_purpose": "password-site",
        "branch_inception_public_key_hash": branch_inception,
        "inception_public_key_hash": main_inception,
        "id": txn.get("id") or txn.get("transaction_signature"),
        "public_key": pub,
        "public_key_hash": pkh,
        "prerotated_key_hash": txn.get("prerotated_key_hash") or "",
        "twice_prerotated_key_hash": txn.get("twice_prerotated_key_hash") or "",
        "txn": txn,
        "password": pw,
        "timestamp": time.time(),
    }

    await handler.config.mongo.async_db.key_event_log.replace_one(
        {"branch_peer": branch_peer, "counter": counter},
        doc,
        upsert=True,
    )

    return 200, {
        "status": True,
        "authenticated": True if require_password is not None else None,
        "rotated": bool(pw and prev is not None),
        "branch_peer": branch_peer,
        "counter": counter,
        "public_key_hash": pkh,
        "prerotated_key_hash": doc["prerotated_key_hash"],
        "password": pw,
        "message": (
            "signed in and password rotated"
            if require_password is not None
            else "off-chain step accepted"
        ),
    }


class PasswordOffchainSubmitHandler(BaseHandler):
    """POST /password-rotation/offchain

    Store a client-signed off-chain ratchet step for a per-site branch.

    Bootstrap (no prior password tip): counter 0 root / first password commit.
    After a password tip exists: body.password is required and the step must
    rotate the dual-commit (same rules as /verify).
    """

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "invalid json body"}
            )

        code, payload = await _accept_offchain_step(self, body, require_password=None)
        # Drop authenticated:null for cleaner JSON
        if payload.get("authenticated") is None:
            payload.pop("authenticated", None)
        self.set_status(code)
        return self.render_as_json(payload)


class PasswordSigninVerifyHandler(BaseHandler):
    """POST /password-rotation/verify

    Enforced sign-in + rotation (atomic):

      password     — must hash to tip.prerotated_password_hash
      branch_peer  — full origin
      counter      — tip.counter + 1
      txn          — client-signed next ratchet step with new dual-commit
                     (pre == tip.twice, twice == H(new forward password))

    Auth succeeds only if the rotation step is accepted. There is no
    password-check-only path.
    """

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "invalid json body"}
            )

        password = body.get("password") or ""
        if not password:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "password and signed rotation txn are required",
                }
            )
        if not isinstance(body.get("txn"), dict):
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        "signed rotation txn required — sign-in always advances "
                        "the password ratchet"
                    ),
                }
            )

        code, payload = await _accept_offchain_step(
            self, body, require_password=password
        )
        if code == 200:
            payload["authenticated"] = True
            payload["rotated"] = True
            tip_pw = payload.get("password") or {}
            payload["tip"] = {
                "prerotated_password_hash": tip_pw.get("prerotated_password_hash"),
                "twice_prerotated_password_hash": tip_pw.get(
                    "twice_prerotated_password_hash"
                ),
            }
            if is_admin_branch_peer(self, body.get("branch_peer") or ""):
                mismatch = await vault_matches_node(
                    self,
                    body.get("inception_public_key_hash")
                    or payload.get("inception_public_key_hash")
                    or "",
                )
                if mismatch:
                    code, payload = mismatch[0], {
                        "status": False,
                        "authenticated": False,
                        "rotated": False,
                        "message": mismatch[1],
                    }
                else:
                    payload["token"] = await self.issue_operator_session()
                    payload["operator_session"] = True
        else:
            payload["authenticated"] = False
            payload["rotated"] = False
        self.set_status(code)
        return self.render_as_json(payload)


class PasswordOffchainTipHandler(BaseHandler):
    """GET /password-rotation/offchain/tip?branch_peer="""

    async def get(self):
        branch_peer = (self.get_query_argument("branch_peer", "") or "").strip()
        if not branch_peer:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "branch_peer required"}
            )

        tip = await self.config.mongo.async_db.key_event_log.find_one(
            {"branch_peer": branch_peer},
            sort=[("counter", -1)],
        )
        if not tip:
            self.set_status(404)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "no off-chain entries for branch_peer",
                    "branch_peer": branch_peer,
                }
            )

        tip.pop("_id", None)
        return self.render_as_json({"status": True, "tip": tip})


class PasswordOffchainChainHandler(BaseHandler):
    """GET /password-rotation/offchain-chain?branch_peer=&limit="""

    async def get(self):
        branch_peer = (self.get_query_argument("branch_peer", "") or "").strip()
        if not branch_peer:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "branch_peer required"}
            )
        try:
            limit = min(int(self.get_query_argument("limit", "100")), 500)
        except Exception:
            limit = 100

        cursor = (
            self.config.mongo.async_db.key_event_log.find({"branch_peer": branch_peer})
            .sort([("counter", 1)])
            .limit(limit)
        )
        entries = []
        async for doc in cursor:
            doc.pop("_id", None)
            entries.append(doc)

        return self.render_as_json(
            {"status": True, "branch_peer": branch_peer, "entries": entries}
        )


class PasswordOffchainResetHandler(BaseHandler):
    """POST /password-rotation/offchain/reset

    Delete all off-chain key_event_log rows for a branch_peer so the client
    can register a new unique branch from K0.
    """

    async def post(self):
        try:
            body = json.loads(self.request.body or b"{}")
        except Exception:
            body = {}
        branch_peer = (
            body.get("branch_peer") or self.get_argument("branch_peer", "")
        ).strip()
        if not branch_peer:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "branch_peer required"}
            )
        if is_admin_branch_peer(self, branch_peer):
            mismatch = await vault_matches_node(
                self, body.get("inception_public_key_hash") or ""
            )
            if mismatch:
                self.set_status(mismatch[0])
                return self.render_as_json({"status": False, "message": mismatch[1]})
        result = await self.config.mongo.async_db.key_event_log.delete_many(
            {"branch_peer": branch_peer}
        )
        return self.render_as_json(
            {
                "status": True,
                "deleted": int(result.deleted_count or 0),
                "branch_peer": branch_peer,
            }
        )


class PasswordThemeHandler(BaseHandler):
    """GET /password-rotation/theme.json"""

    async def get(self):
        theme = None
        cfg_theme = getattr(self.config, "password_rotation_theme", None)
        if isinstance(cfg_theme, dict):
            theme = cfg_theme
        else:
            path = getattr(self.config, "password_rotation_theme_path", None) or ""
            if path:
                try:
                    if os.path.isfile(path):
                        with open(path, "r", encoding="utf-8") as fh:
                            theme = json.load(fh)
                except Exception as exc:
                    self.config.app_log.warning(
                        "PasswordThemeHandler: failed to load %s: %s", path, exc
                    )

        if not isinstance(theme, dict):
            brand_name = getattr(self.config, "username", None) or "Yada Password"
            theme = {
                "id": "node-default",
                "name": str(brand_name),
                "mode": "system",
                "brand": {"name": str(brand_name)},
            }

        self.set_header("Content-Type", "application/json; charset=UTF-8")
        self.set_header("Cache-Control", "public, max-age=60")
        return self.render_as_json(theme)


class PasswordMobileDemoHandler(BaseHandler):
    """GET /password-rotation/mobile — redirect into static demo app index."""

    async def get(self):
        self.redirect("/password-rotation/mobile/index.html")


class PasswordAppHandler(BaseHandler):
    """GET /password-rotation/app — Yada Password web vault (password-native www)."""

    async def get(self):
        self.redirect("/password-rotation/app/index.html")


class PasswordHarnessHandler(BaseHandler):
    """GET /password-rotation|/password-rotation/harness — browser test page."""

    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")

    async def get(self):
        self.render("password_harness.html")


class PasswordAuthSessionCreateHandler(BaseHandler):
    """POST /password-rotation/auth-session

    WebView / RP handoff: create a short-lived auth session by Yada username.
    Home SP is chosen deterministically from the identity username_signature
    (same modular pick as seed-gateway selection, stable / no epoch rotate).
    """

    async def post(self):
        from tornado.httpclient import AsyncHTTPClient, HTTPRequest

        from plugins.passwordrotation import auth_session as asess

        try:
            body = json.loads(self.request.body or b"{}")
        except Exception:
            body = {}

        username = (body.get("username") or "").strip()
        site = asess.validate_site(body.get("site") or "")
        action = asess.validate_action(body.get("action") or "signin")
        expected_hash = (
            body.get("expectedHash") or body.get("expected_hash") or ""
        ).strip()
        nonce = (body.get("nonce") or "").strip() or asess.new_nonce()
        forward = bool(body.get("_forwarded"))

        if not username:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "username is required"}
            )
        if not site:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "valid site origin is required"}
            )
        if not action:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "action must be signin, register, status, or operator",
                }
            )

        ip = self.request.remote_ip or "unknown"
        limited = asess.check_rate_limits(username, ip)
        if limited:
            self.set_status(429)
            return self.render_as_json({"status": False, "message": limited})

        route = await asess.resolve_password_route(username, self)
        if not route.get("status"):
            self.set_status(404)
            return self.render_as_json(route)

        public_key = route.get("public_key") or ""
        username_signature = route.get("username_signature") or ""
        inception_pkh = ""
        try:
            inception_pkh = asess._pkh_from_pubhex(public_key)
        except Exception:
            inception_pkh = ""

        this_base = asess.this_node_http_base(self)
        # Operator unlock binds to *this* node's treasury — never proxy away.
        if action == "operator":
            site = asess.normalize_site(this_base) or this_base
            mismatch = await vault_matches_node(self, inception_pkh)
            if mismatch:
                self.set_status(mismatch[0])
                return self.render_as_json({"status": False, "message": mismatch[1]})
            home_url = this_base
            is_local = True
        else:
            home_url = asess.normalize_http_base(route.get("node_http_base") or "")
            is_local = bool(route.get("is_local")) or asess.is_same_home(
                home_url, this_base
            )

        # Proxy to deterministic home SP when this node is not that SP.
        # On proxy failure, fall back to creating the session locally so local
        # demos (and misconfigured pool-as-SP entries) still work.
        if not forward and home_url and not is_local:
            try:
                client = AsyncHTTPClient()
                payload = {
                    "username": username,
                    "site": site,
                    "action": action,
                    "expectedHash": expected_hash or None,
                    "nonce": nonce,
                    "_forwarded": True,
                }
                req = HTTPRequest(
                    url=f"{home_url}/password-rotation/auth-session",
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    body=json.dumps(payload),
                    connect_timeout=8,
                    request_timeout=15,
                )
                resp = await client.fetch(req, raise_error=False)
                try:
                    data = json.loads(resp.body or b"{}")
                except Exception:
                    data = {"status": False, "message": "invalid home SP response"}
                if (
                    resp.code == 200
                    and isinstance(data, dict)
                    and data.get("status")
                    and data.get("session_id")
                ):
                    data.setdefault("home_node", home_url)
                    data.setdefault("proxied", True)
                    data.setdefault("source", "deterministic")
                    data.setdefault(
                        "sp_username_signature", route.get("sp_username_signature")
                    )
                    return self.render_as_json(data)
                # else fall through to local
            except Exception:
                pass
            home_url = this_base
            is_local = True

        now = asess._now()
        expires_at = now + asess.SESSION_TTL_SEC
        session_id = asess.new_session_id()
        result_token = asess.new_result_token()
        doc = {
            "session_id": session_id,
            "username": username,
            "username_signature": username_signature,
            "public_key": public_key,
            "inception_pkh": inception_pkh,
            "site": site,
            "action": action,
            "nonce": nonce,
            "expected_hash": expected_hash,
            "result_token": result_token,
            "status": "pending",
            "created_at": now,
            "expires_at": expires_at,
            "expires_date": asess.expires_date_from_ts(expires_at),
            "home_node": home_url or this_base,
            "result": None,
            "delivered_at": None,
        }
        await asess.insert_session(doc)
        delivered = await asess.push_password_auth_request(doc)
        if delivered:
            doc["status"] = "delivered"
            doc["delivered_at"] = asess._now()

        view = asess.public_session_view(doc)
        view["poll_url"] = f"/password-rotation/auth-session/{session_id}"
        view["source"] = route.get("source") or "deterministic"
        view["sp_username_signature"] = route.get("sp_username_signature")
        if delivered:
            view["message"] = "delivered to password app"
        else:
            view["message"] = (
                "password app not connected — open Yada Password so it can "
                "connect to your home service provider"
            )
            view["hint"] = "open_app"
        return self.render_as_json(view)


class PasswordAuthSessionGetHandler(BaseHandler):
    """GET /password-rotation/auth-session/{id} — RP poll."""

    async def get(self, session_id):
        from plugins.passwordrotation import auth_session as asess

        doc = await asess.get_session(session_id)
        if not doc:
            self.set_status(404)
            return self.render_as_json(
                {"status": False, "message": "session not found"}
            )
        if float(doc.get("expires_at") or 0) < asess._now():
            if doc.get("status") not in ("approved", "denied", "expired"):
                await asess.update_session(session_id, {"status": "expired"})
                doc["status"] = "expired"
        view = asess.public_session_view(doc)
        # After RP has read an approved result once, optionally scrub secrets
        if doc.get("status") == "approved" and not doc.get("result_consumed"):
            await asess.update_session(session_id, {"result_consumed": True})
        elif doc.get("status") == "approved" and doc.get("result_consumed"):
            view.pop("password", None)
            view.pop("token", None)
        return self.render_as_json(view)


class PasswordAuthSessionResultHandler(BaseHandler):
    """POST /password-rotation/auth-session/{id}/result — authenticator posts outcome."""

    async def post(self, session_id):
        from plugins.passwordrotation import auth_session as asess

        try:
            body = json.loads(self.request.body or b"{}")
        except Exception:
            body = {}

        doc = await asess.get_session(session_id)
        if not doc:
            self.set_status(404)
            return self.render_as_json(
                {"status": False, "message": "session not found"}
            )
        if float(doc.get("expires_at") or 0) < asess._now():
            await asess.update_session(session_id, {"status": "expired"})
            self.set_status(410)
            return self.render_as_json({"status": False, "message": "session expired"})

        token = (
            body.get("result_token")
            or body.get("resultToken")
            or self.request.headers.get("X-Password-Auth-Token")
            or ""
        )
        if not asess.verify_result_token(doc, token):
            self.set_status(403)
            return self.render_as_json(
                {"status": False, "message": "invalid result token"}
            )

        if doc.get("status") in ("approved", "denied"):
            return self.render_as_json(asess.public_session_view(doc))

        deny = body.get("denied") is True or body.get("deny") is True
        ok = bool(body.get("ok")) and not deny
        status = "approved" if ok else "denied"
        action = (body.get("action") or doc.get("action") or "").strip().lower()

        result = {
            "ok": ok,
            "action": action or doc.get("action"),
            "nonce": body.get("nonce") or doc.get("nonce"),
            "message": body.get("message") or ("denied" if status == "denied" else ""),
            "counter": body.get("counter"),
            "registered": body.get("registered"),
        }
        if ok:
            result["password"] = body.get("password")
            result["nextPasswordHash"] = body.get("nextPasswordHash") or body.get(
                "next_password_hash"
            )

        # Operator unlock: issue node JWT when vault matches this node's KEL.
        if ok and action == "operator":
            mismatch = await vault_matches_node(self, doc.get("inception_pkh") or "")
            if mismatch:
                status = "denied"
                result = {
                    "ok": False,
                    "action": "operator",
                    "nonce": doc.get("nonce"),
                    "message": mismatch[1],
                }
            else:
                password = body.get("password") or ""
                branch_peer = (doc.get("site") or request_origin(self)).strip().lower()
                tip = await self.config.mongo.async_db.key_event_log.find_one(
                    {"branch_peer": branch_peer},
                    sort=[("counter", -1)],
                )
                if tip and password:
                    hashes = []
                    current_pre = (tip.get("password") or {}).get(
                        "prerotated_password_hash"
                    )
                    if current_pre:
                        hashes.append(current_pre)
                    prev = await self.config.mongo.async_db.key_event_log.find_one(
                        {
                            "branch_peer": branch_peer,
                            "counter": int(tip.get("counter") or 0) - 1,
                        }
                    )
                    prev_pre = ((prev or {}).get("password") or {}).get(
                        "prerotated_password_hash"
                    )
                    if prev_pre:
                        hashes.append(prev_pre)
                    matched = False
                    for stored in hashes:
                        try:
                            if _verify_password(password, stored):
                                matched = True
                                break
                        except Exception:
                            continue
                    if not matched:
                        status = "denied"
                        result = {
                            "ok": False,
                            "action": "operator",
                            "nonce": doc.get("nonce"),
                            "message": "invalid password for node branch",
                        }
                    else:
                        op_token = await self.issue_operator_session()
                        result["token"] = op_token
                        result["operator_session"] = True
                        result["message"] = (
                            result.get("message") or "operator session issued"
                        )
                elif not tip:
                    # No password branch yet — still issue if vault matches
                    # (first-time operator after register is handled by client
                    # posting password after register+rotate).
                    op_token = await self.issue_operator_session()
                    result["token"] = op_token
                    result["operator_session"] = True
                    result["message"] = (
                        result.get("message")
                        or "operator session issued (no password branch tip)"
                    )
                else:
                    status = "denied"
                    result = {
                        "ok": False,
                        "action": "operator",
                        "nonce": doc.get("nonce"),
                        "message": "password required to open operator session",
                    }

        updated = await asess.mark_result(session_id, result, status)
        return self.render_as_json(asess.public_session_view(updated or doc))


class PasswordAuthSessionPendingHandler(BaseHandler):
    """GET /password-rotation/auth-session/pending — drain queue for authenticator.

    Query: username, username_signature, public_key (or inception_pkh).
    """

    async def get(self):
        from plugins.passwordrotation import auth_session as asess

        username = (self.get_argument("username", "") or "").strip()
        username_signature = (self.get_argument("username_signature", "") or "").strip()
        public_key = (self.get_argument("public_key", "") or "").strip()
        inception_pkh = (self.get_argument("inception_pkh", "") or "").strip()
        if not inception_pkh and public_key:
            try:
                inception_pkh = asess._pkh_from_pubhex(public_key)
            except Exception:
                inception_pkh = ""

        if not (username or username_signature or inception_pkh):
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "username, username_signature, or inception_pkh required",
                }
            )

        rows = await asess.list_pending_for_identity(
            inception_pkh=inception_pkh,
            username_signature=username_signature,
            username=username,
        )
        pending = []
        for doc in rows:
            pending.append(asess.push_payload_from_session(doc))
            if doc.get("status") == "pending":
                await asess.update_session(
                    doc["session_id"],
                    {"status": "delivered", "delivered_at": asess._now()},
                )
        return self.render_as_json({"status": True, "pending": pending})


class PasswordHomeHandler(BaseHandler):
    """GET/POST /password-rotation/home — resolve deterministic password-home SP.

    GET uses identity username_signature → service provider (stable modular pick).
    POST still accepts a signed claim for diagnostics / overrides.
    """

    async def get(self):
        from plugins.passwordrotation import auth_session as asess

        username = (self.get_argument("username", "") or "").strip()
        if not username:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "username required"}
            )
        route = await asess.resolve_password_route(username, self)
        if not route.get("status"):
            self.set_status(404)
            return self.render_as_json(route)
        return self.render_as_json(
            {
                "status": True,
                "username": username,
                "node_http_base": route.get("node_http_base"),
                "source": route.get("source"),
                "is_local": route.get("is_local"),
                "sp_username_signature": route.get("sp_username_signature"),
                "sp_host": route.get("sp_host"),
                "claimed": route.get("claimed"),
                "inception_pkh": asess._pkh_from_pubhex(route.get("public_key") or ""),
                "username_signature": route.get("username_signature"),
                "message": route.get("message"),
            }
        )

    async def post(self):
        from plugins.passwordrotation import auth_session as asess

        try:
            body = json.loads(self.request.body or b"{}")
        except Exception:
            body = {}

        username = (body.get("username") or "").strip()
        node_http_base = asess.normalize_http_base(body.get("node_http_base") or "")
        public_key = (body.get("public_key") or "").strip()
        try:
            timestamp = int(body.get("timestamp") or 0)
        except Exception:
            timestamp = 0
        signature = (body.get("signature") or "").strip()

        if not username or not node_http_base or not public_key or not signature:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "username, node_http_base, public_key, timestamp, signature required",
                }
            )

        now = int(asess._now())
        if abs(now - timestamp) > 600:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "timestamp out of range"}
            )

        identity = await asess.resolve_identity(username)
        if not identity:
            self.set_status(404)
            return self.render_as_json(
                {"status": False, "message": f"username '{username}' not found"}
            )
        chain_pub = (identity.get("public_key") or "").strip()
        if chain_pub and chain_pub != public_key:
            self.set_status(403)
            return self.render_as_json(
                {"status": False, "message": "public_key does not match identity"}
            )

        if not asess.verify_home_signature(
            public_key=public_key,
            username=username,
            node_http_base=node_http_base,
            timestamp=timestamp,
            signature_b64=signature,
        ):
            self.set_status(403)
            return self.render_as_json(
                {"status": False, "message": "invalid home signature"}
            )

        inception_pkh = asess._pkh_from_pubhex(public_key)
        doc = {
            "username": username,
            "node_http_base": node_http_base,
            "public_key": public_key,
            "inception_pkh": inception_pkh,
            "username_signature": (identity.get("identity") or {}).get(
                "username_signature"
            )
            or "",
            "updated_at": asess._now(),
            "expires_at": asess._now() + asess.HOME_TTL_SEC,
            "signature": signature,
            "timestamp": timestamp,
        }
        await asess.set_home(doc)
        return self.render_as_json(
            {
                "status": True,
                "username": username,
                "node_http_base": node_http_base,
                "inception_pkh": inception_pkh,
                "claimed": True,
            }
        )


class PasswordAdminSessionHandler(BaseHandler):
    """POST /password-rotation/admin-session

    Issues an operator cookie/JWT after the password app/extension has rotated
    this *node origin's* password branch (vault must match the node KEL).

    Same-origin browser pages get the secure cookie. Cross-origin wallets
    (e.g. ionic app on another host) still receive ``token`` for Bearer use;
    Origin may differ from the node host in that case. ``branch_peer`` must
    still equal this node's origin so only the node admin branch unlocks spend.
    """

    async def post(self):
        try:
            body = json.loads(self.request.body or b"{}")
        except Exception:
            body = {}
        origin = request_origin(self)
        branch_peer = (body.get("branch_peer") or origin).strip().lower()
        if not is_admin_branch_peer(self, branch_peer):
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "admin session is only for this node's origin",
                }
            )
        tip = await self.config.mongo.async_db.key_event_log.find_one(
            {"branch_peer": branch_peer},
            sort=[("counter", -1)],
        )
        if not tip:
            self.set_status(401)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "no password branch for this origin — register via the extension",
                }
            )
        mismatch = await vault_matches_node(
            self, tip.get("inception_public_key_hash") or ""
        )
        if mismatch:
            self.set_status(mismatch[0])
            return self.render_as_json({"status": False, "message": mismatch[1]})
        password = body.get("password") or ""
        if not password:
            self.set_status(401)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "sign in with the Yada Password extension first",
                }
            )
        hashes = []
        current_pre = (tip.get("password") or {}).get("prerotated_password_hash")
        if current_pre:
            hashes.append(current_pre)
        prev = await self.config.mongo.async_db.key_event_log.find_one(
            {
                "branch_peer": branch_peer,
                "counter": int(tip.get("counter") or 0) - 1,
            }
        )
        prev_pre = ((prev or {}).get("password") or {}).get("prerotated_password_hash")
        if prev_pre:
            hashes.append(prev_pre)
        matched = False
        for stored in hashes:
            try:
                if _verify_password(password, stored):
                    matched = True
                    break
            except Exception:
                continue
        if not matched:
            self.set_status(401)
            return self.render_as_json({"status": False, "message": "invalid password"})
        token = await self.issue_operator_session()
        return self.render_as_json(
            {"status": True, "token": token, "operator_session": True}
        )


class _PasswordDocHandler(BaseHandler):
    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")


class PasswordProtocolHandler(_PasswordDocHandler):
    """GET /password-rotation-protocol"""

    async def get(self):
        self.render("password_rotation_protocol.html")


class MobilePasswordRotationHandler(_PasswordDocHandler):
    """GET /mobile-password-rotation — local mobile test setup."""

    async def get(self):
        self.render("mobile_password_rotation.html")


def _passwordrotation_mobile_static_path():
    return os.path.join(os.path.dirname(__file__), "static", "mobile")


def _password_native_www_path():
    """Monorepo clients/password-manager/apps/password-native/www."""
    return os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "clients",
            "password-manager",
            "apps",
            "password-native",
            "www",
        )
    )


HANDLERS = PASSWORD_ROTATION_HANDLERS = [
    (r"/password-rotation/offchain/tip", PasswordOffchainTipHandler),
    (r"/password-rotation/offchain/reset", PasswordOffchainResetHandler),
    (r"/password-rotation/offchain", PasswordOffchainSubmitHandler),
    (r"/password-rotation/offchain-chain", PasswordOffchainChainHandler),
    (r"/password-rotation/verify", PasswordSigninVerifyHandler),
    (r"/password-rotation/admin-session", PasswordAdminSessionHandler),
    (r"/password-rotation/auth-session/pending", PasswordAuthSessionPendingHandler),
    (
        r"/password-rotation/auth-session/([^/]+)/result",
        PasswordAuthSessionResultHandler,
    ),
    (r"/password-rotation/auth-session/([^/]+)", PasswordAuthSessionGetHandler),
    (r"/password-rotation/auth-session", PasswordAuthSessionCreateHandler),
    (r"/password-rotation/home", PasswordHomeHandler),
    (r"/password-rotation/theme\.json", PasswordThemeHandler),
    (r"/password-rotation/mobile", PasswordMobileDemoHandler),
    (
        r"/password-rotation/mobile/(.*)",
        StaticFileHandler,
        {"path": _passwordrotation_mobile_static_path()},
    ),
    (r"/password-rotation/app", PasswordAppHandler),
    (
        r"/password-rotation/app/(.*)",
        StaticFileHandler,
        {"path": _password_native_www_path()},
    ),
    (r"/password-rotation-protocol", PasswordProtocolHandler),
    (r"/mobile-password-rotation", MobilePasswordRotationHandler),
    (r"/password-rotation/harness", PasswordHarnessHandler),
    (r"/password-rotation/?$", PasswordHarnessHandler),
]
