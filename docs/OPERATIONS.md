# Operations

Owner-run procedures that are intentionally **not** automated from CI (they need
repository admin rights or external accounts). Day-to-day incident handling lives
in `docs/runbook.md`.

## Branch protection

`main` is protected but, as of audit item A21, only `backend` and `frontend` were
required status checks. CI also runs `mobile` and `secrets`; both must gate merges.
Nothing in the repository changes protection automatically; the owner runs this once
with a token that has `administration:write` on `suleymansd/Svontai`.

Update only the required checks (keeps every other protection setting as is):

```sh
gh api -X PATCH repos/suleymansd/Svontai/branches/main/protection/required_status_checks \
  -F strict=true \
  -f 'contexts[]=backend' \
  -f 'contexts[]=frontend' \
  -f 'contexts[]=mobile' \
  -f 'contexts[]=secrets'
```

If the endpoint returns 404 (protection not yet created through the REST API, or a
ruleset is used instead), set the whole protection object in one call:

```sh
gh api -X PUT repos/suleymansd/Svontai/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["backend", "frontend", "mobile", "secrets"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
```

Verify:

```sh
gh api repos/suleymansd/Svontai/branches/main/protection/required_status_checks --jq '.contexts'
# expected: ["backend","frontend","mobile","secrets"]
```

The context names are the CI job ids in `.github/workflows/ci.yml` (`secrets`,
`backend`, `frontend`, `mobile`). Renaming a job requires re-running the command.

## External uptime monitor

`.github/workflows/uptime.yml` runs on a 15-minute cron and opens/updates an issue
labelled `incident` when it fails, but **GitHub scheduled workflows are best-effort**:
during load, intervals routinely stretch to an hour or more and runs are skipped
entirely. Treat it as a secondary alarm and point an external monitor (UptimeRobot,
Better Stack, Checkly, Pingdom, ... free tiers are enough) at production.

| Setting | Value |
| --- | --- |
| URL | `https://svontai-production.up.railway.app/health/ready` |
| Method | `GET`, no auth, 20 s timeout |
| Interval | 1 minute |
| Alert on | HTTP status other than `200` for 2 consecutive checks |
| Keyword check (optional) | body contains `"worker":"ok"` and `"status":"ready"` |

Expected body (abridged):

```json
{
  "status": "ready",
  "environment": "prod",
  "components": {"database": "ok", "redis": "ok", "worker": "ok"},
  "deployment": {
    "api_commit": "<sha>",
    "worker_commit": "<sha>",
    "worker_heartbeat_age_seconds": 12,
    "worker_heartbeat_max_age_seconds": 300,
    "migration_heads": ["<head>"],
    "pipeline_health": {"webhook_inbox": "ok", "operator_outbox": "ok", "ai_delivery": "ok"}
  }
}
```

The endpoint returns `503` with `"status": "not_ready"` when the database or Redis is
unavailable, when `components.worker` is `stale` (heartbeat older than
`WORKER_HEARTBEAT_MAX_AGE_SECONDS`, default 300 s; the worker beats every 30 s), or
when it is `missing` in production (no worker has ever registered). Set the variable
to `0` on the API service to make the worker fields informational only.

Note: Railway's deploy health check also uses `/health/ready` (see `docs/runbook.md`).
A stopped worker therefore blocks new API deploys until the worker is back; that is
intentional (the product is not serving customers without it), but if you need to
ship an API hotfix during a worker outage, temporarily set
`WORKER_HEARTBEAT_MAX_AGE_SECONDS=0` on the API service.

Also monitor `https://www.svontai.com/api/frontend-config` (expect `200`) with the
same interval, and route both alerts to a channel someone actually reads (Slack or
SMS), not only e-mail.

## Backup and restore drill

Audit A24 asked for proof that a backup can actually be restored somewhere other
than the server that produced it. The code path is `DatabaseBackupService`
(`backend/app/services/database_backup_service.py`); the drill tooling is
`scripts/restore_drill.py` and `.github/workflows/backup-drill.yml`.

### Where backups live

All names below are environment variable names (see
`deploy/oracle/.env.oracle.example`); the values are secrets and are not in git.

| What | Where | Produced by |
| --- | --- | --- |
| PostgreSQL dumps (`pg_dump --format=custom`, AES-256-GCM, `.dump.aes256gcm`) | R2 bucket `DATABASE_BACKUP_R2_BUCKET`, key prefix `DATABASE_BACKUP_R2_PREFIX/` (default `postgres/`) | Worker scheduled job, every `DATABASE_BACKUP_INTERVAL_SECONDS` (daily), retention `DATABASE_BACKUP_RETENTION_DAYS` (30) |
| OpenWA sessions, n8n data, legacy artifacts (restic repository) | Same bucket, path `oracle-volumes/`, repository password `RESTIC_PASSWORD` | `deploy/oracle/scripts/backup-volumes.sh`, systemd timer nightly at 03:35 Europe/Istanbul |
| Customer artifacts | R2 bucket `ARTIFACT_R2_BUCKET` (prefix `ARTIFACT_R2_PREFIX`) | Written directly by the app; **not** covered by either backup job, relies on R2 durability |

