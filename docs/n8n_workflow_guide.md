# n8n Workflow Teknik Rehberi

Bu doküman, tool entegrasyonlarının n8n tarafındaki teknik akışını standartlaştırır. Her tool aynı çekirdek şemayı kullanır.

## Ortak Trigger Şeması
- Webhook (n8n) veya WhatsApp event
- Payload: `tenant_id`, `user_id`, `message`, `files[]`, `tool_config`
- Correlation: `correlation_id`

## Ortak Node Akışı
1) Trigger Node
2) Data Normalize Node
3) Logic / AI Node
4) External API Node
5) Response Builder Node
6) SvontAI Callback Node

## Standart Callback Endpoint’leri
- Tool çıktısı / durum güncelleme: `POST /api/v1/channels/automation/status`
- WhatsApp outbound: `POST /api/v1/channels/whatsapp/send`

## Tool Şablonları

### 1) WhatsApp Autoresponder
**Trigger**: WhatsApp inbound webhook
**Inputs**:
- `tenant_id`, `from_number`, `message_content`, `correlation_id`

**Node Akışı**:
- Trigger → Normalize → AI Response → Response Builder → WhatsApp Send

**Output**:
- WhatsApp mesajı + run status update

**Fallback**:
- `system_events` log (WH_TIMEOUT / META_SEND_FAIL)

---

### 2) CRM Sync Tool
**Trigger**: Webhook (CRM update)
**Inputs**:
- `tenant_id`, `lead_id`, `payload`, `tool_config`

**Node Akışı**:
- Trigger → Normalize → Validation → CRM API Node → Response Builder

**Output**:
- JSON response + status update

**Fallback**:
- CRM API fail → incident + retry

---

### 3) Scheduling Assistant
**Trigger**: WhatsApp inbound or Webhook
**Inputs**:
- `tenant_id`, `user_id`, `calendar`, `date_request`

**Node Akışı**:
- Trigger → Normalize → Availability Check → Scheduling API → Response Builder

**Output**:
- Slot confirmation + status update

**Fallback**:
- Slot unavailable → alternative suggestions

---

### 4) KYC Document Validator
**Trigger**: File upload
**Inputs**:
- `tenant_id`, `user_id`, `file_url`, `tool_config`

**Node Akışı**:
- Trigger → Normalize → Document Parse → Validation → Response Builder

**Output**:
- Validation result + status update

**Fallback**:
- File parse fail → error event + manual review queue

## Error & Fallback Standardı
- `system_events` kayıtları ile hata raporu
- `incidents` otomatik açılır (eşik aşımları)
- Retry stratejisi: `max_retries` + exponential backoff
