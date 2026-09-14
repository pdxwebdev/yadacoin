"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

Network probes for crypto discovery: TLS/certs, HTTP security headers,
DNS CAA, and KEL endpoint signals.
"""

from __future__ import annotations

import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed448, ed25519, rsa
except Exception:  # pragma: no cover
    x509 = None
    default_backend = None
    rsa = ec = dsa = ed25519 = ed448 = None

DEFAULT_TIMEOUT = 8
KEL_PATHS = (
    "/.well-known/yada-kel",
    "/.well-known/kel",
    "/kel",
    "/key-event-log",
    "/api/kel",
    "/post-quantum-readiness",
    "/key-rotation",
)


def parse_targets(
    raw_targets: List[Any], default_port: int = 443
) -> List[Dict[str, Any]]:
    """Normalize hosts, host:port, and URLs into probe targets."""
    out: List[Dict[str, Any]] = []
    seen = set()
    for item in raw_targets or []:
        if isinstance(item, dict):
            host = (item.get("host") or item.get("hostname") or "").strip().lower()
            port = int(item.get("port") or default_port)
            scheme = (item.get("scheme") or "https").lower()
            url = item.get("url") or f"{scheme}://{host}:{port}"
            name = item.get("name") or host
        else:
            text = str(item or "").strip()
            if not text:
                continue
            if "://" not in text and "/" not in text and ":" in text:
                # host:port
                host, _, p = text.rpartition(":")
                host = host.lower()
                try:
                    port = int(p)
                except ValueError:
                    host, port = text.lower(), default_port
                scheme, url, name = "https", f"https://{host}:{port}", host
            elif "://" in text:
                parsed = urlparse(text)
                host = (parsed.hostname or "").lower()
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                scheme = (parsed.scheme or "https").lower()
                url = text
                name = host or text
            else:
                host = text.lower().rstrip(".")
                port = default_port
                scheme = "https"
                url = f"https://{host}:{port}"
                name = host
        if not host:
            continue
        key = (host, port, scheme)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "host": host,
                "port": port,
                "scheme": scheme,
                "url": url,
                "name": name,
            }
        )
    return out


def _algo_from_public_key(pub) -> str:
    if rsa and isinstance(pub, rsa.RSAPublicKey):
        return f"RSA-{pub.key_size}"
    if ec and isinstance(pub, ec.EllipticCurvePublicKey):
        curve = getattr(pub.curve, "name", None) or type(pub.curve).__name__
        return f"ECDSA-{curve}"
    if ed25519 and isinstance(pub, ed25519.Ed25519PublicKey):
        return "Ed25519"
    if ed448 and isinstance(pub, ed448.Ed448PublicKey):
        return "Ed448"
    if dsa and isinstance(pub, dsa.DSAPublicKey):
        return f"DSA-{pub.key_size}"
    return type(pub).__name__ if pub is not None else "unknown"


def probe_tls(
    host: str, port: int = 443, timeout: float = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "kind": "tls",
        "host": host,
        "port": port,
        "ok": False,
        "error": None,
        "protocol": None,
        "cipher": None,
        "tls_version": None,
        "algorithm": None,
        "subject": None,
        "issuer": None,
        "not_after": None,
        "not_before": None,
        "san": [],
        "expired": False,
        "expiring_soon": False,
        "self_signed": False,
    }
    try:
        ctx = ssl.create_default_context()
        # Still collect certs even if verification fails (discovery > blocking)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                result["tls_version"] = ssock.version()
                result["protocol"] = (
                    (ssock.version() or "").replace(" ", "").replace("_", "")
                )
                # normalize TLS1.3 style
                ver = (ssock.version() or "").upper().replace(" ", "")
                if "TLS" in ver:
                    result["protocol"] = ver.replace("V", "").replace("TLS", "TLS")
                    # TLSv1.3 -> TLS1.3
                    m = re.search(r"TLS.?(\d+(?:\.\d+)?)", ver, re.I)
                    if m:
                        result["protocol"] = f"TLS{m.group(1)}"
                cipher = ssock.cipher()
                if cipher:
                    result["cipher"] = {
                        "name": cipher[0],
                        "protocol": cipher[1],
                        "bits": cipher[2],
                    }
                der = ssock.getpeercert(binary_form=True)
                peer = ssock.getpeercert()
                if peer:
                    subj = dict(x[0] for x in peer.get("subject", ()))
                    iss = dict(x[0] for x in peer.get("issuer", ()))
                    result["subject"] = subj.get("commonName") or subj.get(
                        "organizationName"
                    )
                    result["issuer"] = iss.get("commonName") or iss.get(
                        "organizationName"
                    )
                    result["not_after"] = peer.get("notAfter")
                    result["not_before"] = peer.get("notBefore")
                    result["self_signed"] = (
                        result["subject"] and result["subject"] == result["issuer"]
                    )
                    sans = []
                    for typ, val in peer.get("subjectAltName") or []:
                        if typ.lower() == "dns":
                            sans.append(val)
                    result["san"] = sans
                if der and x509 is not None:
                    cert = x509.load_der_x509_certificate(der, default_backend())
                    result["algorithm"] = _algo_from_public_key(cert.public_key())
                    try:
                        nb = cert.not_valid_before_utc
                        na = cert.not_valid_after_utc
                    except Exception:
                        nb = cert.not_valid_before
                        na = cert.not_valid_after
                    result["not_before_ts"] = int(nb.timestamp())
                    result["not_after_ts"] = int(na.timestamp())
                    now = time.time()
                    result["expired"] = now > result["not_after_ts"]
                    result["expiring_soon"] = (not result["expired"]) and (
                        result["not_after_ts"] - now < 30 * 86400
                    )
                    if not result["subject"]:
                        try:
                            attrs = cert.subject.get_attributes_for_oid(
                                x509.oid.NameOID.COMMON_NAME
                            )
                            if attrs:
                                result["subject"] = attrs[0].value
                        except Exception:
                            pass
                result["ok"] = True
    except Exception as exc:
        result["error"] = str(exc)[:400]
    return result


def probe_http(url: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "kind": "http",
        "url": url,
        "ok": False,
        "error": None,
        "status": None,
        "headers": {},
        "security_headers": {},
        "server": None,
        "hsts": False,
        "title": None,
        "body_snippet": "",
        "links": [],
    }
    try:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": "YadaPostQuantumReadiness/1.0 (+discovery)",
                "Accept": "text/html,application/json,*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result["status"] = getattr(resp, "status", None) or resp.getcode()
            headers = {k.lower(): v for k, v in resp.headers.items()}
            result["headers"] = {
                k: headers[k]
                for k in (
                    "strict-transport-security",
                    "content-security-policy",
                    "x-frame-options",
                    "x-content-type-options",
                    "server",
                    "via",
                    "alt-svc",
                )
                if k in headers
            }
            result["server"] = headers.get("server")
            result["hsts"] = "strict-transport-security" in headers
            result["security_headers"] = {
                "hsts": result["hsts"],
                "csp": "content-security-policy" in headers,
                "xfo": "x-frame-options" in headers,
                "xcto": "x-content-type-options" in headers,
            }
            raw = resp.read(65536)
            ctype = (headers.get("content-type") or "").lower()
            text = raw.decode("utf-8", errors="replace")
            result["body_snippet"] = text[:2000]
            m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
            if m:
                result["title"] = re.sub(r"\s+", " ", m.group(1)).strip()[:200]
            if "json" in ctype:
                try:
                    result["json_keys"] = list(json.loads(text).keys())[:40]
                except Exception:
                    pass
            # light link harvest for further targets
            for href in re.findall(r'href=["\']([^"\']+)["\']', text, re.I)[:30]:
                if href.startswith("http"):
                    result["links"].append(href)
            result["ok"] = True
    except urllib.error.HTTPError as exc:
        result["status"] = exc.code
        result["error"] = f"HTTP {exc.code}"
        result["ok"] = exc.code < 500
    except Exception as exc:
        result["error"] = str(exc)[:400]
    return result


def probe_dns_caa(host: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "kind": "dns_caa",
        "host": host,
        "ok": False,
        "records": [],
        "error": None,
    }
    try:
        # Prefer dnspython if present; otherwise skip gracefully
        import dns.resolver  # type: ignore

        answers = dns.resolver.resolve(host, "CAA", lifetime=timeout)
        for r in answers:
            result["records"].append(str(r))
        result["ok"] = True
    except ImportError:
        result["error"] = "dnspython not installed"
    except Exception as exc:
        result["error"] = str(exc)[:200]
        result["ok"] = True  # absence of CAA is still a finding
    return result


def probe_kel_signals(
    base_url: str, timeout: float = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """Detect KEL abstraction layer signals on a host."""
    parsed = urlparse(base_url if "://" in base_url else f"https://{base_url}")
    origin = f"{parsed.scheme or 'https'}://{parsed.hostname}"
    if parsed.port:
        origin += f":{parsed.port}"

    result: Dict[str, Any] = {
        "kind": "kel",
        "origin": origin,
        "ok": False,
        "has_kel": False,
        "kel_status": "none",
        "signals": [],
        "paths_hit": [],
        "error": None,
    }
    keywords = (
        "key_event_log",
        "prerotated_key_hash",
        "twice_prerotated",
        "kel",
        "key-rotation",
        "yadacoin",
        "crypto-agility",
        "post-quantum-readiness",
    )
    for path in KEL_PATHS:
        url = origin.rstrip("/") + path
        try:
            req = urllib.request.Request(
                url,
                method="GET",
                headers={"User-Agent": "YadaPostQuantumReadiness/1.0", "Accept": "*/*"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(32768).decode("utf-8", errors="replace").lower()
                headers = {k.lower(): v for k, v in resp.headers.items()}
                hit = {
                    "path": path,
                    "status": getattr(resp, "status", None) or resp.getcode(),
                }
                result["paths_hit"].append(hit)
                blob = body + " " + " ".join(f"{k}:{v}" for k, v in headers.items())
                found = [k for k in keywords if k in blob]
                if (
                    found
                    or hit["status"] == 200
                    and path
                    in (
                        "/key-rotation",
                        "/kel",
                        "/.well-known/kel",
                        "/.well-known/yada-kel",
                    )
                ):
                    result["signals"].extend(found or [f"reachable:{path}"])
                    result["has_kel"] = True
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                # protected KEL endpoint still indicates presence
                result["paths_hit"].append({"path": path, "status": exc.code})
                result["signals"].append(f"protected:{path}")
                result["has_kel"] = True
            else:
                result["paths_hit"].append({"path": path, "status": exc.code})
        except Exception:
            continue

    if result["has_kel"]:
        result["kel_status"] = "kel_abstracted"
        result["ok"] = True
    else:
        result["ok"] = True
    result["signals"] = sorted(set(result["signals"]))
    return result


def findings_to_assets(
    target: Dict[str, Any],
    tls: Dict[str, Any],
    http: Dict[str, Any],
    kel: Dict[str, Any],
    dns: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Rule-based mapping of probe results → readiness assets."""
    assets: List[Dict[str, Any]] = []
    host = target.get("host") or ""
    name_base = target.get("name") or host

    has_kel = bool(kel.get("has_kel"))
    kel_status = kel.get("kel_status") or ("kel_abstracted" if has_kel else "none")

    if tls.get("ok"):
        algo = tls.get("algorithm") or "unknown"
        proto = tls.get("protocol") or "TLS1.2"
        assets.append(
            {
                "name": f"{name_base} TLS endpoint",
                "description": f"Discovered TLS service on {host}:{target.get('port')}",
                "algorithm": algo,
                "protocol": proto,
                "environment": "production",
                "exposure": "internet",
                "business_criticality": "high",
                "kel_status": kel_status,
                "has_kel": has_kel,
                "owner": "discovered",
                "key_rotation_days": None,
                "hsm_backed": False,
                "certificate_auto_renew": False,
                "expired": bool(tls.get("expired")),
                "expiring_soon": bool(tls.get("expiring_soon")),
                "in_policy": None,
                "data_classification": "discovered",
                "category": "network_transport",
                "subcategory": "tls_https",
                "tags": ["discovered", "tls", "agent"],
                "metadata": {
                    "source": "pqr_discovery_agent",
                    "host": host,
                    "port": target.get("port"),
                    "cipher": tls.get("cipher"),
                    "subject": tls.get("subject"),
                    "issuer": tls.get("issuer"),
                    "san": tls.get("san"),
                    "kel_signals": kel.get("signals") or [],
                },
            }
        )

    if http.get("ok") and not tls.get("ok"):
        # plain HTTP or TLS failed but HTTP worked
        assets.append(
            {
                "name": f"{name_base} HTTP service",
                "description": f"HTTP probe {http.get('url')}",
                "algorithm": "unknown",
                "protocol": "http" if target.get("scheme") == "http" else "https",
                "environment": "production",
                "exposure": "internet",
                "business_criticality": "medium",
                "kel_status": kel_status,
                "has_kel": has_kel,
                "owner": "discovered",
                "tags": ["discovered", "http", "agent"],
                "metadata": {
                    "source": "pqr_discovery_agent",
                    "status": http.get("status"),
                    "server": http.get("server"),
                    "security_headers": http.get("security_headers"),
                    "title": http.get("title"),
                },
            }
        )
    elif http.get("ok") and not http.get("hsts") and tls.get("ok"):
        # separate finding: missing HSTS as governance signal on same host — fold into metadata
        if assets:
            assets[0].setdefault("metadata", {})["hsts"] = False
            assets[0]["metadata"]["security_headers"] = http.get("security_headers")

    if has_kel and not assets:
        assets.append(
            {
                "name": f"{name_base} KEL layer",
                "description": "KEL abstraction signals detected without TLS inventory",
                "algorithm": "unknown",
                "protocol": "https",
                "environment": "production",
                "exposure": "internet",
                "business_criticality": "high",
                "kel_status": "kel_abstracted",
                "has_kel": True,
                "owner": "discovered",
                "category": "crypto_agility_layer",
                "subcategory": "kel_app_integration",
                "tags": ["discovered", "kel", "agent"],
                "metadata": {
                    "source": "pqr_discovery_agent",
                    "kel_signals": kel.get("signals") or [],
                    "paths_hit": kel.get("paths_hit") or [],
                },
            }
        )

    if dns and dns.get("records") is not None:
        for a in assets:
            a.setdefault("metadata", {})["dns_caa"] = dns.get("records") or []
            if not dns.get("records"):
                a["metadata"]["dns_caa_missing"] = True

    # stable ids from host+kind
    for a in assets:
        slug = re.sub(r"[^a-z0-9]+", "-", (a["name"] or "").lower()).strip("-")[:48]
        a["id"] = f"disc-{host}-{slug}"[:64]
    return assets


def probe_target(
    target: Dict[str, Any], timeout: float = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    host = target["host"]
    port = int(target.get("port") or 443)
    scheme = target.get("scheme") or "https"
    url = target.get("url") or f"{scheme}://{host}:{port}"

    tls = (
        probe_tls(host, port, timeout=timeout)
        if scheme == "https" or port in (443, 8443)
        else {"kind": "tls", "ok": False, "skipped": True}
    )
    http = probe_http(
        url if url.startswith("http") else f"https://{host}", timeout=timeout
    )
    kel = probe_kel_signals(url, timeout=timeout)
    dns = probe_dns_caa(host, timeout=min(timeout, 5))
    assets = findings_to_assets(target, tls, http, kel, dns)
    return {
        "target": target,
        "tls": tls,
        "http": http,
        "kel": kel,
        "dns": dns,
        "assets": assets,
        "probed_at": int(time.time()),
    }
