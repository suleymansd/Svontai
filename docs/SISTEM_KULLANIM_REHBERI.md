# SvontAI Sistem Kullanım Rehberi

Bu rehber, **kullanıcı paneli** ve **super admin paneli** için standart kullanım akışını özetler.

## 1) Kullanıcı Paneli (Tenant)

### İlk kurulum
1. Kayıt ol, e-posta doğrulamasını tamamla.
2. Giriş yap ve tenant bilgilerini kontrol et.
3. `Botlarım` ekranından ilk botu oluştur.
4. `Tool Kataloğu`ndan gerekli toolları seç.
5. `WhatsApp Kurulum` adımlarını tamamla.

### Günlük operasyon
1. `Konuşmalar` ekranından mesajları takip et.
2. `Leadler` ekranında lead durumlarını güncelle.
3. Tool sayfalarından (entegrasyon + iç düzenleme) işlemleri yönet.
4. `Analitikler` ve `Kullanım` ekranlarından performans/limit takibi yap.
5. `Ayarlar` altında güvenlik ve bildirimleri düzenli kontrol et.

## 2) Super Admin Paneli (Şirket Yönetimi)

### Güvenli giriş
- Super admin için `/admin/login` veya `/login?portal=super_admin` kullan.
- Üretimde `SUPER_ADMIN_REQUIRE_2FA=true` önerilir.
- Super admin girişinde oturum notu zorunlu tutulur (audit kaydı için).

### Tenant yönetimi
1. `Tenantlar` ekranından müşteri tenantını seç.
2. Gerekirse “Müşteri Paneline Geç” ile tenant context aç.
3. Plan / tool / feature flag değişikliklerini admin panelinden uygula.
4. `Audit Logs` ve `Hata Merkezi` üzerinden değişiklik etkisini doğrula.

## 3) Canlıya Alma Kontrol Listesi

- Railway:
  - `DATABASE_URL`
  - `JWT_SECRET_KEY`
  - `FRONTEND_URL`
  - `BACKEND_URL`
- Mail:
  - `EMAIL_ENABLED=true`
  - `RESEND_API_KEY`
- WhatsApp:
  - `META_APP_ID`
  - `META_APP_SECRET`
  - `META_CONFIG_ID`
  - `META_REDIRECT_URI`
- Voice Gateway:
  - `VOICE_GATEWAY_TO_SVONTAI_SECRET`
- Vercel:
  - `NEXT_PUBLIC_BACKEND_URL`
- Güvenlik:
  - `SUPER_ADMIN_REQUIRE_2FA=true`

## 4) Sistem İçi Rehber Sayfaları

- Kullanıcı paneli rehberi: `/dashboard/help`
- WhatsApp kurulum rehberi: `/dashboard/help/whatsapp-setup`
- Super admin rehberi: `/admin/help`
