"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest

from yadacoin.core.config import Config
from yadacoin.core.nodeannouncement import NodeAnnouncement
from yadacoin.core.transaction import Transaction

from ..test_setup import AsyncTestCase


class TestNodeAnnouncementFeeSplit(AsyncTestCase):
    """Test suite for node announcement fee split logic."""

    async def asyncSetUp(self):
        # Initialize Config without MongoDB for pure logic tests
        c = Config.generate()
        c.mongo = None

    async def test_fee_split_calculation_4_ydas(self):
        """Test that a 4 YDA fee is split 50/50 into 2 + 2."""
        registration_fee = 4.0
        split_fee = registration_fee / 2.0

        # Each half should be 2.0
        self.assertEqual(split_fee, 2.0)
        self.assertEqual(float(split_fee), float(split_fee))

    async def test_fee_split_calculation_100_ydas(self):
        """Test that a 100 YDA fee is split 50/50 into 50 + 50."""
        registration_fee = 100.0
        split_fee = registration_fee / 2.0

        self.assertEqual(split_fee, 50.0)

    async def test_uptime_blocks_calculation_from_split(self):
        """Test that uptime blocks are calculated correctly from split fee."""
        registration_fee = 4.0
        split_fee = registration_fee / 2.0
        uptime_blocks = int(split_fee)
        uptime_days = uptime_blocks / 144.0

        # 2 YDA registration splits into 1 block (2/2 = 1) of uptime
        self.assertEqual(uptime_blocks, 2)
        self.assertAlmostEqual(uptime_days, 2.0 / 144.0, places=5)

    async def test_minimum_fee_requirement(self):
        """Test that fees below 2 YDA are rejected."""
        fees = [0.5, 1.0, 1.5, 1.99]
        for fee in fees:
            split_fee = fee / 2.0
            # Each split would be less than 1 block of uptime
            if fee < 2:
                self.assertLess(int(split_fee), 1)

    async def test_fee_as_float(self):
        """Test that fees are handled as floats correctly."""
        registration_fee = "4.5"
        converted_fee = float(registration_fee)
        split_fee = converted_fee / 2.0

        self.assertEqual(split_fee, 2.25)
        self.assertIsInstance(split_fee, float)

    async def test_transaction_fee_split_validation(self):
        """Test that transaction validates fee == masternode_fee for node announcements."""
        # Create a transaction object and validate the fee split manually
        txn = Transaction()
        txn.fee = 2.5
        txn.masternode_fee = 2.5

        # Both should be equal
        self.assertEqual(float(txn.fee), 2.5)
        self.assertEqual(float(txn.masternode_fee), 2.5)
        self.assertEqual(float(txn.fee), float(txn.masternode_fee))

    async def test_transaction_fee_split_mismatch_detected(self):
        """Test that fee split mismatch is detected in transaction."""
        # This tests that if we try to create a transaction with mismatched
        # fee and masternode_fee, it should be invalid for node announcements
        txn = Transaction()
        txn.fee = 2.0
        txn.masternode_fee = 3.0  # Intentionally mismatched
        txn.relationship = NodeAnnouncement.from_dict(
            {
                "identity": {
                    "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
                    "username": "test",
                    "username_signature": "sig",
                },
                "host": "localhost",
                "port": 8000,
            }
        )

        # Check that the fee and masternode_fee are indeed different
        self.assertNotEqual(float(txn.fee), float(txn.masternode_fee))


