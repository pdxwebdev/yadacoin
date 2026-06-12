#!/bin/sh

# Alpine Linux setup script for Termux QEMU environments.
# Runs as root without sudo. Uses OpenRC instead of systemd.
# No hugepages manipulation (not available in QEMU/Termux VMs).

# Install base required packages (non-Docker)
apk update
apk add --no-cache python3 py3-setuptools curl git openrc

# Check if Docker is installed; offer to install if not
if ! command -v docker >/dev/null 2>&1; then
  printf "Docker is not installed. Would you like to install it now? [y/N] "
  read INSTALL_DOCKER
  case "$INSTALL_DOCKER" in
    [yY][eE][sS]|[yY])
      echo "Enabling community repositories..."
      # Add community repo if not already present
      if ! grep -q "^[^#]*community" /etc/apk/repositories; then
        ALPINE_VER=$(cat /etc/alpine-release | cut -d. -f1,2)
        echo "https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VER}/community" >> /etc/apk/repositories
        apk update
      fi
      echo "Installing Docker..."
      apk add --no-cache docker docker-cli-compose
      ;;
    *)
      echo "Skipping Docker installation. The node manager requires Docker to run containers."
      echo "You can install it later with:"
      echo "  echo 'https://dl-cdn.alpinelinux.org/alpine/v\$(cat /etc/alpine-release | cut -d. -f1,2)/community' >> /etc/apk/repositories"
      echo "  apk update && apk add docker docker-cli-compose"
      ;;
  esac
fi

# Enable and start Docker daemon via OpenRC (if installed)
if command -v docker >/dev/null 2>&1; then
  rc-update add docker default
  rc-service docker start
fi

# Create the directory for your application
DEFAULT_APP_DIR="/etc/yadacoin"
APP_DIR="${1:-$DEFAULT_APP_DIR}"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# Clone the repository
git clone https://github.com/pdxwebdev/yadacoin

# Download blockchain data
curl https://yadacoin.io/yadacoinstatic/bootstrap.tar.gz | tar -xz

# Create an OpenRC init script for the node manager
SERVICE_FILE="/etc/init.d/yadanodemanager"
cat << EOF > "$SERVICE_FILE"
#!/sbin/openrc-run

description="YadaCoin Node Manager"
command="/usr/bin/python3"
command_args="$APP_DIR/yadanodemanager.py"
command_background=true
pidfile="/run/yadanodemanager.pid"
directory="$APP_DIR"

depend() {
    need docker
    after net
}

stop() {
    ebegin "Stopping yadanodemanager"
    docker compose -f $APP_DIR/docker-compose.yml down 2>/dev/null || true
    start-stop-daemon --stop --pidfile "\$pidfile"
    eend \$?
}
EOF

chmod +x "$SERVICE_FILE"

# Enable and start the service
rc-update add yadanodemanager default
rc-service yadanodemanager start

echo "Initial setup complete. Bootstrap data will install in the background. This will take a few minutes. Check status with: rc-service yadanodemanager status. Once that completes, your node will start automatically. You can access it on the web at port 8001"
