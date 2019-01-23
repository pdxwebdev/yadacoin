import os
if not os.path.exists(os.getcwd() + '/services'):
    os.makedirs(os.getcwd() + '/services')
with open(os.getcwd() + '/services/yadacoin-serve.service', 'w+') as f:
    out = """#!/bin/bash
[Unit]
Description=Yada Coin Serve Worker

[Service]
Type=simple
WorkingDirectory={cwd}
ExecStart={cwd}/scripts/start_serve.sh

[Install]
WantedBy=multi-user.target
""".format(cwd=os.getcwd())
    f.write(out)
with open(os.getcwd() + '/services/yadacoin-mine.service', 'w+') as f:
    out = """#!/bin/bash
[Unit]
Description=Yada Coin Mine Worker

[Service]
Type=simple
WorkingDirectory={cwd}
ExecStart={cwd}/scripts/start_mine.sh

[Install]
WantedBy=multi-user.target
""".format(cwd=os.getcwd())
    f.write(out)
with open(os.getcwd() + '/services/yadacoin-consensus.service', 'w+') as f:
    out = """#!/bin/bash
[Unit]
Description=Yada Coin Consensus Worker

[Service]
Type=simple
WorkingDirectory={cwd}
ExecStart={cwd}/scripts/start_consensus.sh

[Install]
WantedBy=multi-user.target
""".format(cwd=os.getcwd())
    f.write(out)
with open(os.getcwd() + '/services/yadacoin-pool.service', 'w+') as f:
    out = """#!/bin/bash
[Unit]
Description=Yada Coin Pool Worker

[Service]
Type=simple
WorkingDirectory={cwd}
ExecStart={cwd}/scripts/start_pool.sh

[Install]
WantedBy=multi-user.target
""".format(cwd=os.getcwd())
    f.write(out)

