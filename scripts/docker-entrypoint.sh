#!/bin/sh
set -eu

if [ -n "${YADA_PLUGINS_DIR:-}" ]; then
  dest=$YADA_PLUGINS_DIR
elif grep -q ' /plugins ' /proc/mounts 2>/dev/null; then
  dest=/plugins
else
  exec "$@"
fi

deps=$dest/.pydeps
mkdir -p "$dest" "$deps"
export YADA_PLUGINS_DIR=$dest
export PYTHONPATH=$deps${PYTHONPATH:+:$PYTHONPATH}

manifest=${YADA_PLUGINS_MANIFEST:-/app/plugins.txt}
essential="operator app nodeapi graphapi explorerapi kel apidocs product yadacoinwallet yadacoinpool yadapasswordsignin passwordrotation"

https_url() {
  case "$1" in
    git@github.com:*) printf 'https://github.com/%s\n' "${1#git@github.com:}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

latest_tag() {
  git ls-remote --tags "$1" | python3 -c '
import sys
found = {}
for line in sys.stdin:
    parts = line.split()
    if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
        continue
    ref = parts[1][:-3] if parts[1].endswith("^{}") else parts[1]
    name = ref.rsplit("/", 1)[-1]
    text = name[1:] if name.startswith("v") else name
    bits = text.split(".")
    if bits and all(bit.isdigit() for bit in bits):
        found[name] = tuple(int(bit) for bit in bits)
if found:
    print(max(found, key=found.get))
' || true
}

update_plugin() {
  name=$1
  url=$2
  tag=$(latest_tag "$url")
  if [ -d "$dest/$name/.git" ] || [ -f "$dest/$name/.git" ]; then
    git -C "$dest/$name" remote set-url origin "$url"
    if [ -n "$tag" ]; then
      git -C "$dest/$name" fetch --depth 1 origin "refs/tags/$tag:refs/tags/$tag"
      git -C "$dest/$name" checkout --detach "$tag"
    else
      git -C "$dest/$name" fetch --depth 1 origin
      git -C "$dest/$name" checkout --detach FETCH_HEAD
    fi
    return
  fi
  tmp=$(mktemp -d)
  if [ -n "$tag" ]; then
    git clone --depth 1 --branch "$tag" "$url" "$tmp/$name"
  else
    git clone --depth 1 "$url" "$tmp/$name"
  fi
  if [ -f "$tmp/$name/handlers.py" ]; then
    rm -rf "$dest/$name"
    mv "$tmp/$name" "$dest/$name"
  fi
  rm -rf "$tmp"
}

if [ -f "$manifest" ]; then
  while IFS="$(printf '\t')" read -r name url; do
    [ -n "${name:-}" ] || continue
    case "$name" in \#*) continue ;; esac
    url=$(https_url "$url")
    if ! update_plugin "$name" "$url"; then
      echo "skip $name (update failed)" >&2
    fi
  done < "$manifest"
fi

missing=""
for name in $essential; do
  if [ ! -f "$dest/$name/handlers.py" ]; then
    missing="$missing $name"
  fi
done
if [ -n "$missing" ]; then
  echo "essential plugins missing:$missing" >&2
  exit 1
fi

for req in "$dest"/*/requirements.txt; do
  [ -f "$req" ] || continue
  pip install -r "$req" --target "$deps"
done

exec "$@"
