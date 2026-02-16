export default function TermsPage() {
  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold">Kullanım Koşulları</h1>
        <p className="text-sm text-muted-foreground">Son güncelleme: 16 Şubat 2026</p>
      </header>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">1. Hizmet Kapsamı</h2>
        <p className="text-muted-foreground">
          SvontAI; çok kiracılı (multi-tenant) SaaS altyapısı, mesajlaşma otomasyonu, araç yönetimi, raporlama
          ve entegrasyon özellikleri sunar. Özellik kapsamı plan seviyesine göre değişebilir.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">2. Hesap Sorumluluğu</h2>
        <p className="text-muted-foreground">
          Kullanıcı; hesap erişim bilgilerinin gizliliğinden, ekip kullanıcı yetkilerinden ve entegrasyon
          anahtarlarının güvenli saklanmasından sorumludur.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">3. Kullanım Kuralları</h2>
        <p className="text-muted-foreground">
          Platform; yasalara aykırı, spam niteliğinde veya üçüncü taraf haklarını ihlal eden amaçlarla
          kullanılamaz. WhatsApp ve diğer sağlayıcı politikalarına uyum kullanıcı sorumluluğundadır.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">4. Planlar ve Ödeme</h2>
        <p className="text-muted-foreground">
          Ücretli plan yükseltmeleri ödeme sağlayıcısı üzerinden tamamlanır. Plan limitleri aşıldığında ilgili
          özellikler geçici olarak sınırlandırılabilir.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">5. Hizmet Sürekliliği</h2>
        <p className="text-muted-foreground">
          Planlı bakım, üçüncü taraf kesintileri veya güvenlik gerekçeleri nedeniyle hizmette geçici aksama
          yaşanabilir. Ekip mümkün olan en kısa sürede toparlama sağlar.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">6. Fesih ve İptal</h2>
        <p className="text-muted-foreground">
          Hesap sahibi aboneliğini panel üzerinden iptal edebilir. Ciddi ihlal durumlarında platform, hesabı
          geçici veya kalıcı olarak askıya alma hakkını saklı tutar.
        </p>
      </section>
    </main>
  )
}
