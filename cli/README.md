# YadaCoin CLI

A generalized command-line interface for YadaCoin node management and configuration.

## Overview

The YadaCoin CLI provides a hierarchical command structure for managing node operations, with a focus on configuration management. The interface is designed to be extensible, allowing new commands and subcommands to be added easily.

## Directory Structure

```
cli/
├── __init__.py              # Package marker
├── cli.py                   # Main entry point and command router
├── README.md                # This file
└── commands/
    ├── __init__.py          # Package marker
    └── config/
        ├── __init__.py      # Package marker
        ├── config_base.py   # Base class for config updaters
        └── update_username.py  # Username update handler
```

## Getting Started

### Prerequisites

- Python 3.7+
- Virtual environment activated (if using `venv37`)
- Dependencies installed via `requirements.txt`

### Basic Usage

Run the CLI from the project root:

```bash
python3 cli/cli.py --help
```

View available commands:

```bash
python3 cli/cli.py config --help
```

## Commands

### `config` Namespace

Operations related to modifying `config.json` settings.

#### `config set-username`

Update the node's username and automatically recalculate the username signature.

**Signature:**

```
python3 cli/cli.py config set-username -u USERNAME [--config PATH] [--confirm-backup]
```

**Arguments:**

- `-u, --username USERNAME` (required): New username for the node
- `-c, --config PATH` (optional): Path to config.json (default: `config/config.json`)
- `--confirm-backup` (optional): Skip interactive backup confirmation (assumes environment has backed up)

**Examples:**

Interactive mode (prompts for backup confirmation):

```bash
python3 cli/cli.py config set-username -u "my-node"
```

Non-interactive mode (for scripts/automation):

```bash
python3 cli/cli.py config set-username -u "my-node" --confirm-backup
```

Custom config file:

```bash
python3 cli/cli.py config set-username -u "my-node" -c /etc/yadacoin/config.json --confirm-backup
```

**What It Does:**

1. Displays a data-loss warning
2. Prompts for backup confirmation (unless `--confirm-backup` is set)
3. Loads the existing `config.json`
4. Updates the `username` field
5. Recalculates `username_signature` using the node's private key
6. Atomically writes the updated config back to disk

**Important:** The `username_signature` is a deterministic signature of the username using your node's private key. This signature is used for peer authentication on the YadaCoin network. Any time the username changes, the signature must be recalculated.

## Architecture

### Command Routing

1. **Main Entry Point (`cli.py`)**: Parses arguments and routes to command handlers
2. **Command Handlers**: Functions like `_handle_set_username()` that orchestrate the update flow
3. **Config Updaters**: Classes that extend `ConfigUpdaterBase` to implement specific update logic

### Base Classes

#### `ConfigUpdaterBase`

Provides common functionality for all config file updaters:

- **load_config(path)**: Parse JSON config file
- **confirm_backup(path, confirmed_flag)**: Prompt for backup confirmation with warnings
- **write_config(path, config)**: Atomically write config using temp file + rename pattern

Subclasses implement a specific update method (e.g., `update_username()`).

#### `UsernameConfigUpdater`

Extends `ConfigUpdaterBase` to handle username updates with automatic signature recalculation.

## Safety Features

### Data Protection

- **Mandatory Backup Confirmation**: Before any modification, users must either:
  - Provide `--confirm-backup` flag, or
  - Type "yes" at the interactive prompt
- **Clear Warnings**: Displays warning about potential data loss before requesting confirmation
- **Atomic Writes**: Uses temporary file + atomic rename to prevent corruption if write fails midway

### Error Handling

- **Validation**: Checks that username is not empty and private key exists
- **File Safety**: Preserves original file permissions (mode) after write
- **Exception Safety**: Catches errors and returns non-zero exit codes

## Exit Codes

- `0`: Success
- `1`: Command error or user declined backup confirmation
- `2`: No command provided (shows help)

## Adding New Commands

To add a new config updater:

1. Create a new file in `cli/commands/config/` (e.g., `update_peer_host.py`)
2. Subclass `ConfigUpdaterBase` and implement the update logic:

```python
from cli.commands.config.config_base import ConfigUpdaterBase

class PeerHostConfigUpdater(ConfigUpdaterBase):
    def update_peer_host(self, config, peer_host):
        # Validate
        if not peer_host:
            raise ValueError("peer_host cannot be empty")
        # Update
        config["peer_host"] = peer_host
```

3. Create a handler in `cli/cli.py`:

```python
def _handle_set_peer_host(args):
    updater = PeerHostConfigUpdater()
    if not updater.confirm_backup(args.config, args.confirm_backup):
        return 1
    config = updater.load_config(args.config)
    updater.update_peer_host(config, args.peer_host)
    updater.write_config(args.config, config)
    print("Updated peer_host in {}".format(args.config))
    return 0
```

4. Register the command in `build_parser()`:

```python
set_peer_host_parser = config_subparsers.add_parser(
    "set-peer-host",
    help="Update peer host in config.json",
)
set_peer_host_parser.add_argument("-p", "--peer-host", required=True)
set_peer_host_parser.set_defaults(handler=_handle_set_peer_host)
```

## Technical Details

### Deterministic Signatures

The `username_signature` is computed using:

```python
TU.generate_deterministic_signature(config, username, private_key=private_key)
```

This creates a cryptographic signature of the username byte string using SECP256k1 curve with the node's private key. The signature is base64-encoded and stored in the config.

### Atomic File Writes

To prevent corruption, config writes follow this pattern:

1. Write to temporary file (e.g., `config.json.tmp`)
2. Call `os.replace()` to atomically move temp to target
3. Restore original file permissions

This ensures the original file is never partially written.

## Troubleshooting

### ModuleNotFoundError

**Error:** `ModuleNotFoundError: No module named 'coincurve'`

**Solution:** Activate the virtual environment first:

```bash
source venv37/bin/activate
python3 cli/cli.py config set-username -u "mynode"
```

### RuntimeError: Module has already been initialized

**Error:** Python dependency module already loaded

**Solution:** Run the CLI in a fresh process; this typically occurs when running multiple tests in sequence in the same Python session.

### Invalid JSON in config file

**Error:** `JSONDecodeError` or similar

**Solution:** Ensure `config/config.json` is valid JSON. You can check with:

```bash
python3 -m json.tool config/config.json
```

## Development

### Running Tests

Tests for the update_username feature are in `tests/`. Run with:

```bash
python3 -m pytest tests/ -v
```

### Code Style

The codebase follows PEP 8. Docstrings use Google style.

## See Also

- [config.json Schema](../docs/config_json.md)
- [YadaCoin Architecture](../docs/index.md)
