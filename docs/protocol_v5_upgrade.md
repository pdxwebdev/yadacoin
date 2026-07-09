# Protocol Version 5 Upgrade Guide — KEL Enforcement

> ⚠️ **This is a breaking change.** Nodes running protocol version < 5 will be
> rejected by all upgraded peers. Network disruptions are expected over the next
> several days while the network migrates.

## What's changing

YadaCoin now enforces **mandatory Key Event Log (KEL)** registration for all
nodes. Every node must have:

1. A **BIP39 seed phrase** (`"seed"` field in `config.json`)
2. A **`SECOND_FACTOR` environment variable** set at startup

These two secrets together derive a KEL-protected signing key that replaces the
plain WIF private key for block signing, transaction signing, and peer
authentication. If either is missing the node will refuse to start.

Nodes without a `seed` must follow the full migration path below to move funds
to the new KEL-protected address before upgrading.

---

## Before you begin — back up your config

```bash
cp config/config.json config/config.json.bak
```

Keep this backup somewhere safe. You will need it in several steps below.

---

## Step 1 — Does your config have a `seed`?

Open your backup `config.json` and look for a `"seed"` field.

- **Yes, it has a `seed`** → skip to [Step 4](#step-4--set-second_factor-and-restart).
- **No `seed` field** → continue to Step 2.

---

## Step 2 — Import your old WIF into the web wallet (no-seed configs only)

Your current node address is controlled by the `"wif"` value in `config.json`.
You need to move those funds to the new KEL address after the upgrade.

1. Copy the `"wif"` value from your backup `config.json`.
2. Open the YadaCoin web wallet (`http://your-node:port/wallet`).
3. Use **Import WIF** to load your old key — your balance will appear.
4. **Do not send anything yet.** You need your new KEL address first (see [Step 5](#step-5--find-your-new-kel-address)).

---

## Step 3 — Generate a fresh config (no-seed configs only)

Delete the existing `config.json` so the node generates a new one with a fresh
seed and keypair, then **stop the node immediately** once it starts.

**Linux / macOS:**
```bash
rm config/config.json
python yadacoin/app.py --config=config/config.json
# Wait for "Node started" then Ctrl+C
```

**Windows:** delete `config.json` from the YadaCoin folder, launch the node
executable, wait for it to start, then close it.

Now re-open `config.json` and copy back your custom values from the backup —
`peer_host`, `peer_port`, `serve_port`, `mongodb_host`, `site_database`, API
keys, etc.

> **Do not copy back** `private_key`, `wif`, `public_key`, `address`, or
> `username_signature`. Leave the newly generated values in place.

---

## Step 4 — Set your `username` and second factor, then restart

### 4a — Set your username in `config.json`

Protocol V5 uses your `username` as part of your node's on-chain identity.
Open `config/config.json` and make sure the `"username"` field is set to a
unique, non-blank string — this becomes your permanent node identity on the
network:

```json
{
  "username": "your_unique_node_name",
  ...
}
```

> ⚠️ Pick carefully — username is registered on-chain at inception and cannot
> be changed without re-registering. It must be unique across the entire network.

### 4b — Set your second factor

Choose a strong secret string and store it securely alongside your seed —
**you need both to recover your node.**

See the **[README — Required environment variables](../README.md#required-environment-variables)**
section for all options (`SECOND_FACTOR_FILE` recommended, `SECOND_FACTOR` env
var as fallback) with full examples for Linux, Docker, and Windows.

**Quick reference:**

### Linux (systemd)

Add to your service file:
```ini
[Service]
Environment=SECOND_FACTOR=your_secret_here
```
Then:
```bash
sudo systemctl daemon-reload
sudo systemctl restart yadacoin
```

### Linux (manual)

```bash
export SECOND_FACTOR=your_secret_here
python yadacoin/app.py --config=config/config.json
```

### Docker (`docker-compose.yml`)

**Option A — bind mount from `/etc/yadacoin/second_factor` (recommended for VPS/bare-metal Docker):**

On the host:
```bash
sudo mkdir -p /etc/yadacoin
echo "your_strong_secret" | sudo tee /etc/yadacoin/second_factor > /dev/null
sudo chmod 400 /etc/yadacoin/second_factor
sudo chown root:root /etc/yadacoin/second_factor
```

In `docker-compose.yml`:
```yaml
services:
  yadacoin:
    environment:
      - SECOND_FACTOR_FILE=/run/secrets/second_factor
    volumes:
      - type: bind
        source: /etc/yadacoin/second_factor
        target: /run/secrets/second_factor
        read_only: true
```

**Option B — plain environment variable (development only):**
```yaml
environment:
  - SECOND_FACTOR=your_secret_here
```

Then restart:
```bash
docker-compose down && docker-compose up -d
```

### Windows

Search **Environment Variables** in Windows Settings → add `SECOND_FACTOR` as a
User variable → restart the node executable.

---

## Step 5 — Find your new KEL address

Once the node starts, it automatically submits a KEL inception transaction to
the mempool. After it confirms (~1–2 min / 1 block), your new KEL-protected
address is the `prerotated_key_hash` of the **last entry** in your key event
log.

**Via the API:**
```
GET http://your-node:port/key-event-log?public_key=YOUR_NEW_PUBLIC_KEY
```
Look at the last object in the returned array — the `prerotated_key_hash` field
is your active KEL address.

**Via the node UI:**  
Browse to `http://your-node:port/key-rotation` and check the current active
address displayed there.

---

## Step 6 — Send funds to the new address (no-seed configs only)

Back in the web wallet where you imported your old WIF (Step 2):

1. Paste your new KEL address (from Step 5) as the recipient.
2. Send your full balance.
3. Done — your funds are now under KEL protection.

Your old address will continue to work for spending via the cross-key KEL
spending feature, but all new activity should use the KEL address.

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `FATAL: config.json is missing the 'seed'` | No `seed` in config | Follow Steps 2–3 |
| `FATAL: environment variable SECOND_FACTOR is not set` | Env var missing | Set `SECOND_FACTOR` before starting |
| `FATAL: admin_kel inception public_key mismatch` | Wrong seed or SECOND_FACTOR for existing `admin_kel` | Verify both secrets match what was used during init |
| `username is required and must not be blank` | No `username` in config.json | Add a unique `"username"` field — see Step 4a |
| Node rejected by peers | Protocol version mismatch | Ensure you are running the latest release |
