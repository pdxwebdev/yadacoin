#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
dest=${YADA_PLUGINS_DIR:-"$root/plugins"}
manifest="$root/plugins.txt"
mkdir -p "$dest"
while IFS="$(printf '\t')" read -r name url; do
  name=$(printf '%s' "$name" | tr -d '\r')
  url=$(printf '%s' "$url" | tr -d '\r')
  [ -n "${name:-}" ] || continue
  case "$name" in \#*) continue ;; esac
  if [ -d "$dest/$name/.git" ] || [ -f "$dest/$name/.git" ]; then
    git -C "$dest/$name" pull --ff-only || true
    continue
  fi
  case "$url" in
    git@github.com:*) url="https://github.com/${url#git@github.com:}" ;;
  esac
  tmp=$(mktemp -d)
  if git clone --depth 1 "$url" "$tmp/$name" && [ -f "$tmp/$name/handlers.py" ]; then
    rm -rf "$dest/$name"
    mv "$tmp/$name" "$dest/$name"
  else
    echo "skip $name (clone failed)"
  fi
  rm -rf "$tmp"
done < "$manifest"
