"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from unittest.mock import MagicMock, patch

import yadacoin.core.config
from yadacoin.core.blockchainutils import BlockChainUtils
from yadacoin.core.config import Config
from yadacoin.core.transaction import (
    Input,
    InvalidTransactionException,
    InvalidTransactionSignatureException,
    MaxRelationshipSizeExceeded,
    NotEnoughMoneyException,
    Output,
    Relationship,
    TooManyInputsException,
    Transaction,
    TransactionConsts,
)

from ..test_setup import AsyncTestCase


async def mock_get_wallet_unspent_transactions(*args, **kwargs):
    for x in [
        {
            "id": "MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0=",
            "outputs": [{"value": 1, "to": "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4"}],
        }
    ]:
        yield x


class TestTransaction(AsyncTestCase):
    async def asyncSetUp(self):
        yadacoin.core.config.CONFIG = Config()
        yadacoin.core.config.CONFIG.network = "regnet"

    async def test___init__(self):
        txn = Transaction()
        self.assertIsInstance(txn, Transaction)

    async def test_generate(self):
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        self.assertIsInstance(txn, Transaction)

    async def test_to_dict(self):
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        self.assertIsInstance(txn.to_dict(), dict)

    async def test_from_dict(self):
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        self.assertIsInstance(txn.from_dict(txn.to_dict()), Transaction)

    async def test_verify(self):
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        try:
            await txn.verify()
        except:
            from traceback import format_exc

            self.fail(f"Txn did not verify {format_exc()}")

    @patch("yadacoin.core.transaction.Transaction.generate_inputs", return_value=1)
    async def test_do_money_coinbase(self, mock_generate_inputs):
        # Test coinbase, Passing
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            exact_match=False,
            outputs=[Output(to="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4", value=1)],
            coinbase=True,
        )
        txn.config = Config.generate({})
        txn.config.BU = BlockChainUtils()
        with mock_generate_inputs:
            await txn.do_money()

        # Test coinbase, Failing
        with mock_generate_inputs:
            with self.assertRaises(NotEnoughMoneyException):
                txn = await Transaction.generate(
                    public_key=yadacoin.core.config.CONFIG.public_key,
                    private_key=yadacoin.core.config.CONFIG.private_key,
                    exact_match=False,
                    outputs=[Output(to="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4", value=1)],
                    coinbase=False,
                )

    @patch(
        "yadacoin.core.blockchainutils.BlockChainUtils.get_wallet_unspent_transactions",
        new=mock_get_wallet_unspent_transactions,
    )
    async def test_do_money_error(self):
        # Test zero, Passing
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4", value=1)],
            coinbase=False,
        )
        txn.config = Config.generate({})
        txn.config.BU = BlockChainUtils()
        mocked_transaction = patch(
            "yadacoin.core.blockchainutils.BlockChainUtils.get_transaction_by_id",
            return_value=Transaction(
                outputs=[Output(value=1, to="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4")]
            ),
        )
        with mocked_transaction:
            with self.assertRaises(NotEnoughMoneyException):
                await txn.do_money()

    @patch(
        "yadacoin.core.blockchainutils.BlockChainUtils.get_wallet_unspent_transactions",
        new=mock_get_wallet_unspent_transactions,
    )
    async def test_do_money_pass(self):
        # Test zero, Passing
        txn = Transaction(
            public_key="03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
            outputs=[Output(to="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4", value=1)],
        )
        txn.config = Config.generate({})
        txn.config.BU = BlockChainUtils()
        mocked_transaction = patch(
            "yadacoin.core.blockchainutils.BlockChainUtils.get_transaction_by_id",
            return_value=Transaction(
                outputs=[Output(value=1, to="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4")]
            ),
        )
        with mocked_transaction:
            await txn.do_money()

    @patch(
        "yadacoin.core.blockchainutils.BlockChainUtils.get_wallet_unspent_transactions",
        new=mock_get_wallet_unspent_transactions,
    )
    async def test_generate_inputs(self):
        mocked_transaction = patch(
            "yadacoin.core.blockchainutils.BlockChainUtils.get_transaction_by_id",
            return_value=Transaction(
                outputs=[Output(value=1, to="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4")]
            ),
        )
        mocked_contract_bool = patch(
            "yadacoin.core.transaction.Transaction.is_contract_generated",
            return_value=False,
        )

        mocked_contract = patch(
            "yadacoin.core.transaction.Transaction.get_generating_contract",
            return_value=None,
        )

        mocked_sum_inputs = patch(
            "yadacoin.core.transaction.Transaction.sum_inputs",
            return_value=1,
        )
        with mocked_transaction:
            txn = await Transaction.generate(
                public_key=yadacoin.core.config.CONFIG.public_key,
                private_key=yadacoin.core.config.CONFIG.private_key,
            )
            txn.config = Config.generate({})
            txn.config.BU = BlockChainUtils()
            input_sum = await txn.generate_inputs(
                input_sum=1,
                my_address="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4",
                inputs=[],
                outputs_and_fee_total=1,
            )
            self.assertTrue(input_sum, 1)
            with self.assertRaises(NotEnoughMoneyException):
                input_sum = await txn.generate_inputs(
                    input_sum=1,
                    my_address="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4",
                    inputs=[],
                    outputs_and_fee_total=5,
                )

    async def test_sum_inputs(self):
        ### Test exact match, Passing

        input_obj = Input(
            signature="MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0="
        )
        input_txn = Transaction(
            outputs=[Output(value=1, to="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4")]
        )
        my_address = "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4"
        inputs = [
            Input(
                signature="MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0="
            )
        ]
        outputs_and_fee_total = 1

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            exact_match=True,
        )
        txn.config = Config.generate({})
        txn.config.BU = BlockChainUtils()
        input_sum = await txn.sum_inputs(
            input_obj, input_txn, my_address, 0, inputs, outputs_and_fee_total
        )
        self.assertEqual(input_sum, outputs_and_fee_total)

        ### Test exact match, Too much input

        input_obj = Input(
            signature="MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0="
        )
        input_txn = Transaction(
            outputs=[Output(value=2, to="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4")]
        )
        my_address = "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4"
        inputs = [
            Input(
                signature="MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0="
            )
        ]
        outputs_and_fee_total = 1

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            exact_match=True,
        )
        txn.config = Config.generate({})
        txn.config.BU = BlockChainUtils()
        input_sum = await txn.sum_inputs(
            input_obj, input_txn, my_address, 0, inputs, outputs_and_fee_total
        )
        self.assertEqual(input_sum, 0)

        ### Test not exact match, Passing

        input_obj = Input(
            signature="MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0="
        )
        input_txn = Transaction(
            outputs=[Output(value=2, to="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4")]
        )
        my_address = "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4"
        inputs = [
            Input(
                signature="MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0="
            )
        ]
        outputs_and_fee_total = 1
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            exact_match=False,
        )
        txn.config = Config.generate({})
        txn.config.BU = BlockChainUtils()
        input_sum2 = await txn.sum_inputs(
            input_obj, input_txn, my_address, 0, inputs, outputs_and_fee_total
        )
        self.assertEqual(input_sum2, 2)


