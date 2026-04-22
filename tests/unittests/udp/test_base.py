"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from ipaddress import IPv4Address

from yadacoin.udp.base import (
    DEFAULT_FORWARDER,
    DNSQueryFailed,
    MultipleForwardersForInterface,
    NoActiveRecordForHost,
    NoForwardersConfigured,
    get_active_redirect_record_for_host,
    get_all_forwarders,
    get_default_forwarder,
    get_forwarders_by_interface,
)


class TestDefaultForwarder(unittest.TestCase):
    def test_default_forwarder_is_string(self):
        self.assertIsInstance(DEFAULT_FORWARDER, str)

    def test_default_forwarder_value(self):
        self.assertEqual(DEFAULT_FORWARDER, "0.0.0.0")


class TestGetAllForwarders(unittest.TestCase):
    def test_returns_list(self):
        result = get_all_forwarders()
        self.assertIsInstance(result, list)

    def test_returns_copy(self):
        result1 = get_all_forwarders()
        result2 = get_all_forwarders()
        self.assertIsNot(result1, result2)

    def test_contains_known_forwarder(self):
        result = get_all_forwarders()
        self.assertIn("208.67.222.222", result)


class TestGetForwardersByInterface(unittest.TestCase):
    def test_returns_list(self):
        result = get_forwarders_by_interface("eth0")
        self.assertIsInstance(result, list)


class TestGetDefaultForwarder(unittest.TestCase):
    def test_returns_list(self):
        result = get_default_forwarder()
        self.assertIsInstance(result, list)


class TestGetActiveRedirectRecord(unittest.TestCase):
    def test_yadaproxy_host_returns_record(self):
        record = get_active_redirect_record_for_host("foo.yadaproxy")
        self.assertIsInstance(record, dict)
        self.assertIn("redirect_host", record)
        self.assertTrue(record.get("active"))

    def test_non_yadaproxy_host_raises(self):
        with self.assertRaises(NoActiveRecordForHost):
            get_active_redirect_record_for_host("www.google.com")

    def test_host_with_trailing_dot_stripped(self):
        # trailing dot should be stripped before checking
        record = get_active_redirect_record_for_host("foo.yadaproxy.")
        self.assertIsInstance(record, dict)

    def test_non_yadaproxy_raises_correct_exception(self):
        try:
            get_active_redirect_record_for_host("example.com")
        except NoActiveRecordForHost as e:
            self.assertIn("example.com", str(e))


class TestExceptionClasses(unittest.TestCase):
    def test_multiple_forwarders_is_exception(self):
        self.assertTrue(issubclass(MultipleForwardersForInterface, Exception))

    def test_dns_query_failed_is_exception(self):
        self.assertTrue(issubclass(DNSQueryFailed, Exception))

    def test_no_active_record_is_exception(self):
        self.assertTrue(issubclass(NoActiveRecordForHost, Exception))

    def test_no_forwarders_is_exception(self):
        self.assertTrue(issubclass(NoForwardersConfigured, Exception))

    def test_raise_multiple_forwarders(self):
        with self.assertRaises(MultipleForwardersForInterface):
            raise MultipleForwardersForInterface("test")

    def test_raise_dns_query_failed(self):
        with self.assertRaises(DNSQueryFailed):
            raise DNSQueryFailed("query failed")

    def test_raise_no_active_record(self):
        with self.assertRaises(NoActiveRecordForHost):
            raise NoActiveRecordForHost("host")

    def test_raise_no_forwarders(self):
        with self.assertRaises(NoForwardersConfigured):
            raise NoForwardersConfigured("no forwarders")


class TestDNSQuery(unittest.TestCase):
    """Tests for DNSQuery using mocked DNS wire data."""

    def _make_query_data(self, name="www.google.com"):
        """Build minimal DNS query wire data for the given name."""
        import struct

        parts = name.split(".")
        question = b""
        for part in parts:
            encoded = part.encode()
            question += struct.pack("B", len(encoded)) + encoded
        question += b"\x00"  # end of name
        question += b"\x00\x01"  # QTYPE A
        question += b"\x00\x01"  # QCLASS IN
        # DNS message: ID, flags, QDCOUNT=1, ANCOUNT=0, NSCOUNT=0, ARCOUNT=0
        header = struct.pack("!HHHHHH", 1234, 0x0100, 1, 0, 0, 0)
        return header + question

    def test_dns_query_init_with_mock(self):
        """Test DNSQuery can be instantiated with mocked wire data."""
        from yadacoin.udp.base import DNSQuery

        data = self._make_query_data("www.google.com")
        query = DNSQuery(
            data=data, client_address=("192.168.1.1", 5353), interface="eth0"
        )
        self.assertIsNotNone(query.question)
        self.assertEqual(query.interface, "eth0")
        self.assertIsNone(query.ip)

    def test_dns_query_default_interface(self):
        from yadacoin.udp.base import DNSQuery

        data = self._make_query_data("test.example.com")
        query = DNSQuery(data=data)
        self.assertEqual(query.interface, "default")

    def test_dns_query_bad_reply_returns_bytes(self):
        from yadacoin.udp.base import DNSQuery

        data = self._make_query_data("www.google.com")
        query = DNSQuery(data=data, client_address=("192.168.1.1", 5353))
        result = query._bad_reply()
        self.assertIsInstance(result, bytes)

    def test_dns_query_bad_reply_sets_localhost(self):
        from yadacoin.udp.base import DNSQuery

        data = self._make_query_data("www.google.com")
        query = DNSQuery(data=data, client_address=("192.168.1.1", 5353))
        query._bad_reply()
        self.assertEqual(query.ip, IPv4Address("127.0.0.1"))

    def test_dns_query_ip_setter(self):
        from yadacoin.udp.base import DNSQuery

        data = self._make_query_data("www.google.com")
        query = DNSQuery(data=data)
        query.ip = "192.168.100.1"
        self.assertEqual(query.ip, IPv4Address("192.168.100.1"))


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
