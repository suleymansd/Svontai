#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE=(docker compose --env-file "$ROOT/.env.oracle" -f "$ROOT/docker-compose.yml" --profile maintenance)
VERIFY_VOLUME=svontai-restic-restore-verification

cleanup() {
  docker volume rm -f "$VERIFY_VOLUME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

python3 "$ROOT/scripts/validate-env.py"
cleanup
docker volume create "$VERIFY_VOLUME" >/dev/null

echo "Restoring the latest encrypted volume snapshot into an isolated test volume..."
"${COMPOSE[@]}" run --rm \
  --volume "$VERIFY_VOLUME:/restore" \
  volume-backup restore latest --target /restore

docker run --rm \
  -v "$VERIFY_VOLUME:/restore:ro" \
  alpine:3.22 sh -eu -c '
    test -d /restore/data/openwa
    test -d /restore/data/n8n
    test -d /restore/data/legacy-artifacts
    find /restore/data -type f -print -quit | grep -q .
  '

echo "Encrypted R2 volume restore verification passed. Production volumes were not changed."
