# SvontAI API Overview

## Base URL
- Default: `http://localhost:8000`
- All endpoints are prefixed with `/api` in the backend router configuration.

## Auth
- Bearer token: `Authorization: Bearer <access_token>`
- Refresh tokens via `/auth/refresh`.

## Pagination
- Offset-based: `skip`, `limit`
- Page-based: `page`, `page_size` (admin lists)

## Core Endpoints
### Auth
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`

### Me / Users
- `GET /me`
- `PUT /me`

### Tenants
- `POST /tenants`
- `GET /tenants/my`
- `PUT /tenants/{tenant_id}`

### Bots
- `GET /bots`
- `POST /bots`
- `GET /bots/{bot_id}`
- `PUT /bots/{bot_id}`
- `DELETE /bots/{bot_id}`

### Knowledge
- `GET /knowledge`
- `POST /knowledge`
- `PUT /knowledge/{item_id}`
- `DELETE /knowledge/{item_id}`

### Leads
- `GET /leads`
- `POST /leads`
- `PUT /leads/{lead_id}`
- `DELETE /leads/{lead_id}`

### Automation
- `GET /automation/settings`
- `PUT /automation/settings`
- `GET /automation/runs`
- `POST /automation/test`
- `GET /automation/status`

### Observability
- `GET /system-events`
- `GET /incidents`
- `GET /incidents/{incident_id}`
- `POST /incidents`
- `PATCH /incidents/{incident_id}`

### Tickets
- `GET /tickets`
- `POST /tickets`
- `GET /tickets/{ticket_id}`
- `POST /tickets/{ticket_id}/messages`
- `PATCH /tickets/{ticket_id}`

### Admin (internal)
- `GET /admin/stats`
- `GET /admin/tenants`
- `GET /admin/tenants/{tenant_id}`
- `PATCH /admin/tenants/{tenant_id}`
- `GET /admin/plans`
- `POST /admin/plans`
- `PATCH /admin/plans/{plan_id}`
- `GET /admin/tools`
- `POST /admin/tools`
- `PATCH /admin/tools/{tool_id}`
- `GET /admin/audit`
- `GET /admin/users`

### Public Widget
- `POST /public/chat/init`
- `POST /public/chat/send`
- `GET /public/chat/messages`
- `POST /public/leads`

Notes:
- `POST /public/chat/send` accepts optional `external_user_id` for validation.

### n8n Channels
- `POST /api/v1/channels/whatsapp/send`
- `POST /api/v1/channels/automation/status`

## Error Codes
Common errors:
- `401` Unauthorized
- `403` Forbidden (RBAC/entitlements)
- `404` Not Found
- `429` Rate Limit
- `500` Internal Error
