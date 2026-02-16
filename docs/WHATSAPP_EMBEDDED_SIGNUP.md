# WhatsApp Embedded Signup Entegrasyonu

Bu döküman, SvontAi'ın WhatsApp Business API ile nasıl entegre olduğunu ve kurulumu için gerekli adımları açıklar.

## 🎯 Genel Bakış

SvontAi, Meta'nın resmi **Embedded Signup** yöntemini kullanarak WhatsApp Business API entegrasyonu sağlar. Bu yöntem:

- ✅ Resmi ve güvenli
- ✅ Kullanıcı dostu (1-3 dakika kurulum)
- ✅ Otomatik webhook yapılandırması
- ✅ Token yönetimi otomatik

## 📋 Gerekli Meta App Ayarları

### 1. Meta Developer Hesabı Oluşturma

1. [developers.facebook.com](https://developers.facebook.com) adresine gidin
2. Developer hesabı oluşturun veya giriş yapın
3. "My Apps" → "Create App" tıklayın
4. "Business" türünü seçin

### 2. WhatsApp Ürününü Ekleme

1. App Dashboard'da "Add Products" bölümüne gidin
2. "WhatsApp" kartında "Set Up" tıklayın
3. Business Account'unuzu bağlayın

### 3. Embedded Signup Konfigürasyonu

1. WhatsApp → Configuration → Embedded Signup
2. "Create Configuration" tıklayın
3. Aşağıdaki ayarları yapın:
   - **Configuration Name**: SvontAi WhatsApp Signup
   - **Callback URL**: `https://your-domain.com/api/onboarding/whatsapp/callback`
   - **Permissions**: `whatsapp_business_management`, `whatsapp_business_messaging`

### 4. OAuth Redirect URI

App Settings → Basic → Add Platform → Website:
```
https://your-domain.com/api/onboarding/whatsapp/callback
```

## 🔧 Ortam Değişkenleri

Backend `.env` dosyasına eklenecek değişkenler:

```bash
# Meta App Credentials
META_APP_ID=your-meta-app-id
META_APP_SECRET=your-meta-app-secret
META_REDIRECT_URI=https://your-domain.com/api/onboarding/whatsapp/callback
META_CONFIG_ID=your-embedded-signup-config-id

# Graph API
GRAPH_API_VERSION=v18.0

# Webhook
WEBHOOK_PUBLIC_URL=https://your-domain.com

# Encryption (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ENCRYPTION_KEY=your-fernet-key
```

### Environment Variable Açıklamaları

| Değişken | Açıklama | Nereden Alınır |
|----------|----------|----------------|
| `META_APP_ID` | Meta App ID | App Dashboard > Settings > Basic |
| `META_APP_SECRET` | App Secret | App Dashboard > Settings > Basic |
| `META_REDIRECT_URI` | OAuth callback URL | App'te kayıtlı olmalı |
| `META_CONFIG_ID` | Embedded Signup Config | WhatsApp > Configuration |
| `GRAPH_API_VERSION` | Graph API versiyonu | Genelde v18.0 veya v19.0 |
| `WEBHOOK_PUBLIC_URL` | Webhook için public URL | Sunucunuzun URL'i |
| `ENCRYPTION_KEY` | Token şifreleme anahtarı | Kendiniz oluşturun |

## 🔐 Güvenlik

### Token Şifreleme

Access tokenlar veritabanında **Fernet symmetric encryption** ile şifrelenir:

```python
from cryptography.fernet import Fernet

# Yeni key oluşturma
key = Fernet.generate_key()
print(key.decode())  # Bu değeri ENCRYPTION_KEY'e koyun
```

### Webhook Signature Doğrulama

Meta'dan gelen webhook istekleri `X-Hub-Signature-256` header'ı ile doğrulanır:

```python
import hmac
import hashlib

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

## 📡 API Endpoints

### Onboarding Endpoints

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/api/onboarding/whatsapp/start` | POST | Kurulumu başlatır, OAuth URL döner |
| `/api/onboarding/whatsapp/callback` | GET | OAuth callback handler |
| `/api/onboarding/whatsapp/status` | GET | Kurulum durumunu döner |
| `/api/onboarding/whatsapp/account` | GET | WhatsApp hesap bilgisi |
| `/api/onboarding/whatsapp/diagnostics` | GET | Konfigürasyon tanılama (`?live=true` ile canlı OAuth probe) |
| `/api/onboarding/whatsapp/reset` | POST | Kurulumu sıfırlar |

### Webhook Endpoints

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/whatsapp/webhook` | GET | Meta webhook doğrulama |
| `/whatsapp/webhook` | POST | Gelen mesajları işler |

## 🗄️ Veritabanı Şeması

### whatsapp_accounts

```sql
CREATE TABLE whatsapp_accounts (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    waba_id VARCHAR(50),
    phone_number_id VARCHAR(50),
    display_phone_number VARCHAR(20),
    business_id VARCHAR(50),
    app_id VARCHAR(50),
    access_token_encrypted TEXT,
    token_status VARCHAR(20) DEFAULT 'pending',
    token_expires_at TIMESTAMP,
    webhook_verify_token VARCHAR(100),
    webhook_status VARCHAR(30) DEFAULT 'not_configured',
    webhook_url VARCHAR(500),
    is_active BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

### onboarding_steps

```sql
CREATE TABLE onboarding_steps (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    provider VARCHAR(30) NOT NULL,
    step_key VARCHAR(50) NOT NULL,
    step_order INTEGER DEFAULT 0,
    step_name VARCHAR(100) NOT NULL,
    step_description VARCHAR(500),
    status VARCHAR(20) DEFAULT 'pending',
    message TEXT,
    metadata_json JSON,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL
);
```

### audit_logs

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    payload_json JSON,
    ip_address VARCHAR(50),
    user_agent VARCHAR(500),
    created_at TIMESTAMP NOT NULL
);
```

## 🔄 Kurulum Akışı

```
┌─────────────────────────────────────────────────────────────────┐
│                     WhatsApp Kurulum Akışı                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Kullanıcı "WhatsApp'ı Bağla" tıklar                        │
│              ↓                                                   │
│  2. Backend: /api/onboarding/whatsapp/start                     │
│     - Onboarding steps oluşturulur                              │
│     - Verify token oluşturulur                                  │
│     - OAuth URL döner                                           │
│              ↓                                                   │
│  3. Popup açılır → Meta OAuth sayfası                          │
│              ↓                                                   │
│  4. Kullanıcı WhatsApp Business seçer                          │
│              ↓                                                   │
│  5. Meta callback'e yönlendirir                                │
│     /api/onboarding/whatsapp/callback?code=xxx                  │
│              ↓                                                   │
│  6. Backend:                                                    │
│     - Code → Access Token exchange                              │
│     - Short-lived → Long-lived token                           │
│     - WABA ve Phone bilgileri çekilir                          │
│     - Token şifrelenerek kaydedilir                            │
│     - Webhook subscription yapılır                              │
│              ↓                                                   │
│  7. Meta webhook doğrulama isteği gönderir                     │
│     GET /whatsapp/webhook?hub.verify_token=xxx                  │
│              ↓                                                   │
│  8. Backend doğrular, challenge döner                          │
│              ↓                                                   │
│  9. Kurulum tamamlandı! ✅                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 📱 24 Saat Kuralı

WhatsApp Business API'de önemli bir kural:

1. **Kullanıcı başlattığı konuşmalar**: 24 saat içinde serbest mesaj gönderebilirsiniz
2. **24 saat sonra**: Yalnızca onaylanmış mesaj şablonları kullanılabilir

SvontAi bu kuralı otomatik olarak takip eder ve müşterilerinize zamanında yanıt verir.

## 🧪 Test Etme

### Local Development

Local geliştirme için [ngrok](https://ngrok.com) kullanın:

```bash
# ngrok'u başlatın
ngrok http 8000

# .env'de güncelleyin
WEBHOOK_PUBLIC_URL=https://abc123.ngrok.io
META_REDIRECT_URI=https://abc123.ngrok.io/api/onboarding/whatsapp/callback
```

### Webhook Test

```bash
# Webhook doğrulama testi
curl "http://localhost:8000/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test123"

# Başarılı yanıt: test123
```

## 🩺 “Geçersiz Sayfa” Hızlı Teşhis

1. Panelden `Dashboard > WhatsApp Kurulum > Tanılama` açın.
2. `META_REDIRECT_URI` ile `Beklenen callback` değerlerinin birebir aynı olduğunu doğrulayın.
3. `Canlı OAuth Probe` sonucu `ok` değilse:
   - `META_CONFIG_ID` yanlış app’e bağlı olabilir,
   - Meta App > **App Domains** ve **Valid OAuth Redirect URIs** eksik olabilir,
   - Redirect URI Meta panelinde farklı kayıtlı olabilir.
4. Gerekirse API ile doğrudan kontrol edin:

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  "https://<backend-domain>/api/onboarding/whatsapp/diagnostics?live=true"
```

## 🐛 Sorun Giderme

### "Invalid verify token" hatası

- Verify token'ın doğru olduğunu kontrol edin
- Tenant ID'nin doğru olduğundan emin olun
- Database'de `whatsapp_accounts` tablosunu kontrol edin

### "Token exchange failed" hatası

- `META_APP_SECRET`'ın doğru olduğunu kontrol edin
- Redirect URI'nin Meta App'te kayıtlı olduğundan emin olun

### Webhook mesajları gelmiyor

- Webhook URL'inin public olduğunu kontrol edin
- Meta App'te webhook subscription yapıldığını doğrulayın
- Logları kontrol edin: `docker logs svontai-backend`

## 📚 Faydalı Linkler

- [Meta for Developers](https://developers.facebook.com)
- [WhatsApp Business Platform](https://developers.facebook.com/docs/whatsapp)
- [Embedded Signup Documentation](https://developers.facebook.com/docs/whatsapp/embedded-signup)
- [Graph API Reference](https://developers.facebook.com/docs/graph-api)
- [Webhook Reference](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks)
