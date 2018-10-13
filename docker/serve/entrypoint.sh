#!/bin/bash
python -u ./utils/generate_config.py auto -c config/config-docker.json
python ./p2p.py serve config/config-docker.json