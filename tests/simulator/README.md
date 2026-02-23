# YadaCoin Network Simulator

A comprehensive network simulation framework for testing YadaCoin blockchain features, with a focus on dynamic node behavior.

## Overview

The Network Simulator provides a complete testing environment for YadaCoin's peer-to-peer network. It allows you to:

- Simulate large-scale networks with hundreds of nodes
- Test dynamic node joining and leaving (node churn)
- Simulate network partitions and healing
- Measure block and transaction propagation
- Stress test under high load
- Experiment with different network topologies

## Directory Structure

```
tests/simulator/
├── __init__.py              # Package initialization
├── network.py               # Main NetworkSimulator class
├── simnode.py               # SimulatedNode class
├── scenarios.py             # Pre-built test scenarios
├── test_simulator.py        # Unit tests
├── examples/                # Example scripts
│   ├── basic_simulation.py
│   ├── dynamic_nodes_simulation.py
│   └── advanced_scenarios.py
└── README.md               # This file
```

## Quick Start

### Basic Usage

```python
import asyncio
from tests.simulator import NetworkSimulator

async def main():
    # Create simulator
    simulator = NetworkSimulator(latency_ms=100)
    await simulator.initialize()

    # Add nodes
    await simulator.add_node("seed1", "seed")
    await simulator.add_node("gateway1", "seed_gateway")
    await simulator.add_node("provider1", "service_provider")

    # Connect nodes
    simulator.connect_nodes("seed1", "gateway1")
    simulator.connect_nodes("gateway1", "provider1")

    # Print network status
    simulator.print_network_status()

    # Cleanup
    await simulator.shutdown()

asyncio.run(main())
```

### Testing Dynamic Nodes

The primary use case - testing nodes joining and leaving:

```python
from tests.simulator import NetworkSimulator, DynamicNodeScenario

async def test_dynamic_nodes():
    simulator = NetworkSimulator(latency_ms=50)
    await simulator.initialize()

    scenario = DynamicNodeScenario(
        simulator=simulator,
        initial_seeds=3,
        initial_gateways=5,
        initial_providers=15,
        nodes_to_add=10,
        nodes_to_remove=5
    )

    results = await scenario.execute()
    print(f"Network functional: {results['network_remained_functional']}")

    await simulator.shutdown()
```

## Running Examples

### Basic Simulation

```bash
cd tests/simulator/examples
python basic_simulation.py
```

### Dynamic Nodes Test (Full)

```bash
python dynamic_nodes_simulation.py
```

### Dynamic Nodes Test (Quick)

```bash
python dynamic_nodes_simulation.py --quick
```

### Advanced Scenarios

```bash
# Run all tests
python advanced_scenarios.py combined

# Run only partition test
python advanced_scenarios.py partition

# Run only stress test
python advanced_scenarios.py stress
```

## Core Components

### NetworkSimulator

The main class that manages the entire simulated network.

**Key Methods:**

- `add_node()` - Add a new node to the network
- `remove_node()` - Remove a node from the network
- `connect_nodes()` - Create bidirectional connection between nodes
- `disconnect_nodes()` - Remove connection between nodes
- `propagate_block()` - Simulate block propagation
- `propagate_transaction()` - Simulate transaction propagation
- `auto_connect_new_node()` - Automatically connect new nodes based on type
- `create_network_partition()` - Create network partition for testing
- `heal_network_partition()` - Heal network partition
- `get_statistics()` - Get network performance statistics

**Configuration:**

```python
simulator = NetworkSimulator(
    latency_ms=100,              # Base network latency
    packet_loss_rate=0.01,       # 1% packet loss
    max_connections_per_node=100 # Max connections per node
)
```

### SimulatedNode

Represents an individual node in the network.

**Node Types:**

- `seed` - Seed nodes (core network nodes)
- `seed_gateway` - Gateway nodes connecting to seeds
- `service_provider` - Service provider nodes

