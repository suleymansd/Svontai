# Reliability Release Status - Updated 14 October 2026

## Release Decision

The existing production release is reachable. The latest R2 backup passed an
independent download, authenticated-decryption and local restore test on 14 October.
The pending reliability and
private-demo changes are packaged on the working branch and remain undeployed.
They are not yet an approved production release. Passing local tests is not a guarantee of zero
defects or evidence of real provider acceptance.

Working branch: `codex/premium-demo-links`.
Base commit: `1ecd0bb5825ffbccacb9f6602af5997846ca1838`.
Current production migration: `055`. Pending repository head: `057`.

## Verified Production Evidence

Read-only checks on 14 October 2026:

| Check | Result |
| --- | --- |
| Railway project access | Restored after account reauthentication; all services reported online |
| Backend `/health/ready` | HTTP 200, `ready`, environment `prod` |
| Database and Redis readiness | Both reported `ok` |
| API and worker version | Both report the base commit above |
| Worker heartbeat | 2 seconds old during the readiness check |
| Migration | `055` |
| Frontend `/`, `/pricing`, `/tools`, `/security` | HTTP 200 at `https://www.svontai.com` |
| Frontend backend configuration | Points to `https://svontai-production.up.railway.app` |
| Protected API smoke | GitHub Production Uptime succeeded on 14 October, 08:11 Istanbul; fresh login and protected endpoints passed |

