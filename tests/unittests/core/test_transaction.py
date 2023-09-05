import unittest
from unittest.mock import patch

import yadacoin.core.config
from yadacoin.core.blockchainutils import BlockChainUtils
from yadacoin.core.config import Config
from yadacoin.core.transaction import (
    Input,
    NotEnoughMoneyException,
    Output,
    Transaction,
)

from ..test_setup import AsyncTestCase


async def mock_get_wallet_unspent_transactions(*args, **kwargs):
    for x in [
        Transaction(outputs=[Output(value=1, to="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4")])
    ]:
        yield x


class TestTransaction(AsyncTestCase):
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
                mtxn_ids=[],
                inputs=[],
                outputs_and_fee_total=1,
            )
            self.assertTrue(input_sum, 1)
            with self.assertRaises(NotEnoughMoneyException):
                input_sum = await txn.generate_inputs(
                    input_sum=1,
                    my_address="1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4",
                    mtxn_ids=[],
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


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