**Key Features:**

- Maintains local blockchain copy
- Tracks mempool (pending transactions)
- Records statistics (blocks/transactions received)
- Can simulate mining
- Validates blocks and transactions

### Pre-built Scenarios

#### DynamicNodeScenario

Tests network behavior during node churn (joining/leaving).

**Configuration:**

```python
scenario = DynamicNodeScenario(
    simulator=simulator,
    initial_seeds=3,           # Initial seed nodes
    initial_gateways=5,        # Initial gateway nodes
    initial_providers=20,      # Initial provider nodes
    nodes_to_add=10,           # How many nodes to add
    nodes_to_remove=5,         # How many nodes to remove
    churn_interval_seconds=2.0 # Time between changes
)
```

**Test Phases:**

1. Setup initial network topology
2. Baseline network activity measurement
3. Dynamically add nodes
4. Dynamically remove nodes
5. Final stability test

**Results:**

- Network functionality status
- Propagation time changes
- Node count changes
- Statistics comparison

#### NetworkPartitionScenario

Tests network split-brain scenarios and healing.

**Configuration:**

```python
scenario = NetworkPartitionScenario(
    simulator=simulator,
    total_nodes=20,
    partition_duration=10.0
)
```

#### StressTestScenario

Tests network performance under high transaction load.

**Configuration:**

```python
scenario = StressTestScenario(
    simulator=simulator,
    num_nodes=50,
    transactions_per_second=100,
    duration_seconds=30.0
)
```

## Statistics and Monitoring

### Network Statistics

The simulator tracks comprehensive statistics:

```python
stats = simulator.get_statistics()
```

**Available Metrics:**

- `total_blocks_created` - Number of blocks propagated
- `total_transactions` - Number of transactions propagated
- `total_messages` - Total network messages sent
- `avg_block_propagation_time` - Average time to propagate blocks
- `avg_transaction_propagation_time` - Average time to propagate transactions
- `node_join_count` - Total nodes that joined
- `node_leave_count` - Total nodes that left

### Node Statistics

Get statistics for individual nodes:

```python
node = simulator.nodes["node_id"]
stats = node.get_stats()
```

**Available Metrics:**

- `blockchain_height` - Current blockchain height
- `mempool_size` - Number of pending transactions
- `blocks_received` - Blocks received
- `transactions_received` - Transactions received
- `blocks_sent` - Blocks sent
- `transactions_sent` - Transactions sent
- `peers_count` - Number of connected peers
- `uptime_seconds` - Node uptime

### Network Visualization

Print current network status:

```python
simulator.print_network_status()
```

Output includes:

- Total nodes and connections
- Breakdown by node type
- Propagation statistics
- Node churn statistics

## Testing

### Running Unit Tests

```bash
cd tests/simulator
python -m pytest test_simulator.py -v
```

Or using unittest:

```bash
python test_simulator.py
```

### Test Coverage

The test suite covers:

- Network simulator initialization
- Node addition and removal
- Node connections and disconnections
- Network topology management
- Statistics tracking
- Auto-connection logic
- Scenario initialization and setup

## Use Cases

### 1. Testing Dynamic Nodes Feature

**Goal:** Verify that nodes can join and leave the network without disrupting operations.

**Approach:**

- Use `DynamicNodeScenario`
- Monitor propagation times during churn
- Verify network remains functional
- Check for message delivery failures

**Example:**

```bash
python examples/dynamic_nodes_simulation.py
```

### 2. Testing Network Partitions

**Goal:** Verify network can handle and recover from partitions.

**Approach:**

- Create network partition
- Simulate activity in both partitions
- Heal partition
- Measure convergence time

### 3. Testing Scalability

**Goal:** Determine maximum network capacity.

**Approach:**

- Use `StressTestScenario`
- Gradually increase transaction rate
- Monitor propagation times
- Identify bottlenecks

### 4. Testing New Features