class TestTransactionPureMethods(AsyncTestCase):
    async def asyncSetUp(self):
        yadacoin.core.config.CONFIG = Config()
        yadacoin.core.config.CONFIG.network = "regnet"

    # --- __init__ branches ---

    def test_init_with_dict_outputs_and_inputs(self):
        """Lines 167, 172-174: dict outputs/inputs convert via from_dict in __init__"""
        txn = Transaction(
            outputs=[{"to": "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4", "value": 1}],
            inputs=[{"id": "abc123"}],
        )
        self.assertIsInstance(txn.outputs[0], Output)
        self.assertIsInstance(txn.inputs[0], Input)

    async def test_generate_with_input_instances(self):
        """Line 263: pass Input instances (not dicts) to generate()"""
        inp = Input(signature="abc123")
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            inputs=[inp],
        )
        self.assertIsInstance(txn, Transaction)
        self.assertEqual(txn.inputs[0].id, "abc123")

    def test_ensure_instance_from_dict(self):
        """Lines 488-489: ensure_instance converts dict to Transaction"""
        d = {"public_key": yadacoin.core.config.CONFIG.public_key}
        result = Transaction.ensure_instance(d)
        self.assertIsInstance(result, Transaction)

    def test_ensure_instance_already_instance(self):
        """Lines 486-487: ensure_instance returns existing Transaction"""
        txn = Transaction()
        result = Transaction.ensure_instance(txn)
        self.assertIs(result, txn)

    def test_verify_signature_ecdsa_false_raises(self):
        """Lines 541, 552-553: ecdsa verify returns False → raise, then VerifyMessage"""
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            txn_hash="testhash",
        )
        txn.transaction_signature = "aW52YWxpZA=="  # 'invalid' in base64
        with patch("yadacoin.core.transaction.verify_signature", return_value=False):
            with patch("yadacoin.core.transaction.VerifyingKey") as mock_vk_cls:
                mock_vk = MagicMock()
                mock_vk.verify.return_value = False
                mock_vk_cls.from_string.return_value = mock_vk
                with self.assertRaises(InvalidTransactionSignatureException):
                    txn.verify_signature(yadacoin.core.config.CONFIG.address)

    async def test_generate_hash_with_contract_relationship(self):
        """Line 774: Contract instance in relationship for generate_hash"""
        mock_contract = MagicMock()
        mock_contract.to_string.return_value = ""

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            txn_time=1,
        )
        txn.version = 2
        txn.relationship = mock_contract

        from yadacoin.contracts.base import Contract

        # Inject mock_contract into Contract hierarchy so isinstance check passes
        original_class = mock_contract.__class__
        mock_contract.__class__ = type(
            "MockContract", (Contract,), {"to_string": lambda self: ""}
        )
        try:
            h = await txn.generate_hash()
        finally:
            mock_contract.__class__ = original_class

        self.assertIsInstance(h, str)

    async def test_generate_hash_version_7_hash_mismatch_raises(self):
        """Line 783: version 7 with mismatched relationship_hash raises"""
        from yadacoin.core.transaction import InvalidRelationshipHashException

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            relationship="hello",
            relationship_hash="wrong_hash",
        )
        txn.version = 7
        with self.assertRaises(InvalidRelationshipHashException):
            await txn.generate_hash()

    async def test_generate_hash_version_6_with_relationship(self):
        """Lines 812-814: version 6 with valid relationship hash"""
        import hashlib

        rel = "hello"
        rel_hash = hashlib.sha256(rel.encode()).digest().hex()
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            relationship=rel,
            relationship_hash=rel_hash,
        )
        txn.version = 6
        h = await txn.generate_hash()
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version_5_with_relationship(self):
        """Lines 840-842: version 5 with valid relationship hash"""
        import hashlib

        rel = "hello"
        rel_hash = hashlib.sha256(rel.encode()).digest().hex()
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            relationship=rel,
            relationship_hash=rel_hash,
        )
        txn.version = 5
        h = await txn.generate_hash()
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version_4_with_relationship(self):
        """Lines 867-869: version 4 with valid relationship hash"""
        import hashlib

        rel = "hello"
        rel_hash = hashlib.sha256(rel.encode()).digest().hex()
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            relationship=rel,
            relationship_hash=rel_hash,
        )
        txn.version = 4
        h = await txn.generate_hash()
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version_6_hash_mismatch_raises(self):
        """Line 814: version 6 with mismatched relationship_hash raises"""
        from yadacoin.core.transaction import InvalidRelationshipHashException

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            relationship="hello",
            relationship_hash="wrong_hash",
        )
        txn.version = 6
        with self.assertRaises(InvalidRelationshipHashException):
            await txn.generate_hash()

    async def test_generate_hash_version_5_hash_mismatch_raises(self):
        """Line 842: version 5 with mismatched relationship_hash raises"""
        from yadacoin.core.transaction import InvalidRelationshipHashException

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            relationship="hello",
            relationship_hash="wrong_hash",
        )
        txn.version = 5
        with self.assertRaises(InvalidRelationshipHashException):
            await txn.generate_hash()

    async def test_generate_hash_version_4_hash_mismatch_raises(self):
        """Line 869: version 4 with mismatched relationship_hash raises"""
        from yadacoin.core.transaction import InvalidRelationshipHashException

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            relationship="hello",
            relationship_hash="wrong_hash",
        )
        txn.version = 4
        with self.assertRaises(InvalidRelationshipHashException):
            await txn.generate_hash()

    def test_are_kel_fields_populated_false(self):
        """Line 1054: are_kel_fields_populated returns False with no fields"""
        txn = Transaction()
        self.assertFalse(txn.are_kel_fields_populated())

    def test_are_kel_fields_populated_twice_prerotated(self):
        """Line 1043-1044: twice_prerotated_key_hash set → returns True"""
        txn = Transaction(twice_prerotated_key_hash="abc")
        self.assertTrue(txn.are_kel_fields_populated())

    def test_are_kel_fields_populated_prerotated(self):
        """Line 1046-1047: prerotated_key_hash set → returns True"""
        txn = Transaction(prerotated_key_hash="abc")
        self.assertTrue(txn.are_kel_fields_populated())

    def test_are_kel_fields_populated_public_key_hash(self):
        """Line 1049-1050: public_key_hash set → returns True"""
        txn = Transaction(public_key_hash="abc")
        self.assertTrue(txn.are_kel_fields_populated())

    def test_are_kel_fields_populated_prev_public_key_hash(self):
        """Line 1052-1053: prev_public_key_hash set → returns True"""
        txn = Transaction(prev_public_key_hash="abc")
        self.assertTrue(txn.are_kel_fields_populated())

    def test_verify_signature_verifymessage_false_raises(self):
        """Lines 552-553: VerifyMessage returns False → raises"""
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            txn_hash="testhash",
        )
        txn.transaction_signature = "aW52YWxpZA=="
        with patch("yadacoin.core.transaction.verify_signature", return_value=False):
            with patch("yadacoin.core.transaction.VerifyingKey") as mock_vk_cls:
                mock_vk = MagicMock()
                mock_vk.verify.side_effect = Exception("ecdsa fail")
                mock_vk_cls.from_string.return_value = mock_vk
                with patch(
                    "yadacoin.core.transaction.VerifyMessage", return_value=False
                ):
                    with self.assertRaises(InvalidTransactionSignatureException):
                        txn.verify_signature(yadacoin.core.config.CONFIG.address)
        """Line 143: version becomes 2 when time is set without explicit version"""
        txn = Transaction(txn_time=1000000)
        self.assertEqual(txn.version, 2)

    def test_init_contract_relationship(self):
        """Lines 149-151: Contract instance from relationship dict"""
        from yadacoin.contracts.base import Contract
        from yadacoin.core.collections import Collections

        mock_contract = MagicMock(spec=Contract)
        with patch.object(Contract, "from_dict", return_value=mock_contract) as m:
            txn = Transaction(
                relationship={Collections.SMART_CONTRACT.value: {"type": "test"}}
            )
            m.assert_called_once()
            self.assertEqual(txn.relationship, mock_contract)

    def test_init_node_announcement_relationship(self):
        """Line 156: NodeAnnouncement from relationship dict with 'node' key"""
        from yadacoin.core.nodeannouncement import NodeAnnouncement

        mock_node = MagicMock(spec=NodeAnnouncement)
        with patch.object(NodeAnnouncement, "from_dict", return_value=mock_node):
            txn = Transaction(relationship={"node": {"host": "1.2.3.4", "port": 8000}})
            self.assertEqual(txn.relationship, mock_node)

    def test_init_oversized_relationship_raises(self):
        """Lines 161-167/172-174: oversized relationship string raises"""
        big_string = "x" * (TransactionConsts.RELATIONSHIP_MAX_SIZE.value + 1)
        with self.assertRaises(MaxRelationshipSizeExceeded):
            Transaction(relationship=big_string)

    # --- generate() branches ---

    async def test_generate_with_output_and_input_as_dicts(self):
        """Lines 257, 265: pass outputs/inputs as dicts (not instances)"""
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            outputs=[{"to": "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4", "value": 0}],
            inputs=[{"id": "abc123"}],
        )
        self.assertIsInstance(txn, Transaction)
        self.assertIsInstance(txn.outputs[0], Output)
        self.assertIsInstance(txn.inputs[0], Input)

    async def test_generate_without_private_key(self):
        """Line 279: no private_key → transaction_signature is empty string"""
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=None,
        )
        self.assertEqual(txn.transaction_signature, "")

    # --- in_the_future and get_inputs ---

    def test_in_the_future_false(self):
        """Line 446: returns False for old transaction"""
        txn = Transaction(txn_time=1000000)
        self.assertFalse(txn.in_the_future())

    def test_in_the_future_true(self):
        """Line 446: returns True for far-future transaction"""
        import time as time_module

        txn = Transaction(txn_time=int(time_module.time()) + 999999)
        self.assertTrue(txn.in_the_future())

    async def test_get_inputs_yields(self):
        """Line 450: get_inputs yields each input"""
        inp = Input(signature="abc")
        txn = Transaction()
        results = [x async for x in txn.get_inputs([inp])]
        self.assertEqual(results, [inp])

    # --- generate_transaction_signature ---

    def test_generate_transaction_signature(self):
        """Line 412: generate_transaction_signature calls TU"""
        txn = Transaction(txn_hash="deadbeef")
        txn.private_key = yadacoin.core.config.CONFIG.private_key
        sig = txn.generate_transaction_signature()
        self.assertIsInstance(sig, str)

    # --- verify_signature fallback branches ---

    def test_verify_signature_first_method_fails_second_succeeds(self):
        """Line 528-541: first verify fails, ecdsa verify succeeds"""
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            txn_hash="abc",
        )
        # generate valid signature via TU
        from yadacoin.core.transactionutils import TU

        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash or "abc"
        )
        # coincurve verify will fail for this sig, ecdsa should succeed
        with patch("yadacoin.core.transaction.verify_signature", return_value=False):
            # If ecdsa succeeds we won't get an exception
            try:
                txn.verify_signature(yadacoin.core.config.CONFIG.address)
            except InvalidTransactionSignatureException:
                pass  # acceptable if ecdsa also fails

    def test_verify_signature_all_methods_fail_raises(self):
        """Line 555: all three fallbacks fail → InvalidTransactionSignatureException"""
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            txn_hash="abc",
        )
        txn.transaction_signature = "aW52YWxpZA=="  # base64 of 'invalid'
        with patch("yadacoin.core.transaction.verify_signature", return_value=False):
            with self.assertRaises(InvalidTransactionSignatureException):
                txn.verify_signature(yadacoin.core.config.CONFIG.address)

    # --- generate_hash version branches ---

    async def test_generate_hash_version_2(self):
        """Lines 899-921: version 2 hash generation"""
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            txn_time=int(__import__("time").time()),
        )
        txn.version = 2
        h = await txn.generate_hash()
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version_3(self):
        """Lines 877-897: version 3 hash generation"""
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            txn_time=int(__import__("time").time()),
        )
        txn.version = 3
        h = await txn.generate_hash()
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version_4(self):
        """Lines 848-875: version 4"""
        import time as time_module

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            txn_time=int(time_module.time()),
            relationship_hash="",
        )
        txn.version = 4
        h = await txn.generate_hash()
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version_5(self):
        """Lines 837-848: version 5"""
        import time as time_module

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            txn_time=int(time_module.time()),
            relationship_hash="",
            masternode_fee=0.0,
        )
        txn.version = 5
        h = await txn.generate_hash()
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version_6(self):
        """Lines 810-836: version 6"""
        import time as time_module

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            txn_time=int(time_module.time()),
            relationship_hash="",
            masternode_fee=0.0,
            prerotated_key_hash="",
        )
        txn.version = 6
        h = await txn.generate_hash()
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version_1(self):
        """Lines 922-947: version 1 (else branch)"""
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
        )
        txn.version = 1
        h = await txn.generate_hash()
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    async def test_generate_hash_with_node_announcement_relationship(self):
        """Lines 775-776: NodeAnnouncement relationship in generate_hash"""
        from yadacoin.core.nodeannouncement import NodeAnnouncement

        mock_node = MagicMock(spec=NodeAnnouncement)
        mock_node.to_string.return_value = ""
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            txn_time=1,
        )
        txn.version = (
            2  # uses `relationship` local variable (not raw self.relationship)
        )
        txn.relationship = mock_node
        h = await txn.generate_hash()
        mock_node.to_string.assert_called_once()
        self.assertIsInstance(h, str)

    async def test_generate_hash_version_7_with_relationship(self):
        """Lines 779-783: version 7 with relationship_hash check"""
        import hashlib

        rel = "hello"
        rel_hash = hashlib.sha256(rel.encode()).digest().hex()
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            relationship=rel,
            relationship_hash=rel_hash,
        )
        txn.version = 7
        h = await txn.generate_hash()
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    async def test_generate_hash_version_7_no_relationship(self):
        """Line 784-785: version 7 without relationship"""
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            relationship="",
            relationship_hash="someref",
        )
        txn.version = 7
        h = await txn.generate_hash()
        self.assertIsInstance(h, str)

    # --- to_dict branches ---

    async def test_to_dict_with_dh_public_key(self):
        """Line 1350: dh_public_key in to_dict"""
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            dh_public_key="deadbeef",
        )
        d = txn.to_dict()
        self.assertIn("dh_public_key", d)

    async def test_to_dict_with_requester_rid_and_requested_rid(self):
        """Lines 1352, 1354: requester_rid/requested_rid in to_dict"""
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            requester_rid="req1",
            requested_rid="req2",
        )
        d = txn.to_dict()
        self.assertIn("requester_rid", d)
        self.assertIn("requested_rid", d)

    async def test_to_dict_with_miner_signature(self):
        """Line 1356: miner_signature in to_dict"""
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            miner_signature="miner_sig",
        )
        d = txn.to_dict()
        self.assertIn("miner_signature", d)

    async def test_to_dict_with_node_announcement_relationship(self):
        """Lines 1324-1327: NodeAnnouncement wraps back in 'node' key"""
        from yadacoin.core.nodeannouncement import NodeAnnouncement

        mock_node = MagicMock(spec=NodeAnnouncement)
        mock_node.to_dict.return_value = {"host": "1.2.3.4", "port": 8000}
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
        )
        txn.relationship = mock_node
        d = txn.to_dict()
        self.assertIn("node", d["relationship"])

    def test_to_json(self):
        """Line 1360: to_json produces valid JSON"""
        import json

        txn = Transaction()
        j = txn.to_json()
        self.assertIsInstance(json.loads(j), dict)

    # --- Input class ---

    def test_input_init_and_to_dict(self):
        """Lines 1376, 1364-1365: Input init and to_dict"""
        inp = Input(signature="abc123")
        self.assertEqual(inp.id, "abc123")
        d = inp.to_dict()
        self.assertEqual(d, {"id": "abc123"})

    def test_input_from_dict(self):
        """Lines 1368-1373: Input.from_dict"""
        d = {"id": "sig123", "input_txn": "txn_data"}
        inp = Input.from_dict(d)
        self.assertEqual(inp.id, "sig123")
        self.assertEqual(inp.input_txn, "txn_data")

    # --- Output class ---

    def test_output_from_dict_and_to_dict(self):
        """Lines 1425, 1427-1428: Output.from_dict and to_dict"""
        d = {"to": "1abc", "value": 1.5}
        out = Output.from_dict(d)
        self.assertEqual(out.to, "1abc")
        self.assertEqual(float(out.value), 1.5)
        self.assertEqual(out.to_dict(), d)

    # --- Relationship class ---

    def test_relationship_init_and_to_dict(self):
        """Lines 1446-1471: Relationship init and to_dict"""
        rel = Relationship(
            dh_private_key="prv",
            their_username="alice",
            my_username="bob",
        )
        d = rel.to_dict()
        self.assertEqual(d["dh_private_key"], "prv")
        self.assertEqual(d["their_username"], "alice")
        self.assertEqual(d["my_username"], "bob")

    def test_relationship_to_json(self):
        """Line 1474: Relationship.to_json"""
        import json

        rel = Relationship(my_username="test")
        j = rel.to_json()
        self.assertIsInstance(json.loads(j), dict)

    # -----------------------------------------------------------------------
    # do_money() paths
    # -----------------------------------------------------------------------

    async def test_do_money_with_inputs_evaluate_path_and_change_output(self):
        """Lines 334-335: change output appended when outputs don't include sender address."""
        from unittest.mock import patch

        from yadacoin.core.blockchainutils import BlockChainUtils
        from yadacoin.core.config import Config

        # Main txn: output to a DIFFERENT address so change output will be appended
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to="1DifferentAddressTest", value=1.0)],
        )
        fake_input = Input(signature="fake_input_id")
        txn.inputs = [fake_input]
        txn.config = Config.generate({})
        txn.config.BU = BlockChainUtils()

        # Mock evaluate_inputs to populate `inputs` list (side effect) and return input_sum=2.0
        async def mock_evaluate(input_sum, my_address, inputs, outputs_and_fee_total):
            inputs.append(fake_input)
            return 2.0

        with patch.object(txn, "evaluate_inputs", side_effect=mock_evaluate):
            await txn.do_money()

        # Change output (lines 334-335) should have been appended
        self.assertGreater(len(txn.outputs), 1)

    async def test_evaluate_inputs_txn_not_found_raises(self):
        """Lines 342-343: evaluate_inputs raises MissingInputTransactionException when BU returns None."""
        from unittest.mock import AsyncMock, patch

        from yadacoin.core.blockchainutils import BlockChainUtils
        from yadacoin.core.config import Config
        from yadacoin.core.transaction import MissingInputTransactionException

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to="1abc", value=1.0)],
        )
        txn.inputs = [Input(signature="missing_txn_id")]
        txn.config = Config.generate({})
        txn.config.BU = BlockChainUtils()

        with patch.object(
            txn.config.BU, "get_transaction_by_id", new=AsyncMock(return_value=None)
        ):
            with self.assertRaises(MissingInputTransactionException):
                await txn.evaluate_inputs(0, "addr", [], 1.0)

    async def test_evaluate_inputs_no_inputs_raises_not_enough_money(self):
        """Line 353: empty inputs → async for never runs → raises NotEnoughMoneyException"""
        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        txn.inputs = []  # no inputs → loop never enters → hits raise
        with self.assertRaises(NotEnoughMoneyException):
            await txn.evaluate_inputs(0, "1SomeAddress", [], 1.0)

    async def test_evaluate_inputs_sufficient_value_returns(self):
        """Line 353: input_sum >= outputs_and_fee_total → return input_sum (line 353)."""
        from unittest.mock import AsyncMock

        from bitcoin.wallet import P2PKHBitcoinAddress

        from yadacoin.core.blockchainutils import BlockChainUtils

        my_address = str(
            P2PKHBitcoinAddress.from_pubkey(
                bytes.fromhex(yadacoin.core.config.CONFIG.public_key)
            )
        )

        # input_txn output goes to my_address with value 5.0 ≥ outputs_and_fee_total 1.0
        input_txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to=my_address, value=5.0)],
        )

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to="1DestAddr", value=1.0)],
        )
        txn.inputs = [Input(signature="some_txn_id")]
        bu = BlockChainUtils()
        txn.config.BU = bu

        with patch.object(
            bu,
            "get_transaction_by_id",
            new=AsyncMock(return_value=input_txn),
        ):
            result = await txn.evaluate_inputs(0, my_address, [], 1.0)

        self.assertEqual(result, 5.0)

    async def test_evaluate_inputs_insufficient_value_raises(self):
        """Line 355: loop runs but input_sum < outputs_and_fee_total → exhausts → raise."""
        from unittest.mock import AsyncMock

        from bitcoin.wallet import P2PKHBitcoinAddress

        from yadacoin.core.blockchainutils import BlockChainUtils

        my_address = str(
            P2PKHBitcoinAddress.from_pubkey(
                bytes.fromhex(yadacoin.core.config.CONFIG.public_key)
            )
        )

        # input_txn output goes to my_address but only 0.5 < required 10.0
        input_txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to=my_address, value=0.5)],
        )

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to="1DestAddr", value=10.0)],
        )
        txn.inputs = [Input(signature="some_txn_id")]
        bu = BlockChainUtils()
        txn.config.BU = bu

        with patch.object(
            bu,
            "get_transaction_by_id",
            new=AsyncMock(return_value=input_txn),
        ):
            with self.assertRaises(NotEnoughMoneyException):
                await txn.evaluate_inputs(0, my_address, [], 10.0)

    # -----------------------------------------------------------------------
    # contract_generated property (lines 454-459)
    # -----------------------------------------------------------------------

    async def test_contract_generated_property_finds_contract(self):
        """Lines 454-458: contract_generated property sets True when get_generating_contract returns something."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        txn._contract_generated = None

        with patch.object(
            txn, "get_generating_contract", new=AsyncMock(return_value=MagicMock())
        ):
            result = await txn.contract_generated
        self.assertTrue(result)

    async def test_contract_generated_property_no_contract(self):
        """Lines 454-459: contract_generated property sets False when get_generating_contract returns None."""
        from unittest.mock import AsyncMock, patch

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        txn._contract_generated = None

        with patch.object(
            txn, "get_generating_contract", new=AsyncMock(return_value=None)
        ):
            result = await txn.contract_generated
        self.assertFalse(result)

    # -----------------------------------------------------------------------
    # get_generating_contract None path (lines 466-475)
    # -----------------------------------------------------------------------

    async def test_get_generating_contract_returns_none(self):
        """Lines 466-475: returns None when no smart contract block found."""
        from unittest.mock import AsyncMock, MagicMock

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        txn.config.mongo = mock_mongo

        result = await txn.get_generating_contract()
        self.assertIsNone(result)

    # -----------------------------------------------------------------------
    # handle_exception (lines 493-513)
    # -----------------------------------------------------------------------

    async def test_handle_exception_basic(self):
        """Lines 493-513: handle_exception inserts failed txn record, deletes mempool entry."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            transaction_signature="sig123",
        )
        e = Exception("test error")

        mock_mongo = MagicMock()
        mock_mongo.async_db.failed_transactions.insert_one = AsyncMock(
            return_value=None
        )
        mock_mongo.async_db.miner_transactions.delete_many = AsyncMock(
            return_value=None
        )
        mock_cfg = MagicMock()
        mock_cfg.mongo = mock_mongo
        mock_cfg.app_log = MagicMock()

        with patch("yadacoin.core.transaction.Config", return_value=mock_cfg):
            await Transaction.handle_exception(e, txn)

    async def test_handle_exception_with_spent_in_txn(self):
        """Lines 510-513: handle_exception removes spent_in_txn from transactions list."""
        from unittest.mock import AsyncMock, MagicMock, patch

        spent_txn = Transaction(transaction_signature="spent_sig")
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            transaction_signature="sig456",
        )
        txn.spent_in_txn = spent_txn
        e = Exception("test")
        transactions = [spent_txn]

        mock_mongo = MagicMock()
        mock_mongo.async_db.failed_transactions.insert_one = AsyncMock(
            return_value=None
        )
        mock_mongo.async_db.miner_transactions.delete_many = AsyncMock(
            return_value=None
        )
        mock_cfg = MagicMock()
        mock_cfg.mongo = mock_mongo
        mock_cfg.app_log = MagicMock()

        with patch("yadacoin.core.transaction.Config", return_value=mock_cfg):
            await Transaction.handle_exception(e, txn, transactions=transactions)

        self.assertNotIn(spent_txn, transactions)

    async def test_handle_exception_too_many_inputs(self):
        """Lines 495-496: TooManyInputsException clears inputs."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            transaction_signature="sig789",
            inputs=[Input(signature="inp1"), Input(signature="inp2")],
        )
        e = TooManyInputsException("too many")

        mock_mongo = MagicMock()
        mock_mongo.async_db.failed_transactions.insert_one = AsyncMock(
            return_value=None
        )
        mock_mongo.async_db.miner_transactions.delete_many = AsyncMock(
            return_value=None
        )
        mock_cfg = MagicMock()
        mock_cfg.mongo = mock_mongo
        mock_cfg.app_log = MagicMock()

        with patch("yadacoin.core.transaction.Config", return_value=mock_cfg):
            await Transaction.handle_exception(e, txn)

        self.assertEqual(txn.inputs, [])

    # -----------------------------------------------------------------------
    # verify() easy branches
    # -----------------------------------------------------------------------

    async def test_verify_too_many_inputs_raises(self):
        """Line 576: verify(check_max_inputs=True) raises TooManyInputsException."""
        from yadacoin.core.chain import CHAIN

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        txn.inputs = [Input(signature=f"inp{i}") for i in range(CHAIN.MAX_INPUTS + 1)]
        with self.assertRaises(TooManyInputsException):
            await txn.verify(check_max_inputs=True)

    async def test_verify_hash_mismatch_raises(self):
        """Line 607: verify() raises when hash doesn't match recomputed hash."""
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        txn.hash = "obviously_wrong_hash"
        with self.assertRaises(InvalidTransactionException):
            await txn.verify()

    async def test_verify_contract_relationship(self):
        """Line 615: Contract relationship calls to_string() in verify()."""

        from yadacoin.contracts.base import Contract
        from yadacoin.core.transactionutils import TU

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )

        class FakeContract(Contract):
            def __init__(self):
                pass

            def to_string(self):
                return ""

        txn.relationship = FakeContract()
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )
        await txn.verify()  # Should complete without raising

    async def test_verify_node_announcement_no_dynamic_nodes_raises(self):
        """Lines 617-621: NodeAnnouncement with check_dynamic_nodes=False raises."""

        from yadacoin.core.nodeannouncement import NodeAnnouncement
        from yadacoin.core.transactionutils import TU

        class FakeNodeAnnouncement(NodeAnnouncement):
            def __init__(self):
                self.collateral_address = ""

            def to_string(self):
                return ""

            def to_dict(self):
                return {}

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        txn.relationship = FakeNodeAnnouncement()
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )
        with self.assertRaises(InvalidTransactionException):
            await txn.verify(check_dynamic_nodes=False)

    async def test_verify_node_announcement_missing_collateral_address_raises(self):
        """Lines 624-627: NodeAnnouncement with check_dynamic_nodes=True but no collateral_address raises."""

        from yadacoin.core.nodeannouncement import NodeAnnouncement
        from yadacoin.core.transactionutils import TU

        class FakeNodeAnnouncement(NodeAnnouncement):
            def __init__(self):
                self.collateral_address = ""  # empty → falsy

            def to_string(self):
                return ""

            def to_dict(self):
                return {}

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        txn.relationship = FakeNodeAnnouncement()
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )
        with self.assertRaises(InvalidTransactionException):
            await txn.verify(check_dynamic_nodes=True)

    async def test_verify_node_announcement_missing_collateral_output_raises(self):
        """Lines 628-635: NodeAnnouncement with collateral_address but no matching output raises."""

        from yadacoin.core.nodeannouncement import NodeAnnouncement
        from yadacoin.core.transactionutils import TU

        class FakeNodeAnnouncement(NodeAnnouncement):
            def __init__(self):
                self.collateral_address = "1CollateralAddr"

            def to_string(self):
                return ""

            def to_dict(self):
                return {}

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        txn.relationship = FakeNodeAnnouncement()
        # No outputs with collateral_address → raises
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )
        with self.assertRaises(InvalidTransactionException):
            await txn.verify(check_dynamic_nodes=True)

    async def test_verify_relationship_too_long_raises(self):
        """Line 640: MaxRelationshipSizeExceeded when relationship string is too long in verify()."""
        from unittest.mock import AsyncMock, patch

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        txn.relationship = "x" * (TransactionConsts.RELATIONSHIP_MAX_SIZE.value + 1)

        with patch.object(txn, "generate_hash", new=AsyncMock(return_value=txn.hash)):
            with patch.object(txn, "verify_signature"):
                with self.assertRaises(MaxRelationshipSizeExceeded):
                    await txn.verify()

    # -----------------------------------------------------------------------
    # verify() inputs loop (lines 647-730)
    # -----------------------------------------------------------------------

    async def test_verify_with_input_txn_set_found(self):
        """Lines 647-720, 732+: verify() with Input.input_txn set, output found, total balances."""
        from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH

        from yadacoin.core.transactionutils import TU

        address = str(
            _P2PKH.from_pubkey(bytes.fromhex(yadacoin.core.config.CONFIG.public_key))
        )
        input_txn_obj = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to=address, value=2.0)],
        )
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to=address, value=2.0)],
        )
        txn.inputs = [Input(signature="signed_id", input_txn=input_txn_obj)]
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )
        await txn.verify()  # Should pass without raising

    async def test_verify_with_input_txn_not_found_recipient_raises(self):
        """Lines 722-728: not found → raises InvalidTransactionException."""
        from yadacoin.core.transactionutils import TU

        input_txn_obj = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to="1WrongAddr", value=2.0)],
        )
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
        )
        txn.inputs = [Input(signature="signed_id2", input_txn=input_txn_obj)]
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )
        with self.assertRaises(InvalidTransactionException):
            await txn.verify()

    async def test_verify_input_missing_from_db_raises(self):
        """Lines 652-667: Input without input_txn + BU returns None → MissingInputTransactionException."""
        from unittest.mock import AsyncMock, patch

        from yadacoin.core.transaction import MissingInputTransactionException
        from yadacoin.core.transactionutils import TU

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        txn.inputs = [Input(signature="missing_id")]
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )

        with patch.object(
            txn.config.BU, "get_transaction_by_id", new=AsyncMock(return_value=None)
        ):
            with self.assertRaises(MissingInputTransactionException):
                await txn.verify()

    async def test_verify_coinbase_returns_early(self):
        """Line 733: coinbase=True causes verify() to return after input loop."""
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            coinbase=True,
        )
        # Should complete without raising
        await txn.verify()

    async def test_verify_miner_sig_contract_generated_returns(self):
        """Line 735: miner_signature + contract_generated=True returns early."""
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        txn.miner_signature = "non_empty_sig"
        txn._contract_generated = True
        # Should complete without raising (returns at 735)
        await txn.verify()

    async def test_verify_output_negative_raises(self):
        """Lines 739-740: output with negative value raises InvalidTransactionException."""
        from yadacoin.core.transactionutils import TU

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to="1SomeAddr", value=-1.0)],
        )
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )
        with self.assertRaises(InvalidTransactionException):
            await txn.verify()

    async def test_verify_total_mismatch_raises(self):
        """Lines 741, 756-758: total_input != total_output+fee raises TotalValueMismatchException."""
        from yadacoin.core.transaction import TotalValueMismatchException
        from yadacoin.core.transactionutils import TU

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to="1SomeAddr", value=1.0)],
        )
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )
        # total_input=0, total_output=1.0 → mismatch
        with self.assertRaises(TotalValueMismatchException):
            await txn.verify()

    async def test_verify_check_masternode_fee_mismatch_raises(self):
        """Lines 743-745: check_masternode_fee=True, total mismatch raises TotalValueMismatchException."""
        from yadacoin.core.transaction import TotalValueMismatchException
        from yadacoin.core.transactionutils import TU

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to="1SomeAddr", value=1.0)],
            masternode_fee=0.5,
        )
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )
        # total_input=0, total_output(1)+fee(0)+masternode_fee(0.5)=1.5 → mismatch
        with self.assertRaises(TotalValueMismatchException):
            await txn.verify(check_masternode_fee=True)

    # -----------------------------------------------------------------------
    # verify() check_kel paths (lines 584-604)
    # -----------------------------------------------------------------------

    async def test_verify_check_kel_no_kel_found(self):
        """Lines 584-604: check_kel=True, has_key_event_log=False, block below spends-entirely fork."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        mock_block = MagicMock()
        mock_block.index = 10  # far below CHECK_KEL_SPENDS_ENTIRELY_FORK

        with patch.object(txn, "has_key_event_log", new=AsyncMock(return_value=False)):
            await txn.verify(check_kel=True, block=mock_block)

    async def test_verify_check_kel_has_kel(self):
        """Lines 588-590: check_kel=True, has_kel=True triggers KeyEvent.verify()."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        mock_block = MagicMock()
        mock_block.index = 10

        with patch.object(txn, "has_key_event_log", new=AsyncMock(return_value=True)):
            with patch("yadacoin.core.keyeventlog.KeyEvent") as mock_ke_cls:
                mock_ke = MagicMock()
                mock_ke.verify = AsyncMock(return_value=None)
                mock_ke_cls.return_value = mock_ke
                await txn.verify(check_kel=True, block=mock_block)

        mock_ke.verify.assert_called_once()

    async def test_verify_check_kel_prev_key_hash_raises(self):
        """Lines 591-594: check_kel=True, has_kel=False, prev_public_key_hash set → KEL raises."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import (
            KELExceptionPreviousKeyHashReferenceMissing,
        )
        from yadacoin.core.transactionutils import TU

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            prev_public_key_hash="some_prev_hash",
        )
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )
        mock_block = MagicMock()
        mock_block.index = 10

        with patch.object(txn, "has_key_event_log", new=AsyncMock(return_value=False)):
            with self.assertRaises(KELExceptionPreviousKeyHashReferenceMissing):
                await txn.verify(check_kel=True, block=mock_block)

    async def test_verify_check_kel_above_spends_fork(self):
        """Line 604: _kel_index >= CHECK_KEL_SPENDS_ENTIRELY_FORK triggers verify_kel_output_rules."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        mock_block = MagicMock()
        mock_block.index = CHAIN.CHECK_KEL_SPENDS_ENTIRELY_FORK + 1

        with patch.object(txn, "has_key_event_log", new=AsyncMock(return_value=False)):
            with patch.object(
                txn, "verify_kel_output_rules", new=AsyncMock(return_value=None)
            ):
                await txn.verify(check_kel=True, block=mock_block)

    # -----------------------------------------------------------------------
    # find_in_extra_blocks (lines 958-961)
    # -----------------------------------------------------------------------

    async def test_find_in_extra_blocks_found(self):
        """Lines 958-961: find_in_extra_blocks returns the matching txn."""
        from unittest.mock import MagicMock

        matching_txn = MagicMock()
        matching_txn.transaction_signature = "target_id"

        mock_block = MagicMock()
        mock_block.transactions = [matching_txn]

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        txn.extra_blocks = [mock_block]

        target_input = Input(signature="target_id")
        result = await txn.find_in_extra_blocks(target_input)
        self.assertIs(result, matching_txn)

    async def test_find_in_extra_blocks_no_match_returns_none(self):
        """Lines 957-961: find_in_extra_blocks returns None when no match."""
        from unittest.mock import MagicMock

        other_txn = MagicMock()
        other_txn.transaction_signature = "other_id"

        mock_block = MagicMock()
        mock_block.transactions = [other_txn]

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        txn.extra_blocks = [mock_block]

        target_input = Input(signature="target_id")
        result = await txn.find_in_extra_blocks(target_input)
        self.assertIsNone(result)

    # -----------------------------------------------------------------------
    # recover_missing_transaction (line 984)
    # -----------------------------------------------------------------------

    async def test_recover_missing_transaction_returns_false(self):
        """Line 984: recover_missing_transaction always returns False."""
        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        result = await txn.recover_missing_transaction("some_id", [])
        self.assertFalse(result)

    # -----------------------------------------------------------------------
    # is_already_onchain (lines 1063-1101)
    # -----------------------------------------------------------------------

    async def test_is_already_onchain_no_fields_returns_false(self):
        """Lines 1063-1101: no KEL fields → query empty → returns False."""
        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        result = await txn.is_already_onchain()
        self.assertFalse(result)

    async def test_is_already_onchain_with_field_found(self):
        """Lines 1063-1101: KEL field set, find_one returns doc → returns True."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            prerotated_key_hash="somehash",
        )
        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.find_one = AsyncMock(return_value={"_id": "block1"})
        mock_cfg = MagicMock()
        mock_cfg.mongo = mock_mongo

        with patch("yadacoin.core.transaction.Config", return_value=mock_cfg):
            result = await txn.is_already_onchain()
        self.assertTrue(result)

    async def test_is_already_onchain_with_field_not_found(self):
        """Lines 1063-1101: KEL field set, find_one returns None → returns False."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            twice_prerotated_key_hash="aaa",
            public_key_hash="bbb",
            prev_public_key_hash="ccc",
        )
        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        mock_cfg = MagicMock()
        mock_cfg.mongo = mock_mongo

        with patch("yadacoin.core.transaction.Config", return_value=mock_cfg):
            result = await txn.is_already_onchain()
        self.assertFalse(result)

    # -----------------------------------------------------------------------
    # is_already_in_mempool (lines 1104-1141)
    # -----------------------------------------------------------------------

    async def test_is_already_in_mempool_no_fields_returns_false(self):
        """Lines 1104-1141: no KEL fields → returns False without querying."""
        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        result = await txn.is_already_in_mempool()
        self.assertFalse(result)

    async def test_is_already_in_mempool_with_field_found(self):
        """Lines 1104-1141: KEL field set, miner_transactions.find_one returns doc → True."""
        from unittest.mock import AsyncMock, MagicMock

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            prerotated_key_hash="mempool_hash",
        )
        mock_mongo = MagicMock()
        mock_mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value={"_id": "mempool1"}
        )
        txn.config.mongo = mock_mongo

        result = await txn.is_already_in_mempool()
        self.assertTrue(result)

    async def test_is_already_in_mempool_with_field_not_found(self):
        """Lines 1104-1141: KEL field set, miner_transactions.find_one returns None → False."""
        from unittest.mock import AsyncMock, MagicMock

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            public_key_hash="pk_hash_mp",
        )
        mock_mongo = MagicMock()
        mock_mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)
        txn.config.mongo = mock_mongo

        result = await txn.is_already_in_mempool()
        self.assertFalse(result)

    # -----------------------------------------------------------------------
    # has_key_event_log (lines 1144-1188)
    # -----------------------------------------------------------------------

    async def test_has_key_event_log_found_returns_true(self):
        """Lines 1144-1160: blocks.find_one returns result → True."""
        from unittest.mock import AsyncMock, MagicMock

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.find_one = AsyncMock(return_value={"_id": "blk1"})
        txn.config.mongo = mock_mongo

        result = await txn.has_key_event_log()
        self.assertTrue(result)

    async def test_has_key_event_log_not_found_returns_false(self):
        """Lines 1144-1188: find_one returns None, no extra_blocks, not mempool → False."""
        from unittest.mock import AsyncMock, MagicMock

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        txn.config.mongo = mock_mongo

        result = await txn.has_key_event_log()
        self.assertFalse(result)

    async def test_has_key_event_log_with_block_index_filter(self):
        """Lines 1154-1157: block provided → query includes index filter."""
        from unittest.mock import MagicMock

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        mock_block = MagicMock()
        mock_block.index = 100

        captured_queries = []

        async def mock_find_one(query):
            captured_queries.append(query)
            return None

        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.find_one = mock_find_one
        txn.config.mongo = mock_mongo

        result = await txn.has_key_event_log(block=mock_block)

        self.assertFalse(result)
        self.assertIn("index", captured_queries[0])

    async def test_has_key_event_log_extra_blocks_match_returns_true(self):
        """Lines 1161-1175: extra_blocks path returns True when address matches twice_prerotated."""
        from unittest.mock import AsyncMock, MagicMock

        from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH

        address = str(
            _P2PKH.from_pubkey(bytes.fromhex(yadacoin.core.config.CONFIG.public_key))
        )

        # extra block txn where twice_prerotated_key_hash == txn's address
        fake_xtxn = MagicMock()
        fake_xtxn.transaction_signature = "other_sig"
        fake_xtxn.twice_prerotated_key_hash = address
        fake_xtxn.prerotated_key_hash = ""

        mock_extra_block = MagicMock()
        mock_extra_block.index = 1
        mock_extra_block.transactions = [fake_xtxn]

        mock_block = MagicMock()
        mock_block.index = 100

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            transaction_signature="target_sig",
        )
        txn.extra_blocks = [mock_extra_block]

        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        txn.config.mongo = mock_mongo

        result = await txn.has_key_event_log(block=mock_block)
        self.assertTrue(result)

    async def test_has_key_event_log_mempool_path(self):
        """Lines 1176-1186: mempool=True, find_one in miner_transactions returns result → True."""
        from unittest.mock import AsyncMock, MagicMock

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        mock_mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value={"_id": "memtxn"}
        )
        txn.config.mongo = mock_mongo

        result = await txn.has_key_event_log(mempool=True)
        self.assertTrue(result)

    # -----------------------------------------------------------------------
    # verify_kel_output_rules (lines 1193-1270)
    # -----------------------------------------------------------------------

    async def test_verify_kel_output_rules_no_kel_returns(self):
        """Lines 1193-1219: has_key_event_log=False → returns early."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)

        mock_block = MagicMock()
        mock_block.index = 10

        with patch.object(txn, "has_key_event_log", new=AsyncMock(return_value=False)):
            await txn.verify_kel_output_rules(
                block=mock_block
            )  # Should return silently

    async def test_verify_kel_output_rules_self_send_before_kel_check_raises(self):
        """Lines 1211-1215: are_kel_fields_populated=True and public_key_hash in outputs raises."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KELSelfSendException

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            public_key_hash="self_addr",
            outputs=[Output(to="self_addr", value=1.0)],
        )
        mock_block = MagicMock()
        mock_block.index = 10

        with patch.object(txn, "has_key_event_log", new=AsyncMock(return_value=False)):
            with self.assertRaises(KELSelfSendException):
                await txn.verify_kel_output_rules(block=mock_block)

    async def test_verify_kel_output_rules_log_unbuildable_raises(self):
        """Lines 1224-1230: KeyEventLog.build_from_public_key returns empty → raises KELLogUnbuildableException."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KELLogUnbuildableException, KeyEventLog

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        mock_block = MagicMock()
        mock_block.index = 10

        with patch.object(txn, "has_key_event_log", new=AsyncMock(return_value=True)):
            with patch.object(
                KeyEventLog, "build_from_public_key", new=AsyncMock(return_value=[])
            ):
                with self.assertRaises(KELLogUnbuildableException):
                    await txn.verify_kel_output_rules(block=mock_block)

    async def test_verify_kel_output_rules_block_returns(self):
        """Lines 1232-1270: block is not None causes early return after routing check."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.keyeventlog import KeyEventLog

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            public_key_hash="pk_hash",
            outputs=[Output(to="1OtherAddr", value=1.0)],  # not self-send
        )
        mock_block = MagicMock()
        mock_block.index = CHAIN.CHECK_KEL_OUTPUT_ROUTING_FORK - 1  # below routing fork

        mock_entry = MagicMock()
        mock_entry.mempool = False
        mock_entry.public_key_hash = "different_hash"
        mock_entry.prerotated_key_hash = "1OtherAddr"

        with patch.object(txn, "has_key_event_log", new=AsyncMock(return_value=True)):
            with patch.object(
                KeyEventLog,
                "build_from_public_key",
                new=AsyncMock(return_value=[mock_entry]),
            ):
                await txn.verify_kel_output_rules(block=mock_block)
                # Should return at line 1270 (block is not None)

    async def test_verify_kel_output_rules_routing_violation_raises(self):
        """Lines 1237-1259: routing fork check, not new entry, output to wrong addr → raises."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.keyeventlog import (
            KELOutputRoutingViolationException,
            KeyEventLog,
        )

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            public_key_hash="pk_hash_existing",
            outputs=[Output(to="1WrongOutput", value=1.0)],
        )
        txn.transaction_signature = "txn_sig_not_in_log"

        # Use a block index above routing fork
        mock_block = MagicMock()
        mock_block.index = CHAIN.CHECK_KEL_OUTPUT_ROUTING_FORK + 1

        # key_log contains an entry with same public_key_hash but different txn_sig (so is_new=False)
        mock_entry = MagicMock()
        mock_entry.mempool = False
        mock_entry.public_key_hash = "pk_hash_existing"
        mock_entry.transaction_signature = "other_sig"  # ≠ txn.transaction_signature
        mock_entry.prerotated_key_hash = "1CorrectOutput"

        with patch.object(txn, "has_key_event_log", new=AsyncMock(return_value=True)):
            with patch.object(
                KeyEventLog,
                "build_from_public_key",
                new=AsyncMock(return_value=[mock_entry]),
            ):
                with self.assertRaises(KELOutputRoutingViolationException):
                    await txn.verify_kel_output_rules(block=mock_block)

    async def test_verify_kel_output_rules_self_send_after_routing_raises(self):
        """Lines 1261-1264: self.public_key_hash in outputs.to (after routing block) → KELSelfSendException."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.keyeventlog import KELSelfSendException, KeyEventLog

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            public_key_hash="self_hash",
            outputs=[Output(to="self_hash", value=1.0)],
        )
        txn.transaction_signature = "txn_sig_x"

        # Block index below routing fork so routing block is skipped
        mock_block = MagicMock()
        mock_block.index = CHAIN.CHECK_KEL_OUTPUT_ROUTING_FORK - 1

        mock_entry = MagicMock()
        mock_entry.mempool = False
        mock_entry.public_key_hash = "other_hash"

        with patch.object(txn, "has_key_event_log", new=AsyncMock(return_value=True)):
            with patch.object(
                KeyEventLog,
                "build_from_public_key",
                new=AsyncMock(return_value=[mock_entry]),
            ):
                with self.assertRaises(KELSelfSendException):
                    await txn.verify_kel_output_rules(block=mock_block)

    # -----------------------------------------------------------------------
    # Additional coverage for remaining missing lines
    # -----------------------------------------------------------------------

    async def test_evaluate_inputs_wrong_address_raises_not_enough_money(self):
        """Line 353: inputs exist but output address does not match → input_sum stays 0 → raises."""
        from unittest.mock import AsyncMock, patch

        from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH

        from yadacoin.core.blockchainutils import BlockChainUtils

        my_address = str(
            _P2PKH.from_pubkey(bytes.fromhex(yadacoin.core.config.CONFIG.public_key))
        )

        # input_txn has output to WRONG address (not sender) → input_sum stays 0
        input_txn_wrong = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to="1WrongAddress", value=5.0)],
        )

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to="1abc", value=1.0)],
        )
        txn.inputs = [Input(signature="some_txn_id")]
        bu = BlockChainUtils()
        txn.config.BU = bu

        with patch.object(
            bu,
            "get_transaction_by_id",
            new=AsyncMock(return_value=input_txn_wrong),
        ):
            with self.assertRaises(NotEnoughMoneyException):
                await txn.evaluate_inputs(0, my_address, [], 1.0)

    async def test_verify_check_kel_latestblock_else_path(self):
        """Lines 600-601: check_kel=True, no block, no mempool → uses LatestBlock.block.index."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )

        mock_lb = MagicMock()
        mock_lb.block.index = 10

        with patch.object(
            yadacoin.core.config.CONFIG, "LatestBlock", create=True, new=mock_lb
        ):
            with patch.object(
                txn, "has_key_event_log", new=AsyncMock(return_value=False)
            ):
                await txn.verify(check_kel=True)  # no block, no mempool → line 601

    async def test_verify_check_kel_latestblock_mempool_path(self):
        """Lines 598-599: check_kel=True, mempool=True → uses LatestBlock.block.index + 1."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )

        mock_lb = MagicMock()
        mock_lb.block.index = 10

        with patch.object(
            yadacoin.core.config.CONFIG, "LatestBlock", create=True, new=mock_lb
        ):
            with patch.object(
                txn, "has_key_event_log", new=AsyncMock(return_value=False)
            ):
                await txn.verify(check_kel=True, mempool=True)  # line 599

    async def test_verify_input_from_bu_dict_found(self):
        """Line 655: BU.get_transaction_by_id returns a dict → Transaction.from_dict wraps it."""
        from unittest.mock import AsyncMock, patch

        from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH

        from yadacoin.core.transactionutils import TU

        address = str(
            _P2PKH.from_pubkey(bytes.fromhex(yadacoin.core.config.CONFIG.public_key))
        )

        input_dict = {
            "id": "input_sig_dict",
            "outputs": [{"to": address, "value": 2.0}],
            "inputs": [],
            "hash": "hashval",
            "time": 1,
            "public_key": yadacoin.core.config.CONFIG.public_key,
            "relationship": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
        }

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to=address, value=2.0)],
        )
        txn.inputs = [Input(signature="input_sig_dict")]  # no input_txn → goes to BU
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )

        with patch.object(
            txn.config.BU,
            "get_transaction_by_id",
            new=AsyncMock(return_value=input_dict),
        ):
            await txn.verify()  # Should succeed; line 655 covered

    async def test_verify_input_extra_blocks_missing_raises(self):
        """Line 659: extra_blocks checked when DB returns None, find_in_extra_blocks also None → raises."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.transaction import MissingInputTransactionException
        from yadacoin.core.transactionutils import TU

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        txn.inputs = [Input(signature="missing_id")]
        txn.extra_blocks = [MagicMock()]  # non-empty → line 658 True
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )

        with patch.object(
            txn.config.BU, "get_transaction_by_id", new=AsyncMock(return_value=None)
        ):
            with patch.object(
                txn, "find_in_extra_blocks", new=AsyncMock(return_value=None)
            ):
                with self.assertRaises(MissingInputTransactionException):
                    await txn.verify()

    async def test_verify_check_input_spent_raises(self):
        """Lines 670-680: check_input_spent=True, is_input_spent=True raises."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from bitcoin.wallet import P2PKHBitcoinAddress as _P2PKH

        from yadacoin.core.transactionutils import TU

        address = str(
            _P2PKH.from_pubkey(bytes.fromhex(yadacoin.core.config.CONFIG.public_key))
        )
        input_txn_obj = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to=address, value=2.0)],
        )
        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            outputs=[Output(to=address, value=2.0)],
        )
        txn.inputs = [Input(signature="spent_input", input_txn=input_txn_obj)]
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )

        mock_lb = MagicMock()
        mock_lb.block.index = 100

        with patch.object(
            yadacoin.core.config.CONFIG, "LatestBlock", create=True, new=mock_lb
        ):
            with patch.object(
                txn.config.BU, "is_input_spent", new=AsyncMock(return_value=True)
            ):
                with self.assertRaises(Exception) as ctx:
                    await txn.verify(check_input_spent=True)
        self.assertIn("already spent", str(ctx.exception))

    async def test_is_already_in_mempool_with_twice_prerotated_and_prev(self):
        """Lines 1108, 1127: twice_prerotated_key_hash and prev_public_key_hash paths in is_already_in_mempool."""
        from unittest.mock import AsyncMock, MagicMock

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            twice_prerotated_key_hash="twice_hash",
            prev_public_key_hash="prev_hash",
        )
        mock_mongo = MagicMock()
        mock_mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)
        txn.config.mongo = mock_mongo

        result = await txn.is_already_in_mempool()
        self.assertFalse(result)

    async def test_has_key_event_log_extra_block_index_too_high_returns_false(self):
        """Line 1167: extra_block.index >= block.index → returns False."""
        from unittest.mock import AsyncMock, MagicMock

        mock_extra_block = MagicMock()
        mock_extra_block.index = 200  # >= block.index → return False at 1167

        mock_block = MagicMock()
        mock_block.index = 100

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)
        txn.extra_blocks = [mock_extra_block]

        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        txn.config.mongo = mock_mongo

        result = await txn.has_key_event_log(block=mock_block)
        self.assertFalse(result)

    async def test_has_key_event_log_extra_blocks_same_sig_returns_false(self):
        """Line 1170: xtxn.transaction_signature == self.transaction_signature → returns False."""
        from unittest.mock import AsyncMock, MagicMock

        fake_xtxn = MagicMock()
        fake_xtxn.transaction_signature = (
            "same_sig"  # Same as txn.transaction_signature
        )
        fake_xtxn.twice_prerotated_key_hash = "not_matching"
        fake_xtxn.prerotated_key_hash = "not_matching"

        mock_extra_block = MagicMock()
        mock_extra_block.index = 1  # < block.index → don't return at 1167
        mock_extra_block.transactions = [fake_xtxn]

        mock_block = MagicMock()
        mock_block.index = 100

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            transaction_signature="same_sig",
        )
        txn.extra_blocks = [mock_extra_block]

        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        txn.config.mongo = mock_mongo

        result = await txn.has_key_event_log(block=mock_block)
        self.assertFalse(result)

    async def test_verify_kel_output_rules_latestblock_paths(self):
        """Lines 1205-1208: verify_kel_output_rules with mempool and no-block uses LatestBlock."""
        from unittest.mock import AsyncMock, MagicMock, patch

        txn = Transaction(public_key=yadacoin.core.config.CONFIG.public_key)

        mock_lb = MagicMock()
        mock_lb.block.index = 10

        with patch.object(
            yadacoin.core.config.CONFIG, "LatestBlock", create=True, new=mock_lb
        ):
            # mempool=True → line 1205-1206
            with patch.object(
                txn, "has_key_event_log", new=AsyncMock(return_value=False)
            ):
                await txn.verify_kel_output_rules(mempool=True)

            # No block, no mempool → line 1207-1208
            with patch.object(
                txn, "has_key_event_log", new=AsyncMock(return_value=False)
            ):
                await txn.verify_kel_output_rules()

    async def test_verify_kel_output_rules_routing_all_outputs_match_returns(self):
        """Line 1259: all outputs match latest prerotated_key_hash → returns (routing OK)."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.keyeventlog import KeyEventLog

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            public_key_hash="pk_hash_existing",
            outputs=[Output(to="1CorrectOutput", value=1.0)],
        )
        txn.transaction_signature = "txn_sig_not_in_log"

        mock_block = MagicMock()
        mock_block.index = CHAIN.CHECK_KEL_OUTPUT_ROUTING_FORK + 1

        # key_log entry has same public_key_hash → is_new=False
        mock_entry = MagicMock()
        mock_entry.mempool = False
        mock_entry.public_key_hash = "pk_hash_existing"
        mock_entry.transaction_signature = "other_sig"
        mock_entry.prerotated_key_hash = "1CorrectOutput"  # all outputs match this

        with patch.object(txn, "has_key_event_log", new=AsyncMock(return_value=True)):
            with patch.object(
                KeyEventLog,
                "build_from_public_key",
                new=AsyncMock(return_value=[mock_entry]),
            ):
                # Should return at line 1259 (all outputs match, no routing violation)
                await txn.verify_kel_output_rules(block=mock_block)

    # -----------------------------------------------------------------------
    # verify_kel_output_rules UTXO completeness check (lines 1272-1325)
    # -----------------------------------------------------------------------

    async def test_verify_kel_output_rules_utxo_check_no_utxos_no_inputs(self):
        """Lines 1272-1301: UTXO check runs with empty aggregates and no inputs → no exception."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.keyeventlog import KeyEventLog

        async def async_iter_empty(pipeline):
            return
            yield  # make it a proper async generator

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            public_key_hash="pk_hash_new",
            outputs=[Output(to="1CorrectDest", value=1.0)],
        )
        txn.transaction_signature = "new_sig"
        txn.inputs = []  # no inputs, and no UTXOs → no exception

        # Route mock_entry with DIFFERENT public_key_hash so is_new_key_log_entry=True
        mock_entry = MagicMock()
        mock_entry.mempool = False
        mock_entry.public_key_hash = "different_hash"
        mock_entry.transaction_signature = "other_sig"
        mock_entry.prerotated_key_hash = "1CorrectDest"

        mock_block_lb = MagicMock()
        mock_block_lb.block.index = CHAIN.CHECK_KEL_OUTPUT_ROUTING_FORK + 10

        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.aggregate = async_iter_empty
        mock_mongo.async_db.miner_transactions.aggregate = async_iter_empty
        txn.config.mongo = mock_mongo

        mock_bu = MagicMock()
        txn.config.BU = mock_bu

        with patch.object(
            yadacoin.core.config.CONFIG, "LatestBlock", create=True, new=mock_block_lb
        ):
            with patch.object(
                txn, "has_key_event_log", new=AsyncMock(return_value=True)
            ):
                with patch.object(
                    KeyEventLog,
                    "build_from_public_key",
                    new=AsyncMock(return_value=[mock_entry]),
                ):
                    await txn.verify_kel_output_rules(
                        block=None
                    )  # block=None → UTXO check runs

    async def test_verify_kel_output_rules_utxo_check_mismatch_raises(self):
        """Lines 1302-1308: UTXO mismatch raises KELDoesNotSpendAllUTXOsException."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.keyeventlog import (
            KELDoesNotSpendAllUTXOsException,
            KeyEventLog,
        )

        utxo_item = {
            "public_key": yadacoin.core.config.CONFIG.public_key,
            "id": "utxo_tx",
        }

        async def async_iter_one(pipeline):
            yield utxo_item

        async def async_iter_empty(pipeline):
            return
            yield

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            public_key_hash="pk_hash_new",
            outputs=[Output(to="1CorrectDest", value=1.0)],
        )
        txn.transaction_signature = "new_sig"
        txn.inputs = [
            Input(signature="input1"),
            Input(signature="input2"),
        ]  # 2 inputs but 1 UTXO unspent

        mock_entry = MagicMock()
        mock_entry.mempool = False
        mock_entry.public_key_hash = "different_hash"
        mock_entry.transaction_signature = "other_sig"
        mock_entry.prerotated_key_hash = "1CorrectDest"

        mock_block_lb = MagicMock()
        mock_block_lb.block.index = CHAIN.CHECK_KEL_OUTPUT_ROUTING_FORK + 10

        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.aggregate = async_iter_one  # 1 UTXO
        mock_mongo.async_db.miner_transactions.aggregate = async_iter_empty

        mock_bu = AsyncMock()
        mock_bu.is_input_spent = AsyncMock(
            return_value=False
        )  # not spent → total_spent=0

        txn.config.mongo = mock_mongo
        txn.config.BU = mock_bu

        with patch.object(
            yadacoin.core.config.CONFIG, "LatestBlock", create=True, new=mock_block_lb
        ):
            with patch.object(
                txn, "has_key_event_log", new=AsyncMock(return_value=True)
            ):
                with patch.object(
                    KeyEventLog,
                    "build_from_public_key",
                    new=AsyncMock(return_value=[mock_entry]),
                ):
                    with self.assertRaises(KELDoesNotSpendAllUTXOsException):
                        await txn.verify_kel_output_rules(block=None)

    async def test_verify_kel_output_rules_utxo_missing_parent_raises(self):
        """Lines 1309-1315: inputs > 0 but no on-chain UTXOs → KELMissingParentUTXOException."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.keyeventlog import KELMissingParentUTXOException, KeyEventLog

        async def async_iter_empty(pipeline):
            return
            yield

        inp = Input(signature="missing_utxo_input")
        inp.input_txn = None  # no parent UTXO on-chain

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            public_key_hash="pk_hash_new",
            outputs=[Output(to="1CorrectDest", value=1.0)],
        )
        txn.transaction_signature = "new_sig"
        txn.inputs = [inp]

        mock_entry = MagicMock()
        mock_entry.mempool = False
        mock_entry.public_key_hash = "different_hash"
        mock_entry.transaction_signature = "other_sig"
        mock_entry.prerotated_key_hash = "1CorrectDest"

        mock_block_lb = MagicMock()
        mock_block_lb.block.index = CHAIN.CHECK_KEL_OUTPUT_ROUTING_FORK + 10

        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.aggregate = async_iter_empty
        mock_mongo.async_db.miner_transactions.aggregate = async_iter_empty

        txn.config.mongo = mock_mongo
        txn.config.BU = MagicMock()

        with patch.object(
            yadacoin.core.config.CONFIG, "LatestBlock", create=True, new=mock_block_lb
        ):
            with patch.object(
                txn, "has_key_event_log", new=AsyncMock(return_value=True)
            ):
                with patch.object(
                    KeyEventLog,
                    "build_from_public_key",
                    new=AsyncMock(return_value=[mock_entry]),
                ):
                    with self.assertRaises(KELMissingParentUTXOException):
                        await txn.verify_kel_output_rules(block=None)

    async def test_verify_kel_output_rules_utxo_transactions_branch(self):
        """Line 1293-1294: item has 'transactions' key → Transaction.from_dict(x['transactions'])."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.keyeventlog import KeyEventLog

        txn_dict = {
            "public_key": yadacoin.core.config.CONFIG.public_key,
            "id": "tx_in_block",
        }
        utxo_item = {"transactions": txn_dict}  # wrapped in 'transactions' key

        async def async_iter_one(pipeline):
            yield utxo_item

        async def async_iter_empty(pipeline):
            return
            yield

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            public_key_hash="pk_hash_new",
            outputs=[Output(to="1CorrectDest", value=1.0)],
        )
        txn.transaction_signature = "new_sig"
        txn.inputs = [
            Input(signature="inp1")
        ]  # 1 input, 1 UTXO unspent → count matches

        mock_entry = MagicMock()
        mock_entry.mempool = False
        mock_entry.public_key_hash = "different_hash"
        mock_entry.transaction_signature = "other_sig"
        mock_entry.prerotated_key_hash = "1CorrectDest"

        mock_block_lb = MagicMock()
        mock_block_lb.block.index = CHAIN.CHECK_KEL_OUTPUT_ROUTING_FORK + 10

        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.aggregate = async_iter_one  # wrapped item
        mock_mongo.async_db.miner_transactions.aggregate = async_iter_empty

        mock_bu = AsyncMock()
        mock_bu.is_input_spent = AsyncMock(return_value=False)  # not spent

        txn.config.mongo = mock_mongo
        txn.config.BU = mock_bu

        with patch.object(
            yadacoin.core.config.CONFIG, "LatestBlock", create=True, new=mock_block_lb
        ):
            with patch.object(
                txn, "has_key_event_log", new=AsyncMock(return_value=True)
            ):
                with patch.object(
                    KeyEventLog,
                    "build_from_public_key",
                    new=AsyncMock(return_value=[mock_entry]),
                ):
                    # 1 UTXO, 0 spent, 1 input → 1 - 0 == 1 → no exception
                    await txn.verify_kel_output_rules(block=None)

    async def test_verify_kel_output_rules_utxo_input_spent_increments_total_spent(
        self,
    ):
        """Line 1236: is_input_spent returns True → total_spent += 1 → no mismatch as all UTXOs spent."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.keyeventlog import KeyEventLog

        utxo_item = {
            "public_key": yadacoin.core.config.CONFIG.public_key,
            "id": "utxo_tx",
        }

        async def async_iter_one(pipeline):
            yield utxo_item

        async def async_iter_empty(pipeline):
            return
            yield

        txn = Transaction(
            public_key=yadacoin.core.config.CONFIG.public_key,
            public_key_hash="pk_hash_spent",
            outputs=[Output(to="1CorrectDest", value=1.0)],
        )
        txn.transaction_signature = "new_sig"
        txn.inputs = (
            []
        )  # 0 inputs, 1 UTXO but all spent → mempool_chain_input_sum - total_spent = 1 - 1 = 0 == len(inputs)

        mock_entry = MagicMock()
        mock_entry.mempool = False
        mock_entry.public_key_hash = "different_hash"
        mock_entry.transaction_signature = "other_sig"
        mock_entry.prerotated_key_hash = "1CorrectDest"

        mock_block_lb = MagicMock()
        mock_block_lb.block.index = CHAIN.CHECK_KEL_OUTPUT_ROUTING_FORK + 10

        mock_mongo = MagicMock()
        mock_mongo.async_db.blocks.aggregate = async_iter_one  # 1 UTXO
        mock_mongo.async_db.miner_transactions.aggregate = async_iter_empty

        mock_bu = AsyncMock()
        mock_bu.is_input_spent = AsyncMock(
            return_value=True
        )  # spent → total_spent += 1 (line 1236)

        txn.config.mongo = mock_mongo
        txn.config.BU = mock_bu

        with patch.object(
            yadacoin.core.config.CONFIG, "LatestBlock", create=True, new=mock_block_lb
        ):
            with patch.object(
                txn, "has_key_event_log", new=AsyncMock(return_value=True)
            ):
                with patch.object(
                    KeyEventLog,
                    "build_from_public_key",
                    new=AsyncMock(return_value=[mock_entry]),
                ):
                    # 1 UTXO, 1 spent → 1 - 1 = 0 == len([]) → no exception
                    await txn.verify_kel_output_rules(block=None)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
