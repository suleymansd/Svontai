# SvontAI Runbook (Ops + Support)

## Scope
This runbook covers incident triage, error center usage, and common failure paths for WhatsApp + n8n integrations.

## Access
- Admin panel: `/admin`
- Error Center: `/admin/incidents` + `/admin/events`
- Customer Errors page: `/dashboard/errors`
- Tickets: `/admin/tickets`

## Severity Guide
- **sev1**: Production outage, inbound/outbound messaging blocked, widespread auth failures.
- **sev2**: Partial outage, major automation failures, elevated error spikes.
- **sev3**: Single-tenant issues, degraded performance.
- **sev4**: Minor defects, UX or cosmetic issues.

## Incident Workflow
1) **Detect**: Check `system_events` spike and dashboard “Today’s failures.”
2) **Triage**: Open incident, assign owner, capture root cause hypothesis.
3) **Mitigate**: Apply temporary fix or toggle feature flag.
4) **Resolve**: Confirm error rate returns to baseline.
5) **Postmortem**: Add notes + preventive action.

## Error Center Triage Steps
1) Filter by **tenant** and **code**.
2) Inspect `meta_json` for correlation ID and payload context.
3) Open related **automation_run** and **ticket** if available.
4) Create incident if the same code spikes across tenants.

## Common Failure Modes
### WhatsApp Inbound
- **Symptoms**: No inbound events, no new automation runs.
- **Checks**:
  - Meta webhook verification status.
  - `system_events` codes: `META_WEBHOOK_VERIFY_FAIL`, `META_WEBHOOK_TIMEOUT`.
  - Ensure `phone_number_id` and `waba_id` are active.

### WhatsApp Outbound
- **Symptoms**: Messages not delivered.
- **Checks**:
  - `system_events` codes: `META_SEND_FAIL`, `META_TOKEN_EXPIRED`.
  - Verify access token refresh and rate limit responses.

### n8n Down / Timeout
- **Symptoms**: Runs stuck in `running` or `timeout`.
- **Checks**:
  - `system_events` codes: `N8N_TRIGGER_FAIL`, `N8N_TIMEOUT`.
  - Validate `N8N_BASE_URL`, token secrets, and network access.

### Plan / Limit Exceeded
- **Symptoms**: UI shows “limit reached,” no new messages/bots.
- **Checks**:
  - `system_events` codes: `MESSAGE_LIMIT_EXCEEDED`, `BOT_LIMIT_EXCEEDED`.
  - Confirm tenant plan limits and usage counters.

## Ticket Response Workflow
1) Review ticket context (tenant, priority, last activity).
2) Check Error Center for correlated events.
3) Reply to customer with steps and expected ETA.
4) Update ticket status to `pending` or `solved`.

## Audit + Security Checks
- Verify all sensitive operations appear in `/admin/audit`.
- Validate role permissions on any unauthorized action reports.
- Confirm account lockouts for repeated failed logins.

## Recovery Checklist
- Restart services (API, worker, frontend) if required.
- Clear stuck automation runs and mark failed with reason.
- Add incident notes and a follow-up task.

## Prod-like Release Smoke
Use this flow after Railway/Vercel deploys and before a sales demo.

### No-charge automated checks
- Public smoke:
  - `BACKEND_URL=https://<railway-api> FRONTEND_URL=https://<vercel-app> python scripts/prod_smoke.py`
  - This also checks `FRONTEND_URL/api/frontend-config` so a Vercel build pointing at the wrong backend fails immediately.
- Protected smoke:
  - Add `SMARTWA_SMOKE_ACCESS_TOKEN` and `SMARTWA_SMOKE_TENANT_ID`.
  - Re-run `python scripts/prod_smoke.py`.
  - This checks customer-safe endpoints including onboarding, autopilot, integrations, voice settings, intents, jobs, calls, bots, leads, and appointments.
- End-user journey smoke:
  - `BACKEND_URL=https://<railway-api> python scripts/user_journey_smoke.py`
  - This creates a disposable smoke user and tenant, completes guided onboarding, runs autopilot setup, and creates a voice test-call intent/job.
  - It does not send WhatsApp messages, charge Stripe, or place real phone calls.
