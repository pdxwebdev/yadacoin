# Network Simulator - Quick Start Guide

## Installation

No installation needed! The simulator is part of the YadaCoin test suite.

## Quick Start (5 minutes)

### 1. Run the Interactive Simulator

```bash
cd /Users/matt.vogel/yadacoin/tests/simulator
python run_simulator.py
```

This launches an interactive menu where you can choose different simulations.

### 2. Run a Quick Dynamic Nodes Test

```bash
python run_simulator.py dynamic-quick
```

This runs a fast test of nodes joining and leaving the network in ~10 seconds.

### 3. Run Full Dynamic Nodes Test

```bash
python run_simulator.py dynamic
```

This runs a comprehensive test with realistic network conditions (~60 seconds).

## Command Line Options

```bash
# Interactive menu
python run_simulator.py

# Specific tests
python run_simulator.py dynamic          # Full dynamic nodes test
python run_simulator.py dynamic-quick    # Quick dynamic nodes test
python run_simulator.py partition        # Network partition test
python run_simulator.py stress           # Stress test
python run_simulator.py custom           # Custom simulation
python run_simulator.py all              # Run all tests
```

## Example Scripts

### Basic Simulation

```bash
cd examples
python basic_simulation.py
```

### Dynamic Nodes Testing

```bash
python dynamic_nodes_simulation.py
python dynamic_nodes_simulation.py --quick
```

### Advanced Scenarios

```bash
python advanced_scenarios.py partition   # Test network partition
python advanced_scenarios.py stress      # Test high load
python advanced_scenarios.py combined    # Run all tests
```

## Testing Your Changes

Before pushing dynamic nodes changes to production:

1. **Quick validation** (30 seconds):

   ```bash
   python run_simulator.py dynamic-quick
   ```

2. **Full validation** (2 minutes):

   ```bash
   python run_simulator.py all
   ```

3. **Custom testing** (as needed):
   ```bash
   python run_simulator.py
   # Choose option 5 for custom interactive testing
   ```

## Understanding the Output

### Network Status Display

```
============================================================
NETWORK STATUS
============================================================
Total Nodes: 23
Total Connections: 45

Nodes by Type:
  seed: 3
  seed_gateway: 5
  service_provider: 15

Statistics:
  Blocks Propagated: 5
  Transactions Propagated: 42
  Total Messages: 387
  Avg Block Propagation Time: 0.156s
  Avg Txn Propagation Time: 0.089s
  Nodes Joined: 23
  Nodes Left: 0
============================================================
```

### Key Metrics

- **Total Nodes**: Current number of active nodes
- **Total Connections**: Total peer connections (counted twice for bidirectional)
- **Avg Propagation Time**: How long it takes for data to reach all nodes
- **Nodes Joined/Left**: Track of network churn

### Success Indicators

✓ **Network Functional**: Network can propagate messages
✓ **Propagation Times Reasonable**: Times stayed below threshold during churn
✓ **Network Size Maintained**: Most nodes remained connected

## Common Use Cases

### 1. Testing Dynamic Nodes Feature

**What to test**: Nodes can join and leave without breaking the network

**How to test**:

```bash
python run_simulator.py dynamic
```

**What to look for**:

- ✓ "Network Functional: True"
- ✓ Propagation times stay reasonable (< 2x baseline)
- ✓ No errors or exceptions

### 2. Testing Network Resilience

**What to test**: Network survives partitions and high load

**How to test**:

```bash
python run_simulator.py all
```

**What to look for**:

- ✓ All tests pass
- ✓ Network heals after partition
- ✓ Can handle target load

### 3. Debugging Network Issues

**What to test**: Specific scenarios relevant to your bug

**How to test**:

```bash
python run_simulator.py custom
```

Then modify the custom simulation in `run_simulator.py` to reproduce your scenario.

## Customization

### Create Your Own Scenario

Edit `tests/simulator/scenarios.py`:

```python
class MyCustomScenario(BaseScenario):
    async def setup(self):
        # Create your network topology
        pass

    async def run(self):
        # Run your test
        pass
```

### Modify Network Conditions

Edit parameters in `run_simulator.py`:

```python
simulator = NetworkSimulator(
    latency_ms=100,        # Increase for slower network
    packet_loss_rate=0.05, # Increase for lossy network
    max_connections_per_node=50  # Limit connections
)
```

### Add More Nodes

In any example script:

```python
# Add 100 service providers
for i in range(100):
    node = await simulator.add_node(f"provider_{i}", "service_provider")
    await simulator.auto_connect_new_node(node.node_id, 3)
```

## Running Unit Tests

```bash
cd /Users/matt.vogel/yadacoin/tests/simulator
python -m pytest test_simulator.py -v
```

Or:

```bash
python test_simulator.py
```

## Troubleshooting

### "Import Error"

**Solution**: Make sure you're in the correct directory or Python path is set

### "Simulator hangs"

**Solution**: Press Ctrl+C and ensure you call `await simulator.shutdown()`

### "Tests fail with transaction errors"

**Solution**: This is expected if running outside full YadaCoin environment. The simulator will skip transaction creation and still test network topology.

## Next Steps

1. ✓ Run quick test: `python run_simulator.py dynamic-quick`
2. ✓ Read the full README: `tests/simulator/README.md`
3. ✓ Explore examples: `tests/simulator/examples/`
4. ✓ Run full test suite before pushing to production: `python run_simulator.py all`

## Need Help?

- Check the full documentation: `README.md`
- Look at example scripts in `examples/`
- Contact: info@yadacoin.io

---

**Happy Testing!** 🚀
