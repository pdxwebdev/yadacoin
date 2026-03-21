#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status.
[ -f .env ] && source .env
python -m pytest tests/unittests --hash_server_domain=$HASH_SERVER_DOMAIN # workaround for hashing with pyrx on mac