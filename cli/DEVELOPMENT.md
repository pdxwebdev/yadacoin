# CLI Development Guide

This document explains how to extend the YadaCoin CLI by adding new commands and subcommands.

## Architecture Overview

The CLI uses a hierarchical command structure:

```
cli.py (main router)
  ├── config (command namespace)
  │   ├── set-username (subcommand)
  │   ├── set-peer-host (subcommand)
  │   └── ...
  ├── status (command namespace)
  │   ├── show (subcommand)
  │   └── ...
  └── ...
```

Each subcommand is implemented as:

1. An **updater class** (extends `ConfigUpdaterBase` or custom logic)
2. A **handler function** (orchestrates the update flow)
3. An **argument parser** (registered in `build_parser()`)

## Step-by-Step: Adding a New Config Updater

### Example: Add `config set-peer-host`

#### Step 1: Create the Updater Class

File: `cli/commands/config/update_peer_host.py`

```python
"""Handler for updating peer_host in config.json."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)) + "/../../..")

from cli.commands.config.config_base import ConfigUpdaterBase

class PeerHostConfigUpdater(ConfigUpdaterBase):
    """Updater for the peer_host field in config.json.

    Validates that the peer host is a valid IPv4 address and not localhost.
    """

    def update_peer_host(self, config, peer_host):
        """Update peer_host field.

        Args:
            config (dict): The config dictionary to update in-place.
            peer_host (str): New peer host value (IPv4 address).

        Raises:
            ValueError: If peer_host is invalid.
        """
        if not peer_host:
            raise ValueError("peer_host cannot be empty")
        if peer_host in ["0.0.0.0", "localhost", "127.0.0.1"]:
            raise ValueError("peer_host cannot be localhost or 0.0.0.0")
        # TODO: Add IPv4 validation

        config["peer_host"] = peer_host
```

#### Step 2: Add Handler Function

File: `cli/cli.py` (add to module)

```python
def _handle_set_peer_host(args):
    """Handle the 'config set-peer-host' command."""
    from cli.commands.config.update_peer_host import PeerHostConfigUpdater

    updater = PeerHostConfigUpdater()
    if not updater.confirm_backup(args.config, args.confirm_backup):
        return 1

    config = updater.load_config(args.config)
    updater.update_peer_host(config, args.peer_host)
    updater.write_config(args.config, config)
    print("Updated peer_host in {}".format(args.config))
    return 0
```

#### Step 3: Register Parser

File: `cli/cli.py`, in `build_parser()` function:

```python
def build_parser():
    # ... existing code ...

    # Add this after set_username_parser registration:
    set_peer_host_parser = config_subparsers.add_parser(
        "set-peer-host",
        help="Update peer host in config.json",
    )
    set_peer_host_parser.add_argument(
        "-c",
        "--config",
        default="config/config.json",
        help="Path to config.json",
    )
    set_peer_host_parser.add_argument(
        "-p",
        "--peer-host",
        required=True,
        help="New peer host (IPv4 address)",
    )
    set_peer_host_parser.add_argument(
        "--confirm-backup",
        action="store_true",
        help="Confirm you have backed up your config.json",
    )
    set_peer_host_parser.set_defaults(handler=_handle_set_peer_host)

    return parser
```

#### Step 4: Test

```bash
# Interactive mode
python3 cli/cli.py config set-peer-host -p "192.168.1.100"

# Non-interactive mode
python3 cli/cli.py config set-peer-host -p "192.168.1.100" --confirm-backup

# Show help
python3 cli/cli.py config set-peer-host --help
```

## Adding a New Command Namespace

To add a completely new namespace (e.g., `peers`):

1. Create `cli/commands/peers/` directory
2. Create `cli/commands/peers/__init__.py` with docstring
3. Create command modules inside (e.g., `list_peers.py`)
4. In `cli/cli.py`, add to `build_parser()`:

```python
peers_parser = subparsers.add_parser("peers", help="Peer management")
peers_subparsers = peers_parser.add_subparsers(dest="peers_command")

list_peers_parser = peers_subparsers.add_parser("list")
# ... register arguments and handler ...
list_peers_parser.set_defaults(handler=_handle_list_peers)
```

## Design Patterns

### ConfigUpdaterBase Pattern

For operations that modify `config.json`:

```python
class MyConfigUpdater(ConfigUpdaterBase):
    def update_field(self, config, value):
        # Validate value
        # Update config dict
        # Do NOT write; handler does that
        config["field"] = value
```

