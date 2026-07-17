# n8n Workflow Engine Integration

SvontAI, n8n workflow engine ile entegre çalışarak WhatsApp mesajlarını görsel workflow'lar ile işlemenize olanak tanır.

## 🎯 Genel Bakış

### Mimari

```
┌─────────────────────────────────────────────────────────────┐
│                     WhatsApp Users                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Meta WhatsApp API                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      SvontAI Backend                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  WhatsApp Webhook Handler                            │    │
│  │  - Tenant resolution                                 │    │
│  │  - Message storage                                   │    │
│  │  - Security validation                               │    │
│  │  - Feature flag check (USE_N8N)                      │    │
│  └───────────────────────┬─────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│         ┌────────────────┴────────────────┐                 │
│         │                                  │                 │
│    USE_N8N=true                      USE_N8N=false          │
│         │                                  │                 │
│         ▼                                  ▼                 │
│  ┌──────────────┐                  ┌──────────────┐         │
│  │  n8n Client  │                  │  AI Service  │         │
│  │  (Bridge)    │                  │  (Legacy)    │         │
│  └──────┬───────┘                  └──────────────┘         │
│         │                                                    │
└─────────┼────────────────────────────────────────────────────┘
          │
          │ HMAC Signed Request
          ▼
┌─────────────────────────────────────────────────────────────┐
│                      n8n Workflow Engine                     │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Workflow Execution                                  │    │
│  │  - Conditions                                        │    │
│  │  - Transformations                                   │    │
│  │  - External API calls                                │    │
│  │  - AI/LLM integration                                │    │
│  └───────────────────────┬─────────────────────────────┘    │
│                          │                                   │
└──────────────────────────┼───────────────────────────────────┘
                           │
                           │ Callback with JWT
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               SvontAI Channels API                           │
│  POST /api/v1/channels/whatsapp/send                        │
│  - JWT verification                                          │
│  - Message sending via Meta API                              │
│  - Conversation history update                               │
│  - Automation run status update                              │
└─────────────────────────────────────────────────────────────┘
```

### Önemli Kurallar

1. **WhatsApp webhook'ları ASLA doğrudan n8n'e gitmez**
2. Tüm gelen/giden WhatsApp trafiği SvontAI üzerinden geçer
3. n8n sadece workflow executor olarak çalışır
4. Multi-tenant güvenlik SvontAI tarafından sağlanır

## 🚀 Kurulum

### 1. Docker Compose ile Başlatma

```bash
# Tüm servisleri başlat
docker compose up -d

# Logları izle
docker compose logs -f n8n
docker compose logs -f backend
```

### 2. Environment Variables

`.env` dosyasını oluşturun:

```env
# n8n Feature Flag
USE_N8N=true

# n8n Connection
N8N_BASE_URL=http://n8n:5678
N8N_API_KEY=

# Security (Mutlaka değiştirin!)
SVONTAI_TO_N8N_SECRET=your-secure-random-string-svontai-to-n8n
N8N_TO_SVONTAI_SECRET=your-secure-random-string-n8n-to-svontai
N8N_ERROR_WEBHOOK_SECRET=your-secure-random-string-error-webhook

# Default Workflow
N8N_INCOMING_WORKFLOW_ID=svontai-incoming

# Timeouts
N8N_TIMEOUT_SECONDS=10
N8N_RETRY_COUNT=2

# n8n Admin Credentials
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=change-this-password
```

n8n servisine ayrıca aşağıdaki değişkenleri ekleyin:

```env
SVONTAI_BACKEND_URL=https://your-backend.example.com
N8N_ERROR_WEBHOOK_SECRET=your-secure-random-string-error-webhook
```

### 3. Database Migration

```bash
cd backend
source venv/bin/activate
alembic upgrade head
```

### 4. n8n Workflow Import

Production workflow ve merkezi hata akışını API üzerinden doğrulayın:

```bash
python scripts/install_n8n_error_workflow.py
python scripts/audit_n8n_workflows.py
```

## 🔧 Yapılandırma

### Tenant Seviyesinde Yapılandırma

Her tenant kendi n8n ayarlarını yönetebilir:

1. Dashboard > Ayarlar > Otomasyon (n8n) sekmesine gidin
2. "n8n Workflow'ları Kullan" seçeneğini aktifleştirin
3. Workflow ID'sini girin (örn: `svontai-incoming`)
4. Ayarları kaydedin
5. "Test Mesajı Gönder" ile doğrulayın

### API ile Yapılandırma

```bash
# Ayarları getir
curl -X GET "http://localhost:8000/automation/settings" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Ayarları güncelle
curl -X PUT "http://localhost:8000/automation/settings" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "use_n8n": true,
    "default_workflow_id": "svontai-incoming",
    "enable_auto_retry": true,
    "max_retries": 2,
    "timeout_seconds": 10
  }'
```

## 📝 Workflow Geliştirme

### Gelen Mesaj Payload'ı

SvontAI'dan n8n'e gönderilen payload:

