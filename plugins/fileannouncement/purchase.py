"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import base64
import hashlib
import hmac
import secrets
import time
from decimal import Decimal, InvalidOperation, localcontext

INVOICES = "ppv_invoices"
INVOICE_TTL = 3600
EXPIRED_ERROR = "Access for this payment has expired. Pay again to keep watching."


class AccessExpired(Exception):
    pass


def _amount(value) -> Decimal:
    try:
        text = str(value if value is not None else 0)
        with localcontext() as ctx:
            ctx.prec = max(28, len(text) + 8)
            return Decimal(text).quantize(Decimal("0.00000000"))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def output_pays(txn: dict, pay_to: str, min_price: str) -> bool:
    if not pay_to or not min_price:
        return False
    needed = _amount(min_price)
    if needed <= 0:
        return False
    for out in txn.get("outputs") or []:
        if not isinstance(out, dict):
            continue
        if str(out.get("to") or "") != pay_to:
            continue
        if _amount(out.get("value")) >= needed:
            return True
    return False


def payer_matches(txn: dict, payer_ids) -> bool:
    wanted = {str(i).strip() for i in (payer_ids or []) if str(i).strip()}
    if not wanted:
        return False
    found = {
        str(txn.get("public_key_hash") or "").strip(),
        str(txn.get("inception_public_key_hash") or "").strip(),
    }
    found.discard("")
    return bool(found & wanted)


def invoice_amount(price: str, jitter: int) -> str:
    base = _amount(price)
    with localcontext() as ctx:
        ctx.prec = 28
        extra = Decimal(int(jitter)) / Decimal(100000000)
        total = base + extra
    return f"{total:.8f}"


def new_invoice_amount(price: str) -> str:
    return invoice_amount(price, secrets.randbelow(999999) + 1)


def output_equals(txn: dict, pay_to: str, amount: str) -> bool:
    if not pay_to or not amount:
        return False
    needed = _amount(amount)
    if needed <= 0:
        return False
    for out in txn.get("outputs") or []:
        if not isinstance(out, dict):
            continue
        if str(out.get("to") or "") != pay_to:
            continue
        if _amount(out.get("value")) == needed:
            return True
    return False


def grant_limit(value) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        seconds = int(text)
    except (TypeError, ValueError):
        return 0
    return seconds if seconds > 0 else 0


def access_expiry(anchor: int, grant_seconds) -> int:
    """0 means the confirmed payment does not expire."""
    limit = grant_limit(grant_seconds)
    if limit <= 0:
        return 0
    return int(anchor) + limit


def access_open(exp, now=None) -> bool:
    now = int(time.time() if now is None else now)
    try:
        exp = int(exp or 0)
    except (TypeError, ValueError):
        return False
    return exp == 0 or exp >= now


def access_token_expired(token: str) -> bool:
    token = (token or "").strip()
    if "." not in token:
        return False
    try:
        exp = int(token.split(".", 1)[0])
    except ValueError:
        return False
    return exp != 0 and exp < int(time.time())


def access_token(config, announcement_id: str, exp: int) -> str:
    payload = f"{announcement_id}|{int(exp)}"
    secret = str(getattr(config, "private_key", "") or "").encode()
    sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return f"{int(exp)}.{sig}"


def access_token_ok(config, announcement_id: str, token: str) -> bool:
    announcement_id = (announcement_id or "").strip()
    token = (token or "").strip()
    if not announcement_id or "." not in token:
        return False
    exp_s, sig = token.split(".", 1)
    try:
        exp = int(exp_s)
    except ValueError:
        return False
    if exp != 0 and exp < int(time.time()):
        return False
    expected = access_token(config, announcement_id, exp)
    return hmac.compare_digest(expected, f"{exp}.{sig}")


async def _payment_txns(config, pay_to: str):
    """Yield mempool txns first, then confirmed ones. A broadcast spend can unlock playback."""
    try:
        cursor = config.mongo.async_db.miner_transactions.find(
            {"outputs.to": pay_to},
            {"_id": 0},
        )
        async for txn in cursor:
            if isinstance(txn, dict):
                yield txn
    except Exception:
        pass
    try:
        cursor = config.mongo.async_db.blocks.find(
            {"transactions.outputs.to": pay_to},
            {"transactions": 1, "index": 1},
        ).sort("index", -1)
        async for block in cursor:
            for txn in block.get("transactions") or []:
                if isinstance(txn, dict):
                    yield txn
    except Exception:
        return


async def find_payment_from_key(config, pay_to: str, min_price: str, public_key: str):
    public_key = (public_key or "").strip()
    if not public_key:
        return None
    pay_to = (pay_to or "").strip()
    async for txn in _payment_txns(config, pay_to):
        if str(txn.get("public_key") or "") != public_key:
            continue
        if output_pays(txn, pay_to, min_price):
            return txn
    return None


