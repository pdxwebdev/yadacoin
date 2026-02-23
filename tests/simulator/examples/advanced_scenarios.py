"""
Example: Network Partition and Healing

This example demonstrates how to simulate network partitions (split-brain scenarios)
and test the network's ability to heal and converge.
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from tests.simulator import NetworkSimulator
from tests.simulator.scenarios import NetworkPartitionScenario, StressTestScenario


async def partition_example():
    """Run a network partition simulation"""

    print("=" * 70)
    print("NETWORK PARTITION SIMULATION")
    print("=" * 70)
    print("\nThis simulation tests network resilience to partitions and healing.\n")

    simulator = NetworkSimulator(latency_ms=50)
    await simulator.initialize()

    scenario = NetworkPartitionScenario(
        simulator=simulator, total_nodes=20, partition_duration=5.0
    )

    results = await scenario.execute()

    print("\n" + "=" * 70)
    print("PARTITION SIMULATION RESULTS")
    print("=" * 70)
    print(f"\nPartition Configuration:")
    print(f"  Total Nodes: {len(simulator.nodes)}")
    print(f"  Partition Duration: {results['partition_duration']}s")
    print(f"  Group 1 Size: {results['group1_size']}")
    print(f"  Group 2 Size: {results['group2_size']}")

    final_stats = results["final_stats"]
    print(f"\nFinal Network Statistics:")
    print(f"  Total Messages: {final_stats['total_messages']}")
    print(f"  Blocks Propagated: {final_stats['total_blocks_created']}")
    print(f"  Transactions Propagated: {final_stats['total_transactions']}")

    print("\n" + "=" * 70 + "\n")

    await simulator.shutdown()


async def stress_test_example():
    """Run a stress test simulation"""

    print("=" * 70)
    print("STRESS TEST SIMULATION")
    print("=" * 70)
    print("\nThis simulation tests network performance under high load.\n")

    simulator = NetworkSimulator(latency_ms=50, packet_loss_rate=0.02)
    await simulator.initialize()

    scenario = StressTestScenario(
        simulator=simulator,
        num_nodes=30,
        transactions_per_second=50,
        duration_seconds=10.0,
    )

    results = await scenario.execute()

    print("\n" + "=" * 70)
    print("STRESS TEST RESULTS")
    print("=" * 70)

    stats = results["final_stats"]
    actual_tps = stats["total_transactions"] / results["duration"]

    print(f"\nConfiguration:")
    print(f"  Total Nodes: {results['total_nodes']}")
    print(f"  Target TPS: {results['target_tps']}")
    print(f"  Duration: {results['duration']}s")

    print(f"\nPerformance:")
    print(f"  Actual TPS: {actual_tps:.2f}")
    print(f"  Total Transactions: {stats['total_transactions']}")
    print(f"  Total Messages: {stats['total_messages']}")
    print(f"  Avg Propagation Time: {stats['avg_transaction_propagation_time']:.3f}s")

    efficiency = (actual_tps / results["target_tps"]) * 100
    print(f"\nEfficiency: {efficiency:.1f}%")

    if efficiency > 80:
        print("✓ Network handled load efficiently")
    elif efficiency > 50:
        print("⚠ Network struggled with load but remained functional")
    else:
        print("✗ Network could not sustain target load")

    print("\n" + "=" * 70 + "\n")

    await simulator.shutdown()


async def combined_test():
    """Run multiple tests in sequence"""

    print("\n" + "=" * 70)
    print("COMBINED NETWORK TESTS")
    print("=" * 70 + "\n")

    print("Running test suite...\n")

    print("Test 1: Network Partition")
    print("-" * 70)
    await partition_example()

    print("\nTest 2: Stress Test")
    print("-" * 70)
    await stress_test_example()

    print("\nAll tests complete!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "partition":
            asyncio.run(partition_example())
        elif sys.argv[1] == "stress":
            asyncio.run(stress_test_example())
        elif sys.argv[1] == "combined":
            asyncio.run(combined_test())
        else:
            print("Usage: python advanced_scenarios.py [partition|stress|combined]")
    else:
        asyncio.run(combined_test())
