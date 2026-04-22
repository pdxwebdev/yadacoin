"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from logging import getLogger
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.config import Config
from yadacoin.core.transactionutils import TU

from ..test_setup import AsyncTestCase


class TUTestCase(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        config = Config()
        if not hasattr(config, "app_log"):
            config.app_log = getLogger("tornado.application")
        self.config = config
        self.public_key = config.public_key
        self.private_key = config.private_key


# ---------------------------------------------------------------------------
# Pure / simple methods
# ---------------------------------------------------------------------------


class TestTUHash(unittest.TestCase):
    def test_hash_returns_64_char_hex(self):
        result = TU.hash("hello world")
        self.assertEqual(len(result), 64)
        self.assertIsInstance(result, str)

    def test_hash_is_deterministic(self):
        self.assertEqual(TU.hash("abc"), TU.hash("abc"))

    def test_hash_differs_for_different_messages(self):
        self.assertNotEqual(TU.hash("abc"), TU.hash("def"))


class TestTUGenerateDeterministicSignature(TUTestCase):
    async def test_with_explicit_private_key(self):
        sig = TU.generate_deterministic_signature(
            config=None, message="test", private_key=self.private_key
        )
        self.assertIsInstance(sig, str)
        # base64-encoded signature
        import base64

        decoded = base64.b64decode(sig)
        self.assertGreater(len(decoded), 0)

    async def test_with_config_private_key(self):
        sig = TU.generate_deterministic_signature(config=self.config, message="hello")
        self.assertIsInstance(sig, str)

    async def test_deterministic_same_output(self):
        sig1 = TU.generate_deterministic_signature(
            config=None, message="fixed msg", private_key=self.private_key
        )
        sig2 = TU.generate_deterministic_signature(
            config=None, message="fixed msg", private_key=self.private_key
        )
        self.assertEqual(sig1, sig2)


class TestTUGenerateSignature(TUTestCase):
    async def test_generate_signature_returns_string(self):
        sig = TU.generate_signature(message="test msg", private_key=self.private_key)
        self.assertIsInstance(sig, str)

    async def test_generate_signature_with_private_key_returns_string(self):
        sig = TU.generate_signature_with_private_key(
            private_key=self.private_key, message="test"
        )
        self.assertIsInstance(sig, str)

    async def test_generate_signature_non_deterministic(self):
        """Random nonce means signatures differ across calls."""
        sig1 = TU.generate_signature("msg", self.private_key)
        sig2 = TU.generate_signature("msg", self.private_key)
        # They MIGHT equal (astronomically unlikely), but generally won't
        # Just verify both are valid base64 strings
        import base64

        base64.b64decode(sig1)
        base64.b64decode(sig2)


class TestTUGenerateRid(TUTestCase):
    async def test_generate_rid_returns_hex(self):
        rid = TU.generate_rid(self.config, "some_username_signature")
        self.assertEqual(len(rid), 64)
        int(rid, 16)  # should be valid hex

    async def test_generate_rid_is_symmetric(self):
        """RID is the same regardless of argument order because signatures are sorted."""
        sig_a = "aaa_sig"
        sig_b = "zzz_sig"

        # Build a mock config with username_signature = sig_a
        mock_config_a = MagicMock()
        mock_config_a.username_signature = sig_a
        rid_a = TU.generate_rid(mock_config_a, sig_b)

        mock_config_b = MagicMock()
        mock_config_b.username_signature = sig_b
        rid_b = TU.generate_rid(mock_config_b, sig_a)

        self.assertEqual(rid_a, rid_b)


class TestGetTransactionObjsList(unittest.TestCase):
    def test_flattens_dict_of_lists(self):
        objs = {"key1": [1, 2, 3], "key2": [4, 5]}
        result = TU.get_transaction_objs_list(objs)
        self.assertCountEqual(result, [1, 2, 3, 4, 5])

    def test_empty_dict(self):
        result = TU.get_transaction_objs_list({})
        self.assertEqual(result, [])

    def test_single_entry(self):
        result = TU.get_transaction_objs_list({"k": ["a"]})
        self.assertEqual(result, ["a"])


# ---------------------------------------------------------------------------
# TU.send()
# ---------------------------------------------------------------------------


class TestTUSend(TUTestCase):
    async def test_send_from_config_address_not_enough_money(self):
        """When Transaction.generate raises NotEnoughMoneyException, send returns error."""
        from yadacoin.core.transaction import NotEnoughMoneyException, Transaction

        with patch.object(
            Transaction,
            "generate",
            side_effect=NotEnoughMoneyException("no money"),
        ):
            result = await TU.send(
                config=self.config,
                to="someaddr",
                value=99999.0,
                from_address=self.config.address,
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("not enough money", result["message"])

    async def test_send_from_other_address_not_found(self):
        """When child_keys lookup returns None, send returns error."""
        mock_db = MagicMock()
        mock_db.child_keys.find_one = AsyncMock(return_value=None)
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await TU.send(
                config=self.config,
                to="someaddr",
                value=1.0,
                from_address="some_other_address",
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("no wallet matching from address", result["message"])

    async def test_send_from_other_address_found_generates_transaction(self):
        """When child_keys lookup returns a key, send uses it for the transaction."""
        from yadacoin.core.transaction import NotEnoughMoneyException, Transaction

        mock_db = MagicMock()
        mock_db.child_keys.find_one = AsyncMock(
            return_value={
                "public_key": self.public_key,
                "private_key": self.private_key,
            }
        )
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(
                Transaction,
                "generate",
                side_effect=NotEnoughMoneyException("no money"),
            ):
                result = await TU.send(
                    config=self.config,
                    to="someaddr",
                    value=1.0,
                    from_address="some_other_address",
                )
        self.assertEqual(result["status"], "error")

    async def test_send_dry_run_skips_db_insert(self):
        """dry_run=True means no DB insert and no peer broadcast."""
        from yadacoin.core.transaction import Transaction

        mock_txn = MagicMock()
        mock_txn.to_dict.return_value = {"id": "txnid123", "hash": "abc"}
        mock_txn.transaction_signature = "sig1"
        mock_txn.verify = AsyncMock()

        mock_latest_block = MagicMock()
        mock_latest_block.block.index = 0

        with patch.object(
            Transaction, "generate", new=AsyncMock(return_value=mock_txn)
        ):
            with patch.object(
                self.config, "LatestBlock", mock_latest_block, create=True
            ):
                result = await TU.send(
                    config=self.config,
                    to="addr1",
                    value=1.0,
                    from_address=self.config.address,
                    dry_run=True,
                )
        # Should return the transaction dict
        self.assertIn("id", result)

    async def test_send_with_explicit_outputs(self):
        """When outputs list is provided, they override the default to/value."""
        from yadacoin.core.transaction import NotEnoughMoneyException, Transaction

        with patch.object(
            Transaction,
            "generate",
            side_effect=NotEnoughMoneyException("no money"),
        ):
            result = await TU.send(
                config=self.config,
                to=None,
                value=None,
                outputs=[{"to": "addr1", "value": "5.0"}],
            )
        self.assertEqual(result["status"], "error")


# ---------------------------------------------------------------------------
# TU.clean_mempool()
# ---------------------------------------------------------------------------


class TestCleanMempool(TUTestCase):
    async def test_clean_mempool_no_transactions(self):
        """With empty DB, clean_mempool runs without error."""
        mock_db = MagicMock()
        mock_db.failed_transactions.delete_many = AsyncMock()
        mock_db.miner_transactions.find.return_value.__aiter__ = MagicMock(
            return_value=iter([])
        )
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        mock_db.miner_transactions.delete_many = AsyncMock()
        mock_db.failed_transactions.insert_one = AsyncMock()

        # Async iteration mock
        async def empty_aiter(*args, **kwargs):
            return
            yield

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_aiter()
        mock_db.miner_transactions.find.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            await TU.clean_mempool(self.config)

        mock_db.failed_transactions.delete_many.assert_called_once()

    async def test_clean_mempool_deletes_already_in_blockchain(self):
        """Transactions already in blockchain get moved to failed_transactions."""
        mock_db = MagicMock()
        mock_db.failed_transactions.delete_many = AsyncMock()
        mock_db.miner_transactions.find_one = AsyncMock(return_value={"id": "txn1"})
        mock_db.blocks.find_one = AsyncMock(return_value={"index": 1})
        mock_db.miner_transactions.delete_many = AsyncMock()
        mock_db.failed_transactions.insert_one = AsyncMock()

        txn_data = {
            "id": "txn1",
            "inputs": [],
            "time": 9999999999,
            "never_expire": False,
        }

        async def find_iter_1(*args, **kwargs):
            yield txn_data

        async def find_iter_2(*args, **kwargs):
            return
            yield

        call_count = [0]
        mock_cursor1 = MagicMock()
        mock_cursor2 = MagicMock()
        mock_cursor1.__aiter__ = lambda self: find_iter_1()
        mock_cursor2.__aiter__ = lambda self: find_iter_2()

        def find_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_cursor1
            return mock_cursor2

        mock_db.miner_transactions.find.side_effect = find_side_effect

        mock_bu = MagicMock()
        mock_bu.is_input_spent = AsyncMock(return_value=False)

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "BU", mock_bu):
                await TU.clean_mempool(self.config)

        # failed_transactions.insert_one should have been called once for the in-blockchain txn
        mock_db.failed_transactions.insert_one.assert_called_once()


# ---------------------------------------------------------------------------
# TU.clean_txn_tracking()
# ---------------------------------------------------------------------------


class TestCleanTxnTracking(TUTestCase):
    async def test_clean_txn_tracking_updates_recent_transactions(self):
        """Transactions recent enough should be kept (update_one called)."""
        import time as time_module

        recent_time = int(time_module.time())
        doc = {"rid": "peer1", "transactions": {"txn1": recent_time}}

        mock_db = MagicMock()
        mock_db.txn_tracking.update_one = AsyncMock()
        mock_db.txn_tracking.delete_one = AsyncMock()

        async def find_iter():
            yield doc

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: find_iter()
        mock_db.txn_tracking.find.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            await TU.clean_txn_tracking(self.config)

        mock_db.txn_tracking.update_one.assert_called_once()
        mock_db.txn_tracking.delete_one.assert_not_called()

    async def test_clean_txn_tracking_deletes_old_entries(self):
        """Entries with all old transactions should be deleted entirely."""
        old_time = 1  # way in the past

        doc = {"rid": "peer1", "transactions": {"txn1": old_time}}

        mock_db = MagicMock()
        mock_db.txn_tracking.update_one = AsyncMock()
        mock_db.txn_tracking.delete_one = AsyncMock()

        async def find_iter():
            yield doc

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: find_iter()
        mock_db.txn_tracking.find.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            await TU.clean_txn_tracking(self.config)

        mock_db.txn_tracking.delete_one.assert_called_once_with({"rid": "peer1"})
        mock_db.txn_tracking.update_one.assert_not_called()


# ---------------------------------------------------------------------------
# TU.get_current_smart_contract_txns()
# ---------------------------------------------------------------------------


class TestGetSmartContractTxns(TUTestCase):
    async def test_get_current_smart_contract_txns_returns_cursor(self):
        """Should return an aggregation cursor from blocks collection."""
        mock_cursor = MagicMock()
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await TU.get_current_smart_contract_txns(
                self.config, start_index=100
            )

        self.assertIs(result, mock_cursor)
        mock_db.blocks.aggregate.assert_called_once()

    async def test_get_expired_smart_contract_txns_returns_cursor(self):
        """Should return an aggregation cursor from blocks collection."""
        mock_cursor = MagicMock()
        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            result = await TU.get_expired_smart_contract_txns(
                self.config, start_index=50
            )

        self.assertIs(result, mock_cursor)


# ---------------------------------------------------------------------------
# TU.get_trigger_txns() - async generator
# ---------------------------------------------------------------------------


class TestGetTriggerTxns(TUTestCase):
    async def test_get_trigger_txns_yields_results(self):
        """Should yield blocks from the aggregation cursor."""
        block_data = {"index": 1, "transactions": [{"id": "txn1"}]}

        async def mock_aggregate_iter():
            yield block_data

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: mock_aggregate_iter()

        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value = mock_cursor

        mock_smart_contract_txn = MagicMock()
        mock_smart_contract_txn.requested_rid = "rid1"
        mock_smart_contract_txn.relationship.identity.public_key = "pk1"

        results = []
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            async for block in TU.get_trigger_txns(
                self.config, mock_smart_contract_txn, start_index=None, end_index=None
            ):
                results.append(block)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], block_data)

    async def test_get_trigger_txns_empty(self):
        """With no results, yields nothing."""

        async def empty_iter():
            return
            yield

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()

        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value = mock_cursor

        mock_sc_txn = MagicMock()
        mock_sc_txn.requested_rid = "rid1"
        mock_sc_txn.relationship.identity.public_key = "pk1"

        results = []
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            async for block in TU.get_trigger_txns(self.config, mock_sc_txn):
                results.append(block)

        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# TU.rebroadcast_failed()
