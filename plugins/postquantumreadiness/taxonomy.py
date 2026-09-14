"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

Taxonomy of systems/surfaces that may use post-quantum-unsafe cryptography.
Progress is measured per category and subcategory.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# ── Canonical taxonomy ────────────────────────────────────────────────────────
# Each category groups real-world places classical public-key crypto (RSA/ECC/DH)
# or weak primitives commonly appear. Subcategories are inventory slots we track.

TAXONOMY: List[Dict[str, Any]] = [
    {
        "id": "network_transport",
        "name": "Network & transport",
        "description": "Data in motion — protocols that negotiate keys or authenticate peers on the wire.",
        "quantum_risk": "high",
        "subcategories": [
            {"id": "tls_https", "name": "TLS / HTTPS endpoints"},
            {"id": "tls_mtls", "name": "mTLS / service mesh"},
            {"id": "quic_http3", "name": "QUIC / HTTP/3"},
            {"id": "ssh", "name": "SSH (admin & file transfer)"},
            {"id": "vpn_ipsec", "name": "VPN / IPsec / WireGuard"},
            {"id": "rdp_vnc", "name": "Remote desktop (RDP/VNC)"},
            {"id": "email_transport", "name": "SMTP/IMAP STARTTLS"},
            {"id": "wireless", "name": "Wi‑Fi / WPA enterprise / 802.1X"},
            {"id": "load_balancers", "name": "Load balancers & reverse proxies"},
            {"id": "cdn_edges", "name": "CDN / edge TLS termination"},
        ],
    },
    {
        "id": "pki_certificates",
        "name": "PKI & certificates",
        "description": "Certificate authorities, issued certs, and trust anchors — long-lived RSA/ECDSA exposure.",
        "quantum_risk": "critical",
        "subcategories": [
            {"id": "public_ca", "name": "Public CA / publicly trusted certs"},
            {"id": "private_ca", "name": "Private / internal CA"},
            {"id": "code_signing", "name": "Code signing certificates"},
            {"id": "document_signing", "name": "Document / PDF signing"},
            {"id": "smime", "name": "S/MIME email certificates"},
            {"id": "client_certs", "name": "Client authentication certificates"},
            {"id": "ocsp_crl", "name": "OCSP / CRL infrastructure"},
            {"id": "cert_transparency", "name": "Certificate transparency logs"},
        ],
    },
    {
        "id": "identity_authn",
        "name": "Identity & authentication",
        "description": "How users and services prove identity — often backed by classical signatures or password crypto.",
        "quantum_risk": "high",
        "subcategories": [
            {"id": "password_login", "name": "Password authentication / stores"},
            {"id": "mfa_totp", "name": "MFA (TOTP / HOTP / SMS)"},
            {"id": "webauthn", "name": "WebAuthn / passkeys / FIDO"},
            {"id": "oauth_oidc", "name": "OAuth / OIDC token signing"},
            {"id": "saml", "name": "SAML assertions"},
            {"id": "jwt_api", "name": "JWT / API bearer tokens"},
            {"id": "kerberos", "name": "Kerberos / Active Directory"},
            {"id": "ldap_bind", "name": "LDAP binds"},
            {"id": "session_cookies", "name": "Session cookies / server sessions"},
            {"id": "kel_identity", "name": "KEL / key-event identity roots"},
        ],
    },
    {
        "id": "data_at_rest",
        "name": "Data at rest",
        "description": "Stored data protection — key wrap and access control often use RSA/ECC even when bulk cipher is AES.",
        "quantum_risk": "critical",
        "subcategories": [
            {"id": "disk_encryption", "name": "Full-disk / volume encryption"},
            {"id": "database_tde", "name": "Database TDE / column encryption"},
            {"id": "object_storage", "name": "Object storage (S3, etc.)"},
            {"id": "backups", "name": "Backup encryption"},
            {"id": "file_shares", "name": "File shares / NAS encryption"},
            {"id": "secrets_at_rest", "name": "Secrets vaults at rest"},
            {
                "id": "archives_hnl",
                "name": "Long-term archives (harvest-now/decrypt-later)",
            },
            {"id": "mobile_device_storage", "name": "Mobile device storage encryption"},
        ],
    },
    {
        "id": "keys_hsm_kms",
        "name": "Keys, HSM & KMS",
        "description": "Where keys live and how they are generated, wrapped, and rotated.",
        "quantum_risk": "critical",
        "subcategories": [
            {"id": "hsm", "name": "Hardware security modules"},
            {"id": "cloud_kms", "name": "Cloud KMS / managed keys"},
            {"id": "software_keystore", "name": "Software key stores (JKS, PKCS#12)"},
            {"id": "tpm_secure_enclave", "name": "TPM / secure enclave"},
            {"id": "smart_cards", "name": "Smart cards / PIV / CAC"},
            {"id": "key_wrapping", "name": "Key wrapping / envelope encryption"},
            {"id": "key_rotation", "name": "Key rotation / prerotation (KEL)"},
            {"id": "seed_mnemonics", "name": "Seed phrases / BIP39 roots"},
        ],
    },
    {
        "id": "messaging_collab",
        "name": "Messaging & collaboration",
        "description": "Human communications channels with end-to-end or transport crypto.",
        "quantum_risk": "high",
        "subcategories": [
            {"id": "email_e2e", "name": "End-to-end email (PGP/S/MIME)"},
            {"id": "secure_chat", "name": "Secure chat / messaging apps"},
            {"id": "video_conf", "name": "Video conferencing encryption"},
            {"id": "voip", "name": "VoIP / SIP-TLS"},
            {"id": "collaboration_suites", "name": "Collaboration suites (docs/chat)"},
        ],
    },
    {
        "id": "software_supply_chain",
        "name": "Software supply chain",
        "description": "Integrity of code and artifacts — classical signatures are a quantum target.",
        "quantum_risk": "high",
        "subcategories": [
            {"id": "package_signing", "name": "Package / library signing"},
            {"id": "container_images", "name": "Container image signing"},
            {"id": "firmware_signing", "name": "Firmware / boot signing"},
            {"id": "ci_artifacts", "name": "CI/CD artifact signing"},
            {"id": "sbom_attestation", "name": "SBOM / provenance attestation"},
            {"id": "app_store_signing", "name": "Mobile/desktop app store signing"},
            {"id": "git_commit_signing", "name": "Git commit / tag signing"},
        ],
    },
    {
        "id": "blockchain_assets",
        "name": "Blockchain & digital assets",
        "description": "On-chain and wallet cryptography — overwhelmingly ECC today.",
        "quantum_risk": "critical",
        "subcategories": [
            {"id": "hot_wallets", "name": "Hot wallets / exchange keys"},
            {"id": "cold_wallets", "name": "Cold / custody wallets"},
            {"id": "chain_signatures", "name": "Transaction / block signatures"},
            {"id": "smart_contracts", "name": "Smart contract auth / oracles"},
            {"id": "bridges", "name": "Cross-chain bridges"},
            {"id": "nft_identity", "name": "NFT / DID on-chain identity"},
        ],
    },
    {
        "id": "iot_embedded_ot",
        "name": "IoT, embedded & OT",
        "description": "Constrained devices and operational technology with long upgrade cycles.",
        "quantum_risk": "high",
        "subcategories": [
            {"id": "device_identity", "name": "Device identity certificates"},
            {"id": "secure_boot", "name": "Secure boot"},
            {"id": "firmware_update", "name": "Signed firmware updates"},
            {"id": "ot_protocols", "name": "Industrial / OT protocols"},
            {"id": "vehicle_telematics", "name": "Vehicle / telematics links"},
            {"id": "medical_devices", "name": "Medical devices"},
        ],
    },
    {
        "id": "developer_internal",
        "name": "Developer & internal tooling",
        "description": "Day-to-day engineering crypto that often escapes enterprise inventory.",
        "quantum_risk": "medium",
        "subcategories": [
            {"id": "dev_ssh_keys", "name": "Developer SSH keys"},
            {"id": "ci_secrets", "name": "CI secrets & deploy keys"},
            {"id": "api_client_certs", "name": "API client keys / mTLS clients"},
            {"id": "local_dev_tls", "name": "Local / staging TLS certs"},
            {"id": "password_managers", "name": "Password managers / vaults"},
            {"id": "internal_admin_tools", "name": "Internal admin panels"},
        ],
    },
    {
        "id": "payments_finance",
        "name": "Payments & finance",
        "description": "Payment rails and financial messaging with strict compliance crypto.",
        "quantum_risk": "critical",
        "subcategories": [
            {"id": "card_payments", "name": "Card payments / POS"},
            {"id": "payment_gateways", "name": "Payment gateways"},
            {"id": "swift_messaging", "name": "SWIFT / bank messaging"},
            {"id": "open_banking", "name": "Open banking APIs"},
            {"id": "hsm_payment", "name": "Payment HSMs"},
        ],
    },
    {
        "id": "crypto_agility_layer",
        "name": "Crypto-agility layer (KEL)",
        "description": "Abstraction that lets algorithms change without rewriting apps — progress even on classical ECC/RSA.",
        "quantum_risk": "strategic",
        "subcategories": [
            {"id": "kel_roots", "name": "KEL identity roots"},
            {"id": "kel_branches", "name": "KEL branches / derived keys"},
            {"id": "kel_app_integration", "name": "Application KEL integration"},
            {"id": "algorithm_registry", "name": "Algorithm registry / policy"},
            {"id": "hybrid_rollout", "name": "Hybrid classical+PQC rollout"},
            {"id": "pqc_cutover", "name": "Pure PQC cutover"},
        ],
    },
]


