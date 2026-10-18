#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
dest=${YADA_PLUGINS_DIR:-"$root/plugins"}
manifest="$root/plugins.txt"
mkdir -p "$dest"
while IFS="$(printf '\t')" read -r name url; do
  [ -n "${name:-}" ] || continue
  case "$name" in \#*) continue ;; esac
  if [ -d "$dest/$name/.git" ] || [ -f "$dest/$name/.git" ]; then
    git -C "$dest/$name" pull --ff-only || true
    continue
  fi
  if [ -d "$dest/$name" ]; then
    echo "skip $name (exists, not a git checkout)"
    continue
  fi
  git clone "$url" "$dest/$name"
done < "$manifest"
