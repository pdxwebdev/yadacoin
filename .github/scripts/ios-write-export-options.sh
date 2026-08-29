#!/usr/bin/env bash
set -euo pipefail
OUT="${1:?}"
TEAM_ID="${2:?}"
BUNDLE_ID="${3:?}"
PROFILE_NAME="${4:?}"
python3 - "$OUT" "$TEAM_ID" "$BUNDLE_ID" "$PROFILE_NAME" <<'PY'
import sys
from pathlib import Path
from xml.sax.saxutils import escape
out, team, bundle, profile = sys.argv[1], escape(sys.argv[2]), escape(sys.argv[3]), escape(sys.argv[4])
Path(out).write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>method</key>
  <string>app-store-connect</string>
  <key>signingStyle</key>
  <string>manual</string>
  <key>teamID</key>
  <string>%s</string>
  <key>uploadSymbols</key>
  <true/>
  <key>compileBitcode</key>
  <false/>
  <key>provisioningProfiles</key>
  <dict>
    <key>%s</key>
    <string>%s</string>
  </dict>
</dict>
</plist>
""" % (team, bundle, profile))
PY
