# YadaCoin CLI - Examples

Real-world examples for common use cases.

## Local Development Setup

### Example 1: Initial Node Setup

You've just installed YadaCoin and want to configure your node with a custom name.

```bash
cd /path/to/yadacoin

# 1. Backup the initial config
cp config/config.json config/config.json.backup

# 2. Update the username to something meaningful
python3 cli/cli.py config set-username -u "development-node"

# 3. Verify the change
python3 -c "
import json
config = json.load(open('config/config.json'))
print('✓ Username is now:', config['username'])
print('✓ Signature length:', len(config['username_signature']))
"
```

Output:

```
WARNING: Updating your config.json can invalidate existing data or keys.
There is a possibility that all data could be lost.
Have you backed up config/config.json? Type 'yes' to continue: yes
Updated username and username_signature in config/config.json
✓ Username is now: development-node
✓ Signature length: 88
```

## Production Deployment

### Example 2: Deploy via Shell Script

Automate node deployment with a setup script:

```bash
#!/bin/bash
set -e

NODE_NAME="${1:-yadacoin-node-$(date +%s)}"
CONFIG_PATH="/etc/yadacoin/config.json"

echo "Deploying YadaCoin node: $NODE_NAME"

# Ensure we have the venv activated
source /opt/yadacoin/venv37/bin/activate

# Update node username
python3 /opt/yadacoin/cli/cli.py config set-username \
    -u "$NODE_NAME" \
    -c "$CONFIG_PATH" \
    --confirm-backup

echo "✓ Node '$NODE_NAME' configured successfully"

# Start the node
systemctl restart yadanode.service
echo "✓ Node service restarted"
```

Usage:

```bash
./deploy.sh "production-node-01"
# Or use auto-generated name:
./deploy.sh
```

### Example 3: Deploy with Ansible

Use the CLI in an Ansible playbook:

```yaml
---
- name: Configure YadaCoin Node
  hosts: yadacoin_nodes
  vars:
    node_user: "{{ ansible_user }}"
    node_name: "{{ inventory_hostname }}"
    venv_path: /opt/yadacoin/venv37/bin/activate
  tasks:
    - name: Backup config.json
      copy:
        src: /etc/yadacoin/config.json
        dest: /etc/yadacoin/config.json.backup
        remote_src: yes
      become: yes

    - name: Update node username
      shell: |
        source {{ venv_path }}
        python3 /opt/yadacoin/cli/cli.py config set-username \
            -u "{{ node_name }}" \
            -c /etc/yadacoin/config.json \
            --confirm-backup
      become: yes
      become_user: yadacoin
      register: update_result

    - name: Verify update
      debug:
        msg: "{{ update_result.stdout }}"

    - name: Restart YadaCoin service
      service:
        name: yadanode.service
        state: restarted
      become: yes
```

Deployment:

```bash
ansible-playbook -i inventory.ini deploy_nodes.yml
```

### Example 4: Deploy with Terraform + Local-Exec

Use Terraform to provision nodes and configure them:

```hcl
locals {
  node_name = "yadacoin-${var.environment}-${var.node_index}"
}

resource "aws_instance" "yadacoin_node" {
  count         = var.node_count
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type

  provisioner "file" {
    source      = "${path.module}/../../cli"
    destination = "/tmp/cli"

    connection {
      type        = "ssh"
      user        = "ubuntu"
      private_key = file(var.ssh_key)
      host        = self.public_ip
    }
  }

  provisioner "remote-exec" {
    inline = [
      "cd /opt/yadacoin",
      ". venv37/bin/activate",
      "python3 /tmp/cli/cli.py config set-username \\",
      "-u ${local.node_name} \\",
      "-c /etc/yadacoin/config.json \\",
      "--confirm-backup"
    ]

    connection {
      type        = "ssh"
      user        = "ubuntu"
      private_key = file(var.ssh_key)
      host        = self.public_ip
    }
  }

  tags = {
    Name = local.node_name
  }
}
```

## Maintenance Operations

### Example 5: Bulk Update Multiple Nodes

Update usernames on multiple node instances:

```bash
#!/bin/bash

NODES=("node1" "node2" "node3")
CONFIG_PATH="/etc/yadacoin/config.json"

for node in "${NODES[@]}"; do
    echo "Updating node: $node"
    ssh "yadacoin@$node" "
        source ~/yadacoin/venv37/bin/activate
        python3 ~/yadacoin/cli/cli.py config set-username \
            -u '$node' \
            -c '$CONFIG_PATH' \
            --confirm-backup
    "
done

echo "✓ All nodes updated"
```

### Example 6: Scheduled Maintenance Script

Rotate node names monthly with a cron job:

