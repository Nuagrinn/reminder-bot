#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-reminder-bot}"
APP_HOME="${APP_HOME:-/home/$APP_USER}"
APP_DIR="${APP_DIR:-/opt/reminder-bot}"
BOT_REPO_URL="${BOT_REPO_URL:-}"
BOT_GIT_BRANCH="${BOT_GIT_BRANCH:-main}"
ASSISTANT_SHARED_DIR="${ASSISTANT_SHARED_DIR:-/opt/assistant-shared}"
WHISPER_MODEL="${WHISPER_MODEL:-medium}"
INSTALL_CLAUDE_CLI="${INSTALL_CLAUDE_CLI:-1}"
NODE_MAJOR="${NODE_MAJOR:-22}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root or through sudo." >&2
  exit 1
fi

if [ -z "$BOT_REPO_URL" ]; then
  echo "Set BOT_REPO_URL to the git URL of reminder-bot." >&2
  exit 1
fi

apt-get update
apt-get install -y \
  build-essential \
  ca-certificates \
  cmake \
  curl \
  ffmpeg \
  git \
  python3 \
  python3-pip \
  python3-venv \
  sqlite3 \
  sudo

if ! command -v node >/dev/null 2>&1 || ! node --version | grep -qE "^v${NODE_MAJOR}\\."; then
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
  apt-get install -y nodejs
fi

if ! getent group "$APP_USER" >/dev/null 2>&1; then
  groupadd "$APP_USER"
fi

if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --create-home --home-dir "$APP_HOME" --gid "$APP_USER" --shell /bin/bash "$APP_USER"
fi

mkdir -p "$APP_DIR" "$ASSISTANT_SHARED_DIR"
chown -R "$APP_USER:$APP_USER" "$APP_DIR" "$ASSISTANT_SHARED_DIR"

if [ ! -d "$APP_DIR/.git" ]; then
  sudo -u "$APP_USER" git clone --branch "$BOT_GIT_BRANCH" "$BOT_REPO_URL" "$APP_DIR"
else
  sudo -u "$APP_USER" git config --global --add safe.directory "$APP_DIR" || true
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only origin "$BOT_GIT_BRANCH"
fi
sudo -u "$APP_USER" git config --global --add safe.directory "$APP_DIR" || true

sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" -m pip install -e "$APP_DIR"

if [ "$INSTALL_CLAUDE_CLI" = "1" ] && ! command -v claude >/dev/null 2>&1; then
  npm install -g @anthropic-ai/claude-code
fi

sudo -u "$APP_USER" \
  ASSISTANT_WHISPER_CPP_DIR="$ASSISTANT_SHARED_DIR/whisper.cpp" \
  bash "$APP_DIR/scripts/setup-shared-whisper-cpp-linux.sh" "$WHISPER_MODEL"

if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/deploy/env.vps.example" "$APP_DIR/.env"
  chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "Created $APP_DIR/.env. Fill secrets before starting the service."
fi

install -m 0644 "$APP_DIR/deploy/systemd/reminder-bot.service" /etc/systemd/system/reminder-bot.service
systemctl daemon-reload
systemctl enable reminder-bot.service

echo "Bootstrap complete."
echo "Next:"
echo "1. Edit $APP_DIR/.env"
echo "2. Authorize Claude CLI as $APP_USER if needed"
echo "3. Run: systemctl start reminder-bot.service"
