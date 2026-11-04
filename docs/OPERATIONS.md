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

## Quota unit

Pricing sells "AI yanıtı/ay" (`frontend/src/lib/public-plans.ts`); the backend meters
exactly that unit, and nothing else counts against it.

| Event | Reply quota (`messages_used_this_month`, `tenant_usage_counters.message_count`) | AI token budget |
| --- | --- | --- |
| Inbound customer message | none (stored only) | none |
| AI reply generated **and delivered** (text, or text + media answering the same inbound) | **1 unit**, charged once per inbound message (`reply_usage` on the inbound row, ledger key `ai_reply:<inbound id>`) | input + output tokens of the call |
| Inbound for a contact with AI disabled, paused or in human takeover | none (no reservation is made) | none (model is not called) |
| Operator-sent message (`/operator` outbox) | none | none |
| Reply attempt that fails before delivery or is refused by the daily AI budget | none (reservation released / marked `budget_exceeded`) | none |
| Delivery left uncertain (provider timeout) | reservation held until the operator resolves it as sent (1 unit) or not sent (0) | tokens already spent are counted |

Plan limits (`plans.message_limit`) are therefore "delivered AI replies per calendar
month (UTC)". `reserve_reply` holds a unit while a reply is in flight so parallel
workers cannot overspend; `tenant_usage_counters.extra_json` additionally records
`ai_input_tokens`, `ai_output_tokens`, `ai_calls` and the rolling `ai_tokens_today`
used by the daily AI budget (`AI_DAILY_TOKEN_BUDGET_PER_TENANT`,
`AI_DAILY_TOKEN_BUDGET_GLOBAL`). When a budget is reached the conversation is handed
to the operator queue and `SystemEvent AI_BUDGET_EXCEEDED` is logged once per tenant per day.
