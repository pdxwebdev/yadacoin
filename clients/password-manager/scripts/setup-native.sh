#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> install + build JS"
npm install
npm run build:native

export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-en_US.UTF-8}"

for app in password-native demo-native; do
  echo "==> cap sync $app"
  (cd "apps/$app" && npx cap sync) || true
done

echo ""
echo "Next:"
echo "  # iOS (needs modern CocoaPods + Xcode; system Ruby 2.0 pods will fail)"
echo "  cd apps/password-native && npx cap open ios"
echo "  cd apps/demo-native && npx cap open ios"
echo ""
echo "  # Android"
echo "  cd apps/password-native && npx cap open android"
echo "  cd apps/demo-native && npx cap open android"
echo ""
echo "Install BOTH apps on the same device. See apps/NATIVE.md"