def taxonomy_tree() -> List[Dict[str, Any]]:
    """Public tree for API/UI (no mutable shared state)."""
    out = []
    for cat in TAXONOMY:
        out.append(
            {
                "id": cat["id"],
                "name": cat["name"],
                "description": cat["description"],
                "quantum_risk": cat["quantum_risk"],
                "subcategories": [
                    {"id": s["id"], "name": s["name"]} for s in cat["subcategories"]
                ],
            }
        )
    return out


def category_ids() -> List[str]:
    return [c["id"] for c in TAXONOMY]


def subcategory_map() -> Dict[str, str]:
    """subcategory_id → category_id"""
    m = {}
    for c in TAXONOMY:
        for s in c["subcategories"]:
            m[s["id"]] = c["id"]
    return m


def category_meta(cat_id: str) -> Optional[Dict[str, Any]]:
    for c in TAXONOMY:
        if c["id"] == cat_id:
            return c
    return None


def subcategory_meta(sub_id: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    for c in TAXONOMY:
        for s in c["subcategories"]:
            if s["id"] == sub_id:
                return c, s
    return None


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower().replace("_", "-").replace(" ", "-")


# Heuristic routing from discovered asset fields → (category, subcategory)
_INFER_RULES: List[Tuple[Tuple[str, ...], str, str]] = [
    # (needles in name/protocol/tags/metadata blob, category, subcategory)
    (
        ("kel", "key-event", "key_event", "prerotated", "key-rotation"),
        "crypto_agility_layer",
        "kel_roots",
    ),
    (
        ("mtls", "m-tls", "service-mesh", "istio", "linkerd"),
        "network_transport",
        "tls_mtls",
    ),
    (("quic", "http/3", "http3"), "network_transport", "quic_http3"),
    (("ssh",), "network_transport", "ssh"),
    (("vpn", "ipsec", "wireguard", "openvpn"), "network_transport", "vpn_ipsec"),
    (("rdp", "vnc"), "network_transport", "rdp_vnc"),
    (("smtp", "imap", "starttls"), "network_transport", "email_transport"),
    (("wpa", "802.1x", "radius", "wifi"), "network_transport", "wireless"),
    (("cdn", "cloudflare", "fastly", "akamai"), "network_transport", "cdn_edges"),
    (
        ("load-balancer", "loadbalancer", "haproxy", "nginx"),
        "network_transport",
        "load_balancers",
    ),
    (("tls", "https", "ssl"), "network_transport", "tls_https"),
    (("code-sign", "codesign", "authenticode"), "pki_certificates", "code_signing"),
    (("smime", "s/mime"), "pki_certificates", "smime"),
    (("client-cert", "client_cert"), "pki_certificates", "client_certs"),
    (("ocsp", "crl"), "pki_certificates", "ocsp_crl"),
    (
        ("private-ca", "internal-ca", "intermediate-ca"),
        "pki_certificates",
        "private_ca",
    ),
    (("certificate", "x509", "pki", "ca "), "pki_certificates", "public_ca"),
    (("webauthn", "passkey", "fido"), "identity_authn", "webauthn"),
    (("oauth", "oidc", "openid"), "identity_authn", "oauth_oidc"),
    (("saml",), "identity_authn", "saml"),
    (("jwt", "jws", "jwe"), "identity_authn", "jwt_api"),
    (("kerberos", "active-directory", "activedirectory"), "identity_authn", "kerberos"),
    (("ldap",), "identity_authn", "ldap_bind"),
    (("totp", "hotp", "mfa", "2fa"), "identity_authn", "mfa_totp"),
    (
        ("password", "passwd", "bcrypt", "argon2", "scrypt", "pbkdf"),
        "identity_authn",
        "password_login",
    ),
    (("session", "cookie"), "identity_authn", "session_cookies"),
    (("tde", "transparent-data", "column-encrypt"), "data_at_rest", "database_tde"),
    (("backup",), "data_at_rest", "backups"),
    (
        ("s3", "object-storage", "blob-storage", "gcs", "azure-blob"),
        "data_at_rest",
        "object_storage",
    ),
    (
        ("luks", "bitlocker", "filevault", "full-disk", "disk-encrypt"),
        "data_at_rest",
        "disk_encryption",
    ),
    (("archive", "cold-storage", "legal-hold"), "data_at_rest", "archives_hnl"),
    (("vault", "secrets-manager", "secret-store"), "data_at_rest", "secrets_at_rest"),
    (("hsm", "ncipher", "luna", "cloudhsm"), "keys_hsm_kms", "hsm"),
    (("kms", "key-management"), "keys_hsm_kms", "cloud_kms"),
    (("tpm", "secure-enclave"), "keys_hsm_kms", "tpm_secure_enclave"),
    (("pkcs12", "jks", "keystore", "pfx"), "keys_hsm_kms", "software_keystore"),
    (("smart-card", "piv", "cac"), "keys_hsm_kms", "smart_cards"),
    (("bip39", "mnemonic", "seed-phrase"), "keys_hsm_kms", "seed_mnemonics"),
    (("pgp", "gpg", "openpgp"), "messaging_collab", "email_e2e"),
    (("signal", "whatsapp", "matrix", "e2ee"), "messaging_collab", "secure_chat"),
    (
        ("container", "cosign", "docker-sign"),
        "software_supply_chain",
        "container_images",
    ),
    (("firmware", "uefi", "secure-boot"), "software_supply_chain", "firmware_signing"),
    (("sbom", "in-toto", "slsa"), "software_supply_chain", "sbom_attestation"),
    (
        ("git-sign", "gpg-sign", "commit-sign"),
        "software_supply_chain",
        "git_commit_signing",
    ),
    (
        ("npm", "maven", "pypi", "package-sign"),
        "software_supply_chain",
        "package_signing",
    ),
    (
        ("wallet", "bitcoin", "ethereum", "secp256k1"),
        "blockchain_assets",
        "hot_wallets",
    ),
    (("cold-wallet", "custody"), "blockchain_assets", "cold_wallets"),
    (("bridge", "cross-chain"), "blockchain_assets", "bridges"),
    (("iot", "device-cert"), "iot_embedded_ot", "device_identity"),
    (("ot-", "scada", "modbus", "opc-ua"), "iot_embedded_ot", "ot_protocols"),
    (("payment", "pos", "pci"), "payments_finance", "card_payments"),
    (("swift",), "payments_finance", "swift_messaging"),
]


def infer_category(
    asset: Dict[str, Any],
) -> Tuple[str, str, str]:
    """
    Return (category_id, subcategory_id, source) where source is
    'explicit' | 'inferred' | 'default'.
    """
    explicit_cat = (asset.get("category") or asset.get("category_id") or "").strip()
    explicit_sub = (
        asset.get("subcategory") or asset.get("subcategory_id") or ""
    ).strip()
    smap = subcategory_map()

    if explicit_sub and explicit_sub in smap:
        return smap[explicit_sub], explicit_sub, "explicit"
    if explicit_cat and explicit_cat in category_ids():
        # pick first sub if only category given
        meta = category_meta(explicit_cat)
        sub = explicit_sub or (meta["subcategories"][0]["id"] if meta else "unknown")
        if sub in smap:
            return explicit_cat, sub, "explicit"
        return explicit_cat, meta["subcategories"][0]["id"], "explicit"

    blob_parts = [
        asset.get("name") or "",
        asset.get("description") or "",
        asset.get("protocol") or "",
        asset.get("transport") or "",
        asset.get("algorithm") or "",
        asset.get("owner") or "",
        asset.get("data_classification") or "",
        " ".join(asset.get("tags") or []),
    ]
    meta = asset.get("metadata") or {}
    if isinstance(meta, dict):
        blob_parts.extend(str(v) for v in meta.values() if v is not None)
    blob = _norm(" ".join(blob_parts))

    for needles, cat, sub in _INFER_RULES:
        for n in needles:
            if _norm(n) in blob:
                return cat, sub, "inferred"

    # Protocol defaults
    proto = _norm(asset.get("protocol") or "")
    if proto.startswith("tls") or proto in ("https", "ssl"):
        return "network_transport", "tls_https", "inferred"
    if "ssh" in proto:
        return "network_transport", "ssh", "inferred"

    return "network_transport", "tls_https", "default"


def empty_progress() -> Dict[str, Any]:
    cats = []
    for c in TAXONOMY:
        subs = []
        for s in c["subcategories"]:
            subs.append(
                {
                    "id": s["id"],
                    "name": s["name"],
                    "asset_count": 0,
                    "inventoried": False,
                    "overall": None,
                    "kel_percent": 0.0,
                    "agility_enhanced_percent": 0.0,
                    "quantum_safe_percent": 0.0,
                    "status_band": "not_started",
                }
            )
        cats.append(
            {
                "id": c["id"],
                "name": c["name"],
                "description": c["description"],
                "quantum_risk": c["quantum_risk"],
                "subcategory_count": len(c["subcategories"]),
                "subcategories_inventoried": 0,
                "coverage_percent": 0.0,
                "asset_count": 0,
                "overall": None,
                "kel_percent": 0.0,
                "agility_enhanced_percent": 0.0,
                "quantum_safe_percent": 0.0,
                "status_band": "not_started",
                "subcategories": subs,
            }
        )
    return {
        "categories": cats,
        "totals": {
            "categories": len(TAXONOMY),
            "subcategories": sum(len(c["subcategories"]) for c in TAXONOMY),
            "subcategories_inventoried": 0,
            "coverage_percent": 0.0,
            "asset_count": 0,
        },
    }


def _band_from_scores(overall: Optional[float], inventoried: bool) -> str:
    if not inventoried:
        return "not_started"
    if overall is None:
        return "unknown"
    if overall >= 85:
        return "ready"
    if overall >= 70:
        return "enhanced"
    if overall >= 50:
        return "transitioning"
    if overall >= 30:
        return "at_risk"
    return "critical"


def compute_category_progress(
    scored_assets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    scored_assets: list of {asset, score} or flat scored rows with category fields.
    """
    progress = empty_progress()
    cat_index = {c["id"]: c for c in progress["categories"]}
    sub_index = {}
    for c in progress["categories"]:
        for s in c["subcategories"]:
            sub_index[(c["id"], s["id"])] = s

    # Accumulators
    cat_scores: Dict[str, List[float]] = {c["id"]: [] for c in TAXONOMY}
    sub_scores: Dict[Tuple[str, str], List[float]] = {}
    cat_kel = {c["id"]: {"kel": 0, "enh": 0, "qs": 0, "n": 0} for c in TAXONOMY}
    sub_kel: Dict[Tuple[str, str], Dict[str, int]] = {}

    for item in scored_assets:
        if "asset" in item and "score" in item:
            asset = item["asset"]
            score = item["score"]
        else:
            asset = item
            score = item.get("score") or item

        cat_id = asset.get("category") or score.get("category")
        sub_id = asset.get("subcategory") or score.get("subcategory")
        if not cat_id or not sub_id:
            cat_id, sub_id, _ = infer_category(asset)

        if cat_id not in cat_index:
            cat_id, sub_id, _ = infer_category(asset)

        overall = score.get("overall")
        if overall is None:
            continue
        overall = float(overall)

        cat_scores.setdefault(cat_id, []).append(overall)
        key = (cat_id, sub_id)
        sub_scores.setdefault(key, []).append(overall)

        kel_status = score.get("kel_status") or asset.get("kel_status") or "none"
        enh = bool(score.get("agility_enhanced"))
        qs = kel_status == "kel_quantum_safe" or score.get("algorithm_class") == "pqc"

        ck = cat_kel.setdefault(cat_id, {"kel": 0, "enh": 0, "qs": 0, "n": 0})
        ck["n"] += 1
        if kel_status and kel_status != "none":
            ck["kel"] += 1
        if enh:
            ck["enh"] += 1
        if qs:
            ck["qs"] += 1

        sk = sub_kel.setdefault(key, {"kel": 0, "enh": 0, "qs": 0, "n": 0})
        sk["n"] += 1
        if kel_status and kel_status != "none":
            sk["kel"] += 1
        if enh:
            sk["enh"] += 1
        if qs:
            sk["qs"] += 1

    total_subs = 0
    inv_subs = 0
    total_assets = 0

    for c in progress["categories"]:
        cid = c["id"]
        scores = cat_scores.get(cid) or []
        ck = cat_kel.get(cid) or {"kel": 0, "enh": 0, "qs": 0, "n": 0}
        c["asset_count"] = ck["n"]
        total_assets += ck["n"]
        if scores:
            c["overall"] = round(sum(scores) / len(scores), 1)
        n = ck["n"] or 1
        c["kel_percent"] = round(100.0 * ck["kel"] / n, 1) if ck["n"] else 0.0
        c["agility_enhanced_percent"] = (
            round(100.0 * ck["enh"] / n, 1) if ck["n"] else 0.0
        )
        c["quantum_safe_percent"] = round(100.0 * ck["qs"] / n, 1) if ck["n"] else 0.0

        inv = 0
        for s in c["subcategories"]:
            total_subs += 1
            key = (cid, s["id"])
            ss = sub_scores.get(key) or []
            sk = sub_kel.get(key) or {"kel": 0, "enh": 0, "qs": 0, "n": 0}
            s["asset_count"] = sk["n"]
            s["inventoried"] = sk["n"] > 0
            if s["inventoried"]:
                inv += 1
                inv_subs += 1
            if ss:
                s["overall"] = round(sum(ss) / len(ss), 1)
            sn = sk["n"] or 1
            s["kel_percent"] = round(100.0 * sk["kel"] / sn, 1) if sk["n"] else 0.0
            s["agility_enhanced_percent"] = (
                round(100.0 * sk["enh"] / sn, 1) if sk["n"] else 0.0
            )
            s["quantum_safe_percent"] = (
                round(100.0 * sk["qs"] / sn, 1) if sk["n"] else 0.0
            )
            s["status_band"] = _band_from_scores(s["overall"], s["inventoried"])

        c["subcategories_inventoried"] = inv
        c["coverage_percent"] = round(100.0 * inv / max(len(c["subcategories"]), 1), 1)
        c["status_band"] = _band_from_scores(c["overall"], c["asset_count"] > 0)

    progress["totals"] = {
        "categories": len(progress["categories"]),
        "subcategories": total_subs,
        "subcategories_inventoried": inv_subs,
        "coverage_percent": round(100.0 * inv_subs / max(total_subs, 1), 1),
        "asset_count": total_assets,
    }
    return progress
