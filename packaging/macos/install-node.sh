#!/bin/bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${HOME}/Library/Application Support/YadaCoin"
BOOTSTRAP_URL="https://yadacoin.io/yadacoinstatic/bootstrap.tar.gz"
RESTORE_MARKER=".bootstrap-restore-pending"

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "Docker Desktop is not running."
  echo "Install it from https://docs.docker.com/desktop/setup/install/mac-install/ and run this again."
  open "https://docs.docker.com/desktop/setup/install/mac-install/" || true
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is not available."
  exit 1
fi

mkdir -p "$APP_DIR/config"
cd "$APP_DIR"

if [ ! -f config/second_factor ]; then
  install -m 600 /dev/null config/second_factor
fi

FIRST_INSTALL=0
if [ ! -f docker-compose.yml ]; then
  FIRST_INSTALL=1
  cp "$SOURCE_DIR/docker-compose.yml" docker-compose.yml
fi

cp "$SOURCE_DIR/strip-block-indexes.sh" strip-block-indexes.sh
chmod +x strip-block-indexes.sh

if [ "$FIRST_INSTALL" -eq 1 ]; then
  touch "$RESTORE_MARKER"
fi

if [ -f "$RESTORE_MARKER" ]; then
  if [ ! -f dump/yadacoin/blocks.metadata.json ]; then
    rm -rf dump
    curl -fsSL "$BOOTSTRAP_URL" | tar -xz
  fi
fi

docker compose up -d mongodb

if [ -f "$RESTORE_MARKER" ]; then
  docker compose --profile restore up --abort-on-container-exit --exit-code-from restore restore
  docker compose --profile restore rm -f restore
  rm -rf dump
  rm -f "$RESTORE_MARKER"
fi

if [ "$FIRST_INSTALL" -eq 1 ]; then
  docker compose up -d yada-node updater
else
  docker compose up -d
fi

echo "Node is starting."
node_url=""
for _ in $(seq 1 30); do
  node_url=$(docker compose logs --no-color --tail 200 yada-node 2>/dev/null | grep -o 'http://[^ ]*/operator/setup?code=[^ ]*' | tail -n 1 || true)
  if [ -n "$node_url" ]; then
    break
  fi
  sleep 1
done
if [ -z "$node_url" ]; then
  echo "Setup link was not in the node log yet. Read it from: docker compose logs yada-node"
  echo "Do not open /operator/setup without the code from that log."
else
  echo "Open $node_url"
  open "$node_url" || true
fi
echo "State is in $APP_DIR"
