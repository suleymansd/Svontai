# Tool Catalog (Animasyon + Teknik Dokümantasyon)

Bu doküman, her tool icin animasyonlu rehber akisini ve n8n teknik workflow detaylarini tek yerde birlestirir.

## Ortak Animasyon Akisi
1) Tool Secimi
2) Surukle & Birak
3) Tool Sayfasi Acilisi
4) Adim Adim Entegrasyon
5) Dongusel Rehber

> Tool bazli tooltip metinleri asagida ozel olarak verilir.

---

## 1) WhatsApp Autoresponder

### Animasyon Rehberi (Tooltip)
- Tool Secimi: "WhatsApp Autoresponder ile mesajlari otomatik yanitlayin"
- Surukle & Birak: "Tool'u akisa birakarak aktif edin"
- Tool Sayfasi: "WhatsApp hesap baglantisini tamamlayin"
- Entegrasyon: "Telefon numarasi ve token bilgilerini girin"
- Dongu: "Rehberi kapatabilir veya bastan izleyebilirsiniz"

### Teknik Workflow (n8n)
- Trigger: WhatsApp inbound webhook
- Inputs:
  - tenant_id, from_number, message_content, correlation_id
- Node Akisi:
  1) Trigger Node
  2) Normalize Node (message parsing)
  3) AI Node (cevap olusturma)
  4) Response Builder Node
  5) WhatsApp Send Node
- Output:
  - `POST /api/v1/channels/whatsapp/send`
  - `POST /api/v1/channels/automation/status`
- Error & Fallback:
  - `WH_SEND_FAILED`, `WH_NO_ACCESS_TOKEN`, `WH_AI_ERROR`
  - `system_events` kaydi + incident tetikleme

---

## 2) CRM Sync

### Animasyon Rehberi (Tooltip)
- Tool Secimi: "CRM kayitlarini otomatik senkronize edin"
- Surukle & Birak: "CRM tool'unu akisa ekleyin"
- Tool Sayfasi: "API anahtarlarini baglayin"
- Entegrasyon: "Alan eslestirmeleri yapin"
- Dongu: "Rehberi kapatabilir veya bastan izleyebilirsiniz"

### Teknik Workflow (n8n)
- Trigger: Webhook (CRM data update)
- Inputs:
  - tenant_id, lead_id, payload, tool_config
- Node Akisi:
  1) Trigger Node
  2) Normalize Node
  3) Validation Node
  4) CRM API Node
  5) Response Builder Node
- Output:
  - JSON response + `POST /api/v1/channels/automation/status`
- Error & Fallback:
  - `N8N_HTTP_ERROR`, `N8N_CONNECT_ERROR`
  - `system_events` + retry

---

## 3) Scheduling Assistant

### Animasyon Rehberi (Tooltip)
- Tool Secimi: "Randevu akisini otomatiklestirin"
- Surukle & Birak: "Tool'u takvime baglayin"
- Tool Sayfasi: "Takvim entegrasyonunu acin"
- Entegrasyon: "Saat araligi ve kaynak secin"
- Dongu: "Rehberi kapatabilir veya bastan izleyebilirsiniz"

### Teknik Workflow (n8n)
- Trigger: WhatsApp inbound veya Webhook
- Inputs:
  - tenant_id, user_id, date_request, tool_config
- Node Akisi:
  1) Trigger Node
  2) Normalize Node
  3) Availability Check
  4) Scheduling API Node
  5) Response Builder Node
- Output:
  - Slot onayi + status update
- Error & Fallback:
  - Slot bulunamazsa alternatif teklif
  - `system_events` kaydi

---

## 4) KYC Document Validator

### Animasyon Rehberi (Tooltip)
- Tool Secimi: "KYC belgelerini dogrulayin"
- Surukle & Birak: "Belge dogrulama tool'unu ekleyin"
- Tool Sayfasi: "Belge kurallarini secin"
- Entegrasyon: "Dosya yukleme ve kontrol adimlarini etkinlestirin"
- Dongu: "Rehberi kapatabilir veya bastan izleyebilirsiniz"

### Teknik Workflow (n8n)
- Trigger: File upload webhook
- Inputs:
  - tenant_id, user_id, file_url, tool_config
- Node Akisi:
  1) Trigger Node
  2) Normalize Node
  3) Document Parse
  4) Validation Node
  5) Response Builder Node
- Output:
  - Validation sonucu + status update
- Error & Fallback:
  - Parse hatasi -> manual review
  - `system_events` kaydi

---

## 5) Support Ticket Assistant

### Animasyon Rehberi (Tooltip)
- Tool Secimi: "Destek taleplerini otomatik duzenleyin"
- Surukle & Birak: "Ticket tool'unu akisa ekleyin"
- Tool Sayfasi: "SLA ve oncelik kurallarini belirleyin"
- Entegrasyon: "Ticket otomasyon kurallarini ayarlayin"
- Dongu: "Rehberi kapatabilir veya bastan izleyebilirsiniz"

### Teknik Workflow (n8n)
- Trigger: Ticket create event
- Inputs:
  - tenant_id, ticket_id, message, priority
- Node Akisi:
  1) Trigger Node
  2) Normalize Node
  3) Classification Node (priority)
  4) Response Builder Node
- Output:
  - Ticket status update (`PATCH /tickets/{id}`)
- Error & Fallback:
  - N8N error -> `system_events`

---

## Loglama ve Geri Alma
- Tum kritik aksiyonlar `audit_logs` ile loglanir
- Geri alma istenen akislarda tool status geri alinir ve audit kaydi olusturulur
