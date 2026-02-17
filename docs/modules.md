# SvontAI Modules

## Customer Portal (Tenant-facing)
Routes under `/dashboard`:
- Dashboard overview + widgets
- Tools catalog + tool detail
- In-app usage guide (`/dashboard/help`)
- Automations run history
- Tickets
- Team management
- Settings + KYC stepper
- Usage + Errors

## Company Management Panel (Internal Ops)
Routes under `/admin`:
- Admin dashboard
- Tenants management
- Super admin usage guide (`/admin/help`)
- Plans & packages
- Tools catalog management
- Tickets ops
- KYC review
- Incidents + Error Center
- Audit logs

## Observability + Error Center
Backend:
- `system_events` (high-volume events)
- `incidents` (triage lifecycle)
Frontend:
- `/dashboard/errors` (tenant scoped)
- `/admin/incidents` (global)

## Tool Guides + Workflow Docs
Docs:
- `/docs/tool_guide_system.md`
- `/docs/tool_catalog.md`
- `/docs/n8n_workflow_guide.md`
- `/docs/admin_panel_architecture.md`
- `/docs/SISTEM_KULLANIM_REHBERI.md`
- `/docs/prompts/animation_guide_prompt.md`
- `/docs/prompts/admin_panel_prompt.md`

## Landing / Marketing
Public routes:
- `/`, `/pricing`, `/features`, `/use-cases/[segment]`, `/security`, `/contact`, `/docs`
