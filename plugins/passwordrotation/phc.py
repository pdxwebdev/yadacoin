"""PHC password hashes for password-rotation dual-commit fields."""

import base64
import hashlib
import hmac
import re
from typing import Optional

DEFAULT_PASSWORD_PHC = "$argon2id$v=19$m=19456,t=2,p=1"
HEX64 = __import__("re").compile(r"^[0-9a-f]{64}$", __import__("re").I)
_BCRYPT_MODULAR = re.compile(r"^\$2[aby]\$(\d{2})\$")
_KNOWN = {
    "pbkdf2-sha256",
    "pbkdf2-hmac-sha256",
    "pbkdf2-hmac-sha-256",
    "scrypt",
    "argon2id",
    "bcrypt",
    "2a",
    "2b",
    "2y",
}
MAX_PBKDF2_ITERS = 1_000_000
MAX_SCRYPT_LN = 20
MAX_ARGON2_M = 1_048_576
MAX_ARGON2_T = 32
MAX_BCRYPT_ROUNDS = 15


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii").rstrip("=")


def _b64decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.b64decode(s + pad)


def _normalize_id(ident: str) -> str:
    n = ident.lower()
    if n in ("pbkdf2-hmac-sha256", "pbkdf2-hmac-sha-256"):
        return "pbkdf2-sha256"
    if n in ("2a", "2b", "2y"):
        return "bcrypt"
    return n


def parse_phc(value: str):
    s = (value or "").strip()
    if not s.startswith("$"):
        return None
    m = _BCRYPT_MODULAR.match(s)
    if m:
        return {
            "id": "bcrypt",
            "version": "2b",
            "params": {"t": str(int(m.group(1)))},
            "salt": None,
            "hash": s,
        }
    parts = s.split("$")
    if len(parts) < 2 or parts[0] != "" or not parts[1]:
        return None
    ident = _normalize_id(parts[1])
    if ident not in ("pbkdf2-sha256", "scrypt", "argon2id", "bcrypt"):
        return None
    i = 2
    version = None
    if i < len(parts) and (parts[i] or "").startswith("v="):
        version = parts[i][2:]
        i += 1
    params = {}
    if i < len(parts) and "=" in (parts[i] or ""):
        for kv in parts[i].split(","):
            if "=" not in kv:
                return None
            k, v = kv.split("=", 1)
            if not k:
                return None
            params[k] = v
        i += 1
    salt = parts[i] if i < len(parts) and parts[i] else None
    digest = parts[i + 1] if i + 1 < len(parts) and parts[i + 1] else None
    return {
        "id": ident,
        "version": version,
        "params": params,
        "salt": salt,
        "hash": digest,
    }


def format_phc(parts: dict) -> str:
    digest = parts.get("hash")
    if parts.get("id") == "bcrypt" and digest and _BCRYPT_MODULAR.match(digest):
        return digest
    out = "$" + parts["id"]
    if parts.get("version"):
        out += "$v=" + str(parts["version"])
    params = parts.get("params") or {}
    if params:
        out += "$" + ",".join(f"{k}={params[k]}" for k in params)
    if parts.get("salt") is not None:
        out += "$" + parts["salt"]
    if digest is not None:
        out += "$" + digest
    return out


def is_password_hash(value: str) -> bool:
    v = (value or "").strip()
    if len(v) == 64 and all(c in "0123456789abcdefABCDEF" for c in v):
        return True
    return parse_phc(v) is not None


def _bcrypt_rounds(parsed: dict) -> int:
    params = parsed.get("params") or {}
    t = int(params.get("t") or params.get("r") or params.get("cost") or 12)
    if t < 4 or t > MAX_BCRYPT_ROUNDS:
        raise ValueError("invalid bcrypt cost")
    return t


