#!/usr/bin/env python3
"""
Network Simulator - Main Execution Script

Quick access to all simulator functionality.
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tests.simulator import DynamicNodeScenario, NetworkSimulator
from tests.simulator.scenarios import NetworkPartitionScenario, StressTestScenario


def print_menu():
    """Print main menu"""
    print("\n" + "=" * 70)
    print("YADACOIN NETWORK SIMULATOR")
    print("=" * 70)
    print("\nAvailable Simulations:")
    print("  1. Dynamic Nodes (Full) - Test nodes joining/leaving network")
    print("  2. Dynamic Nodes (Quick) - Fast version for development")
    print("  3. Network Partition - Test network split and healing")
    print("  4. Stress Test - High load performance testing")
    print("  5. Custom - Interactive custom simulation")
    print("  6. Run All Tests")
    print("  0. Exit")
    print("\n" + "=" * 70)


async def run_dynamic_nodes_full():
    """Run full dynamic nodes simulation"""
    print("\n>>> Running Full Dynamic Nodes Simulation")

    simulator = NetworkSimulator(latency_ms=50, packet_loss_rate=0.01)
    await simulator.initialize()

    scenario = DynamicNodeScenario(
        simulator=simulator,
        initial_seeds=3,
        initial_gateways=5,
        initial_providers=15,
        nodes_to_add=10,
        nodes_to_remove=5,
        churn_interval_seconds=1.0,
    )

    results = await scenario.execute()

    print("\n✓ Dynamic Nodes Simulation Complete")
    print(f"  Network Functional: {results['network_remained_functional']}")
    print(f"  Final Node Count: {results['final_node_count']}")

    await simulator.shutdown()


async def run_dynamic_nodes_quick():
    """Run quick dynamic nodes simulation"""
    print("\n>>> Running Quick Dynamic Nodes Simulation")

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

    print("\n✓ Quick Test Complete")
    print(f"  Nodes Added: {results['nodes_added']}")
    print(f"  Nodes Removed: {results['nodes_removed']}")
    print(f"  Network Functional: {results['network_remained_functional']}")

    await simulator.shutdown()


async def run_network_partition():
    """Run network partition simulation"""
    print("\n>>> Running Network Partition Simulation")

    simulator = NetworkSimulator(latency_ms=50)
    await simulator.initialize()

    scenario = NetworkPartitionScenario(
        simulator=simulator, total_nodes=20, partition_duration=5.0
    )

    results = await scenario.execute()

    print("\n✓ Network Partition Test Complete")
    print(f"  Total Nodes: {len(simulator.nodes)}")
    print(f"  Partition Duration: {results['partition_duration']}s")

    await simulator.shutdown()


async def run_stress_test():
    """Run stress test simulation"""
    print("\n>>> Running Stress Test Simulation")

    simulator = NetworkSimulator(latency_ms=50, packet_loss_rate=0.02)
    await simulator.initialize()

    scenario = StressTestScenario(
        simulator=simulator,
        num_nodes=30,
        transactions_per_second=50,
        duration_seconds=10.0,
    )

    results = await scenario.execute()

    stats = results["final_stats"]
    actual_tps = stats["total_transactions"] / results["duration"]

    print("\n✓ Stress Test Complete")
    print(f"  Target TPS: {results['target_tps']}")
    print(f"  Actual TPS: {actual_tps:.2f}")
    print(f"  Efficiency: {(actual_tps / results['target_tps'] * 100):.1f}%")

    await simulator.shutdown()


async def run_custom():
    """Run custom interactive simulation"""
    print("\n>>> Custom Simulation Mode")
    print("Creating basic network...")

    simulator = NetworkSimulator(latency_ms=100)
    await simulator.initialize()

    # Create a small network
    for i in range(3):
        await simulator.add_node(f"seed_{i}", "seed")

    for i in range(3):
        await simulator.add_node(f"gateway_{i}", "seed_gateway")
        await simulator.auto_connect_new_node(f"gateway_{i}", 2)

    for i in range(10):
        await simulator.add_node(f"provider_{i}", "service_provider")
        await simulator.auto_connect_new_node(f"provider_{i}", 2)

    simulator.print_network_status()

    print("\nCustom network created. You can now:")
    print("  - Add more nodes programmatically")
    print("  - Run custom scenarios")
    print("  - Analyze network behavior")

    await simulator.shutdown()


async def run_all_tests():
    """Run all tests sequentially"""
    print("\n>>> Running All Tests")

    tests = [
        ("Dynamic Nodes (Quick)", run_dynamic_nodes_quick),
        ("Network Partition", run_network_partition),
        ("Stress Test", run_stress_test),
    ]

    for name, test_func in tests:
        print(f"\n{'='*70}")
        print(f"Running: {name}")
        print("=" * 70)
        try:
            await test_func()
        except Exception as e:
            print(f"✗ Test failed: {e}")
        await asyncio.sleep(1)

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)


async def interactive_mode():
    """Run simulator in interactive mode"""
    while True:
        print_menu()

        try:
            choice = input("\nSelect option (0-6): ").strip()

            if choice == "0":
                print("\nExiting simulator. Goodbye!")
                break
            elif choice == "1":
                await run_dynamic_nodes_full()
            elif choice == "2":
                await run_dynamic_nodes_quick()
            elif choice == "3":
                await run_network_partition()
            elif choice == "4":
                await run_stress_test()
            elif choice == "5":
                await run_custom()
            elif choice == "6":
                await run_all_tests()
            else:
                print("\n✗ Invalid option. Please try again.")

            input("\nPress Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n✗ Interrupted by user. Exiting...")
            break
        except Exception as e:
            print(f"\n✗ Error: {e}")
            input("\nPress Enter to continue...")


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        # Command line mode
        command = sys.argv[1].lower()

        if command == "dynamic":
            asyncio.run(run_dynamic_nodes_full())
        elif command == "dynamic-quick":
            asyncio.run(run_dynamic_nodes_quick())
        elif command == "partition":
            asyncio.run(run_network_partition())
        elif command == "stress":
            asyncio.run(run_stress_test())
        elif command == "custom":
            asyncio.run(run_custom())
        elif command == "all":
            asyncio.run(run_all_tests())
        else:
            print(
                "Usage: python run_simulator.py [dynamic|dynamic-quick|partition|stress|custom|all]"
            )
            print("   Or: python run_simulator.py (for interactive mode)")
    else:
        # Interactive mode
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
