import time

from yadacoin.core.keyeventlog import KeyEventLog
from yadacoin.core.transaction import Transaction
from yadacoin.http.base import BaseHandler


class HasKELHandler(BaseHandler):
    async def get(self):
        public_key = self.get_query_argument("public_key")
        txn = Transaction(public_key=public_key)
        result = await txn.has_key_event_log()
        return self.render_as_json({"status": result})


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
    (r"/key-event-log", KELHandler),
    (r"/kel-reports", KELReportsHandler),
]
