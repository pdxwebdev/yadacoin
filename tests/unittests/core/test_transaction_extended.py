"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import hashlib
import time
import unittest
from logging import getLogger
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.config import Config
from yadacoin.core.keyrotation import NodeKeyRotationManager
from yadacoin.core.transaction import (
    Input,
    InvalidTransactionSignatureException,
    MaxRelationshipSizeExceeded,
    NotEnoughMoneyException,
    Output,
    Relationship,
    TooManyInputsException,
    Transaction,
    TransactionConsts,
    equal,
)

from ..test_setup import AsyncTestCase


class TransactionTestCase(AsyncTestCase):
    """Base class: ensures app_log and sets up common config."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        config = Config()
        if not hasattr(config, "app_log"):
            config.app_log = getLogger("tornado.application")
        self.config = config
        self.public_key = config.public_key
        self.private_key = config.private_key


# ---------------------------------------------------------------------------
# Input, Output, Relationship
# ---------------------------------------------------------------------------


class TestInput(unittest.TestCase):
    def test_init(self):
        inp = Input(signature="abc123")
        self.assertEqual(inp.id, "abc123")
        self.assertIsNone(inp.input_txn)

    def test_init_with_input_txn(self):
        mock_txn = MagicMock()
        inp = Input(signature="sig1", input_txn=mock_txn)
        self.assertEqual(inp.input_txn, mock_txn)

    def test_from_dict(self):
        inp = Input.from_dict({"id": "mysig", "input_txn": None})
        self.assertEqual(inp.id, "mysig")

    def test_from_dict_missing_id(self):
        inp = Input.from_dict({})
        self.assertEqual(inp.id, "")

    def test_to_dict(self):
        inp = Input(signature="abc123")
        d = inp.to_dict()
        self.assertEqual(d, {"id": "abc123"})


class TestOutput(unittest.TestCase):
    def test_init(self):
        out = Output(to="addr1", value=10.5)
        self.assertEqual(out.to, "addr1")
        self.assertEqual(out.value, 10.5)

    def test_from_dict(self):
        out = Output.from_dict({"to": "myaddr", "value": 5.0})
        self.assertEqual(out.to, "myaddr")
        self.assertEqual(out.value, 5.0)

    def test_from_dict_defaults(self):
        out = Output.from_dict({})
        self.assertEqual(out.to, "")
        self.assertEqual(out.value, "")

    def test_to_dict(self):
        out = Output(to="addr1", value=2.5)
        self.assertEqual(out.to_dict(), {"to": "addr1", "value": 2.5})


class TestRelationship(unittest.TestCase):
    def test_to_dict(self):
        rel = Relationship(
            dh_private_key="dh1",
            their_username_signature="sig1",
            their_username="user1",
            my_username_signature="sig2",
            my_username="user2",
        )
        d = rel.to_dict()
        self.assertEqual(d["dh_private_key"], "dh1")
        self.assertEqual(d["their_username"], "user1")
        self.assertIn("my_public_key", d)

    def test_to_json(self):
        rel = Relationship()
        j = rel.to_json()
        self.assertIsInstance(j, str)
        self.assertIn("{", j)


# ---------------------------------------------------------------------------
# Transaction.__init__ edge cases
# ---------------------------------------------------------------------------


class TestTransactionInit(TransactionTestCase):
    async def test_init_empty(self):
        txn = Transaction()
        self.assertIsInstance(txn, Transaction)

    async def test_init_node_announcement_dict(self):
        """Test that relationship dict with 'node' key → NodeAnnouncement instance."""
        from unittest.mock import MagicMock, patch

        from yadacoin.core.nodeannouncement import NodeAnnouncement as NA

        node_data = {"host": "127.0.0.1", "port": 8000}
        mock_na = MagicMock(spec=NA)
        with patch.object(NA, "from_dict", return_value=mock_na) as mock_from_dict:
            txn = Transaction(
                public_key=self.public_key,
                relationship={"node": node_data},
                inputs=[],
                outputs=[],
            )
            mock_from_dict.assert_called_once_with(node_data)
        self.assertIs(txn.relationship, mock_na)

    async def test_init_oversized_string_relationship_raises(self):
        oversized = "x" * (TransactionConsts.RELATIONSHIP_MAX_SIZE.value + 1)
        with self.assertRaises(MaxRelationshipSizeExceeded):
            Transaction(
                public_key=self.public_key,
                relationship=oversized,
                inputs=[],
                outputs=[],
            )

    async def test_init_outputs_from_dicts(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[{"to": "addr1", "value": 1.0}],
        )
        self.assertEqual(len(txn.outputs), 1)
        self.assertIsInstance(txn.outputs[0], Output)

    async def test_init_outputs_from_instances(self):
        out = Output(to="addr1", value=1.0)
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[out],
        )
        self.assertIs(txn.outputs[0], out)

    async def test_init_inputs_from_dicts(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[{"id": "txnsig1"}],
            outputs=[],
        )
        self.assertEqual(len(txn.inputs), 1)
        self.assertIsInstance(txn.inputs[0], Input)

    async def test_init_version_set_from_time(self):
        txn = Transaction(txn_time=int(time.time()))
        self.assertEqual(txn.version, 2)

    async def test_init_version_explicit(self):
        txn = Transaction(version=7, txn_time=int(time.time()))
        self.assertEqual(txn.version, 7)

    async def test_init_negative_fee_raises(self):
        from yadacoin.core.transaction import InvalidTransactionException

        with self.assertRaises(InvalidTransactionException):
            Transaction(fee=-0.01)

    async def test_init_negative_masternode_fee_raises(self):
        from yadacoin.core.transaction import InvalidTransactionException

        with self.assertRaises(InvalidTransactionException):
            Transaction(masternode_fee=-0.01)


# ---------------------------------------------------------------------------
# Transaction.from_dict and ensure_instance
# ---------------------------------------------------------------------------


class TestTransactionFromDict(TransactionTestCase):
    async def test_from_dict_returns_transaction(self):
        d = {
            "time": int(time.time()),
            "id": "sig1",
            "rid": "",
            "relationship": "",
            "public_key": self.public_key,
            "dh_public_key": None,
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "",
            "inputs": [],
            "outputs": [],
            "coinbase": False,
            "version": 2,
        }
        txn = Transaction.from_dict(d)
        self.assertIsInstance(txn, Transaction)
        self.assertEqual(txn.public_key, self.public_key)

    async def test_ensure_instance_with_transaction(self):
        txn = Transaction()
        result = Transaction.ensure_instance(txn)
        self.assertIs(result, txn)

    async def test_ensure_instance_with_dict(self):
        d = {
            "time": int(time.time()),
            "id": "sig1",
            "rid": "",
            "relationship": "",
            "public_key": self.public_key,
            "dh_public_key": None,
            "fee": 0.0,
            "inputs": [],
            "outputs": [],
        }
        result = Transaction.ensure_instance(d)
        self.assertIsInstance(result, Transaction)


# ---------------------------------------------------------------------------
# Transaction.in_the_future
# ---------------------------------------------------------------------------


class TestTransactionInTheFuture(TransactionTestCase):
    async def test_not_in_the_future(self):
        txn = Transaction(txn_time=int(time.time()) - 100)
        self.assertFalse(txn.in_the_future())

    async def test_in_the_future(self):
        txn = Transaction(txn_time=int(time.time()) + 99999)
        self.assertTrue(txn.in_the_future())


# ---------------------------------------------------------------------------
# Transaction.are_kel_fields_populated
# ---------------------------------------------------------------------------


class TestAreKelFieldsPopulated(TransactionTestCase):
    async def test_empty_returns_false(self):
        txn = Transaction(public_key=self.public_key, inputs=[], outputs=[])
        self.assertFalse(txn.are_kel_fields_populated())

    async def test_twice_prerotated_key_hash_returns_true(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            twice_prerotated_key_hash="abc",
        )
        self.assertTrue(txn.are_kel_fields_populated())

    async def test_prerotated_key_hash_returns_true(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            prerotated_key_hash="abc",
        )
        self.assertTrue(txn.are_kel_fields_populated())

    async def test_public_key_hash_returns_true(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            public_key_hash="abc",
        )
        self.assertTrue(txn.are_kel_fields_populated())

    async def test_prev_public_key_hash_returns_true(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            prev_public_key_hash="abc",
        )
        self.assertTrue(txn.are_kel_fields_populated())


# ---------------------------------------------------------------------------
# Transaction.get_output_hashes
# ---------------------------------------------------------------------------


class TestGetOutputHashes(TransactionTestCase):
    async def test_empty_outputs(self):
        txn = Transaction(public_key=self.public_key, inputs=[], outputs=[])
        result = txn.get_output_hashes()
        self.assertEqual(result, "")

    async def test_single_output(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[Output(to="addr1", value=1.0)],
        )
        result = txn.get_output_hashes()
        self.assertIn("addr1", result)
        self.assertIn("1.00000000", result)

    async def test_outputs_sorted_by_to(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[
                Output(to="zzz_addr", value=1.0),
                Output(to="aaa_addr", value=2.0),
            ],
        )
        result = txn.get_output_hashes()
        self.assertTrue(result.startswith("aaa_addr"))


# ---------------------------------------------------------------------------
# Transaction.generate_hash - all versions
# ---------------------------------------------------------------------------


class TestGenerateHash(TransactionTestCase):
    def _make_txn(self, version, relationship="", relationship_hash=""):
        txn = Transaction(
            txn_time=1000000,
            public_key=self.public_key,
            relationship=relationship,
            relationship_hash=relationship_hash,
            inputs=[],
            outputs=[],
            version=version,
            dh_public_key="" if not hasattr(self, "_dh_pk") else self._dh_pk,
        )
        txn.fee = 0.0
        txn.masternode_fee = 0.0
        txn.rid = ""
        txn.requester_rid = ""
        txn.requested_rid = ""
        txn.dh_public_key = ""
        txn.prerotated_key_hash = ""
        txn.twice_prerotated_key_hash = ""
        txn.public_key_hash = ""
        txn.prev_public_key_hash = ""
        return txn

    async def test_generate_hash_version2(self):
        txn = self._make_txn(version=2)
        h = await txn.generate_hash()
        self.assertEqual(len(h), 64)
        self.assertIsInstance(h, str)

    async def test_generate_hash_version3(self):
        txn = self._make_txn(version=3)
        h = await txn.generate_hash()
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version4(self):
        txn = self._make_txn(version=4)
        h = await txn.generate_hash()
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version5(self):
        rh = hashlib.sha256(b"test").digest().hex()
        txn = self._make_txn(version=5, relationship_hash=rh)
        h = await txn.generate_hash()
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version6(self):
        rh = hashlib.sha256(b"test").digest().hex()
        txn = self._make_txn(version=6, relationship_hash=rh)
        h = await txn.generate_hash()
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version7(self):
        rh = hashlib.sha256(b"test").digest().hex()
        txn = self._make_txn(version=7, relationship_hash=rh)
        h = await txn.generate_hash()
        self.assertEqual(len(h), 64)

    async def test_generate_hash_v1_fallback(self):
        txn = self._make_txn(version=1)
        txn.relationship = ""
        h = await txn.generate_hash()
        self.assertEqual(len(h), 64)

    async def test_generate_hash_is_deterministic(self):
        txn = self._make_txn(version=2)
        h1 = await txn.generate_hash()
        h2 = await txn.generate_hash()
        self.assertEqual(h1, h2)

    async def test_generate_hash_v7_with_relationship_invalid_hash_raises(self):
        from yadacoin.core.transaction import InvalidRelationshipHashException

        txn = self._make_txn(
            version=7, relationship="myrelationship", relationship_hash="wrong_hash"
        )
        with self.assertRaises(InvalidRelationshipHashException):
            await txn.generate_hash()


# ---------------------------------------------------------------------------
# Transaction.get_input_hashes
# ---------------------------------------------------------------------------


class TestGetInputHashes(TransactionTestCase):
    async def test_empty_inputs(self):
        txn = Transaction(public_key=self.public_key, inputs=[], outputs=[])
        result = await txn.get_input_hashes()
        self.assertEqual(result, "")

    async def test_single_input(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[Input(signature="abc123")],
            outputs=[],
        )
        result = await txn.get_input_hashes()
        self.assertEqual(result, "abc123")

    async def test_multiple_inputs_sorted(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[Input(signature="zzz"), Input(signature="aaa")],
            outputs=[],
        )
        result = await txn.get_input_hashes()
        self.assertEqual(result, "aaazzz")


# ---------------------------------------------------------------------------
# Transaction.do_money()
# ---------------------------------------------------------------------------


class TestDoMoney(TransactionTestCase):
    async def test_coinbase_clears_inputs(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[Input("inp1")],
            outputs=[],
        )
        txn.coinbase = True
        txn.fee = 0.0
        txn.outputs = []
        txn.inputs = [Input("inp1")]
        # Calls do_money but sets coinbase=True first
        await txn.do_money()
        self.assertEqual(txn.inputs, [])

    async def test_zero_outputs_and_fee_returns_early(self):
        txn = Transaction(public_key=self.public_key, inputs=[], outputs=[])
        txn.coinbase = False
        txn.fee = 0.0
        txn.outputs = []
        # Should return without error - no inputs needed when total=0
        await txn.do_money()
        self.assertEqual(txn.inputs, [])

    async def test_do_money_remainder_added_to_existing_output(self):
        """When my_address is already an output, remainder is added to it."""
        from bitcoin.wallet import P2PKHBitcoinAddress

        my_address = str(
            P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key))
        )
        input_value = 5.0
        output_value = 3.0

        txn = Transaction(public_key=self.public_key, inputs=[], outputs=[])
        txn.coinbase = False
        txn.fee = 0.0
        txn.masternode_fee = 0.0
        txn.outputs = [Output(to=my_address, value=output_value)]
        txn.inputs = []

        # Mock generate_inputs to return input_sum = 5.0
        async def mock_generate_inputs(input_sum, my_address, inputs, total):
            inputs.append(Input("input_id"))
            return input_value

        txn.generate_inputs = mock_generate_inputs
        await txn.do_money()

        # my_address output should have had remainder (5-3=2) added
        my_output = next(o for o in txn.outputs if o.to == my_address)
        self.assertAlmostEqual(my_output.value, 5.0, places=7)

    async def test_do_money_remainder_new_output_when_not_found(self):
        """When my_address is NOT in outputs, a new output is added."""
        from bitcoin.wallet import P2PKHBitcoinAddress

        my_address = str(
            P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key))
        )
        other_address = "1SomeOtherAddress"
        input_value = 5.0
        output_value = 3.0

        txn = Transaction(public_key=self.public_key, inputs=[], outputs=[])
        txn.coinbase = False
        txn.fee = 0.0
        txn.masternode_fee = 0.0
        txn.outputs = [Output(to=other_address, value=output_value)]
        txn.inputs = []

        async def mock_generate_inputs(input_sum, addr, inputs, total):
            inputs.append(Input("input_id"))
            return input_value

        txn.generate_inputs = mock_generate_inputs
        await txn.do_money()

        # A new output for my_address should have been appended
        my_outputs = [o for o in txn.outputs if o.to == my_address]
        self.assertEqual(len(my_outputs), 1)
        self.assertAlmostEqual(my_outputs[0].value, 2.0, places=7)

    async def test_do_money_no_inputs_raises_not_enough_money(self):
        """generate_inputs returns without appending to `inputs` → self.inputs
        stays empty → NotEnoughMoneyException raised (not coinbase, total > 0)."""
        txn = Transaction(public_key=self.public_key, inputs=[], outputs=[])
        txn.coinbase = False
        txn.fee = 0.0
        txn.masternode_fee = 0.0
        txn.outputs = [Output(to="1SomeOtherAddress", value=3.0)]
        txn.inputs = []

        async def mock_generate_inputs(input_sum, addr, inputs, total):
            # Does not append anything to `inputs`, simulating a helper that
            # returns a sum without ever finding a spendable input.
            return 0.0

        txn.generate_inputs = mock_generate_inputs
        with self.assertRaises(NotEnoughMoneyException):
            await txn.do_money()


# ---------------------------------------------------------------------------
# Transaction.is_already_onchain / is_already_in_mempool
# ---------------------------------------------------------------------------


class TestIsAlreadyOnchain(TransactionTestCase):
    async def test_no_kel_fields_returns_false(self):
        txn = Transaction(public_key=self.public_key, inputs=[], outputs=[])
        result = await txn.is_already_onchain()
        self.assertFalse(result)

    async def test_with_prerotated_key_hash_no_result_returns_false(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            prerotated_key_hash="somehash",
        )
        mock_db = MagicMock()

        async def _empty(*a, **k):
            if False:
                yield None

        mock_db.blocks.find = MagicMock(side_effect=_empty)
        with patch.object(txn.config.mongo, "async_db", new=mock_db):
            result = await txn.is_already_onchain()
        self.assertFalse(result)

    async def test_with_prerotated_key_hash_found_returns_true(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            prerotated_key_hash="somehash",
        )
        mock_db = MagicMock()

        async def _find(*a, **k):
            yield {
                "index": 1,
                "transactions": [{"id": "other", "prerotated_key_hash": "somehash"}],
            }

        mock_db.blocks.find = MagicMock(side_effect=_find)
        with patch.object(txn.config.mongo, "async_db", new=mock_db):
            result = await txn.is_already_onchain()
        self.assertTrue(result)

    async def test_with_block_index_adds_index_filter(self):
        """block_index provided → query includes an index '$lt' filter."""
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            prerotated_key_hash="somehash",
        )
        captured_queries = []

        async def mock_find(query, *a, **k):
            captured_queries.append(query)
            if False:
                yield None

        mock_db = MagicMock()
        mock_db.blocks.find = MagicMock(side_effect=mock_find)
        with patch.object(txn.config.mongo, "async_db", new=mock_db):
            result = await txn.is_already_onchain(block_index=100)
        self.assertFalse(result)
        self.assertIn("index", captured_queries[0])
        self.assertEqual(captured_queries[0]["index"], {"$lt": 100})

    async def test_skips_fork_replaced_height(self):
        """Local KEL at a height covered by extra_blocks must not count."""
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            prerotated_key_hash="somehash",
            transaction_signature="inbound_sig",
        )
        mock_db = MagicMock()

        async def _find(*a, **k):
            yield {
                "index": 100,
                "transactions": [
                    {"id": "local_sig", "prerotated_key_hash": "somehash"}
                ],
            }

        mock_db.blocks.find = MagicMock(side_effect=_find)
        eb = MagicMock()
        eb.index = 100
        with patch.object(txn.config.mongo, "async_db", new=mock_db):
            result = await txn.is_already_onchain(block_index=101, extra_blocks=[eb])
        self.assertFalse(result)

    async def test_same_id_revalidation_not_already_onchain(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            prerotated_key_hash="somehash",
            transaction_signature="same_sig",
        )
        mock_db = MagicMock()

        async def _find(*a, **k):
            yield {
                "index": 50,
                "transactions": [{"id": "same_sig", "prerotated_key_hash": "somehash"}],
            }

        mock_db.blocks.find = MagicMock(side_effect=_find)
        with patch.object(txn.config.mongo, "async_db", new=mock_db):
            result = await txn.is_already_onchain(block_index=100)
        self.assertFalse(result)


class TestIsAlreadyInMempool(TransactionTestCase):
    async def test_no_kel_fields_returns_false(self):
        txn = Transaction(public_key=self.public_key, inputs=[], outputs=[])
        result = await txn.is_already_in_mempool()
        self.assertFalse(result)

    async def test_with_public_key_hash_not_found_returns_false(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            public_key_hash="some_hash",
        )
        mock_db = MagicMock()
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        with patch.object(txn.config.mongo, "async_db", new=mock_db):
            result = await txn.is_already_in_mempool()
        self.assertFalse(result)

    async def test_with_public_key_hash_found_returns_true(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            public_key_hash="some_hash",
        )
        mock_db = MagicMock()
        mock_db.miner_transactions.find_one = AsyncMock(return_value={"id": "txn1"})
        with patch.object(txn.config.mongo, "async_db", new=mock_db):
            result = await txn.is_already_in_mempool()
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# Transaction.handle_exception
# ---------------------------------------------------------------------------


class TestHandleException(TransactionTestCase):
    async def test_handle_exception_too_many_inputs(self):
        txn = Transaction(public_key=self.public_key, inputs=[Input("i1")], outputs=[])
        mock_db = MagicMock()
        mock_db.failed_transactions.insert_one = AsyncMock()
        mock_db.miner_transactions.delete_many = AsyncMock()

        with patch.object(txn.config.mongo, "async_db", new=mock_db):
            e = TooManyInputsException("too many")
            await Transaction.handle_exception(e, txn)

        # TooManyInputsException should clear inputs
        self.assertEqual(txn.inputs, [])

    async def test_handle_exception_regular_exception(self):
        txn = Transaction(public_key=self.public_key, inputs=[], outputs=[])
        mock_db = MagicMock()
        mock_db.failed_transactions.insert_one = AsyncMock()
        mock_db.miner_transactions.delete_many = AsyncMock()

        with patch.object(txn.config.mongo, "async_db", new=mock_db):
            e = NotEnoughMoneyException("not enough")
            await Transaction.handle_exception(e, txn, transactions=[])
        # Should not raise


# ---------------------------------------------------------------------------
# Transaction.generate (with coinbase=True - skips do_money)
# ---------------------------------------------------------------------------


class TestTransactionGenerate(TransactionTestCase):
    async def test_generate_coinbase(self):
        txn = await Transaction.generate(
            public_key=self.public_key,
            private_key=self.private_key,
            coinbase=True,
            outputs=[Output(to="addr1", value=50.0)],
            inputs=[],
            version=2,
        )
        self.assertIsInstance(txn, Transaction)
        self.assertTrue(txn.coinbase)
        self.assertEqual(txn.inputs, [])

    async def test_generate_with_relationship(self):
        txn = await Transaction.generate(
            public_key=self.public_key,
            private_key=self.private_key,
            coinbase=True,
            relationship="test_relationship",
            outputs=[],
            inputs=[],
            version=2,
        )
        self.assertEqual(txn.relationship, "test_relationship")
        self.assertNotEqual(txn.relationship_hash, "")

    async def test_generate_with_no_private_key(self):
        txn = await Transaction.generate(
            public_key=self.public_key,
            private_key="",
            coinbase=True,
            outputs=[],
            inputs=[],
            version=2,
        )
        self.assertEqual(txn.transaction_signature, "")

    async def test_generate_version7_with_outputs(self):
        txn = await Transaction.generate(
            public_key=self.public_key,
            private_key=self.private_key,
            coinbase=True,
            outputs=[Output(to="someaddr", value=10.0)],
            inputs=[],
            version=7,
        )
        self.assertEqual(txn.version, 7)
        self.assertIsInstance(txn, Transaction)


# ---------------------------------------------------------------------------
# Transaction.to_dict
# ---------------------------------------------------------------------------


class TestTransactionToDict(TransactionTestCase):
    async def test_to_dict_basic_fields(self):
        txn = await Transaction.generate(
            public_key=self.public_key,
            private_key=self.private_key,
            coinbase=True,
            outputs=[],
            inputs=[],
            version=2,
        )
        d = txn.to_dict()
        self.assertIn("time", d)
        self.assertIn("rid", d)
        self.assertIn("id", d)
        self.assertIn("relationship", d)
        self.assertIn("public_key", d)
        self.assertIn("fee", d)
        self.assertIn("hash", d)
        self.assertIn("inputs", d)
        self.assertIn("outputs", d)
        self.assertIn("version", d)

    async def test_to_dict_coinbase_not_in_dict(self):
        """coinbase is an instance attribute but NOT included in to_dict() output."""
        txn = await Transaction.generate(
            public_key=self.public_key,
            private_key=self.private_key,
            coinbase=True,
            outputs=[],
            inputs=[],
        )
        self.assertTrue(txn.coinbase)
        d = txn.to_dict()
        # coinbase is intentionally not serialized in to_dict()
        self.assertNotIn("coinbase", d)
        # But a roundtrip via from_dict gives coinbase=False (default)
        txn2 = Transaction.from_dict(d)
        self.assertFalse(txn2.coinbase)

    async def test_to_dict_prerotated_key_hash(self):
        txn = await Transaction.generate(
            public_key=self.public_key,
            private_key=self.private_key,
            coinbase=True,
            outputs=[],
            inputs=[],
            prerotated_key_hash="pkhash123",
        )
        d = txn.to_dict()
        self.assertEqual(d["prerotated_key_hash"], "pkhash123")


# ---------------------------------------------------------------------------
# Transaction.contract_generated property
# ---------------------------------------------------------------------------


class TestContractGeneratedProperty(TransactionTestCase):
    async def test_contract_generated_setter_and_getter(self):
        txn = Transaction(public_key=self.public_key, inputs=[], outputs=[])
        txn.contract_generated = True
        result = await txn.contract_generated
        self.assertTrue(result)

    async def test_contract_generated_none_checks_db(self):
        txn = Transaction(public_key=self.public_key, inputs=[], outputs=[])
        txn._contract_generated = None
        mock_db = MagicMock()
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        with patch.object(txn.config.mongo, "async_db", new=mock_db):
            result = await txn.contract_generated
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Transaction.verify_signature
# ---------------------------------------------------------------------------


class TestVerifySignature(TransactionTestCase):
    async def test_verify_signature_invalid_raises(self):
        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            transaction_signature="invalidsig==",
        )
        txn.hash = "0" * 64
        from bitcoin.wallet import P2PKHBitcoinAddress

        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))
        with self.assertRaises(InvalidTransactionSignatureException):
            txn.verify_signature(address)


# ---------------------------------------------------------------------------
# Transaction.equal helper
# ---------------------------------------------------------------------------


class TestEqual(unittest.TestCase):
    def test_equal_close_values(self):
        self.assertTrue(equal(1.0, 1.0 + 1e-10))

    def test_equal_different_values(self):
        self.assertFalse(equal(1.0, 2.0))

    def test_equal_exact(self):
        self.assertTrue(equal(0.0, 0.0))


# ---------------------------------------------------------------------------
# Coverage gap tests: Transaction.__init__ relationship parsing branches
# ---------------------------------------------------------------------------


class TestTransactionInitRelationshipParsing(TransactionTestCase):
    """Cover Transaction.__init__ branches for RecoveryTransition and CredentialReceipt."""

    async def test_init_recovery_transition_relationship(self):
        """Lines 172-177: dict with both 'recovers' and 'recovery' → RecoveryTransition."""
        from yadacoin.core.recoveryannouncement import RecoveryTransition

        txn = Transaction(
            public_key=self.public_key,
            relationship={
                "recovers": {"commitment": "aabb", "R": "ccdd", "s": "eeff"},
                "recovery": {"witness_hash": "11223344"},
            },
            inputs=[],
            outputs=[],
        )
        self.assertIsInstance(txn.relationship, RecoveryTransition)

    async def test_init_recovery_announcement_only_relationship(self):
        """Line 223: dict with only 'recovery' key → RecoveryAnnouncement."""
        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        txn = Transaction(
            public_key=self.public_key,
            relationship={"recovery": "11223344"},
            inputs=[],
            outputs=[],
        )
        self.assertIsInstance(txn.relationship, RecoveryAnnouncement)
        self.assertEqual(txn.relationship.witness_hash, "11223344")

    async def test_init_recovery_proof_only_relationship(self):
        """Line 233: dict with only 'recovers' key → RecoveryProof."""
        from yadacoin.core.recoveryannouncement import RecoveryProof

        txn = Transaction(
            public_key=self.public_key,
            relationship={"recovers": {"commitment": "aabb", "R": "ccdd", "s": "eeff"}},
            inputs=[],
            outputs=[],
        )
        self.assertIsInstance(txn.relationship, RecoveryProof)
        self.assertEqual(txn.relationship.commitment, "aabb")

    async def test_init_credential_receipt_relationship(self):
        """Lines 209-214: dict with 'credential_receipt' key → CredentialReceipt."""
        from yadacoin.core.credentialreceipt import CredentialReceipt

        txn = Transaction(
            public_key=self.public_key,
            relationship={
                "credential_receipt": {
                    "lookup_key": "aabbccdd",
                    "iv": "eeff0011",
                    "ct": "base64ct==",
                }
            },
            inputs=[],
            outputs=[],
        )
        self.assertIsInstance(txn.relationship, CredentialReceipt)


# ---------------------------------------------------------------------------
# Coverage gap tests: Transaction.generate_hash recovery/credential branches
# ---------------------------------------------------------------------------


class TestGenerateHashRecoveryCredential(TransactionTestCase):
    """Cover generate_hash lines 853 and 855 for Recovery* and CredentialReceipt."""

    def _make_v7_txn(self, relationship_str):
        """Create a version-7 transaction with pre-computed relationship_hash."""
        rh = hashlib.sha256(relationship_str.encode()).digest().hex()
        txn = Transaction(
            txn_time=1000000,
            public_key=self.public_key,
            relationship="",
            relationship_hash=rh,
            inputs=[],
            outputs=[],
            version=7,
        )
        txn.fee = 0.0
        txn.masternode_fee = 0.0
        txn.rid = ""
        txn.requester_rid = ""
        txn.requested_rid = ""
        txn.dh_public_key = ""
        txn.prerotated_key_hash = ""
        txn.twice_prerotated_key_hash = ""
        txn.public_key_hash = ""
        txn.prev_public_key_hash = ""
        return txn, rh

    async def test_generate_hash_v7_recovery_proof(self):
        """Line 853: RecoveryProof in generate_hash."""
        from yadacoin.core.recoveryannouncement import RecoveryProof

        proof = RecoveryProof("aabb", "ccdd", "eeff")
        txn, _ = self._make_v7_txn(proof.to_string())
        txn.relationship = proof
        h = await txn.generate_hash()
        self.assertEqual(len(h), 64)

    async def test_generate_hash_v7_recovery_transition(self):
        """Line 853: RecoveryTransition in generate_hash."""
        from yadacoin.core.recoveryannouncement import (
            RecoveryAnnouncement,
            RecoveryProof,
            RecoveryTransition,
        )

        proof = RecoveryProof("aabb", "ccdd", "eeff")
        ann = RecoveryAnnouncement("11223344")
        rt = RecoveryTransition(proof, ann)
        txn, _ = self._make_v7_txn(rt.to_string())
        txn.relationship = rt
        h = await txn.generate_hash()
        self.assertEqual(len(h), 64)

    async def test_generate_hash_v7_credential_receipt(self):
        """Line 855: CredentialReceipt in generate_hash."""
        from yadacoin.core.credentialreceipt import CredentialReceipt

        cr = CredentialReceipt("aabbccdd", "eeff0011", "ct==")
        txn, _ = self._make_v7_txn(cr.to_string())
        txn.relationship = cr
        h = await txn.generate_hash()
        self.assertEqual(len(h), 64)


# ---------------------------------------------------------------------------
# Coverage gap tests: Transaction.verify() CredentialReceipt/Recovery branches
# ---------------------------------------------------------------------------


class TestVerifyCoverageGaps(TransactionTestCase):
    """Cover lines 644-647, 667-668, 677-680, 683, 732-734 in verify()."""

    def _make_txn_with_relationship(self, rel_obj):
        """Create a Transaction whose relationship is already a typed instance."""

        txn = Transaction(
            txn_time=1000000,
            public_key=self.public_key,
            relationship="",
            relationship_hash="",
            inputs=[],
            outputs=[],
            version=7,
        )
        txn.fee = 0.0
        txn.masternode_fee = 0.0
        txn.rid = ""
        txn.requester_rid = ""
        txn.requested_rid = ""
        txn.dh_public_key = ""
        txn.prerotated_key_hash = ""
        txn.twice_prerotated_key_hash = ""
        txn.public_key_hash = ""
        txn.prev_public_key_hash = ""
        txn.relationship = rel_obj
        # Compute and store the correct relationship_hash so generate_hash passes
        import hashlib as _hashlib

        rel_str = rel_obj.to_string()
        txn.relationship_hash = _hashlib.sha256(rel_str.encode()).digest().hex()
        return txn

    async def test_verify_credential_receipt_with_inputs_raises(self):
        """Lines 644-647: CredentialReceipt + inputs → InvalidTransactionException."""
        from unittest.mock import AsyncMock, patch

        from yadacoin.core.credentialreceipt import CredentialReceipt
        from yadacoin.core.transaction import Input, InvalidTransactionException

        cr = CredentialReceipt("aabb", "ccdd", "ee==")
        txn = self._make_txn_with_relationship(cr)
        # Add an input to trigger the invariant check
        txn.inputs = [Input(signature="fakesig")]

        # Patch generate_hash and verify_signature so we don't need a real signature
        with patch.object(
            Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
        ):
            with patch.object(Transaction, "verify_signature", return_value=None):
                with self.assertRaises(InvalidTransactionException) as ctx:
                    await txn.verify(check_kel=True)
                self.assertIn("CredentialReceipt", str(ctx.exception))

    async def test_verify_recovery_proof_routes_to_keyevent_verify(self):
        """Lines 667-668: RecoveryProof with no KEL → KeyEvent.verify called."""
        from unittest.mock import AsyncMock, patch

        from yadacoin.core.keyeventlog import KeyEvent
        from yadacoin.core.recoveryannouncement import RecoveryProof

        proof = RecoveryProof("aa", "bb", "cc")
        txn = self._make_txn_with_relationship(proof)
        txn.prev_public_key_hash = "SOME_PREV_PKH"

        with patch.object(
            Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
        ):
            with patch.object(Transaction, "verify_signature", return_value=None):
                with patch.object(
                    Transaction, "has_key_event_log", new=AsyncMock(return_value=False)
                ):
                    with patch.object(
                        KeyEvent, "verify", new=AsyncMock(return_value=None)
                    ) as mock_verify:
                        await txn.verify(check_kel=True)
                        mock_verify.assert_called_once()

    async def test_verify_has_kel_mempool_branch(self):
        """Lines 677-678: has_kel=True + mempool=True → _kel_index = LatestBlock.index+1."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KeyEvent
        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        ann = RecoveryAnnouncement("aabbccdd")
        txn = self._make_txn_with_relationship(ann)

        mock_latest = MagicMock()
        # Use index well below CHECK_KEL_SPENDS_ENTIRELY_FORK to avoid verify_kel_output_rules
        mock_latest.block.index = 0
        Config().LatestBlock = mock_latest

        with patch.object(
            Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
        ):
            with patch.object(Transaction, "verify_signature", return_value=None):
                with patch.object(
                    Transaction, "has_key_event_log", new=AsyncMock(return_value=True)
                ):
                    with patch.object(
                        KeyEvent, "verify", new=AsyncMock(return_value=None)
                    ):
                        # mempool=True → _kel_index = LatestBlock.block.index + 1 = 1
                        await txn.verify(check_kel=True, mempool=True)

    async def test_verify_has_kel_no_block_no_mempool_branch(self):
        """Lines 679-680: has_kel=True + block=None + mempool=False → _kel_index = LatestBlock.index."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KeyEvent
        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        ann = RecoveryAnnouncement("aabbccdd")
        txn = self._make_txn_with_relationship(ann)

        mock_latest = MagicMock()
        mock_latest.block.index = 0
        Config().LatestBlock = mock_latest

        with patch.object(
            Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
        ):
            with patch.object(Transaction, "verify_signature", return_value=None):
                with patch.object(
                    Transaction, "has_key_event_log", new=AsyncMock(return_value=True)
                ):
                    with patch.object(
                        KeyEvent, "verify", new=AsyncMock(return_value=None)
                    ):
                        # block=None, mempool=False → _kel_index = LatestBlock.block.index = 0
                        await txn.verify(check_kel=True)

    async def test_verify_has_kel_verify_output_rules_called(self):
        """Line 683: has_kel=True + kel_index >= CHECK_KEL_SPENDS_ENTIRELY_FORK → verify_kel_output_rules."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.keyeventlog import KeyEvent
        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        ann = RecoveryAnnouncement("aabbccdd")
        txn = self._make_txn_with_relationship(ann)

        mock_latest = MagicMock()
        # Set kel_index well above CHECK_KEL_SPENDS_ENTIRELY_FORK
        mock_latest.block.index = CHAIN.CHECK_KEL_SPENDS_ENTIRELY_FORK + 1000
        Config().LatestBlock = mock_latest

        with patch.object(
            Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
        ):
            with patch.object(Transaction, "verify_signature", return_value=None):
                with patch.object(
                    Transaction, "has_key_event_log", new=AsyncMock(return_value=True)
                ):
                    with patch.object(
                        KeyEvent, "verify", new=AsyncMock(return_value=None)
                    ):
                        with patch.object(
                            Transaction,
                            "verify_kel_output_rules",
                            new=AsyncMock(return_value=None),
                        ) as mock_rules:
                            await txn.verify(check_kel=True)
                            mock_rules.assert_called_once()

    async def test_verify_recovery_announcement_to_string(self):
        """Line 732: RecoveryAnnouncement relationship.to_string() called in verify()."""
        from unittest.mock import AsyncMock, patch

        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        ann = RecoveryAnnouncement("aabbccdd")
        txn = self._make_txn_with_relationship(ann)
        # Set hash to what generate_hash will produce
        txn.hash = (
            txn.relationship_hash
        )  # short-circuit: set stored hash = relationship_hash

        with patch.object(
            Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
        ):
            with patch.object(Transaction, "verify_signature", return_value=None):
                # No check_kel — just verify the relationship.to_string() path
                await txn.verify()

    async def test_verify_credential_receipt_to_string(self):
        """Line 734: CredentialReceipt relationship.to_string() called in verify()."""
        from unittest.mock import AsyncMock, patch

        from yadacoin.core.credentialreceipt import CredentialReceipt

        cr = CredentialReceipt("aabb", "ccdd", "ee==")
        txn = self._make_txn_with_relationship(cr)

        with patch.object(
            Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
        ):
            with patch.object(Transaction, "verify_signature", return_value=None):
                await txn.verify()

    async def test_assert_unique_inception_rejects_onchain_pkh(self):
        """Second inception for same public_key_hash is rejected."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.transaction import InvalidTransactionException

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1PkHash",
            prev_public_key_hash="",
            transaction_signature="sig-new",
            inception_public_key_hash="1PkHash",
        )
        mock_db = MagicMock()

        async def _find(_q, _p=None):
            yield {"index": 100, "transactions": []}

        mock_db.blocks.find = MagicMock(side_effect=lambda *a, **k: _find(*a, **k))
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        with patch.object(txn.config.mongo, "async_db", mock_db):
            with self.assertRaises(InvalidTransactionException) as ctx:
                await txn.assert_unique_inception(block_index=600000)
        self.assertIn("Duplicate KEL inception", str(ctx.exception))
        mock_db.blocks.find.assert_called()

    async def test_assert_unique_inception_skips_fork_replaced_height(self):
        """Local KEL at a height covered by extra_blocks must not block inbound."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1PkHash",
            prev_public_key_hash="",
            transaction_signature="sig-new",
            inception_public_key_hash="1PkHash",
        )
        # Inbound fork block at height 100 replaces local chain content.
        eb = MagicMock()
        eb.index = 100
        eb.transactions = []  # no competing inception on inbound

        mock_db = MagicMock()

        async def _find(_q, _p=None):
            yield {
                "index": 100,
                "transactions": [
                    {
                        "id": "local-other",
                        "public_key_hash": "1PkHash",
                        "prev_public_key_hash": "",
                        "inception_public_key_hash": "1PkHash",
                    }
                ],
            }

        mock_db.blocks.find = MagicMock(side_effect=lambda *a, **k: _find(*a, **k))
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        with patch.object(txn.config.mongo, "async_db", mock_db):
            await txn.assert_unique_inception(block_index=101, extra_blocks=[eb])

    async def test_assert_unique_inception_rejects_batch_sibling(self):
        """Two inceptions for same pkh in one batch — second fails."""
        from yadacoin.core.transaction import InvalidTransactionException

        a = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1PreA",
            twice_prerotated_key_hash="1TwiceA",
            public_key_hash="1Same",
            prev_public_key_hash="",
            transaction_signature="sig-a",
            inception_public_key_hash="1Same",
        )
        b = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1PreB",
            twice_prerotated_key_hash="1TwiceB",
            public_key_hash="1Same",
            prev_public_key_hash="",
            transaction_signature="sig-b",
            inception_public_key_hash="1Same",
        )
        with self.assertRaises(InvalidTransactionException):
            await b.assert_unique_inception(batch_txns=[a, b])

    async def test_assert_unique_inception_allows_first(self):
        """First inception with no on-chain/mempool hit is allowed."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1Fresh",
            prev_public_key_hash="",
            transaction_signature="sig-fresh",
            inception_public_key_hash="1Fresh",
        )
        mock_db = MagicMock()

        async def _find(_q, _p=None):
            if False:
                yield None

        mock_db.blocks.find = MagicMock(side_effect=lambda *a, **k: _find(*a, **k))
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        with patch.object(txn.config.mongo, "async_db", mock_db):
            await txn.assert_unique_inception(block_index=700000)
        mock_db.blocks.find.assert_called()

    async def test_assert_unique_inception_skips_rotations(self):
        """Entries with prev_public_key_hash are not inceptions."""
        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
            transaction_signature="sig-rot",
        )
        # Would fail if it queried mongo without short-circuit.
        await txn.assert_unique_inception(block_index=700000)

    async def test_assert_unique_inception_rejects_extra_blocks(self):
        from yadacoin.core.transaction import InvalidTransactionException

        a = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1PreA",
            twice_prerotated_key_hash="1TwiceA",
            public_key_hash="1Same",
            prev_public_key_hash="",
            transaction_signature="sig-a",
            inception_public_key_hash="1Same",
        )
        b = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1PreB",
            twice_prerotated_key_hash="1TwiceB",
            public_key_hash="1Same",
            prev_public_key_hash="",
            transaction_signature="sig-b",
            inception_public_key_hash="1Same",
        )
        eb = MagicMock()
        eb.index = 10
        eb.transactions = [a]
        with self.assertRaises(InvalidTransactionException):
            await b.assert_unique_inception(block_index=20, extra_blocks=[eb])

    async def test_assert_unique_inception_rejects_mempool(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.transaction import InvalidTransactionException

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1PkHash",
            prev_public_key_hash="",
            transaction_signature="sig-new",
            inception_public_key_hash="1PkHash",
        )
        mock_db = MagicMock()

        async def _find(_q, _p=None):
            if False:
                yield None

        mock_db.blocks.find = MagicMock(side_effect=lambda *a, **k: _find(*a, **k))
        mock_db.miner_transactions.find_one = AsyncMock(return_value={"id": "other"})
        with patch.object(txn.config.mongo, "async_db", mock_db):
            with self.assertRaises(InvalidTransactionException):
                await txn.assert_unique_inception(block_index=700000)

    async def test_assert_unique_inception_skips_no_kel_fields(self):
        txn = Transaction(public_key=self.public_key)
        await txn.assert_unique_inception(block_index=700000)

    async def test_assert_unique_inception_skips_recovery(self):
        from yadacoin.core.recoveryannouncement import RecoveryProof

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1Pk",
            prev_public_key_hash="",
            transaction_signature="sig-r",
        )
        txn.relationship = RecoveryProof("aa" * 32, "bb" * 32, "cc" * 32)
        await txn.assert_unique_inception(block_index=700000)

    async def test_output_owned_by_kel_spender(self):
        from unittest.mock import AsyncMock, patch

        txn = Transaction(public_key=self.public_key)
        txn.inception_public_key_hash = "1Inc"
        self.assertTrue(await txn._output_owned_by_kel_spender("addr", "addr", False))
        self.assertFalse(await txn._output_owned_by_kel_spender("other", "addr", False))
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
            new=AsyncMock(
                return_value=MagicMock(
                    inception_public_key_hash="1Inc", public_key_hash="1Inc"
                )
            ),
        ):
            self.assertTrue(
                await txn._output_owned_by_kel_spender("out", "spender", True)
            )
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
            new=AsyncMock(return_value=None),
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.is_same_kel",
                new=AsyncMock(return_value=True),
            ):
                self.assertTrue(
                    await txn._output_owned_by_kel_spender("out", "spender", True)
                )
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
            new=AsyncMock(return_value=None),
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.is_same_kel",
                new=AsyncMock(return_value=False),
            ):
                self.assertFalse(
                    await txn._output_owned_by_kel_spender("out", "spender", True)
                )

    async def test_get_kel_cross_key_auth_batch_walk(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        spender = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1TipPre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1TipPkh",
            prev_public_key_hash="1MidPre",
            inception_public_key_hash="1Inc",
            transaction_signature="sig-tip",
        )
        parent = MagicMock()
        parent.are_kel_fields_populated = lambda: True
        parent.transaction_signature = "sig-parent"
        parent.prev_public_key_hash = "1OnchainPkh"
        parent.public_key_hash = "1OnchainPre"
        parent.prerotated_key_hash = "1TipPkh"
        parent.inception_public_key_hash = "1Inc"

        mid = MagicMock()
        mid.are_kel_fields_populated = lambda: True
        mid.transaction_signature = "sig-mid"
        mid.prev_public_key_hash = "1OnchainPre"
        mid.public_key_hash = "1TipPkh"
        mid.prerotated_key_hash = "1TipPre"
        mid.inception_public_key_hash = "1Inc"

        latest = MagicMock()
        latest.public_key_hash = "1OnchainPkh"
        latest.prerotated_key_hash = "1OnchainPre"

        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK + 10
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                new=AsyncMock(return_value=latest),
            ):
                ok = await spender.get_kel_cross_key_auth(
                    "1TipPre", mempool=True, batch_txns=[parent, mid, spender]
                )
        self.assertTrue(ok)

    async def test_get_kel_cross_key_auth_extra_blocks_walk(self):
        """Inbound fork KEL tips must authorize spends, not only local mongo."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        spender = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1TipPre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1TipPkh",
            prev_public_key_hash="1MidPre",
            inception_public_key_hash="1Inc",
            transaction_signature="sig-tip",
        )
        parent = MagicMock()
        parent.are_kel_fields_populated = lambda: True
        parent.transaction_signature = "sig-parent"
        parent.prev_public_key_hash = "1OnchainPkh"
        parent.public_key_hash = "1OnchainPre"
        parent.prerotated_key_hash = "1TipPkh"
        parent.inception_public_key_hash = "1Inc"

        mid = MagicMock()
        mid.are_kel_fields_populated = lambda: True
        mid.transaction_signature = "sig-mid"
        mid.prev_public_key_hash = "1OnchainPre"
        mid.public_key_hash = "1TipPkh"
        mid.prerotated_key_hash = "1TipPre"
        mid.inception_public_key_hash = "1Inc"

        fork_block = MagicMock()
        fork_block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK + 5
        fork_block.transactions = [parent, mid]

        # Local mongo tip is older / on the losing branch — walk must use
        # extra_blocks to reach 1TipPre.
        latest = MagicMock()
        latest.public_key_hash = "1OnchainPkh"
        latest.prerotated_key_hash = "1OnchainPre"

        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK + 10
        block = MagicMock()
        block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK + 6
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                new=AsyncMock(return_value=latest),
            ):
                ok = await spender.get_kel_cross_key_auth(
                    "1TipPre",
                    block=block,
                    batch_txns=[spender],
                    extra_blocks=[fork_block],
                )
        self.assertTrue(ok)

    async def test_sum_inputs_kel_parent_inc_match(self):
        """sum_inputs credits prerotated out via parent inception match."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.transaction import Output

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
            inception_public_key_hash="1Inc",
        )
        out = Output(to="1Pre", value=10.0)
        out_zero = Output(to="1Pre", value=0.0)
        parent = MagicMock()
        parent.outputs = [out_zero, out]
        parent.inception_public_key_hash = "1Inc"
        parent.prerotated_key_hash = "1Pre"
        inp = MagicMock()
        inputs = []
        with patch.object(
            txn, "get_kel_cross_key_auth", new=AsyncMock(return_value=True)
        ):
            with patch.object(
                txn,
                "_output_owned_by_kel_spender",
                new=AsyncMock(return_value=False),
            ):
                total = await txn.sum_inputs(inp, parent, "1Spender", 0.0, inputs, 5.0)
        self.assertEqual(total, 10.0)
        self.assertEqual(len(inputs), 1)

    async def test_sum_inputs_auth_exception(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.transaction import Output

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
        )
        parent = MagicMock()
        parent.outputs = [Output(to="1X", value=1.0)]
        with patch.object(
            txn, "get_kel_cross_key_auth", new=AsyncMock(side_effect=RuntimeError("x"))
        ):
            total = await txn.sum_inputs(MagicMock(), parent, "1X", 0.0, [], 10.0)
        # auth failed → kel_log_spend False → exact address match still works
        self.assertEqual(total, 1.0)

    async def test_assert_unique_inception_empty_pkh(self):
        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="",
            prev_public_key_hash="",
            transaction_signature="s",
        )
        # Force are_kel_fields true but empty pkh
        txn.public_key_hash = ""
        txn.prerotated_key_hash = "1Pre"
        txn.twice_prerotated_key_hash = "1T"
        txn.prev_public_key_hash = ""
        await txn.assert_unique_inception()

    async def test_assert_unique_inception_skips_future_extra_block(self):
        a = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1PreA",
            twice_prerotated_key_hash="1TwiceA",
            public_key_hash="1Same",
            prev_public_key_hash="",
            transaction_signature="sig-a",
            inception_public_key_hash="1Same",
        )
        b = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1PreB",
            twice_prerotated_key_hash="1TwiceB",
            public_key_hash="1Same",
            prev_public_key_hash="",
            transaction_signature="sig-b",
            inception_public_key_hash="1Same",
        )
        eb = MagicMock()
        eb.index = 50  # >= block_index → skip
        eb.transactions = [a]
        from unittest.mock import AsyncMock, patch

        mock_db = MagicMock()

        async def _find(_q, _p=None):
            if False:
                yield None

        mock_db.blocks.find = MagicMock(side_effect=lambda *a, **k: _find(*a, **k))
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        with patch.object(b.config.mongo, "async_db", mock_db):
            await b.assert_unique_inception(block_index=20, extra_blocks=[eb])

    async def test_assert_unique_inception_other_not_kel(self):
        from unittest.mock import AsyncMock, patch

        a = MagicMock()
        a.transaction_signature = "sig-a"
        a.are_kel_fields_populated = lambda: False
        a.prev_public_key_hash = ""
        a.public_key_hash = "1Same"
        b = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1PreB",
            twice_prerotated_key_hash="1TwiceB",
            public_key_hash="1Same",
            prev_public_key_hash="",
            transaction_signature="sig-b",
            inception_public_key_hash="1Same",
        )
        mock_db = MagicMock()

        async def _find(_q, _p=None):
            if False:
                yield None

        mock_db.blocks.find = MagicMock(side_effect=lambda *a, **k: _find(*a, **k))
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        with patch.object(b.config.mongo, "async_db", mock_db):
            await b.assert_unique_inception(batch_txns=[a, b])

    async def test_get_kel_cross_key_auth_from_batch_tag(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
            # no inception on self
        )
        sibling = MagicMock()
        sibling.inception_public_key_hash = "1Inc"
        sibling.are_kel_fields_populated = lambda: True
        sibling.transaction_signature = "sib"
        sibling.prev_public_key_hash = "x"
        sibling.public_key_hash = "y"
        sibling.prerotated_key_hash = "z"
        latest = MagicMock(public_key_hash="1Pk", prerotated_key_hash="1Pre")
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                new=AsyncMock(return_value=latest),
            ):
                ok = await txn.get_kel_cross_key_auth("1Pre", batch_txns=[sibling])
        self.assertTrue(ok)

    async def test_get_kel_cross_key_auth_resolve_via_address(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
        )
        inception = MagicMock(
            inception_public_key_hash="1Inc",
            public_key_hash="1Inc",
            public_key="aa" * 33,
        )
        latest = MagicMock(public_key_hash="1A", prerotated_key_hash="1Pre")
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(return_value=inception),
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                    new=AsyncMock(return_value=latest),
                ):
                    ok = await txn.get_kel_cross_key_auth("1Pre")
        self.assertTrue(ok)

    async def test_get_kel_cross_key_auth_no_batch_false(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
            inception_public_key_hash="1Inc",
        )
        latest = MagicMock(public_key_hash="1A", prerotated_key_hash="1Other")
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                new=AsyncMock(return_value=latest),
            ):
                ok = await txn.get_kel_cross_key_auth("1Pre", batch_txns=None)
        self.assertFalse(ok)

    async def test_get_kel_cross_key_auth_block_index(self):
        from unittest.mock import MagicMock

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
            inception_public_key_hash="1Inc",
        )
        block = MagicMock()
        block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK - 1
        self.assertFalse(await txn.get_kel_cross_key_auth("1Pre", block=block))

    async def test_get_kel_cross_key_auth_empty_cand_and_batch_resolve(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="",
            prev_public_key_hash="",
            # no inception tag on self
        )
        # Force empty public_key_hash after construct
        txn.public_key_hash = ""
        txn.prev_public_key_hash = ""
        batch_t = MagicMock()
        batch_t.prev_public_key_hash = ""
        batch_t.public_key_hash = ""
        batch_t.prerotated_key_hash = "1Cand"
        batch_t.are_kel_fields_populated = lambda: True
        batch_t.transaction_signature = "b"
        inception = MagicMock(
            inception_public_key_hash="1Inc", public_key_hash="1Inc", public_key=None
        )
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK + 1

        async def get_inc(address=None, **k):
            if address == "1Cand":
                return inception
            return None

        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(side_effect=get_inc),
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                    new=AsyncMock(return_value=None),
                ):
                    # latest None → False
                    ok = await txn.get_kel_cross_key_auth("addr", batch_txns=[batch_t])
        self.assertFalse(ok)

    async def test_get_kel_cross_key_auth_latest_from_inception_pubkey(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
        )
        inception = MagicMock(
            inception_public_key_hash="1Inc",
            public_key_hash="1Inc",
            public_key="aa" * 33,
        )
        latest = MagicMock(public_key_hash="1A", prerotated_key_hash="1Pre")
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(return_value=inception),
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                    new=AsyncMock(return_value=None),
                ):
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
                        new=AsyncMock(return_value=latest),
                    ):
                        ok = await txn.get_kel_cross_key_auth("1Pre")
        self.assertTrue(ok)

    async def test_get_kel_cross_key_auth_walk_skips_non_kel(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1TipPre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1TipPkh",
            prev_public_key_hash="1Mid",
            inception_public_key_hash="1Inc",
            transaction_signature="sig-tip",
        )
        junk = MagicMock()
        junk.are_kel_fields_populated = lambda: False
        junk.transaction_signature = "junk"
        # same signature as self should skip
        twin = MagicMock()
        twin.are_kel_fields_populated = lambda: True
        twin.transaction_signature = "sig-tip"
        twin.prev_public_key_hash = "x"
        twin.public_key_hash = "y"
        twin.prerotated_key_hash = "z"
        latest = MagicMock(public_key_hash="1A", prerotated_key_hash="1B")
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                new=AsyncMock(return_value=latest),
            ):
                ok = await txn.get_kel_cross_key_auth(
                    "1TipPre", batch_txns=[junk, twin, txn]
                )
        self.assertFalse(ok)

    async def test_assert_unique_other_has_prev(self):
        from unittest.mock import AsyncMock, patch

        a = MagicMock()
        a.transaction_signature = "sig-a"
        a.are_kel_fields_populated = lambda: True
        a.prev_public_key_hash = "1Prev"  # rotation, not inception
        a.public_key_hash = "1Same"
        b = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1PreB",
            twice_prerotated_key_hash="1TwiceB",
            public_key_hash="1Same",
            prev_public_key_hash="",
            transaction_signature="sig-b",
            inception_public_key_hash="1Same",
        )
        mock_db = MagicMock()

        async def _find(_q, _p=None):
            if False:
                yield None

        mock_db.blocks.find = MagicMock(side_effect=lambda *a, **k: _find(*a, **k))
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        with patch.object(b.config.mongo, "async_db", mock_db):
            await b.assert_unique_inception(batch_txns=[a, b])

    async def test_verify_owned_via_parent_inc(self):
        """verify() credits out when parent inception matches."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.keyrotation import NodeKeyRotationManager
        from yadacoin.core.transaction import Input, Output

        parent = Transaction(
            public_key=self.public_key,
            outputs=[Output(to="1PreParent", value=5.0)],
            prerotated_key_hash="1PreParent",
            twice_prerotated_key_hash="1T",
            public_key_hash="1PkP",
            prev_public_key_hash="",
            inception_public_key_hash="1Inc",
            transaction_signature="parent_sig",
            coinbase=True,
        )
        txn = Transaction(
            public_key=self.public_key,
            outputs=[Output(to="1Dest", value=4.0)],
            fee=1.0,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash=str(
                __import__(
                    "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
                ).P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key))
            ),
            prev_public_key_hash="1Prev",
            inception_public_key_hash="1Inc",
        )
        txn.inputs = [Input(signature="parent_sig", input_txn=parent)]
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = NodeKeyRotationManager._sign(
            self.private_key, txn.hash
        )
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK + 10
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch.object(
                txn, "get_kel_cross_key_auth", new=AsyncMock(return_value=True)
            ):
                with patch.object(
                    txn,
                    "_output_owned_by_kel_spender",
                    new=AsyncMock(return_value=False),
                ):
                    with patch.object(
                        txn, "has_key_event_log", new=AsyncMock(return_value=False)
                    ):
                        with patch.object(
                            txn, "assert_unique_inception", new=AsyncMock()
                        ):
                            await txn.verify(check_input_spent=False, check_kel=False)

    async def test_get_kel_cross_key_auth_block_branch(self):
        """Below fork: get_kel_cross_key_auth returns False."""
        from unittest.mock import MagicMock

        from yadacoin.core.chain import CHAIN

        txn = Transaction(public_key=self.public_key)
        mock_block = MagicMock()
        mock_block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK - 1

        result = await txn.get_kel_cross_key_auth("some_address", block=mock_block)

        self.assertFalse(result)

    async def test_get_kel_cross_key_auth_mempool_branch(self):
        """Mempool path below fork returns False."""
        from unittest.mock import MagicMock

        from yadacoin.core.chain import CHAIN

        txn = Transaction(public_key=self.public_key)
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK - 2

        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            result = await txn.get_kel_cross_key_auth(
                "some_address", block=None, mempool=True
            )

        self.assertFalse(result)

    async def test_get_kel_cross_key_auth_returns_true_for_tip(self):
        """True when KEL fields set and signer is tip prerotated_key_hash."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(public_key=self.public_key)
        txn.prerotated_key_hash = "1Pre"
        txn.twice_prerotated_key_hash = "1Twice"
        txn.public_key_hash = "1Pk"
        txn.prev_public_key_hash = "1Prev"
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK

        address = "1TargetAddress"
        inception = MagicMock()
        inception.inception_public_key_hash = "1Inception"
        inception.public_key_hash = "1Inception"
        inception.public_key = "aa" * 33
        kel_entry = MagicMock()
        kel_entry.prerotated_key_hash = address

        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(return_value=inception),
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                    new=AsyncMock(return_value=kel_entry),
                ):
                    result = await txn.get_kel_cross_key_auth(address)

        self.assertTrue(result)

    async def test_get_kel_cross_key_auth_false_without_kel_fields(self):
        """Plain tip transfer cannot cross-spend prior KEL addresses."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(public_key=self.public_key)
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK
        kel_entry = MagicMock()
        kel_entry.prerotated_key_hash = "1TargetAddress"

        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
                new=AsyncMock(return_value=kel_entry),
            ):
                result = await txn.get_kel_cross_key_auth("1TargetAddress")

        self.assertFalse(result)

    async def test_get_kel_cross_key_auth_no_match_returns_false(self):
        """False when signer is not the KEL tip key."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(public_key=self.public_key)
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK

        kel_entry = MagicMock()
        kel_entry.prerotated_key_hash = "1SomeOtherAddress"

        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
                new=AsyncMock(return_value=kel_entry),
            ):
                result = await txn.get_kel_cross_key_auth("1NotMatching")

        self.assertFalse(result)

    async def test_verify_kel_authorized_output_found(self):
        """Lines 799-801: kel_authorized_addresses is not None and output.to matches."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH

        address = str(_P2PKH.from_pubkey(bytes.fromhex(self.public_key)))

        # Input transaction whose output goes to `address`
        input_txn_obj = Transaction(
            public_key=self.public_key,
            outputs=[Output(to=address, value=2.0)],
        )
        txn = Transaction(
            public_key=self.public_key,
            outputs=[Output(to=address, value=2.0)],
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash=address,
            prev_public_key_hash="1Prev",
        )
        txn.inputs = [Input(signature="sig1", input_txn=input_txn_obj)]
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = NodeKeyRotationManager._sign(
            self.private_key, txn.hash
        )

        mock_lb = MagicMock()
        mock_lb.block.index = 100

        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch.object(
                txn,
                "get_kel_cross_key_auth",
                new=AsyncMock(return_value=True),
            ):
                with patch.object(
                    txn, "has_key_event_log", new=AsyncMock(return_value=False)
                ):
                    # check_input_spent=False avoids needing to mock BU.is_input_spent
                    await txn.verify(check_input_spent=False, check_kel=False)


