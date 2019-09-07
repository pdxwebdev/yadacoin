#!/bin/bash
python -u /usr/src/app/yadacoin/utils/generate_config.py auto -c /config/config-docker.json --mongodb-host mongodb
python /usr/src/app/yadacoin/tnode.py --config=/config/config-docker.json --debug=true --verify=false