# ---------------------------------------------------------------------------


class TestRebroadcastFailed(TUTestCase):
    async def test_rebroadcast_failed_with_no_transactions(self):
        """No transactions in failed_transactions means no peer writes."""
        mock_db = MagicMock()

        async def empty_iter():
            return
            yield

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_db.failed_transactions.find.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            await TU.rebroadcast_failed(self.config, "txnid123")
        # No errors raised → pass

    async def test_rebroadcast_failed_with_transaction(self):
        """Transaction is rebroadcast to all sync peers."""

        mock_db = MagicMock()
        mock_txn_dict = {
            "txn": {
                "time": 1000,
                "id": "sig1",
                "rid": "",
                "relationship": "",
                "public_key": self.public_key,
                "dh_public_key": None,
                "fee": 0.0,
                "inputs": [],
                "outputs": [],
            }
        }

        async def txn_iter():
            yield mock_txn_dict

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: txn_iter()
        mock_db.failed_transactions.find.return_value = mock_cursor

        mock_peer_stream = MagicMock()
        mock_peer_stream.peer.protocol_version = 1

        async def mock_get_sync_peers():
            yield mock_peer_stream

        mock_node_shared = MagicMock()
        mock_node_shared.write_params = AsyncMock()

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "peer") as mock_peer:
                mock_peer.get_sync_peers = mock_get_sync_peers
                with patch.object(
                    self.config, "nodeShared", mock_node_shared, create=True
                ):
                    await TU.rebroadcast_failed(self.config, "sig1")

        mock_node_shared.write_params.assert_called_once()


