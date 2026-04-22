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

from yadacoin.enums.modes import MODES


class TestMODES(unittest.TestCase):
    def test_modes_is_enum(self):
        self.assertTrue(issubclass(MODES, Enum))

    def test_modes_has_dns(self):
        self.assertEqual(MODES.DNS.value, "dns")

    def test_modes_has_node(self):
        self.assertEqual(MODES.NODE.value, "node")

    def test_modes_has_pool(self):
        self.assertEqual(MODES.POOL.value, "pool")

    def test_modes_has_proxy(self):
        self.assertEqual(MODES.PROXY.value, "proxy")

    def test_modes_has_ssl(self):
        self.assertEqual(MODES.SSL.value, "ssl")

    def test_modes_has_web(self):
        self.assertEqual(MODES.WEB.value, "web")

    def test_modes_member_count(self):
        self.assertEqual(len(MODES), 6)

    def test_modes_values_are_strings(self):
        for mode in MODES:
            self.assertIsInstance(mode.value, str)

    def test_modes_lookup_by_value(self):
        self.assertEqual(MODES("dns"), MODES.DNS)
        self.assertEqual(MODES("node"), MODES.NODE)
        self.assertEqual(MODES("pool"), MODES.POOL)
        self.assertEqual(MODES("proxy"), MODES.PROXY)
        self.assertEqual(MODES("ssl"), MODES.SSL)
        self.assertEqual(MODES("web"), MODES.WEB)

    def test_modes_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            MODES("invalid")

    def test_modes_membership(self):
        all_values = [m.value for m in MODES]
        self.assertIn("dns", all_values)
        self.assertIn("node", all_values)
        self.assertIn("pool", all_values)
        self.assertIn("proxy", all_values)
        self.assertIn("ssl", all_values)
        self.assertIn("web", all_values)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
