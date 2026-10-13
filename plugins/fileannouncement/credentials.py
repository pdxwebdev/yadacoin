"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import base64
import json
import re
import time
from datetime import datetime, timezone

from yadacoin.core.credentialannouncement import DID_PREFIX, parse_did
from yadacoin.core.locationrecovery import verify_proof

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class PresentationError(Exception):
    pass


def credential_requirement(live) -> tuple:
    """Return (claim, issuer) from a live announcement or its file relationship."""
    if not isinstance(live, dict):
        return "", ""
    file_rel = live.get("file") if isinstance(live.get("file"), dict) else {}
    claim = str(
        file_rel.get("required_claim") or live.get("required_claim") or ""
    ).strip()
    issuer = str(
        file_rel.get("required_issuer") or live.get("required_issuer") or ""
    ).strip()
    return claim, issuer


def requirement_applies(live, file_id: str = "") -> bool:
    """True when this object, not its public thumbnail, requires a credential."""
    claim, issuer = credential_requirement(live)
    if not claim and not issuer:
        return False
    file_id = (file_id or "").strip()
    if not file_id:
        return True
    file_rel = live.get("file") if isinstance(live.get("file"), dict) else live
    media_id = ""
    thumb = ""
    if isinstance(file_rel, dict):
        media_id = str(file_rel.get("file_id") or "").strip()
        thumb = str(file_rel.get("thumbnail_file_id") or "").strip()
    media_id = media_id or str((live or {}).get("file_id") or "").strip()
    thumb = thumb or str((live or {}).get("thumbnail_file_id") or "").strip()
    if thumb and file_id == thumb and file_id != media_id:
        return False
    if media_id and file_id != media_id:
        return False
    return True


def issuer_id(value) -> str:
    text = str(value or "").strip()
    if text.lower().startswith(DID_PREFIX):
        text = text[len(DID_PREFIX) :].strip()
    if text.startswith("@"):
        text = text[1:].strip()
    return text


def looks_like_username(value) -> bool:
    text = issuer_id(value)
    if not text or len(text) > 32 or any(ch in text for ch in "+/="):
        return False
    return bool(_USERNAME_RE.match(text))


def same_issuer(wanted, candidate) -> bool:
    want = issuer_id(wanted)
    got = issuer_id(candidate)
    if not want or not got:
        return False
    if want == got:
        return True
    if looks_like_username(want) and looks_like_username(got):
        return want.lower() == got.lower()
    return False


async def canonical_issuer(value) -> str:
    """Store a username signature. @username is resolved; DID prefix is stripped."""
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("@"):
        username = text[1:].strip().lower()
        if not username:
            raise ValueError("issuer username is empty")
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        found = await IdentityAnnouncement.get_by_username(username)
        if not found:
            raise ValueError(f"no identity for issuer @{username}")
        identity = found.get("identity") or {}
        sig = (identity.get("username_signature") or "").strip()
        if not sig:
            raise ValueError(f"issuer @{username} has no username signature")
        return issuer_id(sig)
    return issuer_id(text)


def _types(value) -> list:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    return []


def _expired(vc, now: int) -> bool:
    if "expires" in vc and vc.get("expires") not in (None, ""):
        try:
            if int(vc.get("expires")) <= now:
                return True
        except (TypeError, ValueError):
            return True
    raw = vc.get("expirationDate") or vc.get("validUntil") or ""
    if not isinstance(raw, str) or not raw.strip():
        return False
    text = raw.strip().replace("Z", "+00:00")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return True
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.timestamp() <= now


def claim_matches(vc, required_claim: str) -> bool:
    required_claim = (required_claim or "").strip()
    if not required_claim:
        return True
    if not isinstance(vc, dict):
        return False
    if str(vc.get("claim") or "").strip() == required_claim:
        return True
    subject = vc.get("credentialSubject")
    if isinstance(subject, dict) and subject.get(required_claim):
        return True
    return f"{required_claim}Credential" in _types(vc.get("type"))


def issuer_matches(vc, required_issuer: str) -> bool:
    required_issuer = (required_issuer or "").strip()
    if not required_issuer:
        return True
    if not isinstance(vc, dict):
        return False
    return same_issuer(required_issuer, vc.get("issuer")) or same_issuer(
        required_issuer, vc.get("issuer_username_signature")
    )