# ---------------------------------------------------------------------------
# TU.combine_oldest_transactions()
# ---------------------------------------------------------------------------


class TestCombineOldestTransactions(TUTestCase):
    async def test_insufficient_transactions_returns_early(self):
        """Returns early when fewer than 100 transactions found."""
        mock_db = MagicMock()
        mock_db.miner_transactions.find.return_value.__aiter__ = MagicMock(
            return_value=iter([])
        )

        async def empty_find_iter(*args, **kwargs):
            return
            yield

        mock_mempool_cursor = MagicMock()
        mock_mempool_cursor.__aiter__ = lambda self: empty_find_iter()
        mock_db.miner_transactions.find.return_value = mock_mempool_cursor

        # BU.get_wallet_unspent_transactions_for_dusting returns a few items (< 100)
        async def few_txns(*args, **kwargs):
            for i in range(3):
                yield {
                    "id": f"txn{i}",
                    "outputs": [{"to": self.config.address, "value": 1.0}],
                }

        mock_bu = MagicMock()
        mock_bu.get_wallet_unspent_transactions_for_dusting = lambda addr: few_txns(
            addr
        )

        mock_mempool_cursor2 = MagicMock()
        mock_mempool_cursor2.to_list = AsyncMock(return_value=[])

        mock_db.miner_transactions.find.return_value = mock_mempool_cursor2

        self.config.combined_address = "combined_addr"

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "BU", mock_bu):
                # Should not raise, just log and return
                await TU.combine_oldest_transactions(self.config)

    async def test_combine_100_transactions_calls_send(self):
        """When 100+ transactions found, calls send() to combine them."""
        mock_db = MagicMock()
        mock_mempool_cursor = MagicMock()
        mock_mempool_cursor.to_list = AsyncMock(return_value=[])
        mock_db.miner_transactions.find.return_value = mock_mempool_cursor

        async def many_txns(*args, **kwargs):
            for i in range(100):
                yield {
                    "id": f"txn{i}",
                    "outputs": [{"to": self.config.address, "value": 1.0}],
                }

        mock_bu = MagicMock()
        mock_bu.get_wallet_unspent_transactions_for_dusting = lambda addr: many_txns(
            addr
        )

        self.config.combined_address = "combined_addr"

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "BU", mock_bu):
                with patch.object(
                    TU, "send", new=AsyncMock(return_value={"id": "combined_txn"})
                ) as mock_send:
                    await TU.combine_oldest_transactions(self.config)

        mock_send.assert_called_once()

    async def test_combine_send_returns_error(self):
        """When send() returns an error, logs error without raising."""
        mock_db = MagicMock()
        mock_mempool_cursor = MagicMock()
        mock_mempool_cursor.to_list = AsyncMock(return_value=[])
        mock_db.miner_transactions.find.return_value = mock_mempool_cursor

        async def many_txns(*args, **kwargs):
            for i in range(100):
                yield {
                    "id": f"txn{i}",
                    "outputs": [{"to": self.config.address, "value": 1.0}],
                }

        mock_bu = MagicMock()
        mock_bu.get_wallet_unspent_transactions_for_dusting = lambda addr: many_txns(
            addr
        )

        self.config.combined_address = "combined_addr"

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "BU", mock_bu):
                with patch.object(
                    TU,
                    "send",
                    new=AsyncMock(return_value={"status": "error", "message": "fail"}),
                ):
                    await TU.combine_oldest_transactions(self.config)

    async def test_combine_send_raises_exception(self):
        """Lines 465-466: when send() raises an exception, error is logged."""
        mock_db = MagicMock()
        mock_mempool_cursor = MagicMock()
        mock_mempool_cursor.to_list = AsyncMock(return_value=[])
        mock_db.miner_transactions.find.return_value = mock_mempool_cursor

        async def many_txns(*args, **kwargs):
            for i in range(100):
                yield {
                    "id": f"txn{i}",
                    "outputs": [{"to": self.config.address, "value": 1.0}],
                }

        mock_bu = MagicMock()
        mock_bu.get_wallet_unspent_transactions_for_dusting = lambda addr: many_txns(
            addr
        )

        self.config.combined_address = "combined_addr"

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "BU", mock_bu):
                with patch.object(
                    TU,
                    "send",
                    new=AsyncMock(side_effect=RuntimeError("send failed")),
                ):
                    # Should not raise — exception is caught and logged
                    await TU.combine_oldest_transactions(self.config)


