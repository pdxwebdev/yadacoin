#!/bin/bash
python -u ./utils/generate_config.py auto -c config/config-docker.json
python ./p2p.py mine config/config-docker.json