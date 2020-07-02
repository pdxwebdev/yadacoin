import os
if not os.path.exists(os.getcwd() + '/services'):
    os.makedirs(os.getcwd() + '/services')
with open(os.getcwd() + '/services/yadacoin-node.service', 'w+') as f:
    out = """[Unit]
Description=Yada Coin Node service
After=network.target

[Service]
Type=forking
User={user}
Group={user}
RemainAfterExit=true
WorkingDirectory={cwd}
ExecStart={cwd}/scripts/start_node.sh
Environment=MOTOR_MAX_WORKERS=1
TimeoutStopSec=2
Restart=always

[Install]
WantedBy=multi-user.target
""".format(cwd=os.getcwd())
    f.write(out)