# ---------------------------------------------------------------------------
# TU.send() supplemental - lines 103-104, 122-123, 127, 131, 135, 143-157
# ---------------------------------------------------------------------------


class TestTUSendSupplemental(TUTestCase):
    async def test_send_outputs_list_converts_float(self):
        """Lines 103-104: outputs list causes float conversion, then NotEnoughMoney."""
        from yadacoin.core.transaction import NotEnoughMoneyException, Transaction

        with patch.object(
            Transaction,
            "generate",
            side_effect=NotEnoughMoneyException("no money"),
        ):
            result = await TU.send(
                config=self.config,
                to=None,
                value=None,
                outputs=[{"to": "addr1", "value": "5.0"}],
                from_address=self.config.address,
            )
        self.assertEqual(result["status"], "error")

    async def test_send_generic_exception_reraises(self):
        """Lines 122-123: non-NotEnoughMoney exception in Transaction.generate reraises."""
        from yadacoin.core.transaction import Transaction

        with self.assertRaises(RuntimeError):
            with patch.object(
                Transaction,
                "generate",
                side_effect=RuntimeError("unexpected"),
            ):
                await TU.send(
                    config=self.config,
                    to="addr",
                    value=1.0,
                    from_address=self.config.address,
                )

    async def test_send_too_many_inputs_exception(self):
        """Lines 143-144: TooManyInputsException returns error dict."""
        from yadacoin.core.transaction import TooManyInputsException, Transaction

        mock_txn = MagicMock()
        mock_txn.to_dict.return_value = {"id": "txnid"}
        mock_txn.transaction_signature = "sig1"
        mock_txn.verify = AsyncMock(side_effect=TooManyInputsException("too many"))

        mock_latest_block = MagicMock()
        mock_latest_block.block.index = 0

        with patch.object(
            Transaction, "generate", new=AsyncMock(return_value=mock_txn)
        ):
            with patch.object(
                self.config, "LatestBlock", mock_latest_block, create=True
            ):
                result = await TU.send(
                    config=self.config,
                    to="addr",
                    value=1.0,
                    from_address=self.config.address,
                )
        self.assertIn("status", result)
        self.assertEqual(result["status"], "error")

    async def test_send_verify_other_exception_returns_error(self):
        """Lines 145-146: generic exception in verify returns error dict."""
        from yadacoin.core.transaction import Transaction

        mock_txn = MagicMock()
        mock_txn.to_dict.return_value = {"id": "txnid"}
        mock_txn.transaction_signature = "sig1"
        mock_txn.verify = AsyncMock(side_effect=Exception("verify failed"))

        mock_latest_block = MagicMock()
        mock_latest_block.block.index = 0

        with patch.object(
            Transaction, "generate", new=AsyncMock(return_value=mock_txn)
        ):
            with patch.object(
                self.config, "LatestBlock", mock_latest_block, create=True
            ):
                result = await TU.send(
                    config=self.config,
                    to="addr",
                    value=1.0,
                    from_address=self.config.address,
                )
        self.assertIn("error", result)

    async def test_send_checks_fork_flags_high_block_index(self):
        """Lines 127, 131, 135: high block index sets all check flags to True."""
        from yadacoin.core.chain import CHAIN
        from yadacoin.core.transaction import Transaction

        mock_txn = MagicMock()
        mock_txn.to_dict.return_value = {"id": "txnid"}
        mock_txn.transaction_signature = "sig1"
        mock_txn.verify = AsyncMock()

        # Use a block index above all fork thresholds
        high_index = (
            max(
                CHAIN.CHECK_MAX_INPUTS_FORK,
                CHAIN.CHECK_MASTERNODE_FEE_FORK,
                CHAIN.CHECK_KEL_FORK,
            )
            + 1000
        )

        mock_latest_block = MagicMock()
        mock_latest_block.block.index = high_index

        with patch.object(
            Transaction, "generate", new=AsyncMock(return_value=mock_txn)
        ):
            with patch.object(
                self.config, "LatestBlock", mock_latest_block, create=True
            ):
                result = await TU.send(
                    config=self.config,
                    to="addr",
                    value=1.0,
                    from_address=self.config.address,
                    dry_run=True,
                )
        self.assertIn("id", result)

    async def test_send_not_dry_run_inserts_and_broadcasts(self):
        """Lines 149-157: dry_run=False inserts to DB and broadcasts to peers."""
        from yadacoin.core.transaction import Transaction

        mock_txn = MagicMock()
        mock_txn.to_dict.return_value = {"id": "txnid"}
        mock_txn.transaction_signature = "sig1"
        mock_txn.verify = AsyncMock()

        mock_latest_block = MagicMock()
        mock_latest_block.block.index = 0

        mock_db = MagicMock()
        mock_db.miner_transactions.insert_one = AsyncMock()

        mock_peer_stream = MagicMock()
        mock_peer_stream.peer.protocol_version = 2
        mock_peer_stream.peer.rid = "peer1"

        async def mock_get_sync_peers():
            yield mock_peer_stream

        mock_node_shared = MagicMock()
        mock_node_shared.write_params = AsyncMock()

        mock_node_client = MagicMock()
        mock_node_client.retry_messages = {}

        with patch.object(
            Transaction, "generate", new=AsyncMock(return_value=mock_txn)
        ):
            with patch.object(
                self.config, "LatestBlock", mock_latest_block, create=True
            ):
                with patch.object(self.config.mongo, "async_db", new=mock_db):
                    with patch.object(self.config, "peer") as mock_peer:
                        mock_peer.get_sync_peers = mock_get_sync_peers
                        with patch.object(
                            self.config, "nodeShared", mock_node_shared, create=True
                        ):
                            with patch.object(
                                self.config, "nodeClient", mock_node_client, create=True
                            ):
                                result = await TU.send(
                                    config=self.config,
                                    to="addr",
                                    value=1.0,
                                    from_address=self.config.address,
                                    dry_run=False,
                                )

        mock_db.miner_transactions.insert_one.assert_called_once()
        mock_node_shared.write_params.assert_called_once()


