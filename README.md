# yadacoin

[![Build and Release](https://github.com/pdxwebdev/yadacoin/actions/workflows/main.yml/badge.svg)](https://github.com/pdxwebdev/yadacoin/actions/workflows/main.yml)

## Setup

### Ubuntu 22/24 install command:

`curl -fsSL https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/yadanodesetup.sh | sudo bash`

### Windows installer:

https://yadacoin.io/download

## Command-Line Interface

YadaCoin includes a CLI for node management and configuration. For complete documentation on available commands, usage examples, and development guide, see:

- **[CLI Documentation](./cli/INDEX.md)** - Start here for overview and navigation
- **[Quick Start Guide](./cli/QUICKSTART.md)** - One-liner examples and common workflows
- **[Development Guide](./cli/DEVELOPMENT.md)** - For developers adding new commands

## Developer Resources

### Network Simulator

For testing network behavior and dynamic nodes, use the built-in network simulator:

- **[Network Simulator Documentation](./tests/simulator/README.md)** - Complete simulation framework
- **[Quick Start Guide](./tests/simulator/QUICKSTART.md)** - Run simulations in 5 minutes
- **[Example Scripts](./tests/simulator/examples/)** - Pre-built test scenarios

The simulator is essential for testing dynamic nodes, network partitions, and high-load scenarios before deploying to production.

## Configuration

- modes
  - type: array
  - default: ["node", "web", "pool"]
  - description: This setting defines all the modules to initialize when running the node. Node - will initialize all of the networking for exchanging blocks, syncing, transactions, etc. Web - will enable the http interface which can be used in your browser including the pool information and wallet app pages.
- root_app
  - type: string
  - default: "yadacoinpool"
  - description: If multiple http apps are loaded, this setting tells the node which app owns the root / path in the case of a conflict.
- seed
  - type: string
  - default: auto-generated
  - description: This is an auto-generated set of words representing your private key.
- xprv
  - type: string
  - default: auto-generated
  - description: Extended private key. This allows a heirarchy of keys to be created. Useful for exchanges with many child wallets.
- public_key
  - type: string
  - default: auto-generated
  - description: Public key for the corresponding private key.
- address
  - type: string
  - default: auto-generated
  - description: Bitcoin-style address for the corresponding public key
- private_key
  - type: string
  - default: auto-generated
  - description: Private key for the corresponding public key.
- wif
  - type: string
  - default: auto-generated
  - description: Bitcoin-style Wallet Import Format string for the corresponding private key.
- username_signature
  - type: string
  - default: auto-generated
  - description: The signature generated when this wallet signs the username field.
- mongodb_host
  - type: string
  - default: localhost
  - description: The server where the mongo db is located.
- mongodb_username
  - type: string
  - default: undefined
  - description: The username to authenticate against mongodb.
- mongodb_password
  - type: string
  - default: undefined
  - description: The password to authenticate against mongodb.
- api_whitelist
  - type: array
  - default: []
  - description: An array of IP addresses that are allowed to access your node. ie. ["ip.address.goes.here"]
- username
  - type: string
  - default: ""
  - description: This is the username other users on the network will see when interacting with you on the network.
- network
  - type: string
  - default: mainnet
  - description: Tell the node which network to use. Possible values are mainnet, testnet, regnet.
- database
  - type: string
  - default: yadacoin
  - description: The name of the mongodb database where all collections/yadacoin data will be stored.
- site_database
  - type: string
  - default: yadacoin_site
  - description: The name of the mongodb database where all third-party app data will be stored.
- peer_host
  - type: string
  - default: auto-generated
  - description: The IP address used by the network to access your node.
- peer_port
  - type: string
  - default: 8000
  - description: The port used by the network to access your node
- peer_type
  - type: string
  - default: user
  - description: The node type that determines when this node will place itself in the network topology. Possible values are user, service_provider, seed_gateway, and seed. If you would like to be a seed node, then you'll need to also run service_provider and seed_gateway nodes for your seed node. You'll also need to submit a pull request, requesting your servers be added to the network.
- serve_host
  - type: string
  - default: 0.0.0.0
  - description: The IP address bound by the node when initializing the server.
- serve_port
  - type: string
  - default: 8000
  - description: The port bound by the node when initializing the server.
- ssl
  - type: object
  - default: undefined
  - description: Specify the SSL information to enable https on your web server.
  - nested properties:
    - cafile
      - type: string
      - default: undefined
      - description: The absolute file path to your CA file.
    - certfile
      - type: string
      - default: undefined
      - description: The absolute file path to your Cetfificate file.
    - keyfile
      - type: string
      - default: undefined
      - description: The absolute file path to your Key file.
    - common_name
      - type: string
      - default: undefined
      - description: The common name used in your certificate.
    - port
      - type: integer
      - default: undefined
      - description: The port you wish to use for your SSL connections.
- origin
  - type: string
  - default: ""
  - description: Depricated
- fcm_key
  - type: string
  - default: undefined
  - description: Depricated
- sia_api_key
  - type: string
  - default: undefined
  - description: Depricated
- jwt_public_key
  - type: string
  - default: auto-generated
  - description: This value is generated to perform JWT auth for yadacoin apps.
- callbackurl
  - type: string
  - default: undefined
  - description: Depricated
- wallet_host_port
  - type: string
  - default: "http://localhost:8001"
  - description: The url used to contact the node from the wallet user interface. You may want to change this is you would like to access your wallet remotely.
- credits_per_share
  - type: decimal
  - default: 5
  - description: Specifies the number of credits a user earch for every share they submit to your pool.
- shares_required
  - type: bool
  - default: false
  - description: Specifies if shares are required to use an app on your node.
- pool_payout
  - type: bool
  - default: false
  - description: Specifies if your pool will payout to the addresses submitting shares. If false, the pool will keep all won coins in it's own wallet.
- pool_take
  - type: decimal
  - default: .01
  - description: Specifies the percentage of coins that are awarded to the pool for each block.
- pool_public_key
  - type: string
  - default: undefined
  - description: This allows you to specify a pool public key other than the current node in the case where you want to provide stats on the web and run the pool on a separate server.
- stratum_pool_port
  - type: integer
  - default: 3333
  - description: The port where your pool can be accessed by mining rigs.
- payout_frequency
  - type: integer
  - default: 6
  - description: This specifies the number of blocks that must by won by the pool before a payout can take place.
- max_miners
  - type: integer
  - default: 100
  - description: This specifies the number of miners for your pool.
- max_peers
  - type: integer
  - default: 20
  - description: This specifies the number of peers that can connect to your node.
- pool_diff
  - type: integer
  - default: 100000
  - description: This specifies the difficulty for pool shares in both xmrig versions 2/3
- email
  - type: object
  - default: undefined
  - description: Specify the email server you wish to use for notifications, communication, etc.
    - smtp_server
      - type: string
      - default: undefined
      - description: The hostname or IP address of your smtp server.
    - smtp_port
      - type: number
      - default: undefined
      - description: The port of your smtp server.
    - username
      - type: string
      - default: undefined
      - description: The username of your email account.
    - password
      - type: string
      - default: undefined
      - description: The password of your email account.
- skynet_url
  - type: string
  - default: ''
  - description: Specify the url of your skynet server.
- skynet_api_key
  - type: string
  - default: ''
  - description: Specify the api password for your skynet server.
- web_jwt_expiry
  - type: string
  - default: 23040
  - description: Specify the validity period for a json web token in seconds.
- websocket_host_port
  - type: string
  - default: 'ws://localhost:8000/websocket'
  - description: Specify the host and port of your websocket.
- tcp_traffic_debug
  - type: bool
  - default: undefined
  - description: Specify if you want all tcp traffic in debug logging.
- debug_memory
  - type: bool
  - default: undefined
  - description: Specify if you want a complete breakdown of memory usage by object type in status output.
- websocket_traffic_debug
  - type: bool
  - default: undefined
  - description: Specify if you want all websocket traffic in debug logging.
- mongo_debug
  - type: bool
  - default: undefined
  - description: Specify if you want all Mongo DB queries to be logged and profiled.
- peers_wait
  - type: integer
  - default: 3
  - description: Specify the number of seconds to wait before attempting to reconnect to peers.
- status_wait
  - type: integer
  - default: 10
  - description: Specify the number of seconds to wait before printing status message to terminal.
- queue_processor_wait
  - type: integer
  - default: 10
  - description: Specify the number of seconds to wait before checking for new transactions to process.
- block_checker_wait
  - type: integer
  - default: 1
  - description: Specify the number of seconds to wait before checking the for block height changes and updating peers.
- message_sender_wait
  - type: integer
  - default: 10
  - description: Specify the number of seconds to wait before retrying messages for transactions, blocks, etc.
- pool_payer_wait
  - type: integer
  - default: 120
  - description: Specify the number of seconds to wait before running the pool payout process.
- cache_validator_wait
  - type: integer
  - default: 30
  - description: Specify the number of seconds to wait before running the cache validator process.
- mempool_cleaner_wait
  - type: integer
  - default: 1200
  - description: Specify the number of seconds to wait before clearing the mempool of old and invalid transactions.
- nonce_processor_wait
  - type: integer
  - default: 1
  - description: Specify the number of seconds to wait before checking for new share submissions to process.
- mongo_query_timeout
  - type: integer
  - default: 30000
  - description: Specify the max number of milliseconds of execution time for all mongo queries.
- http_request_timeout
  - type: integer
  - default: 3000
  - description: Specify the max number of milliseconds of execution time for all http requests.
- log_health_status
  - type: bool
  - default: undefined
  - description: Specify if you want all Mongo DB queries to be logged and profiled.
- docker_debug
  - type: bool
  - default: undefined
  - description: Specify if you want to log resources used by docker.
- asyncio_debug
  - type: bool
  - default: undefined
  - description: Specify if you want to log slow running asyncio tasks.
- asyncio_debug_duration
  - type: bool
  - default: undefined
  - description: Specify duration of what is considered a "slow" task in asyncio.
- combined_address
  - type: string
  - default: your node's wallet address
  - description: Specify a wallet address to combine transactions. This can be useful when running multiple nodes and consolidating their transactions into a central wallet.
- activate_peerjs
  - type: bool
  - default: undefined
  - description: If your node is not a service provide node, which have this enabled by default, you can use this setting to activate peerjs p2p connection broker endpoints and user interface.
- masternode_fee_minimum
  - type: integer
  - default: 1
  - description: If your node is a service provider or you have activate_peerjs set to true, then you may set your minimum required amount of YDA to broker p2p connections.
- balance_min_utxo
  - type: integer
  - default: 1
  - description: This value determines the minimum amount of yada for a UTXO for it to be included in the list of available UTXOs

## Development Environment

We use Black, Autoflake, isort, and commit message enforcement as pre-commit hooks. To install the hooks, run the following commands:

```
pip install pre-commit mongomock black autoflake isort pytest
pre-commit install
pre-commit install --hook-type pre-push
pre-commit install -t commit-msg
pre-commit autoupdate
```

## Testing

### Running Tests

Tests are configured to run from the project root directory using pytest. All tests require your virtual environment to be activated.

#### Run All Tests

```bash
# Activate virtual environment
source venv37/bin/activate

# Run all unit tests
pytest tests/unittests/ -v
```

#### Run Specific Test File

```bash
# Run tests from a specific file
pytest tests/unittests/core/test_block.py -v

# Example: Run transaction tests
pytest tests/unittests/core/test_transaction.py -v
```

#### Run Specific Test

```bash
# Run a single test by class and method
pytest tests/unittests/core/test_block.py::TestBlock::test_copy -v

# Example: Run wallet balance test
pytest tests/unittests/core/test_get_wallet_balance.py::TestWalletBalance::test_get_wallet_balance -v
```

#### Run Tests with Quiet Output

```bash
# Run tests with minimal output
pytest tests/unittests/ -q

# Run with no traceback for failures
pytest tests/unittests/ -q --tb=no
```

#### Using Custom Configuration Flags

For systems that require remote hash servers or other custom configurations, you can pass flags via pytest:

```bash
# Run tests with a remote hash server domain
pytest tests/unittests/ -v --hash_server_domain="http://remotelyrich.com"

# Example with other pytest options
pytest tests/unittests/core/test_block.py -v --hash_server_domain="http://your-hash-server.com"
```

### Test Organization

Tests are organized in the `tests/unittests/` directory:

- `core/` - Tests for core blockchain functionality
  - `test_block.py` - Block creation, validation, and hashing
  - `test_blockchain.py` - Blockchain operations and chain management
  - `test_blockchainutils.py` - Utility functions for blockchain operations
  - `test_transaction.py` - Transaction creation, validation, and signing
  - `test_keyeventlog.py` - Key event log validation and operations
  - `test_consensus.py` - Consensus mechanism tests
  - `test_mongo.py` - MongoDB integration tests
  - `test_nodes.py` - Node management and discovery tests
  - `test_get_unspent_outputs.py` - UTXO retrieval tests
  - `test_get_wallet_balance.py` - Wallet balance calculation tests
- `socket/` - WebSocket and networking tests
- `config/` - Test configuration files

### Test Configuration

The test configuration is specified in `pytest.ini` at the project root. Key settings:

- **Test Discovery**: Follows pytest conventions (`test_*.py` files, `Test*` classes, `test_*` methods)
- **Async Support**: Tests use `IsolatedAsyncioTestCase` for async/await testing
- **Path Setup**: `conftest.py` automatically adds the workspace root to Python path for proper imports

### Writing New Tests

New tests should inherit from `AsyncTestCase` defined in `test_setup.py`:

```python
from tests.unittests.test_setup import AsyncTestCase

class TestMyFeature(AsyncTestCase):
    async def test_my_feature(self):
        # Your test code here
        self.assertTrue(True)
```

#### Key Test Utilities

- `AsyncTestCase` - Base class for async unit tests with asyncio loop support
- `BaseTestCase` - Base class for HTTP-based tests using Tornado
- Mock fixtures in test files for blockchain data, transactions, and wallet state

### Debugging Tests

To troubleshoot test failures:

```bash
# Run with verbose output and full tracebacks
pytest tests/unittests/ -vv

# Stop on first failure
pytest tests/unittests/ -x

# Show print statements and logging
pytest tests/unittests/ -s

# Run with specific verbosity for a file
pytest tests/unittests/core/test_block.py::TestBlock::test_verify -vv
```

### Network Simulator

For testing network behavior, dynamic nodes, and distributed scenarios, YadaCoin includes a comprehensive network simulator. The simulator allows you to:

- Test dynamic node joining and leaving (node churn)
- Simulate network partitions and healing
- Measure block and transaction propagation times
- Stress test under high load
- Create custom network topologies

**Quick Start:**

```bash
cd tests/simulator
python run_simulator.py dynamic-quick  # Run a quick dynamic nodes test
```

**Documentation:**

- **[Network Simulator Documentation](./tests/simulator/README.md)** - Complete guide to using the simulator
- **[Quick Start Guide](./tests/simulator/QUICKSTART.md)** - Get started in 5 minutes
- **[Example Scripts](./tests/simulator/examples/)** - Ready-to-run simulation examples

The simulator is particularly useful for testing the dynamic nodes feature before deploying to production.
