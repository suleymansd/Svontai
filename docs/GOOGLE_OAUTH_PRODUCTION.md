# Google Calendar Production OAuth

SvontAI yalnızca randevu uygunluğu ve takvim kaydı için gerekli minimum Calendar izinlerini ister:

```text
openid
email
profile
https://www.googleapis.com/auth/calendar.events
https://www.googleapis.com/auth/calendar.events.freebusy
```

Drive, Gmail ve Sheets izinleri bu akışa eklenmemelidir. Uygulamada bu servisler için çalışan bir müşteri OAuth akışı bulunmadığından bağlantı düğmeleri gösterilmez.

## Google Cloud Kontrol Listesi

1. Google Calendar API'yi production projesinde etkinleştirin.
2. Google Auth Platform > Branding bölümünde uygulama adı, `info@svontai.com`, ana sayfa, gizlilik ve kullanım şartları URL'lerini tanımlayın.
3. Authorized domains alanına `svontai.com` ekleyin ve domain sahipliğini doğrulayın.
4. Audience bölümünü External ve In production olarak ayarlayın.
5. Data Access bölümüne yalnızca yukarıdaki kapsamları ekleyin.
6. OAuth Web Client authorized redirect URI değerini backend ayarıyla birebir eşleştirin:

```text
https://svontai-production.up.railway.app/real-estate/calendar/google/callback
```

7. Verification Center üzerinden brand ve sensitive scope doğrulamasını gönderin. Calendar bağlantısının randevu uygunluğu okuduğunu ve onaylanan randevuyu takvime yazdığını gösteren bir inceleme videosu ekleyin.
8. Google onayı tamamlandıktan sonra Railway API servisinde aşağıdaki değeri ayarlayıp yeniden deploy edin:

```env
GOOGLE_OAUTH_PUBLIC_ENABLED=true
```

Onay tamamlanmadan bu değer `false` kalmalıdır. Böylece müşteriler Google'ın "unverified app" güvenlik ekranına gönderilmez.

## OpenWA Gateway Güncellemesi

Railway'deki ayrı OpenWA servisinin image kaynağını aşağıdaki sabit sürüme güncelleyin:

```text
ghcr.io/rmyndharis/openwa:0.23.4
```

Mevcut `/app/data` volume'u silmeyin veya değiştirmeyin. Tek replica kullanın. Deploy sonrasında `/api/health/ready` yanıtını ve mevcut oturumları kontrol edin. Bu sürüm QR tarandıktan sonraki `authenticating` geçişini ve geçersiz QR önbelleği yarışlarını düzeltir.
