# Environment Variables

## Backend (`backend/app/core/config.py`)
- `DATABASE_URL` (default: `sqlite:///./smartwa.db`)
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM` (production requires `HS256`)
- `API_KEY_HASH_SECRET` (production requires a separate random value of at least 32 characters)
- `SUPER_ADMIN_REQUIRE_2FA` (production requires `true`)
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `AI_PROVIDER` (`openai` | `gemini`, default: `openai`)
- `AI_MODEL` (optional shared model override)
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (default: `gemini-3.1-flash-lite`)
- `GEMINI_BASE_URL` (default: Google OpenAI-compatible API endpoint)
- `WHATSAPP_BASE_URL`
- `META_APP_ID`
- `META_APP_SECRET`
- `META_REDIRECT_URI`
- `META_CONFIG_ID`
- `GRAPH_API_VERSION`
- `OPENWA_ENABLED`
- `OPENWA_BASE_URL`
- `OPENWA_API_KEY`
- `OPENWA_WEBHOOK_SECRET`
- `OPENWA_WEBHOOK_PUBLIC_URL`
- `OPENWA_TIMEOUT_SECONDS`
- `WEBHOOK_PUBLIC_URL`
- `ENCRYPTION_KEY`
- `BACKEND_URL`
- `FRONTEND_URL`
- `EMAIL_ENABLED`
- `EMAIL_PROVIDER` (`resend` | `smtp`, default: `resend`)
- `RESEND_API_KEY`
- `RESEND_API_BASE_URL`
- `RESEND_TIMEOUT_SECONDS`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME`
- `SMTP_USE_TLS`
- `SMTP_USE_SSL`
- `SMTP_TIMEOUT_SECONDS`
- `PASSWORD_RESET_CODE_EXPIRE_MINUTES`
- `PASSWORD_RESET_MAX_ATTEMPTS`
- `ENVIRONMENT` (`dev` | `prod`)
- `REDIS_URL`
- `RATE_LIMIT_BACKEND` (`memory` | `redis`; production requires `redis`)
- `RATE_LIMIT_FAIL_CLOSED` (production requires `true`; rejects traffic if Redis protection is unavailable)
- `RATE_LIMIT_REDIS_PREFIX`
- `TRUSTED_PROXY_CIDRS` (only these immediate proxy networks may supply client IP forwarding headers)
- `SENTRY_DSN`
- `SENTRY_TRACES_SAMPLE_RATE`
- `INTEGRATION_DIAGNOSTICS_INTERVAL_SECONDS` (production minimum `300`, default `900`)
- `OPENWA_SESSION_HEALTH_INTERVAL_SECONDS` (production minimum `120`, default `300`)
- `OPENWA_RECONNECT_BASE_BACKOFF_SECONDS` (default `900`)
- `OPENWA_RECONNECT_MAX_BACKOFF_SECONDS` (default `21600`)
- `GOOGLE_CALENDAR_SYNC_INTERVAL_SECONDS` (production minimum `300`, default `600`)
- `AI_MAX_REPLY_TOKENS` (hard customer-reply output cap; default `800`)
- `AI_REQUEST_TIMEOUT_SECONDS` (provider timeout; default `30`)
- `AI_REQUEST_MAX_RETRIES` (provider retry cap; default `1`)
- `USE_N8N`
- `N8N_BASE_URL`
- `N8N_API_KEY`
- `SVONTAI_TO_N8N_SECRET`
- `N8N_TO_SVONTAI_SECRET`
- `N8N_ERROR_WEBHOOK_SECRET`
- `N8N_INCOMING_WORKFLOW_ID`
- `N8N_TIMEOUT_SECONDS`
- `N8N_RETRY_COUNT`
- `N8N_WEBHOOK_PATH`
- `VOICE_GATEWAY_TO_SVONTAI_SECRET`
- `VOICE_GATEWAY_PUBLIC_URL`
- `VOICE_OUTBOUND_MODE` (`dry_run` | `live`, default: `dry_run`)
- `VOICE_OUTBOUND_PROVIDER` (`twilio`)
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `VOICE_GLOBAL_DAILY_CALL_LIMIT` (default: `50`)
- `VOICE_GLOBAL_MONTHLY_CALL_LIMIT` (default: `500`)
- `VOICE_MAX_CALL_DURATION_SECONDS` (default: `300`)
- `VOICE_ALLOWED_DESTINATION_PREFIXES` (comma-separated E.164 prefixes, default: `+90`)
- `VOICE_ESTIMATED_COST_PER_MINUTE_USD` (Twilio kesin fiyatı oluşana kadar gösterilecek dakika tahmini, default: `0.03`)
- `BILLING_MODE` (`manual` | `stripe`, default: `manual`)
- `PAYMENTS_ENABLED`
- `SALES_CONTACT_EMAIL`
- `SALES_CONTACT_URL`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_IDS`
- `ARTIFACT_STORAGE_PROVIDER`
- `ARTIFACT_STORAGE_LOCAL_BASE_PATH`
- `RAILWAY_VOLUME_MOUNT_PATH`
- `ARTIFACT_MAX_FILE_SIZE_BYTES`
- `ARTIFACT_SIGNED_URL_EXPIRES_SECONDS`
- `ARTIFACT_SIGNING_SECRET`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET`
- `ARTIFACT_R2_ENDPOINT_URL`
- `ARTIFACT_R2_ACCESS_KEY_ID`
- `ARTIFACT_R2_SECRET_ACCESS_KEY`
- `ARTIFACT_R2_BUCKET`
- `ARTIFACT_R2_PREFIX`
- `DATABASE_BACKUP_ENABLED`
- `DATABASE_BACKUP_INTERVAL_SECONDS`
- `DATABASE_BACKUP_RETENTION_DAYS`
- `DATABASE_BACKUP_VERIFY_RESTORE`
- `DATABASE_BACKUP_ENCRYPTION_KEY_B64`
- `DATABASE_BACKUP_R2_ENDPOINT_URL`
- `DATABASE_BACKUP_R2_ACCESS_KEY_ID`
- `DATABASE_BACKUP_R2_SECRET_ACCESS_KEY`
- `DATABASE_BACKUP_R2_BUCKET`
- `DATABASE_BACKUP_R2_PREFIX`

