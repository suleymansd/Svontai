export default function PrivacyPage() {
  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold">Gizlilik Politikası</h1>
        <p className="text-sm text-muted-foreground">Son güncelleme: 16 Şubat 2026</p>
      </header>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">1. Toplanan Veriler</h2>
        <p className="text-muted-foreground">
          SvontAI; hesap bilgileri, iletişim kayıtları, entegrasyon yapılandırmaları, kullanım metrikleri ve
          destek taleplerini hizmetin sunulması amacıyla işler.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">2. Kullanım Amaçları</h2>
        <p className="text-muted-foreground">
          Veriler; hesap yönetimi, mesajlaşma otomasyonu, raporlama, güvenlik doğrulaması, hata analizi ve
          mevzuata uyum süreçleri için kullanılır.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">3. Saklama ve Güvenlik</h2>
        <p className="text-muted-foreground">
          Erişim yetkilendirmesi, tenant izolasyonu, şifreleme ve denetim logları uygulanır. Hassas anahtarlar
          maskeli gösterilir, ham değerler yalnızca oluşturma anında paylaşılır.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">4. Üçüncü Taraf Servisler</h2>
        <p className="text-muted-foreground">
          WhatsApp Cloud API, e-posta sağlayıcıları ve ödeme altyapıları gibi servislerle entegrasyon sırasında
          gerekli asgari veri paylaşılır. Her entegrasyon kendi hizmet koşullarına tabidir.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">5. Haklarınız</h2>
        <p className="text-muted-foreground">
          Hesap sahibi, veriye erişim, düzeltme ve silme taleplerini destek kanalları üzerinden iletebilir.
          Yasal yükümlülükler kapsamında saklanması gereken kayıtlar hariç talepler değerlendirilir.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">6. İletişim</h2>
        <p className="text-muted-foreground">
          Gizlilik talepleriniz için hesap içi destek ekranını kullanabilir veya kayıtlı destek e-posta
          kanalından bizimle iletişime geçebilirsiniz.
        </p>
      </section>
    </main>
  )
}
