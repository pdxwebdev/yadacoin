import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pymongo.errors import DuplicateKeyError

from yadacoin.websocket.base import RCPWebSocketServer


class TestWebsocketNewtxnSlotCollision(unittest.IsolatedAsyncioTestCase):
    def _server(self, replace_side_effect=None):
        server = RCPWebSocketServer.__new__(RCPWebSocketServer)
        server.config = MagicMock()
        server.config.LatestBlock.block.index = 0
        server.peer = MagicMock()
        server.peer.identity.public_key = "local"
        server.write_params = AsyncMock()
        coll = server.config.mongo.async_db.miner_transactions
        coll.replace_one = AsyncMock(side_effect=replace_side_effect)
        return server, coll

    def _txn(self):
        txn = MagicMock()
        txn.transaction_signature = "sig"
        txn.verify = AsyncMock()
        txn.mempool_doc = AsyncMock(return_value={"id": "sig", "first_seen": 1.0})
        return txn

    async def test_duplicate_key_is_logged_and_not_relayed(self):
        server, coll = self._server(replace_side_effect=DuplicateKeyError("slot"))
        params = {"transaction": {"id": "sig"}}
        with patch(
            "yadacoin.websocket.base.Transaction.from_dict",
            return_value=self._txn(),
        ):
            await server.newtxn({"params": params}, source="websocket")
        coll.replace_one.assert_awaited_once()
        server.write_params.assert_not_awaited()
        server.config.app_log.warning.assert_called_once()

    async def test_stores_mempool_doc_and_relays(self):
        server, coll = self._server()
        params = {"transaction": {"id": "sig"}}
        with patch(
            "yadacoin.websocket.base.Transaction.from_dict",
            return_value=self._txn(),
        ):
            await server.newtxn({"params": params}, source="websocket")
        doc = coll.replace_one.await_args[0][1]
        self.assertEqual(doc["first_seen"], 1.0)
        server.write_params.assert_awaited_once_with("newtxn", params)


class TestWebsocketRouteSlotCollision(unittest.IsolatedAsyncioTestCase):
    def _server(self, replace_side_effect=None):
        server = RCPWebSocketServer.__new__(RCPWebSocketServer)
        server.config = MagicMock()
        server.config.LatestBlock.block.index = 0
        server.config.shares_required = False
        server.config.peer = MagicMock()
        server.write_result = AsyncMock()
        server.config.websocketServer.inbound_streams = {
            "User": {},
            "Group": {},
        }
        coll = server.config.mongo.async_db.miner_transactions
        coll.replace_one = AsyncMock(side_effect=replace_side_effect)
        private = server.config.mongo.async_db.private_transactions
        private.replace_one = AsyncMock()
        return server, coll, private

    def _txn(self, private=True, verify_side_effect=None):
        txn = MagicMock()
        txn.transaction_signature = "sig"
        txn.requester_rid = "r"
        txn.private = private
        txn.to_dict.return_value = {"id": "sig"}
        txn.verify = AsyncMock(side_effect=verify_side_effect)
        return txn

    async def test_duplicate_key_skips_private_mirror_and_confirms(self):
        server, coll, private = self._server(
            replace_side_effect=DuplicateKeyError("slot")
        )
        body = {"params": {"route": "r", "transaction": {"id": "sig"}}}
        with patch(
            "yadacoin.websocket.base.Transaction.from_dict",
            return_value=self._txn(),
        ):
            await server.route(body, source="websocket")
        coll.replace_one.assert_awaited_once()
        private.replace_one.assert_not_awaited()
        server.write_result.assert_awaited_once()

    async def test_stores_and_mirrors_private_transaction(self):
        server, coll, private = self._server()
        body = {"params": {"route": "r", "transaction": {"id": "sig"}}}
        with patch(
            "yadacoin.websocket.base.Transaction.from_dict",
            return_value=self._txn(),
        ):
            await server.route(body, source="websocket")
        coll.replace_one.assert_awaited_once()
        private.replace_one.assert_awaited_once()

    async def test_invalid_transaction_is_not_stored_or_relayed(self):
        server, coll, private = self._server()
        body = {"params": {"route": "r", "transaction": {"id": "sig"}}}
        with patch(
            "yadacoin.websocket.base.Transaction.from_dict",
            return_value=self._txn(verify_side_effect=ValueError("bad sig")),
        ):
            await server.route(body, source="websocket")
        coll.replace_one.assert_not_awaited()
        private.replace_one.assert_not_awaited()
        server.write_result.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
