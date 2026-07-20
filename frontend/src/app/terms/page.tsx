export default function TermsPage() {
  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold">Kullanım Koşulları</h1>
        <p className="text-sm text-muted-foreground">Son güncelleme: 20 Temmuz 2026</p>
        <p className="text-muted-foreground">
          Bu koşullar SvontAI&apos;nin self-serve ve concierge kurulum, WhatsApp AI, randevu, lead, destek ve ajans/kurumsal yönetim özelliklerini kapsar.
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">1. Hizmet Kapsamı</h2>
        <p className="text-muted-foreground">
          SvontAI; işletmeler için WhatsApp odaklı AI asistan, bot yönetimi, mesaj/lead/randevu takibi, entegrasyon sağlık kontrolü, concierge kurulum ve operasyon araçları sunar. Canlı telefon araması henüz sunulmaz; paneldeki arama alanı yalnızca test modunda çalışır. Özellikler plan, kullanım hakkı ve entegrasyon durumuna göre değişebilir.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">2. Kurulum Modları</h2>
        <p className="text-muted-foreground">
          Self-serve kurulumda işletme bilgilerini siz girersiniz. Concierge kurulumda minimum bilgiyi paylaşırsınız; ekibimiz bilgi formasyonu ve yayına hazırlık sürecini yönetir. WhatsApp, ödeme, dış servis yetkilendirme ve müşteri adına riskli işlem gerektiren aksiyonlarda açık onayınız gerekir.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">3. Hesap ve Yetki Sorumluluğu</h2>
        <p className="text-muted-foreground">
          Hesap erişimi, ekip yetkileri, entegrasyon anahtarları, müşteri verilerinin doğruluğu ve üçüncü taraf servislerdeki izinler hesabı yöneten işletmenin sorumluluğundadır. Şüpheli erişim veya yanlış yetkilendirme durumunda destek ekibine bildirim yapılmalıdır.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">4. Kabul Edilebilir Kullanım</h2>
        <p className="text-muted-foreground">
          Platform spam, izinsiz pazarlama, aldatıcı iletişim, yasa dışı içerik, hassas verilerin yetkisiz işlenmesi, üçüncü taraf haklarının ihlali veya sağlayıcı politikalarına aykırı kullanım için kullanılamaz. Meta WhatsApp, ödeme, e-posta ve telefon sağlayıcılarının kurallarına uyum müşteriye aittir.
        </p>
        <p className="text-muted-foreground">
          QR tabanlı WhatsApp bağlantısı resmi Meta Cloud API değildir. Bu yöntem seçildiğinde bağlantı kesintisi veya WhatsApp hesabı kısıtlaması riski bulunduğu kullanıcıya gösterilir ve açık onay alınır.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">5. AI Çıktıları ve Otonomi</h2>
        <p className="text-muted-foreground">
          Sistem güvenli otonomi prensibiyle çalışır; rutin yanıt, tanılama, retry, incident ve ticket akışlarını otomatik yürütebilir. AI çıktıları hatalı veya eksik olabilir. Hukuki, tıbbi, finansal veya yüksek riskli kararlar için insan kontrolü ve işletme onayı gerekir.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">6. Ödeme, Plan ve Limitler</h2>
        <p className="text-muted-foreground">
          Lansman döneminde plan başvuruları görüşme yoluyla alınır; ücret, dönem ve hizmet kapsamı ayrıca yazılı olarak mutabık kalındıktan sonra plan yönetici tarafından etkinleştirilir. Platform içinde kartla ödeme alınmaz. Plan limitleri ve özellik erişimleri kullanım hakkı sistemiyle uygulanır. Süresi dolan veya iptal edilen planlarda bazı özellikler sınırlandırılabilir.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">7. Hizmet Sürekliliği</h2>
        <p className="text-muted-foreground">
          Planlı bakım, güvenlik önlemleri, sağlayıcı kesintileri, rate limit, ağ sorunları veya entegrasyon hataları nedeniyle hizmette geçici aksama olabilir. Sistem mümkün olan durumlarda otomatik retry, health check ve incident/ticket akışlarını çalıştırır.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">8. Askıya Alma ve Fesih</h2>
        <p className="text-muted-foreground">
          Güvenlik riski, kötüye kullanım, ödeme sorunu veya sağlayıcı politikalarının ihlali halinde hesap, tenant veya entegrasyon geçici olarak sınırlandırılabilir. Hesap sahibi aboneliğini panel veya destek kanalı üzerinden iptal edebilir.
        </p>
      </section>
    </main>
  )
}