`ARTIFACT_STORAGE_PROVIDER=local` yalnızca geliştirme içindir. Production için önerilen
değer `r2`'dır. R2 bucket private kalmalı, token yalnızca ilgili bucket üzerinde Object
Read & Write yetkisine sahip olmalı ve `ARTIFACT_R2_PREFIX=artifacts` kullanılmalıdır.
`railway_volume` mevcut tek-replica kayıtlarla geriye dönük uyumluluk için desteklenir;
birden fazla API replica için paylaşılan object storage zorunludur. Artifact indirme
bağlantıları iki aşamalı HMAC + provider imzasıyla kısa ömürlüdür ve cache kapalıdır.

Production database backups run inside the Railway worker and upload only
AES-256-GCM ciphertext to a private Cloudflare R2 bucket. Keep `r2.dev` public
access disabled and issue a bucket-scoped Object Read & Write token. Generate
`DATABASE_BACKUP_ENCRYPTION_KEY_B64` as 32 random bytes encoded with base64;
store it separately from R2 credentials and never rotate it before old backups
have expired or been re-encrypted.

## Production defaults
- `SERVICE_ROLE=api` web servisi için, `SERVICE_ROLE=worker` dedicated worker için zorunludur.
- `ENVIRONMENT=prod` rejects insecure default JWT, n8n and voice gateway secrets at startup.
- `USE_N8N` defaults to `false`; set `N8N_BASE_URL` explicitly for Railway/n8n deployments.
- `ALLOW_UNPAID_PLAN_UPGRADES` is forced off in production.
- `BILLING_MODE=manual` does not require Stripe and requires `PAYMENTS_ENABLED=false`. Customers create a plan request; admins activate the agreed plan from the tenant detail page.
- Webhook alias credentials are required: `WEBHOOK_USERNAME` and `WEBHOOK_PASSWORD`.
- Run `alembic upgrade head` before starting the API. Runtime schema compatibility patches are dev-only.

## Live external service wiring
- Meta WhatsApp:
  - Set `META_APP_ID`, `META_APP_SECRET`, `META_CONFIG_ID`, `META_REDIRECT_URI`, `WEBHOOK_PUBLIC_URL`, `BACKEND_URL`.
  - `META_REDIRECT_URI` must equal `<WEBHOOK_PUBLIC_URL>/api/onboarding/whatsapp/callback`.
  - Run `/api/onboarding/whatsapp/diagnostics?live=true` from an authenticated tenant session before sales demos.
