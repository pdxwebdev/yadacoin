"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest

from yadacoin.core.rotationannouncement import RotationAnnouncement

_PRIV_HEX = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
_PUB_HEX = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"


class TestRotationAnnouncementInit(unittest.TestCase):
    def test_valid_secp256k1_construction(self):
        ra = RotationAnnouncement(curve="secp256k1")
        self.assertEqual(ra.curve, "secp256k1")

    def test_unsupported_curve_raises(self):
        with self.assertRaises(ValueError):
            RotationAnnouncement(curve="ed25519")

    def test_to_dict_includes_optional_fields(self):
        ra = RotationAnnouncement(
            curve="secp256r1",
            public_key="0400",
            key_hash="1abc",
            dtls_fingerprint="sha-256:AA:BB",
        )
        d = ra.to_dict()
        self.assertEqual(d["curve"], "secp256r1")
        self.assertEqual(d["public_key"], "0400")
        self.assertEqual(d["key_hash"], "1abc")
        self.assertEqual(d["dtls_fingerprint"], "sha-256:AA:BB")

    def test_to_dict_omits_empty_fields(self):
        ra = RotationAnnouncement(curve="secp256k1")
        d = ra.to_dict()
        self.assertEqual(d, {"curve": "secp256k1"})

    def test_to_string_contains_rotation_key(self):
        ra = RotationAnnouncement(curve="secp256k1")
        s = ra.to_string()
        self.assertIn("secp256k1", s)

    def test_to_relationship_key_constant(self):
        self.assertEqual(RotationAnnouncement.RELATIONSHIP_KEY, "rotation")

    def test_get_string_none_returns_empty(self):
        self.assertEqual(RotationAnnouncement.get_string(None), "")
        self.assertEqual(RotationAnnouncement.get_string("x"), "x")

    def test_from_dict_non_dict_raises(self):
        with self.assertRaises(ValueError):
            RotationAnnouncement.from_dict("bad")

    def test_from_dict_valid(self):
        ra = RotationAnnouncement.from_dict({"curve": "secp256k1"})
        self.assertEqual(ra.curve, "secp256k1")

    def test_from_relationship_missing_key_raises(self):
        with self.assertRaises(ValueError):
            RotationAnnouncement.from_relationship({"other": {}})

    def test_from_relationship_valid(self):
        ra = RotationAnnouncement.from_relationship(
            {"rotation": {"curve": "secp256k1"}}
        )
        self.assertEqual(ra.curve, "secp256k1")

    def test_validate_p256_secp256k1_returns_true(self):
        ra = RotationAnnouncement(curve="secp256k1")
        self.assertTrue(ra.validate_p256())

    def test_validate_p256_missing_public_key_raises(self):
        ra = RotationAnnouncement(curve="secp256r1", public_key="")
        with self.assertRaises(ValueError):
            ra.validate_p256()

    def test_validate_p256_invalid_hex_raises(self):
        ra = RotationAnnouncement(curve="secp256r1", public_key="ZZZZ")
        with self.assertRaises(ValueError):
            ra.validate_p256()

    def test_validate_p256_wrong_key_hash_raises(self):
        ra = RotationAnnouncement(
            curve="secp256r1", public_key=_PUB_HEX, key_hash="1WRONGHASH"
        )
        with self.assertRaises(ValueError):
            ra.validate_p256()

    def test_validate_p256_correct_key_hash_passes(self):
        from bitcoin.wallet import P2PKHBitcoinAddress

        pub_bytes = bytes.fromhex(_PUB_HEX)
        expected = str(P2PKHBitcoinAddress.from_pubkey(pub_bytes))
        ra = RotationAnnouncement(
            curve="secp256r1", public_key=_PUB_HEX, key_hash=expected
        )
        self.assertTrue(ra.validate_p256())


class TestDerivep256FromK0(unittest.TestCase):
    def test_returns_rotation_announcement(self):
        priv = bytes.fromhex(_PRIV_HEX)
        ra = RotationAnnouncement.derive_p256_from_k0(priv)
        self.assertIsInstance(ra, RotationAnnouncement)
        self.assertEqual(ra.curve, "secp256r1")
        self.assertTrue(ra.public_key.startswith("04"))
        self.assertTrue(ra.dtls_fingerprint.startswith("sha-256:"))

    def test_deterministic(self):
        priv = bytes.fromhex(_PRIV_HEX)
        ra1 = RotationAnnouncement.derive_p256_from_k0(priv)
        ra2 = RotationAnnouncement.derive_p256_from_k0(priv)
        self.assertEqual(ra1.public_key, ra2.public_key)
        self.assertEqual(ra1.key_hash, ra2.key_hash)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