Evidence: [Production Uptime run](https://github.com/suleymansd/Svontai/actions/runs/38515296294).
This checks the existing release, not the pending `057` release. Its mostly empty
test tenant does not exercise real providers. The pending smoke additionally
requires exact API/worker commit alignment and functional pipeline health.
Do not retain a `055` migration override after deploying the new migration. Railway deployment status
alone is not evidence that WhatsApp, Google, n8n or voice workflows work end to end.

## Backup Evidence

Latest object independently checked on 14 October:

```text
postgres/2026/10/svontai-20261013T223751Z.dump.aes256gcm
Last modified: 2026-10-13T22:37:59.237000Z
Local time: 14 October 2026, 01:37 Europe/Istanbul
Age at verification: 37,436 seconds (under the 36-hour freshness limit)
Size: 11,228,098 bytes
SHA-256: 1a72c5f7618fcbd819d52a0088f7b817a3e4e35b5d1c4bab213d30f3a13b9b80
Restored migration: 055
```

Verification went beyond object metadata:

1. Listed the R2 objects and checked freshness, size and backup metadata.
2. Downloaded the latest stored object and compared its actual SHA-256.
3. Decrypted it and verified AES-256-GCM authentication.
4. Restored it with PostgreSQL 17 into a disposable local PostgreSQL cluster.
5. Verified migration `055` and the `tenants`, `users`, `messages` and
   `sales_inquiries` tables.
6. Stopped the temporary server and removed its data directory and downloaded
   encrypted/decrypted files.

The verification's PostgreSQL commands used a private local Unix socket and
separate credentials, never the production database connection. No production
database write, backup deletion, customer message or phone call was performed.
The local restore cluster used UTF-8, a private Unix socket and no TCP listener.
The run explicitly selected PostgreSQL 17 tools. A restore success proves this
snapshot can be restored with those tools; it does not prove
all application behavior after disaster recovery, nor future backup availability.

## Pending Code Changes

- Isolated Premium evaluation links with revocation, expiry, an atomic AI request
  budget and blocked external side effects. See [Private Demo Access](PRIVATE_DEMO_ACCESS.md).
- Tenant-serialized appointment writes, overlap rejection, UTC normalization and
  rejection of null values for required update fields.
- Server-owned booking proposals and explicit subsequent customer confirmation
  before appointment creation; deterministic Google event IDs for retry safety.
- Durable reply ownership and dispatch states, plus fenced webhook inbox leases
  and worker lease renewal. Ambiguous delivery is not blindly retried.
- Atomic usage increments and idempotent metering of delivered replies in the
  same database transaction as their recorded message.
- Shared AI rate limiting, bounded knowledge prompt content and bot-capacity checks.
- Latest-message previews without loading entire conversation relationships;
  bounded operator message windows and realtime reconnect invalidation.
- Recoverable web/mobile session errors that preserve credentials for transient
  failures; mobile request timeouts and session regression tests.
- Retention for old terminal webhook payloads and expired training sessions;
  isolation of per-tenant retention failures.
- Stronger stored-backup verification and restore cleanup, PostgreSQL regression
  testing in CI, dependency updates and automated dependency update configuration.
- Migration `057`: per-source reply reservations, tenant-subscription row locking,
  and a durable operator outbox with unique tenant/request identifiers. Failed
  generation releases reservations; ambiguous dispatch retains them until review.
- Operator sends persist intent before network I/O, recover queued work after a
  worker restart, and quarantine uncertain outcomes instead of resending. Web
  reconciliation requires explicit WhatsApp verification and records an audit event.
- Stale AI dispatch can be reconciled in the web conversation panel. Confirmed
  delivery is metered once; confirmed non-delivery releases quota and pauses AI.
  Prepared reply text is persisted, and unconfirmed operator intents are excluded
  from AI history. This is not a generic AI/media transactional outbox.
- Cursor-based web/mobile conversation history and bounded AI context; mobile
  FlatList virtualization, preserved drafts and stable send request IDs.
- Foreground-only authenticated native SSE, backoff, heartbeat watchdog and
  coalesced refresh; polling fallback when live streaming is unavailable. Redis
  leases cap tenant SSE connections across API instances (default 20).
- Public readiness exposes only payload-free pipeline status. External protected
  smoke fails on stale/dead-letter inbox work, blocked outbox or stalled AI replies;
  business failures do not force an API restart. Missing frontend API configuration
  fails the production build rather than producing an unusable page.

These changes have not modified historical usage, customer records or live
provider credentials. Publishing the working branch does not deploy or merge this
batch into `main`; production deployment remains gated by the checks below.

## Local Verification

Results recorded during this implementation session, before deployment:

| Check | Result |
| --- | --- |
| Full backend suite on SQLite | 324 passed, 4 environment-dependent tests skipped |
| PostgreSQL reliability, inbox, quota and outbox suite | 43 passed |
| Production-build Playwright, desktop and mobile viewports | 64 passed |
| Mobile unit/regression tests | 30 passed |
| Frontend lint and production build | Passed |
| Mobile lint, typecheck and iOS/Android Expo export | Passed |
| Frontend production dependency audit | 0 known vulnerabilities reported |
| Backend requirements audit | CI rerun required for this release; previous audit passed |
| Bandit medium/high gate | Passed; not a full penetration test |
| Root/backend requirements alignment and whitespace checks | Passed |
| Mobile production dependency audit | 19 high, 0 moderate, two root advisories; not passed |

The PostgreSQL suite uses actual Alembic migrations through `057`, concurrent
appointment collision and usage checks, plus 300 quota attempts across 100 synthetic
tenants using 12 local DB workers. Exactly one request per tenant was admitted with
a limit of one. This is database isolation evidence, not a 100-WhatsApp-session
capacity guarantee. A real Redis concurrent lease test is added to CI; local runs
skip it when an isolated Redis instance is unavailable. Browser tests mock backend and
provider responses; Expo export is not an IPA build or physical-device acceptance.
Audit counts are a point-in-time tool result, not a claim that unreported issues
do not exist.

Mobile security follow-up: published fixes now address the URI decoder, UUID and
development-only brace-expansion findings. Reproducible local patches and
regression tests mitigate the remaining braces/forge defects. The raw production
audit still lists 19 high findings from those two upstream advisories; its CI gate
has not been suppressed. See [Mobile Dependency Security](../mobile/SECURITY.md).

## Remaining Gates And Risks

1. Independently review the mobile braces/forge security backports and replace them
   with compatible official fixes when available. The raw audit gate remains open;
   no unrestricted release approval or new IPA is implied by passing regression tests.
2. Review this batch through a PR and pass all required checks. Main branch
   protection now requires `backend`, `frontend`, `mobile`, and `secrets`, with
   strict branch freshness. No bypass is authorized; the mobile audit is a blocker.
3. Deploy migrations `056` and `057` and matching API/worker revisions, then the compatible
   frontend. Repeat public and protected smoke checks against the release head.
4. With a dedicated consented test customer, exercise WhatsApp inbound -> one AI
   reply -> customer/appointment -> Google event, plus a consented voice booking.
   Verify failed provider paths and private-demo isolation/revocation live.
5. Complete a real capacity test before increasing the gateway session ceiling
   or promising support for 100 concurrent businesses.
6. Finish provider production approvals and review commercial/legal documents
   using the actual seller's identity and qualified professional advice.

Additional engineering debt still exists:

- The operator outbox and manual reconciliation do not provide exactly-once
  delivery. A generic AI/media outbox and provider-side idempotency are still absent.
- Inbound reply quota is reserved. Legacy/proactive automation sends without an
  inbound source are not covered by that reservation contract. Provider spend
  accounting is not a strict currency ledger or a provider billing hard cap.
- Per-tenant worker fairness and real gateway capacity need measured validation.
  Functional monitoring detects queued/stalled states, not a silent external
  provider malfunction with no recorded work. Provider acceptance remains mandatory.
- UI, splash and notes changes are preserved in this branch; build 5 predates the
  new history/SSE/outbox client work. A subsequent native build and physical-device
  acceptance are required. JavaScript export does not update installed applications.
- Google production approval and seller/legal verification remain external gates;
  do not label them complete from code tests. The R2 restore evidence above must
  be refreshed if the deployment is delayed beyond the freshness threshold.

## Deployment Safeguards

Take and verify a fresh backup before migration. Record the intended commit and
deploy it to both API and worker; do not deploy this dirty worktree directly.
After deployment, assert migration `057`, matching commit IDs, all pipeline health
signals `ok`, and fresh worker
heartbeat. Check provider behavior using test accounts, not unsolicited customer
messages or calls. For an application regression, prefer a compatible application
rollback; never restore an old database or downgrade migrations over customer
data without an explicit, reviewed recovery plan.