```json
{
  "event": "incoming_message",
  "runId": "uuid-of-automation-run",
  "tenantId": "uuid-of-tenant",
  "channel": "whatsapp",
  "from": "+905551234567",
  "to": "+905559876543",
  "text": "Merhaba, fiyat bilgisi alabilir miyim?",
  "messageId": "wamid.xxx",
  "timestamp": "2024-01-20T10:00:00.000Z",
  "contactName": "John Doe",
  "callback": {
    "url": "http://svontai:8000/api/v1/channels/whatsapp/send",
    "token": "jwt-token-for-callback"
  },
  "extra": {
    "bot_id": "uuid",
    "conversation_id": "uuid",
    "message_type": "text"
  }
}
```

### Yanıt Gönderme

n8n'den SvontAI'a yanıt göndermek için HTTP Request node kullanın:

```json
// POST http://svontai:8000/api/v1/channels/whatsapp/send
// Headers:
//   Authorization: Bearer {{ $json.callback.token }}
//   X-Tenant-Id: {{ $json.tenantId }}

{
  "tenantId": "{{ $json.tenantId }}",
  "to": "{{ $json.from }}",
  "text": "Merhaba! Size nasıl yardımcı olabilirim?",
  "meta": {
    "runId": "{{ $json.runId }}",
    "n8nExecutionId": "{{ $execution.id }}"
  }
}
```

### Örnek Workflow Senaryoları

#### 1. Anahtar Kelime Bazlı Yönlendirme

```
Webhook Trigger → IF (contains "fiyat") → Price Response
                → IF (contains "destek") → Support Response
                → Default Response
```

#### 2. Harici API Entegrasyonu

```
Webhook Trigger → CRM Lookup → IF (existing customer) → VIP Response
                                                      → New Customer Response
```

#### 3. AI/LLM Entegrasyonu

```
Webhook Trigger → OpenAI Node → Response Formatting → Send to SvontAI
```

## 🔒 Güvenlik

### HMAC Signature Doğrulama

SvontAI → n8n istekleri HMAC-SHA256 ile imzalanır:

```
X-SvontAI-Signature: HMAC_SHA256(timestamp.payload, SVONTAI_TO_N8N_SECRET)
X-SvontAI-Timestamp: Unix timestamp
X-Tenant-Id: Tenant UUID
```

### JWT Token Doğrulama

n8n → SvontAI callback'leri JWT ile doğrulanır:

```
Authorization: Bearer <jwt_token>
X-Tenant-Id: Tenant UUID
```

JWT payload:
```json
{
  "tenant_id": "uuid",
  "type": "n8n_callback",
  "exp": "expiry_time",
  "iat": "issued_at"
}
```

### n8n'de Signature Doğrulama (Opsiyonel)

Ek güvenlik için n8n workflow'unda signature doğrulayabilirsiniz:

```javascript
// Code node
const crypto = require('crypto');

const signature = $input.first().headers['x-svontai-signature'];
const timestamp = $input.first().headers['x-svontai-timestamp'];
const body = JSON.stringify($input.first().json.body);
const secret = 'your-shared-secret';

const expectedSig = crypto
  .createHmac('sha256', secret)
  .update(`${timestamp}.${body}`)
  .digest('hex');

if (signature !== expectedSig) {
  throw new Error('Invalid signature');
}

return $input.all();
```

## 📊 İzleme ve Debug

### Automation Runs

```bash
# Son çalıştırmaları listele
curl -X GET "http://localhost:8000/automation/runs?limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Duruma göre filtrele
curl -X GET "http://localhost:8000/automation/runs?status_filter=failed" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Status Endpoint

```bash
curl -X GET "http://localhost:8000/automation/status" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response:
{
  "global_enabled": true,
  "tenant_enabled": true,
  "is_configured": true,
  "n8n_url": "http://n8n:5678",
  "stats_24h": {
    "total": 150,
    "successful": 145,
    "failed": 5,
    "success_rate": 96.7
  }
}
```

### n8n Execution Logs

n8n Dashboard > Executions sekmesinden tüm çalıştırmaları görebilirsiniz.

## 🐛 Sorun Giderme

### 1. "n8n is not enabled for this tenant"

- Global flag kontrol edin: `USE_N8N=true`
- Tenant ayarlarını kontrol edin: Dashboard > Ayarlar > Otomasyon

### 2. "No workflow configured"

- `N8N_INCOMING_WORKFLOW_ID` veya tenant'ın `default_workflow_id` ayarlı olmalı
- n8n'de workflow aktif olmalı

### 3. "Connection refused to n8n"

- Docker network kontrol edin: `docker network ls`
- n8n servisinin çalıştığından emin olun: `docker compose ps`

### 4. "Invalid signature"

- Shared secret'ların eşleştiğinden emin olun
- Timestamp farkının 5 dakikadan az olduğunu kontrol edin

### 5. n8n Workflow Timeout

- `N8N_TIMEOUT_SECONDS` değerini artırın
- n8n worker'ların çalıştığından emin olun

## 🔄 Eski Sisteme Geri Dönüş

n8n'i devre dışı bırakmak için:

1. **Global:** `.env`'de `USE_N8N=false` yapın ve backend'i yeniden başlatın
2. **Tenant:** Dashboard'dan "n8n Workflow'ları Kullan" seçeneğini kapatın

Eski AI response sistemi otomatik olarak devreye girer.

## 📚 Ek Kaynaklar

- [n8n Documentation](https://docs.n8n.io/)
- [n8n Webhook Node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [SvontAI API Documentation](/docs/API.md)
