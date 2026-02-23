"""
Simulated Node - Individual Node Behavior

This module provides the SimulatedNode class which represents
an individual node in the simulated network.
"""

import asyncio
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Set

from yadacoin.core.block import Block
from yadacoin.core.peer import Identity
from yadacoin.core.transaction import Transaction

if TYPE_CHECKING:
    from yadacoin.core.consensus import Consensus


class SimulatedNode:
    """
    Represents a single node in the simulated network.

    Each node can:
    - Receive and store blocks
    - Receive and store transactions
    - Maintain a local view of the blockchain
    - Track connected peers
    - Simulate mining (optional)
    """

    def __init__(
        self,
        node_id: str,
        node_type: str,
        host: str,
        port: int,
        simulator: "NetworkSimulator",
        public_key: Optional[str] = None,
        private_key: Optional[str] = None,
        consensus: Optional["Consensus"] = None,
        **kwargs,
    ):
        """
        Initialize a simulated node.

        Args:
            node_id: Unique identifier for this node
            node_type: Type of node ("seed", "seed_gateway", "service_provider")
            host: Host address
            port: Port number
            simulator: Reference to the NetworkSimulator
            public_key: Node's public key (generated if not provided)
            private_key: Node's private key (generated if not provided)
            consensus: Optional Consensus instance for real validation (if None, uses simplified validation)
        """
        self.node_id = node_id
        self.node_type = node_type
        self.host = host
        self.port = port
        self.simulator = simulator
        self.consensus = consensus

        # Generate keys if not provided
        if not public_key or not private_key:
            from yadacoin.core.transactionutils import TU

            public_key, private_key = TU.generate_deterministic_signature()

        self.public_key = public_key
        self.private_key = private_key

        # Identity
        self.identity = Identity(
            username=f"sim_node_{node_id}", username_signature="", public_key=public_key
        )

        # Node state
        self.blockchain: List[Block] = []
        self.mempool: List[Transaction] = []
        self.seen_blocks: Set[str] = set()
        self.seen_transactions: Set[str] = set()

        # Peer management
        self.peers: Dict[str, "SimulatedNode"] = {}

        # Statistics
        self.blocks_received = 0
        self.transactions_received = 0
        self.blocks_sent = 0
        self.transactions_sent = 0
        self.uptime_start = None

        # Configuration
        self.is_mining = kwargs.get("is_mining", False)
        self.processing_delay_ms = kwargs.get("processing_delay_ms", 10)

        # State
        self.running = False

    async def start(self):
        """Start the node"""
        self.running = True
        self.uptime_start = time.time()

        if self.is_mining:
            asyncio.create_task(self._mining_loop())

    async def stop(self):
        """Stop the node"""
        self.running = False

    def add_peer(self, peer: "SimulatedNode"):
        """Add a peer connection"""
        self.peers[peer.node_id] = peer

    def remove_peer(self, peer_id: str):
        """Remove a peer connection"""
        if peer_id in self.peers:
            del self.peers[peer_id]

    async def receive_block(self, block: Block):
        """
        Receive a block from the network.

        Args:
            block: The block received
        """
        # Skip if already seen
        if block.hash in self.seen_blocks:
            return

        self.seen_blocks.add(block.hash)
        self.blocks_received += 1

        # Simulate processing delay
        await asyncio.sleep(self.processing_delay_ms / 1000.0)

        # Add to blockchain if valid (simplified validation)
        if await self._validate_block(block):
            self.blockchain.append(block)

            # Remove confirmed transactions from mempool
            confirmed_sigs = {tx.transaction_signature for tx in block.transactions}
            self.mempool = [
                tx
                for tx in self.mempool
                if tx.transaction_signature not in confirmed_sigs
            ]

    async def receive_transaction(self, transaction: Transaction):
        """
        Receive a transaction from the network.

        Args:
            transaction: The transaction received
        """
        # Skip if already seen
        if transaction.transaction_signature in self.seen_transactions:
            return

        self.seen_transactions.add(transaction.transaction_signature)
        self.transactions_received += 1

        # Simulate processing delay
        await asyncio.sleep(self.processing_delay_ms / 1000.0)

        # Add to mempool if valid (simplified validation)
        if await self._validate_transaction(transaction):
            self.mempool.append(transaction)

    async def _validate_block(self, block: Block) -> bool:
        """
        Validate block using real consensus rules if available.

        Args:
            block: Block to validate

        Returns:
            True if valid, False otherwise
        """
        if not block.hash:
            return False

        # Use real block validation if available
        if self.consensus:
            try:
                # Use the real block.verify() method
                await block.verify()
                return True
            except Exception:
                # Log validation error and reject block
                return False

        # Fallback: simplified validation if no consensus engine
        # Check if block builds on our chain
        if block.index > 0:
            if not self.blockchain:
                return False
            if block.prev_hash != self.blockchain[-1].hash:
                return False
            if block.index != len(self.blockchain):
                return False

        return True

    async def _validate_transaction(self, transaction: Transaction) -> bool:
        """
        Validate transaction using real consensus rules if available.

        Args:
            transaction: Transaction to validate

        Returns:
            True if valid, False otherwise
        """
        if not transaction.transaction_signature:
            return False

        # Check if not already in mempool
        if any(
            tx.transaction_signature == transaction.transaction_signature
            for tx in self.mempool
        ):
            return False

        # Use real transaction validation if available
        if self.consensus:
            try:
                # Use the real transaction.verify() method
                await transaction.verify()
                return True
            except Exception:
                # Log validation error and reject transaction
                return False

        return True

    async def _mining_loop(self):
        """Background mining loop (simplified)"""
        while self.running:
            await asyncio.sleep(10)  # Mine every 10 seconds

            if self.mempool:
                # Create a new block
                try:
                    prev_hash = self.blockchain[-1].hash if self.blockchain else ""
                    index = len(self.blockchain)

                    # Take up to 100 transactions from mempool
                    transactions = self.mempool[:100]

                    block = await Block.generate(
                        transactions=transactions,
                        public_key=self.public_key,
                        private_key=self.private_key,
                        index=index,
                        prev_hash=prev_hash,
                    )

                    # Propagate to network
                    await self.simulator.propagate_block(block, self.node_id)

                except Exception as e:
                    print(f"Mining error on node {self.node_id}: {e}")

    async def broadcast_transaction(self, transaction: Transaction):
        """
        Broadcast a transaction to the network.

        Args:
            transaction: Transaction to broadcast
        """
        self.transactions_sent += 1
        await self.simulator.propagate_transaction(transaction, self.node_id)

    async def broadcast_block(self, block: Block):
        """
        Broadcast a block to the network.

        Args:
            block: Block to broadcast
        """
        self.blocks_sent += 1
        await self.simulator.propagate_block(block, self.node_id)

    def get_blockchain_height(self) -> int:
        """Get the current blockchain height"""
        return len(self.blockchain)

    def get_mempool_size(self) -> int:
        """Get the current mempool size"""
        return len(self.mempool)

    def get_uptime(self) -> float:
        """Get node uptime in seconds"""
        if self.uptime_start:
            return time.time() - self.uptime_start
        return 0.0

    def get_stats(self) -> Dict:
        """Get node statistics"""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "blockchain_height": self.get_blockchain_height(),
            "mempool_size": self.get_mempool_size(),
            "blocks_received": self.blocks_received,
            "transactions_received": self.transactions_received,
            "blocks_sent": self.blocks_sent,
            "transactions_sent": self.transactions_sent,
            "peers_count": len(self.peers),
            "uptime_seconds": self.get_uptime(),
            "is_running": self.running,
        }

    def to_dict(self) -> Dict:
        """Convert node to dictionary representation"""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "host": self.host,
            "port": self.port,
            "public_key": self.public_key,
            "identity": {
                "username": self.identity.username,
                "public_key": self.identity.public_key,
            },
        }

    def __repr__(self):
        return (
            f"SimulatedNode(id={self.node_id}, type={self.node_type}, "
            f"height={self.get_blockchain_height()}, peers={len(self.peers)})"
        )
