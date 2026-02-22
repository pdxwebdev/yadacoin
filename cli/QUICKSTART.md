# YadaCoin CLI - Quick Reference

## One-Liner Examples

### Update username (interactive)

```bash
python3 cli/cli.py config set-username -u "my-node"
```

Prompts: "Have you backed up config/config.json? Type 'yes' to continue:"

### Update username (non-interactive)

```bash
python3 cli/cli.py config set-username -u "my-node" --confirm-backup
```

Use this in scripts/automation. No prompts.

### Update username with custom config path

```bash
python3 cli/cli.py config set-username -u "my-node" -c /etc/yadacoin/config.json --confirm-backup
```

### Show all available commands

```bash
python3 cli/cli.py --help
```

### Show config command options

```bash
python3 cli/cli.py config --help
```

### Show set-username command help

```bash
python3 cli/cli.py config set-username --help
```

## What It Does

When you update the username:

1. ✓ Backup confirmation (with data-loss warning)
2. ✓ Load config.json
3. ✓ Update "username" field
4. ✓ Recalculate "username_signature" using your private key
5. ✓ Atomically write config back to disk

## Common Workflows

### Scenario: You want to rename your node

```bash
# 1. Backup your config first!
cp config/config.json config/config.json.backup

# 2. Update username
python3 cli/cli.py config set-username -u "new-node-name"

# 3. Type 'yes' when prompted

# 4. Verify the change
python3 -c "
import json
config = json.load(open('config/config.json'))
print('Username:', config['username'])
print('Signature set:', bool(config.get('username_signature')))
"
```

### Scenario: Deploy with Ansible/Terraform

```bash
python3 cli/cli.py config set-username \
    -u "$NODE_NAME" \
    -c /etc/yadacoin/config.json \
    --confirm-backup
```

### Scenario: Recover from failed update

```bash
# Restore backup
cp config/config.json.backup config/config.json

# Try again
python3 cli/cli.py config set-username -u "node-name" --confirm-backup
```

## Exit Codes

| Code | Meaning                                    |
| ---- | ------------------------------------------ |
| 0    | Success                                    |
| 1    | Error or user declined backup confirmation |
| 2    | No command provided                        |

Use in scripts:

```bash
python3 cli/cli.py config set-username -u "my-node" --confirm-backup
if [ $? -eq 0 ]; then
    echo "✓ Config updated successfully"
else
    echo "✗ Config update failed"
    exit 1
fi
```

## Troubleshooting

### Error: ModuleNotFoundError: No module named 'coincurve'

**Solution:** Activate the virtual environment first

```bash
source venv37/bin/activate
python3 cli/cli.py config set-username -u "my-node" --confirm-backup
```

### Error: "config.json must contain a JSON object"

**Solution:** Verify config/config.json is valid JSON

```bash
python3 -m json.tool config/config.json
```

### Error: "config.json is missing 'private_key'"

**Solution:** Your config.json is missing the required 'private_key' field

### "Aborted: backup confirmation was not provided"

This is not an error—it means the CLI is working as designed. Either:

- Type 'yes' at the confirmation prompt, or
- Use `--confirm-backup` flag to skip the prompt

## Safety

The CLI protects your data by:

- **Requiring backup confirmation**: Must say "yes" before any changes
- **Showing clear warnings**: "WARNING: Updating your config.json can invalidate existing data or keys"
- **Atomic writes**: Uses a safe temp-file pattern to avoid corruption
- **Preserving permissions**: Keeps the original file's chmod settings

**Always backup your config.json before making changes!**

```bash
cp config/config.json config/config.json.backup
```

## More Help

- Full documentation: See [README.md](./README.md)
- For developers: See [DEVELOPMENT.md](./DEVELOPMENT.md)
- Config.json schema: See [../docs/config_json.md](../docs/config_json.md)
