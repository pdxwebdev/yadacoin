"""
Network Simulation Scenarios

This module provides pre-built scenarios for testing various
network behaviors, including dynamic nodes, network partitions,
and stress testing.
"""

import asyncio
import random

from yadacoin.core.transaction import Transaction

from .network import NetworkSimulator


class BaseScenario:
    """Base class for network simulation scenarios"""

    def __init__(self, simulator: NetworkSimulator):
        self.simulator = simulator
        self.results = {}

    async def setup(self):
        """Setup the scenario (override in subclasses)"""

    async def run(self):
        """Run the scenario (override in subclasses)"""

    async def teardown(self):
        """Cleanup after scenario (override in subclasses)"""

    async def execute(self):
        """Execute the full scenario lifecycle"""
        await self.setup()
        await self.run()
        await self.teardown()
        return self.results


class DynamicNodeScenario(BaseScenario):
    """
    Scenario for testing dynamic node joining and leaving.

    This scenario:
    1. Creates an initial network topology
    2. Adds nodes dynamically over time
    3. Removes nodes dynamically
    4. Measures network resilience and propagation during churn
    """

    def __init__(
        self,
        simulator: NetworkSimulator,
        initial_seeds: int = 3,
        initial_gateways: int = 5,
        initial_providers: int = 20,
        nodes_to_add: int = 10,
        nodes_to_remove: int = 5,
        churn_interval_seconds: float = 2.0,
    ):
        super().__init__(simulator)
        self.initial_seeds = initial_seeds
        self.initial_gateways = initial_gateways
        self.initial_providers = initial_providers
        self.nodes_to_add = nodes_to_add
        self.nodes_to_remove = nodes_to_remove
        self.churn_interval_seconds = churn_interval_seconds

        self.added_nodes = []
        self.removed_nodes = []

    async def setup(self):
        """Setup initial network topology"""
        print("Setting up initial network topology...")

        # Create seeds
        for i in range(self.initial_seeds):
            node = await self.simulator.add_node(
                f"seed_{i}", "seed", host=f"10.0.0.{i+1}", port=8000 + i
            )
            self.added_nodes.append(node.node_id)

        # Connect seeds to each other
        for i in range(self.initial_seeds):
            for j in range(i + 1, self.initial_seeds):
                self.simulator.connect_nodes(f"seed_{i}", f"seed_{j}")

        # Create gateways
        for i in range(self.initial_gateways):
            node = await self.simulator.add_node(
                f"gateway_{i}", "seed_gateway", host=f"10.0.1.{i+1}", port=8000 + i
            )
            self.added_nodes.append(node.node_id)

            # Connect to random seeds
            for seed_id in random.sample(
                [f"seed_{j}" for j in range(self.initial_seeds)],
                min(2, self.initial_seeds),
            ):
                self.simulator.connect_nodes(node.node_id, seed_id)

        # Create providers
        for i in range(self.initial_providers):
            node = await self.simulator.add_node(
                f"provider_{i}", "service_provider", host=f"10.0.2.{i+1}", port=8000 + i
            )
            self.added_nodes.append(node.node_id)

            # Connect to random gateways
            gateway_ids = [f"gateway_{j}" for j in range(self.initial_gateways)]
            for gateway_id in random.sample(gateway_ids, min(2, self.initial_gateways)):
                self.simulator.connect_nodes(node.node_id, gateway_id)

        print(f"Initial network: {len(self.simulator.nodes)} nodes")
        self.simulator.print_network_status()

    async def run(self):
        """Run the dynamic node scenario"""
        print("\n" + "=" * 60)
        print("STARTING DYNAMIC NODE SCENARIO")
        print("=" * 60 + "\n")

        # Phase 1: Stable network with some activity
        print("Phase 1: Baseline network activity...")
        await self._simulate_network_activity(duration=5)
        baseline_stats = self.simulator.get_statistics()

        # Phase 2: Add nodes dynamically
        print(f"\nPhase 2: Adding {self.nodes_to_add} nodes dynamically...")
        for i in range(self.nodes_to_add):
            node_type = random.choice(["seed_gateway", "service_provider"])
            node_id = f"dynamic_{node_type}_{i}"

            node = await self.simulator.add_node(
                node_id, node_type, host=f"10.0.3.{i+1}", port=9000 + i
            )

            # Auto-connect to appropriate peers
            await self.simulator.auto_connect_new_node(node_id, num_connections=3)

            print(f"  Added {node_type} node: {node_id}")
            self.added_nodes.append(node_id)

            # Simulate some activity
            await self._simulate_network_activity(duration=self.churn_interval_seconds)

        self.simulator.print_network_status()

        # Phase 3: Remove nodes dynamically
        print(f"\nPhase 3: Removing {self.nodes_to_remove} nodes dynamically...")
        removable_nodes = [
            nid
            for nid in self.simulator.nodes.keys()
            if nid.startswith("provider_") or nid.startswith("dynamic_")
        ]

        nodes_to_remove = random.sample(
            removable_nodes, min(self.nodes_to_remove, len(removable_nodes))
        )

        for node_id in nodes_to_remove:
            print(f"  Removing node: {node_id}")
            await self.simulator.remove_node(node_id)
            self.removed_nodes.append(node_id)

            # Simulate some activity
            await self._simulate_network_activity(duration=self.churn_interval_seconds)

        self.simulator.print_network_status()

        # Phase 4: Final stability test
        print("\nPhase 4: Testing network stability after churn...")
        await self._simulate_network_activity(duration=5)
        final_stats = self.simulator.get_statistics()

        # Store results
        self.results = {
            "baseline_stats": baseline_stats,
            "final_stats": final_stats,
            "nodes_added": len(self.added_nodes),
            "nodes_removed": len(self.removed_nodes),
            "final_node_count": len(self.simulator.nodes),
            "network_remained_functional": final_stats["total_messages"] > 0,
        }

        print("\n" + "=" * 60)
        print("DYNAMIC NODE SCENARIO COMPLETED")
        print("=" * 60)
        print(f"Nodes added: {self.results['nodes_added']}")
        print(f"Nodes removed: {self.results['nodes_removed']}")
        print(f"Final node count: {self.results['final_node_count']}")
        print(f"Network functional: {self.results['network_remained_functional']}")
        print("=" * 60 + "\n")

    async def _simulate_network_activity(self, duration: float):
        """Simulate transactions and blocks for a given duration"""
        end_time = asyncio.get_event_loop().time() + duration

        while asyncio.get_event_loop().time() < end_time:
            # Create and broadcast a transaction
            random_node = random.choice(list(self.simulator.nodes.values()))

            try:
                # Create a simple transaction
                tx = await self._create_test_transaction(random_node)
                await self.simulator.propagate_transaction(tx, random_node.node_id)
            except Exception as e:
                print(f"Error creating transaction: {e}")

            await asyncio.sleep(0.5)

    async def _create_test_transaction(self, node):
        """Create a test transaction from a node"""
        from yadacoin.core.transaction import Output

        outputs = [Output.from_dict({"value": 1.0, "to": "test_address"})]

        tx = await Transaction.generate(
            public_key=node.public_key,
            private_key=node.private_key,
            outputs=outputs,
        )

        return tx


