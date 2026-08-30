# SvontAI Oracle Always Free Production

This package runs the complete production application on one Oracle Ampere A1
VM without removing product capabilities:

- Next.js frontend
- FastAPI API
- dedicated autonomous worker
- PostgreSQL 17
- Redis
- n8n 2.30.7 with its matching external task runner
- OpenWA 0.10.0 with persistent session storage
- Voice Gateway
- Caddy automatic HTTPS reverse proxy

Private Cloudflare R2 buckets remain external because they are the off-server,
encrypted disaster-recovery copy. Vercel and Railway remain untouched only
during the rollback window, then can be disconnected.

No application feature is removed by this deployment. The free single-node
stage deliberately limits OpenWA to 10 concurrently active WhatsApp sessions
and n8n to 8 concurrent production executions so one customer cannot exhaust
the VM. Reaching those limits is the signal to move the busy service or the
whole stack to paid capacity; this VM is not a 100-active-tenant target.

## Required VM

- Oracle `VM.Standard.A1.Flex` (ARM64)
- Ubuntu 24.04
- 2 OCPU / 12 GB RAM
- at least 100 GB boot volume
- a reserved public IPv4 address

Do not choose the 1 GB AMD micro instance; it cannot run this stack safely.

## Cost and reliability boundary

Oracle currently keeps a [Free Tier tenancy](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm)
at no charge when the total Ampere A1 allocation stays at or below 2 OCPU and
12 GB RAM. Capacity can be
temporarily unavailable, Free Tier has community support only, and one VM is a
single failure domain. This package therefore keeps off-server encrypted
backups and an explicit rollback procedure; it does not claim the same
availability as a paid multi-node platform.

