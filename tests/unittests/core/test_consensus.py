"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest

from yadacoin.core.consensus import Consensus

from ..test_setup import AsyncTestCase


class TestTransaction(AsyncTestCase):
    async def test___init__(self):
        c = Consensus()
        self.assertIsInstance(c, Consensus)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
