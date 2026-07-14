# SvontAI ↔ n8n Integration Guide (Production)

Bu doküman, SvontAI’nin **n8n-first orchestration** mimarisinde n8n workflow’larının hangi endpoint’leri nasıl kullanacağını netleştirir.

## 1) Auth (n8n → SvontAI)

SvontAI, n8n’ye event gönderirken payload içinde tenant-scoped kısa ömürlü bir token verir:

- `payload.svontai.token`
- `payload.callback.token`

n8n, SvontAI callback’lerini çağırırken şu header’ı kullanır:

- `Authorization: Bearer {{ $json.svontai.token }}`

Opsiyonel:
- `X-Tenant-Id: {{ $json.tenantId }}` (SvontAI, token-tenant mismatch kontrolü yapar)

## 2) Standard Event Payload (SvontAI → n8n)

SvontAI n8n’ye her zaman aşağıdaki normalize formda gönderir:

```json
{
  "event": "svontai_event",
  "eventType": "incoming_message | voice_call_started | voice_call_intent | voice_call_completed | ...",
  "runId": "uuid",
  "correlationId": "optional",
  "tenantId": "uuid",
  "channel": "whatsapp | web_widget | call",
  "externalEventId": "wamid... | twilio:CA...:intent",
  "from": "tel:+90... | +90... | whatsapp-id",
  "to": "tel:+90... | ...",
  "text": "optional",
  "timestamp": "ISO8601",
  "metadata": {},
  "svontai": {
    "baseUrl": "https://<backend>",
    "tenantId": "uuid",
    "token": "JWT",
    "endpoints": {
      "whatsapp_send": "POST /api/v1/channels/whatsapp/send",
      "whatsapp_send_template": "POST /api/v1/channels/whatsapp/send-template",
      "whatsapp_send_document": "POST /api/v1/channels/whatsapp/send-document",
      "automation_status": "POST /api/v1/channels/automation/status",
      "voice_call_summary": "POST /api/v1/voice/calls/summary",
      "leads_upsert": "POST /api/v1/n8n/leads/upsert",
      "notes_create": "POST /api/v1/n8n/notes/create",
      "usage_increment": "POST /api/v1/n8n/usage/increment",
      "audit_log": "POST /api/v1/n8n/audit/log",
      "calls_resolve": "POST /api/v1/n8n/calls/resolve",
      "calls_transcript": "POST /api/v1/n8n/calls/transcript"
    }
  }
}
```

Not: SvontAI ayrıca başarılı n8n trigger’larında `workflow_runs` metriğini otomatik arttırır.

### 2.1) Signature verification (SvontAI → n8n)

SvontAI, n8n webhook’larını HMAC ile imzalar:
- `X-SvontAI-Signature`
- `X-SvontAI-Timestamp`

`n8n/workflows/SvontAI_Router_v2.json` template’i bunları doğrulamak için n8n instance’ında şu env’i bekler:
- `SVONTAI_TO_N8N_SECRET` (SvontAI backend’deki `SVONTAI_TO_N8N_SECRET` ile aynı)

### 2.2) OpenAI (opsiyonel)

`n8n/workflows/SvontAI_Router_v3_openai.json` template’i OpenAI üzerinden cevap üretir. n8n instance’ında:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (opsiyonel, default: `gpt-4o-mini`)

## 3) Tool Endpoints (n8n → SvontAI)

### 3.1) Lead Upsert

`POST {{ $json.svontai.endpoints.leads_upsert }}`

Body:
```json
{
  "tenantId": "{{ $json.tenantId }}",
  "phone": "{{ $json.from }}",
  "email": null,
  "name": null,
  "status": "new",
  "source": "whatsapp",
  "tags": ["voice"],
  "extraData": {},
  "callProvider": "twilio",
  "callProviderCallId": "{{ $json.metadata.call.provider_call_id }}"
}
```

Response:
```json
{ "ok": true, "leadId": "...", "created": true, "updated": false }
```

### 3.2) Create Note (Lead/Call/Conversation)

`POST {{ $json.svontai.endpoints.notes_create }}`

Body:
```json
{
  "tenantId": "{{ $json.tenantId }}",
  "leadId": "{{ $node['Lead Upsert'].json.leadId }}",
  "callProvider": "twilio",
  "callProviderCallId": "{{ $json.metadata.call.provider_call_id }}",
  "noteType": "call_summary",
  "title": "Call Summary",
  "content": "Özet metin...",
  "source": "n8n",
  "metaJson": { "intent": "buyer", "labels": { "budget": "..." } }
}
```

### 3.3) Persist Call Summary

`POST {{ $json.svontai.endpoints.voice_call_summary }}`

Body:
```json
{
  "tenantId": "{{ $json.tenantId }}",
  "provider": "twilio",
  "providerCallId": "{{ $json.metadata.call.provider_call_id }}",
  "leadId": "{{ $node['Lead Upsert'].json.leadId }}",
  "intent": "buyer",
  "summary": "Kısa özet...",
  "labelsJson": { "location": "ankara" },
  "actionItemsJson": { "next": ["randevu"] },
  "createLeadNote": true
}
```

