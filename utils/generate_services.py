import os
if not os.path.exists(os.getcwd() + '/services'):
    os.makedirs(os.getcwd() + '/services')
with open(os.getcwd() + '/services/yadacoin-node.service', 'w+') as f:
    out = """#!/bin/bash
[Unit]
Description=Yada Coin Node service

[Service]
Type=simple
WorkingDirectory={cwd}
ExecStart={cwd}/scripts/start_node.sh

[Install]
WantedBy=multi-user.target
""".format(cwd=os.getcwd())
    f.write(out)
