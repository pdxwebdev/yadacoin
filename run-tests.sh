#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status.
[ -f .env ] && source .env
python -m pytest tests/unittests/core --cov=yadacoin.core --cov-config=.coveragerc --cov-report=term-missing --cov-fail-under=100 "$@"