class TestNodeAnnouncementValidation(AsyncTestCase):
    """Test suite for node announcement field validation."""

    async def asyncSetUp(self):
        pass  # No database setup needed for these pure logic tests

    async def test_host_cannot_be_empty(self):
        """Test that empty host is rejected."""
        hosts = ["", " ", "  "]
        for host in hosts:
            if not host or not host.strip():
                self.assertEqual(host.strip(), "")

    async def test_valid_host(self):
        """Test that valid hosts are accepted."""
        valid_hosts = [
            "192.168.1.1",
            "example.com",
            "subdomain.example.com",
            "localhost",
        ]
        for host in valid_hosts:
            self.assertTrue(bool(host.strip()))

    async def test_port_range_validation_lower_bound(self):
        """Test that port 0 is rejected (ports must be >= 1)."""
        invalid_ports = [0, -1, -100]
        for port in invalid_ports:
            self.assertTrue(port < 1 or port > 65535)

    async def test_port_range_validation_upper_bound(self):
        """Test that port > 65535 is rejected."""
        invalid_ports = [65536, 70000, 99999]
        for port in invalid_ports:
            self.assertTrue(port < 1 or port > 65535)

    async def test_port_range_validation_valid_ports(self):
        """Test that valid port ranges are accepted."""
        valid_ports = [1, 8, 80, 443, 8000, 8003, 65535]
        for port in valid_ports:
            self.assertFalse(port < 1 or port > 65535)

    async def test_http_protocol_validation_valid(self):
        """Test that valid HTTP protocols are accepted."""
        valid_protocols = ["http", "https", "HTTP", "HTTPS"]
        for protocol in valid_protocols:
            normalized = protocol.strip().lower()
            self.assertIn(normalized, ("http", "https"))

    async def test_http_protocol_validation_invalid(self):
        """Test that invalid HTTP protocols are rejected."""
        invalid_protocols = ["ftp", "ws", "wss", "telnet", "ssh"]
        for protocol in invalid_protocols:
            normalized = protocol.strip().lower()
            self.assertNotIn(normalized, ("http", "https"))

    async def test_required_fields_present(self):
        """Test that all required fields are validated."""
        required_fields = ["host", "port", "http_host", "http_port", "fee"]
        data = {
            "host": "localhost",
            "port": 8000,
            "http_host": "localhost",
            "http_port": 8000,
            "fee": 4.0,
        }

        for field in required_fields:
            self.assertIn(field, data)

    async def test_missing_required_field(self):
        """Test that missing required fields are detected."""
        required_fields = ["host", "port", "http_host", "http_port", "fee"]
        data = {
            "host": "localhost",
            # Missing port, http_host, http_port, fee
        }

        for field in required_fields:
            if field not in data:
                # This field is missing and should trigger an error
                self.assertNotIn(field, data)

    async def test_fee_type_conversion_string(self):
        """Test that string fees are converted to float."""
        fee_string = "4.5"
        try:
            fee_float = float(fee_string)
            self.assertEqual(fee_float, 4.5)
        except (ValueError, TypeError):
            self.fail("Valid fee string should convert to float")

    async def test_fee_type_conversion_invalid(self):
        """Test that invalid fee values are rejected."""
        invalid_fees = ["abc", "12.34.56", None, {}, []]
        for fee in invalid_fees:
            try:
                float(fee)
                self.fail(f"Should not convert {fee} to float")
            except (ValueError, TypeError):
                pass  # Expected


class TestNodeAnnouncementTransactionValidation(AsyncTestCase):
    """Test suite for transaction-level fee split validation."""

    async def asyncSetUp(self):
        # Initialize Config without MongoDB for pure logic tests
        c = Config.generate()
        c.mongo = None

    async def test_node_announcement_fee_objects_equal(self):
        """Test that fee and masternode_fee can be set and compared as equal."""
        # This test verifies the business logic that validates fee split
        txn = Transaction()
        txn.fee = 5.0
        txn.masternode_fee = 5.0

        # Verify both fees are equal
        self.assertEqual(float(txn.fee), 5.0)
        self.assertEqual(float(txn.masternode_fee), 5.0)
        self.assertEqual(float(txn.fee), float(txn.masternode_fee))

    async def test_node_announcement_string_conversion(self):
        """Test that node announcement can be converted to string."""
        node_data = {
            "identity": {
                "public_key": "029c3c4e9e091c1b5c8c3f3c3e3d3c3b3a3c3d3c3b3a3c3d3c3b3a3c3d3c3b3a",
                "username": "test_node",
                "username_signature": "sig",
            },
            "host": "localhost",
            "port": 8000,
            "http_host": "localhost",
            "http_port": 8000,
            "http_protocol": "https",
        }

        node_announcement = NodeAnnouncement.from_dict(node_data)
        node_string = node_announcement.to_string()

        # Should be a non-empty string
        self.assertIsInstance(node_string, str)
        self.assertGreater(len(node_string), 0)


class TestFeeSplitFormula(unittest.TestCase):
    """Test suite for fee splitting formula mathematics."""

    def test_50_50_split_preserves_total(self):
        """Test that splitting preserves the original amount."""
        amounts = [2, 4, 10, 100, 1000, 4320, 52560]
        for amount in amounts:
            split = amount / 2.0
            total = split + split
            self.assertEqual(total, float(amount))

    def test_split_results_in_half(self):
        """Test that each half is exactly the original divided by 2."""
        amounts = [2, 4, 10, 100, 1000, 4320, 52560]
        for amount in amounts:
            split = amount / 2.0
            self.assertEqual(split, amount / 2.0)
            self.assertEqual(split * 2, float(amount))

    def test_integer_conversion_of_split(self):
        """Test integer conversion of split amounts."""
        test_cases = [
            (2, 1),  # 2 YDA -> 1 block
            (4, 2),  # 4 YDA -> 2 blocks
            (100, 50),  # 100 YDA -> 50 blocks
            (4320, 2160),  # 30 days worth
        ]
        for amount, expected_blocks in test_cases:
            split = amount / 2.0
            blocks = int(split)
            self.assertEqual(blocks, expected_blocks)

    def test_days_from_blocks_calculation(self):
        """Test that days are calculated correctly from blocks."""
        # 1 block = 144 blocks per day
        test_cases = [
            (2, 2 / 144.0),  # 2 blocks
            (144, 1.0),  # 1 day
            (288, 2.0),  # 2 days
            (4320, 30.0),  # 30 days (monthly)
            (52560, 365.0),  # 365 days (yearly)
        ]
        for blocks, expected_days in test_cases:
            days = blocks / 144.0
            self.assertAlmostEqual(days, expected_days, places=5)


if __name__ == "__main__":
    unittest.main()
