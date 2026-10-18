#!/bin/bash

set -euo pipefail

IS_TERMUX=0
if [ -n "${TERMUX_VERSION:-}" ] || [ "${PREFIX:-}" = "/data/data/com.termux/files/usr" ]; then
  IS_TERMUX=1
fi

BOOTSTRAP_URL="https://yadacoin.io/yadacoinstatic/bootstrap.tar.gz"

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
  pkg install -y python git curl tar proot proot-distro mongodb mongodb-tools

  mkdir -p "$TERMUX_APP_DIR"
  cd "$TERMUX_APP_DIR"

  if [ -d .git ]; then
    git pull --ff-only
  else
    git clone https://github.com/pdxwebdev/yadacoin .
  fi

  python3 -m pip install --upgrade pip
  python3 -m pip install -r requirements.txt

  BOOTSTRAP_ARCHIVE="$TERMUX_APP_DIR/bootstrap.tar.gz"
  BOOTSTRAP_DIR="$TERMUX_APP_DIR/bootstrap"

  curl -fsSL "$BOOTSTRAP_URL" -o "$BOOTSTRAP_ARCHIVE"
  rm -rf "$BOOTSTRAP_DIR"
  mkdir -p "$BOOTSTRAP_DIR"
  tar -xzf "$BOOTSTRAP_ARCHIVE" -C "$BOOTSTRAP_DIR"

  if ! command -v mongorestore >/dev/null 2>&1; then
    echo "Termux detected, but mongorestore was not found after installing mongodb-tools."
    exit 1
  fi

  BOOTSTRAP_DUMP_DIR=$(find "$BOOTSTRAP_DIR" -type d -name dump | head -n 1)
  if [ -z "$BOOTSTRAP_DUMP_DIR" ]; then
    echo "Could not find a dump directory inside the bootstrap archive."
    exit 1
  fi

  mongorestore --drop "$BOOTSTRAP_DUMP_DIR"

  echo "Termux detected: Docker, compose, and service manager setup were intentionally skipped."
  echo "MongoDB was installed through Termux packages; proot support was added to keep the Android path non-rooted."
  echo "Bootstrap data was downloaded, extracted, and restored with mongorestore."
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
  apt-get install -y docker.io curl tar
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y curl tar

  if dnf install -y docker docker-compose-plugin; then
    true
  elif dnf install -y moby-engine docker-compose-plugin; then
    true
  else
    curl -fsSL https://get.docker.com | sh
  fi
elif command -v yum >/dev/null 2>&1; then
  yum install -y curl tar
  if ! yum install -y docker; then
    curl -fsSL https://get.docker.com | sh
  fi
elif command -v apk >/dev/null 2>&1; then
  apk update
  apk add --no-cache docker docker-cli-compose curl tar
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

COMPOSE_URL="https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/docker-compose.example.yml"
STRIP_URL="https://raw.githubusercontent.com/pdxwebdev/yadacoin/master/docker/strip-block-indexes.sh"
RESTORE_MARKER=".bootstrap-restore-pending"

compose_has_service() {
  docker compose --profile restore config --services | grep -qx "$1"
}

