#!/bin/sh

COMMIT_MSG_FILE=$1
COMMIT_MSG_CONTENT=$(cat $COMMIT_MSG_FILE)

# Example regex pattern: Require "fix|feat|chore|docs|style|refactor|perf|test" at the beginning of the commit message.
if ! echo "$COMMIT_MSG_CONTENT" | grep -qE "^(fix|feat|chore|docs|style|refactor|perf|test)"; then
    echo "error: invalid commit message format" >&2
    exit 1
fi

exit 0