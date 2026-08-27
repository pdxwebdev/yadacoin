#!/usr/bin/env bash
# Build password-manager packages.
# Usage: ./scripts/build.sh <all|core|extension|android|ios>
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TARGET="${1:-}"
if [[ -z "$TARGET" || "$TARGET" == "-h" || "$TARGET" == "--help" ]]; then
  cat <<EOF
Usage: $(basename "$0") <target>

  all         core + shared-ui + extension + mobile + native (JS) + demo-native
  core        @yadacoin/password-core
  extension   core + shared-ui + browser extension (dist/)
  android     core + shared-ui + password-native JS, cap sync, assembleDebug
  ios         core + shared-ui + password-native JS, cap sync, simulator build

Run from anywhere; script cds to clients/password-manager.
EOF
  exit 0
fi

need_node() {
  command -v npm >/dev/null || { echo "npm is required"; exit 1; }
}

build_core() {
  echo "==> core"
  npm run build -w @yadacoin/password-core
}

build_ui() {
  echo "==> shared-ui"
  npm run build -w @yadacoin/password-shared-ui
}

build_extension() {
  build_core
  build_ui
  echo "==> extension"
  npm run build -w @yadacoin/password-extension
}

build_native_js() {
  build_core
  build_ui
  echo "==> password-native www"
  npm run build -w @yadacoin/password-native
}

build_android() {
  need_node
  build_native_js
  echo "==> capacitor sync android"
  (cd apps/password-native && npx cap sync android)
  echo "==> gradle assembleDebug"
  (cd apps/password-native/android && ./gradlew assembleDebug)
  echo "APK: apps/password-native/android/app/build/outputs/apk/debug/"
}

build_ios() {
  need_node
  build_native_js
  echo "==> capacitor sync ios"
  (cd apps/password-native && npx cap sync ios)
  if [[ -f apps/password-native/ios/App/Podfile ]]; then
    echo "==> pod install"
    (cd apps/password-native/ios/App && pod install)
  fi
  echo "==> xcodebuild (iphonesimulator Debug)"
  xcodebuild \
    -workspace apps/password-native/ios/App/App.xcworkspace \
    -scheme App \
    -configuration Debug \
    -sdk iphonesimulator \
    -destination 'generic/platform=iOS Simulator' \
    CODE_SIGNING_ALLOWED=NO \
    build
}

build_all() {
  need_node
  build_extension
  echo "==> mobile"
  npm run build -w @yadacoin/password-mobile
  echo "==> password-native www"
  npm run build -w @yadacoin/password-native
  echo "==> demo-native www"
  npm run build -w @yadacoin/demo-native
}

need_node
case "$TARGET" in
  all) build_all ;;
  core) build_core ;;
  extension) build_extension ;;
  android) build_android ;;
  ios) build_ios ;;
  *)
    echo "unknown target: $TARGET"
    echo "use: all | core | extension | android | ios"
    exit 1
    ;;
esac

echo "done: $TARGET"
