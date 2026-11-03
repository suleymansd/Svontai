#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE=(docker compose --env-file "$ROOT/.env.oracle" -f "$ROOT/docker-compose.yml")

python3 "$ROOT/scripts/validate-env.py"
"${COMPOSE[@]}" config --quiet

failed=0
expected_services=(
  caddy frontend api worker voice-gateway postgres redis n8n n8n-runners openwa
)

for service in "${expected_services[@]}"; do
  container_id=$("${COMPOSE[@]}" ps -q "$service")
  if [[ -z "$container_id" ]]; then
    echo "[FAIL] $service: container is missing"
    failed=1
    continue
  fi

  state=$(docker inspect --format '{{.State.Status}}' "$container_id")
  if [[ "$state" != "running" ]]; then
    echo "[FAIL] $service: $state"
    failed=1
    continue
  fi

  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")
  if [[ "$health" != "none" && "$health" != "healthy" ]]; then
    echo "[FAIL] $service: health=$health"
    failed=1
  else
    echo "[OK] $service: running health=$health"
  fi
done

if ! "${COMPOSE[@]}" exec -T api alembic current | grep -q '(head)'; then
  echo "[FAIL] Alembic is not at migration head"
  failed=1
else
  echo "[OK] Alembic migration head"
fi

read_env() {
  sed -n "s/^$1=//p" "$ROOT/.env.oracle" | tail -n 1
}

frontend_url="https://$(read_env FRONTEND_DOMAIN)"
api_url="https://$(read_env API_DOMAIN)"
voice_url="https://$(read_env VOICE_DOMAIN)"
n8n_url="https://$(read_env N8N_DOMAIN)"

if [[ "${VERIFY_EXTERNAL:-true}" == "true" ]]; then
  curl -fsS "$frontend_url/" >/dev/null || { echo "[FAIL] Frontend HTTPS"; failed=1; }
  curl -fsS "$api_url/health/ready" >/dev/null || { echo "[FAIL] API readiness"; failed=1; }
  curl -fsS "$voice_url/health" >/dev/null || { echo "[FAIL] Voice Gateway health"; failed=1; }
  curl -fsS "$n8n_url/healthz" >/dev/null || { echo "[FAIL] n8n health"; failed=1; }
else
  echo "[SKIP] External HTTPS checks (VERIFY_EXTERNAL=false)"
fi

if ((failed)); then
  exit 1
fi

echo "Oracle stack verification passed."