**Goal:** Validate new blockchain features in controlled environment.

**Approach:**

- Create custom scenario
- Implement feature-specific behavior
- Measure impact on network
- Compare with baseline

## Advanced Topics

### Custom Scenarios

Create your own scenarios by extending `BaseScenario`:

```python
from tests.simulator.scenarios import BaseScenario

class CustomScenario(BaseScenario):
    async def setup(self):
        # Setup your test
        pass

    async def run(self):
        # Run your test
        pass

    async def teardown(self):
        # Cleanup
        pass
```

### Custom Node Behavior

Extend `SimulatedNode` for custom behavior:

```python
from tests.simulator.simnode import SimulatedNode

class CustomNode(SimulatedNode):
    async def receive_block(self, block):
        # Custom block processing
        await super().receive_block(block)
```

### Network Conditions

Simulate various network conditions:

```python
# High latency
simulator = NetworkSimulator(latency_ms=500)

# Packet loss
simulator = NetworkSimulator(packet_loss_rate=0.1)  # 10% loss

# Limited connections
simulator = NetworkSimulator(max_connections_per_node=10)
```

### Topology Patterns

Create specific network topologies:

```python
# Star topology
center = await simulator.add_node("center", "seed")
for i in range(10):
    node = await simulator.add_node(f"node_{i}", "service_provider")
    simulator.connect_nodes("center", f"node_{i}")

# Ring topology
nodes = []
for i in range(10):
    nodes.append(await simulator.add_node(f"node_{i}", "seed"))
for i in range(len(nodes)):
    simulator.connect_nodes(f"node_{i}", f"node_{(i+1) % len(nodes)}")

# Mesh topology
for i in range(10):
    await simulator.add_node(f"node_{i}", "seed")
for i in range(10):
    for j in range(i+1, 10):
        simulator.connect_nodes(f"node_{i}", f"node_{j}")
```

## Performance Considerations

### Memory Usage

Each simulated node stores:

- Complete blockchain
- Full mempool
- Connection state

For large simulations (>100 nodes), consider:

- Reducing initial blockchain size
- Limiting mempool size
- Clearing old data periodically

### Simulation Speed

Factors affecting speed:

- Network latency setting (higher = slower)
- Number of nodes
- Transaction rate
- Packet loss rate (requires retries)

For faster testing:

- Reduce latency_ms
- Use fewer nodes
- Decrease transaction rate
- Set packet_loss_rate to 0

### Scalability

Tested configurations:

- ✓ 10 nodes: Very fast
- ✓ 50 nodes: Fast
- ✓ 100 nodes: Moderate
- ⚠ 500+ nodes: Slower (still functional)

## Troubleshooting

### Issue: Simulator hangs

**Cause:** Async tasks not completing
**Solution:** Ensure `await simulator.shutdown()` is called

### Issue: Nodes not connecting

**Cause:** Max connections reached or incompatible types
**Solution:** Increase `max_connections_per_node` or check node types

### Issue: Import errors

**Cause:** Python path not set correctly
**Solution:** Add to path or run from correct directory

### Issue: Transaction/block creation fails

**Cause:** Missing YadaCoin dependencies
**Solution:** Ensure full environment is set up

## Future Enhancements

Planned features:

- [ ] Malicious node simulation
- [ ] Byzantine failure scenarios
- [ ] Network topology visualization
- [ ] Real-time monitoring dashboard
- [ ] Export results to CSV/JSON
- [ ] Replay historical network states
- [ ] Integration with actual node software

## Contributing

To add new scenarios or features:

1. Create new scenario class in `scenarios.py`
2. Add tests in `test_simulator.py`
3. Add example in `examples/`
4. Update this README

## License

This simulator follows the same license as YadaCoin (YOSL v1.1).

## Support

For questions or issues:

- Open an issue on GitHub
- Contact: info@yadacoin.io

---

**Last Updated:** February 2026
**Version:** 1.0.0