- OpenWA QR:
  - Deploy OpenWA as a separate single-replica service with persistent `/app/data` storage.
  - Set `ENGINE_TYPE=baileys`, `API_MASTER_KEY`, `API_KEY_PEPPER`, `DATABASE_TYPE=sqlite`, `BAILEYS_AUTH_DIR=/app/data/baileys` and `AUTO_START_SESSIONS=true`.
  - Backend env: `OPENWA_ENABLED=true`, `OPENWA_BASE_URL`, `OPENWA_API_KEY`, `OPENWA_WEBHOOK_SECRET`, `OPENWA_WEBHOOK_PUBLIC_URL`.
  - `OPENWA_API_KEY` must equal OpenWA's `API_MASTER_KEY`.
  - `OPENWA_WEBHOOK_PUBLIC_URL` must be the public SmartWA backend URL.
- Manual billing (current launch mode):
  - Set `BILLING_MODE=manual`, `PAYMENTS_ENABLED=false`, `SALES_CONTACT_EMAIL` and `SALES_CONTACT_URL`.
  - Plan requests create an idempotent support ticket and system event. Complete the commercial agreement outside SmartWA, then activate the plan from the admin tenant page.
- Stripe (future):
  - Set `BILLING_MODE=stripe`, `PAYMENTS_ENABLED=true`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL`, `STRIPE_PORTAL_RETURN_URL`.
  - Set `STRIPE_PRICE_IDS`, for example `{"pro":{"monthly":"price_...","yearly":"price_..."},"premium":{"monthly":"price_...","yearly":"price_..."}}`.
  - Configure Stripe webhook target: `<BACKEND_URL>/billing/stripe/webhook`.
- Voice / Twilio:
  - Backend env: `VOICE_GATEWAY_TO_SVONTAI_SECRET`, `VOICE_GATEWAY_PUBLIC_URL`, `VOICE_OUTBOUND_MODE=live`, `VOICE_OUTBOUND_PROVIDER=twilio`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`.
  - Voice gateway env: `VOICE_GATEWAY_PUBLIC_URL`, `SVONTAI_BACKEND_URL`, `VOICE_GATEWAY_TO_SVONTAI_SECRET`, `TWILIO_AUTH_TOKEN`. The auth token is required for Twilio HTTP and ConversationRelay WebSocket signature validation.
  - Natural Turkish fallback: `TWILIO_TTS_VOICE=Google.tr-TR-Wavenet-D`, `TWILIO_GATHER_SPEECH_MODEL=googlev2_telephony_short`, `TWILIO_GATHER_SPEECH_TIMEOUT=1`.
  - Realtime conversation: complete Twilio ConversationRelay onboarding first, then set `TWILIO_VOICE_MODE=conversation_relay`. Optional tuning envs are documented in `backend/voice_gateway/.env.example`.
  - Twilio inbound number voice webhook: `<VOICE_GATEWAY_PUBLIC_URL>/twilio/voice/inbound`.
  - Outbound calls are created by the worker through Twilio Calls API and receive TwiML from `<VOICE_GATEWAY_PUBLIC_URL>/twilio/voice/outbound`.
- Admin smoke:
  - Use `SMARTWA_ADMIN_ACCESS_TOKEN` or `SMARTWA_ADMIN_EMAIL`/`SMARTWA_ADMIN_PASSWORD`.
  - `SMARTWA_SMOKE_TENANT_ID` is optional; if omitted, `scripts/admin_smoke.py` creates a disposable customer tenant.

## Autopilot / Agency APIs
- `GET /setup/autopilot/status`
- `POST /setup/autopilot/run`
- `GET /integrations/diagnostics`
- `POST /integrations/{provider}/repair`
- `GET /agency/clients`
- `POST /agency/clients`
- `GET /agency/clients/{tenant_id}/health`
- `PATCH /agency/clients/{relationship_id}`
- `DELETE /agency/clients/{relationship_id}`
- Agency read/write access is controlled by `agency:read` and `agency:write` RBAC permissions.

## Worker / Scheduler
- Railway should run both Procfile processes: `web` for API and `worker` for scheduled autonomy.
- Worker jobs persist lock/retry state in `scheduled_jobs`; this prevents duplicate runs across multiple worker instances.
- Current scheduled jobs: appointment reminders, real-estate automation, integration diagnostics, Google Calendar appointment sync, stuck automation run cleanup, outbound voice jobs, and daily/weekly operational reports.
- Current Alembic migration head: `046`.

