# Reliability Release Status - 12 October 2026

## Release Decision

The existing production release is reachable and its latest stored database
backup has passed an independent restore test. The pending reliability and
private-demo changes are packaged on the working branch and remain undeployed.
They are not yet an approved production release. Passing local tests is not a guarantee of zero
defects or evidence of real provider acceptance.

Working branch: `codex/premium-demo-links`.
Base commit: `1ecd0bb5825ffbccacb9f6602af5997846ca1838`.
Current production migration: `055`. Pending repository head: `056`.

## Verified Production Evidence

Read-only checks on 12 October 2026:

| Check | Result |
| --- | --- |
| Railway project access | Restored; correct production project is linked |
| Backend `/health/ready` | HTTP 200, `ready`, environment `prod` |
| Database and Redis readiness | Both reported `ok` |
| API and worker version | Both report the base commit above |
| Worker heartbeat | 20 seconds old during the final smoke check |
| Migration | `055` |
| Frontend `/`, `/pricing`, `/tools`, `/security` | HTTP 200 at `https://www.svontai.com` |
| Frontend backend configuration | Points to `https://svontai-production.up.railway.app` |
| Protected API smoke | Not run in this verification pass; credentials were not supplied |

The public smoke explicitly used `SMARTWA_EXPECTED_MIGRATION_HEAD=055` to check
the existing release, not to approve the pending `056` release. Do not retain
that override after deploying the new migration. Railway deployment status
alone is not evidence that WhatsApp, Google, n8n or voice workflows work end to end.

## Backup Evidence

Latest object checked:

```text
postgres/2026/10/svontai-20261011T223723Z.dump.aes256gcm
Last modified: 2026-10-11T22:37:32.259000Z
Local time: 12 October 2026, 01:37 Europe/Istanbul
Size: 10,656,837 bytes
SHA-256: 2081aab6ba24ced809c8656f40141c699d9c3a5eb4c0decf843af412a0e92cb6
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
Worker logs also record successful daily backup/restore checks from 5-11 October.

An initial local attempt selected an older `pg_restore` and rejected archive
format 1.16. The successful run explicitly selected PostgreSQL 17 tools. A restore
success proves this snapshot can be restored with those tools; it does not prove
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

These changes have not modified historical usage, customer records or live
provider credentials. Publishing the working branch does not deploy or merge this
batch into `main`; production deployment remains gated by the checks below.

## Local Verification

Results recorded during this implementation session, before deployment:

| Check | Result |
| --- | --- |
| Full backend suite on SQLite | 292 passed, 1 skipped |
| PostgreSQL reliability and inbox suite | 23 passed |
| Production-build Playwright, desktop and mobile viewports | 56 passed |
| Mobile session unit tests | 6 passed |
| Frontend lint and production build | Passed |
| Mobile lint, typecheck and iOS/Android Expo export | Passed |
| Frontend production dependency audit | 0 known vulnerabilities reported |
| Backend requirements audit | No known vulnerabilities reported |
| Bandit medium/high gate | No medium/high findings; 15 low findings remain |
| Root/backend requirements alignment and whitespace checks | Passed |
| Mobile production dependency audit | 19 high, 11 moderate; not passed |

The PostgreSQL suite uses actual Alembic migrations and includes concurrent
appointment collision and usage increment checks. Browser tests mock backend and
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
2. Review this batch through a PR and require all intended CI checks.
   Branch protection was not changed. Verify that automatic deployments cannot
   bypass the release gate.
3. Deploy migration `056` and matching API/worker revisions, then the compatible
   frontend. Repeat public and protected smoke checks against the release head.
4. With a dedicated consented test customer, exercise WhatsApp inbound -> one AI
   reply -> customer/appointment -> Google event, plus a consented voice booking.
   Verify failed provider paths and private-demo isolation/revocation live.
5. Complete a real capacity test before increasing the gateway session ceiling
   or promising support for 100 concurrent businesses.
6. Finish provider production approvals and review commercial/legal documents
   using the actual seller's identity and qualified professional advice.

Additional engineering debt still exists:

- Ambiguous provider delivery needs an operator reconciliation workflow and a
  complete transactional outbox; duplicate protection is not exactly-once delivery.
- Message quota checks do not reserve in-flight requests. Concurrent requests near
  a limit can exceed it. Provider spend accounting is not a strict cost ledger.
- Deep conversation detail/AI history reads and some list endpoints still need
  bounded database queries; the mobile older-message navigation is unfinished.
- Per-tenant workload fairness, realtime connection limits and independent
  functional uptime alerting require further work and measured validation.
- The newer mobile feature branch must be reconciled before publishing a build;
  this worktree must not overwrite its unmerged UI, splash or notes work.

## Deployment Safeguards

Take and verify a fresh backup before migration. Record the intended commit and
deploy it to both API and worker; do not deploy this dirty worktree directly.
After deployment, assert migration `056`, matching commit IDs and fresh worker
heartbeat. Check provider behavior using test accounts, not unsolicited customer
messages or calls. For an application regression, prefer a compatible application
rollback; never restore an old database or downgrade migrations over customer
data without an explicit, reviewed recovery plan.
