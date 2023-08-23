import unittest
from unittest import (
    IsolatedAsyncioTestCase,  # python 3.8 requiredsudo apt install python3.8
)

import yadacoin.core.config
from yadacoin.core.transaction import Transaction


class TestTransaction(IsolatedAsyncioTestCase):
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


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
