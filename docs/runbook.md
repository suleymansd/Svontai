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
