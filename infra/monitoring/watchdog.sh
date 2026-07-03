#!/usr/bin/env bash
# Health watchdog: runs every 5 minutes via cron, alerts over Signal on
# healthy<->unhealthy transitions only (not every failed check, to avoid
# paging every 5 minutes for the duration of an outage). See
# docs/adr/0014-phase6c-monitoring-alerting.md.
set -uo pipefail

REPO_DIR="/opt/collabrains"
STATE_FILE="/opt/collabrains-monitoring-state"
LOCK_FILE="/tmp/collabrains-watchdog.lock"
PUBLIC_URL="https://v78281.1blu.de/health"
INTERNAL_URL="http://127.0.0.1:8000/health/ready"
DISK_THRESHOLD_PCT=90

exec 9>"$LOCK_FILE"
flock -n 9 || { echo "[$(date -Iseconds)] previous run still in progress, skipping"; exit 0; }

cd "$REPO_DIR"
source .env

failures=()

# 1. every currently-running compose service should still be running
while read -r svc state; do
  [ -z "$svc" ] && continue
  if [ "$state" != "running" ]; then
    failures+=("container not running: $svc ($state)")
  fi
done < <(docker compose ps -a --format '{{.Service}} {{.State}}' 2>/dev/null)

# 2. internal health (DB connectivity, direct to the API)
if ! curl -fsS --max-time 10 "$INTERNAL_URL" >/dev/null 2>&1; then
  failures+=("internal /health/ready check failed")
fi

# 3. public health (TLS + Caddy routing + API, the path a real user hits)
if ! curl -fsS --max-time 10 "$PUBLIC_URL" >/dev/null 2>&1; then
  failures+=("public HTTPS /health check failed")
fi

# 4. disk usage
disk_pct="$(df --output=pcent / | tail -1 | tr -dc '0-9')"
if [ -n "$disk_pct" ] && [ "$disk_pct" -ge "$DISK_THRESHOLD_PCT" ]; then
  failures+=("disk usage at ${disk_pct}% (threshold ${DISK_THRESHOLD_PCT}%)")
fi

previous_status="unknown"
[ -f "$STATE_FILE" ] && previous_status="$(cat "$STATE_FILE")"

send_alert() {
  local text="$1"
  curl -fsS --max-time 10 -X POST "http://127.0.0.1:8011/v2/send" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "import json,sys; print(json.dumps({'message': sys.argv[1], 'number': sys.argv[2], 'recipients': [sys.argv[3]]}))" "$text" "$SIGNAL_PHONE_NUMBER" "$ALERT_PHONE_NUMBER")" \
    >/dev/null 2>&1 || echo "[$(date -Iseconds)] WARNING: failed to send Signal alert"
}

if [ "${#failures[@]}" -gt 0 ]; then
  echo "[$(date -Iseconds)] UNHEALTHY: ${failures[*]}"
  if [ "$previous_status" != "unhealthy" ]; then
    send_alert "CollaBrains ALERT: unhealthy since $(date -Iseconds)
$(printf '%s\n' "${failures[@]}")"
  fi
  echo "unhealthy" > "$STATE_FILE"
else
  echo "[$(date -Iseconds)] healthy"
  if [ "$previous_status" = "unhealthy" ]; then
    send_alert "CollaBrains RECOVERED: all checks passing again as of $(date -Iseconds)"
  fi
  echo "healthy" > "$STATE_FILE"
fi
