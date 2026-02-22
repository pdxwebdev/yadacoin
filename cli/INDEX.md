# YadaCoin CLI Documentation Index

## For Users

Start here if you want to use the CLI to manage your YadaCoin node.

- **[QUICKSTART.md](./QUICKSTART.md)** - Quick reference and common workflows
- **[README.md](./README.md)** - Complete user documentation with all options

## For Developers

Start here if you want to extend the CLI or add new commands.

- **[DEVELOPMENT.md](./DEVELOPMENT.md)** - Step-by-step guide to adding new commands
- **[README.md](./README.md)** - See "Architecture" and "Adding New Commands" sections

## CLI Structure

```
cli/
├── INDEX.md                  # This file
├── QUICKSTART.md            # User quick reference
├── README.md                # Full user documentation
├── DEVELOPMENT.md           # Developer guide
├── cli.py                   # Main entry point
├── __init__.py              # Package marker
└── commands/
    ├── __init__.py
    └── config/
        ├── __init__.py
        ├── config_base.py   # Base class for config updaters
        └── update_username.py  # Username updater implementation
```

## Available Commands

### config

**Subcommands:** `set-username`

Configuration file management commands.

#### config set-username

Update the node's username and recalculate its signature.

```bash
# Interactive mode
python3 cli/cli.py config set-username -u "my-node"

# Non-interactive mode
python3 cli/cli.py config set-username -u "my-node" --confirm-backup

# Custom config path
python3 cli/cli.py config set-username -u "my-node" \
    -c /etc/yadacoin/config.json --confirm-backup
```

**Options:**

- `-u, --username` (required): New username
- `-c, --config` (optional): Path to config.json (default: `config/config.json`)
- `--confirm-backup` (optional): Skip interactive confirmation

## Getting Started

1. **To use the CLI:**

   ```bash
   python3 cli/cli.py config set-username -u "my-node"
   ```

   Read [QUICKSTART.md](./QUICKSTART.md) for more examples.

2. **To add a new command:**
   Follow the steps in [DEVELOPMENT.md](./DEVELOPMENT.md).

3. **To understand the architecture:**
   See "Architecture" section in [README.md](./README.md).

## Key Concepts

### ConfigUpdaterBase

Base class that all config updaters inherit from. Provides:

- `load_config(path)` - Load JSON config
- `confirm_backup(path, flag)` - Prompt for backup confirmation
- `write_config(path, config)` - Atomically write config

### Subclasses

Implemented for specific config fields:

- `UsernameConfigUpdater` - Updates username field with signature recalculation

### Handlers

Functions that coordinate the update flow:

- `_handle_set_username(args)` - Orchestrates username update

### Command Registration

In `build_parser()`:

- Create `argparse` subparser
- Set default handler via `set_defaults(handler=...)`
- CLI routes to handler based on command

## Design Philosophy

The CLI is built on these principles:

1. **Safety First**: Backup confirmation, atomic writes, clear warnings
2. **Extensibility**: Easy to add new commands via base classes
3. **Clarity**: Well-documented code with comprehensive docstrings
4. **Consistency**: All config updaters follow the same pattern
5. **Usability**: Works both interactively and in automation scripts

## Common Tasks

### Update node username

See [QUICKSTART.md](./QUICKSTART.md) - "Update username"

### Add a new config field updater

See [DEVELOPMENT.md](./DEVELOPMENT.md) - "Step-by-Step: Adding a New Config Updater"

### Add a new command namespace

See [DEVELOPMENT.md](./DEVELOPMENT.md) - "Adding a New Command Namespace"

### Run tests

```bash
source venv37/bin/activate
python3 -m pytest tests/ -v
```

### Check CLI help

```bash
python3 cli/cli.py --help
python3 cli/cli.py config --help
python3 cli/cli.py config set-username --help
```

## Troubleshooting

| Issue                          | Solution                                              |
| ------------------------------ | ----------------------------------------------------- |
| ModuleNotFoundError            | Activate venv: `source venv37/bin/activate`           |
| Invalid JSON config            | Check with: `python3 -m json.tool config/config.json` |
| "Aborted: backup confirmation" | Type 'yes' at prompt, or use `--confirm-backup`       |
| Permission denied              | Check file permissions: `ls -l config/config.json`    |

See [README.md](./README.md) for more troubleshooting.

## See Also

- [YadaCoin Main Docs](../docs/index.md)
- [Config.json Schema](../docs/config_json.md)
- [API Documentation](../docs/API/)

---

**Last Updated:** February 2026

For issues or questions, see the [README.md](./README.md) or [DEVELOPMENT.md](./DEVELOPMENT.md).