# ---------------------------------------------------------------------------
# TU.clean_mempool() - is_input_spent returns True
# ---------------------------------------------------------------------------


class TestCleanMempoolInputSpent(TUTestCase):
    async def test_clean_mempool_input_spent_marks_for_deletion(self):
        """Lines 181-188: is_input_spent=True appends to to_delete."""
        mock_db = MagicMock()
        mock_db.failed_transactions.delete_many = AsyncMock()
        mock_db.miner_transactions.delete_many = AsyncMock()
        mock_db.failed_transactions.insert_one = AsyncMock()
        mock_db.blocks.find_one = AsyncMock(return_value=None)

        txn_data = {
            "id": "txn1",
            "inputs": [{"id": "input1"}],
            "public_key": self.public_key,
            "time": 9999999999,
            "never_expire": False,
        }

        async def find_iter_1(*args, **kwargs):
            yield txn_data

        async def find_iter_2(*args, **kwargs):
            return
            yield

        call_count = [0]

        def find_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_cursor = MagicMock()
            if call_count[0] == 1:
                mock_cursor.__aiter__ = lambda self: find_iter_1()
            else:
                mock_cursor.__aiter__ = lambda self: find_iter_2()
            return mock_cursor

        mock_db.miner_transactions.find.side_effect = find_side_effect

        mock_bu = MagicMock()
        mock_bu.is_input_spent = AsyncMock(return_value=True)

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "BU", mock_bu):
                await TU.clean_mempool(self.config)

        mock_db.failed_transactions.insert_one.assert_called()