### 3.4) Usage Increment (Opsiyonel)

`POST {{ $json.svontai.endpoints.usage_increment }}`

Body:
```json
{
  "tenantId": "{{ $json.tenantId }}",
  "toolCalls": 1,
  "messageCount": 0,
  "voiceSeconds": 0,
  "workflowRuns": 0,
  "outboundCalls": 0,
  "extra": { "reason": "followup" }
}
```

## 4) Voice Call Intent (Synchronous Response Contract)

SvontAI, Voice Gateway üzerinden `voice_call_intent` olaylarında n8n’yi **synchronous** çalıştırır ve n8n’den response bekler.

n8n webhook response body örneği:
```json
{
  "responseText": "Merhaba! Hangi bölgede ev bakıyorsunuz?",
  "endCall": false,
  "intent": "buyer"
}
```

Minimum zorunlu alanlar:
- `responseText` (string)
- `endCall` (bool, default false)

## 5) Workflow Templates (Repo)

Repo içinde hazır n8n workflow template’leri:
- `n8n/workflows/SvontAI_WhatsApp_Agent_v1.json` → webhook path: `svontai-wa-agent`
- `n8n/workflows/SvontAI_Voice_Agent_v1.json` → webhook path: `svontai-voice-agent`
- `n8n/workflows/SvontAI_RealEstate_WhatsApp_v1.json` → webhook path: `svontai-re-wa`
- `n8n/workflows/SvontAI_RealEstate_Voice_v1.json` → webhook path: `svontai-re-voice`

SvontAI panelde tenant bazlı ayar:
- WhatsApp workflow id: `svontai-wa-agent`
- Call workflow id: `svontai-voice-agent`

Real Estate Pack (n8n-first) için:
- WhatsApp workflow id: `svontai-re-wa`
- Call workflow id: `svontai-re-voice`

Gerekli n8n env:
- `SVONTAI_TO_N8N_SECRET` (SvontAI backend ile aynı)
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (opsiyonel, default: `gpt-4o-mini`)
- `WA_FALLBACK_TEMPLATE_NAME` (opsiyonel; 24h pencere dışı için)
- `WA_FALLBACK_TEMPLATE_LANG` (opsiyonel; default `tr`)

## 6) Marketplace Tool Runner (Yeni)

Backend artık tenant bazlı tool marketplace için standart runner endpoint’leri sunar:

- `GET /tools/registry`
- `PUT /tools/{tool_slug}/settings`
- `POST /tools/run`
- `POST /assistant/chat`

İlk 10 marketplace tool kaydını üretmek için (Super Admin):
- `POST /admin/tools/seed-initial`

### 6.1) `/tools/run` standart contract

Request:
```json
{
  "requestId": "optional-uuid",
  "toolSlug": "pdf_summary",
  "toolInput": { "text": "..." },
  "context": {
    "locale": "tr-TR",
    "timezone": "Europe/Istanbul",
    "channel": "web",
    "memory": {}
  }
}
```

Response:
```json
{
  "requestId": "uuid",
  "success": true,
  "data": {},
  "error": null,
  "usage": { "timeMs": 1200, "tokens": null, "cost": null },
  "artifacts": []
}
```

### 6.2) Tool Runner için gerekli backend env

- `USE_N8N=true`
- `N8N_BASE_URL`
- `N8N_INTERNAL_RUN_ENDPOINT_TEMPLATE` (default: `/api/v1/workflows/{workflow_id}/run`)
- `N8N_TOOL_RUNNER_WORKFLOW_ID` (default: `svontai-tool-runner`)
- `N8N_TIMEOUT_SECONDS`
- `SVONTAI_TO_N8N_SECRET`
- `N8N_API_KEY` (opsiyonel)

Not:
- Tool runner path’i public webhook kullanmaz; backend doğrudan n8n internal API run endpoint’ine çağrı yapar.
- Template dosyaları:
  - `n8n/templates/svontai-tool-runner.json`
  - `n8n/templates/tools/pdf_summary_wrapper.json`
  - `n8n/templates/tools/pdf_to_word_wrapper.json`
  - `n8n/templates/tools/drive_save_file_wrapper.json`
  - `n8n/templates/tools/gmail_summary_wrapper.json`
- Import sonrası tüm workflow’lar `inactive` kalmalıdır.

### 6.3) Yeni tool slug’ları

- `pdf_to_word`
- `drive_save_file`
- `gmail_summary`

Runner `tool_slug` eşleşmezse standart hata döner:
```json
{
  "request_id": "....",
  "success": false,
  "error": { "code": "UNSUPPORTED_TOOL_SLUG", "message": "Unsupported tool_slug: ..." }
}
```
