import time

from yadacoin.core.identityannouncement import IdentityAnnouncement
from yadacoin.core.keyeventlog import KeyEventLog
from yadacoin.core.transaction import Transaction
from yadacoin.http.base import BaseHandler


def _kel_entry_prev(x) -> str:
    """prev_public_key_hash from a Transaction, KeyEvent wrapper, or dict."""
    if isinstance(x, dict):
        return x.get("prev_public_key_hash") or ""
    try:
        wrapped = getattr(x, "txn", None)
        if wrapped is not None:
            prev = getattr(wrapped, "prev_public_key_hash", None) or ""
            if prev:
                return prev
    except Exception:
        pass
    try:
        prev = getattr(x, "prev_public_key_hash", None) or ""
        if prev:
            return prev
    except Exception:
        pass
    if hasattr(x, "to_dict"):
        try:
            return (x.to_dict() or {}).get("prev_public_key_hash") or ""
        except Exception:
            return ""
    return ""


def _kel_rotation_depth(log) -> int:
    """Match password-core kelRotationDepth: inception + rotations."""
    if not log:
        return 0
    inception = 0
    rotations = 0
    for x in log:
        prev = _kel_entry_prev(x)
        if not prev:
            if not inception:
                inception = 1
        else:
            rotations += 1
    return inception + rotations


class HasKELHandler(BaseHandler):
    async def get(self):
        public_key = self.get_query_argument("public_key")
        txn = Transaction(public_key=public_key)
        result = await txn.has_key_event_log()
        return self.render_as_json({"status": result})


class IdentityInceptionStatusHandler(BaseHandler):
    """Whether a vault K0 already has an identity announcement / KEL inception.

    Query:
      public_key  (required) — K0 compressed public key hex
      username    (optional) — cross-check IdentityAnnouncement username

    Response:
      status, incepted, has_kel, kel_depth, identity (optional match info)
    """

    async def get(self):
        public_key = self.get_query_argument("public_key", None)
        username = self.get_query_argument("username", None)
        if not public_key:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "public_key required"}
            )

        public_key = str(public_key).strip()
        log = []
        try:
            log = await KeyEventLog.build_from_public_key(public_key) or []
        except Exception:
            log = []

        kel_depth = _kel_rotation_depth(log)
        has_kel = kel_depth >= 1 or bool(log)

        # has_key_event_log only checks prerotated/twice-prerotated addresses,
        # so K0 inception alone is false there — still treat a non-empty log as KEL.
        if not has_kel:
            try:
                txn = Transaction(public_key=public_key)
                if await txn.has_key_event_log():
                    has_kel = True
                    if kel_depth < 1:
                        kel_depth = 1
            except Exception:
                pass

        identity_info = None
        username_matches = None
        if username is not None and str(username).strip():
            uname = str(username).strip()
            found = await IdentityAnnouncement.get_by_username(uname)
            if found:
                pk = found.get("public_key") or ""
                # Hex public keys are case-insensitive
                username_matches = pk.lower() == public_key.lower() if pk else False
                identity_info = {
                    "username": (found.get("identity") or {}).get("username") or uname,
                    "public_key": pk,
                    "source": found.get("source"),
                    "matches_public_key": username_matches,
                }
            else:
                username_matches = False
                identity_info = {
                    "username": uname,
                    "public_key": "",
                    "source": None,
                    "matches_public_key": False,
                }

        # Incepted if KEL exists for this key, or username identity is already
        # claimed by this same public key (announcement is the inception txn).
        incepted = bool(has_kel) or bool(username_matches)

        return self.render_as_json(
            {
                "status": True,
                "incepted": incepted,
                "has_kel": bool(has_kel),
                "kel_depth": int(
                    kel_depth if has_kel else (1 if username_matches else 0)
                ),
                "identity": identity_info,
            }
        )


class KELHandler(BaseHandler):
    async def get(self):
        public_key = self.get_query_argument("public_key")
        log = await KeyEventLog.build_from_public_key(public_key)
        outlog = []
        for x in log:
            y = x.to_dict()
            if hasattr(x, "mempool"):
                y["mempool"] = x.mempool
            outlog.append(y)
        return self.render_as_json({"status": True, "key_event_log": outlog})


class KELReportsHandler(BaseHandler):
    async def get(self):
        report_type = self.get_query_argument("report_type", "all")
        from_date = self.get_query_argument("from_date", None)
        to_date = self.get_query_argument("to_date", time.time())

        date_preset = self.get_query_argument("date_preset", None)
        counts = int(self.get_query_argument("counts", 1))

        if date_preset == "day":
            from_date = time.time() - (60 * 60 * 24 * 1)
        elif date_preset == "week":
            from_date = time.time() - (60 * 60 * 24 * 7)
        elif date_preset == "month":
            from_date = time.time() - (60 * 60 * 24 * 31)

        query = {"public_key_hash": {"$ne": "", "$exists": True}}
        query2 = {
            "transactions.time": {"$gte": int(from_date), "$lte": int(to_date)},
            "transactions.public_key_hash": {"$ne": "", "$exists": True},
        }

        if report_type == "new":
            query2["transactions.prev_public_key_hash"] = ""

        result = await self.config.mongo.async_db.blocks.aggregate(
            [
                {"$match": {"transactions": {"$elemMatch": query}}},
                {"$unwind": "$transactions"},
                {"$match": query2},
            ]
        ).to_list(None)
        if counts:
            result = len(result)

        return self.render_as_json({"result": result}, indent=True)


KEY_EVENT_LOG_HANDLERS = [
    (r"/has-key-event-log", HasKELHandler),
    (r"/identity-inception-status", IdentityInceptionStatusHandler),
    (r"/key-event-log", KELHandler),
    (r"/kel-reports", KELReportsHandler),
]