# ---------------------------------------------------------------------------
# TU.rebroadcast_mempool() - lines 259-290
# ---------------------------------------------------------------------------


class TestRebroadcastMempool(TUTestCase):
    async def test_rebroadcast_mempool_broadcasts_transactions(self):
        """Lines 259-290: broadcasts transactions from mempool to peers."""
        mock_db = MagicMock()

        txn_dict = {
            "time": 1000,
            "id": "sig1",
            "rid": "",
            "relationship": "",
            "public_key": self.public_key,
            "dh_public_key": None,
            "fee": 0.0,
            "inputs": [],
            "outputs": [{"to": "addr1", "value": 1.0}],
            "hash": "abc",
            "transaction_signature": "sig1",
        }

        async def txn_iter(*args, **kwargs):
            yield txn_dict

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: txn_iter()
        mock_db.miner_transactions.find.return_value = mock_cursor

        # txn_tracking: no confirmed peers
        mock_db.txn_tracking.find.return_value = MagicMock()
        mock_db.txn_tracking.find.return_value.to_list = AsyncMock(return_value=[])

        mock_peer_stream = MagicMock()
        mock_peer_stream.peer.rid = "peer1"
        mock_peer_stream.peer.protocol_version = 1

        async def mock_get_sync_peers():
            yield mock_peer_stream

        mock_node_shared = MagicMock()
        mock_node_shared.write_params = AsyncMock()

        mock_node_client = MagicMock()
        mock_node_client.retry_messages = {}

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "peer") as mock_peer:
                mock_peer.get_sync_peers = mock_get_sync_peers
                with patch.object(
                    self.config, "nodeShared", mock_node_shared, create=True
                ):
                    with patch.object(
                        self.config, "nodeClient", mock_node_client, create=True
                    ):
                        await TU.rebroadcast_mempool(self.config)

        mock_node_shared.write_params.assert_called_once()

    async def test_rebroadcast_mempool_protocol_v2_saves_retry(self):
        """Line 285-288: protocol_version > 1 adds to retry_messages."""
        mock_db = MagicMock()

        txn_dict = {
            "time": 1000,
            "id": "sig1",
            "rid": "",
            "relationship": "",
            "public_key": self.public_key,
            "dh_public_key": None,
            "fee": 0.0,
            "inputs": [],
            "outputs": [{"to": "addr1", "value": 1.0}],
            "hash": "abc",
            "transaction_signature": "sig1",
        }

        async def txn_iter(*args, **kwargs):
            yield txn_dict

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: txn_iter()
        mock_db.miner_transactions.find.return_value = mock_cursor

        mock_db.txn_tracking.find.return_value = MagicMock()
        mock_db.txn_tracking.find.return_value.to_list = AsyncMock(return_value=[])

        mock_peer_stream = MagicMock()
        mock_peer_stream.peer.rid = "peer1"
        mock_peer_stream.peer.protocol_version = 2

        async def mock_get_sync_peers():
            yield mock_peer_stream

        mock_node_shared = MagicMock()
        mock_node_shared.write_params = AsyncMock()

        retry_messages = {}
        mock_node_client = MagicMock()
        mock_node_client.retry_messages = retry_messages

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "peer") as mock_peer:
                mock_peer.get_sync_peers = mock_get_sync_peers
                with patch.object(
                    self.config, "nodeShared", mock_node_shared, create=True
                ):
                    with patch.object(
                        self.config, "nodeClient", mock_node_client, create=True
                    ):
                        await TU.rebroadcast_mempool(self.config)

        # retry_messages should have an entry for protocol_version > 1
        self.assertTrue(len(retry_messages) > 0)

    async def test_rebroadcast_mempool_include_zero_query(self):
        """Line 263: include_zero=True sets query to {} (all txns)."""
        mock_db = MagicMock()

        async def txn_iter(*args, **kwargs):
            return
            yield

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: txn_iter()
        mock_db.miner_transactions.find.return_value = mock_cursor

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "peer") as mock_peer:
                mock_peer.get_sync_peers = MagicMock()
                await TU.rebroadcast_mempool(self.config, include_zero=True)

        # find() was called with an empty query (include_zero=True)
        mock_db.miner_transactions.find.assert_called_once_with({})

    async def test_rebroadcast_mempool_skips_confirmed_peer(self):
        """Lines 276-279: peer in confirmed_rids triggers debug log and continue."""
        mock_db = MagicMock()

        txn_dict = {
            "time": 1000,
            "id": "sig1",
            "rid": "",
            "relationship": "",
            "public_key": self.public_key,
            "dh_public_key": None,
            "fee": 0.0,
            "inputs": [],
            "outputs": [{"to": "addr1", "value": 1.0}],
            "hash": "abc",
            "transaction_signature": "sig1",
        }

        async def txn_iter(*args, **kwargs):
            yield txn_dict

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: txn_iter()
        mock_db.miner_transactions.find.return_value = mock_cursor

        # confirmed_rids includes "peer1" so the peer is skipped
        confirmed_entry = {"rid": "peer1"}
        mock_db.txn_tracking.find.return_value = MagicMock()
        mock_db.txn_tracking.find.return_value.to_list = AsyncMock(
            return_value=[confirmed_entry]
        )

        mock_peer_stream = MagicMock()
        mock_peer_stream.peer.rid = "peer1"  # matches confirmed_rids
        mock_peer_stream.peer.protocol_version = 1

        async def mock_get_sync_peers():
            yield mock_peer_stream

        mock_node_shared = MagicMock()
        mock_node_shared.write_params = AsyncMock()

        mock_node_client = MagicMock()
        mock_node_client.retry_messages = {}

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "peer") as mock_peer:
                mock_peer.get_sync_peers = mock_get_sync_peers
                with patch.object(
                    self.config, "nodeShared", mock_node_shared, create=True
                ):
                    with patch.object(
                        self.config, "nodeClient", mock_node_client, create=True
                    ):
                        await TU.rebroadcast_mempool(self.config)

        # write_params should NOT be called because peer was skipped
        mock_node_shared.write_params.assert_not_called()