node_restarts() {
  docker compose config | awk '
    /^  yada-node:/ { in_node=1; next }
    in_node && /^  [^ ]/ { in_node=0 }
    in_node && $1 == "restart:" {
      gsub(/"/, "", $2)
      if ($2 == "always" || $2 == "on-failure" || $2 == "unless-stopped") found=1
    }
    END { exit found ? 0 : 1 }
  '
}

stop_legacy_manager() {
  if [ "$INIT_SYSTEM" = "systemd" ]; then
    if ! systemctl cat yadanodemanager.service >/dev/null 2>&1; then
      return 0
    fi
    install -d /etc/systemd/system/yadanodemanager.service.d
    cat > /etc/systemd/system/yadanodemanager.service.d/no-compose-down.conf << 'EOF'
[Service]
ExecStop=
ExecStop=/bin/true
EOF
    systemctl daemon-reload
    systemctl disable --now yadanodemanager
    echo "Stopped yadanodemanager without running its compose down hook."
  elif [ -x /etc/init.d/yadanodemanager ]; then
    rc-service yadanodemanager stop || true
    rc-update del yadanodemanager default || true
    echo "Stopped yadanodemanager."
  fi
}

# Host state only. The published image is the application.
DEFAULT_APP_DIR="/etc/yadacoin"
APP_DIR="${1:-$DEFAULT_APP_DIR}"
mkdir -p "$APP_DIR/config"
cd "$APP_DIR"

if [ ! -f config/second_factor ]; then
  install -m 600 /dev/null config/second_factor
fi

FIRST_INSTALL=0
if [ ! -f docker-compose.yml ]; then
  FIRST_INSTALL=1
  curl -fsSL "$COMPOSE_URL" -o docker-compose.yml
fi

curl -fsSL "$STRIP_URL" -o strip-block-indexes.sh
chmod +x strip-block-indexes.sh

if [ "$FIRST_INSTALL" -eq 1 ]; then
  touch "$RESTORE_MARKER"
fi

if [ -f "$RESTORE_MARKER" ]; then
  if [ ! -f dump/yadacoin/blocks.metadata.json ]; then
    rm -rf dump
    curl -fsSL "$BOOTSTRAP_URL" | tar -xz
  fi
elif [ -d dump ]; then
  echo "Leaving dump/ in place. This run will not restore over an existing database."
fi

if node_restarts; then
  stop_legacy_manager
else
  echo "Leaving yadanodemanager enabled: yada-node has no restart policy in docker-compose.yml."
fi

if ! compose_has_service mongodb; then
  echo "docker-compose.yml has no mongodb service. Not restoring or starting the node."
  exit 1
fi

docker compose up -d mongodb

if [ -f "$RESTORE_MARKER" ]; then
  if ! compose_has_service restore; then
    echo "Bootstrap is pending, but docker-compose.yml has no restore service. dump/ was left in place."
    exit 1
  fi
  docker compose --profile restore up --abort-on-container-exit --exit-code-from restore restore
  docker compose --profile restore rm -f restore
  rm -rf dump
  rm -f "$RESTORE_MARKER"
fi

if [ "$FIRST_INSTALL" -eq 1 ]; then
  docker compose up -d yada-node updater
else
  docker compose up -d
fi

echo "Node is starting."
reset=$'\033[0m'
bold=$'\033[1m'
node_url="http://127.0.0.1:8001/operator/setup"
printf '\n\n'
printf '%s%s%s%s\n' "$bold" $'\033[38;5;39m' '██╗   ██╗ █████╗ ██████╗  █████╗  ██████╗ ██████╗ ██╗███╗   ██╗' "$reset"
printf '%s%s%s%s\n' "$bold" $'\033[38;5;45m' '╚██╗ ██╔╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔═══██╗██║████╗  ██║' "$reset"
printf '%s%s%s%s\n' "$bold" $'\033[38;5;51m' ' ╚████╔╝ ███████║██║  ██║███████║██║     ██║   ██║██║██╔██╗ ██║' "$reset"
printf '%s%s%s%s\n' "$bold" $'\033[38;5;50m' '  ╚██╔╝  ██╔══██║██║  ██║██╔══██║██║     ██║   ██║██║██║╚██╗██║' "$reset"
printf '%s%s%s%s\n' "$bold" $'\033[38;5;48m' '   ██║   ██║  ██║██████╔╝██║  ██║╚██████╗╚██████╔╝██║██║ ╚████║' "$reset"
printf '%s%s%s%s\n' "$bold" $'\033[38;5;46m' '   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝' "$reset"
printf '\n'
printf '%s%s  VISIT %s%s%s TO CONFIGURE YOUR NODE%s\n' "$bold" $'\033[38;5;226m' $'\033[1;97m' "$node_url" $'\033[38;5;226m' "$reset"
printf '\n'
echo "Set a username and second factor. Write both down."
echo "The next screen shows the seed once. It is also in $APP_DIR/config/config.json."
echo "The second factor file is $APP_DIR/config/second_factor. Both are required to recover the node."
echo "Wallet: http://127.0.0.1:8001/app"
echo "From another machine, use this host's address on port 8001."
if grep -q '\.:/app' docker-compose.yml; then
  echo "docker-compose.yml still bind-mounts the repo at /app. It was not overwritten."
  echo "The current example does not: $COMPOSE_URL"
fi
if ! compose_has_service updater; then
  echo "This compose file has no updater service, so it was left unchanged."
  echo "The current example is $COMPOSE_URL"
else
  echo "Image updates are applied by the updater service."
fi
echo "Logs: docker compose -f $APP_DIR/docker-compose.yml logs -f yada-node"
echo "The web UI is on port 8001."
