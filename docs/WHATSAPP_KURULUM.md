# 📱 WhatsApp Entegrasyonu Kurulum Rehberi

Bu rehber, SvontAi'ı WhatsApp Business API ile entegre etmenizi adım adım anlatır.

---

## 📋 İçindekiler

1. [Gereksinimler](#gereksinimler)
2. [Meta Business Suite Kurulumu](#1-meta-business-suite-kurulumu)
3. [WhatsApp Business API Erişimi](#2-whatsapp-business-api-erişimi)
4. [API Kimlik Bilgilerini Alma](#3-api-kimlik-bilgilerini-alma)
5. [SvontAi'da Entegrasyonu Kurma](#4-svontaida-entegrasyonu-kurma)
6. [Webhook Yapılandırması](#5-webhook-yapılandırması)
7. [Test Etme](#6-test-etme)
8. [Sorun Giderme](#7-sorun-giderme)

---

## Gereksinimler

Başlamadan önce aşağıdakilere sahip olduğunuzdan emin olun:

| Gereksinim | Açıklama |
|------------|----------|
| ✅ Facebook Hesabı | Meta Business Suite için gerekli |
| ✅ WhatsApp Business Hesabı | Normal WhatsApp değil, Business versiyonu |
| ✅ İşletme Belgesi | Vergi levhası veya ticaret sicil belgesi |
| ✅ Domain (Alan Adı) | Webhook için gerekli (örn: api.siteniz.com) |
| ✅ SSL Sertifikası | HTTPS zorunlu |
| ✅ SvontAi Hesabı | Sistemde kayıtlı olmanız gerekli |

---

## 1. Meta Business Suite Kurulumu

### 1.1 Business Manager Hesabı Oluşturun

1. [business.facebook.com](https://business.facebook.com) adresine gidin
2. **"Hesap Oluştur"** butonuna tıklayın
3. İşletme bilgilerinizi girin:
   - İşletme adı
   - Adınız soyadınız
   - İş e-postası
4. **"Gönder"** butonuna tıklayın
5. E-postanızı doğrulayın

### 1.2 İşletmenizi Doğrulayın

1. Business Manager'da **Ayarlar** → **İşletme Bilgileri** → **İşletme Doğrulama** bölümüne gidin
2. **"Doğrulamayı Başlat"** butonuna tıklayın
3. Gerekli belgeleri yükleyin:
   - Vergi levhası
   - Ticaret sicil belgesi
   - Faaliyet belgesi (herhangi biri yeterli)
4. Doğrulama genellikle 1-3 iş günü sürer

> ⚠️ **Önemli:** İşletme doğrulaması olmadan WhatsApp Business API kullanamazsınız!

---

## 2. WhatsApp Business API Erişimi

### 2.1 WhatsApp Business Hesabı Oluşturun

1. [developers.facebook.com](https://developers.facebook.com) adresine gidin
2. Sağ üstten **"Başlayın"** veya **"Uygulamalarım"** tıklayın
3. **"Uygulama Oluştur"** butonuna tıklayın
4. Uygulama türü olarak **"Business"** seçin
5. Uygulama bilgilerini girin:
   - Uygulama adı: `SvontAi WhatsApp Bot`
   - E-posta: İş e-postanız
   - Business Account: Oluşturduğunuz Business Manager

### 2.2 WhatsApp Ürününü Ekleyin

1. Uygulama Dashboard'unda **"Ürün Ekle"** bölümüne gidin
2. **"WhatsApp"** kartında **"Kurulum"** butonuna tıklayın
3. WhatsApp Business hesabınızı seçin veya yeni oluşturun

### 2.3 Telefon Numarası Ekleyin

1. WhatsApp → **Başlangıç** → **API Kurulumu** bölümüne gidin
2. **"Telefon numarası ekle"** butonuna tıklayın
3. İşletme telefon numaranızı girin
4. SMS veya arama ile doğrulayın

> 💡 **İpucu:** Bu numara WhatsApp Business uygulamasında aktif olmamalı!

---

## 3. API Kimlik Bilgilerini Alma

WhatsApp API için 4 önemli bilgiye ihtiyacınız var:

### 3.1 Phone Number ID (Telefon Numarası ID)

1. [developers.facebook.com](https://developers.facebook.com) → Uygulamanız
2. **WhatsApp** → **API Kurulumu**
3. **"Gönderen"** bölümünde Phone Number ID'yi bulun
4. Örnek: `123456789012345`

### 3.2 WhatsApp Business Account ID

1. Aynı sayfada **"WhatsApp Business Account ID"** bölümünü bulun
2. Örnek: `987654321098765`

### 3.3 Access Token (Erişim Anahtarı)

**Geçici Token (Test için):**
1. API Kurulumu sayfasında **"Geçici erişim anahtarı"** bölümünü bulun
2. **"Oluştur"** butonuna tıklayın
3. Bu token 24 saat geçerlidir

**Kalıcı Token (Üretim için):**
1. **İşletme Ayarları** → **Sistem Kullanıcıları** bölümüne gidin
2. **"Ekle"** butonuna tıklayın
3. Sistem kullanıcısı oluşturun (Admin rolü verin)
4. **"Token Oluştur"** butonuna tıklayın
5. WhatsApp Business messaging izinlerini seçin
6. Bu token süresiz geçerlidir

### 3.4 Webhook Verify Token

Bu, sizin belirlediğiniz gizli bir şifredir:
- Kendiniz oluşturun (örn: `svontai_webhook_secret_123`)
- Güvenli ve tahmin edilemez olsun
- Bu değeri iki yerde kullanacaksınız

---

## 4. SvontAi'da Entegrasyonu Kurma

### 4.1 Bot Oluşturun

1. SvontAi Dashboard'a giriş yapın
2. **Botlar** → **Yeni Bot Oluştur**
3. Bot bilgilerini girin:
   - Bot Adı: `WhatsApp Destek`
   - Açıklama: WhatsApp müşteri destek botu
   - Karşılama Mesajı: `Merhaba! 👋 Size nasıl yardımcı olabilirim?`

### 4.2 Bilgi Tabanını Doldurun

1. Bot'un **"Eğit"** butonuna tıklayın
2. İşletmeniz hakkında bilgiler ekleyin:
   - Çalışma saatleri
   - Ürün/hizmet bilgileri
   - İletişim bilgileri
   - Sık sorulan sorular

### 4.3 WhatsApp Entegrasyonunu Ekleyin

1. Bot ayarlarında **"WhatsApp Entegrasyonu"** bölümüne gidin
2. Aşağıdaki bilgileri girin:

```
Phone Number ID: [Meta'dan aldığınız Phone Number ID]
Business Account ID: [Meta'dan aldığınız WABA ID]
Access Token: [Oluşturduğunuz kalıcı token]
Webhook Verify Token: [Belirlediğiniz gizli şifre]
```

3. **"Kaydet"** butonuna tıklayın

---

## 5. Webhook Yapılandırması

Webhook, WhatsApp'tan gelen mesajları SvontAi'a iletir.

### 5.1 Sunucu Gereksinimi

SvontAi backend'iniz internetten erişilebilir olmalı:

```
https://api.siteniz.com  (Örnek)
```

**Seçenekler:**
- VPS/Cloud sunucu (AWS, DigitalOcean, Hetzner)
- Heroku, Railway, Render gibi PaaS platformları
- Ngrok (sadece test için)

### 5.2 Meta'da Webhook Ayarlama

1. [developers.facebook.com](https://developers.facebook.com) → Uygulamanız
2. **WhatsApp** → **Yapılandırma** → **Webhook**
3. **"Düzenle"** butonuna tıklayın
4. Aşağıdaki bilgileri girin:

```
Callback URL: https://api.siteniz.com/whatsapp/webhook
Verify Token: [SvontAi'da belirlediğiniz aynı token]
```

5. **"Doğrula ve Kaydet"** butonuna tıklayın

### 5.3 Webhook Alanlarını Seçin

Webhook yapılandırmasında şu alanları **abone olun**:

| Alan | Açıklama |
|------|----------|
| ✅ `messages` | Gelen mesajlar |
| ✅ `message_deliveries` | Teslimat durumları |
| ✅ `message_reads` | Okundu bilgisi |

---

## 6. Test Etme

### 6.1 Hızlı Test

1. WhatsApp entegrasyonu olan telefon numaranıza mesaj gönderin
2. SvontAi Dashboard'da **Konuşmalar** bölümünü kontrol edin
3. Mesajın geldiğini ve AI'ın yanıt verdiğini doğrulayın

### 6.2 Test Mesajı Gönderme

Meta Dashboard'dan test mesajı gönderebilirsiniz:

1. WhatsApp → API Kurulumu
2. **"Test mesajı gönder"** bölümünü bulun
3. Alıcı numarasını girin
4. Mesaj gönderin

### 6.3 Webhook Test

```bash
# Webhook'un çalıştığını kontrol edin
curl -X GET "https://api.siteniz.com/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test123"

# Başarılı yanıt: test123
```

---

## 7. Sorun Giderme

### ❌ "Webhook doğrulanamadı" hatası

**Nedenler:**
- Verify token eşleşmiyor
- URL erişilemiyor
- SSL sertifikası geçersiz

**Çözüm:**
```bash
# URL'in erişilebilir olduğunu kontrol edin
curl -I https://api.siteniz.com/whatsapp/webhook

# Token'ların eşleştiğinden emin olun
```

### ❌ Mesajlar gelmiyor

**Kontrol listesi:**
1. ✅ Webhook alanlarına abone oldunuz mu?
2. ✅ Access token geçerli mi?
3. ✅ Telefon numarası doğrulandı mı?
4. ✅ Bot aktif mi?

### ❌ "Token süresi doldu" hatası

**Çözüm:**
- Geçici token yerine kalıcı sistem kullanıcısı token'ı oluşturun
- Token'ı SvontAi'da güncelleyin

### ❌ Mesajlar gidiyor ama cevap gelmiyor

**Kontrol listesi:**
1. ✅ Bilgi tabanı dolu mu?
2. ✅ OpenAI API key geçerli mi?
3. ✅ Backend loglarını kontrol edin

---

## 📊 Maliyet Bilgisi

### Meta (WhatsApp) Ücretleri

| Konuşma Türü | İlk 1000/ay | Sonrası |
|--------------|-------------|---------|
| Kullanıcı başlattı | ÜCRETSİZ | ~$0.005 |
| İşletme başlattı | ~$0.03 | ~$0.03 |

> 💡 Kullanıcı mesaj attığında açılan konuşmalar daha ucuz!

### SvontAi Ücretleri

OpenAI API kullanım maliyeti hesabınıza yansır.
Ortalama maliyet: ~$0.002 per mesaj

---

## 🚀 Üretime Geçiş Kontrol Listesi

Canlıya almadan önce:

- [ ] İşletme doğrulaması tamamlandı
- [ ] Kalıcı access token oluşturuldu
- [ ] Webhook HTTPS üzerinden çalışıyor
- [ ] SSL sertifikası geçerli
- [ ] Bilgi tabanı yeterli içerikle dolu
- [ ] Test mesajları başarılı
- [ ] Yedek iletişim bilgileri eklendi
- [ ] Hata bildirimleri aktif

---

## 📞 Destek

Sorun yaşarsanız:

- 📧 E-posta: support@svontai.com
- 📚 Dokümantasyon: https://docs.svontai.com
- 💬 Canlı destek: Dashboard içinden

---

**Son güncelleme:** Aralık 2024

