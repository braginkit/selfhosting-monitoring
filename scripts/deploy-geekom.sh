#!/usr/bin/env bash
set -euo pipefail
cd ~/monitoring

export GH_APP_ID="${GH_APP_ID:-3500273}"
export GH_APP_INSTALLATION_ID="${GH_APP_INSTALLATION_ID:-126991713}"
export GH_APP_PRIVATE_KEY_PATH="${GH_APP_PRIVATE_KEY_PATH:-$HOME/.config/selfhosting/gh-app-private-key.pem}"
scripts/ghcr-login-github-app.sh

IMAGE_TAG="${MONITOR_IMAGE_TAG:-v0.2.1}"
sed -i "s|ghcr.io/braginkit/selfhosting-monitoring:.*|ghcr.io/braginkit/selfhosting-monitoring:${IMAGE_TAG}|g" .env .env.base

if ! grep -q '^MONITOR_SMTP_DELIVERY_TRACKING_ENABLED=' .env.base; then
  cat >>.env.base <<'EOF'
MONITOR_SMTP_DELIVERY_TRACKING_ENABLED=true
MONITOR_SMTP_DELIVERY_GRACE_SECONDS=120
MONITOR_SMTP_DELIVERY_TIMEOUT_SECONDS=600
MONITOR_MAIL_LOG_DIR=/var/log/mail
EOF
fi

docker compose pull
docker compose up -d
docker compose ps
