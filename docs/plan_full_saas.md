# SvontAI Full SaaS Plan (Enterprise Build)

Status date: 2026-01-30
Owner: Codex

## Assumptions (based on scan)
- Frontend: Next.js app router (`frontend/src/app`), Tailwind + shadcn/ui
- Auth: JWT stored in localStorage (`frontend/src/lib/api.ts`)
- Backend: FastAPI, SQLAlchemy, RBAC with roles/permissions
- Multi-tenant: `tenant_id` on most models, `TenantMembership` for role scoping
- Audit logs: `audit_logs` table in `backend/app/models/onboarding.py`
- Automation runs: `automation_runs` model exists

If any assumption is wrong, update this plan before implementing.

## Phase Order (must follow)
1) system_events + incidents models + logging capture points
2) Admin dashboard + tenants + error center
3) Plans/tools management pages
4) Customer Errors + Usage pages
5) Landing + pricing + features + use-cases
6) Polish + tests + docs

---

## Phase 0 — Repo Scan + Single Source of Truth
- [x] Confirm frontend routes: `frontend/src/app`
- [x] Confirm backend routers/services/models
- [x] Confirm auth storage: localStorage
- [x] Confirm RBAC: `backend/app/services/rbac_service.py`
- [x] Confirm audit logs: `backend/app/models/onboarding.py` + `AuditLogService`

Docs to produce (existing from prior step):
- [x] `/docs/architecture.md` (update if needed)
- [x] `/docs/modules.md`
- [x] `/docs/env_vars.md`

---

## Phase 1 — System Events + Incidents (Observability Core)

### Backend
- [x] Add models:
  - `backend/app/models/system_event.py`
  - `backend/app/models/incident.py`
- [x] Add schemas:
  - `backend/app/schemas/system_event.py`
  - `backend/app/schemas/incident.py`
- [x] Add services:
  - `backend/app/services/system_event_service.py`
  - `backend/app/services/incident_service.py`
- [x] Add routers:
  - `backend/app/api/routers/system_events.py`
  - `backend/app/api/routers/incidents.py`
- [x] Wire routers in `backend/app/api/routers/__init__.py`
- [x] Migration: `backend/alembic/versions/008_add_system_events_incidents.py`

### Logging capture points
- [x] WhatsApp inbound processing: `backend/app/api/routers/whatsapp_webhook.py`
- [x] n8n trigger failures: `backend/app/services/n8n_client.py`
- [x] outbound send failures: `backend/app/services/whatsapp_service.py` / `meta_api.py`
- [x] auth failures: `backend/app/api/routers/auth.py`
- [ ] KYC submission/review: `backend/app/api/routers/onboarding.py`
- [x] plan/limit exceed: `backend/app/services/subscription_service.py`

### Correlation ID
- [x] Generate `correlation_id` per inbound message
- [x] Pass into n8n payload
- [x] Store on automation_runs + system_events

---

## Phase 2 — Admin Dashboard + Tenants + Error Center

### Admin (internal ops)
- [x] Admin dashboard KPIs + failure list
  - `frontend/src/app/admin/page.tsx`
- [x] Tenants list + detail
  - `frontend/src/app/admin/tenants/page.tsx`
  - `frontend/src/app/admin/tenants/[tenantId]/page.tsx`
- [x] Incidents / Error Center
  - `frontend/src/app/admin/incidents/page.tsx`
- [x] Incidents detail view
  - `frontend/src/app/admin/incidents/[incidentId]/page.tsx`
- [x] Audit logs view
  - `frontend/src/app/admin/audit/page.tsx`

### Backend endpoints
- [x] Admin dashboard stats endpoint
  - `backend/app/api/routers/admin.py`
- [x] Tenants detail endpoint + feature toggles
- [x] Incidents CRUD + triage endpoints
- [x] Audit log list with pagination

---

## Phase 3 — Plans & Tools Management

### Backend
- [x] Plans CRUD endpoints
  - `backend/app/api/routers/admin.py` or `plans.py`
- [x] Tools CRUD endpoints
  - add model: `backend/app/models/tool.py`
  - add endpoints: `backend/app/api/routers/admin.py`
- [x] Feature flags for new modules