## n8n execution capacity
- SmartWA uses shared, tenant-aware workflows. Do not duplicate a workflow for every customer.
- Recommended initial production settings for approximately 100 normal-traffic tenants:
  - `EXECUTIONS_TIMEOUT=120`
  - `EXECUTIONS_TIMEOUT_MAX=300`
  - `EXECUTIONS_DATA_SAVE_ON_ERROR=all`
  - `EXECUTIONS_DATA_SAVE_ON_SUCCESS=all`
  - `EXECUTIONS_DATA_SAVE_ON_PROGRESS=false`
  - `EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS=false`
  - `EXECUTIONS_DATA_PRUNE=true`
  - `EXECUTIONS_DATA_MAX_AGE=168`
  - `EXECUTIONS_DATA_PRUNE_MAX_COUNT=5000`
  - `N8N_CONCURRENCY_PRODUCTION_LIMIT=20`
  - `N8N_SECURE_COOKIE=true`
- Keep `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` while workflow signature verification reads `SVONTAI_TO_N8N_SECRET` from the n8n environment.
- Run `python scripts/install_n8n_error_workflow.py` with backend n8n envs to install the central error handler and attach it to production workflows.
- The n8n service must also receive `SVONTAI_BACKEND_URL` and the same `N8N_ERROR_WEBHOOK_SECRET` as the backend.
- Move n8n to queue mode with Redis and separate workers only when observed concurrent execution demand exceeds the regular-mode limit.

## OpenWA capacity
- `OPENWA_MAX_ACTIVE_SESSIONS` limits how many connected or connecting tenant sessions one gateway may own; default `75`.
- Setup and repair endpoints reject new sessions at the ceiling instead of overloading the gateway.
- Scale beyond the measured ceiling with another isolated gateway and persistent volume plus explicit tenant routing. Do not increase the limit without a load test.


## Rate limiting / Abuse protection
- Built-in API rate limits protect global IP traffic, auth/register/login/refresh, email verification, password reset, WhatsApp webhooks, public chat, public lead capture, assistant/tool execution and voice test-call endpoints.
- Production uses the Railway Redis service with `RATE_LIMIT_BACKEND=redis`; hashed keys and counters are shared across all API instances.
- In production, Redis failure closes the limiter and rejects protected traffic. Development may use the process-local fallback.
- In production, Meta webhook POST requests require a valid `X-Hub-Signature-256`; missing or invalid signatures are rejected.

## Production smoke
- Run `python scripts/prod_smoke.py` after Railway/Vercel deploys.
- Run `python scripts/integration_readiness.py --profile prod --role api` inside the Railway API service.
- Run `python scripts/integration_readiness.py --profile prod --role frontend` with Vercel public env values.
- For local files, use `python scripts/integration_readiness.py --env-file backend/.env --profile dev`.
- Required for public checks: `BACKEND_URL` and/or `FRONTEND_URL`.
- When both values are provided, the smoke test calls `FRONTEND_URL/api/frontend-config` and fails if the frontend is not configured to use the same backend URL.
- Protected checks prefer `SMARTWA_SMOKE_EMAIL` and `SMARTWA_SMOKE_PASSWORD`, which obtain a fresh access token on every run. `SMARTWA_SMOKE_TENANT_ID` is optional when the account has one tenant. The old `SMARTWA_SMOKE_ACCESS_TOKEN` remains a short-lived local fallback.
- Run `python scripts/user_journey_smoke.py` against staging/prod-like backend for a no-charge end-user journey smoke.
- `scripts/user_journey_smoke.py` creates a disposable user/tenant, completes onboarding, runs autopilot setup, and creates a dry-run voice test call intent/job. It does not send WhatsApp messages, charge Stripe or place real calls.
- Run `python scripts/admin_smoke.py` with `SMARTWA_ADMIN_ACCESS_TOKEN` or `SMARTWA_ADMIN_EMAIL`/`SMARTWA_ADMIN_PASSWORD` to verify concierge launch operations.

## Frontend (`frontend`)
- `NEXT_PUBLIC_BACKEND_URL` is required. There is no production-safe fallback.
- `NEXT_PUBLIC_SITE_URL` (used for sitemap/OG URLs)
- Local fallback file: `frontend/.env.local` currently points to `http://127.0.0.1:8001` because `8000` may be occupied by unrelated local services.
