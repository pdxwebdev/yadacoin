from yadacoin.core.keyeventlog import KeyEventLog
from yadacoin.core.transaction import Transaction
from yadacoin.http.base import BaseHandler


class HasKELHandler(BaseHandler):
    async def get(self):
        public_key = self.get_query_argument("public_key")
        txn = Transaction(public_key=public_key)
        await txn.has_key_event_log()
        return self.render_as_json({"status": True})


class KELHandler(BaseHandler):
    async def get(self):
        public_key = self.get_query_argument("public_key")
        log = await KeyEventLog.build_from_public_key(public_key)
        return self.render_as_json(
            {"status": True, "key_event_log": [x.to_dict() for x in log]}
        )


KEY_EVENT_LOG_HANDLERS = [
    (r"/has-key-event-log", HasKELHandler),
    (r"/key-event-log", KELHandler),
]