def hash_password(password: str, phc: Optional[str] = None) -> str:
    parsed = parse_phc(phc or DEFAULT_PASSWORD_PHC)
    if not parsed:
        raise ValueError("invalid PHC string")
    ident = parsed["id"]
    if ident == "bcrypt":
        import bcrypt

        return bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt(_bcrypt_rounds(parsed))
        ).decode("ascii")
    salt = (
        _b64decode(parsed["salt"])
        if parsed.get("salt")
        else hashlib.sha256(b"yada-phc-salt-v1|" + password.encode("utf-8")).digest()[
            :16
        ]
    )
    digest = _kdf_digest(ident, password, parsed, salt)
    return format_phc(
        {
            "id": ident,
            "version": parsed.get("version") or ("19" if ident == "argon2id" else None),
            "params": parsed.get("params") or {},
            "salt": _b64encode(salt),
            "hash": digest,
        }
    )


def _kdf_digest(ident: str, password: str, parsed: dict, salt: bytes) -> str:
    params = parsed.get("params") or {}
    pw = password.encode("utf-8")
    if ident == "pbkdf2-sha256":
        iters = int(params.get("i") or params.get("iterations") or 310000)
        if iters < 1 or iters > MAX_PBKDF2_ITERS:
            raise ValueError("invalid PHC pbkdf2 iteration count")
        return _b64encode(hashlib.pbkdf2_hmac("sha256", pw, salt, iters, dklen=32))
    if ident == "scrypt":
        ln = int(params.get("ln", 14))
        r = int(params.get("r", 8))
        p = int(params.get("p", 1))
        if ln < 1 or ln > MAX_SCRYPT_LN:
            raise ValueError("invalid PHC scrypt ln")
        return _b64encode(hashlib.scrypt(pw, salt=salt, n=2**ln, r=r, p=p, dklen=32))
    if ident == "argon2id":
        m = int(params.get("m", 19456))
        t = int(params.get("t", 2))
        par = int(params.get("p", 1))
        if m < 8 or m > MAX_ARGON2_M or t < 1 or t > MAX_ARGON2_T:
            raise ValueError("invalid PHC argon2 parameters")
        try:
            from argon2.low_level import Type, hash_secret
        except ImportError:
            raise RuntimeError(
                "argon2id hash requires the argon2-cffi package on the node"
            )

        raw = hash_secret(
            pw,
            salt,
            time_cost=t,
            memory_cost=m,
            parallelism=par,
            hash_len=32,
            type=Type.ID,
            version=int(parsed.get("version") or 19),
        )
        phc = raw.decode("ascii") if isinstance(raw, (bytes, bytearray)) else str(raw)
        parsed_out = parse_phc(phc)
        if not parsed_out or not parsed_out.get("hash"):
            raise ValueError("argon2 produced unreadable PHC")
        return parsed_out["hash"]
    raise ValueError(f"unsupported PHC id {ident}")


def verify_password(password: str, stored: str) -> bool:
    s = (stored or "").strip()
    if len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s):
        digest = hashlib.sha256(
            b"yada-password-v1|" + password.encode("utf-8")
        ).hexdigest()
        return hmac.compare_digest(digest, s.lower())
    parsed = parse_phc(s)
    if not parsed:
        return False
    ident = parsed["id"]
    if ident == "bcrypt":
        import bcrypt

        crypt = parsed.get("hash") or stored
        try:
            return bcrypt.checkpw(password.encode("utf-8"), crypt.encode("ascii"))
        except Exception:
            return False
    if ident == "argon2id":
        try:
            from argon2.exceptions import VerifyMismatchError
            from argon2.low_level import Type, verify_secret
        except ImportError:
            raise RuntimeError(
                "argon2id hash requires the argon2-cffi package on the node"
            )
        try:
            return bool(
                verify_secret(stored.encode("ascii"), password.encode("utf-8"), Type.ID)
            )
        except VerifyMismatchError:
            return False
        except Exception:
            try:
                recomputed = hash_password(password, stored)
            except Exception:
                return False
            return hmac.compare_digest(recomputed, stored)
    if not parsed.get("hash"):
        return False
    try:
        recomputed = hash_password(password, stored)
    except Exception:
        return False
    return hmac.compare_digest(recomputed, stored) or hmac.compare_digest(
        recomputed, format_phc(parsed)
    )
