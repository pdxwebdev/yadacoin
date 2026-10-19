#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGE="$(mktemp -d)"
PAYLOAD="$STAGE/payload"
SCRIPTS="$STAGE/scripts"
VERSION="$(head -1 "$ROOT/VERSION" | tr -d '[:space:]')"
OUT="${1:-$ROOT/yadacoin-node.pkg}"

mkdir -p "$PAYLOAD" "$SCRIPTS"
cp "$ROOT/packaging/macos/install-node.sh" "$PAYLOAD/install-node.sh"
cp "$ROOT/docker-compose.example.yml" "$PAYLOAD/docker-compose.yml"
cp "$ROOT/docker/strip-block-indexes.sh" "$PAYLOAD/strip-block-indexes.sh"
cp "$ROOT/packaging/macos/scripts/postinstall" "$SCRIPTS/postinstall"
chmod 755 "$PAYLOAD/install-node.sh" "$PAYLOAD/strip-block-indexes.sh" "$SCRIPTS/postinstall"

pkgbuild \
  --root "$PAYLOAD" \
  --scripts "$SCRIPTS" \
  --identifier io.yadacoin.node \
  --version "$VERSION" \
  --install-location /usr/local/yadacoin \
  "$OUT"

rm -rf "$STAGE"
echo "Wrote unsigned $OUT"
