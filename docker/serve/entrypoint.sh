#!/bin/bash
mkdir /usr/src/app/yadacoin/config
python -u /usr/src/app/yadacoin/utils/generate_config.py auto -c /usr/src/app/yadacoin/config/config-docker.json --mongodb-host mongodb
python /usr/src/app/yadacoin/tnode.py --config=/usr/src/app/yadacoin/config/config-docker.json --debug=true --verify=false