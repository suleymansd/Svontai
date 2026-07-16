# WhatsApp QR / OpenWA Kurulumu

SmartWA, OpenWA'yı ayrı bir WhatsApp gateway servisi olarak kullanır. Müşteri teknik ayar görmez; panelde QR kodu tarar ve tenant'a özel oturum otomatik oluşturulur.

## Railway OpenWA Servisi

1. Railway projesinde yeni bir servis oluşturun.
2. Kaynak olarak Docker image seçin:

```text
ghcr.io/rmyndharis/openwa:0.8.17
```

3. `/app/data` mount path'i için kalıcı volume ekleyin.
4. Tek replica kullanın.
5. Servise public domain oluşturun.
6. Şu environment değerlerini ekleyin:

```env
NODE_ENV=production
PORT=2785
DATABASE_TYPE=sqlite
ENGINE_TYPE=baileys
SESSION_DATA_PATH=/app/data/sessions
BAILEYS_AUTH_DIR=/app/data/baileys
BAILEYS_SYNC_FULL_HISTORY=false
RESOLVE_LID_TO_PHONE=true
AUTO_START_SESSIONS=true
MAX_CONCURRENT_SESSIONS=10
API_MASTER_KEY=<guclu-rastgele-api-key>
API_KEY_PEPPER=<farkli-guclu-rastgele-secret>
ENABLE_SWAGGER=false
WEBHOOK_SSRF_PROTECT=true
```

Secret üretmek için:

```bash
openssl rand -hex 32
```

Health kontrolü:

```text
https://<openwa-domain>/api/health/ready
```

## SmartWA Backend Environment

Railway'deki SmartWA backend servisine ekleyin:

```env
OPENWA_ENABLED=true
OPENWA_BASE_URL=https://<openwa-domain>
OPENWA_API_KEY=<OpenWA API_MASTER_KEY ile ayni>
OPENWA_WEBHOOK_SECRET=<farkli-guclu-rastgele-secret>
OPENWA_WEBHOOK_PUBLIC_URL=https://<smartwa-backend-domain>
OPENWA_TIMEOUT_SECONDS=20
```

Backend deploy sırasında `alembic upgrade head` çalışmalı ve migration head `037` olmalıdır.

## Çalışma Akışı

1. Müşteri `QR ile WhatsApp Bağla` seçeneğine basar.
2. SmartWA tenant'a özel OpenWA oturumu ve HMAC webhook oluşturur.
3. Müşteri telefondan QR kodu tarar.
4. Oturum `ready` olduğunda SmartWA hesabı aktif işaretler.
5. Gelen mesajlar SmartWA konuşma, AI, n8n, lead, randevu ve ticket akışına girer.
6. Giden mesajlar tenant'ın kendi OpenWA session ID'si üzerinden gönderilir.

## Güvenlik ve Operasyon

- OpenWA API anahtarı frontend'e veya tenant verisine yazılmaz.
- Webhook istekleri `X-OpenWA-Signature` HMAC-SHA256 imzasıyla doğrulanır.
- Aynı mesaj ID'si ikinci kez işlenmez.
- Grup mesajları ilk sürümde otomatik yanıta alınmaz.
- Rate limit hem SmartWA hem OpenWA katmanında uygulanır.
- OpenWA tek replica ve kalıcı disk ile çalıştırılmalıdır.
- `AUTO_START_SESSIONS=true` deploy veya crash sonrasında bağlı oturumları otomatik geri getirir.
- QR bağlantısı resmi Meta Cloud API değildir. Ana işletme numarası için hesap kısıtlama riski müşteriye açıkça gösterilir.
