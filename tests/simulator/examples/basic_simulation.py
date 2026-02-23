"""
Example: Basic Network Simulation

This example demonstrates basic usage of the network simulator.
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tests.simulator import NetworkSimulator


async def main():
    """Run a basic network simulation"""

    # Create simulator with 100ms latency
    simulator = NetworkSimulator(latency_ms=100, packet_loss_rate=0.0)
    await simulator.initialize()

    print("=" * 60)
    print("BASIC NETWORK SIMULATION")
    print("=" * 60)

    # Create some seed nodes
    print("\n1. Creating seed nodes...")
    seed1 = await simulator.add_node("seed1", "seed", host="10.0.0.1", port=8000)
    seed2 = await simulator.add_node("seed2", "seed", host="10.0.0.2", port=8001)
    seed3 = await simulator.add_node("seed3", "seed", host="10.0.0.3", port=8002)
    print(f"   Created {len(simulator.nodes)} seed nodes")

    # Connect seeds to each other
    print("\n2. Connecting seed nodes...")
    simulator.connect_nodes("seed1", "seed2")
    simulator.connect_nodes("seed2", "seed3")
    simulator.connect_nodes("seed3", "seed1")
    print("   Seeds connected in a triangle topology")

    # Create gateway nodes
    print("\n3. Creating gateway nodes...")
    for i in range(3):
        gateway = await simulator.add_node(
            f"gateway{i}", "seed_gateway", host=f"10.0.1.{i+1}", port=8100 + i
        )
        # Connect each gateway to 2 random seeds
        await simulator.auto_connect_new_node(f"gateway{i}", num_connections=2)
    print(f"   Created {simulator.stats.node_join_count - 3} gateway nodes")

    # Create service provider nodes
    print("\n4. Creating service provider nodes...")
    for i in range(10):
        provider = await simulator.add_node(
            f"provider{i}", "service_provider", host=f"10.0.2.{i+1}", port=8200 + i
        )
        # Connect each provider to 2 gateways
        await simulator.auto_connect_new_node(f"provider{i}", num_connections=2)
    print(f"   Created 10 service provider nodes")

    # Print network status
    print("\n5. Network topology created:")
    simulator.print_network_status()

    # Simulate some network activity
    print("6. Simulating network activity...")
    from yadacoin.core.transaction import Output, Transaction

    # Create and propagate a transaction
    node = simulator.nodes["provider0"]
    outputs = [Output.from_dict({"value": 1.0, "to": "test_address"})]

    try:
        tx = await Transaction.generate(
            public_key=node.public_key,
            private_key=node.private_key,
            outputs=outputs,
        )

        print(f"   Broadcasting transaction from provider0...")
        await simulator.propagate_transaction(tx, "provider0")
        print(
            f"   Transaction propagated to {simulator.stats.transactions_propagated.get(tx.transaction_signature, 0)} nodes"
        )
    except Exception as e:
        print(f"   Note: Transaction creation requires full YadaCoin environment: {e}")

    # Print final statistics
    print("\n7. Final network statistics:")
    simulator.print_network_status()

    # Cleanup
    await simulator.shutdown()
    print("\nSimulation complete!")


if __name__ == "__main__":
    asyncio.run(main())
