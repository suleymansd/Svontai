## Architecture Decisions (Phase 0)

### Repo scan summary
- Frontend uses Next.js App Router under `frontend/src/app` with shared UI in `frontend/src/components/ui`.
- Backend is FastAPI with routers in `backend/app/api/routers`, SQLAlchemy models in `backend/app/models`, Pydantic schemas in `backend/app/schemas`, and Alembic migrations in `backend/alembic/versions`.
- Auth currently uses JWT access/refresh tokens via `Authorization: Bearer` and localStorage (`frontend/src/lib/api.ts`, `backend/app/core/security.py`).
- Tenant isolation is currently owner-based (`backend/app/models/tenant.py`, `backend/app/dependencies/auth.py`).

### Decisions
1) **Frontend routing and layout**
   - Keep App Router and extend `frontend/src/app/dashboard` for the customer portal and `frontend/src/app/admin` for admin.
   - Create shared layout components (sidebar, topbar, breadcrumbs, command palette) in `frontend/src/components/layout` to unify styles and behavior.

2) **Auth + tenant context**
   - Preserve existing JWT Bearer flow to avoid breaking current API clients.
   - Introduce refresh rotation + session store on backend while keeping the same endpoints.
   - Add `/api/me` to return user + tenant + role + entitlements + feature flags.
   - Add tenant membership model to support multiple tenants per user while honoring current owner-based flow by migrating owners into memberships.

3) **RBAC and permissions**
   - Add roles and permissions to backend with explicit checks per router via dependencies.
   - Enforce tenant scoping in every query using tenant context from token/session, not request payloads.
   - Add frontend route guards and permission-aware UI toggles.

4) **Audit logs and feature flags**
   - Add `audit_logs` and `feature_flags` tables with tenant scoping.
   - Log sensitive actions (role changes, tool enablement, ticket updates, KYC state changes).

5) **Data model expansion**
   - Add tools catalog, entitlements, dashboard widgets, tool panels, tickets, KYC tables, and audit logs as new models in `backend/app/models`.
   - Expose CRUD via new routers in `backend/app/api/routers` and schemas in `backend/app/schemas`.

6) **Pagination and tables**
   - Standardize server-side pagination (offset + limit) for existing endpoints to avoid API breakage.
   - Implement a reusable table component with loading/empty/error states on the frontend.

7) **Migrations**
   - Continue with Alembic; create incremental migrations with backward-compatible changes.
   - Add a seed script in backend for demo tenant, tools, runs, and tickets.

8) **Observability**
   - Add `system_events` for high-volume operational events (tenant-scoped or global).
   - Add `incidents` for triage lifecycle (open → mitigated → resolved).
   - Introduce `correlation_id` to link inbound messages, automation runs, events, and tickets.