```bash
#!/bin/bash
# /opt/yadacoin/scripts/monthly_node_rotate.sh

set -e

LOGFILE="/var/log/yadacoin/node_rotate.log"
CONFIG_PATH="/etc/yadacoin/config.json"
VENV="/opt/yadacoin/venv37/bin/activate"

{
    echo "$(date): Starting monthly node rotation"

    # Generate new node name with timestamp
    NEW_NAME="node-$(date +%Y%m)-$(hostname -s)"

    # Verify backup exists and is recent (less than 24 hours old)
    if [ -f "$CONFIG_PATH.backup" ]; then
        BACKUP_AGE=$(($(date +%s) - $(stat -f%m "$CONFIG_PATH.backup")))
        if [ $BACKUP_AGE -gt 86400 ]; then
            echo "WARNING: Backup is older than 24 hours"
            exit 1
        fi
    else
        echo "ERROR: No backup found"
        exit 1
    fi

    # Update node name
    source "$VENV"
    python3 /opt/yadacoin/cli/cli.py config set-username \
        -u "$NEW_NAME" \
        -c "$CONFIG_PATH" \
        --confirm-backup

    # Verify update succeeded
    ACTUAL_NAME=$(python3 -c \
        "import json; print(json.load(open('$CONFIG_PATH'))['username'])")

    if [ "$ACTUAL_NAME" = "$NEW_NAME" ]; then
        echo "$(date): ✓ Node rotation successful: $NEW_NAME"
    else
        echo "$(date): ERROR - Name mismatch"
        exit 1
    fi

} | tee -a "$LOGFILE"
```

Add to crontab:

```bash
0 0 1 * * /opt/yadacoin/scripts/monthly_node_rotate.sh
```

## Testing and Validation

### Example 7: Test Script Before Production

Validate the CLI works with your setup:

```bash
#!/bin/bash
# test_cli.sh

set -e

echo "Testing YadaCoin CLI..."

# 1. Check Python environment
echo "1. Checking Python environment..."
python3 --version
source venv37/bin/activate
pip list | grep coincurve

# 2. Check CLI exists and is executable
echo "2. Checking CLI files..."
test -f cli/cli.py
test -f cli/commands/config/update_username.py
test -f cli/commands/config/config_base.py

# 3. Check help output
echo "3. Testing CLI help..."
python3 cli/cli.py --help > /dev/null
python3 cli/cli.py config --help > /dev/null
python3 cli/cli.py config set-username --help > /dev/null

# 4. Test with backup config
echo "4. Testing with backup config..."
cp config/config.json config/config.test.json

python3 cli/cli.py config set-username \
    -u "test-node" \
    -c config/config.test.json \
    --confirm-backup

# 5. Verify config was updated
echo "5. Verifying update..."
NEW_NAME=$(python3 -c \
    "import json; print(json.load(open('config/config.test.json'))['username'])")

if [ "$NEW_NAME" = "test-node" ]; then
    echo "✓ Username updated correctly"
else
    echo "✗ Username update failed"
    exit 1
fi

# 6. Verify signature exists
SIGNATURE=$(python3 -c \
    "import json; cfg = json.load(open('config/config.test.json')); \
     print(bool(cfg.get('username_signature')))")

if [ "$SIGNATURE" = "True" ]; then
    echo "✓ Signature generated correctly"
else
    echo "✗ Signature generation failed"
    exit 1
fi

# Clean up
rm config/config.test.json

echo ""
echo "✓ All tests passed!"
```

Usage:

```bash
bash test_cli.sh
```

### Example 8: Compare Before/After Config

Validate changes with a diff:

```bash
#!/bin/bash

FILE="config/config.json"

cp "$FILE" "$FILE.before"

echo "Updating node username..."
python3 cli/cli.py config set-username -u "new-name" --confirm-backup

echo ""
echo "=== Changes Made ==="
diff <(jq '.username' "$FILE.before") <(jq '.username' "$FILE")
diff <(jq '.username_signature | length' "$FILE.before") \
     <(jq '.username_signature | length' "$FILE")

rm "$FILE.before"
```

## CI/CD Integration

### Example 9: GitHub Actions Workflow

```yaml
name: Deploy YadaCoin Node

on:
  workflow_dispatch:
    inputs:
      node_name:
        description: "Node name"
        required: true
        default: "staging-node"

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.9"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Backup config
        run: cp config/config.json config/config.json.backup

      - name: Update node username
        run: |
          python3 cli/cli.py config set-username \
              -u "${{ github.event.inputs.node_name }}" \
              --confirm-backup

      - name: Verify changes
        run: |
          python3 -c "
          import json
          config = json.load(open('config/config.json'))
          assert config['username'] == '${{ github.event.inputs.node_name }}'
          assert config.get('username_signature')
          print('✓ Config verified')
          "

      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: updated-config
          path: config/config.json
```

## Error Recovery

### Example 10: Rollback Failed Update

```bash
#!/bin/bash

CONFIG="/etc/yadacoin/config.json"
BACKUP="$CONFIG.backup"

echo "YadaCoin CLI - Rollback Utility"
echo ""

if [ ! -f "$BACKUP" ]; then
    echo "✗ No backup found at $BACKUP"
    echo "Manual recovery required. Check:"
    echo "  1. Git history: git log --oneline"
    echo "  2. Existing backups in /etc/yadacoin/"
    exit 1
fi

echo "Current username: $(jq -r '.username' < $CONFIG)"
echo "Backup username: $(jq -r '.username' < $BACKUP)"
echo ""
read -p "Restore from backup? (yes/no): " response

if [ "$response" = "yes" ]; then
    cp "$BACKUP" "$CONFIG"
    echo "✓ Restored from backup"
    echo "New username: $(jq -r '.username' < $CONFIG)"
else
    echo "Rollback cancelled"
fi
```

---

For more information, see:

- [QUICKSTART.md](./QUICKSTART.md) - Quick reference
- [README.md](./README.md) - Full documentation
- [DEVELOPMENT.md](./DEVELOPMENT.md) - Developer guide
