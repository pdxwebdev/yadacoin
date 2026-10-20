#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PKG="${1:-$ROOT/yadacoin-node.pkg}"
DMG="${2:-$ROOT/yadacoin-macos.dmg}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

required=(
  MACOS_INSTALLER_CERTIFICATE_BASE64
  MACOS_APPLICATION_CERTIFICATE_BASE64
  MACOS_CERTIFICATE_PASSWORD
  KEYCHAIN_PASSWORD
  APPLE_TEAM_ID
  APP_STORE_CONNECT_API_KEY
  APP_STORE_CONNECT_KEY_ID
  APP_STORE_CONNECT_ISSUER_ID
)
for name in "${required[@]}"; do
  if [ -z "${!name:-}" ]; then
    echo "Refusing to publish an unsigned installer. Missing $name."
    exit 1
  fi
done

KEYCHAIN="$WORKDIR/signing.keychain-db"
security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security set-keychain-settings -lut 21600 "$KEYCHAIN"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN"
security list-keychains -d user -s "$KEYCHAIN" $(security list-keychains -d user | tr -d '"')

import_p12() {
  local b64="$1"
  echo "$b64" | base64 --decode > "$WORKDIR/cert.p12"
  security import "$WORKDIR/cert.p12" -k "$KEYCHAIN" -P "$MACOS_CERTIFICATE_PASSWORD" -T /usr/bin/productsign -T /usr/bin/codesign
  rm -f "$WORKDIR/cert.p12"
}
import_p12 "$MACOS_INSTALLER_CERTIFICATE_BASE64"
import_p12 "$MACOS_APPLICATION_CERTIFICATE_BASE64"
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN"

INSTALLER_ID="$(security find-identity -v "$KEYCHAIN" | sed -n 's/.*"\(Developer ID Installer:.*\)"/\1/p' | head -1)"
APP_ID="$(security find-identity -v -p codesigning "$KEYCHAIN" | sed -n 's/.*"\(Developer ID Application:.*\)"/\1/p' | head -1)"
if [ -z "$INSTALLER_ID" ] || [ -z "$APP_ID" ]; then
  echo "Developer ID Installer and Developer ID Application identities were not found."
  echo "The iOS distribution certificate cannot sign a downloadable Mac installer."
  exit 1
fi

SIGNED="$WORKDIR/yadacoin-node.pkg"
productsign --sign "$INSTALLER_ID" --keychain "$KEYCHAIN" "$PKG" "$SIGNED"
pkgutil --check-signature "$SIGNED"

printf '%s' "$APP_STORE_CONNECT_API_KEY" | base64 --decode > "$WORKDIR/AuthKey.p8"
notarize() {
  xcrun notarytool submit "$1" \
    --key "$WORKDIR/AuthKey.p8" \
    --key-id "$APP_STORE_CONNECT_KEY_ID" \
    --issuer "$APP_STORE_CONNECT_ISSUER_ID" \
    --wait
  xcrun stapler staple "$1"
  xcrun stapler validate "$1"
}
notarize "$SIGNED"

STAGE="$WORKDIR/dmg"
mkdir -p "$STAGE"
cp "$SIGNED" "$STAGE/YadaCoin Node.pkg"
cat > "$STAGE/README.txt" << 'EOF'
Open "YadaCoin Node.pkg".

Docker Desktop must already be installed and running.
The package installs to /usr/local/yadacoin and starts the node for the logged-in user.
Then open the /operator/setup?code= link printed in the node log.
Do not open /operator/setup without that code.
EOF

rm -f "$DMG"
hdiutil create -volname "YadaCoin Node" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
codesign --force --sign "$APP_ID" --keychain "$KEYCHAIN" --timestamp "$DMG"
codesign --verify --verbose=2 "$DMG"
notarize "$DMG"
spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG"

cp "$SIGNED" "$PKG"
security delete-keychain "$KEYCHAIN"
echo "Signed and notarized $DMG"
