"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest

from yadacoin.contracts.asset import Asset


def _make_asset():
    from yadacoin.core.identity import Identity

    identity = Identity.generate(username="asset_test_user")
    return Asset(identity=identity, data="hello", checksum="abc"), identity


class TestAssetInit(unittest.TestCase):
    def test_valid_init(self):
        asset, identity = _make_asset()
        self.assertEqual(asset.data, "hello")
        self.assertEqual(asset.checksum, "abc")

    def test_init_non_string_data_raises(self):
        from yadacoin.core.identity import Identity

        identity = Identity.generate(username="asset_test_user2")
        with self.assertRaises(Exception) as ctx:
            Asset(identity=identity, data=123, checksum="abc")
        self.assertIn("not type string", str(ctx.exception))

    def test_init_too_large_data_raises(self):
        from yadacoin.core.identity import Identity

        identity = Identity.generate(username="asset_test_user3")
        big_data = "x" * 20481
        with self.assertRaises(Exception) as ctx:
            Asset(identity=identity, data=big_data, checksum="abc")
        self.assertIn("too large", str(ctx.exception))


class TestAssetGenerate(unittest.TestCase):
    def test_generate_sets_data(self):
        from yadacoin.core.identity import Identity

        identity = Identity.generate(username="gen_user")
        asset = Asset(identity=identity, data="initial", checksum="")
        asset.generate(username="gen_user2", data="new_data")
        self.assertEqual(asset.data, "new_data")

    def test_generate_with_parent(self):
        from yadacoin.core.identity import Identity

        identity = Identity.generate(username="gen_user3")
        asset = Asset(identity=identity, data="initial", checksum="")
        asset.generate(username="gen_user3", data="data2", parent="some_parent")
        self.assertEqual(asset.data, "data2")


class TestAssetToDict(unittest.TestCase):
    def test_to_dict_keys(self):
        asset, _ = _make_asset()
        d = asset.to_dict()
        self.assertIn("identity", d)
        self.assertIn("data", d)
        self.assertIn("checksum", d)
        self.assertEqual(d["data"], "hello")


class TestAssetToString(unittest.TestCase):
    def test_to_string_returns_string(self):
        from yadacoin.core.identity import Identity

        identity = Identity.generate(username="str_user")
        asset = Asset(identity=identity, data="mydata", checksum="mychecksum")
        result = asset.to_string()
        self.assertIsInstance(result, str)
        self.assertIn("mydata", result)
        self.assertIn("mychecksum", result)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
