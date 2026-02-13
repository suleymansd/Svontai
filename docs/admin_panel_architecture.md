# Admin Panel Mimarisi (Enterprise)

## ERD Özeti
**Admin** (user)
- id, email, role, status

**Customer (Tenant)**
- id, name, plan_id, status

**Panel**
- id, tenant_id, layout_json

**Tool**
- id, key, name, category, status, required_plan

**Workflow**
- id, tenant_id, tool_id, n8n_workflow_id, status

**Execution (AutomationRun)**
- id, tenant_id, workflow_id, status, duration, correlation_id

**ErrorLog (SystemEvent)**
- id, tenant_id, source, code, level, correlation_id

**Incident**
- id, tenant_id, severity, status, assigned_to

**Ticket**
- id, tenant_id, requester_id, status, priority, assigned_to

**TicketMessage**
- id, ticket_id, sender_type, body, created_at

**AuditLog**
- id, tenant_id, action, resource_type, resource_id, created_at

**PartnerRequest**
- id, tenant_id, type, status, assigned_to

### İlişkiler
- Tenant → Panel (1:1)
- Tenant → Workflow (1:N)
- Tool → Workflow (1:N)
- Workflow → Execution (1:N)
- Tenant → ErrorLog (1:N)
- ErrorLog → Incident (N:1)
- Ticket → TicketMessage (1:N)
- Tenant → AuditLog (1:N)

## Yetki Matrisi
| Rol | Tenant Görüntüleme | Tool Yönetimi | Workflow Müdahale | Audit Log | Incident | Ticket |
| --- | --- | --- | --- | --- | --- | --- |
| Admin | Tam | Tam | Tam | Tam | Tam | Tam |
| Support Admin | Tam | Kısıtlı | Kısıtlı | Tam | Tam | Tam |
| Partner | Kısıtlı | Yok | Kısıtlı | Kısıtlı | Yok | Kısıtlı |
| Customer | Sadece kendi | Yok | Yok | Kendi | Kendi | Kendi |

## Admin Akışları
1) Tenant listesi → plan durumu → kullanım
2) Uzaktan panel görüntüleme → read/write modu
3) Tool yönetimi → ekle / sil / güncelle
4) Entegrasyon hata listesi → düzeltme → yeniden dene
5) Workflow iptali → geri alma → audit log
6) Plan uyumsuzluğu düzeltme → feature flags
7) Incident yönetimi → triage → postmortem
8) Partner talepleri → atama → çözüm

## Uzaktan Müdahale
- “Read-only” izleme
- “Write” modu için audit log + onay
- Tüm aksiyonlar `AuditLog` ile kayıt
