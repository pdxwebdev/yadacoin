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


def _sp_candidate_list(username_signature: str) -> list:
    """Ordered SP candidates: primary deterministic pick, then wrap the ring.

    Primary index matches ``Peer.select_service_provider(..., rotate=False)``.
    Callers probe in order and skip dead / pool hosts.
    """
    import hashlib

    from yadacoin.core.peer import Peer

    sig = (username_signature or "").strip()
    if not sig:
        return []
    providers = Peer._service_providers_map() or {}
    if not providers:
        return []
    keys = list(providers)
    n = len(keys)
    if n < 1:
        return []
    h = hashlib.sha256(sig.encode()).hexdigest()
    # seed_time fixed at 1 — same as rotate=False password-home pick
    start = (int(h, 16) * 1) % n
    ordered = []
    for i in range(n):
        sp = providers[keys[(start + i) % n]]
        host = getattr(sp, "host", None) or getattr(sp, "http_host", None) or ""
        base = peer_http_base(sp)
        if _host_looks_like_pool(str(host)) or _host_looks_like_pool(base or ""):
            continue
        if not base:
            continue
        ordered.append(sp)
    return ordered


async def probe_node_http_alive(base: str, timeout: float = 3.0) -> bool:
    """True if base answers a cheap HTTP GET (get-status or password home)."""
    from tornado.httpclient import AsyncHTTPClient, HTTPRequest

    b = normalize_http_base(base or "")
    if not b:
        return False
    client = AsyncHTTPClient()
    for path in ("/get-status", "/password-rotation/theme.json", "/"):
        try:
            req = HTTPRequest(
                url=b + path,
                method="GET",
                connect_timeout=timeout,
                request_timeout=timeout,
                validate_cert=False,
            )
            resp = await client.fetch(req, raise_error=False)
            if 200 <= int(resp.code) < 500:
                return True
        except Exception:
            continue
    return False


def resolve_password_home_sp(username_signature: str, handler=None) -> dict:
    """Sync pick (no liveness). Prefer ``resolve_password_home_sp_live``."""
    this = this_node_http_base(handler)
    local = {
        "node_http_base": this,
        "source": "local",
        "is_local": True,
        "sp_username_signature": None,
        "sp_host": None,
        "message": "no service provider directory — using this node",
        "tried": [],
    }
    candidates = _sp_candidate_list(username_signature)
    if not candidates:
        return local
    sp = candidates[0]
    host = getattr(sp, "host", None) or getattr(sp, "http_host", None) or ""
    base = peer_http_base(sp) or this
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
        "tried": [],
    }


async def _tested_node_http_bases() -> list:
    """HTTP bases from latest NodesTester successful_nodes (online snapshot)."""
    try:
        config = Config()
        doc = await config.mongo.async_db.tested_nodes.find_one(
            {"_id": "latest_test"}, {"_id": 0, "successful_nodes": 1}
        )
    except Exception:
        return []
    out = []
    seen = set()
    for n in (doc or {}).get("successful_nodes") or []:
        host = n.get("http_host") or n.get("host") or ""
        if not host:
            continue
        port = n.get("http_port") or n.get("port") or 80
        proto = (n.get("http_protocol") or "").lower()
        if not proto:
            proto = "https" if str(port) in ("443", "8443") else "http"
        if (proto == "https" and str(port) in ("443", None)) or (
            proto == "http" and str(port) in ("80", None)
        ):
            base = f"{proto}://{host}"
        else:
            base = f"{proto}://{host}:{port}"
        base = normalize_http_base(base)
        if not base or _host_looks_like_pool(base) or base.lower() in seen:
            continue
        pt = (n.get("peer_type") or "").lower()
        # Prefer SPs; still keep seeds/gateways as last-resort live entries
        priority = 0 if pt == "service_provider" else 1
        seen.add(base.lower())
        out.append((priority, base))
    out.sort(key=lambda x: x[0])
    return [b for _, b in out]