Advantages:

- Centralized backup confirmation
- Atomic file writes
- Consistent error handling
- Easy to test

### Custom Handler Pattern

For complex operations:

```python
def _handle_complex_operation(args):
    # Acquire resources
    try:
        # Perform operation
        result = do_something(args.input)
        print("Success: {}".format(result))
        return 0
    except CustomError as e:
        print("Error: {}".format(e))
        return 1
    finally:
        # Clean up resources
        pass
```

## Testing

### Unit Testing Config Updaters

```python
# test_update_peer_host.py
import json
import tempfile
import os
from cli.commands.config.update_peer_host import PeerHostConfigUpdater

def test_update_peer_host():
    updater = PeerHostConfigUpdater()

    # Create temp config
    config = {"peer_host": "192.168.1.1", "username": "node1"}

    # Update
    updater.update_peer_host(config, "10.0.0.1")

    # Verify
    assert config["peer_host"] == "10.0.0.1"

def test_invalid_peer_host():
    updater = PeerHostConfigUpdater()
    config = {"peer_host": "192.168.1.1"}

    with pytest.raises(ValueError):
        updater.update_peer_host(config, "localhost")
```

### Integration Testing

```bash
# Create test config
cp config/config.json config/config.test.json

# Run CLI
python3 cli/cli.py config set-peer-host -c config/config.test.json \
    -p "10.0.0.1" --confirm-backup

# Verify
python3 -c "
import json
with open('config/config.test.json') as f:
    config = json.load(f)
    assert config['peer_host'] == '10.0.0.1'
    print('✓ Test passed')
"

# Clean up
rm config/config.test.json
```

## Error Handling

Always validate inputs and provide clear error messages:

```python
def update_field(self, config, value):
    """Update field with validation."""
    # Check type
    if not isinstance(value, str):
        raise ValueError("field must be a string, got {}".format(type(value).__name__))

    # Check emptiness
    if not value.strip():
        raise ValueError("field cannot be empty")

    # Check constraints
    if len(value) > 255:
        raise ValueError("field must be <= 255 characters")

    # Perform update
    config["field"] = value
```

## Documentation

### Docstring Standards

Follow Google-style docstrings:

```python
def method(self, arg1, arg2):
    """One-line summary.

    Longer description if needed, explaining what this does and why.

    Args:
        arg1 (type): Description.
        arg2 (type): Description.

    Returns:
        type: Description.

    Raises:
        ExceptionType: Description of when raised.
    """
    pass
```

### Command Help Text

Make help text clear and concise:

```python
parser = subparsers.add_parser(
    "set-username",
    help="Update node username (requires backup confirmation)",
    description="""Update the username in config.json.

    When changed, the username_signature is automatically recalculated
    using your node's private key. This signature is required for
    peer authentication on the YadaCoin network."""
)
```

## Common Mistakes

### ❌ Not Extending ConfigUpdaterBase

```python
# DON'T do this
class BadUpdater:
    def update_field(self, config, value):
        config["field"] = value
```

Use `ConfigUpdaterBase` to get backup confirmation, atomic writes, etc.

### ❌ Writing Config in Update Method

```python
# DON'T do this
def update_username(self, config, username):
    config["username"] = username
    self.write_config("config.json", config)  # Handler does this!
```

Let the handler call `write_config()`.

### ❌ Forgetting Docstrings

```python
# DON'T do this
def update_field(self, config, value):
    config["field"] = value
```

Always document your code with docstrings.

### ❌ No Input Validation

```python
# DON'T do this
def update_port(self, config, port):
    config["port"] = port  # Could be string, negative, > 65535!
```

Validate all inputs and raise `ValueError` with clear messages.

## Best Practices

✅ **Do:**

- Use `ConfigUpdaterBase` for config updates
- Validate all inputs thoroughly
- Write atomic transactions for critical operations
- Document functions with docstrings
- Test both happy path and error cases
- Use clear, descriptive error messages
- Follow existing code style

✅ **Prefer:**

- Immutable operations over mutations when possible
- Composition over inheritance for complex logic
- Explicit argument validation over implicit type coercion
- Context managers for resource management

## See Also

- [CLI README](./README.md) - User documentation
- [YadaCoin Architecture](../docs/index.md)
- [Python Best Practices](https://www.python.org/dev/peps/pep-0008/)