### Frontend
- [x] Plans management
  - `frontend/src/app/admin/plans/page.tsx`
- [x] Tools management
  - `frontend/src/app/admin/tools/page.tsx`

---

## Phase 4 — Customer Portal (Errors + Usage)

### Frontend
- [x] Customer Errors page
  - `frontend/src/app/dashboard/errors/page.tsx`
- [x] Usage page
  - `frontend/src/app/dashboard/usage/page.tsx`
- [x] Ticket creation from error (prefilled)

### Tickets (Customer + Admin)
- [x] Ticket models + API
  - `backend/app/models/ticket.py`
  - `backend/app/api/routers/tickets.py`
- [x] Customer ticket list/detail UI
  - `frontend/src/app/dashboard/tickets/page.tsx`
  - `frontend/src/app/dashboard/tickets/[ticketId]/page.tsx`
- [x] Admin ticket list/detail UI
  - `frontend/src/app/admin/tickets/page.tsx`
  - `frontend/src/app/admin/tickets/[ticketId]/page.tsx`

### Backend
- [x] Tenant-scoped system_events list
- [x] Usage data aggregation (messages/runs/seats)
- [x] Incident auto-open on error spikes

---

## Phase 5 — Landing Page + Marketing

Routes
- [x] `/`
- [x] `/pricing`
- [x] `/features`
- [x] `/use-cases/[segment]`
- [x] `/security`
- [x] `/contact`
- [x] `/docs` (public)

Tasks
- [x] Motion (Intersection Observer reveals)
- [x] SEO metadata + OG + sitemap
- [x] Demo preview components

---

## Phase 6 — Security & Performance

### Security
- [ ] RBAC checks server-side everywhere
- [x] Rate limits on auth
- [x] Account lockout
- [ ] Prevent IDOR with tenant filters
- [x] Security headers in Next.js

### Performance
- [x] Server pagination for all lists
- [x] DB indexes for high-volume tables
- [ ] Avoid N+1 queries

---

## Phase 7 — Tests, Seed, Docs

### Tests
- [x] Auth + RBAC
- [x] Tool entitlement checks
- [x] Ticket creation + reply
- [x] n8n callback auth verification
- [x] Event logging pipeline

### Seed
- [x] Demo tenant, demo user, demo staff
- [x] Demo tools + events

### Docs
- [x] `/docs/runbook.md`
- [x] `/docs/landing.md`
- [x] `/docs/api.md`

---

## Notes
- No commits will be created unless explicitly requested.
- Implementation will be incremental; each module must include loading/empty/error states and dark mode polish.
- Motion uses IntersectionObserver-based reveals; Framer Motion is not added to dependencies.
- RBAC enforced on onboarding, WhatsApp integration, and subscription endpoints; full audit remains pending.
- RBAC added to analytics and operator endpoints; remaining audit still pending.
- RBAC added to knowledge base endpoints (list/create/update/delete).
- RBAC added to tenant onboarding endpoints (status/read vs settings write).
- Tool guide system and workflow docs added under `/docs` for animation + technical mapping.
- Tool catalog documentation added: `/docs/tool_catalog.md`.
- Plan/limit exceed now logs system events with dedupe window.
- Operator conversations list uses pagination + subqueries to reduce N+1.
- KYC submission/review logging pending until KYC module exists.
- Seed script added: `backend/scripts/seed_demo.py`.
- RBAC tightened on feature flags + subscription check feature.
- IDOR hardening: analytics bot stats now validate tenant ownership.
- Admin tenant list uses aggregate subqueries to reduce N+1.
- Leads now tenant-scoped and public lead creation sets tenant_id.
- Lead tenant_id backfill migration added for existing data.
- n8n automation status updates now validate run tenant.
- Public chat send optionally validates external_user_id and logs missing ID for visibility.
- Admin actions now audit-log user/tenant mutations (create/update/delete/suspend/feature-flags).
- Feature flags, subscription upgrades/cancels, and WhatsApp integration changes are now audit-logged.
- Widget now includes external_user_id in chat send requests.
- Added indexes for conversations/messages/leads list performance.
- Suspended tenants are now blocked at auth dependency level; inactive users are denied.
- Locked accounts are denied at auth dependency level.
- Admin audit logs now capture ip/user-agent when available.
