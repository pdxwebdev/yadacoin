"""Username-routed password auth sessions (webview handoff).

RP creates a short-lived session by Yada username. The home node pushes
``password_auth_request`` over WebSocket to the connected password app.
The app Approves, runs register/verify, then posts the bridge result.
The RP polls until approved/denied/expired.
"""

from __future__ import annotations

import hmac
import re
import secrets
import time
from typing import Any, Optional
from urllib.parse import urlparse

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import verify_signature

from yadacoin.core.config import Config
from yadacoin.core.identity import Identity
from yadacoin.core.identityannouncement import IdentityAnnouncement
from yadacoin.core.peer import User

COLLECTION = "password_auth_sessions"
HOME_COLLECTION = "password_auth_homes"
SESSION_TTL_SEC = 300
HOME_TTL_SEC = 86400 * 30
RATE_WINDOW_SEC = 60
RATE_MAX_PER_USER = 12
RATE_MAX_PER_IP = 40

_rate_user: dict[str, list[float]] = {}
_rate_ip: dict[str, list[float]] = {}

_SITE_RE = re.compile(
    r"^(https?://[a-zA-Z0-9._~:/?#\[\]@!$&'()*+,;=%-]+|[a-zA-Z][a-zA-Z0-9+.-]*://[^\s]+)$"
)


def _now() -> float:
    return time.time()


def _db():
    return Config().mongo.async_db


def _pkh_from_pubhex(pub_hex: str) -> str:
    if not pub_hex:
        return ""
    return str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(pub_hex)))


def normalize_site(site: str) -> str:
    s = (site or "").strip()
    if not s:
        return ""
    if s.startswith("http://") or s.startswith("https://"):
        try:
            p = urlparse(s)
            origin = f"{p.scheme}://{p.netloc}".lower()
            return origin.rstrip("/")
        except Exception:
            return s.lower().rstrip("/")
    return s


def validate_site(site: str) -> Optional[str]:
    s = normalize_site(site)
    if not s or not _SITE_RE.match(s):
        return None
    if len(s) > 512:
        return None
    return s


def validate_action(action: str) -> Optional[str]:
    a = (action or "").strip().lower()
    if a in ("signin", "register", "status", "operator"):
        return a
    return None


