#!/bin/bash
set -e
if [[ -z "$1" ]]; then
  echo "Usage: bash git_tag.sh <version> <message> [extra-push-args]" >&2
  exit 1
fi
if [[ -z "$2" ]]; then
  echo "Error: tag message is required as the second argument" >&2
  echo "Usage: bash git_tag.sh <version> <message> [extra-push-args]" >&2
  exit 1
fi
sed -i.bak "1s/.*/$1/" VERSION && rm VERSION.bak
git commit VERSION -m "feat: inc version, v$1"
git tag -a "v$1" -m "$2"
git push origin master --tags $3
