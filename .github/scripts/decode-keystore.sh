#!/usr/bin/env bash
set -euo pipefail

: "${ANDROID_KEYSTORE_BASE64:?}"
OUT="${1:-${RUNNER_TEMP}/release.jks}"
python3 -c '
import base64, os, sys
from pathlib import Path
Path(sys.argv[1]).write_bytes(base64.b64decode(os.environ["ANDROID_KEYSTORE_BASE64"]))
print(sys.argv[1])
' "$OUT"
