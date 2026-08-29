#!/usr/bin/env bash
set -euo pipefail

REF="${1:-}"
if [[ -z "$REF" ]]; then
  echo "usage: parse-client-tag.sh <password-vX.Y.Z|wallet-vX.Y.Z>" >&2
  exit 1
fi

REF="${REF#refs/tags/}"

if [[ "$REF" =~ ^(password|wallet)-v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  PRODUCT="${BASH_REMATCH[1]}"
  MAJOR="${BASH_REMATCH[2]}"
  MINOR="${BASH_REMATCH[3]}"
  PATCH="${BASH_REMATCH[4]}"
else
  echo "Tag must be password-vX.Y.Z or wallet-vX.Y.Z, got: $REF" >&2
  exit 1
fi

if (( MAJOR > 99 || MINOR > 99 || PATCH > 99 )); then
  echo "Each version component must be 0-99 for Android versionCode mapping" >&2
  exit 1
fi

VERSION="$MAJOR.$MINOR.$PATCH"
VERSION_CODE=$((MAJOR * 10000 + MINOR * 100 + PATCH))

echo "product=$PRODUCT"
echo "version=$VERSION"
echo "version_code=$VERSION_CODE"
