#!/bin/bash
python -u /usr/src/app/yadacoin/utils/generate_config.py auto -c config-docker.json
python /usr/src/app/yadacoin/p2p.py consensus config-docker.json