#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE=(docker compose --env-file "$ROOT/.env.oracle" -f "$ROOT/docker-compose.yml" --profile maintenance)

python3 "$ROOT/scripts/validate-env.py"

if ! "${COMPOSE[@]}" run --rm volume-backup snapshots >/dev/null 2>&1; then
  echo "Initializing encrypted Restic repository..."
  "${COMPOSE[@]}" run --rm volume-backup init
fi

"${COMPOSE[@]}" run --rm volume-backup backup \
  --host svontai-oracle \
  --tag scheduled \
  /data/openwa /data/n8n /data/legacy-artifacts

"${COMPOSE[@]}" run --rm volume-backup forget \
  --host svontai-oracle \
  --keep-daily 7 \
  --keep-weekly 5 \
  --keep-monthly 6 \
  --prune

"${COMPOSE[@]}" run --rm volume-backup check --read-data-subset=5%
