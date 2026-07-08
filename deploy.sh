#!/usr/bin/env bash
#
# Deploy the latest committed code to this server.
#
# Pulls the target branch, installs backend deps, runs migrations, collects
# static, rebuilds the frontend, restarts gunicorn, reloads nginx, then
# health-checks the API. Safe to re-run; aborts loudly on any failure.
#
# Run ON the EC2 box as root (via SSM Session Manager, or `aws ssm send-command`):
#   sudo bash /opt/vivid/app/deploy.sh
#
# Overridable via env: APP_DIR  APP_USER  SERVICE  BRANCH
#   e.g.  BRANCH=main sudo -E bash deploy.sh
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vivid/app}"
APP_USER="${APP_USER:-vivid_app}"
SERVICE="${SERVICE:-vivid}"
BRANCH="${BRANCH:-main}"

log() { printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

# App-owned steps (git, pip, npm, manage.py) run as $APP_USER so files keep the
# correct owner. Root-only steps (chown, systemctl) use sudo when not already root.
as_app()  { if [ "$(id -un)" = "$APP_USER" ]; then bash -lc "$1"; else sudo -u "$APP_USER" bash -lc "$1"; fi; }
as_root() { if [ "$(id -u)"  = "0" ];         then bash -c  "$1"; else sudo bash -c "$1"; fi; }

log "Deploying '$BRANCH' to $APP_DIR  (service: $SERVICE, user: $APP_USER)"

log "Fetching and fast-forwarding '$BRANCH'"
as_app "git -C '$APP_DIR' fetch origin '$BRANCH'"
as_app "git -C '$APP_DIR' pull --ff-only origin '$BRANCH'"
as_app "git -C '$APP_DIR' log --oneline -1"

log "Installing backend dependencies"
as_app "cd '$APP_DIR/backend' && venv/bin/pip install -q -r requirements.txt"

log "Applying database migrations"
as_app "cd '$APP_DIR/backend' && venv/bin/python manage.py migrate --noinput"

log "Collecting static files"
as_app "cd '$APP_DIR/backend' && venv/bin/python manage.py collectstatic --noinput"

log "Building the frontend"
# The frontend tree (incl. node_modules) must be owned by $APP_USER. The
# cloud-init bootstrap creates node_modules as root, which makes `vite build`
# fail with EACCES writing its temp config under node_modules/.vite-temp.
as_root "chown -R '$APP_USER:$APP_USER' '$APP_DIR/frontend'"
as_app "cd '$APP_DIR/frontend' && npm ci --no-audit --no-fund && npm run build"

log "Restarting $SERVICE"
as_root "systemctl restart '$SERVICE'"
sleep 3
if ! as_root "systemctl is-active --quiet '$SERVICE'"; then
  echo "!! $SERVICE failed to start — recent logs:"
  as_root "journalctl -u '$SERVICE' -n 40 --no-pager" || true
  exit 1
fi

log "Reloading nginx"
as_root "nginx -t"
as_root "systemctl reload nginx"

log "Health check"
code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/api/site/ || true)"
echo "GET /api/site/ -> $code"
[ "$code" = "200" ] || { echo "!! Health check failed"; exit 1; }

log "Deploy complete — now at $(as_app "git -C '$APP_DIR' rev-parse --short HEAD")"
