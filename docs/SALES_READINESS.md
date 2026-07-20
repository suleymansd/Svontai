# SvontAI Sales Readiness

Last reviewed: 20 July 2026

## Launch scope

The first commercial release is concierge-first with optional self-service onboarding.
Customers provide minimum business information, connect WhatsApp by QR, and use the
simplified customer panel. SvontAI creates one protected Main Assistant, configures its expert
capabilities, checks integrations, runs
automations, records leads and appointments, retries recoverable failures, and reports
issues that require customer action.

## Ready in code

- Tenant-isolated registration, email verification, login, HttpOnly refresh cookie and RBAC.
- Self-service and concierge onboarding with idempotent autopilot setup.
- One protected Main Assistant per tenant with guided training; knowledge, lead qualification,
  appointment, human handoff and verified catalog sharing operate as capabilities behind it.
- Customer-safe navigation for status, bots, conversations, calls, leads, appointments and support.
- OpenWA inbound/outbound messaging, AI replies, lead/appointment extraction and signed webhooks.
- Schedule-aware natural AI replies, tenant working hours, service durations, conflict-safe availability and customer-confirmed appointment booking.
- n8n tenant-aware workflows with external task runners and worker-owned scheduled jobs.
- Manual plan request workflow; no unapproved or fake production upgrade.
- Redis-backed rate limiting, Sentry backend/frontend capture and readiness checks.
- Encrypted PostgreSQL backups with restore verification and private R2 upload.
- Private R2 artifact storage with tenant-scoped keys and short-lived signed downloads.
- CI gates for backend tests, dependency audit, frontend audit, lint, build and Playwright.
- Public/protected production smoke scripts and recurring GitHub uptime checks.

## Deliberately unavailable at launch

- Live phone calling: UI shows unavailable until a real Twilio account, number and explicit tenant permission exist.
- In-app card payment: sales and payment are handled manually until a legal entity and payment account are ready.
- Official Meta Embedded Signup: OpenWA QR is the launch path; Meta remains an optional verified-business alternative.
- Unreviewed marketplace tools: only capabilities marked production-ready should be customer-visible.

## External actions before the first paid customer

1. Deploy the release and confirm API `/health/ready`, Worker, OpenWA, n8n and n8n-runners are all healthy.
2. Scan a real WhatsApp QR and complete one no-charge inbound message test from another phone.
3. Save the tenant working plan, then confirm the reply, real slot selection, appointment event, notification and daily report.
4. Create a dedicated smoke customer and add its email/password to GitHub uptime secrets.
5. Attach the final custom domain and sender domain; repeat public smoke on those URLs.
6. Publish final privacy, terms, KVKK disclosure, OpenWA consent and commercial contract reviewed for the actual seller.
7. Establish a legally valid invoicing/sales process before accepting payment.
8. Keep Google OAuth optional until its production consent/publishing verification is complete.

## Release gate

A release is sellable only when all automated checks are green, the production database is
at Alembic head, the Worker has processed at least one current scheduled cycle, a backup has
passed restore verification, and the real WhatsApp acceptance test has passed. Missing external
credentials must appear as an actionable customer/admin state; they must never be represented as
a successful connection.