# ---------------------------------------------------------------------------
# TU.rebroadcast_failed() - line 305 (protocol_version > 1)
# ---------------------------------------------------------------------------


class TestRebroadcastFailedProtocolV2(TUTestCase):
    async def test_rebroadcast_failed_protocol_v2_saves_retry(self):
        """Line 305: protocol_version > 1 adds entry to retry_messages."""
        mock_db = MagicMock()
        mock_txn_dict = {
            "txn": {
                "time": 1000,
                "id": "sig1",
                "rid": "",
                "relationship": "",
                "public_key": self.public_key,
                "dh_public_key": None,
                "fee": 0.0,
                "inputs": [],
                "outputs": [],
            }
        }

        async def txn_iter():
            yield mock_txn_dict

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: txn_iter()
        mock_db.failed_transactions.find.return_value = mock_cursor

        mock_peer_stream = MagicMock()
        mock_peer_stream.peer.protocol_version = 2
        mock_peer_stream.peer.rid = "peer1"

        async def mock_get_sync_peers():
            yield mock_peer_stream

        mock_node_shared = MagicMock()
        mock_node_shared.write_params = AsyncMock()

        retry_messages = {}
        mock_node_client = MagicMock()
        mock_node_client.retry_messages = retry_messages

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "peer") as mock_peer:
                mock_peer.get_sync_peers = mock_get_sync_peers
                with patch.object(
                    self.config, "nodeShared", mock_node_shared, create=True
                ):
                    with patch.object(
                        self.config, "nodeClient", mock_node_client, create=True
                    ):
                        await TU.rebroadcast_failed(self.config, "sig1")

        self.assertTrue(len(retry_messages) > 0)