def normalize_http_base(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if not u:
        return ""
    parsed = urlparse(u if "://" in u else f"http://{u}")
    if parsed.scheme not in ("http", "https"):
        return ""
    if not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _trim_rate(bucket: dict[str, list[float]], key: str, now: float) -> list[float]:
    cut = now - RATE_WINDOW_SEC
    arr = [t for t in bucket.get(key, []) if t >= cut]
    bucket[key] = arr
    return arr


def check_rate_limits(username: str, ip: str) -> Optional[str]:
    now = _now()
    u = _trim_rate(_rate_user, (username or "").lower(), now)
    if len(u) >= RATE_MAX_PER_USER:
        return "too many auth sessions for this username"
    i = _trim_rate(_rate_ip, ip or "unknown", now)
    if len(i) >= RATE_MAX_PER_IP:
        return "too many auth sessions from this client"
    u.append(now)
    i.append(now)
    _rate_user[(username or "").lower()] = u
    _rate_ip[ip or "unknown"] = i
    return None


async def ensure_indexes():
    db = _db()
    try:
        await db[COLLECTION].create_index("session_id", unique=True)
        # Mongo TTL requires a BSON date field
        await db[COLLECTION].create_index("expires_date", expireAfterSeconds=0)
        await db[COLLECTION].create_index(
            [("username", 1), ("status", 1), ("expires_at", 1)]
        )
        await db[COLLECTION].create_index(
            [("inception_pkh", 1), ("status", 1), ("expires_at", 1)]
        )
        await db[HOME_COLLECTION].create_index("username", unique=True)
        await db[HOME_COLLECTION].create_index("inception_pkh")
    except Exception:
        pass


def expires_date_from_ts(ts: float):
    from datetime import datetime, timezone

    return datetime.fromtimestamp(float(ts), tz=timezone.utc)


def new_session_id() -> str:
    return secrets.token_urlsafe(18)


def new_result_token() -> str:
    return secrets.token_urlsafe(32)


def new_nonce() -> str:
    return f"n_{int(_now() * 1000)}_{secrets.token_hex(4)}"


def public_session_view(doc: dict, *, include_secrets: bool = False) -> dict:
    out = {
        "status": True,
        "session_id": doc.get("session_id"),
        "session_status": doc.get("status"),
        "username": doc.get("username"),
        "site": doc.get("site"),
        "action": doc.get("action"),
        "nonce": doc.get("nonce"),
        "expectedHash": doc.get("expected_hash") or None,
        "expires_at": doc.get("expires_at"),
        "created_at": doc.get("created_at"),
        "home_node": doc.get("home_node") or None,
        "delivered": bool(doc.get("delivered_at")),
    }
    st = doc.get("status")
    if st in ("approved", "denied"):
        result = doc.get("result") or {}
        out["ok"] = bool(result.get("ok"))
        if result.get("message"):
            out["message"] = result.get("message")
        if result.get("action"):
            out["action"] = result.get("action")
        if "counter" in result:
            out["counter"] = result.get("counter")
        if "registered" in result:
            out["registered"] = result.get("registered")
        # One-time secrets for RP after approve
        if st == "approved" and result.get("ok"):
            if result.get("password") is not None:
                out["password"] = result.get("password")
            if result.get("nextPasswordHash"):
                out["nextPasswordHash"] = result.get("nextPasswordHash")
            if result.get("token"):
                out["token"] = result.get("token")
            if result.get("operator_session"):
                out["operator_session"] = True
    if include_secrets:
        out["result_token"] = doc.get("result_token")
    return out


async def get_session(session_id: str) -> Optional[dict]:
    if not session_id:
        return None
    return await _db()[COLLECTION].find_one({"session_id": session_id}, {"_id": 0})


async def insert_session(doc: dict) -> None:
    await _db()[COLLECTION].insert_one(doc)


async def update_session(session_id: str, fields: dict) -> None:
    await _db()[COLLECTION].update_one({"session_id": session_id}, {"$set": fields})


async def list_pending_for_identity(
    *, inception_pkh: str = "", username_signature: str = "", username: str = ""
) -> list[dict]:
    now = _now()
    q: dict[str, Any] = {
        "status": {"$in": ["pending", "delivered"]},
        "expires_at": {"$gt": now},
    }
    or_parts = []
    if inception_pkh:
        or_parts.append({"inception_pkh": inception_pkh})
    if username_signature:
        or_parts.append({"username_signature": username_signature})
    if username:
        or_parts.append({"username": username})
    if or_parts:
        q["$or"] = or_parts
    else:
        return []
    cur = _db()[COLLECTION].find(q, {"_id": 0}).sort([("created_at", 1)]).limit(20)
    return await cur.to_list(20)


def push_payload_from_session(doc: dict) -> dict:
    return {
        "session_id": doc.get("session_id"),
        "action": doc.get("action"),
        "site": doc.get("site"),
        "nonce": doc.get("nonce"),
        "expectedHash": doc.get("expected_hash") or None,
        "username": doc.get("username"),
        "result_token": doc.get("result_token"),
        "expires_at": doc.get("expires_at"),
        "home_node": doc.get("home_node") or None,
    }


async def find_ws_streams_for_identity(
    *,
    username: str,
    username_signature: str,
    public_key: str,
) -> list[Any]:
    """Return live WebSocket handlers for this identity on this node."""
    config = Config()
    streams = []
    seen = set()

    ws = getattr(config, "websocketServer", None)
    if ws is None:
        return streams

    inbound = getattr(ws, "inbound_streams", None) or {}
    users = inbound.get(User.__name__) or {}

    # Dedicated password-auth registry (join_password_auth)
    pwd_map = getattr(ws, "password_auth_streams", None) or {}
    for key in (
        username_signature,
        username,
        _pkh_from_pubhex(public_key) if public_key else "",
        public_key,
    ):
        if not key:
            continue
        stream = pwd_map.get(key)
        if stream is not None and id(stream) not in seen:
            seen.add(id(stream))
            streams.append(stream)

    # Standard User rid = generate_rid(node_sig, user_sig)
    try:
        if (
            username_signature
            and getattr(config, "peer", None)
            and config.peer.identity
        ):
            user_id = Identity(
                public_key=public_key or "",
                username=username or "",
                username_signature=username_signature,
            )
            rid = user_id.generate_rid(config.peer.identity.username_signature)
            stream = users.get(rid)
            if stream is not None and id(stream) not in seen:
                seen.add(id(stream))
                streams.append(stream)
    except Exception:
        pass

    # Address key (join_group path)
    try:
        pkh = _pkh_from_pubhex(public_key) if public_key else ""
        if pkh:
            stream = users.get(pkh)
            if stream is not None and id(stream) not in seen:
                seen.add(id(stream))
                streams.append(stream)
    except Exception:
        pass

    return streams


async def push_password_auth_request(doc: dict) -> bool:
    streams = await find_ws_streams_for_identity(
        username=doc.get("username") or "",
        username_signature=doc.get("username_signature") or "",
        public_key=doc.get("public_key") or "",
    )
    if not streams:
        return False
    payload = push_payload_from_session(doc)
    delivered = False
    for stream in streams:
        try:
            await stream.write_params("password_auth_request", payload)
            delivered = True
        except Exception:
            continue
    if delivered:
        await update_session(
            doc["session_id"],
            {"status": "delivered", "delivered_at": _now()},
        )
    return delivered


async def resolve_identity(username: str) -> Optional[dict]:
    uname = (username or "").strip()
    if not uname:
        return None
    return await IdentityAnnouncement.get_by_username(uname)


async def get_home(username: str) -> Optional[dict]:
    uname = (username or "").strip()
    if not uname:
        return None
    doc = await _db()[HOME_COLLECTION].find_one({"username": uname}, {"_id": 0})
    if not doc:
        return None
    if float(doc.get("expires_at") or 0) < _now():
        return None
    return doc


async def set_home(doc: dict) -> None:
    await _db()[HOME_COLLECTION].replace_one(
        {"username": doc["username"]}, doc, upsert=True
    )


def this_node_http_base(handler=None) -> str:
    config = Config()
    if handler is not None:
        proto = (handler.request.protocol or "http").lower()
        host = handler.request.host or ""
        if host:
            return f"{proto}://{host}".rstrip("/")
    http_host = getattr(config, "http_host", None) or getattr(
        getattr(config, "peer", None), "http_host", None
    )
    http_port = getattr(config, "serve_port", None) or getattr(
        getattr(config, "peer", None), "http_port", None
    )
    http_proto = getattr(getattr(config, "peer", None), "http_protocol", None) or "http"
    if http_host and http_port:
        return f"{http_proto}://{http_host}:{http_port}".rstrip("/")
    return ""


def peer_http_base(peer) -> str:
    """Build http(s)://host:port for a Peer / ServiceProvider."""
    if peer is None:
        return ""
    proto = (getattr(peer, "http_protocol", None) or "http").lower()
    host = getattr(peer, "http_host", None) or getattr(peer, "host", None) or ""
    port = getattr(peer, "http_port", None)
    if not host:
        return ""
    if port:
        return normalize_http_base(f"{proto}://{host}:{port}")
    return normalize_http_base(f"{proto}://{host}")


def this_node_matches_sp(sp, handler=None) -> bool:
    """True if *sp* is this process (by HTTP base or identity signature)."""
    if sp is None:
        return True
    this = this_node_http_base(handler)
    base = peer_http_base(sp)
    if base and this and is_same_home(base, this):
        return True
    config = Config()
    peer = getattr(config, "peer", None)
    sp_id = getattr(sp, "identity", None)
    my_id = getattr(peer, "identity", None) if peer else None
    if sp_id and my_id:
        if (sp_id.username_signature or "") == (my_id.username_signature or ""):
            return True
        if (sp_id.public_key or "") and sp_id.public_key == (my_id.public_key or ""):
            return True
    # Dev / single-node: no SP list or only this host
    if not base:
        return True
    return False


def _host_looks_like_pool(host: str) -> bool:
    h = (host or "").lower()
    return "pool.yadacoin" in h or h.startswith("pool.") or h.endswith(".pool")


def resolve_password_home_sp(username_signature: str, handler=None) -> dict:
    """Deterministic password-home service provider for an identity.

    Uses the same sha256(username_signature) modular pick as
    ``Peer.calculate_seed_gateway`` / ``Peer.select_service_provider``, but
    **without** epoch rotation so tip locality stays fixed.

    Returns::

        {
          "node_http_base": str,
          "source": "deterministic" | "local",
          "is_local": bool,
          "sp_username_signature": str | None,
          "sp_host": str | None,
        }
    """
    from yadacoin.core.peer import Peer

    this = this_node_http_base(handler)
    local = {
        "node_http_base": this,
        "source": "local",
        "is_local": True,
        "sp_username_signature": None,
        "sp_host": None,
        "message": "no service provider directory — using this node",
    }
    sig = (username_signature or "").strip()
    sp = (
        Peer.select_service_provider(sig, rotate=False, skip_ignored=False)
        if sig
        else None
    )
    if sp is None:
        return local
    host = getattr(sp, "host", None) or getattr(sp, "http_host", None) or ""
    if _host_looks_like_pool(str(host)):
        local["message"] = "selected peer is a pool, not an SP — using this node"
        return local
    base = peer_http_base(sp) or this
    if _host_looks_like_pool(base):
        local["message"] = "selected home base is a pool — using this node"
        return local
    is_local = this_node_matches_sp(sp, handler)
    sp_id = getattr(sp, "identity", None)
    return {
        "node_http_base": this if is_local else base,
        "source": "deterministic",
        "is_local": is_local,
        "sp_username_signature": (
            sp_id.username_signature if sp_id is not None else None
        ),
        "sp_host": host or None,
        "message": None,
    }


async def resolve_password_route(username: str, handler=None) -> dict:
    """Identity lookup + deterministic SP for password auth routing."""
    identity = await resolve_identity(username)
    if not identity:
        return {
            "status": False,
            "message": f"username '{username}' not found on this node",
        }
    id_fields = identity.get("identity") or {}
    username_signature = id_fields.get("username_signature") or ""
    public_key = identity.get("public_key") or ""
    home = resolve_password_home_sp(username_signature, handler)
    # Optional published claim overrides only the HTTP base when present and
    # still on the same deterministic SP family — prefer deterministic.
    claimed = await get_home(username)
    claimed_base = normalize_http_base((claimed or {}).get("node_http_base") or "")
    # Prefer deterministic SP; claim is advisory / legacy
    node_http_base = (
        home.get("node_http_base") or claimed_base or this_node_http_base(handler)
    )
    return {
        "status": True,
        "username": username,
        "username_signature": username_signature,
        "public_key": public_key,
        "identity": id_fields,
        "node_http_base": node_http_base,
        "source": home.get("source"),
        "is_local": home.get("is_local"),
        "sp_username_signature": home.get("sp_username_signature"),
        "sp_host": home.get("sp_host"),
        "claimed": bool(claimed),
        "message": home.get("message"),
    }


def verify_home_signature(
    *,
    public_key: str,
    username: str,
    node_http_base: str,
    timestamp: int,
    signature_b64: str,
) -> bool:
    try:
        import base64

        msg = f"password-home|{node_http_base}|{username}|{int(timestamp)}".encode(
            "utf-8"
        )
        sig = base64.b64decode(signature_b64)
        pub = bytes.fromhex(public_key)
        return bool(verify_signature(sig, msg, pub))
    except Exception:
        return False


def verify_result_token(doc: dict, token: str) -> bool:
    expected = (doc.get("result_token") or "").strip()
    got = (token or "").strip()
    if not expected or not got:
        return False
    return hmac.compare_digest(expected, got)


async def mark_result(session_id: str, result: dict, status: str) -> Optional[dict]:
    doc = await get_session(session_id)
    if not doc:
        return None
    if float(doc.get("expires_at") or 0) < _now():
        await update_session(session_id, {"status": "expired"})
        return None
    if doc.get("status") in ("approved", "denied", "expired"):
        return doc
    fields = {
        "status": status,
        "result": result,
        "completed_at": _now(),
    }
    await update_session(session_id, fields)
    doc.update(fields)
    return doc


def is_same_home(home_url: str, this_base: str) -> bool:
    a = normalize_http_base(home_url)
    b = normalize_http_base(this_base)
    if not a or not b:
        return False
    return a.lower() == b.lower()