class NetworkPartitionScenario(BaseScenario):
    """
    Scenario for testing network partition and healing.

    This scenario:
    1. Creates a network
    2. Partitions it into two groups
    3. Simulates activity in both partitions
    4. Heals the partition
    5. Measures convergence time
    """

    def __init__(
        self,
        simulator: NetworkSimulator,
        total_nodes: int = 20,
        partition_duration: float = 10.0,
    ):
        super().__init__(simulator)
        self.total_nodes = total_nodes
        self.partition_duration = partition_duration
        self.group1 = []
        self.group2 = []

    async def setup(self):
        """Setup network for partition testing"""
        print("Setting up network for partition testing...")

        # Create nodes
        for i in range(self.total_nodes):
            node_type = "service_provider" if i > 2 else "seed"
            await self.simulator.add_node(
                f"node_{i}", node_type, host=f"10.0.0.{i+1}", port=8000 + i
            )

        # Connect all nodes
        for i in range(self.total_nodes):
            for j in range(i + 1, min(i + 4, self.total_nodes)):
                try:
                    self.simulator.connect_nodes(f"node_{i}", f"node_{j}")
                except:
                    pass

        # Divide into two groups
        half = self.total_nodes // 2
        self.group1 = [f"node_{i}" for i in range(half)]
        self.group2 = [f"node_{i}" for i in range(half, self.total_nodes)]

        print(f"Created network with {self.total_nodes} nodes")
        print(f"Group 1: {len(self.group1)} nodes")
        print(f"Group 2: {len(self.group2)} nodes")

    async def run(self):
        """Run partition scenario"""
        print("\n" + "=" * 60)
        print("STARTING NETWORK PARTITION SCENARIO")
        print("=" * 60 + "\n")

        # Phase 1: Normal operation
        print("Phase 1: Normal network operation...")
        await asyncio.sleep(2)

        # Phase 2: Create partition
        print("\nPhase 2: Creating network partition...")
        self.simulator.create_network_partition(self.group1, self.group2)
        print("Network partitioned!")

        # Simulate activity in partition
        await asyncio.sleep(self.partition_duration)

        # Phase 3: Heal partition
        print("\nPhase 3: Healing network partition...")
        self.simulator.heal_network_partition(self.group1, self.group2)
        print("Network healed!")

        # Wait for convergence
        await asyncio.sleep(5)

        self.results = {
            "partition_duration": self.partition_duration,
            "group1_size": len(self.group1),
            "group2_size": len(self.group2),
            "final_stats": self.simulator.get_statistics(),
        }

        print("\n" + "=" * 60)
        print("NETWORK PARTITION SCENARIO COMPLETED")
        print("=" * 60 + "\n")


