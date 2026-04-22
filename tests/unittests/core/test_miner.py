"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from unittest import mock
from unittest.mock import MagicMock

from yadacoin.core.config import Config
from yadacoin.core.mongo import Mongo


class TestMiner(unittest.TestCase):
    """Tests for yadacoin.core.miner.Miner class."""

    def setUp(self):
        c = Config()
        c.network = "regnet"
        c.mongo = Mongo()

    def test_miner_with_worker_dot_address(self):
        """Lines 28-35: covers 'if . in address' branch with valid address."""
        from yadacoin.core.miner import Miner

        config = Config()
        valid_addr = config.address
        miner = Miner(address=f"{valid_addr}.worker1")
        self.assertEqual(miner.address_only, valid_addr)
        self.assertEqual(miner.worker, "worker1")

    def test_miner_with_dot_address_invalid_raises(self):
        """Line 33: covers InvalidAddressException when address_only is invalid."""
        from yadacoin.core.miner import InvalidAddressException, Miner

        with self.assertRaises(InvalidAddressException):
            Miner(address="notanaddr.worker1")

    def test_miner_without_dot_address(self):
        """Lines 36-44: covers 'else' branch (no worker dot) with valid address."""

        config = Config()
        valid_addr = config.address
        mock_stratum = MagicMock()
        mock_stratum.inbound_streams = {"Miner": {}}
        with mock.patch.dict(
            "sys.modules",
            {"yadacoin.tcpsocket.pool": mock.MagicMock(StratumServer=mock_stratum)},
        ):
            from importlib import reload

            import yadacoin.core.miner as miner_module

            reload(miner_module)
            miner = miner_module.Miner(address=valid_addr)
            self.assertEqual(miner.address, valid_addr)
            self.assertIsInstance(miner.worker, str)

    def test_miner_without_dot_address_invalid_raises(self):
        """Line 43: covers InvalidAddressException in else branch."""
        mock_stratum = MagicMock()
        mock_stratum.inbound_streams = {"Miner": {}}
        with mock.patch.dict(
            "sys.modules",
            {"yadacoin.tcpsocket.pool": mock.MagicMock(StratumServer=mock_stratum)},
        ):
            from importlib import reload

            import yadacoin.core.miner as miner_module

            reload(miner_module)
            with self.assertRaises(miner_module.InvalidAddressException):
                miner_module.Miner(address="notanaddress")

    def test_miner_to_json(self):
        """Line 50: covers to_json() method."""
        from yadacoin.core.miner import Miner

        config = Config()
        valid_addr = config.address
        miner = Miner(
            address=f"{valid_addr}.miner_worker", agent="agent/1.0", peer_id="peer123"
        )
        result = miner.to_json()
        self.assertEqual(result["address"], valid_addr)
        self.assertEqual(result["worker"], "miner_worker")
        self.assertEqual(result["agent"], "agent/1.0")
        self.assertEqual(result["peer_id"], "peer123")


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
