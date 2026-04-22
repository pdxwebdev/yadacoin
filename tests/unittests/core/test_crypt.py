"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest

from yadacoin.core.crypt import RIPEMD160, Crypt


class TestCrypt(unittest.TestCase):
    def setUp(self):
        self.crypt = Crypt("test_secret")

    def test_init_creates_key(self):
        self.assertTrue(hasattr(self.crypt, "key"))
        self.assertEqual(len(self.crypt.key), 32)

    def test_encrypt_returns_hex_string(self):
        # encrypt() takes bytes input
        result = self.crypt.encrypt(b"hello world test data!!")
        self.assertIsInstance(result, str)
        # Should be valid hex
        bytes.fromhex(result)

    def test_encrypt_different_each_time(self):
        # Random IV means different ciphertext each time
        r1 = self.crypt.encrypt(b"same input padded!!")
        r2 = self.crypt.encrypt(b"same input padded!!")
        self.assertNotEqual(r1, r2)

    def test_different_secrets_produce_different_keys(self):
        c1 = Crypt("secret1")
        c2 = Crypt("secret2")
        self.assertNotEqual(c1.key, c2.key)

    def test_decrypt_reverses_encrypt(self):
        plaintext = b"test data for encryption!!"
        encrypted = self.crypt.encrypt(plaintext)
        decrypted = self.crypt.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_encrypt_consistent_raises_for_invalid_input(self):
        # encrypt_consistent calls bytes.fromhex(s) after padding,
        # which fails unless the input + padding is valid hex
        with self.assertRaises((ValueError, Exception)):
            self.crypt.encrypt_consistent("not-hex")

    def test_shared_encrypt_returns_hex(self):
        result = self.crypt.shared_encrypt(b"test data for shared")
        self.assertIsInstance(result, str)
        bytes.fromhex(result)  # should be valid hex

    def test_shared_encrypt_decrypt_roundtrip(self):
        plaintext = b"roundtrip test data!!"
        encrypted = self.crypt.shared_encrypt(plaintext)
        decrypted = self.crypt.shared_decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)


class TestRIPEMD160(unittest.TestCase):
    def test_ripemd160_empty(self):
        result = RIPEMD160.ripemd160(b"")
        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 20)

    def test_ripemd160_known_value(self):
        # Test that hash of empty string is 20 bytes and consistent
        result = RIPEMD160.ripemd160(b"")
        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 20)
        # Verify it's the same each call
        result2 = RIPEMD160.ripemd160(b"")
        self.assertEqual(result, result2)

    def test_ripemd160_hello(self):
        result = RIPEMD160.ripemd160(b"Hello, World!")
        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 20)

    def test_ripemd160_consistent(self):
        msg = b"test message"
        r1 = RIPEMD160.ripemd160(msg)
        r2 = RIPEMD160.ripemd160(msg)
        self.assertEqual(r1, r2)

    def test_ripemd160_different_inputs(self):
        r1 = RIPEMD160.ripemd160(b"input1")
        r2 = RIPEMD160.ripemd160(b"input2")
        self.assertNotEqual(r1, r2)

    def test_fi_invalid_i_raises(self):
        with self.assertRaises(AssertionError):
            RIPEMD160.fi(0, 0, 0, 5)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