class TestVerifyCheckKelBatchAndPrevHash(TransactionTestCase):
    """Cover lines 681-691, 716-719, 726 in verify()'s check_kel branch."""

    def _make_txn_with_relationship(self, rel_obj):
        txn = Transaction(
            txn_time=1000000,
            public_key=self.public_key,
            relationship="",
            relationship_hash="",
            inputs=[],
            outputs=[],
            version=7,
        )
        txn.fee = 0.0
        txn.masternode_fee = 0.0
        txn.rid = ""
        txn.requester_rid = ""
        txn.requested_rid = ""
        txn.dh_public_key = ""
        txn.prerotated_key_hash = ""
        txn.twice_prerotated_key_hash = ""
        txn.public_key_hash = ""
        txn.prev_public_key_hash = ""
        txn.relationship = rel_obj
        import hashlib as _hashlib

        rel_str = rel_obj.to_string()
        txn.relationship_hash = _hashlib.sha256(rel_str.encode()).digest().hex()
        return txn

    async def test_verify_check_kel_batch_txns_prerotated_match(self):
        """Lines 681-685, 691: batch_txns fallback matches prerotated_key_hash."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH

        from yadacoin.core.keyeventlog import KeyEvent
        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        address = str(_P2PKH.from_pubkey(bytes.fromhex(self.public_key)))
        ann = RecoveryAnnouncement("aabbccdd")
        txn = self._make_txn_with_relationship(ann)
        txn.transaction_signature = "self_sig"

        sibling = MagicMock()
        sibling.transaction_signature = "sibling_sig"
        sibling.prerotated_key_hash = address
        sibling.twice_prerotated_key_hash = "unrelated"

        mock_lb = MagicMock()
        mock_lb.block.index = 0
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch.object(
                Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
            ):
                with patch.object(Transaction, "verify_signature", return_value=None):
                    with patch.object(
                        Transaction,
                        "has_key_event_log",
                        new=AsyncMock(return_value=False),
                    ):
                        with patch.object(
                            KeyEvent, "verify", new=AsyncMock(return_value=None)
                        ) as mock_verify:
                            await txn.verify(check_kel=True, batch_txns=[sibling])
                            # has_kel resolved True via batch_txns fallback → KeyEvent.verify called
                            mock_verify.assert_called_once()

    async def test_verify_check_kel_batch_txns_twice_prerotated_match(self):
        """Lines 686-691: batch_txns fallback matches twice_prerotated_key_hash."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH

        from yadacoin.core.keyeventlog import KeyEvent
        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        address = str(_P2PKH.from_pubkey(bytes.fromhex(self.public_key)))
        ann = RecoveryAnnouncement("aabbccdd")
        txn = self._make_txn_with_relationship(ann)
        txn.transaction_signature = "self_sig"

        sibling = MagicMock()
        sibling.transaction_signature = "sibling_sig"
        sibling.prerotated_key_hash = "unrelated"
        sibling.twice_prerotated_key_hash = address

        mock_lb = MagicMock()
        mock_lb.block.index = 0
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch.object(
                Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
            ):
                with patch.object(Transaction, "verify_signature", return_value=None):
                    with patch.object(
                        Transaction,
                        "has_key_event_log",
                        new=AsyncMock(return_value=False),
                    ):
                        with patch.object(
                            KeyEvent, "verify", new=AsyncMock(return_value=None)
                        ) as mock_verify:
                            await txn.verify(check_kel=True, batch_txns=[sibling])
                            mock_verify.assert_called_once()

    async def test_verify_check_kel_batch_txns_no_match_raises_prev_hash(self):
        """Lines 681-691, 716-719: batch_txns present but no match, prev_public_key_hash
        set, block=None → KELExceptionPreviousKeyHashReferenceMissing raised."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import (
            KELExceptionPreviousKeyHashReferenceMissing,
        )
        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        ann = RecoveryAnnouncement("aabbccdd")
        txn = self._make_txn_with_relationship(ann)
        txn.transaction_signature = "self_sig"
        txn.prev_public_key_hash = "some_prev_pkh"

        sibling = MagicMock()
        sibling.transaction_signature = "sibling_sig"
        sibling.prerotated_key_hash = "not_matching"
        sibling.twice_prerotated_key_hash = "also_not_matching"

        with patch.object(
            Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
        ):
            with patch.object(Transaction, "verify_signature", return_value=None):
                with patch.object(
                    Transaction,
                    "has_key_event_log",
                    new=AsyncMock(return_value=False),
                ):
                    with self.assertRaises(KELExceptionPreviousKeyHashReferenceMissing):
                        await txn.verify(check_kel=True, batch_txns=[sibling])

    async def test_verify_check_kel_extra_blocks_prerotated_match(self):
        """Lines 723-737: extra_blocks fallback matches prerotated_key_hash."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH

        from yadacoin.core.keyeventlog import KeyEvent
        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        address = str(_P2PKH.from_pubkey(bytes.fromhex(self.public_key)))
        ann = RecoveryAnnouncement("aabbccdd")
        txn = self._make_txn_with_relationship(ann)
        txn.transaction_signature = "self_sig"

        sibling = MagicMock()
        sibling.transaction_signature = "sibling_sig"
        sibling.prerotated_key_hash = address
        sibling.twice_prerotated_key_hash = "unrelated"

        extra_block = MagicMock()
        extra_block.index = 5
        extra_block.transactions = [sibling]
        block = MagicMock()
        block.index = 10

        mock_lb = MagicMock()
        mock_lb.block.index = 0
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch.object(
                Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
            ):
                with patch.object(Transaction, "verify_signature", return_value=None):
                    with patch.object(
                        Transaction,
                        "has_key_event_log",
                        new=AsyncMock(return_value=False),
                    ):
                        with patch.object(
                            KeyEvent, "verify", new=AsyncMock(return_value=None)
                        ) as mock_verify:
                            await txn.verify(
                                check_kel=True,
                                block=block,
                                extra_blocks=[extra_block],
                            )
                            mock_verify.assert_called_once()

    async def test_verify_check_kel_extra_blocks_twice_prerotated_match(self):
        """Lines 723-737: extra_blocks fallback matches twice_prerotated_key_hash."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH

        from yadacoin.core.keyeventlog import KeyEvent
        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        address = str(_P2PKH.from_pubkey(bytes.fromhex(self.public_key)))
        ann = RecoveryAnnouncement("aabbccdd")
        txn = self._make_txn_with_relationship(ann)
        txn.transaction_signature = "self_sig"

        sibling = MagicMock()
        sibling.transaction_signature = "sibling_sig"
        sibling.prerotated_key_hash = "unrelated"
        sibling.twice_prerotated_key_hash = address

        extra_block = MagicMock()
        extra_block.index = 5
        extra_block.transactions = [sibling]
        block = MagicMock()
        block.index = 10

        mock_lb = MagicMock()
        mock_lb.block.index = 0
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch.object(
                Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
            ):
                with patch.object(Transaction, "verify_signature", return_value=None):
                    with patch.object(
                        Transaction,
                        "has_key_event_log",
                        new=AsyncMock(return_value=False),
                    ):
                        with patch.object(
                            KeyEvent, "verify", new=AsyncMock(return_value=None)
                        ) as mock_verify:
                            await txn.verify(
                                check_kel=True,
                                block=block,
                                extra_blocks=[extra_block],
                            )
                            mock_verify.assert_called_once()

    async def test_verify_check_kel_extra_blocks_skips_self_and_breaks(self):
        """Lines 723-737: skips self signature, matches later extra block, breaks."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH

        from yadacoin.core.keyeventlog import KeyEvent
        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        address = str(_P2PKH.from_pubkey(bytes.fromhex(self.public_key)))
        ann = RecoveryAnnouncement("aabbccdd")
        txn = self._make_txn_with_relationship(ann)
        txn.transaction_signature = "self_sig"

        self_txn = MagicMock()
        self_txn.transaction_signature = "self_sig"
        self_txn.prerotated_key_hash = address
        self_txn.twice_prerotated_key_hash = address

        miss = MagicMock()
        miss.transaction_signature = "miss_sig"
        miss.prerotated_key_hash = "nope"
        miss.twice_prerotated_key_hash = "nope"

        hit = MagicMock()
        hit.transaction_signature = "hit_sig"
        hit.prerotated_key_hash = address
        hit.twice_prerotated_key_hash = "unrelated"

        first_block = MagicMock()
        first_block.index = 5
        first_block.transactions = [self_txn, miss]
        second_block = MagicMock()
        second_block.index = 6
        second_block.transactions = [hit]
        third_block = MagicMock()
        third_block.index = 20
        third_block.transactions = [miss]
        block = MagicMock()
        block.index = 10

        mock_lb = MagicMock()
        mock_lb.block.index = 0
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch.object(
                Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
            ):
                with patch.object(Transaction, "verify_signature", return_value=None):
                    with patch.object(
                        Transaction,
                        "has_key_event_log",
                        new=AsyncMock(return_value=False),
                    ):
                        with patch.object(
                            KeyEvent, "verify", new=AsyncMock(return_value=None)
                        ) as mock_verify:
                            await txn.verify(
                                check_kel=True,
                                block=block,
                                extra_blocks=[first_block, second_block, third_block],
                            )
                            mock_verify.assert_called_once()

    async def test_verify_check_kel_extra_blocks_skips_future_height_only(self):
        """Only future-height extra_blocks are skipped; no match → no KeyEvent.verify."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH

        from yadacoin.core.keyeventlog import KeyEvent
        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        address = str(_P2PKH.from_pubkey(bytes.fromhex(self.public_key)))
        ann = RecoveryAnnouncement("aabbccdd")
        txn = self._make_txn_with_relationship(ann)
        txn.transaction_signature = "self_sig"

        sibling = MagicMock()
        sibling.transaction_signature = "sibling_sig"
        sibling.prerotated_key_hash = address
        sibling.twice_prerotated_key_hash = "unrelated"

        future = MagicMock()
        future.index = 99
        future.transactions = [sibling]
        block = MagicMock()
        block.index = 10

        mock_lb = MagicMock()
        mock_lb.block.index = 0
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch.object(
                Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
            ):
                with patch.object(Transaction, "verify_signature", return_value=None):
                    with patch.object(
                        Transaction,
                        "has_key_event_log",
                        new=AsyncMock(return_value=False),
                    ):
                        with patch.object(
                            KeyEvent, "verify", new=AsyncMock(return_value=None)
                        ) as mock_verify:
                            # Future sibling skipped → has_kel stays False → no KeyEvent
                            try:
                                await txn.verify(
                                    check_kel=True,
                                    block=block,
                                    extra_blocks=[future],
                                )
                            except Exception:
                                pass
                            mock_verify.assert_not_called()

    async def test_verify_check_kel_has_kel_block_index_used(self):
        """Line 726: has_kel=True + block is not None → _kel_index = block.index."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KeyEvent
        from yadacoin.core.recoveryannouncement import RecoveryAnnouncement

        ann = RecoveryAnnouncement("aabbccdd")
        txn = self._make_txn_with_relationship(ann)

        mock_block = MagicMock()
        # Below CHECK_KEL_SPENDS_ENTIRELY_FORK so verify_kel_output_rules is skipped
        mock_block.index = 0

        with patch.object(
            Transaction, "generate_hash", new=AsyncMock(return_value=txn.hash)
        ):
            with patch.object(Transaction, "verify_signature", return_value=None):
                with patch.object(
                    Transaction,
                    "has_key_event_log",
                    new=AsyncMock(return_value=True),
                ):
                    with patch.object(
                        KeyEvent, "verify", new=AsyncMock(return_value=None)
                    ):
                        await txn.verify(check_kel=True, block=mock_block)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)


