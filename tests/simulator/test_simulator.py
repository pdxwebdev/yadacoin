"""
Unit tests for the Network Simulator

This module contains tests for the network simulator functionality.
"""

import asyncio
import os
import sys
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tests.simulator import DynamicNodeScenario, NetworkSimulator
from tests.simulator.scenarios import NetworkPartitionScenario, StressTestScenario


class TestNetworkSimulator(unittest.TestCase):
    """Test NetworkSimulator functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.simulator = NetworkSimulator(latency_ms=10, packet_loss_rate=0.0)

    def tearDown(self):
        """Clean up after tests"""
        asyncio.run(self.simulator.shutdown())

    def test_initialization(self):
        """Test simulator initialization"""
        self.assertEqual(len(self.simulator.nodes), 0)
        self.assertEqual(self.simulator.latency_ms, 10)
        self.assertEqual(self.simulator.packet_loss_rate, 0.0)

    def test_add_node(self):
        """Test adding a node to the network"""

        async def run_test():
            await self.simulator.initialize()

            node = await self.simulator.add_node(
                "test_node_1", "seed", host="127.0.0.1", port=8000
            )

            self.assertEqual(len(self.simulator.nodes), 1)
            self.assertEqual(node.node_id, "test_node_1")
            self.assertEqual(node.node_type, "seed")

        asyncio.run(run_test())

    def test_remove_node(self):
        """Test removing a node from the network"""

        async def run_test():
            await self.simulator.initialize()

            await self.simulator.add_node("test_node_1", "seed")
            await self.simulator.add_node("test_node_2", "seed")

            self.assertEqual(len(self.simulator.nodes), 2)

            await self.simulator.remove_node("test_node_1")

            self.assertEqual(len(self.simulator.nodes), 1)
            self.assertNotIn("test_node_1", self.simulator.nodes)

        asyncio.run(run_test())

    def test_connect_nodes(self):
        """Test connecting two nodes"""

        async def run_test():
            await self.simulator.initialize()

            await self.simulator.add_node("node1", "seed")
            await self.simulator.add_node("node2", "seed")

            self.simulator.connect_nodes("node1", "node2")

            self.assertIn("node2", self.simulator.connections["node1"])
            self.assertIn("node1", self.simulator.connections["node2"])

        asyncio.run(run_test())

    def test_disconnect_nodes(self):
        """Test disconnecting two nodes"""

        async def run_test():
            await self.simulator.initialize()

            await self.simulator.add_node("node1", "seed")
            await self.simulator.add_node("node2", "seed")

            self.simulator.connect_nodes("node1", "node2")
            self.simulator.disconnect_nodes("node1", "node2")

            self.assertNotIn("node2", self.simulator.connections["node1"])
            self.assertNotIn("node1", self.simulator.connections["node2"])

        asyncio.run(run_test())

    def test_network_topology(self):
        """Test getting network topology"""

        async def run_test():
            await self.simulator.initialize()

            await self.simulator.add_node("node1", "seed")
            await self.simulator.add_node("node2", "seed")
            await self.simulator.add_node("node3", "seed")

            self.simulator.connect_nodes("node1", "node2")
            self.simulator.connect_nodes("node2", "node3")

            topology = self.simulator.get_network_topology()

            self.assertEqual(len(topology), 3)
            self.assertIn("node2", topology["node1"])
            self.assertIn("node3", topology["node2"])

        asyncio.run(run_test())

    def test_statistics_tracking(self):
        """Test that statistics are tracked correctly"""
        stats = self.simulator.get_statistics()

        self.assertIn("total_blocks_created", stats)
        self.assertIn("total_transactions", stats)
        self.assertIn("total_messages", stats)

    def test_auto_connect_new_node(self):
        """Test automatic connection of new nodes"""

        async def run_test():
            await self.simulator.initialize()

            # Create some seeds
            await self.simulator.add_node("seed1", "seed")
            await self.simulator.add_node("seed2", "seed")

            # Add a gateway that should connect to seeds
            await self.simulator.add_node("gateway1", "seed_gateway")
            await self.simulator.auto_connect_new_node("gateway1", num_connections=2)

            # Check that gateway is connected to seeds
            connections = self.simulator.get_connected_nodes("gateway1")
            self.assertGreater(len(connections), 0)

        asyncio.run(run_test())


class TestSimulatedNode(unittest.TestCase):
    """Test SimulatedNode functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.simulator = NetworkSimulator()

    def tearDown(self):
        """Clean up after tests"""
        asyncio.run(self.simulator.shutdown())

    def test_node_initialization(self):
        """Test node initialization"""

        async def run_test():
            await self.simulator.initialize()
            node = await self.simulator.add_node("test_node", "seed")

            self.assertEqual(node.node_id, "test_node")
            self.assertEqual(node.node_type, "seed")
            self.assertIsNotNone(node.public_key)
            self.assertIsNotNone(node.private_key)

        asyncio.run(run_test())

    def test_node_stats(self):
        """Test node statistics"""

        async def run_test():
            await self.simulator.initialize()
            node = await self.simulator.add_node("test_node", "seed")

            stats = node.get_stats()

            self.assertIn("node_id", stats)
            self.assertIn("blockchain_height", stats)
            self.assertIn("mempool_size", stats)
            self.assertIn("blocks_received", stats)
            self.assertIn("transactions_received", stats)

        asyncio.run(run_test())

    def test_node_uptime(self):
        """Test node uptime tracking"""

        async def run_test():
            await self.simulator.initialize()
            node = await self.simulator.add_node("test_node", "seed")

            await asyncio.sleep(0.1)

            uptime = node.get_uptime()
            self.assertGreater(uptime, 0)

        asyncio.run(run_test())


