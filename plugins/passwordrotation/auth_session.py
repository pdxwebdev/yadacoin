"""Username-routed password auth sessions (webview handoff).

RP creates a short-lived session by Yada username. The home node pushes
``password_auth_request`` over WebSocket to the connected password app.
The app Approves, runs register/verify, then posts the bridge result.
The RP polls until approved/denied/expired.
"""

from __future__ import annotations

import asyncio
import hmac
import json
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
BIND_COLLECTION = "password_signin_binds"
SIGNIN_BIND_COOKIE = "yada_signin_bind"
SESSION_TTL_SEC = 300
HOME_TTL_SEC = 86400 * 30
RATE_WINDOW_SEC = 60
RATE_MAX_PER_USER = 12
RATE_MAX_PER_IP = 40

_rate_user: dict[str, list[float]] = {}
_rate_ip: dict[str, list[float]] = {}
_PROBE_LIVE_TTL = 90.0
_PROBE_DEAD_TTL = 30.0
_HOME_RESOLVE_TTL = 120.0
_HOME_MISS_TTL = 20.0
_PROBE_TIMEOUT = 1.5
_PROBE_BATCH = 6
_TESTED_FAILOVER_CAP = 8
_probe_cache: dict[str, tuple[float, bool]] = {}
_home_resolve_cache: dict[str, tuple[float, dict]] = {}

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


def https_twin(url: str) -> str:
    """https://host for an http default-port base. Empty if already https or a custom port."""
    parsed = urlparse(normalize_http_base(url))
    if parsed.scheme != "http" or not parsed.hostname:
        return ""
    if parsed.port not in (None, 80):
        return ""
    return f"https://{parsed.hostname}"


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


async def issue_signin_bind(handler, username_signature: str) -> str:
    """HttpOnly cookie the home SP never sees. bind_id is public."""
    bind_id = secrets.token_urlsafe(12)
    secret = secrets.token_urlsafe(24)
    now = _now()
    await _db()[BIND_COLLECTION].insert_one(
        {
            "bind_secret": secret,
            "bind_id": bind_id,
            "username_signature": username_signature or "",
            "expires_at": now + SESSION_TTL_SEC,
        }
    )
    handler.set_cookie(
        SIGNIN_BIND_COOKIE,
        secret,
        path="/",
        httponly=True,
        samesite="Lax",
        expires_days=1,
    )
    return bind_id


async def peek_signin_bind(handler) -> Optional[dict]:
    secret = handler.get_cookie(SIGNIN_BIND_COOKIE) or ""
    if not secret:
        return None
    doc = await _db()[BIND_COLLECTION].find_one({"bind_secret": secret}, {"_id": 0})
    if not doc or float(doc.get("expires_at") or 0) < _now():
        return None
    return doc


async def mark_bind_operator_verified(bind_id: str) -> None:
    bid = (bind_id or "").strip()
    if not bid:
        return
    await _db()[BIND_COLLECTION].update_one(
        {"bind_id": bid},
        {"$set": {"operator_verified": True}},
    )


async def consume_signin_bind(handler) -> None:
    secret = handler.get_cookie(SIGNIN_BIND_COOKIE) or ""
    if secret:
        await _db()[BIND_COLLECTION].delete_one({"bind_secret": secret})
    handler.clear_cookie(SIGNIN_BIND_COOKIE, path="/")


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
        "bind_id": doc.get("bind_id") or None,
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
            if result.get("authenticated"):
                out["authenticated"] = True
            if result.get("nextPasswordHash"):
                out["nextPasswordHash"] = result.get("nextPasswordHash")
            if result.get("token"):
                out["token"] = result.get("token")
            if result.get("operator_session"):
                out["operator_session"] = True
    if include_secrets:
        out["result_token"] = doc.get("result_token")
    return out


async def fetch_remote_session_view(home_base: str, session_id: str) -> Optional[dict]:
    """GET a public auth-session view from the home that actually stores it."""
    from tornado.httpclient import AsyncHTTPClient, HTTPRequest

    base = normalize_http_base(home_base or "")
    if not base or not session_id:
        return None
    try:
        from urllib.parse import quote

        client = AsyncHTTPClient()
        req = HTTPRequest(
            url=f"{base}/password-rotation/auth-session/{quote(session_id, safe='')}",
            method="GET",
            headers={"Accept": "application/json"},
            connect_timeout=8,
            request_timeout=20,
        )
        resp = await client.fetch(req, raise_error=False)
        if resp.code != 200:
            return None
        data = json.loads(resp.body or b"{}")
        return data if isinstance(data, dict) and data.get("status") else None
    except Exception:
        return None


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
        "bind_id": doc.get("bind_id") or None,
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


