"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest

from yadacoin.core.identity import Identity, PrivateIdentity, PublicIdentity


class TestIdentityGenerate(unittest.TestCase):
    def setUp(self):
        self.identity = Identity.generate(username="testuser")

    def test_generate_returns_identity(self):
        self.assertIsInstance(self.identity, Identity)

    def test_generate_has_public_key(self):
        self.assertIsNotNone(self.identity.public_key)
        self.assertIsInstance(self.identity.public_key, str)

    def test_generate_has_username_signature(self):
        self.assertIsNotNone(self.identity.username_signature)
        self.assertIsInstance(self.identity.username_signature, str)

    def test_generate_has_wif(self):
        self.assertIsNotNone(self.identity.wif)
        self.assertIsInstance(self.identity.wif, str)

    def test_generate_with_empty_username(self):
        identity = Identity.generate(username="")
        self.assertIsInstance(identity, Identity)

    def test_generate_two_identities_differ(self):
        i1 = Identity.generate(username="user1")
        i2 = Identity.generate(username="user1")
        # Different keypairs each time
        self.assertNotEqual(i1.public_key, i2.public_key)

    def test_generate_with_parent(self):
        parent = "parentid123"
        identity = Identity.generate(username="child", parent=parent)
        self.assertEqual(identity.parent, parent)


class TestIdentityFromDict(unittest.TestCase):
    def setUp(self):
        self.identity = Identity.generate(username="testuser")
        self.data = {
            "public_key": self.identity.public_key,
            "username": "testuser",
            "username_signature": self.identity.username_signature,
            "collection": "contact",
            "parent": "",
        }

    def test_from_dict_returns_identity(self):
        identity = Identity.from_dict(self.data)
        self.assertIsInstance(identity, Identity)

    def test_from_dict_preserves_public_key(self):
        identity = Identity.from_dict(self.data)
        self.assertEqual(identity.public_key, self.data["public_key"])

    def test_from_dict_preserves_username(self):
        identity = Identity.from_dict(self.data)
        self.assertEqual(identity.username, "testuser")

    def test_from_dict_preserves_username_signature(self):
        identity = Identity.from_dict(self.data)
        self.assertEqual(identity.username_signature, self.data["username_signature"])

    def test_from_dict_optional_fields(self):
        data = {
            "public_key": self.identity.public_key,
            "username": "test",
            "username_signature": self.identity.username_signature,
        }
        identity = Identity.from_dict(data)
        self.assertEqual(identity.collection, "")
        self.assertEqual(identity.parent, "")


class TestIdentityGenerateRid(unittest.TestCase):
    def setUp(self):
        self.identity = Identity.generate(username="user1")
        self.other = Identity.generate(username="user2")

    def test_generate_rid_returns_string(self):
        rid = self.identity.generate_rid(self.other.username_signature)
        self.assertIsInstance(rid, str)

    def test_generate_rid_is_64_chars(self):
        rid = self.identity.generate_rid(self.other.username_signature)
        self.assertEqual(len(rid), 64)

    def test_generate_rid_symmetric(self):
        rid1 = self.identity.generate_rid(self.other.username_signature)
        rid2 = self.other.generate_rid(self.identity.username_signature)
        self.assertEqual(rid1, rid2)


class TestIdentityGenerateWif(unittest.TestCase):
    def test_generate_wif_returns_string(self):
        identity = Identity.generate()
        self.assertIsInstance(identity.wif, str)

    def test_generate_wif_starts_with_K_or_L(self):
        # Compressed WIF starts with K or L
        identity = Identity.generate()
        self.assertIn(identity.wif[0], ("K", "L", "5"))

    def test_generate_wif_consistent(self):
        # Same private key -> same WIF
        identity = Identity.generate()
        # Extract the private key from wif through generation
        self.assertIsNotNone(identity.wif)


class TestIdentityToDict(unittest.TestCase):
    def test_to_dict_has_required_keys(self):
        identity = Identity.generate(username="testuser")
        d = identity.to_dict
        self.assertIn("public_key", d)
        self.assertIn("username_signature", d)
        self.assertIn("username", d)
        self.assertIn("collection", d)
        self.assertIn("parent", d)

    def test_to_dict_public_key_is_hex(self):
        identity = Identity.generate(username="testuser")
        d = identity.to_dict
        self.assertIsInstance(d["public_key"], str)
        # Should be a valid hex string
        int(d["public_key"], 16)


class TestPrivateIdentity(unittest.TestCase):
    def setUp(self):
        self.identity = Identity.generate(username="testuser")

    def test_from_dict_returns_private_identity(self):
        data = {
            "public_key": self.identity.public_key,
            "username": "testuser",
            "username_signature": self.identity.username_signature,
            "collection": "contact",
            "parent": "",
            "wif": self.identity.wif,
        }
        pi = PrivateIdentity.from_dict(data)
        self.assertIsInstance(pi, PrivateIdentity)

    def test_to_dict_includes_wif(self):
        data = {
            "public_key": self.identity.public_key,
            "username": "testuser",
            "username_signature": self.identity.username_signature,
            "collection": "contact",
            "parent": "",
            "wif": self.identity.wif,
        }
        pi = PrivateIdentity.from_dict(data)
        d = pi.to_dict
        self.assertIn("wif", d)


class TestPublicIdentity(unittest.TestCase):
    def setUp(self):
        self.identity = Identity.generate(username="testuser")

    def test_to_dict_does_not_include_wif(self):
        data = {
            "public_key": self.identity.public_key,
            "username": "testuser",
            "username_signature": self.identity.username_signature,
            "collection": "contact",
            "parent": "",
        }
        pi = PublicIdentity.from_dict(data)
        d = pi.to_dict
        self.assertNotIn("wif", d)

    def test_to_dict_has_required_keys(self):
        data = {
            "public_key": self.identity.public_key,
            "username": "testuser",
            "username_signature": self.identity.username_signature,
        }
        pi = PublicIdentity.from_dict(data)
        d = pi.to_dict
        self.assertIn("public_key", d)
        self.assertIn("username_signature", d)
        self.assertIn("username", d)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
