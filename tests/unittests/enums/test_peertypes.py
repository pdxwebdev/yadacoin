"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from enum import Enum

from yadacoin.enums.peertypes import PEER_TYPES


class TestPEERTYPES(unittest.TestCase):
    def test_peer_types_is_enum(self):
        self.assertTrue(issubclass(PEER_TYPES, Enum))

    def test_peer_types_has_seed(self):
        self.assertEqual(PEER_TYPES.SEED.value, "seed")

    def test_peer_types_has_seed_gateway(self):
        self.assertEqual(PEER_TYPES.SEED_GATEWAY.value, "seed_gateway")

    def test_peer_types_has_service_provider(self):
        self.assertEqual(PEER_TYPES.SERVICE_PROVIDER.value, "service_provider")

    def test_peer_types_has_user(self):
        self.assertEqual(PEER_TYPES.USER.value, "user")

    def test_peer_types_has_pool(self):
        self.assertEqual(PEER_TYPES.POOL.value, "pool")

    def test_peer_types_member_count(self):
        self.assertEqual(len(PEER_TYPES), 5)

    def test_peer_types_values_are_strings(self):
        for pt in PEER_TYPES:
            self.assertIsInstance(pt.value, str)

    def test_peer_types_lookup_by_value(self):
        self.assertEqual(PEER_TYPES("seed"), PEER_TYPES.SEED)
        self.assertEqual(PEER_TYPES("seed_gateway"), PEER_TYPES.SEED_GATEWAY)
        self.assertEqual(PEER_TYPES("service_provider"), PEER_TYPES.SERVICE_PROVIDER)
        self.assertEqual(PEER_TYPES("user"), PEER_TYPES.USER)
        self.assertEqual(PEER_TYPES("pool"), PEER_TYPES.POOL)

    def test_peer_types_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            PEER_TYPES("unknown")

    def test_peer_types_membership(self):
        all_values = [pt.value for pt in PEER_TYPES]
        self.assertIn("seed", all_values)
        self.assertIn("seed_gateway", all_values)
        self.assertIn("service_provider", all_values)
        self.assertIn("user", all_values)
        self.assertIn("pool", all_values)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
