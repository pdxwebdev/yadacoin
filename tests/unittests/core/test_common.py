"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest

from yadacoin.core.common import abstract_block, changetime, ts_to_utc


class TestCommon(unittest.TestCase):
    def test_ts_to_utc_basic(self):
        result = ts_to_utc(0)
        self.assertEqual(result, "1970-01-01T00:00:00 UTC")

    def test_ts_to_utc_string_input(self):
        result = ts_to_utc("0")
        self.assertEqual(result, "1970-01-01T00:00:00 UTC")

    def test_ts_to_utc_returns_string(self):
        result = ts_to_utc(1000000)
        self.assertIsInstance(result, str)
        self.assertTrue(result.endswith(" UTC"))

    def test_changetime_with_txn_key(self):
        thing = {
            "txn": {"hash": "abc", "value": 1},
            "time": 0,
        }
        result = changetime(thing)
        self.assertNotIn("txn", result)
        self.assertIn("hash", result)
        self.assertEqual(result["time"], "1970-01-01T00:00:00 UTC")

    def test_changetime_without_txn_key(self):
        thing = {"time": 0, "some_field": "value"}
        result = changetime(thing)
        self.assertNotIn("txn", result)
        self.assertEqual(result["time"], "1970-01-01T00:00:00 UTC")
        self.assertEqual(result["some_field"], "value")

    def test_changetime_returns_dict(self):
        thing = {"time": 1000000}
        result = changetime(thing)
        self.assertIsInstance(result, dict)

    def test_abstract_block_basic(self):
        block = {
            "index": 1,
            "time": 1000000,
            "hash": "abc",
            "transactions": [
                {
                    "inputs": [],
                    "outputs": [{"to": "addr1", "value": 50}],
                },
                {
                    "inputs": [{"id": "txin1"}],
                    "outputs": [{"to": "addr2", "value": 10}],
                },
            ],
        }
        result = abstract_block(block)
        self.assertNotIn("transactions", result)
        self.assertIn("miner", result)
        self.assertIn("reward", result)
        self.assertIn("tx_count", result)
        self.assertIn("time_utc", result)
        self.assertEqual(result["miner"], "addr1")
        self.assertEqual(result["reward"], 50)
        self.assertEqual(result["tx_count"], 2)

    def test_abstract_block_preserves_other_fields(self):
        block = {
            "index": 5,
            "time": 0,
            "hash": "deadbeef",
            "transactions": [
                {"inputs": [], "outputs": [{"to": "mineraddr", "value": 12.5}]}
            ],
        }
        result = abstract_block(block)
        self.assertEqual(result["index"], 5)
        self.assertEqual(result["hash"], "deadbeef")


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
