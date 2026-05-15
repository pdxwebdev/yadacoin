"""
Unit tests for yadacoin.core.credentialreceipt — targets 100 % branch coverage.
"""

import unittest

from yadacoin.core.credentialreceipt import CredentialReceipt


class TestCredentialReceiptInit(unittest.TestCase):
    def test_valid(self):
        cr = CredentialReceipt("AABB1234", "CCDD5678", "base64ct==")
        # lookup_key and iv are lowercased
        self.assertEqual(cr.lookup_key, "aabb1234")
        self.assertEqual(cr.iv, "ccdd5678")
        # ct is verbatim (base64 is case-sensitive)
        self.assertEqual(cr.ct, "base64ct==")
        self.assertEqual(cr.extra_fields, {})

    def test_uppercase_normalised(self):
        cr = CredentialReceipt("ABCD", "EFFF", "CT==")
        self.assertEqual(cr.lookup_key, "abcd")
        self.assertEqual(cr.iv, "efff")
        self.assertEqual(cr.ct, "CT==")

    def test_extra_kwargs_stored(self):
        cr = CredentialReceipt("aa", "bb", "cc", future="yes")
        self.assertEqual(cr.extra_fields, {"future": "yes"})

    def test_empty_lookup_key_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt("", "bb", "cc")

    def test_none_lookup_key_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt(None, "bb", "cc")

    def test_non_string_lookup_key_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt(42, "bb", "cc")

    def test_empty_iv_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt("aa", "", "cc")

    def test_none_iv_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt("aa", None, "cc")

    def test_non_string_iv_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt("aa", 99, "cc")

    def test_empty_ct_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt("aa", "bb", "")

    def test_none_ct_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt("aa", "bb", None)

    def test_non_string_ct_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt("aa", "bb", 3.14)


class TestCredentialReceiptFromDict(unittest.TestCase):
    def test_valid(self):
        cr = CredentialReceipt.from_dict({"lookup_key": "aa", "iv": "bb", "ct": "cc=="})
        self.assertEqual(cr.lookup_key, "aa")
        self.assertEqual(cr.iv, "bb")
        self.assertEqual(cr.ct, "cc==")

    def test_extra_fields_passed_through(self):
        cr = CredentialReceipt.from_dict(
            {"lookup_key": "aa", "iv": "bb", "ct": "cc", "extra": "yes"}
        )
        self.assertEqual(cr.extra_fields, {"extra": "yes"})

    def test_non_dict_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt.from_dict("not a dict")

    def test_missing_lookup_key_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt.from_dict({"iv": "bb", "ct": "cc"})

    def test_missing_iv_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt.from_dict({"lookup_key": "aa", "ct": "cc"})

    def test_missing_ct_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt.from_dict({"lookup_key": "aa", "iv": "bb"})


class TestCredentialReceiptFromRelationship(unittest.TestCase):
    def test_valid(self):
        cr = CredentialReceipt.from_relationship(
            {"credential_receipt": {"lookup_key": "aa", "iv": "bb", "ct": "cc=="}}
        )
        self.assertEqual(cr.lookup_key, "aa")

    def test_missing_credential_receipt_key_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt.from_relationship({"wrong_key": {}})

    def test_non_dict_raises(self):
        with self.assertRaises(ValueError):
            CredentialReceipt.from_relationship("not a dict")


class TestCredentialReceiptToDict(unittest.TestCase):
    def test_basic(self):
        cr = CredentialReceipt("aa", "bb", "cc==")
        d = cr.to_dict()
        self.assertEqual(
            d,
            {"credential_receipt": {"lookup_key": "aa", "iv": "bb", "ct": "cc=="}},
        )

    def test_extra_fields_included(self):
        cr = CredentialReceipt("aa", "bb", "cc", future="yes")
        d = cr.to_dict()
        self.assertEqual(d["credential_receipt"]["future"], "yes")

    def test_roundtrip(self):
        original = {
            "credential_receipt": {"lookup_key": "aabb", "iv": "ccdd", "ct": "eeff=="}
        }
        cr = CredentialReceipt.from_relationship(original)
        self.assertEqual(cr.to_dict(), original)


class TestCredentialReceiptToString(unittest.TestCase):
    def test_concatenation(self):
        cr = CredentialReceipt("aabb", "ccdd", "eeff==")
        self.assertEqual(cr.to_string(), "aabbccddeeff==")


class TestCredentialReceiptRepr(unittest.TestCase):
    def test_repr_contains_class_name(self):
        cr = CredentialReceipt("aabbccdd1122", "eeff00112233", "ct==")
        r = repr(cr)
        self.assertIn("CredentialReceipt", r)
        # repr truncates to 8 chars
        self.assertIn("aabbccdd", r)


if __name__ == "__main__":
    unittest.main()
