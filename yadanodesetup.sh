#!/bin/bash

# Ensure the script is run as root.
if [ "$EUID" -ne 0 ]; then
  echo "Please run this script as root."
  exit
fi

# hugepages reservation
sudo bash -c "echo vm.nr_hugepages=0 >> /etc/sysctl.conf"

# Install required packages
apt update
apt install -y docker.io python3-setuptools curl

# Enable and start Docker daemon
systemctl enable docker
systemctl start docker

# Install Docker Compose V2 plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Create the directory for your application
DEFAULT_APP_DIR="/etc/yadacoin"
APP_DIR="${1:-$DEFAULT_APP_DIR}"
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
ExecStop=/bin/sh -c 'docker compose -f $APP_DIR/docker-compose.yml down 2>/dev/null || docker-compose -f $APP_DIR/docker-compose.yml down'
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

echo "Initial setup complete. Now the boostrap data will install in the background. This will take a few minutes. Check status with: service yadanodemanager status. Once that completes, your node will start automatically. You can access in on the web at port 8001"
