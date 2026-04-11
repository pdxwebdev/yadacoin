"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest


class TestVersion(unittest.TestCase):
    def test_version_module_loads(self):
        import yadacoin.version as v

        self.assertTrue(hasattr(v, "version"))
        self.assertTrue(hasattr(v, "version_str"))

    def test_version_is_tuple(self):
        import yadacoin.version as v

        self.assertIsInstance(v.version, tuple)

    def test_version_str_is_string(self):
        import yadacoin.version as v

        self.assertIsInstance(v.version_str, str)

    def test_version_tuple_has_integers(self):
        import yadacoin.version as v

        for part in v.version:
            self.assertIsInstance(part, int)

    def test_version_str_format(self):
        import yadacoin.version as v

        parts = v.version_str.split(".")
        self.assertGreaterEqual(len(parts), 1)

    def test_version_tuple_matches_str(self):
        import yadacoin.version as v

        parts = v.version_str.split(".")
        self.assertEqual(len(v.version), len(parts))


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
