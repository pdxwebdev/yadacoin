#!/bin/bash
python -u /usr/src/app/yadacoin/utils/generate_config.py auto -c /config/config-docker.json --mongo-host mongodb
python /usr/src/app/yadacoin/p2p.py consensus /config/config-docker.json