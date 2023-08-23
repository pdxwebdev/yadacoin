import unittest

from yadacoin.core.consensus import Consensus

from ..test_setup import AsyncTestCase


class TestTransaction(AsyncTestCase):
    async def test___init__(self):
        c = Consensus()
        self.assertIsInstance(c, Consensus)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