- Admin launch smoke:
  - `BACKEND_URL=https://<railway-api> SMARTWA_ADMIN_ACCESS_TOKEN=<token> SMARTWA_SMOKE_TENANT_ID=<tenant> python scripts/admin_smoke.py`
  - This checks launch board access, concierge status update, admin business profile enrichment and admin-triggered autopilot.
  - It does not launch external WhatsApp, payment, or real phone-call actions.

### Deployment checks
- Railway web service command must run `alembic upgrade head` before API start.
- Railway worker service must run `python -m app.worker`.
- Railway web service must set `SERVICE_ROLE=api`; worker must set `SERVICE_ROLE=worker`.
- Railway web service must set `RUN_SCHEDULED_JOBS_IN_WEB=false`; the worker owns scheduled jobs.
- Railway backend must mount a persistent volume and use `ARTIFACT_STORAGE_PROVIDER=railway_volume`; local ephemeral storage is forbidden in production.
- Artifact volume paths use private directory/file permissions (`0700`/`0600`) and signed download URLs should expire in 300 seconds.
- Vercel `NEXT_PUBLIC_BACKEND_URL` must point to the Railway API domain.
- Frontend builds must fail or smoke must fail if `NEXT_PUBLIC_BACKEND_URL` is missing; do not rely on `localhost:8000` defaults.
- Alembic head must include revision `041`.

## Database backup and restore

- The Railway worker creates a PostgreSQL custom-format dump over the private network. The dump is catalog-checked, encrypted with AES-256-GCM, decrypted, checksum-verified, and restored into a randomly named temporary database before upload.
- Railway currently builds from the repository root with Railpack. Keep `boto3` in the root `requirements.txt` and Mise `postgres=17` in `railpack.json`; the worker must have PostgreSQL 17 `pg_dump`, `pg_restore`, `psql`, `createdb`, and `dropdb` at runtime.
- Only the authenticated ciphertext is uploaded to the private Cloudflare R2 bucket. Keep public `r2.dev` access disabled and restrict the API token to Object Read & Write on the backup bucket only.
- The worker verifies the uploaded object size and SHA-256 metadata. Backups older than `DATABASE_BACKUP_RETENTION_DAYS` are removed automatically; production defaults to 30 days.
- The restore test checks the Alembic heads and critical tables, then force-deletes only the randomly named temporary restore database. It never restores over the active production database.
- Backup failures are persisted by the scheduled-job retry policy and reported to Sentry. The worker retries with exponential backoff without creating concurrent dumps.
- Keep `DATABASE_BACKUP_ENCRYPTION_KEY_B64` outside R2 and retain it for the full lifetime of every encrypted backup. Losing this key makes all backups unrecoverable.
- Railway native daily, weekly, and monthly backups should be enabled as a second independent layer if the project is upgraded to Pro.
- Do not store production database URLs, dump contents, R2 credentials, or encryption keys in GitHub Actions, issues, chat, or unencrypted artifacts.
- Production startup must fail if JWT, n8n, or voice gateway secrets use insecure defaults.
- `WEBHOOK_USERNAME`, `WEBHOOK_PASSWORD`, `JWT_SECRET_KEY`, `SVONTAI_TO_N8N_SECRET`, `N8N_TO_SVONTAI_SECRET`, `N8N_ERROR_WEBHOOK_SECRET`, and `VOICE_GATEWAY_TO_SVONTAI_SECRET` must be real secret values.

## Manual Customer UI Smoke
Run this as a real customer after automated smoke passes.

1. Register a new user.
2. Complete email verification and login.
3. Create a tenant.
4. Confirm onboarding starts instead of opening the full dashboard directly.
5. Choose either `Biz Kuralım` or `Hızlı Kurulum`.
6. Answer industry, customer goal, tone, and handoff questions.
7. Leave website, Instagram, and business summary empty; confirm the flow still continues.
8. Skip or postpone WhatsApp connection.
9. Run SmartWA setup and confirm the customer dashboard opens.
10. Verify simplified customer navigation: Ana Panel, Sistem Durumu, Botlarım, Mesajlar, Aramalar, Müşteriler, Destek.
11. Open Botlarım and confirm the customer can customize their bot.
12. Open Aramalar and toggle AI Arama Asistanı settings.
13. Create a test call intent and confirm the call appears in the calls area without placing a real call.
14. As admin, open `/admin/launch`, set a concierge customer to in progress, enrich profile, run autopilot and mark launched.
15. Check mobile width for obvious text overflow or blocked controls.
