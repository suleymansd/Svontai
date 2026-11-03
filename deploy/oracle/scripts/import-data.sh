#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BUNDLE=${1:-}
CONFIRM=${2:-}
COMPOSE=(docker compose --env-file "$ROOT/.env.oracle" -f "$ROOT/docker-compose.yml")

if [[ -z "$BUNDLE" || ! -d "$BUNDLE" || "$CONFIRM" != "--confirm-replace" ]]; then
  echo "Usage: $0 /absolute/path/to/migration-bundle --confirm-replace" >&2
  echo "This replaces the Oracle database and restored application volumes." >&2
  exit 1
fi

for file in database.dump openwa-data.tar.gz n8n-data.tar.gz legacy-artifacts.tar.gz SHA256SUMS; do
  [[ -f "$BUNDLE/$file" ]] || {
    echo "Missing migration file: $BUNDLE/$file" >&2
    exit 1
  }
done

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$BUNDLE" && sha256sum -c SHA256SUMS)
elif command -v shasum >/dev/null 2>&1; then
  (cd "$BUNDLE" && shasum -a 256 -c SHA256SUMS)
else
  echo "Missing required command: sha256sum or shasum" >&2
  exit 1
fi
python3 "$ROOT/scripts/validate-env.py"

POSTGRES_USER=$(sed -n 's/^POSTGRES_USER=//p' "$ROOT/.env.oracle" | tail -n 1)
POSTGRES_DB=$(sed -n 's/^POSTGRES_DB=//p' "$ROOT/.env.oracle" | tail -n 1)

echo "Stopping application writers before replacing production data..."
"${COMPOSE[@]}" stop api worker n8n n8n-runners openwa voice-gateway 2>/dev/null || true

echo "Starting only PostgreSQL for the initial restore..."
"${COMPOSE[@]}" up -d postgres
until "${COMPOSE[@]}" exec -T postgres pg_isready \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
  sleep 2
done

echo "Restoring PostgreSQL..."
"${COMPOSE[@]}" exec -T postgres dropdb \
  --if-exists --force --maintenance-db=postgres \
  --username "$POSTGRES_USER" "$POSTGRES_DB"
"${COMPOSE[@]}" exec -T postgres createdb \
  --maintenance-db=postgres --owner "$POSTGRES_USER" \
  --username "$POSTGRES_USER" "$POSTGRES_DB"
"${COMPOSE[@]}" exec -T postgres pg_restore \
  --exit-on-error --no-owner --no-privileges \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" <"$BUNDLE/database.dump"

echo "Restoring the OpenWA volume..."
docker volume create svontai-openwa-data >/dev/null
docker run --rm \
  -v svontai-openwa-data:/restore \
  -v "$BUNDLE:/backup:ro" \
  alpine:3.22 sh -c 'find /restore -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar -xzf /backup/openwa-data.tar.gz -C /restore'

echo "Restoring the n8n volume..."
docker volume create svontai-n8n-data >/dev/null
docker run --rm \
  -v svontai-n8n-data:/restore \
  -v "$BUNDLE:/backup:ro" \
  alpine:3.22 sh -c 'find /restore -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar -xzf /backup/n8n-data.tar.gz -C /restore && chown -R 1000:1000 /restore'

echo "Restoring legacy artifact files..."
docker volume create svontai-legacy-artifacts >/dev/null
docker run --rm \
  -v svontai-legacy-artifacts:/restore \
  -v "$BUNDLE:/backup:ro" \
  alpine:3.22 sh -c 'find /restore -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar -xzf /backup/legacy-artifacts.tar.gz -C /restore && chown -R 10001:10001 /restore'

echo "Building and starting the complete Oracle stack..."
"${COMPOSE[@]}" up -d --build

cat <<'EOF'
Restore completed. Do not change DNS and do not shut down Railway yet.
Run scripts/verify-stack.sh, then execute protected smoke and a live acceptance
test before the final maintenance-window database delta/cutover.
EOF
