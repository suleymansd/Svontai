export default function PrivacyPage() {
  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold">Gizlilik ve KVKK Bilgilendirmesi</h1>
        <p className="text-sm text-muted-foreground">Son güncelleme: 20 Temmuz 2026</p>
        <p className="text-muted-foreground">
          Bu metin SvontAI platformunun hangi verileri hangi amaçlarla işlediğini açıklar. Müşterilerinizle ilgili verilerde işletmeniz veri sorumlusu, SvontAI ise hizmet sağlayıcı/alt işleyen rolünde hareket eder.
        </p>
      </header>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">1. İşlenen Veri Kategorileri</h2>
        <p className="text-muted-foreground">
          Hesap bilgileri, işletme profili, kullanıcı yetkileri, WhatsApp konuşmaları, müşteri iletişim bilgileri, lead ve randevu kayıtları, arama kayıtları, çağrı özetleri, destek talepleri, ödeme/abonelik durumu, entegrasyon ayarları, sistem olayları ve güvenlik logları işlenebilir.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">2. İşleme Amaçları</h2>
        <p className="text-muted-foreground">
          Veriler; hesabın açılması, otonom kurulumun yürütülmesi, botların hazırlanması, WhatsApp mesajlarının yanıtlanması, lead/randevu/ticket akışlarının oluşturulması, AI arama otomasyonunun çalıştırılması, ödeme ve entitlement yönetimi, güvenlik, hata analizi, audit log ve müşteri desteği için kullanılır.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">3. Concierge Kurulum ve İşletme Bilgisi</h2>
        <p className="text-muted-foreground">
          “Biz Kuralım” seçeneğinde paylaştığınız işletme bilgileri, web sitesi, sosyal medya bağlantıları ve destek notları ekibimiz tarafından bot bilgi formasyonunu hazırlamak için kullanılabilir. Eksik bilgi olduğunda destek/ticket süreci üzerinden ek bilgi istenebilir.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">4. Üçüncü Taraflar ve Aktarımlar</h2>
        <p className="text-muted-foreground">
          Hizmet kapsamında Meta WhatsApp Cloud API veya kullanıcı tarafından seçilen QR tabanlı WhatsApp bağlantı altyapısı, ödeme sağlayıcısı, e-posta sağlayıcısı, ses/telefon sağlayıcısı, n8n otomasyon altyapısı, dosya saklama altyapısı ve AI model sağlayıcılarıyla gerekli asgari veri paylaşılabilir. Her entegrasyon kendi hizmet koşulları ve veri işleme kurallarına tabidir.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">5. Güvenlik ve Erişim</h2>
        <p className="text-muted-foreground">
          Platform tenant izolasyonu, rol tabanlı erişim, audit log, rate limit, webhook imza kontrolü, hesap kilitleme, kısa ömürlü access token ve güvenli refresh cookie yaklaşımıyla korunur. Buna rağmen hiçbir internet hizmeti mutlak güvenlik garantisi veremez.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">6. Saklama ve Silme</h2>
        <p className="text-muted-foreground">
          Veriler hizmet ilişkisi, yasal yükümlülükler, güvenlik kayıtları ve operasyonel gereklilikler devam ettiği sürece saklanır. Hesap sahibi panel veya destek kanalı üzerinden erişim, düzeltme, dışa aktarma ve silme taleplerini iletebilir. Yasal saklama zorunluluğu olan kayıtlar bu kapsam dışında tutulabilir.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">7. Müşteri Sorumluluğu</h2>
        <p className="text-muted-foreground">
          İşletmeniz, kendi müşterilerine yapılacak aydınlatma, izin, iletişim tercihleri, WhatsApp politikaları ve sektörel mevzuat uyumu konularından sorumludur. SvontAI bu süreçleri yönetmenize yardımcı olan teknik araçları sağlar; hukuki uyumluluk garantisi vermez.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-xl font-semibold">8. Başvuru ve İletişim</h2>
        <p className="text-muted-foreground">
          Gizlilik ve veri talepleri için hesap içi destek ekranını veya satış/destek e-posta kanalını kullanabilirsiniz. Talebin kapsamına göre kimlik ve yetki doğrulaması istenebilir.
        </p>
      </section>
    </main>
  )
}
