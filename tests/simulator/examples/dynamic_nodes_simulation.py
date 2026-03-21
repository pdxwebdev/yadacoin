"""
Example: Dynamic Nodes Simulation

This example demonstrates how to simulate dynamic nodes joining and leaving
the network, which is the main use case for testing the new dynamic nodes feature.
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from tests.simulator import DynamicNodeScenario, NetworkSimulator


async def main():
    """Run a dynamic nodes simulation"""

    print("=" * 70)
    print("DYNAMIC NODES SIMULATION - Testing Node Churn")
    print("=" * 70)
    print("\nThis simulation tests how the network handles nodes joining and leaving")
    print("dynamically, which is crucial for the dynamic nodes feature.\n")

    # Create simulator with realistic network conditions
    simulator = NetworkSimulator(
        latency_ms=50,  # 50ms latency
        packet_loss_rate=0.01,  # 1% packet loss
        max_connections_per_node=100,
    )
    await simulator.initialize()

    # Create the scenario
    scenario = DynamicNodeScenario(
        simulator=simulator,
        initial_seeds=3,
        initial_gateways=5,
        initial_providers=15,
        nodes_to_add=10,
        nodes_to_remove=5,
        churn_interval_seconds=1.0,
    )

    # Run the scenario
    print("Starting scenario execution...\n")
    results = await scenario.execute()

    # Print results
    print("\n" + "=" * 70)
    print("SIMULATION RESULTS")
    print("=" * 70)
    print(f"\nInitial Configuration:")
    print(f"  Seeds: {scenario.initial_seeds}")
    print(f"  Gateways: {scenario.initial_gateways}")
    print(f"  Providers: {scenario.initial_providers}")

    print(f"\nDynamic Changes:")
    print(f"  Nodes Added: {results['nodes_added']}")
    print(f"  Nodes Removed: {results['nodes_removed']}")
    print(f"  Final Node Count: {results['final_node_count']}")

    print(f"\nNetwork Health:")
    print(f"  Network Remained Functional: {results['network_remained_functional']}")

    baseline = results["baseline_stats"]
    final = results["final_stats"]

    print(f"\nBaseline Statistics:")
    print(f"  Total Transactions: {baseline['total_transactions']}")
    print(f"  Total Messages: {baseline['total_messages']}")
    print(
        f"  Avg Txn Propagation Time: {baseline['avg_transaction_propagation_time']:.3f}s"
    )

    print(f"\nFinal Statistics (after churn):")
    print(f"  Total Transactions: {final['total_transactions']}")
    print(f"  Total Messages: {final['total_messages']}")
    print(
        f"  Avg Txn Propagation Time: {final['avg_transaction_propagation_time']:.3f}s"
    )
    print(f"  Nodes Joined: {final['node_join_count']}")
    print(f"  Nodes Left: {final['node_leave_count']}")

    # Calculate impact
    if baseline["avg_transaction_propagation_time"] > 0:
        propagation_change = (
            (
                final["avg_transaction_propagation_time"]
                - baseline["avg_transaction_propagation_time"]
            )
            / baseline["avg_transaction_propagation_time"]
            * 100
        )
        print(f"\nPropagation Time Change: {propagation_change:+.1f}%")

    print("\n" + "=" * 70)
    print("KEY INSIGHTS")
    print("=" * 70)

    if results["network_remained_functional"]:
        print("✓ Network successfully handled node churn")
    else:
        print("✗ Network failed during node churn")

    if (
        final["avg_transaction_propagation_time"]
        < baseline["avg_transaction_propagation_time"] * 1.5
    ):
        print("✓ Propagation times remained reasonable despite churn")
    else:
        print("⚠ Propagation times degraded significantly during churn")

    remaining_ratio = results["final_node_count"] / (
        scenario.initial_seeds + scenario.initial_gateways + scenario.initial_providers
    )
    if remaining_ratio > 0.8:
        print(f"✓ Network maintained good size ({remaining_ratio*100:.1f}% of initial)")
    else:
        print(
            f"⚠ Network size reduced significantly ({remaining_ratio*100:.1f}% of initial)"
        )

    print("\n" + "=" * 70 + "\n")

    # Cleanup
    await simulator.shutdown()
    print("Simulation complete!")


async def quick_test():
    """Run a quick test for development/debugging"""

    print("\n" + "=" * 70)
    print("QUICK DYNAMIC NODES TEST (Fast Version)")
    print("=" * 70 + "\n")

    simulator = NetworkSimulator(latency_ms=10)
    await simulator.initialize()

    scenario = DynamicNodeScenario(
        simulator=simulator,
        initial_seeds=2,
        initial_gateways=3,
        initial_providers=5,
        nodes_to_add=3,
        nodes_to_remove=2,
        churn_interval_seconds=0.5,
    )

    results = await scenario.execute()

    print(f"\nQuick Test Results:")
    print(f"  Nodes Added: {results['nodes_added']}")
    print(f"  Nodes Removed: {results['nodes_removed']}")
    print(f"  Final Node Count: {results['final_node_count']}")
    print(f"  Network Functional: {results['network_remained_functional']}")

    await simulator.shutdown()
    print("\nQuick test complete!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        asyncio.run(quick_test())
    else:
        asyncio.run(main())
