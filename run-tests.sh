#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status.
cd "$(dirname "$0")"
# Always use the project venv — do not rely on PATH or a side-effect .env.
# pre-commit language:script inherits the caller shell PATH (often Anaconda).
if [ -x "./venv37/bin/python" ]; then
  PYTHON="./venv37/bin/python"
elif [ -x "./venv/bin/python" ]; then
  PYTHON="./venv/bin/python"
else
  echo "run-tests.sh: no project venv found (expected ./venv37/bin/python)" >&2
  exit 1
fi
[ -f .env ] && set -a && source .env && set +a
# If .env tried to activate a venv, ignore PATH changes — stick to PYTHON above.
echo "run-tests.sh: using $($PYTHON -c 'import sys; print(sys.executable)') ($($PYTHON -c 'import sys; print(sys.version.split()[0])'))"
exec "$PYTHON" -m pytest tests/unittests/core --cov=yadacoin.core --cov-config=.coveragerc --cov-report=term-missing --cov-fail-under=100
