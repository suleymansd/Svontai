# 📖 SvontAi Kullanım Kılavuzu

Hoş geldiniz! Bu kılavuz, SvontAi'ı en verimli şekilde kullanmanızı sağlayacak.

---

## 🎯 SvontAi Nedir?

SvontAi, işletmeniz için **AI destekli müşteri destek asistanı**dır. İki kanaldan müşterilerinize 7/24 otomatik yanıt verir:

1. **Web Widget** - Web sitenize eklenen sohbet balonu
2. **WhatsApp** - WhatsApp Business entegrasyonu

---

## 🚀 Hızlı Başlangıç (5 Dakikada)

### Adım 1: Hesap Oluşturun
1. [svontai.com](http://localhost:3000) adresine gidin
2. **"Ücretsiz Başla"** butonuna tıklayın
3. Bilgilerinizi girin ve kayıt olun

### Adım 2: İlk Botunuzu Oluşturun
1. Dashboard'da **"Yeni Bot Oluştur"** butonuna tıklayın
2. Bot adı girin (örn: "Müşteri Destek")
3. Karşılama mesajı yazın
4. **"Bot Oluştur"** butonuna tıklayın

### Adım 3: AI'ı Eğitin
1. Oluşturduğunuz botun **"Eğit"** butonuna tıklayın
2. İşletmeniz hakkında bilgiler ekleyin
3. Minimum 5-10 bilgi öğesi ekleyin

### Adım 4: Test Edin
1. Widget test sayfasını açın
2. Botunuza sorular sorun
3. Yanıtları kontrol edin

---

## 🤖 Bot Yönetimi

### Bot Oluşturma

```
Dashboard → Botlar → Yeni Bot Oluştur
```

| Alan | Açıklama | Örnek |
|------|----------|-------|
| Bot Adı | Botunuzun adı | Müşteri Destek |
| Açıklama | Ne işe yaradığı | 7/24 müşteri desteği |
| Karşılama Mesajı | İlk mesaj | Merhaba! 👋 Size nasıl yardımcı olabilirim? |

### Bot Ayarları

Her bot için özelleştirilebilir:

- **Ana Renk**: Widget'ın teması
- **Widget Pozisyonu**: Sağ veya sol
- **Dil**: Varsayılan Türkçe
- **Aktif/Pasif**: Botu açıp kapatma

---

## 🧠 AI Bilgi Tabanı

### Nasıl Çalışır?

```
Siz: Bilgi eklersiniz
     ↓
Müşteri: Soru sorar
     ↓
AI: Bilgilerinizi kullanarak akıllı yanıt üretir
```

### Etkili Bilgi Ekleme İpuçları

#### ✅ İyi Örnek:
```
Başlık: Kargo Bilgisi
Örnek Soru: Kargo ne kadar? Ne zaman gelir?
Bilgi: 150 TL üzeri siparişlerde kargo ücretsizdir. 
       Altında 29.90 TL. Teslimat süresi 2-3 iş günüdür.
       İstanbul içi siparişler 1 iş günü içinde teslim edilir.
```

#### ❌ Kötü Örnek:
```
Başlık: Kargo
Soru: Kargo?
Bilgi: Var.
```

### Önerilen Bilgi Kategorileri

1. **Genel Bilgiler**
   - Çalışma saatleri
   - Adres ve iletişim
   - Hakkımızda

2. **Ürün/Hizmet**
   - Fiyatlar
   - Özellikler
   - Stok durumu

3. **Sipariş Süreci**
   - Nasıl sipariş verilir
   - Ödeme yöntemleri
   - Kargo bilgileri

4. **Destek**
   - İade politikası
   - Garanti koşulları
   - Sık sorulan sorular

### Kaç Bilgi Eklemeliyim?

| Bot Kalitesi | Minimum Bilgi |
|--------------|---------------|
| ⭐ Temel | 5-10 öğe |
| ⭐⭐ İyi | 10-25 öğe |
| ⭐⭐⭐ Harika | 25+ öğe |

---

## 💬 Web Widget

### Widget Kodunu Alma

1. Bot sayfasına gidin
2. **Widget Key**'i kopyalayın
3. Aşağıdaki kodu web sitenize ekleyin:

```html
<!-- SvontAi Widget -->
<script>
  window.SVONTAI_CONFIG = {
    botKey: 'BOT_PUBLIC_KEY_BURAYA'
  };
</script>
<script src="https://api.svontai.com/widget.js" async></script>
```

### Widget Özelleştirme

```javascript
window.SVONTAI_CONFIG = {
  botKey: 'xxx',
  position: 'right',     // veya 'left'
  primaryColor: '#6366f1', // Tema rengi
  welcomeMessage: 'Merhaba! 👋',
  placeholder: 'Mesajınızı yazın...'
};
```

### Widget Test Etme

Canlıya almadan önce test edin:
```
http://localhost:3000/widget-test.html
```

---

## 📱 WhatsApp Entegrasyonu

Detaylı kurulum için: [WHATSAPP_KURULUM.md](./WHATSAPP_KURULUM.md)

### Kısa Özet:

1. Meta Business hesabı oluşturun
2. WhatsApp Business API erişimi alın
3. Telefon numarası doğrulayın
4. API bilgilerini SvontAi'a girin
5. Webhook yapılandırın

---

## 👥 Lead Yönetimi

### Lead Nedir?

Potansiyel müşteri bilgisi. Bot sohbet sırasında şu bilgileri toplayabilir:
- İsim
- E-posta
- Telefon
- Notlar

### Lead'leri Görüntüleme

```
Dashboard → Leadler
```

### Lead Dışa Aktarma

1. **"Dışa Aktar"** butonuna tıklayın
2. CSV dosyası indirilir
3. Excel veya CRM'e aktarabilirsiniz

---

## 💬 Konuşmalar

### Konuşmaları İzleme

```
Dashboard → Konuşmalar
```

Burada görebilirsiniz:
- Tüm müşteri konuşmaları
- Mesaj geçmişi
- Kaynak (Web/WhatsApp)
- Durum (Aktif/Kapalı)

### Konuşma Detayları

Bir konuşmaya tıklayarak:
- Tüm mesaj geçmişini görün
- AI'ın verdiği yanıtları inceleyin
- Müşteri memnuniyetini değerlendirin

---

## ⚙️ Ayarlar

### Profil Ayarları
- Ad soyad güncelleme
- E-posta değiştirme
- Tema tercihi (Açık/Koyu)

### İşletme Ayarları
- İşletme adı
- Logo
- Web sitesi

### Güvenlik
- Şifre değiştirme
- İki faktörlü doğrulama (yakında)

### API Anahtarları
- API key görüntüleme
- Yeni anahtar oluşturma

---

## 📊 İstatistikler (Dashboard)

Dashboard'da şunları görebilirsiniz:

| Metrik | Açıklama |
|--------|----------|
| Toplam Bot | Oluşturduğunuz bot sayısı |
| Aktif Bot | Şu an çalışan botlar |
| Toplam Lead | Toplanan müşteri bilgisi |
| Yanıt Oranı | AI'ın başarı oranı |

---

## ❓ Sık Sorulan Sorular

### AI yanlış cevap veriyor, ne yapmalıyım?

1. Bilgi tabanınızı kontrol edin
2. Daha detaylı bilgi ekleyin
3. Örnek soruları çeşitlendirin

### Müşteri bot yerine insanla konuşmak istiyor?

AI, emin olmadığı durumlarda:
```
"Bu konuda size yardımcı olamıyorum. 
Lütfen 0850 XXX XX XX numarasından bize ulaşın."
```
şeklinde yönlendirir.

### WhatsApp mesajları gelmiyor?

1. Webhook URL'ini kontrol edin
2. Access token'ın geçerli olduğunu doğrulayın
3. Bot'un aktif olduğundan emin olun

### Widget görünmüyor?

1. Bot key'in doğru olduğunu kontrol edin
2. Script'in sayfaya yüklendiğini doğrulayın
3. Tarayıcı konsolunda hata var mı bakın

---

## 🎓 En İyi Pratikler

### 1. Bilgi Tabanını Güncel Tutun
- Yeni ürünler ekleyin
- Fiyat değişikliklerini güncelleyin
- Kampanyaları ekleyin

### 2. Konuşmaları Düzenli İnceleyin
- Müşterilerin en çok neyi sorduğunu görün
- Eksik bilgileri tamamlayın
- AI'ın yanlış cevaplarını düzeltin

### 3. Karşılama Mesajını Optimize Edin
Kısa ve yönlendirici olsun:
```
"Merhaba! 👋 Size şu konularda yardımcı olabilirim:
• Ürün bilgileri
• Sipariş takibi
• İade işlemleri
Nasıl yardımcı olabilirim?"
```

### 4. Test Edin, Test Edin, Test Edin
- Farklı sorular sorun
- Arkadaşlarınıza test ettirin
- Edge case'leri deneyin

---

## 📞 Destek Kanalları

| Kanal | Kullanım |
|-------|----------|
| 📧 support@svontai.com | Genel destek |
| 📚 docs.svontai.com | Teknik dökümanlar |
| 💬 Dashboard Canlı Destek | Acil sorunlar |

---

## 🔄 Güncelleme Notları

### v1.0.0 (Aralık 2024)
- ✅ İlk sürüm yayınlandı
- ✅ Web widget desteği
- ✅ WhatsApp entegrasyonu
- ✅ AI bilgi tabanı
- ✅ Lead yönetimi
- ✅ Admin paneli

---

**İyi çalışmalar! 🚀**

*SvontAi Ekibi*

