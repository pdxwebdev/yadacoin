#!/bin/bash

# Default directory
DEFAULT_DIR="/etc/yadacoin"

# Step 1: Install Docker
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

# Step 2: Create directory if it doesn't exist
if [ ! -d "$DEFAULT_DIR" ]; then
    echo "Creating default directory at $DEFAULT_DIR..."
    sudo mkdir -p $DEFAULT_DIR
fi

# Step 3: Change directory permissions
echo "Setting proper permissions for the default directory..."
sudo chown -R $(whoami) $DEFAULT_DIR

# Step 4: Add the current user to the docker group
if id -nG "$USER" | grep -qw docker; then
    echo "User is already in the docker group!"
else
    # Create docker group if it doesn't exist
    if ! grep -q "^docker:" /etc/group; then
        echo "Docker group does not exist. Creating it..."
        sudo groupadd docker
    fi

    echo "Adding user to the docker group..."
    sudo usermod -aG docker $USER
    echo "You may need to log out and log back in to apply the group changes!"
fi

# Step 5: Set up the systemd service
SERVICE_FILE_NAME="yadanodemanager.service"

echo "Setting up systemd service..."

cat <<EOL | sudo tee "/etc/systemd/system/$SERVICE_FILE_NAME" > /dev/null
[Unit]
Description=Yada Node Process Manager
After=network.target

[Service]
ExecStart=/usr/bin/python3 $DEFAULT_DIR/yadanodemanager.py $DEFAULT_DIR/config/config.json
WorkingDirectory=$DEFAULT_DIR
Restart=always
User=$USER
Group=$(id -gn $USER)

[Install]
WantedBy=multi-user.target
EOL

sudo systemctl daemon-reload
sudo systemctl enable yadanodemanager
sudo systemctl start yadanodemanager

echo "Yada Node Process Manager is now set up as a systemd service and has been started."

echo "Setup completed. Please restart your machine or log out and log back in for group changes to take effect, if necessary."
