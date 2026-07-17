#!/usr/bin/env bash
# Put the test box into (or out of) load-test mode. Idempotent.
#   configure-box.sh loadtest  -> DEBUG off, throttles lifted, demo data seeded
#   configure-box.sh restore   -> put back the pre-loadtest .env
set -euo pipefail

ENV_FILE=/opt/vivid/app/backend/.env
BAK=/opt/vivid/app/backend/.env.pre-loadtest.bak
MANAGE="/opt/vivid/app/backend/venv/bin/python /opt/vivid/app/backend/manage.py"

set_kv() { # set_kv KEY VALUE — replace in place, or append if absent
  local k=$1 v=$2
  if grep -qE "^${k}=" "$ENV_FILE"; then
    sed -i -E "s|^${k}=.*|${k}=${v}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$k" "$v" >> "$ENV_FILE"
  fi
}

case "${1:-}" in
  loadtest)
    [ -f "$BAK" ] || cp "$ENV_FILE" "$BAK"
    echo "==> backed up .env -> $BAK"

    # Production-like app config, minus the things that need real TLS.
    set_kv DJANGO_DEBUG False
    set_kv SECURE_SSL_REDIRECT False     # box is HTTP-only; DEBUG=False would 301 everything
    set_kv AUTH_COOKIE_SECURE False      # else JWT cookies never come back over HTTP
    set_kv SECURE_HSTS_SECONDS 0
    set_kv DJANGO_ALLOWED_HOSTS '35.157.5.65,127.0.0.1,localhost'

    # Lift rate limits so we measure the app, not the throttle.
    set_kv THROTTLE_ANON 1000000/min
    set_kv THROTTLE_USER 1000000/min
    set_kv THROTTLE_LOGIN 1000000/min
    set_kv THROTTLE_LOGIN_ACCOUNT 1000000/hour
    set_kv THROTTLE_REGISTER 1000000/min
    set_kv THROTTLE_PASSWORD_RESET 1000000/min
    echo "==> throttles lifted, DEBUG=False"

    chown vivid_app:vivid_app "$ENV_FILE"
    sudo -u vivid_app $MANAGE seed_demo 2>&1 | tail -3
    echo "==> demo data seeded"
    ;;

  restore)
    [ -f "$BAK" ] || { echo "no backup at $BAK" >&2; exit 1; }
    cp "$BAK" "$ENV_FILE"
    chown vivid_app:vivid_app "$ENV_FILE"
    echo "==> restored .env from backup"
    ;;

  *) echo "usage: $0 {loadtest|restore}" >&2; exit 1 ;;
esac

systemctl restart vivid
sleep 3
systemctl is-active vivid
echo "==> health:"
curl -s -o /dev/null -w "  GET / -> %{http_code}\n" http://127.0.0.1/
curl -s -o /dev/null -w "  GET /api/site/ -> %{http_code}\n" http://127.0.0.1/api/site/
curl -s -w "  spaces: %{http_code}\n" -o /tmp/sp.json http://127.0.0.1/api/spaces/ && head -c 120 /tmp/sp.json && echo
echo "==> effective flags:"
grep -E "^(DJANGO_DEBUG|SECURE_SSL_REDIRECT|AUTH_COOKIE_SECURE|THROTTLE_ANON)=" "$ENV_FILE" | sed 's/^/  /'
