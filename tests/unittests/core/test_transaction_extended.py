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
from yadacoin.core.transaction import (
    ExternalInput,
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
# Input, Output, ExternalInput, Relationship
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


class TestExternalInput(TransactionTestCase):
    async def test_from_dict(self):
        ei = ExternalInput.from_dict(
            {
                "public_key": "pk1",
                "address": "addr1",
                "id": "txnid1",
                "signature": "sig1",
            }
        )
        self.assertEqual(ei.public_key, "pk1")
        self.assertEqual(ei.address, "addr1")
        self.assertEqual(ei.id, "txnid1")
        self.assertEqual(ei.signature, "sig1")

    async def test_to_dict(self):
        ei = ExternalInput(
            public_key="pk1", address="addr1", txn_id="txnid1", signature="sig1"
        )
        d = ei.to_dict()
        self.assertIn("public_key", d)
        self.assertIn("address", d)
        self.assertIn("id", d)
        self.assertIn("signature", d)


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
        mock_db.blocks.find_one = AsyncMock(return_value=None)
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
        mock_db.blocks.find_one = AsyncMock(return_value={"index": 1})
        with patch.object(txn.config.mongo, "async_db", new=mock_db):
            result = await txn.is_already_onchain()
        self.assertTrue(result)


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
    async def test_verify_signature_valid(self):
        """Test that a properly signed hash verifies correctly."""
        txn = await Transaction.generate(
            public_key=self.public_key,
            private_key=self.private_key,
            coinbase=True,
            outputs=[],
            inputs=[],
            version=2,
        )
        # Should not raise
        from bitcoin.wallet import P2PKHBitcoinAddress

        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))
        txn.verify_signature(address)

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


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
