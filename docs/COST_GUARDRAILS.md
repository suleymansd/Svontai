# SvontAI Cost Guardrails

This document records the production cost controls reviewed on 2026-07-21.

## Railway

- Railway bills running CPU, memory, volume storage and network egress even when request traffic is low.
- The production project currently uses separate API, worker, OpenWA, n8n, voice gateway, PostgreSQL and Redis services. Keep one replica per service until measured load requires more.
- In Railway, open **Workspace > Usage > Set Usage Limits**. Configure a compute email alert first, then a hard limit above the alert. Reaching the hard limit stops workloads.
- Review estimated usage weekly during the first month. Remove unused services and set per-service CPU/RAM replica limits where available.
- Keep internal service calls on Railway private networking to avoid public egress.

## Application Controls

- Incoming WhatsApp messages remain webhook driven; they do not poll.
- Integration diagnostics run every 15 minutes and persist all provider results in one database transaction per tenant.
- Google Calendar incremental synchronization runs every 10 minutes instead of every 2 minutes.
- OpenWA session health runs every 5 minutes. Failed reconnects use exponential backoff from 15 minutes up to 6 hours.
- Customer AI replies have a server-side 800-token output cap, a 30-second timeout and at most one provider retry.
- Tenant monthly message limits are enforced before n8n or direct AI reply generation.
- API, authentication, webhook, public chat, tool, media and test-call rate limits use Redis in production.
- Voice automation has tenant and platform-wide daily limits, a platform monthly limit, an allowed destination prefix list and a per-call duration cap. Production defaults are 50 calls/day, 500 calls/month, Turkey (`+90`) only and 300 seconds per call.
- Keep `VOICE_OUTBOUND_MODE=dry_run` except while live calling is intentionally sold. Configure `VOICE_GLOBAL_DAILY_CALL_LIMIT`, `VOICE_GLOBAL_MONTHLY_CALL_LIMIT`, `VOICE_MAX_CALL_DURATION_SECONDS` and `VOICE_ALLOWED_DESTINATION_PREFIXES` before enabling live mode.
- Artifact and database backup retention should remain finite; the default database backup retention is 30 days.

## Provider Limits

- Gemini/OpenAI: set a provider-side project budget or quota when the provider supports it. Never share a production key with a second project.
- Twilio: enable balance and usage trigger alerts. Restrict destination countries to markets actually served.
- Resend: monitor daily send volume and domain reputation; authentication and public form endpoints are rate limited in SvontAI.
- Google APIs: keep only required OAuth scopes and monitor Calendar API quota from Google Cloud.
- Cloudflare R2: keep buckets private and use lifecycle/retention rules for backups and generated artifacts.

## Incident Response

1. If usage spikes, disable the affected provider feature flag before rotating credentials.
2. Check Railway service metrics and SvontAI system events using the same time window.
3. Rotate a key immediately if requests cannot be tied to known tenants.
4. Preserve audit logs, then reduce the affected tenant entitlement or rate limit.