async def payment_by_id(config, payment_id: str):
    payment_id = (payment_id or "").strip()
    if not payment_id:
        return None
    try:
        txn = await config.mongo.async_db.miner_transactions.find_one(
            {"id": payment_id}, {"_id": 0}
        )
    except Exception:
        txn = None
    if isinstance(txn, dict):
        return txn
    try:
        block = await config.mongo.async_db.blocks.find_one(
            {"transactions.id": payment_id}, {"transactions": 1}
        )
    except Exception:
        return None
    for txn in (block or {}).get("transactions") or []:
        if isinstance(txn, dict) and str(txn.get("id") or "") == payment_id:
            return txn
    return None


async def find_exact_payment(config, pay_to: str, amount: str):
    pay_to = (pay_to or "").strip()
    amount = (amount or "").strip()
    if not pay_to or not amount:
        return None
    async for txn in _payment_txns(config, pay_to):
        if output_equals(txn, pay_to, amount):
            return txn
    return None


async def create_invoice(config, announcement_id: str, pay_to: str, price: str) -> dict:
    announcement_id = (announcement_id or "").strip()
    pay_to = (pay_to or "").strip()
    price = (price or "").strip()
    if not announcement_id or not pay_to or not price:
        raise ValueError("announcement, address, and price are required")
    now = int(time.time())
    amount = ""
    for _ in range(8):
        candidate = new_invoice_amount(price)
        clash = await config.mongo.async_db[INVOICES].find_one(
            {
                "pay_to": pay_to,
                "amount": candidate,
                "expires_at": {"$gt": now},
                "redeemed_at": 0,
            }
        )
        if not clash:
            amount = candidate
            break
    if not amount:
        raise ValueError("could not allocate an invoice amount")
    token = secrets.token_hex(32)
    doc = {
        "token": token,
        "announcement_id": announcement_id,
        "pay_to": pay_to,
        "amount": amount,
        "price": price,
        "created_at": now,
        "expires_at": now + INVOICE_TTL,
        "redeemed_at": 0,
    }
    await config.mongo.async_db[INVOICES].insert_one(doc)
    return doc


async def invoice_for_token(config, token: str):
    token = (token or "").strip()
    if not token:
        return None
    return await config.mongo.async_db[INVOICES].find_one({"token": token}, {"_id": 0})


def issue_access(
    config, announcement_id: str, payment_id: str, grant_seconds="", anchor=None
) -> dict:
    now = int(time.time())
    anchor = now if anchor is None else int(anchor)
    exp = access_expiry(anchor, grant_seconds)
    return {
        "access": access_token(config, announcement_id, exp),
        "payment_id": payment_id or "",
        "access_exp": exp,
    }


async def _confirmed_payment(config, doc):
    payment_id = str((doc or {}).get("payment_id") or "")
    if payment_id:
        payment = await payment_by_id(config, payment_id)
        if payment:
            return payment
    return await find_exact_payment(
        config, (doc or {}).get("pay_to") or "", (doc or {}).get("amount") or ""
    )


async def _store_access(config, query, issued, redeemed_at):
    await config.mongo.async_db[INVOICES].update_one(
        query,
        {
            "$set": {
                "redeemed_at": redeemed_at,
                "payment_id": issued["payment_id"],
                "access": issued["access"],
                "access_exp": issued["access_exp"],
            }
        },
    )


async def redeem_invoice(config, token: str, announcement_id: str, grant_seconds=""):
    doc = await invoice_for_token(config, token)
    if not doc or doc.get("announcement_id") != announcement_id:
        return None
    now = int(time.time())
    if doc.get("redeemed_at"):
        anchor = int(doc.get("redeemed_at") or now)
        exp = access_expiry(anchor, grant_seconds)
        if not access_open(exp, now):
            raise AccessExpired(EXPIRED_ERROR)
        if (
            doc.get("access")
            and int(doc.get("access_exp") or 0) == exp
            and access_open(doc.get("access_exp"), now)
        ):
            return doc
        payment = await _confirmed_payment(config, doc)
        if not payment:
            return None
        issued = issue_access(
            config,
            announcement_id,
            payment.get("id") or doc.get("payment_id") or "",
            grant_seconds,
            anchor,
        )
        await _store_access(config, {"token": token}, issued, anchor)
        doc["payment_id"] = issued["payment_id"]
        doc["access"] = issued["access"]
        doc["access_exp"] = issued["access_exp"]
        return doc
    if int(doc.get("expires_at") or 0) < now:
        return None
    payment = await find_exact_payment(
        config, doc.get("pay_to") or "", doc.get("amount") or ""
    )
    if not payment:
        return None
    issued = issue_access(
        config, announcement_id, payment.get("id") or "", grant_seconds
    )
    await config.mongo.async_db[INVOICES].update_one(
        {"token": token, "redeemed_at": 0},
        {
            "$set": {
                "redeemed_at": now,
                "payment_id": issued["payment_id"],
                "access": issued["access"],
                "access_exp": issued["access_exp"],
            }
        },
    )
    doc["redeemed_at"] = now
    doc["payment_id"] = issued["payment_id"]
    doc["access"] = issued["access"]
    doc["access_exp"] = issued["access_exp"]
    return doc


