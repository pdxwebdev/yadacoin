#!/bin/bash

# Ensure the script is run with superuser privileges
if [ "$EUID" -ne 0 ]; then
    echo "Please run this script as root."
    exit
fi

# Step 0: Install git if it isn't already
if ! command -v git &> /dev/null; then
    echo "Git is not installed. Installing Git..."
    sudo apt update
    sudo apt install -y git
else
    echo "Git is already installed."
fi

# Step 1: Clone the Yadacoin repository
if [ ! -d "/etc/yadacoin" ]; then
    echo "Cloning the Yadacoin repository..."
    sudo git clone https://github.com/pdxwebdev/yadacoin /etc/yadacoin
else
    echo "/etc/yadacoin directory already exists."
fi

# Step 2: Install Docker
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Installing Docker..."
    sudo apt update
    sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
    sudo add-apt-repository -y "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
    sudo apt update
    sudo apt install -y docker-ce
else
    echo "Docker is already installed."
fi

# Step 3: Set up user permissions
sudo usermod -aG docker $USER
sudo chown $USER:$USER /var/run/docker.sock
sudo chown -R $USER:$USER /etc/yadacoin

# Step 4: Create and enable systemd service
SERVICE_FILE_CONTENT=$(cat <<EOF
[Unit]
Description=Yadanode Manager

[Service]
ExecStart=/usr/bin/python3 /etc/yadacoin/yadanodemanager.py /etc/yadacoin/config/config.json
WorkingDirectory=/etc/yadacoin
Restart=always
User=$USER
Group=$USER

[Install]
WantedBy=multi-user.target
EOF
)

echo "${SERVICE_FILE_CONTENT}" > /etc/systemd/system/yadanodemanager.service
sudo systemctl daemon-reload
sudo systemctl enable yadanodemanager.service
sudo systemctl start yadanodemanager.service

echo "Setup complete. The Yadacoin Node Manager is now running."