Every dump object carries `sha256`, `encryption`, `backup-format`,
`restore-verified` and migration-head metadata. The dump key is
`DATABASE_BACKUP_ENCRYPTION_KEY_B64`: it must be kept in a separate vault (password
manager entry shared with at least two people), never in R2 and never rotated
without re-encrypting or expiring the old objects. Losing it loses every backup.

### Running the drill by hand

Needs `pg_restore`/`psql` of the same major as the server that produced the dump
(production is PostgreSQL 17) and a scratch PostgreSQL server you are allowed to
create and drop databases on. The drill never writes to the database named in the
URL; it creates `svontai_drill_<timestamp>` next to it and drops it afterwards.

1. Fetch the newest object (any S3 client works against R2), for example:

   ```sh
   aws --endpoint-url "$DATABASE_BACKUP_R2_ENDPOINT_URL" s3 ls "s3://$DATABASE_BACKUP_R2_BUCKET/postgres/" --recursive | sort | tail -1
   aws --endpoint-url "$DATABASE_BACKUP_R2_ENDPOINT_URL" s3 cp "s3://$DATABASE_BACKUP_R2_BUCKET/<key>" ./database.dump.aes256gcm
   ```

2. Restore and report (the key may also be passed with `--encryption-key-b64`):

   ```sh
   DATABASE_BACKUP_ENCRYPTION_KEY_B64=... backend/.venv/bin/python scripts/restore_drill.py restore \
     ./database.dump.aes256gcm \
     --database-url postgresql+psycopg://user:pass@127.0.0.1:5432/postgres \
     --min-messages 1 --result-json drill-result.json
   ```

   Output is one JSON line with `counts` for `tenants`, `users`, `messages`,
   `appointments`, `newest_message_at`, `migration_heads`, `restore_seconds` (your
   measured RTO for the database part) and `ok`. Exit code is non-zero when the
   archive cannot be decrypted, `pg_restore` fails, a critical table is missing, or
   the counts are below the `--min-*` thresholds (default: at least one tenant and
   one user). Hosts other than `127.0.0.1`/`localhost` are refused unless
   `--allow-remote` is passed.

3. Alternatively, on the worker host with production settings loaded,
   `python scripts/verify_production_backup.py --restore-latest` downloads the
   newest object, checks its checksum and metadata and restore-tests it in a
   disposable database on the production server (same server, so it proves the
   archive but not an independent recovery path).

To rehearse end to end without production data (what CI does):

```sh
backend/.venv/bin/python scripts/restore_drill.py seed --database-url "$SOURCE_URL" --messages 25
DATABASE_URL="$SOURCE_URL" DATABASE_BACKUP_ENCRYPTION_KEY_B64="$KEY" \
  backend/.venv/bin/python scripts/restore_drill.py create-archive --output drill/database.dump.aes256gcm
DATABASE_BACKUP_ENCRYPTION_KEY_B64="$KEY" \
  backend/.venv/bin/python scripts/restore_drill.py restore drill/database.dump.aes256gcm --database-url "$SCRATCH_URL" --min-messages 25
```

### Scheduled drill in CI

`.github/workflows/backup-drill.yml` runs every Monday 04:30 UTC and on
`workflow_dispatch`. In one job it migrates and seeds a Postgres 17 service,
produces an encrypted archive through `DatabaseBackupService`, restores it with
`restore_drill.py` and uploads the manifest and result JSON as the
`backup-drill-<run id>` artifact (90 days). It needs one repository secret:

- `BACKUP_DRILL_ENCRYPTION_KEY_B64`: a throw-away 32-byte key, base64 encoded
  (`python3 -c 'import os,base64;print(base64.b64encode(os.urandom(32)).decode())'`).
  **Never** reuse the production `DATABASE_BACKUP_ENCRYPTION_KEY_B64` here.

When the secret is absent the job prints a `::notice::` and exits green so that
forks and fresh clones do not fail; check the run log, not only the badge. The
workflow restores a CI-seeded archive, so it proves the tooling and format, not
the contents of a production object; the monthly checklist covers that.

### Monthly checklist (owner, ~20 minutes)

1. Run `python scripts/verify_production_backup.py` on the worker host (or read
   the latest R2 object's `LastModified`): the newest dump must be younger than
   36 hours and carry `restore-verified=true`.
2. Download that object to a machine that is not the production host and run
   `scripts/restore_drill.py restore` against a scratch PostgreSQL 17. Record
   `restore_seconds`, `counts` and `newest_message_at` in the ops log; the newest
   message must be from the backup day.
3. Run `deploy/oracle/scripts/verify-volume-restore.sh` on the host for the
   restic snapshots (OpenWA sessions and n8n data).
4. Confirm the last `Backup Restore Drill` workflow run is green and recent (the
   schedule is best-effort; dispatch it manually if it was skipped).
5. Open the vault entry for `DATABASE_BACKUP_ENCRYPTION_KEY_B64` and
   `RESTIC_PASSWORD` and confirm two people can still read it.
6. Note any drift from the targets: RPO 24 h (daily dump), RTO 60 min for the
   database (measured `restore_seconds` plus redeploy), owner: platform owner.
