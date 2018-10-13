#!/bin/bash
python -u /usr/src/app/yadacoin/utils/generate_config.py auto -c config/config-docker.json
python /usr/src/app/yadacoin/p2p.py serve config/config-docker.json