class TestDynamicNodeScenario(unittest.TestCase):
    """Test DynamicNodeScenario"""

    def setUp(self):
        """Set up test fixtures"""
        self.simulator = NetworkSimulator(latency_ms=10)

    def tearDown(self):
        """Clean up after tests"""
        asyncio.run(self.simulator.shutdown())

    def test_scenario_initialization(self):
        """Test scenario initialization"""
        scenario = DynamicNodeScenario(
            self.simulator,
            initial_seeds=2,
            initial_gateways=3,
            initial_providers=5,
            nodes_to_add=3,
            nodes_to_remove=2,
        )

        self.assertEqual(scenario.initial_seeds, 2)
        self.assertEqual(scenario.initial_gateways, 3)
        self.assertEqual(scenario.nodes_to_add, 3)

    def test_scenario_setup(self):
        """Test scenario setup phase"""

        async def run_test():
            await self.simulator.initialize()

            scenario = DynamicNodeScenario(
                self.simulator,
                initial_seeds=2,
                initial_gateways=2,
                initial_providers=3,
                nodes_to_add=0,
                nodes_to_remove=0,
            )

            await scenario.setup()

            # Should have created 2 seeds + 2 gateways + 3 providers = 7 nodes
            self.assertEqual(len(self.simulator.nodes), 7)

        asyncio.run(run_test())


class TestNetworkPartitionScenario(unittest.TestCase):
    """Test NetworkPartitionScenario"""

    def setUp(self):
        """Set up test fixtures"""
        self.simulator = NetworkSimulator(latency_ms=10)

    def tearDown(self):
        """Clean up after tests"""
        asyncio.run(self.simulator.shutdown())

    def test_partition_setup(self):
        """Test partition scenario setup"""

        async def run_test():
            await self.simulator.initialize()

            scenario = NetworkPartitionScenario(
                self.simulator,
                total_nodes=10,
                partition_duration=1.0,
            )

            await scenario.setup()

            self.assertEqual(len(self.simulator.nodes), 10)
            self.assertEqual(len(scenario.group1), 5)
            self.assertEqual(len(scenario.group2), 5)

        asyncio.run(run_test())


class TestStressTestScenario(unittest.TestCase):
    """Test StressTestScenario"""

    def setUp(self):
        """Set up test fixtures"""
        self.simulator = NetworkSimulator(latency_ms=10)

    def tearDown(self):
        """Clean up after tests"""
        asyncio.run(self.simulator.shutdown())

    def test_stress_test_setup(self):
        """Test stress test scenario setup"""

        async def run_test():
            await self.simulator.initialize()

            scenario = StressTestScenario(
                self.simulator,
                num_nodes=10,
                transactions_per_second=10,
                duration_seconds=1.0,
            )

            await scenario.setup()

            self.assertEqual(len(self.simulator.nodes), 10)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
