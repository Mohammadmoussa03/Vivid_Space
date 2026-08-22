#!/usr/bin/env bash
#
# Deploy the latest committed code to this server.
#
# Pulls the target branch, installs backend deps, runs migrations, collects
# static, rebuilds the frontend, gracefully reloads gunicorn, reloads nginx,
# then health-checks the API. Safe to re-run; aborts loudly on any failure.
#
# Zero-downtime: the frontend is built into a staging directory and swapped in
# with a rename (never an empty dist/ that would 404 live visitors), and
# gunicorn is reloaded with SIGHUP — the master process keeps the listening
# socket open and cycles workers onto the new code, so no connection is
# refused. A restart (dropping requests for ~2s) is only the fallback when the
# service is not already running.
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

log "Building the frontend (into a staging dir, swapped in at the end)"
# The frontend tree (incl. node_modules) must be owned by $APP_USER. The
# cloud-init bootstrap creates node_modules as root, which makes `vite build`
# fail with EACCES writing its temp config under node_modules/.vite-temp.
as_root "chown -R '$APP_USER:$APP_USER' '$APP_DIR/frontend'"
# Build into dist.new: `vite build` empties its output dir first, so building
# straight into dist/ would leave nginx serving nothing for the ~20s of the
# build. A failed build also leaves the live dist/ untouched.
as_app "cd '$APP_DIR/frontend' && npm ci --no-audit --no-fund && npm run build -- --outDir dist.new --emptyOutDir"
[ -f "$APP_DIR/frontend/dist.new/index.html" ] || { echo "!! Build produced no dist.new/index.html"; exit 1; }

log "Publishing the new frontend build"
# Two renames on the same filesystem — the window where dist/ is absent is
# sub-millisecond, and nginx resolves the path per request.
as_app "cd '$APP_DIR/frontend' && rm -rf dist.old && { [ -d dist ] && mv dist dist.old || true; } && mv dist.new dist"

log "Reloading $SERVICE (graceful, no dropped requests)"
# gunicorn reloads on SIGHUP: the master keeps the socket bound and replaces
# its workers with ones running the new code. Ensure the unit knows how, in
# case the box predates ExecReload (drop-in, so the base unit stays as shipped).
if ! as_root "systemctl show '$SERVICE' -p ExecReload --value | grep -q ."; then
  log "Installing ExecReload drop-in for $SERVICE"
  as_root "mkdir -p /etc/systemd/system/$SERVICE.service.d"
  as_root "{ echo '[Service]'; echo 'ExecReload=/bin/kill -s HUP \$MAINPID'; echo 'KillMode=mixed'; } > /etc/systemd/system/$SERVICE.service.d/reload.conf"
  as_root "systemctl daemon-reload"
fi
if as_root "systemctl is-active --quiet '$SERVICE'"; then
  as_root "systemctl reload '$SERVICE'"
else
  # Not running (first deploy, or it crashed) — nothing to keep alive.
  log "$SERVICE was not running; starting it"
  as_root "systemctl start '$SERVICE'"
fi
sleep 3
if ! as_root "systemctl is-active --quiet '$SERVICE'"; then
  echo "!! $SERVICE is not active — recent logs:"
  as_root "journalctl -u '$SERVICE' -n 40 --no-pager" || true
  exit 1
fi

log "Reloading nginx"
as_root "nginx -t"
as_root "systemctl reload nginx"

log "Health check"
# nginx routes on server_name, so once a real domain is configured a request to
# a bare 127.0.0.1 lands on the catch-all and 404s even though the site is fine.
# Ask for the site *by name* over the loopback instead. Falls back to the raw IP
# in test mode, where every server block is the catch-all (`server_name _`).
# `|| true` keeps a failing `nginx -T` from tripping `set -e` here — an
# undiscoverable hostname should fall back, not abort a finished deploy.
HEALTH_HOST="${HEALTH_HOST:-$({ as_root "nginx -T 2>/dev/null" || true; } \
  | awk '$1=="server_name" { gsub(/;/,"",$2); if ($2 != "_") { print $2; exit } }')}"
HEALTH_HOST="${HEALTH_HOST:-127.0.0.1}"
# Prod redirects HTTP→HTTPS, so try TLS first (-k: the cert is for the domain,
# not the loopback IP); test mode has no TLS listener and answers on plain HTTP.
code="$(curl -sk -o /dev/null -w '%{http_code}' -H "Host: $HEALTH_HOST" \
  https://127.0.0.1/api/site/ 2>/dev/null || true)"
if [ "$code" != "200" ]; then
  code="$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $HEALTH_HOST" \
    http://127.0.0.1/api/site/ || true)"
fi
echo "GET /api/site/ (Host: $HEALTH_HOST) -> $code"
if [ "$code" != "200" ]; then
  echo "!! Health check failed. The previous frontend build is still on disk:"
  echo "   cd $APP_DIR/frontend && rm -rf dist && mv dist.old dist"
  echo "   git -C $APP_DIR reset --hard HEAD~1 && sudo bash $APP_DIR/deploy.sh   # full roll back"
  as_root "journalctl -u '$SERVICE' -n 40 --no-pager" || true
  exit 1
fi

log "Deploy complete — now at $(as_app "git -C '$APP_DIR' rev-parse --short HEAD")"
