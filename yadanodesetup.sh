#!/bin/bash

# Ensure the script is run as root.
if [ "$EUID" -ne 0 ]; then
  echo "Please run this script as root."
  exit
fi

# hugepages reservation
sudo bash -c "echo vm.nr_hugepages=256 >> /etc/sysctl.conf"

# Install required packages
apt update
apt install -y docker-compose

# Create the directory for your application
APP_DIR="/etc/yadacoin"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# Clone the repository
git clone https://github.com/pdxwebdev/yadacoin .

# Download blockchain data
curl https://yadacoin.io/yadacoinstatic/bootstrap.tar.gz | tar -xz

# Create a systemd service for the process manager
SERVICE_FILE="/etc/systemd/system/yadanodemanager.service"
cat << EOF > "$SERVICE_FILE"
[Unit]
Description=YadaCoin Node Manager
After=network.target
StartLimitIntervalSec=500
StartLimitBurst=5

[Service]
User=root
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 yadanodemanager.py
ExecStop=/usr/bin/docker-compose -f /etc/yadacoin/docker-compose.yml down
KillMode=process
Restart=always
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start the service
systemctl daemon-reload
systemctl enable yadanodemanager
systemctl start yadanodemanager

echo "Setup complete. YadaCoin Node Manager is now running."
