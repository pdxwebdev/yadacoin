"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest

import yadacoin.core.config

from .test_block import TestBlock
from .test_blockchain import TestBlockchain
from .test_blockchainutils import TestBlockchainUtils
from .test_transaction import TestTransaction

if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
