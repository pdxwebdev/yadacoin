"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import socket
import unittest
from logging import getLogger
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.config import Config
from yadacoin.core.nodestester import NodesTester, _is_safe_ip

from ..test_setup import AsyncTestCase


class NodesTesterTestCase(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        config = Config()
        if not hasattr(config, "app_log"):
            config.app_log = getLogger("tornado.application")
        # Reset class-level state between tests
        NodesTester.permanently_failed_nodes = set()
        NodesTester.failed_nodes = set()
        NodesTester.successful_nodes = []
        NodesTester.all_nodes = []


class TestIsSafeIp(unittest.TestCase):
    def test_public_ip_is_safe(self):
        self.assertTrue(_is_safe_ip("8.8.8.8"))

    def test_loopback_is_blocked(self):
        self.assertFalse(_is_safe_ip("127.0.0.1"))

    def test_private_10_block_is_blocked(self):
        self.assertFalse(_is_safe_ip("10.0.0.1"))

    def test_private_192_168_is_blocked(self):
        self.assertFalse(_is_safe_ip("192.168.1.100"))

    def test_private_172_16_is_blocked(self):
        self.assertFalse(_is_safe_ip("172.16.0.1"))

    def test_link_local_is_blocked(self):
        self.assertFalse(_is_safe_ip("169.254.1.1"))

    def test_shared_address_space_is_blocked(self):
        self.assertFalse(_is_safe_ip("100.64.0.1"))

    def test_invalid_host_returns_false(self):
        self.assertFalse(_is_safe_ip("this.host.does.not.exist.invalid"))

    def test_public_ip_another(self):
        self.assertTrue(_is_safe_ip("1.1.1.1"))


class TestHasDns(NodesTesterTestCase):
    async def test_direct_ip_returns_true(self):
        result = await NodesTester.has_dns("8.8.8.8")
        self.assertTrue(result)

    async def test_ipv6_address_returns_true(self):
        result = await NodesTester.has_dns("2001:4860:4860::8888")
        self.assertTrue(result)

    async def test_valid_hostname_with_dns_returns_true(self):
        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            result = await NodesTester.has_dns("example.com")
        self.assertTrue(result)

    async def test_nonexistent_hostname_returns_false(self):
        with patch("socket.gethostbyname", side_effect=socket.gaierror("no DNS")):
            result = await NodesTester.has_dns("nonexistent123456789.invalid")
        self.assertFalse(result)


class FakeNodeClass:
    peer_type = "masternode"


def make_mock_node(host="8.8.8.8", http_port=8080, http_protocol="http"):
    node = MagicMock()
    node.host = host
    node.http_port = http_port
    node.http_protocol = http_protocol
    node.__class__ = FakeNodeClass
    return node


class TestTestNode(NodesTesterTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.semaphore = asyncio.Semaphore(10)

    async def test_node_in_permanently_failed_returns_none(self):
        NodesTester.permanently_failed_nodes.add("8.8.8.8")
        node = make_mock_node(host="8.8.8.8")
        result = await NodesTester.test_node(self.config, node, self.semaphore)
        self.assertIsNone(result)

    async def test_node_no_dns_returns_none(self):
        with patch.object(NodesTester, "has_dns", new=AsyncMock(return_value=False)):
            node = make_mock_node(host="nodns.invalid")
            result = await NodesTester.test_node(self.config, node, self.semaphore)
        self.assertIsNone(result)
        self.assertIn("nodns.invalid", NodesTester.permanently_failed_nodes)

    async def test_node_missing_http_port_returns_none(self):
        node = make_mock_node(host="9.9.9.9", http_port=None, http_protocol="http")
        with patch.object(NodesTester, "has_dns", new=AsyncMock(return_value=True)):
            result = await NodesTester.test_node(self.config, node, self.semaphore)
        self.assertIsNone(result)
        self.assertIn("9.9.9.9", NodesTester.permanently_failed_nodes)

    async def test_node_missing_http_protocol_returns_none(self):
        node = make_mock_node(host="9.9.9.9", http_port=8080, http_protocol=None)
        with patch.object(NodesTester, "has_dns", new=AsyncMock(return_value=True)):
            result = await NodesTester.test_node(self.config, node, self.semaphore)
        self.assertIsNone(result)
        self.assertIn("9.9.9.9", NodesTester.permanently_failed_nodes)

    async def test_node_invalid_protocol_returns_none(self):
        node = make_mock_node(host="9.9.9.9", http_port=8080, http_protocol="ftp")
        with patch.object(NodesTester, "has_dns", new=AsyncMock(return_value=True)):
            result = await NodesTester.test_node(self.config, node, self.semaphore)
        self.assertIsNone(result)
        self.assertIn("9.9.9.9", NodesTester.permanently_failed_nodes)

    async def test_node_private_ip_returns_none(self):
        node = make_mock_node(host="192.168.1.10", http_port=8080, http_protocol="http")
        with patch.object(NodesTester, "has_dns", new=AsyncMock(return_value=True)):
            with patch("yadacoin.core.nodestester._is_safe_ip", return_value=False):
                result = await NodesTester.test_node(self.config, node, self.semaphore)
        self.assertIsNone(result)
        self.assertIn("192.168.1.10", NodesTester.permanently_failed_nodes)

    async def test_node_http_200_matching_peer_type_returns_node(self):
        node = make_mock_node(host="8.8.8.8", http_port=8080, http_protocol="http")
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"peer_type": "masternode"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        with patch.object(NodesTester, "has_dns", new=AsyncMock(return_value=True)):
            with patch("yadacoin.core.nodestester._is_safe_ip", return_value=True):
                with patch("aiohttp.ClientSession", return_value=mock_session):
                    result = await NodesTester.test_node(
                        self.config, node, self.semaphore
                    )
        self.assertEqual(result, node)

    async def test_node_http_200_wrong_peer_type_returns_none(self):
        node = make_mock_node(host="8.8.8.8", http_port=8080, http_protocol="http")
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"peer_type": "other_type"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        with patch.object(NodesTester, "has_dns", new=AsyncMock(return_value=True)):
            with patch("yadacoin.core.nodestester._is_safe_ip", return_value=True):
                with patch("aiohttp.ClientSession", return_value=mock_session):
                    result = await NodesTester.test_node(
                        self.config, node, self.semaphore
                    )
        self.assertIsNone(result)

    async def test_node_http_exception_adds_to_failed(self):
        node = make_mock_node(host="8.8.8.8", http_port=8080, http_protocol="http")
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("connection error"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        with patch.object(NodesTester, "has_dns", new=AsyncMock(return_value=True)):
            with patch("yadacoin.core.nodestester._is_safe_ip", return_value=True):
                with patch("aiohttp.ClientSession", return_value=mock_session):
                    result = await NodesTester.test_node(
                        self.config, node, self.semaphore
                    )
        self.assertIsNone(result)
        self.assertIn("8.8.8.8", NodesTester.failed_nodes)

    async def test_node_http_non_200_returns_none(self):
        node = make_mock_node(host="8.8.8.8", http_port=8080, http_protocol="http")
        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        with patch.object(NodesTester, "has_dns", new=AsyncMock(return_value=True)):
            with patch("yadacoin.core.nodestester._is_safe_ip", return_value=True):
                with patch("aiohttp.ClientSession", return_value=mock_session):
                    result = await NodesTester.test_node(
                        self.config, node, self.semaphore
                    )
        self.assertIsNone(result)


class TestTestAllNodes(NodesTesterTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        # Set up async mongo mock
        mock_replace_one = AsyncMock()
        mock_tested_nodes = MagicMock()
        mock_tested_nodes.replace_one = mock_replace_one
        mock_async_db = MagicMock()
        mock_async_db.tested_nodes = mock_tested_nodes
        self.config.mongo.async_db = mock_async_db

    async def test_no_nodes_returns_empty(self):
        with patch(
            "yadacoin.core.nodestester.Nodes.get_all_nodes_for_block_height",
            return_value=[],
        ):
            result = await NodesTester.test_all_nodes(0)
        self.assertEqual(result, [])

    async def test_successful_nodes_are_collected(self):
        node = make_mock_node(host="8.8.8.8")
        node.to_dict = MagicMock(return_value={"host": "8.8.8.8"})
        with patch(
            "yadacoin.core.nodestester.Nodes.get_all_nodes_for_block_height",
            return_value=[node],
        ):
            with patch.object(
                NodesTester, "test_node", new=AsyncMock(return_value=node)
            ):
                result = await NodesTester.test_all_nodes(0)
        self.assertEqual(len(result), 1)
        self.assertEqual(NodesTester.successful_nodes, [node])

    async def test_no_successful_nodes_falls_back_to_nodes_to_test(self):
        node = make_mock_node(host="8.8.8.8")
        node.to_dict = MagicMock(return_value={"host": "8.8.8.8"})
        with patch(
            "yadacoin.core.nodestester.Nodes.get_all_nodes_for_block_height",
            return_value=[node],
        ):
            with patch.object(
                NodesTester, "test_node", new=AsyncMock(return_value=None)
            ):
                result = await NodesTester.test_all_nodes(0)
        self.assertEqual(result, [])
        # Should fall back to nodes_to_test
        self.assertEqual(NodesTester.successful_nodes, [node])

    async def test_no_nodes_to_test_uses_all_nodes(self):
        node = make_mock_node(host="8.8.8.8")
        node.to_dict = MagicMock(return_value={"host": "8.8.8.8"})
        # Mark node as permanently failed so nodes_to_test is empty
        NodesTester.permanently_failed_nodes.add("8.8.8.8")
        with patch(
            "yadacoin.core.nodestester.Nodes.get_all_nodes_for_block_height",
            return_value=[node],
        ):
            result = await NodesTester.test_all_nodes(0)
        self.assertEqual(result, [])
        # Should fall back to all_nodes
        self.assertEqual(NodesTester.successful_nodes, [node])
        self.assertEqual(NodesTester.permanently_failed_nodes, set())


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