The VM itself can remain free, but the domain and external providers are
separate. Twilio calls are usage-priced, and R2 becomes billable above its
[monthly Standard-tier allowance](https://developers.cloudflare.com/r2/pricing/).
The application retains the existing voice
limits, while Restic uses incremental snapshots and retention pruning to keep
backup growth bounded. Review Oracle and R2 usage dashboards monthly even when
the invoice is zero.

## Security boundary

Only TCP 80/443 and restricted administrator SSH are public. PostgreSQL, Redis,
OpenWA, n8n's runner broker, API container ports, and Voice container ports are
private Docker-network services. Caddy is the only public ingress.

## Preparation

1. Add Oracle VCN ingress rules for TCP 80/443 and SSH from your own IP only.
2. Clone the repository on the VM under `/opt/svontai`.
3. Run `sudo deploy/oracle/scripts/bootstrap-host.sh`.
4. Allow SSH from your own IP with UFW, then enable UFW as printed by the script.
5. Run:

   ```bash
   cd /opt/svontai/deploy/oracle
   python3 scripts/generate-secrets.py
   chmod 600 .env.oracle
   ```

6. From the Railway-linked administrator checkout, securely import matching
   values without printing them, then fill any Vercel-only or unresolved
   placeholders manually:

   ```bash
   python3 scripts/import-railway-secrets.py
   ```

   The script never replaces the new Oracle PostgreSQL, Redis, or Restic
   passwords. Preserve existing application/provider secrets unchanged. In
   particular, preserve:
   `JWT_SECRET_KEY`, `API_KEY_HASH_SECRET`, `ENCRYPTION_KEY`,
   `N8N_ENCRYPTION_KEY`, all n8n shared secrets, OpenWA secrets,
   `ARTIFACT_SIGNING_SECRET`, `DATABASE_BACKUP_ENCRYPTION_KEY_B64`, and the
   Voice Gateway shared secret. Rotating these during migration breaks stored
   tokens, API keys, n8n credentials, backups, or webhook signatures.
7. Run `python3 scripts/validate-env.py`.
8. Run `sudo scripts/install-ops-timers.sh` to schedule encrypted OpenWA, n8n,
   and legacy-volume backups to R2.
9. Create the n8n owner account with a unique password and enable n8n two-factor
   authentication before exposing `automation.svontai.com`.

## Data copy rehearsal

From the current administrator Mac, while Railway remains live:

```bash
cd deploy/oracle
./scripts/export-railway-data.sh
scp -r migration/<timestamp> ubuntu@ORACLE_IP:/opt/svontai/deploy/oracle/migration/
```

On Oracle:

```bash
cd /opt/svontai/deploy/oracle
./scripts/import-data.sh /opt/svontai/deploy/oracle/migration/<timestamp> --confirm-replace
VERIFY_EXTERNAL=false ./scripts/verify-stack.sh
```

The export includes the complete shared PostgreSQL database, OpenWA session
volume, n8n state/binary-data volume, and legacy artifact volume. R2 objects
remain in R2 and are not copied. OpenWA and n8n are paused only for the seconds
needed to create their consistent volume archives and are resumed by a shell
trap even if archiving fails.

Before the final window, confirm the Railway service names. Defaults are
`Svontai`, `Worker`, `Voice-Gateway`, `OpenWA`, `n8n`, and `n8n-runners`; they
can be overridden with the corresponding `RAILWAY_*_SERVICE` environment
variables used by `export-railway-data.sh`.

## DNS and provider callbacks

Create DNS A records pointing to the reserved Oracle IP:

- `svontai.com`
- `www.svontai.com`
- `api.svontai.com`
- `voice.svontai.com`
- `automation.svontai.com`

Point them directly to the Oracle IP without an HTTP proxy until Caddy obtains
certificates. During rehearsal, leave `svontai.com` and `www.svontai.com` on
Vercel; switch those two only in the
final maintenance window. Vercel's `NEXT_PUBLIC_BACKEND_URL` only needs to be
updated when using Vercel as the rehearsal or rollback frontend. Then update:

- Vercel `NEXT_PUBLIC_BACKEND_URL=https://api.svontai.com`
- Google callback to
  `https://api.svontai.com/real-estate/calendar/google/callback`
- Meta callback to
  `https://api.svontai.com/api/onboarding/whatsapp/callback`
- Twilio inbound/outbound/status callbacks to `https://voice.svontai.com`

## Final cutover

The rehearsal copy is not the final production cut. During a scheduled window:

1. Announce a short maintenance window and create a fresh encrypted R2 backup.
2. Run `./scripts/export-railway-data.sh migration/final --final-cutover` from
   the linked administrator Mac. It archives OpenWA/n8n consistently, stops
   only Railway writer deployments, and then takes the final PostgreSQL dump.
   On export failure it automatically redeploys anything it stopped. It never
   deletes the PostgreSQL service or any Railway volume.
3. Transfer and import this final bundle with `--confirm-replace`.
4. Start the Oracle stack and run `verify-stack.sh`.
5. Run `scripts/prod_smoke.py` and the protected smoke account.
6. Test one real WhatsApp message, AI reply, appointment, n8n execution, and
   authorized Twilio call.
7. Switch all five public DNS records to Oracle. Vercel remains available as a
   rollback target but no longer serves production traffic.
8. Observe Oracle and Railway in parallel for 48 hours.
9. Stop Railway services only after logs, counts, callbacks, R2 backups, and
   customer acceptance are confirmed.

Never delete Railway volumes or the original database during the rollback
window. A rollback after Oracle accepts writes requires a fresh Oracle database
export back into Railway before DNS is reversed; simply changing DNS would lose
the writes received after cutover.

## Backup verification

The worker continues creating encrypted PostgreSQL backups in R2. The systemd
timer separately snapshots OpenWA sessions, n8n state/binary files, and legacy
artifacts with Restic encryption. Test it before cutover:

```bash
./scripts/backup-volumes.sh
docker compose --env-file .env.oracle -f docker-compose.yml --profile maintenance \
  run --rm volume-backup snapshots
./scripts/verify-volume-restore.sh
```

The restore verifier decrypts the latest R2 snapshot into a disposable Docker
volume, checks the restored OpenWA, n8n, and artifact trees, and deletes only
that disposable volume. It never mounts or replaces production volumes.

Keep `RESTIC_PASSWORD` outside Oracle as well. Losing both the VM and this
password makes those volume snapshots unrecoverable.
