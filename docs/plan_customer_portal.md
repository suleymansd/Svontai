# Customer Portal + Admin Upgrade Plan

## Phase 0 - Repo Scan + Decisions
- [x] Document architecture decisions in `docs/architecture.md`
- [ ] Create detailed checklist with target paths (this file)

## Phase 1 - Auth, RBAC, Tenant Context
- [ ] Backend auth refresh rotation + sessions
  - `backend/app/models/session.py`
  - `backend/app/schemas/session.py`
  - `backend/app/api/routers/auth.py`
  - `backend/app/services/auth_service.py`
- [ ] `/api/me` endpoint
  - `backend/app/api/routers/users.py`
  - `backend/app/schemas/user.py`
  - `frontend/src/lib/api.ts`
- [ ] RBAC + permissions
  - `backend/app/models/role.py`
  - `backend/app/models/permission.py`
  - `backend/app/models/tenant_membership.py`
  - `backend/app/dependencies/permissions.py`
  - `frontend/src/lib/permissions.ts`
  - `frontend/src/components/guards/PermissionGate.tsx`
- [ ] Feature flags
  - `backend/app/models/feature_flag.py`
  - `backend/app/api/routers/feature_flags.py`
  - `frontend/src/lib/feature-flags.ts`
- [ ] Audit logs baseline
  - `backend/app/models/audit_log.py`
  - `backend/app/services/audit_log_service.py`

## Phase 2 - Tools Catalog + Dashboard Widgets
- [ ] Tools catalog + entitlements
  - `backend/app/models/tool.py`
  - `backend/app/models/tenant_tool.py`
  - `backend/app/api/routers/tools.py`
  - `backend/app/schemas/tool.py`
  - `frontend/src/app/dashboard/tools`
- [ ] Tool panels + routing
  - `backend/app/models/tool_panel.py`
  - `backend/app/api/routers/panels.py`
  - `frontend/src/app/dashboard/panels`
- [ ] Dashboard widgets (drag and drop)
  - `backend/app/models/dashboard_widget.py`
  - `backend/app/api/routers/dashboard_widgets.py`
  - `frontend/src/components/dashboard/WidgetGrid.tsx`
  - `frontend/src/app/dashboard/page.tsx`

## Phase 3 - Tickets System
- [ ] Ticket entity + messages
  - `backend/app/models/ticket.py`
  - `backend/app/models/ticket_message.py`
  - `backend/app/api/routers/tickets.py`
  - `backend/app/schemas/ticket.py`
- [ ] Ticket UI
  - `frontend/src/app/dashboard/tickets`
  - `frontend/src/components/tickets`
- [ ] Audit logging for ticket actions
  - `backend/app/services/audit_log_service.py`

## Phase 4 - KYC / Identity Verification
- [ ] KYC models + endpoints
  - `backend/app/models/kyc_profile.py`
  - `backend/app/models/kyc_document.py`
  - `backend/app/api/routers/kyc.py`
  - `backend/app/schemas/kyc.py`
- [ ] Customer UI stepper
  - `frontend/src/app/dashboard/settings/verification`
  - `frontend/src/components/kyc`
- [ ] Admin review UI
  - `frontend/src/app/admin/kyc`

## Phase 5 - Data Tables + Pagination
- [ ] Standardize pagination + filters
  - `backend/app/services/pagination.py`
  - Update existing list endpoints for consistency
- [ ] Reusable Table component
  - `frontend/src/components/table/DataTable.tsx`
  - `frontend/src/components/ui/table.tsx`

## Phase 6 - UI Polish + Quality
- [ ] Command palette, breadcrumbs, notifications
  - `frontend/src/components/layout/CommandPalette.tsx`
  - `frontend/src/components/layout/Breadcrumbs.tsx`
  - `frontend/src/components/notifications`
- [ ] Dark mode and theme consistency
  - `frontend/src/app/globals.css`
  - `frontend/src/lib/store.ts`
- [ ] Error boundaries and 403/404 pages
  - `frontend/src/app/not-found.tsx`
  - `frontend/src/app/forbidden/page.tsx`

## Phase 7 - Tests, Seed Data, Docs
- [ ] Backend smoke tests
  - `backend/tests/test_auth.py`
  - `backend/tests/test_tools.py`
  - `backend/tests/test_dashboard_widgets.py`
  - `backend/tests/test_tickets.py`
- [ ] Frontend e2e smoke
  - `frontend/tests/e2e/smoke.spec.ts`
- [ ] Seed data
  - `backend/app/services/seed_service.py`
  - `backend/app/cli/seed.py`
- [ ] Docs updates
  - `README.md`
  - `docs/SETUP.md`

## Migrations
- [ ] Alembic migration series for new models
  - `backend/alembic/versions/007_add_rbac_and_sessions.py`
  - `backend/alembic/versions/008_add_tools_and_widgets.py`
  - `backend/alembic/versions/009_add_tickets.py`
  - `backend/alembic/versions/010_add_kyc.py`
  - `backend/alembic/versions/011_add_audit_and_feature_flags.py`
