#!/usr/bin/env bash
set -euo pipefail

: "${BUILD_CERTIFICATE_BASE64:?}"
: "${P12_PASSWORD:?}"
: "${BUILD_PROVISION_PROFILE_BASE64:?}"
: "${KEYCHAIN_PASSWORD:?}"

CERTIFICATE_PATH="${RUNNER_TEMP}/build_certificate.p12"
PP_PATH="${RUNNER_TEMP}/build_pp.mobileprovision"
KEYCHAIN_PATH="${RUNNER_TEMP}/app-signing.keychain-db"

python3 -c '
import base64, os, sys
from pathlib import Path
Path(sys.argv[1]).write_bytes(base64.b64decode(os.environ["BUILD_CERTIFICATE_BASE64"]))
Path(sys.argv[2]).write_bytes(base64.b64decode(os.environ["BUILD_PROVISION_PROFILE_BASE64"]))
' "$CERTIFICATE_PATH" "$PP_PATH"

security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security set-keychain-settings -lut 21600 "$KEYCHAIN_PATH"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security import "$CERTIFICATE_PATH" -P "$P12_PASSWORD" -A -t cert -f pkcs12 -k "$KEYCHAIN_PATH"
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security list-keychain -d user -s "$KEYCHAIN_PATH"

PP_DIR="$HOME/Library/MobileDevice/Provisioning Profiles"
mkdir -p "$PP_DIR"
security cms -D -i "$PP_PATH" > "${RUNNER_TEMP}/pp.plist"
UUID="$(/usr/libexec/PlistBuddy -c "Print UUID" "${RUNNER_TEMP}/pp.plist")"
cp "$PP_PATH" "$PP_DIR/${UUID}.mobileprovision"
echo "Installed provisioning profile $UUID"