def _probe_cached(base: str):
    hit = _probe_cache.get((base or "").lower())
    if not hit:
        return None
    expires, ok = hit
    if expires <= _now():
        _probe_cache.pop((base or "").lower(), None)
        return None
    return ok


def _probe_store(base: str, ok: bool) -> None:
    ttl = _PROBE_LIVE_TTL if ok else _PROBE_DEAD_TTL
    _probe_cache[(base or "").lower()] = (_now() + ttl, ok)


def forget_password_home(username_signature: str = "", base: str = "") -> None:
    """Drop a cached home pick so the next sign-in re-probes."""
    sig = (username_signature or "").strip()
    if not sig:
        _home_resolve_cache.clear()
    else:
        for key in list(_home_resolve_cache):
            if key[0] == sig:
                _home_resolve_cache.pop(key, None)
    dead = normalize_http_base(base or "")
    if dead:
        _probe_store(dead, False)


def cached_password_home_base(username_signature: str, handler=None) -> str:
    """Last live home for this identity, if the cache is still fresh. No probe."""
    sig = (username_signature or "").strip()
    if not sig:
        return ""
    this = this_node_http_base(handler)
    hit = _home_resolve_cache.get((sig, (this or "").lower()))
    if not hit or hit[0] <= _now():
        return ""
    home = hit[1] or {}
    if home.get("is_local"):
        return ""
    return str(home.get("node_http_base") or "")


async def _http_probe(base: str, path: str, timeout: float) -> str:
    """ok = answers, down = connect failure, miss = HTTP error."""
    from tornado.httpclient import AsyncHTTPClient, HTTPRequest

    try:
        resp = await AsyncHTTPClient().fetch(
            HTTPRequest(
                url=base + path,
                method="GET",
                connect_timeout=timeout,
                request_timeout=timeout,
                validate_cert=False,
            ),
            raise_error=False,
        )
        code = int(resp.code)
    except Exception:
        return "down"
    if 200 <= code < 500:
        return "ok"
    return "miss"


async def probe_node_http_alive(base: str, timeout: float = _PROBE_TIMEOUT) -> bool:
    """True if base answers a cheap HTTP GET. Dead hosts fail in one timeout."""
    b = normalize_http_base(base or "")
    if not b:
        return False
    cached = _probe_cached(b)
    if cached is not None:
        return cached
    status = await _http_probe(b, "/get-status", timeout)
    if status == "miss":
        status = await _http_probe(b, "/password-rotation/theme.json", timeout)
    ok = status == "ok"
    _probe_store(b, ok)
    return ok


async def _already_live() -> bool:
    return True


def _abandon(tasks) -> None:
    async def _run():
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    try:
        asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        pass


async def _first_live(ordered: list) -> int:
    """Index of the highest-priority live target, probing a batch at a time.

    Within a batch, return as soon as every higher-priority probe has failed
    and one has succeeded. Later batches are not started.
    """
    for start in range(0, len(ordered), _PROBE_BATCH):
        batch = ordered[start : start + _PROBE_BATCH]
        tasks = [
            asyncio.create_task(
                probe_node_http_alive(item["target"])
                if not item.get("is_local")
                else _already_live()
            )
            for item in batch
        ]
        results = [None] * len(tasks)
        pending = set(tasks)
        found = None
        try:
            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    results[tasks.index(task)] = bool(task.result())
                for i, ok in enumerate(results):
                    if ok is None:
                        break
                    if ok:
                        found = start + i
                        break
                if found is not None or all(ok is not None for ok in results):
                    break
        finally:
            if found is not None:
                _abandon(tasks)
            else:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        if found is not None:
            return found
    return -1


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


def _home_cache_key(username_signature: str, handler) -> tuple:
    this = this_node_http_base(handler) or ""
    return ((username_signature or "").strip(), this.lower())


def _home_from_cache(username_signature: str, handler):
    hit = _home_resolve_cache.get(_home_cache_key(username_signature, handler))
    if not hit or hit[0] <= _now():
        return None
    return _copy_home(hit[1])


def _copy_home(home: dict) -> dict:
    stored = dict(home)
    stored["tried"] = list(home.get("tried") or [])
    return stored


def _store_home(username_signature: str, handler, home: dict, ttl: float) -> dict:
    stored = _copy_home(home)
    _home_resolve_cache[_home_cache_key(username_signature, handler)] = (
        _now() + ttl,
        stored,
    )
    return _copy_home(stored)


