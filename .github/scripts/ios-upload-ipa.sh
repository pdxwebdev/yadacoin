#!/usr/bin/env bash
set -euo pipefail

IPA="${1:?ipa path required}"
if [[ ! -f "$IPA" ]]; then
  echo "IPA not found: $IPA" >&2
  exit 1
fi

if [[ -n "${APP_STORE_CONNECT_API_KEY:-}" && -n "${APP_STORE_CONNECT_KEY_ID:-}" && -n "${APP_STORE_CONNECT_ISSUER_ID:-}" ]]; then
  KEY_DIR="$HOME/.appstoreconnect/private_keys"
  mkdir -p "$KEY_DIR"
  python3 -c '
import os, sys
from pathlib import Path
key = os.environ["APP_STORE_CONNECT_API_KEY"].replace("\\n", "\n")
Path(sys.argv[1]).write_text(key if key.endswith("\n") else key + "\n")
' "$KEY_DIR/AuthKey_${APP_STORE_CONNECT_KEY_ID}.p8"
  chmod 600 "$KEY_DIR/AuthKey_${APP_STORE_CONNECT_KEY_ID}.p8"
  if xcrun iTMSTransporter -m upload -assetFile "$IPA" -apiKey "$APP_STORE_CONNECT_KEY_ID" -apiIssuer "$APP_STORE_CONNECT_ISSUER_ID" -v informational; then
    exit 0
  fi
  echo "iTMSTransporter failed, trying altool --apiKey"
  xcrun altool --upload-app --type ios --file "$IPA" --apiKey "$APP_STORE_CONNECT_KEY_ID" --apiIssuer "$APP_STORE_CONNECT_ISSUER_ID"
elif [[ -n "${APP_STORE_CONNECT_USERNAME:-}" && -n "${APP_STORE_CONNECT_PASSWORD:-}" ]]; then
  xcrun altool --upload-app --type ios --file "$IPA" --username "$APP_STORE_CONNECT_USERNAME" --password "$APP_STORE_CONNECT_PASSWORD"
else
  echo "Skipping App Store upload: set APP_STORE_CONNECT_API_KEY + KEY_ID + ISSUER_ID (preferred) or USERNAME + PASSWORD"
  exit 0
fi