class TestNewCodeCoverageFinal(TransactionTestCase):
    async def test_to_dict_includes_counter_and_inception(self):
        txn = Transaction(
            public_key=self.public_key,
            outputs=[],
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1T",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
            counter=7,
            inception_public_key_hash="1Inc",
        )
        d = txn.to_dict()
        self.assertEqual(d["counter"], 7)
        self.assertEqual(d["inception_public_key_hash"], "1Inc")

    async def test_has_key_event_log_bad_pubkey(self):
        txn = Transaction(public_key="not-hex")
        self.assertFalse(await txn.has_key_event_log())

    async def test_has_key_event_log_no_pubkey(self):
        txn = Transaction(public_key="")
        self.assertFalse(await txn.has_key_event_log())

    async def test_get_kel_cross_inception_none(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1T",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
        )
        txn.inception_public_key_hash = None
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(return_value=None),
            ):
                self.assertFalse(await txn.get_kel_cross_key_auth("1Pre"))

    async def test_get_kel_cross_batch_empty_cands(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1T",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
        )
        # No inception on self; batch members have empty cand fields only
        txn.inception_public_key_hash = None
        t = MagicMock(spec=[])  # no auto attrs
        # manually set only what we need
        type(t).prev_public_key_hash = None
        type(t).public_key_hash = None
        type(t).prerotated_key_hash = None
        type(t).inception_public_key_hash = None
        type(t).are_kel_fields_populated = lambda self: True
        type(t).transaction_signature = "t1"
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(return_value=None),
            ):
                # address cand will be tried and return None
                self.assertFalse(
                    await txn.get_kel_cross_key_auth("addr", batch_txns=[t])
                )

    async def test_check_input_spent_block_and_extra(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyrotation import NodeKeyRotationManager
        from yadacoin.core.transaction import Input, Output

        addr = str(
            __import__(
                "bitcoin.wallet", fromlist=["P2PKHBitcoinAddress"]
            ).P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key))
        )
        parent = Transaction(
            public_key=self.public_key,
            outputs=[Output(to=addr, value=5.0)],
            transaction_signature="psig",
            coinbase=True,
        )
        txn = Transaction(
            public_key=self.public_key,
            outputs=[Output(to=addr, value=4.0)],
            fee=1.0,
        )
        txn.inputs = [Input(signature="psig", input_txn=parent)]
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = NodeKeyRotationManager._sign(
            self.private_key, txn.hash
        )
        block = MagicMock()
        block.index = 100
        mock_lb = MagicMock()
        mock_lb.block.index = 100
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch.object(
                self.config.BU, "is_input_spent", new=AsyncMock(return_value=False)
            ) as spent:
                await txn.verify(check_input_spent=True, check_kel=False, block=block)
                self.assertEqual(spent.await_args.kwargs.get("from_index"), 100)

        eb = MagicMock()
        eb.index = 99
        txn.extra_blocks = [eb]
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch.object(
                self.config.BU, "is_input_spent", new=AsyncMock(return_value=False)
            ) as spent2:
                await txn.verify(check_input_spent=True, check_kel=False, block=None)
                self.assertEqual(spent2.await_args.kwargs.get("from_index"), 99)