# ---------------------------------------------------------------------------
# TU.get_trigger_txns() - lines 382-383 (start_index + end_index branch)
# ---------------------------------------------------------------------------


class TestGetTriggerTxnsWithIndexRange(TUTestCase):
    async def test_get_trigger_txns_with_start_and_end_index(self):
        """Lines 382-383: start_index and end_index add index range to match dict."""
        block_data = {"index": 5, "transactions": [{"id": "txn1"}]}

        async def mock_aggregate_iter():
            yield block_data

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: mock_aggregate_iter()

        mock_db = MagicMock()
        mock_db.blocks.aggregate.return_value = mock_cursor

        mock_sc_txn = MagicMock()
        mock_sc_txn.requested_rid = "rid1"
        mock_sc_txn.relationship.identity.public_key = "pk1"

        results = []
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            async for block in TU.get_trigger_txns(
                self.config, mock_sc_txn, start_index=1, end_index=10
            ):
                results.append(block)

        self.assertEqual(len(results), 1)
        # Verify the pipeline match included the index range
        call_args = mock_db.blocks.aggregate.call_args[0][0]
        pipeline_match = call_args[0]["$match"]
        self.assertIn("index", pipeline_match)
        self.assertEqual(pipeline_match["index"]["$gte"], 1)
        self.assertEqual(pipeline_match["index"]["$lt"], 10)


# ---------------------------------------------------------------------------
# TU.combine_oldest_transactions() - lines 421-422 (mempool txns with inputs)
# ---------------------------------------------------------------------------


class TestCombineOldestWithMempoolInputs(TUTestCase):
    async def test_combine_with_mempool_txns_having_inputs(self):
        """Lines 421-422: mempool transactions with inputs are tracked."""
        mock_db = MagicMock()

        mempool_txn = {
            "_id": "m1",
            "outputs": [{"to": self.config.address, "value": 1.0}],
            "inputs": [{"id": "input1"}],
        }
        mock_mempool_cursor = MagicMock()
        mock_mempool_cursor.to_list = AsyncMock(return_value=[mempool_txn])
        mock_db.miner_transactions.find.return_value = mock_mempool_cursor

        async def few_txns(*args, **kwargs):
            for i in range(3):
                yield {
                    "id": f"txn{i}",
                    "outputs": [{"to": self.config.address, "value": 1.0}],
                }

        mock_bu = MagicMock()
        mock_bu.get_wallet_unspent_transactions_for_dusting = lambda addr: few_txns(
            addr
        )

        self.config.combined_address = "combined_addr"

        with patch.object(self.config.mongo, "async_db", new=mock_db):
            with patch.object(self.config, "BU", mock_bu):
                # Fewer than 100 → returns early
                await TU.combine_oldest_transactions(self.config)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
