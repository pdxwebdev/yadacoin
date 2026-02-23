"""
Network Simulator - Core Network Management

This module provides the main NetworkSimulator class that manages
a simulated blockchain network for testing purposes.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from yadacoin.core.block import Block
from yadacoin.core.transaction import Transaction


@dataclass
class NetworkStats:
    """Statistics about network performance"""

    total_blocks_created: int = 0
    total_transactions: int = 0
    total_messages: int = 0
    blocks_propagated: Dict[str, int] = field(default_factory=dict)
    transactions_propagated: Dict[str, int] = field(default_factory=dict)
    avg_block_propagation_time: float = 0.0
    avg_transaction_propagation_time: float = 0.0
    node_join_count: int = 0
    node_leave_count: int = 0

    def to_dict(self):
        return {
            "total_blocks_created": self.total_blocks_created,
            "total_transactions": self.total_transactions,
            "total_messages": self.total_messages,
            "blocks_propagated": self.blocks_propagated,
            "transactions_propagated": self.transactions_propagated,
            "avg_block_propagation_time": self.avg_block_propagation_time,
            "avg_transaction_propagation_time": self.avg_transaction_propagation_time,
            "node_join_count": self.node_join_count,
            "node_leave_count": self.node_leave_count,
        }


class NetworkSimulator:
    """
    Main network simulator for YadaCoin blockchain testing.

    This class provides a complete simulated network environment where you can:
    - Add/remove nodes dynamically
    - Simulate block propagation
    - Simulate transaction propagation
    - Test network partitions and mergers
    - Collect statistics on network behavior

    Example usage:
        simulator = NetworkSimulator()
        await simulator.initialize()

        # Add nodes
        await simulator.add_node("seed1", "seed")
        await simulator.add_node("gateway1", "seed_gateway")
        await simulator.add_node("provider1", "service_provider")

        # Connect nodes
        simulator.connect_nodes("seed1", "gateway1")
        simulator.connect_nodes("gateway1", "provider1")

        # Simulate activity
        await simulator.propagate_block(block)
        await simulator.propagate_transaction(transaction)
    """

    def __init__(
        self,
        latency_ms: int = 100,
        packet_loss_rate: float = 0.0,
        max_connections_per_node: int = 100,
    ):
        """
        Initialize the network simulator.

        Args:
            latency_ms: Base network latency in milliseconds
            packet_loss_rate: Probability of packet loss (0.0 to 1.0)
            max_connections_per_node: Maximum connections per node
        """
        from .simnode import SimulatedNode

        self.nodes: Dict[str, SimulatedNode] = {}
        self.connections: Dict[str, Set[str]] = defaultdict(set)
        self.latency_ms = latency_ms
        self.packet_loss_rate = packet_loss_rate
        self.max_connections_per_node = max_connections_per_node

        # Network state
        self.blockchain: List[Block] = []
        self.mempool: List[Transaction] = []
        self.current_block_height = 0

        # Statistics
        self.stats = NetworkStats()
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.running = False

        # Propagation tracking
        self.block_propagation_times: Dict[str, List[float]] = defaultdict(list)
        self.transaction_propagation_times: Dict[str, List[float]] = defaultdict(list)

    async def initialize(self):
        """Initialize the simulator and start background tasks"""
        self.running = True
        asyncio.create_task(self._process_message_queue())

    async def shutdown(self):
        """Shutdown the simulator gracefully"""
        self.running = False
        await asyncio.sleep(0.1)  # Let queue processing finish

    async def add_node(
        self,
        node_id: str,
        node_type: str,
        host: str = "127.0.0.1",
        port: int = 8000,
        **kwargs,
    ) -> "SimulatedNode":
        """
        Add a new node to the network.

        Args:
            node_id: Unique identifier for the node
            node_type: Type of node ("seed", "seed_gateway", "service_provider")
            host: Host address
            port: Port number
            **kwargs: Additional node configuration

        Returns:
            The created SimulatedNode
        """
        from .simnode import SimulatedNode

        if node_id in self.nodes:
            raise ValueError(f"Node {node_id} already exists")

        node = SimulatedNode(
            node_id=node_id,
            node_type=node_type,
            host=host,
            port=port,
            simulator=self,
            **kwargs,
        )

        self.nodes[node_id] = node
        self.connections[node_id] = set()
        self.stats.node_join_count += 1

        await node.start()

        return node

    async def remove_node(self, node_id: str):
        """
        Remove a node from the network.

        Args:
            node_id: ID of the node to remove
        """
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")

        node = self.nodes[node_id]
        await node.stop()

        # Disconnect all connections
        for connected_id in list(self.connections[node_id]):
            self.disconnect_nodes(node_id, connected_id)

        del self.nodes[node_id]
        del self.connections[node_id]
        self.stats.node_leave_count += 1

    def connect_nodes(self, node1_id: str, node2_id: str):
        """
        Create a bidirectional connection between two nodes.

        Args:
            node1_id: First node ID
            node2_id: Second node ID
        """
        if node1_id not in self.nodes or node2_id not in self.nodes:
            raise ValueError("One or both nodes not found")

        if len(self.connections[node1_id]) >= self.max_connections_per_node:
            raise ValueError(f"Node {node1_id} has reached max connections")

        if len(self.connections[node2_id]) >= self.max_connections_per_node:
            raise ValueError(f"Node {node2_id} has reached max connections")

        self.connections[node1_id].add(node2_id)
        self.connections[node2_id].add(node1_id)

        self.nodes[node1_id].add_peer(self.nodes[node2_id])
        self.nodes[node2_id].add_peer(self.nodes[node1_id])

    def disconnect_nodes(self, node1_id: str, node2_id: str):
        """
        Remove the connection between two nodes.

        Args:
            node1_id: First node ID
            node2_id: Second node ID
        """
        if node1_id in self.connections:
            self.connections[node1_id].discard(node2_id)
            self.nodes[node1_id].remove_peer(node2_id)

        if node2_id in self.connections:
            self.connections[node2_id].discard(node1_id)
            self.nodes[node2_id].remove_peer(node1_id)

    def get_connected_nodes(self, node_id: str) -> List[str]:
        """Get list of node IDs connected to the given node"""
        return list(self.connections.get(node_id, []))

    async def propagate_block(self, block: Block, source_node_id: Optional[str] = None):
        """
        Propagate a block through the network.

        Args:
            block: Block to propagate
            source_node_id: ID of the node that created/received the block first
        """
        start_time = time.time()
        visited = set()

        if source_node_id:
            visited.add(source_node_id)
            await self.nodes[source_node_id].receive_block(block)

        # BFS propagation
        queue = [source_node_id] if source_node_id else list(self.nodes.keys())

        while queue:
            current_id = queue.pop(0)

            for connected_id in self.connections[current_id]:
                if connected_id not in visited:
                    visited.add(connected_id)

                    # Simulate network latency
                    await asyncio.sleep(self.latency_ms / 1000.0)

                    # Simulate packet loss
                    if self.packet_loss_rate > 0:
                        import random

                        if random.random() < self.packet_loss_rate:
                            continue

                    await self.nodes[connected_id].receive_block(block)
                    queue.append(connected_id)

                    self.stats.total_messages += 1

        propagation_time = time.time() - start_time
        self.block_propagation_times[block.hash].append(propagation_time)
        self.stats.blocks_propagated[block.hash] = len(visited)
        self.stats.total_blocks_created += 1

        # Update average
        all_times = [
            t for times in self.block_propagation_times.values() for t in times
        ]
        if all_times:
            self.stats.avg_block_propagation_time = sum(all_times) / len(all_times)

    async def propagate_transaction(
        self, transaction: Transaction, source_node_id: Optional[str] = None
    ):
        """
        Propagate a transaction through the network.

        Args:
            transaction: Transaction to propagate
            source_node_id: ID of the node that created/received the transaction first
        """
        start_time = time.time()
        visited = set()

        if source_node_id:
            visited.add(source_node_id)
            await self.nodes[source_node_id].receive_transaction(transaction)

        # BFS propagation
        queue = [source_node_id] if source_node_id else list(self.nodes.keys())

        while queue:
            current_id = queue.pop(0)

            for connected_id in self.connections[current_id]:
                if connected_id not in visited:
                    visited.add(connected_id)

                    # Simulate network latency
                    await asyncio.sleep(self.latency_ms / 1000.0)

                    # Simulate packet loss
                    if self.packet_loss_rate > 0:
                        import random

                        if random.random() < self.packet_loss_rate:
                            continue

                    await self.nodes[connected_id].receive_transaction(transaction)
                    queue.append(connected_id)

                    self.stats.total_messages += 1

        propagation_time = time.time() - start_time
        self.transaction_propagation_times[transaction.transaction_signature].append(
            propagation_time
        )
        self.stats.transactions_propagated[transaction.transaction_signature] = len(
            visited
        )
        self.stats.total_transactions += 1

        # Update average
        all_times = [
            t for times in self.transaction_propagation_times.values() for t in times
        ]
        if all_times:
            self.stats.avg_transaction_propagation_time = sum(all_times) / len(
                all_times
            )

    async def _process_message_queue(self):
        """Background task to process message queue"""
        while self.running:
            try:
                await asyncio.sleep(0.01)
                # Process any queued messages
            except Exception as e:
                print(f"Error processing message queue: {e}")

    def create_network_partition(self, group1_ids: List[str], group2_ids: List[str]):
        """
        Create a network partition between two groups of nodes.

        Args:
            group1_ids: List of node IDs in first partition
            group2_ids: List of node IDs in second partition
        """
        for node1_id in group1_ids:
            for node2_id in group2_ids:
                if node2_id in self.connections[node1_id]:
                    self.disconnect_nodes(node1_id, node2_id)

    def heal_network_partition(self, group1_ids: List[str], group2_ids: List[str]):
        """
        Heal a network partition by reconnecting nodes.

        Args:
            group1_ids: List of node IDs in first partition
            group2_ids: List of node IDs in second partition
        """
        # Reconnect a subset of nodes between partitions
        for i, node1_id in enumerate(group1_ids[:2]):  # Connect first 2 from each side
            for j, node2_id in enumerate(group2_ids[:2]):
                try:
                    self.connect_nodes(node1_id, node2_id)
                except ValueError:
                    pass  # Already connected or max connections reached

    def get_network_topology(self) -> Dict[str, List[str]]:
        """Get the current network topology"""
        return {node_id: list(peers) for node_id, peers in self.connections.items()}

    def get_statistics(self) -> Dict:
        """Get current network statistics"""
        return self.stats.to_dict()

    def reset_statistics(self):
        """Reset all statistics"""
        self.stats = NetworkStats()
        self.block_propagation_times.clear()
        self.transaction_propagation_times.clear()

    async def auto_connect_new_node(self, new_node_id: str, num_connections: int = 3):
        """
        Automatically connect a new node to existing nodes based on node type.

        Args:
            new_node_id: ID of the new node
            num_connections: Number of connections to create
        """
        new_node = self.nodes[new_node_id]
        node_type = new_node.node_type

        # Find appropriate peers based on node type
        potential_peers = []

        if node_type == "seed":
            # Seeds connect to other seeds
            potential_peers = [
                nid
                for nid, n in self.nodes.items()
                if n.node_type == "seed" and nid != new_node_id
            ]
        elif node_type == "seed_gateway":
            # Gateways connect to seeds
            potential_peers = [
                nid
                for nid, n in self.nodes.items()
                if n.node_type == "seed" and nid != new_node_id
            ]
        elif node_type == "service_provider":
            # Providers connect to gateways
            potential_peers = [
                nid
                for nid, n in self.nodes.items()
                if n.node_type == "seed_gateway" and nid != new_node_id
            ]

        # Connect to random peers
        import random

        peers_to_connect = random.sample(
            potential_peers, min(num_connections, len(potential_peers))
        )

        for peer_id in peers_to_connect:
            try:
                self.connect_nodes(new_node_id, peer_id)
            except ValueError as e:
                print(f"Could not connect {new_node_id} to {peer_id}: {e}")

    def print_network_status(self):
        """Print a summary of the network status"""
        print("\n" + "=" * 60)
        print("NETWORK STATUS")
        print("=" * 60)
        print(f"Total Nodes: {len(self.nodes)}")
        print(
            f"Total Connections: {sum(len(peers) for peers in self.connections.values()) // 2}"
        )
        print(f"\nNodes by Type:")

        type_counts = defaultdict(int)
        for node in self.nodes.values():
            type_counts[node.node_type] += 1

        for node_type, count in sorted(type_counts.items()):
            print(f"  {node_type}: {count}")

        print(f"\nStatistics:")
        print(f"  Blocks Propagated: {self.stats.total_blocks_created}")
        print(f"  Transactions Propagated: {self.stats.total_transactions}")
        print(f"  Total Messages: {self.stats.total_messages}")
        print(
            f"  Avg Block Propagation Time: {self.stats.avg_block_propagation_time:.3f}s"
        )
        print(
            f"  Avg Txn Propagation Time: {self.stats.avg_transaction_propagation_time:.3f}s"
        )
        print(f"  Nodes Joined: {self.stats.node_join_count}")
        print(f"  Nodes Left: {self.stats.node_leave_count}")
        print("=" * 60 + "\n")