class StressTestScenario(BaseScenario):
    """
    Scenario for stress testing the network with high load.

    This scenario:
    1. Creates a large network
    2. Floods with transactions
    3. Measures throughput and propagation times
    """

    def __init__(
        self,
        simulator: NetworkSimulator,
        num_nodes: int = 50,
        transactions_per_second: int = 100,
        duration_seconds: float = 30.0,
    ):
        super().__init__(simulator)
        self.num_nodes = num_nodes
        self.transactions_per_second = transactions_per_second
        self.duration_seconds = duration_seconds

    async def setup(self):
        """Setup large network"""
        print(f"Setting up stress test network with {self.num_nodes} nodes...")

        # Create a mix of nodes
        num_seeds = max(3, self.num_nodes // 10)
        num_gateways = max(5, self.num_nodes // 5)
        num_providers = self.num_nodes - num_seeds - num_gateways

        # Create seeds
        for i in range(num_seeds):
            await self.simulator.add_node(f"seed_{i}", "seed")

        # Create gateways
        for i in range(num_gateways):
            node = await self.simulator.add_node(f"gateway_{i}", "seed_gateway")
            await self.simulator.auto_connect_new_node(node.node_id, 2)

        # Create providers
        for i in range(num_providers):
            node = await self.simulator.add_node(f"provider_{i}", "service_provider")
            await self.simulator.auto_connect_new_node(node.node_id, 3)

        print(f"Network created with {len(self.simulator.nodes)} nodes")

    async def run(self):
        """Run stress test"""
        print("\n" + "=" * 60)
        print("STARTING STRESS TEST SCENARIO")
        print("=" * 60 + "\n")

        print(
            f"Generating {self.transactions_per_second} txns/sec for {self.duration_seconds}s..."
        )

        start_time = asyncio.get_event_loop().time()
        end_time = start_time + self.duration_seconds

        interval = 1.0 / self.transactions_per_second

        while asyncio.get_event_loop().time() < end_time:
            # Create transaction from random node
            node = random.choice(list(self.simulator.nodes.values()))

            try:
                from yadacoin.core.transaction import Output

                outputs = [Output.from_dict({"value": 1.0, "to": "test"})]
                tx = await Transaction.generate(
                    public_key=node.public_key,
                    private_key=node.private_key,
                    outputs=outputs,
                )

                await self.simulator.propagate_transaction(tx, node.node_id)
            except:
                pass

            await asyncio.sleep(interval)

        self.results = {
            "duration": self.duration_seconds,
            "target_tps": self.transactions_per_second,
            "total_nodes": len(self.simulator.nodes),
            "final_stats": self.simulator.get_statistics(),
        }

        stats = self.simulator.get_statistics()
        actual_tps = stats["total_transactions"] / self.duration_seconds

        print("\n" + "=" * 60)
        print("STRESS TEST COMPLETED")
        print("=" * 60)
        print(f"Target TPS: {self.transactions_per_second}")
        print(f"Actual TPS: {actual_tps:.2f}")
        print(f"Total transactions: {stats['total_transactions']}")
        print(f"Avg propagation time: {stats['avg_transaction_propagation_time']:.3f}s")
        print("=" * 60 + "\n")
