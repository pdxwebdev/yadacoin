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


KEY_EVENT_LOG_HANDLERS = [
    (r"/has-key-event-log", HasKELHandler),
    (r"/key-event-log", KELHandler),
]