def _https_first(items: list, this: str) -> list:
    """Probe HTTPS homes before HTTP. An http:80 host is also tried as https://host."""
    https = []
    http = []
    seen = set()

    def add(item, bucket):
        key = (item.get("target") or "").lower()
        if not key or key in seen:
            return
        seen.add(key)
        bucket.append(item)

    for item in items:
        twin = https_twin(item.get("target") or "")
        if twin:
            copy = dict(item)
            copy["target"] = twin
            copy["is_local"] = bool(this) and is_same_home(twin, this)
            copy["source_tag"] = f"{item.get('source_tag') or 'home'}_https"
            add(copy, https)
        target = item.get("target") or ""
        add(item, https if target.lower().startswith("https://") else http)
    return https + http


async def resolve_password_home_sp_live(username_signature: str, handler=None) -> dict:
    """Deterministic SP ring + tested_nodes with parallel HTTP liveness failover.

    Probes a small batch at a time and returns the highest-priority live host
    without waiting on lower-priority nodes. Cached for a couple of minutes.
    Falls back to this node when every remote candidate is dead.
    """
    cached = _home_from_cache(username_signature, handler)
    if cached:
        return cached

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
    ordered = []
    seen = set()

    def _push(target: str, *, host=None, sp=None, source_tag: str) -> None:
        t = normalize_http_base(target or "")
        if not t or t.lower() in seen:
            return
        seen.add(t.lower())
        ordered.append(
            {
                "target": t,
                "host": host,
                "sp": sp,
                "source_tag": source_tag,
                "is_local": bool(this) and is_same_home(t, this),
            }
        )

    for sp in _sp_candidate_list(username_signature):
        host = getattr(sp, "host", None) or getattr(sp, "http_host", None) or ""
        base = peer_http_base(sp)
        if not base:
            continue
        is_local = this_node_matches_sp(sp, handler)
        _push(
            this if is_local else base,
            host=host,
            sp=sp,
            source_tag="deterministic",
        )

    tested = 0
    for base in await _tested_node_http_bases():
        before = len(ordered)
        _push(base, host=base, source_tag="tested_nodes")
        if len(ordered) > before:
            tested += 1
            if tested >= _TESTED_FAILOVER_CAP:
                break

    if not ordered:
        return _store_home(username_signature, handler, local, _HOME_MISS_TTL)

    ordered = _https_first(ordered, this)
    idx = await _first_live(ordered)
    if idx < 0:
        tried = [item["target"] for item in ordered if not item["is_local"]]
        local["tried"] = tried
        local[
            "message"
        ] = f"all {len(tried)} candidate SP(s) unreachable — using this node as home"
        return _store_home(username_signature, handler, local, _HOME_MISS_TTL)

    pick = ordered[idx]
    tried = [
        item["target"]
        for item in ordered[:idx]
        if not item["is_local"] and item["target"] != pick["target"]
    ]
    sp = pick["sp"]
    sp_id = getattr(sp, "identity", None) if sp is not None else None
    home = {
        "node_http_base": this if pick["is_local"] else pick["target"],
        "source": pick["source_tag"] if not tried else f"{pick['source_tag']}_failover",
        "is_local": pick["is_local"],
        "sp_username_signature": (
            sp_id.username_signature if sp_id is not None else None
        ),
        "sp_host": pick["host"] or None,
        "message": (
            None
            if not tried
            else f"primary SP unreachable; using failover after {len(tried)} dead"
        ),
        "tried": tried,
    }
    return _store_home(username_signature, handler, home, _HOME_RESOLVE_TTL)


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


async def password_home_bases(
    username_signature: str, handler=None, tested_limit: int = _TESTED_FAILOVER_CAP
) -> list:
    """HTTP bases that may hold a password-home record for this identity.

    The live pick can move when an SP drops. Checkout tokens already issued
    stay on the SP that was live at the time, so callers retry the ring.
    Tested-node failover is capped; a full topology walk is not required.
    """
    this = this_node_http_base(handler)
    seen = set()
    out = []

    def add(base: str) -> bool:
        normalized = normalize_http_base(base or "")
        if not normalized:
            return False
        if this and is_same_home(normalized, this):
            return False
        key = normalized.lower()
        if key in seen:
            return False
        seen.add(key)
        out.append(normalized)
        return True

    cached = cached_password_home_base(username_signature, handler)
    if cached:
        add(cached)
    for sp in _sp_candidate_list(username_signature or ""):
        add(peer_http_base(sp))
    tested = 0
    for base in await _tested_node_http_bases():
        if add(base):
            tested += 1
            if tested_limit and tested >= tested_limit:
                break
    return out