def badge_satisfies(badge, required_claim="", required_issuer="", now=None) -> bool:
    """UI gate: the signed-in badges list already contains a usable match."""
    required_claim = (required_claim or "").strip()
    required_issuer = (required_issuer or "").strip()
    if not required_claim and not required_issuer:
        return True
    if not isinstance(badge, dict):
        return False
    now = int(time.time() if now is None else now)
    try:
        expires = int(badge.get("expires") or 0)
    except (TypeError, ValueError):
        expires = 0
    if expires and expires <= now:
        return False
    if badge.get("proof_valid") is False:
        return False
    claim = str(badge.get("claim") or "").strip()
    vc = badge.get("vc") if isinstance(badge.get("vc"), dict) else {}
    if (
        required_claim
        and claim != required_claim
        and not claim_matches(vc, required_claim)
    ):
        return False
    if not required_issuer:
        return True
    return any(
        same_issuer(required_issuer, candidate)
        for candidate in (
            badge.get("issuer_username_signature"),
            badge.get("issuer_username"),
            vc.get("issuer"),
        )
    )


def _subject_id(vc) -> str:
    subject = vc.get("credentialSubject") if isinstance(vc, dict) else None
    if not isinstance(subject, dict):
        return ""
    try:
        return parse_did(str(subject.get("id") or ""))
    except ValueError:
        return issuer_id(subject.get("id"))


def _proof_ok(vc, subject: str) -> bool:
    proof = vc.get("proof") if isinstance(vc, dict) else None
    if not isinstance(proof, dict) or not subject:
        return False
    commitment = proof.get("commitment")
    point = proof.get("R")
    scalar = proof.get("s")
    if not commitment or not point or not scalar:
        return False
    return bool(
        verify_proof(str(commitment), str(point), str(scalar), prev_key_hash=subject)
    )


def verify_presentation(vp, required_claim="", required_issuer="", now=None) -> dict:
    """Verify a W3C Verifiable Presentation against an optional claim and issuer.

    The embedded VC must be a VerifiableCredential whose Schnorr proof binds the
    credential subject, and whose holder matches that subject.
    """
    required_claim = (required_claim or "").strip()
    required_issuer = (required_issuer or "").strip()
    if not required_claim and not required_issuer:
        return {"ok": True, "subject": ""}
    if not isinstance(vp, dict):
        raise PresentationError("verifiable presentation is required")
    if "VerifiablePresentation" not in _types(vp.get("type")):
        raise PresentationError("presentation type is invalid")
    creds = vp.get("verifiableCredential")
    if isinstance(creds, dict):
        creds = [creds]
    if not isinstance(creds, list) or not creds:
        raise PresentationError("presentation has no credentials")
    holder = issuer_id(vp.get("holder"))
    now = int(time.time() if now is None else now)
    for vc in creds:
        if not isinstance(vc, dict):
            continue
        if "VerifiableCredential" not in _types(vc.get("type")):
            continue
        if _expired(vc, now):
            continue
        if not claim_matches(vc, required_claim) or not issuer_matches(
            vc, required_issuer
        ):
            continue
        subject = _subject_id(vc)
        if not holder or not subject or holder != subject:
            continue
        if not _proof_ok(vc, subject):
            continue
        return {"ok": True, "subject": subject}
    raise PresentationError("credential required")


def _decode_presentation(raw: str):
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        data = json.loads(text)
    else:
        pad = "=" * (-len(text) % 4)
        try:
            decoded = base64.urlsafe_b64decode(text + pad)
        except Exception:
            decoded = base64.b64decode(text + pad)
        data = json.loads(decoded.decode("utf-8"))
    if not isinstance(data, dict):
        raise PresentationError("verifiable presentation is invalid")
    return data


def presentation_from_parts(header: str = "", query: str = ""):
    raw = (header or "").strip() or (query or "").strip()
    if not raw:
        return None
    try:
        return _decode_presentation(raw)
    except PresentationError:
        raise
    except Exception:
        raise PresentationError("verifiable presentation is invalid")
