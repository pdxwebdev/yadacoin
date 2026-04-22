"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import os
import sys
import unittest

from ..test_setup import AsyncTestCase

parent_dir = os.path.abspath(
    os.path.join(
        os.path.dirname(os.path.realpath(__file__)), os.pardir, os.pardir, os.pardir
    )
)
sys.path.insert(0, parent_dir)
parent_dir = os.path.abspath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir, os.pardir)
)
sys.path.insert(0, parent_dir)
parent_dir = os.path.abspath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir)
)
sys.path.insert(0, parent_dir)


class TestNode(AsyncTestCase):
    async def test_scenerio_1(self):
        """One block ahead, no fork"""


class TestNodeTrackers(unittest.TestCase):
    """Tests for tracker to_dict() methods (coverage for lines 56, 63, 71, 78)."""

    def test_node_server_disconnect_tracker_to_dict(self):
        from yadacoin.tcpsocket.node import NodeServerDisconnectTracker

        tracker = NodeServerDisconnectTracker()
        result = tracker.to_dict()
        self.assertIn("by_host", result)
        self.assertIn("by_reason", result)

    def test_node_server_new_txn_tracker_to_dict(self):
        from yadacoin.tcpsocket.node import NodeServerNewTxnTracker

        tracker = NodeServerNewTxnTracker()
        result = tracker.to_dict()
        self.assertIn("by_host", result)

    def test_node_client_disconnect_tracker_to_dict(self):
        from yadacoin.tcpsocket.node import NodeClientDisconnectTracker

        tracker = NodeClientDisconnectTracker()
        result = tracker.to_dict()
        self.assertIn("by_host", result)
        self.assertIn("by_reason", result)

    def test_node_client_new_txn_tracker_to_dict(self):
        from yadacoin.tcpsocket.node import NodeClientNewTxnTracker

        tracker = NodeClientNewTxnTracker()
        result = tracker.to_dict()
        self.assertIn("by_host", result)
