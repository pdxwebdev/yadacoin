import unittest
from unittest import (
    IsolatedAsyncioTestCase,  # python 3.8 requiredsudo apt install python3.8
)

from yadacoin.core.consensus import Consensus


class TestTransaction(IsolatedAsyncioTestCase):
    async def test___init__(self):
        c = Consensus()
        self.assertIsInstance(c, Consensus)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
