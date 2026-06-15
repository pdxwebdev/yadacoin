#!/bin/bash

set -euo pipefail

IS_TERMUX=0
if [ -n "${TERMUX_VERSION:-}" ] || [ "${PREFIX:-}" = "/data/data/com.termux/files/usr" ]; then
  IS_TERMUX=1
fi

# Ensure the script is run as root.
if [ "$IS_TERMUX" -eq 0 ] && [ "$EUID" -ne 0 ]; then
  echo "Please run this script as root."
  exit 1
fi

if [ "$IS_TERMUX" -eq 1 ]; then
  TERMUX_APP_DIR="${1:-$HOME/yadacoin}"

  if ! command -v pkg >/dev/null 2>&1; then
    echo "Termux detected, but pkg was not found."
    exit 1
  fi

  pkg update -y
  pkg install -y python git curl tar proot proot-distro mongodb

  mkdir -p "$TERMUX_APP_DIR"
  cd "$TERMUX_APP_DIR"

  if [ -d .git ]; then
    git pull --ff-only
  else
    git clone https://github.com/pdxwebdev/yadacoin .
  fi

  python3 -m pip install --upgrade pip
  python3 -m pip install -r requirements.txt

  echo "Termux detected: Docker, compose, and service manager setup were intentionally skipped."
  echo "MongoDB was installed through Termux packages; proot support was added to keep the Android path non-rooted."
  echo "Native Termux support is limited to preparing the codebase without container startup."
  exit 0
fi

if command -v systemctl >/dev/null 2>&1; then
  INIT_SYSTEM="systemd"
elif command -v rc-service >/dev/null 2>&1 && command -v rc-update >/dev/null 2>&1; then
  INIT_SYSTEM="openrc"
else
  echo "Unsupported init system. Requires systemd or openrc."
  exit 1
fi

if [ -r /etc/os-release ]; then
  . /etc/os-release
  OS_ID="${ID:-}"
  OS_ID_LIKE="${ID_LIKE:-}"
else
  echo "Unable to detect operating system (/etc/os-release not found)."
  exit 1
fi

# hugepages reservation
echo "vm.nr_hugepages=0" >/etc/sysctl.d/99-yadacoin.conf
sysctl --system

# Install required packages
if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y docker.io python3 python3-setuptools curl git tar
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y python3 python3-setuptools curl git tar

  if dnf install -y docker docker-compose-plugin; then
    true
  elif dnf install -y moby-engine docker-compose-plugin; then
    true
  else
    curl -fsSL https://get.docker.com | sh
  fi
elif command -v yum >/dev/null 2>&1; then
  yum install -y python3 python3-setuptools curl git tar
  if ! yum install -y docker; then
    curl -fsSL https://get.docker.com | sh
  fi
elif command -v apk >/dev/null 2>&1; then
  apk update
  apk add --no-cache docker docker-cli-compose python3 py3-setuptools curl git tar
else
  echo "Unsupported package manager for OS ID '${OS_ID}' (ID_LIKE='${OS_ID_LIKE}')."
  exit 1
fi

# Enable and start Docker daemon
if [ "$INIT_SYSTEM" = "systemd" ]; then
  if systemctl list-unit-files | grep -q '^docker\.service'; then
    systemctl enable docker
    systemctl start docker
  elif systemctl list-unit-files | grep -q '^moby\.service'; then
    systemctl enable moby
    systemctl start moby
  else
    echo "Could not find docker.service or moby.service."
    exit 1
  fi
else
  rc-update add docker default
  rc-service docker start
fi

# Install Docker Compose V2 plugin
mkdir -p /usr/local/lib/docker/cli-plugins

ARCH=$(uname -m)

case "$ARCH" in
  x86_64)
    COMPOSE_ARCH=x86_64
    ;;
  aarch64|arm64)
    COMPOSE_ARCH=aarch64
    ;;
  armv7l)
    COMPOSE_ARCH=armv7
    ;;
  *)
    echo "Unsupported architecture: $ARCH"
    exit 1
    ;;
esac

if ! docker compose version >/dev/null 2>&1; then
  curl -SL \
  https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${COMPOSE_ARCH} \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is not available after install."
  exit 1
fi

# Create the directory for your application
DEFAULT_APP_DIR="/etc/yadacoin"
APP_DIR="${1:-$DEFAULT_APP_DIR}"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# Clone the repository
if [ -d .git ]; then
  git pull --ff-only
else
  git clone https://github.com/pdxwebdev/yadacoin .
fi

# Download blockchain data
curl https://yadacoin.io/yadacoinstatic/bootstrap.tar.gz | tar -xz

if [ "$INIT_SYSTEM" = "systemd" ]; then
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
ExecStart=/usr/bin/env python3 yadanodemanager.py
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
else
  # Create an OpenRC service for the process manager
  SERVICE_FILE="/etc/init.d/yadanodemanager"
  cat << EOF > "$SERVICE_FILE"
#!/sbin/openrc-run

name="YadaCoin Node Manager"
description="YadaCoin Node Manager"
directory="$APP_DIR"
pidfile="/run/yadanodemanager.pid"
command="/usr/bin/env"
command_args="python3 $APP_DIR/yadanodemanager.py"
command_background="yes"
command_user="root"

depend() {
    need net docker
}
EOF
  chmod +x "$SERVICE_FILE"
  rc-update add yadanodemanager default
  rc-service yadanodemanager start
fi

echo "Initial setup complete. Now the boostrap data will install in the background. This will take a few minutes. Check status with: service yadanodemanager status. Once that completes, your node will start automatically. You can access in on the web at port 8001"