class TestKelCrossRemainingLines(TransactionTestCase):
    async def test_empty_cand_continue(self):
        """Line 1601: skip falsy cands in self-lookup loop."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1T",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
        )
        txn.inception_public_key_hash = None
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(return_value=None),
            ):
                # address=None is skipped (continue); prev/pkh still queried
                self.assertFalse(await txn.get_kel_cross_key_auth(None))

    async def test_batch_resolve_inception(self):
        """Lines 1608-1622: find inception via batch prerotated cand."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1T",
            public_key_hash="x",
            prev_public_key_hash="y",
        )
        txn.inception_public_key_hash = None
        txn.public_key_hash = ""
        txn.prev_public_key_hash = ""

        t = MagicMock()
        t.prev_public_key_hash = None
        t.public_key_hash = None
        t.prerotated_key_hash = "1Hit"
        t.inception_public_key_hash = None
        t.are_kel_fields_populated = lambda: True
        t.transaction_signature = "t"

        inception = MagicMock(
            inception_public_key_hash="1Inc",
            public_key_hash="1Inc",
            public_key=None,
        )
        # tip prerotated must equal the address we pass for auth success
        latest = MagicMock(public_key_hash="1On", prerotated_key_hash="1Wanted")
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK

        async def gi(address=None, **k):
            # Only batch cand resolves; address "1Wanted" must NOT resolve
            # via get_inception or we'd never reach batch loop.
            if address == "1Hit":
                return inception
            return None

        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(side_effect=gi),
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                    new=AsyncMock(return_value=latest),
                ):
                    ok = await txn.get_kel_cross_key_auth("1Wanted", batch_txns=[t])
        self.assertTrue(ok)

    async def test_inception_tag_fields_both_empty(self):
        """Line 1629: inception object exists but tags are empty."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1T",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
        )
        txn.inception_public_key_hash = None
        empty_inc = MagicMock(
            inception_public_key_hash=None,
            public_key_hash=None,
            public_key=None,
        )
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(return_value=empty_inc),
            ):
                self.assertFalse(await txn.get_kel_cross_key_auth("1Pk"))


class TestCoverageGapsTo100(TransactionTestCase):
    """Fill remaining coverage gaps for 100% line coverage."""

    async def test_assert_unique_inception_same_id_revalidation(self):
        """Lines 1428-1441: same-id inception re-validation is allowed."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1PkHash",
            prev_public_key_hash="",
            transaction_signature="same-sig",
            inception_public_key_hash="1PkHash",
        )
        mock_db = MagicMock()

        async def _find(_q, _p=None):
            yield {
                "index": 50,
                "transactions": [
                    "not-a-dict",
                    {
                        "id": "other-sig",
                        "public_key_hash": "nope",
                        "prev_public_key_hash": "",
                    },
                    {
                        "id": "same-sig",
                        "public_key_hash": "1PkHash",
                        "prev_public_key_hash": "has-prev-skip",
                        "inception_public_key_hash": "1PkHash",
                    },
                    {
                        "id": "same-sig",
                        "public_key_hash": "1PkHash",
                        "prev_public_key_hash": "",
                        "inception_public_key_hash": "1PkHash",
                    },
                ],
            }

        mock_db.blocks.find = MagicMock(side_effect=lambda *a, **k: _find(*a, **k))
        mock_db.miner_transactions.find_one = AsyncMock(return_value=None)
        with patch.object(txn.config.mongo, "async_db", mock_db):
            await txn.assert_unique_inception(block_index=100)

    async def test_is_already_onchain_txn_matches_branches(self):
        """Lines 1530-1542: _txn_matches non-dict, twice/pre/pkh/prev/false."""
        from unittest.mock import MagicMock, patch

        txn = Transaction(
            public_key=self.public_key,
            inputs=[],
            outputs=[],
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1Twice",
            public_key_hash="1Pkh",
            prev_public_key_hash="1Prev",
            transaction_signature="my-sig",
        )
        mock_db = MagicMock()

        async def _find_nondict(*a, **k):
            yield {"index": 1, "transactions": ["x", None]}

        mock_db.blocks.find = MagicMock(side_effect=_find_nondict)
        with patch.object(txn.config.mongo, "async_db", mock_db):
            self.assertFalse(await txn.is_already_onchain(block_index=10))

        async def _find_twice(*a, **k):
            yield {
                "index": 1,
                "transactions": [
                    {"id": "other", "twice_prerotated_key_hash": "1Twice"}
                ],
            }

        mock_db.blocks.find = MagicMock(side_effect=_find_twice)
        with patch.object(txn.config.mongo, "async_db", mock_db):
            self.assertTrue(await txn.is_already_onchain(block_index=10))

        async def _find_pkh(*a, **k):
            yield {
                "index": 1,
                "transactions": [{"id": "other", "public_key_hash": "1Pkh"}],
            }

        mock_db.blocks.find = MagicMock(side_effect=_find_pkh)
        with patch.object(txn.config.mongo, "async_db", mock_db):
            self.assertTrue(await txn.is_already_onchain(block_index=10))

        async def _find_prev(*a, **k):
            yield {
                "index": 1,
                "transactions": [{"id": "other", "prev_public_key_hash": "1Prev"}],
            }

        mock_db.blocks.find = MagicMock(side_effect=_find_prev)
        with patch.object(txn.config.mongo, "async_db", mock_db):
            self.assertTrue(await txn.is_already_onchain(block_index=10))

        async def _find_nomatch(*a, **k):
            yield {
                "index": 1,
                "transactions": [{"id": "other", "public_key_hash": "zzz"}],
            }

        mock_db.blocks.find = MagicMock(side_effect=_find_nomatch)
        with patch.object(txn.config.mongo, "async_db", mock_db):
            self.assertFalse(await txn.is_already_onchain(block_index=10))

    def test_kel_walk_candidates_and_inception_tag(self):
        """Lines 1660/1674/1681-1683: walk candidates + inception tag helper."""
        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1T",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
            transaction_signature="self-sig",
        )
        self.assertIsNone(txn._inception_tag_of(None))
        bare = MagicMock()
        bare.inception_public_key_hash = None
        bare.public_key_hash = "1X"
        self.assertEqual(txn._inception_tag_of(bare), "1X")

        a = MagicMock()
        a.are_kel_fields_populated = lambda: True
        a.transaction_signature = "dup"
        a.public_key_hash = "A"
        b = MagicMock()
        b.are_kel_fields_populated = lambda: True
        b.transaction_signature = "dup"  # duplicate sig skipped
        b.public_key_hash = "B"
        self_dup = MagicMock()
        self_dup.are_kel_fields_populated = lambda: True
        self_dup.transaction_signature = "self-sig"
        self_dup.public_key_hash = "S"

        future = MagicMock()
        future.index = 50
        future.transactions = [a]

        prior = MagicMock()
        prior.index = 10
        prior.transactions = [b, self_dup]

        remaining = txn._kel_walk_candidates(
            batch_txns=[a, b, self_dup],
            extra_blocks=[future, prior],
            block_index=20,
        )
        # a from batch; b skipped as dup sig; self_dup skipped; future skipped;
        # prior re-adds nothing new for a/b
        self.assertEqual(len(remaining), 1)
        self.assertIs(remaining[0], a)

    def test_kel_tip_states_from_candidates_filters(self):
        """Lines 1708/1731/1739: tag mismatch, prev seed, empty state skip."""
        txn = Transaction(public_key=self.public_key)
        wrong = MagicMock()
        wrong.inception_public_key_hash = "OTHER"
        wrong.public_key_hash = "W"
        wrong.prev_public_key_hash = ""
        wrong.prerotated_key_hash = "Wp"

        empty = MagicMock()
        empty.inception_public_key_hash = "INC"
        empty.public_key_hash = None
        empty.prev_public_key_hash = ""
        empty.prerotated_key_hash = None

        root = MagicMock()
        root.inception_public_key_hash = "INC"
        root.public_key_hash = "R"
        root.prev_public_key_hash = "OUT"
        root.prerotated_key_hash = "Rp"

        child = MagicMock()
        child.inception_public_key_hash = "INC"
        child.public_key_hash = "C"
        child.prev_public_key_hash = "R"
        child.prerotated_key_hash = "Cp"

        tips, matching = txn._kel_tip_states_from_candidates(
            "INC", [wrong, empty, root, child], None
        )
        self.assertNotIn(wrong, matching)
        self.assertIn(root, matching)
        self.assertIn(child, matching)
        # empty state (None, None) skipped; root and parent-seed present
        self.assertTrue(any(s[0] == "R" for s in tips))
        self.assertTrue(any(s == ("OUT", "R") for s in tips))

    async def test_get_kel_cross_inception_from_extra_blocks_tag(self):
        """Lines 1796-1810: inception tag discovered via extra_blocks."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1T",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
        )
        txn.inception_public_key_hash = None

        tagged = MagicMock()
        tagged.inception_public_key_hash = "1Inc"
        tagged.are_kel_fields_populated = lambda: True
        tagged.transaction_signature = "t1"
        tagged.public_key_hash = "1On"
        tagged.prerotated_key_hash = "1Wanted"
        tagged.prev_public_key_hash = ""

        block = MagicMock()
        block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK + 6

        future = MagicMock()
        future.index = block.index + 50
        future.transactions = [tagged]

        prior = MagicMock()
        prior.index = block.index - 1
        prior.transactions = [tagged]

        latest = MagicMock(public_key_hash="1On", prerotated_key_hash="1Wanted")
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK + 10

        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                new=AsyncMock(return_value=latest),
            ):
                ok = await txn.get_kel_cross_key_auth(
                    "1Wanted",
                    block=block,
                    extra_blocks=[future, prior],
                )
        self.assertTrue(ok)

    async def test_get_kel_cross_inception_resolve_via_extra_blocks(self):
        """Lines 1843-1867: get_inception via extra_blocks cands."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1T",
            public_key_hash="",
            prev_public_key_hash="",
        )
        txn.inception_public_key_hash = None
        txn.public_key_hash = ""
        txn.prev_public_key_hash = ""

        t = MagicMock()
        t.prev_public_key_hash = None
        t.public_key_hash = None
        t.prerotated_key_hash = "1Hit"
        t.inception_public_key_hash = None
        t.are_kel_fields_populated = lambda: True
        t.transaction_signature = "t"

        block = MagicMock()
        block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK + 6

        future = MagicMock()
        future.index = block.index + 50
        future.transactions = [t]

        prior = MagicMock()
        prior.index = block.index - 1
        prior.transactions = [t]

        inception = MagicMock(
            inception_public_key_hash="1Inc",
            public_key_hash="1Inc",
            public_key=None,
        )
        latest = MagicMock(public_key_hash="1On", prerotated_key_hash="1Wanted")
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK + 10

        async def gi(address=None, **k):
            if address == "1Hit":
                return inception
            return None

        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                new=AsyncMock(side_effect=gi),
            ):
                with patch(
                    "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                    new=AsyncMock(return_value=latest),
                ):
                    ok = await txn.get_kel_cross_key_auth(
                        "1Wanted",
                        block=block,
                        extra_blocks=[future, prior],
                    )
        self.assertTrue(ok)

    async def test_get_kel_cross_empty_tips_and_pkh_match_and_walk(self):
        """Lines 1899/1909/1917-1918: empty tips, pkh match, BFS walk."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = Transaction(
            public_key=self.public_key,
            prerotated_key_hash="1Pre",
            twice_prerotated_key_hash="1T",
            public_key_hash="1Pk",
            prev_public_key_hash="1Prev",
            inception_public_key_hash="1Inc",
            transaction_signature="self",
        )
        mock_lb = MagicMock()
        mock_lb.block.index = CHAIN.KEL_CROSS_KEY_SPENDING_FORK + 5

        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                new=AsyncMock(return_value=None),
            ):
                with patch.object(
                    txn, "_kel_tip_states_from_candidates", return_value=([], [])
                ):
                    self.assertFalse(
                        await txn.get_kel_cross_key_auth("1X", mempool=True)
                    )

        # cur_pkh == address (coinbase path)
        latest = MagicMock(public_key_hash="1TipPkh", prerotated_key_hash="1TipPre")
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                new=AsyncMock(return_value=latest),
            ):
                self.assertTrue(
                    await txn.get_kel_cross_key_auth("1TipPkh", mempool=True)
                )

        # BFS walk via first branch (prev==cur_pkh & pkh==cur_pre). Include a
        # root so hop prevs are in-group and are not themselves tip seeds —
        # otherwise (T1,T2) is pre-seeded and 1917-1918 never runs.
        root = MagicMock()
        root.are_kel_fields_populated = lambda: True
        root.transaction_signature = "root"
        root.prev_public_key_hash = ""
        root.public_key_hash = "T0"
        root.prerotated_key_hash = "T1"
        root.inception_public_key_hash = "1Inc"

        hop1 = MagicMock()
        hop1.are_kel_fields_populated = lambda: True
        hop1.transaction_signature = "h1"
        hop1.prev_public_key_hash = "T0"
        hop1.public_key_hash = "T1"
        hop1.prerotated_key_hash = "T2"
        hop1.inception_public_key_hash = "1Inc"

        hop2 = MagicMock()
        hop2.are_kel_fields_populated = lambda: True
        hop2.transaction_signature = "h2"
        hop2.prev_public_key_hash = "T1"
        hop2.public_key_hash = "T2"
        hop2.prerotated_key_hash = "1Wanted"
        hop2.inception_public_key_hash = "1Inc"

        latest2 = MagicMock(public_key_hash="T0", prerotated_key_hash="T1")
        with patch.object(self.config, "LatestBlock", create=True, new=mock_lb):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog._latest_from_inception_tag",
                new=AsyncMock(return_value=latest2),
            ):
                ok = await txn.get_kel_cross_key_auth(
                    "1Wanted", mempool=True, batch_txns=[root, hop1, hop2]
                )
        self.assertTrue(ok)

    def test_kel_txn_matching_address(self):
        """Lines 1935-1957: match helper batch/extra/future skip."""
        txn = Transaction(public_key=self.public_key)
        no_kel = MagicMock()
        no_kel.are_kel_fields_populated = lambda: False

        hit = MagicMock()
        hit.are_kel_fields_populated = lambda: True
        hit.public_key_hash = "1Hit"
        hit.prerotated_key_hash = "x"
        hit.twice_prerotated_key_hash = "y"
        hit.prev_public_key_hash = "z"

        self.assertIs(
            txn._kel_txn_matching_address("1Hit", batch_txns=[no_kel, hit]), hit
        )

        future = MagicMock()
        future.index = 100
        future.transactions = [hit]
        prior = MagicMock()
        prior.index = 5
        prior.transactions = [hit]
        block = MagicMock()
        block.index = 10
        self.assertIsNone(
            txn._kel_txn_matching_address("1Hit", extra_blocks=[future], block=block)
        )
        self.assertIs(
            txn._kel_txn_matching_address(
                "1Hit", extra_blocks=[future, prior], block=block
            ),
            hit,
        )
        self.assertIsNone(txn._kel_txn_matching_address("missing", batch_txns=[hit]))

    async def test_output_owned_inbound_matching(self):
        """Lines 1988-2000: inbound same-inc and prerotated ownership."""
        from unittest.mock import AsyncMock, patch

        txn = Transaction(public_key=self.public_key)
        txn.inception_public_key_hash = "1Inc"

        inbound = MagicMock()
        inbound.are_kel_fields_populated = lambda: True
        inbound.inception_public_key_hash = "1Inc"
        inbound.public_key_hash = "1Out"
        inbound.prerotated_key_hash = "1OutPre"
        inbound.twice_prerotated_key_hash = "t"
        inbound.prev_public_key_hash = "p"

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
            new=AsyncMock(return_value=None),
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.is_same_kel",
                new=AsyncMock(return_value=False),
            ):
                self.assertTrue(
                    await txn._output_owned_by_kel_spender(
                        "1Out",
                        "spender",
                        True,
                        batch_txns=[inbound],
                    )
                )

        inbound2 = MagicMock()
        inbound2.are_kel_fields_populated = lambda: True
        inbound2.inception_public_key_hash = None  # untagged but same walk
        inbound2.public_key_hash = "1Pk"
        inbound2.prerotated_key_hash = "1OutPre"
        inbound2.twice_prerotated_key_hash = "t"
        inbound2.prev_public_key_hash = "p"

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
            new=AsyncMock(return_value=None),
        ):
            with patch(
                "yadacoin.core.keyeventlog.KeyEventLog.is_same_kel",
                new=AsyncMock(return_value=False),
            ):
                self.assertTrue(
                    await txn._output_owned_by_kel_spender(
                        "1OutPre",
                        "spender",
                        True,
                        batch_txns=[inbound2],
                    )
                )