def view_grant(config, announcement_id: str, exp: int) -> dict:
    from coincurve import PrivateKey

    message = f"yada-ppv|{announcement_id}|{int(exp)}"
    key = PrivateKey.from_hex(config.private_key)
    signature = base64.b64encode(key.sign(message.encode())).decode()
    return {
        "message": message,
        "signature": signature,
        "public_key": config.public_key,
        "exp": int(exp),
    }


def view_grant_ok(announcement_id: str, grant: dict, payment: dict) -> bool:
    from coincurve.utils import verify_signature

    if not isinstance(grant, dict) or not isinstance(payment, dict):
        return False
    message = str(grant.get("message") or "")
    expected = f"yada-ppv|{announcement_id}|{grant.get('exp')}"
    if message != expected:
        return False
    try:
        exp = int(grant.get("exp") or 0)
    except (TypeError, ValueError):
        return False
    if exp < int(time.time()):
        return False
    pubkey = str(grant.get("public_key") or "")
    if not pubkey or pubkey != str(payment.get("public_key") or ""):
        return False
    try:
        sig = base64.b64decode(grant.get("signature") or "")
        return bool(verify_signature(sig, message.encode(), bytes.fromhex(pubkey)))
    except Exception:
        return False


async def claim_unique_invoice_payment(
    config, announcement_id: str, pay_to: str, price: str, grant_seconds=""
):
    """Unlock the only outstanding invoice-band payment to this post.

    Used when the checkout token was issued on another node, so this node
    cannot see that invoice amount, but the spend is already in the mempool.
    Refuses when more than one such payment exists.
    """
    pay_to = (pay_to or "").strip()
    announcement_id = (announcement_id or "").strip()
    floor = _amount(price)
    with localcontext() as ctx:
        ctx.prec = 28
        ceiling = floor + Decimal("0.00999999")
    if not pay_to or not announcement_id or floor <= 0:
        return None
    found = {}
    async for txn in _payment_txns(config, pay_to):
        txn_id = str(txn.get("id") or "")
        if not txn_id or txn_id in found:
            continue
        for out in txn.get("outputs") or []:
            if not isinstance(out, dict) or str(out.get("to") or "") != pay_to:
                continue
            value = _amount(out.get("value"))
            if floor < value <= ceiling:
                found[txn_id] = (txn, f"{value:.8f}")
                break
    if len(found) != 1:
        return None
    payment, amount = next(iter(found.values()))
    payment_id = payment.get("id") or ""
    used = await config.mongo.async_db[INVOICES].find_one({"payment_id": payment_id})
    if used:
        if str(used.get("announcement_id") or "") not in ("", announcement_id):
            return None
        now = int(time.time())
        anchor = int(used.get("redeemed_at") or now)
        exp = access_expiry(anchor, grant_seconds)
        if not access_open(exp, now):
            raise AccessExpired(EXPIRED_ERROR)
        if (
            used.get("access")
            and int(used.get("access_exp") or 0) == exp
            and access_open(used.get("access_exp"), now)
        ):
            return {
                "access": used.get("access"),
                "payment_id": payment_id,
                "access_exp": used.get("access_exp"),
            }
        issued = issue_access(
            config, announcement_id, payment_id, grant_seconds, anchor
        )
        await _store_access(config, {"payment_id": payment_id}, issued, anchor)
        return issued
    now = int(time.time())
    issued = issue_access(config, announcement_id, payment_id, grant_seconds)
    await config.mongo.async_db[INVOICES].insert_one(
        {
            "token": secrets.token_hex(32),
            "announcement_id": announcement_id,
            "pay_to": pay_to,
            "amount": amount,
            "price": str(price),
            "created_at": now,
            "expires_at": now + INVOICE_TTL,
            "redeemed_at": now,
            "payment_id": payment_id,
            "access": issued["access"],
            "access_exp": issued["access_exp"],
        }
    )
    return issued


async def payment_grant_elapsed(
    config, announcement_id: str, payment_id: str, grant_seconds
) -> bool:
    if grant_limit(grant_seconds) <= 0 or not payment_id:
        return False
    try:
        doc = await config.mongo.async_db[INVOICES].find_one(
            {"payment_id": payment_id, "announcement_id": announcement_id},
            {"redeemed_at": 1},
        )
    except Exception:
        return False
    if not doc or not doc.get("redeemed_at"):
        return False
    return not access_open(access_expiry(int(doc["redeemed_at"]), grant_seconds))


async def find_confirmed_payment(config, pay_to: str, min_price: str, payer_ids):
    """Return a matching payment from the mempool or a block."""
    pay_to = (pay_to or "").strip()
    if not pay_to or not min_price:
        return None
    async for txn in _payment_txns(config, pay_to):
        if output_pays(txn, pay_to, min_price) and payer_matches(txn, payer_ids):
            return txn
    return None