async def resolve_password_home_sp_live(username_signature: str, handler=None) -> dict:
    """Deterministic SP ring + tested_nodes with HTTP liveness failover.

    Walks config SP directory from the stable modular index, then live nodes
    from tested_nodes. Skips pools and hosts that do not answer. Falls back to
    this node when every remote candidate is dead.
    """
    this = this_node_http_base(handler)
    local = {
        "node_http_base": this,
        "source": "local",
        "is_local": True,
        "sp_username_signature": None,
        "sp_host": None,
        "message": "no live service provider — using this node",
        "tried": [],
    }
    candidates = _sp_candidate_list(username_signature)
    tried = []
    seen_bases = set()

    async def _try_base(target: str, *, host=None, sp=None, source_tag: str):
        nonlocal tried
        t = normalize_http_base(target or "")
        if not t or t.lower() in seen_bases:
            return None
        seen_bases.add(t.lower())
        is_local = bool(this) and is_same_home(t, this)
        if is_local or await probe_node_http_alive(t):
            sp_id = getattr(sp, "identity", None) if sp is not None else None
            return {
                "node_http_base": this if is_local else t,
                "source": source_tag if not tried else f"{source_tag}_failover",
                "is_local": is_local,
                "sp_username_signature": (
                    sp_id.username_signature if sp_id is not None else None
                ),
                "sp_host": host or None,
                "message": (
                    None
                    if not tried
                    else f"primary SP unreachable; using failover after {len(tried)} dead"
                ),
                "tried": list(tried),
            }
        tried.append(t)
        return None

    for sp in candidates:
        host = getattr(sp, "host", None) or getattr(sp, "http_host", None) or ""
        base = peer_http_base(sp)
        if not base:
            continue
        is_local = this_node_matches_sp(sp, handler)
        target = this if is_local else base
        hit = await _try_base(
            target,
            host=host,
            sp=sp,
            source_tag="deterministic",
        )
        if hit:
            return hit

    # Live NodesTester snapshot (often fresher than static config directory)
    for base in await _tested_node_http_bases():
        hit = await _try_base(base, host=base, source_tag="tested_nodes")
        if hit:
            return hit

    local["tried"] = tried
    local[
        "message"
    ] = f"all {len(tried)} candidate SP(s) unreachable — using this node as home"
    return local


async def resolve_password_route(username: str, handler=None) -> dict:
    """Identity lookup + live deterministic (or claimed) home SP."""
    identity = await resolve_identity(username)
    if not identity:
        return {
            "status": False,
            "message": f"username '{username}' not found on this node",
        }
    id_fields = identity.get("identity") or {}
    username_signature = id_fields.get("username_signature") or ""
    public_key = identity.get("public_key") or ""
    home = await resolve_password_home_sp_live(username_signature, handler)
    claimed = await get_home(username)
    claimed_base = normalize_http_base((claimed or {}).get("node_http_base") or "")
    det_base = normalize_http_base(home.get("node_http_base") or "")
    this = this_node_http_base(handler)
    tried = list(home.get("tried") or [])

    # Claimed home if still reachable; else fall through to live deterministic.
    if claimed_base:
        if is_same_home(claimed_base, this) or await probe_node_http_alive(
            claimed_base
        ):
            return {
                "status": True,
                "username": username,
                "username_signature": username_signature,
                "public_key": public_key,
                "identity": id_fields,
                "node_http_base": claimed_base,
                "source": "claimed",
                "is_local": is_same_home(claimed_base, this),
                "sp_username_signature": home.get("sp_username_signature"),
                "sp_host": home.get("sp_host"),
                "claimed": True,
                "deterministic_node_http_base": det_base or None,
                "tried": tried,
                "message": home.get("message"),
            }
        tried.append(claimed_base)

    node_http_base = det_base or this
    return {
        "status": True,
        "username": username,
        "username_signature": username_signature,
        "public_key": public_key,
        "identity": id_fields,
        "node_http_base": node_http_base,
        "source": home.get("source") or "local",
        "is_local": bool(home.get("is_local")),
        "sp_username_signature": home.get("sp_username_signature"),
        "sp_host": home.get("sp_host"),
        "claimed": bool(claimed),
        "deterministic_node_http_base": det_base or None,
        "tried": tried,
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
