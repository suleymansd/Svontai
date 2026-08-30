#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DEST=${1:-"$ROOT/migration/$(date -u +%Y%m%dT%H%M%SZ)"}
MODE=${2:-}

if [[ -n "$MODE" && "$MODE" != "--final-cutover" ]]; then
  echo "Usage: $0 [destination] [--final-cutover]" >&2
  exit 1
fi

FINAL_CUTOVER=false
[[ "$MODE" == "--final-cutover" ]] && FINAL_CUTOVER=true

API_SERVICE=${RAILWAY_API_SERVICE:-Svontai}
WORKER_SERVICE=${RAILWAY_WORKER_SERVICE:-Worker}
VOICE_SERVICE=${RAILWAY_VOICE_SERVICE:-Voice-Gateway}
OPENWA_SERVICE=${RAILWAY_OPENWA_SERVICE:-OpenWA}
N8N_SERVICE=${RAILWAY_N8N_SERVICE:-n8n}
N8N_RUNNERS_SERVICE=${RAILWAY_N8N_RUNNERS_SERVICE:-n8n-runners}
stopped_services=()
stopped_service_count=0
cutover_export_complete=false

restore_stopped_services_on_failure() {
  if [[ "$FINAL_CUTOVER" == "true" && "$cutover_export_complete" != "true" ]]; then
    if ((stopped_service_count > 0)); then
      echo "Final export failed; redeploying stopped Railway services..." >&2
      for service in "${stopped_services[@]}"; do
        railway redeploy --service "$service" --yes >/dev/null 2>&1 || true
      done
    fi
  fi
}
trap restore_stopped_services_on_failure EXIT

for command in railway docker gzip; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required command: $command" >&2
    exit 1
  }
done

umask 077
if [[ -d "$DEST" && -n "$(find "$DEST" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo "Refusing to overwrite non-empty migration directory: $DEST" >&2
  exit 1
fi
mkdir -p "$DEST"

export_paused_node_volume() {
  local service=$1
  local source_path=$2
  local destination=$3

  railway ssh --service "$service" sh -c '
    set -eu
    node_pid=$(pgrep -o -f "[n]ode")
    test -n "$node_pid"
    resume_node() { kill -CONT "$node_pid" >/dev/null 2>&1 || true; }
    trap resume_node EXIT HUP INT TERM
    kill -STOP "$node_pid"
    tar -C "$1" -czf - .
  ' sh "$source_path" >"$destination"
}

stop_writer() {
  local service=$1
  stopped_services+=("$service")
  stopped_service_count=$((stopped_service_count + 1))
  railway down --service "$service" --yes
}

echo "Exporting a process-consistent OpenWA persistent volume..."
export_paused_node_volume "$OPENWA_SERVICE" /app/data "$DEST/openwa-data.tar.gz"
gzip -t "$DEST/openwa-data.tar.gz"
if [[ "$FINAL_CUTOVER" == "true" ]]; then
  stop_writer "$OPENWA_SERVICE"
fi

echo "Exporting a process-consistent n8n persistent volume..."
export_paused_node_volume "$N8N_SERVICE" /home/node/.n8n "$DEST/n8n-data.tar.gz"
gzip -t "$DEST/n8n-data.tar.gz"
if [[ "$FINAL_CUTOVER" == "true" ]]; then
  stop_writer "$N8N_RUNNERS_SERVICE"
  stop_writer "$N8N_SERVICE"
fi

echo "Exporting legacy backend artifacts..."
railway ssh --service "$API_SERVICE" tar -C /app/backend/storage -czf - . >"$DEST/legacy-artifacts.tar.gz"
gzip -t "$DEST/legacy-artifacts.tar.gz"

if [[ "$FINAL_CUTOVER" == "true" ]]; then
  stop_writer "$VOICE_SERVICE"
  stop_writer "$WORKER_SERVICE"
  stop_writer "$API_SERVICE"
fi

echo "Exporting the Railway PostgreSQL database..."
railway run --service Postgres --no-local docker run --rm -i \
  -e DATABASE_PUBLIC_URL \
  postgres:17-alpine \
  sh -c 'exec pg_dump --dbname="$DATABASE_PUBLIC_URL" --format=custom --compress=9 --no-owner --no-privileges' \
  >"$DEST/database.dump"
docker run --rm -i postgres:17-alpine pg_restore --list \
  <"$DEST/database.dump" >/dev/null

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$DEST" && sha256sum database.dump openwa-data.tar.gz n8n-data.tar.gz legacy-artifacts.tar.gz >SHA256SUMS)
elif command -v shasum >/dev/null 2>&1; then
  (cd "$DEST" && shasum -a 256 database.dump openwa-data.tar.gz n8n-data.tar.gz legacy-artifacts.tar.gz >SHA256SUMS)
else
  echo "Missing required command: sha256sum or shasum" >&2
  exit 1
fi

cutover_export_complete=true

cat <<EOF
Migration bundle created at:
  $DEST

This bundle contains production data. Keep it encrypted at rest, transfer it
only over SSH, and delete it after Oracle restore and R2 backup verification.
Railway variables and application secrets were intentionally not exported.
EOF

if [[ "$FINAL_CUTOVER" == "true" ]]; then
  cat <<EOF

Final-cutover mode completed. Railway writer deployments are offline and their
volumes remain intact. Restore this bundle on Oracle now. If cutover is aborted,
redeploy these services before accepting traffic again:
  ${stopped_services[*]}
EOF
fi
