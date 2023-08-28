#!/bin/bash

# Ensure the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run this script as root."
  exit
fi

# Install required packages
apt update
apt install -y python3 python3-pip git

# Create the directory for your application
APP_DIR="/etc/yadacoin"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# Clone the repository
git clone https://github.com/pdxwebdev/yadacoin .

# Create a systemd service for the process manager
SERVICE_FILE="/etc/systemd/system/yadanodemanager.service"
cat << EOF > "$SERVICE_FILE"
[Unit]
Description=YadaCoin Node Manager
After=network.target

[Service]
User=root
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 yadanodemanager.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start the service
systemctl daemon-reload
systemctl enable yadanodemanager
systemctl start yadanodemanager

echo "Setup complete. YadaCoin Node Manager is now running."
