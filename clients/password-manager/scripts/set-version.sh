#!/usr/bin/env bash
set -euo pipefail
VERSION="${1:-}"
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "usage: set-version.sh X.Y.Z" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IFS=. read -r MAJOR MINOR PATCH <<<"$VERSION"
VERSION_CODE=$((10#$MAJOR * 10000 + 10#$MINOR * 100 + 10#$PATCH))

python3 - "$ROOT" "$VERSION" "$VERSION_CODE" <<'PY'
import json, re, sys
from pathlib import Path
root = Path(sys.argv[1])
version, version_code = sys.argv[2], sys.argv[3]

def bump_json(path):
    data = json.loads(path.read_text())
    if "version" in data:
        data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n")

bump_json(root / "package.json")
bump_json(root / "apps/extension/package.json")
bump_json(root / "apps/extension/manifest.json")
bump_json(root / "apps/password-native/package.json")

gradle = root / "apps/password-native/android/app/build.gradle"
g = gradle.read_text()
g = re.sub(
    r'versionName \(System\.getenv\("ANDROID_VERSION_NAME"\) \?: "[^"]+"\)',
    'versionName (System.getenv("ANDROID_VERSION_NAME") ?: "%s")' % version,
    g,
)
g = re.sub(
    r'versionCode \(System\.getenv\("ANDROID_VERSION_CODE"\) \? System\.getenv\("ANDROID_VERSION_CODE"\)\.toInteger\(\) : \d+\)',
    'versionCode (System.getenv("ANDROID_VERSION_CODE") ? System.getenv("ANDROID_VERSION_CODE").toInteger() : %s)' % version_code,
    g,
)
gradle.write_text(g)

pbx = root / "apps/password-native/ios/App/App.xcodeproj/project.pbxproj"
p = pbx.read_text()
p = re.sub(r"MARKETING_VERSION = [^;]+;", "MARKETING_VERSION = %s;" % version, p)
p = re.sub(r"CURRENT_PROJECT_VERSION = [^;]+;", "CURRENT_PROJECT_VERSION = %s;" % version_code, p)
pbx.write_text(p)
print("set password-manager version %s (%s)" % (version, version_code))
PY
