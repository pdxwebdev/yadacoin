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

wanted() {
  case " $essential " in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

if [ -f "$manifest" ]; then
  while IFS="$(printf '\t')" read -r name url; do
    [ -n "${name:-}" ] || continue
    case "$name" in \#*) continue ;; esac
    wanted "$name" || continue
    url=$(https_url "$url")
    if [ -d "$dest/$name/.git" ] || [ -f "$dest/$name/.git" ]; then
      git -C "$dest/$name" pull --ff-only || true
      continue
    fi
    if [ -d "$dest/$name" ]; then
      continue
    fi
    git clone --depth 1 "$url" "$dest/$name"
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
