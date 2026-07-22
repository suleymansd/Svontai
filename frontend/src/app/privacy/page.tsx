import Link from 'next/link'
import { LegalDocument } from '@/components/legal/legal-document'

export default function PrivacyPage() {
  return (
    <LegalDocument
      title="Gizlilik Politikası"
      updatedAt="22 Temmuz 2026"
      introduction={<p>Bu politika, SvontAI platformu kullanılırken kişisel verilerin ve işletme verilerinin nasıl korunduğunu ve işlendiğini açıklar. KVKK kapsamındaki faaliyet bazlı bilgilendirme için ayrıca <Link className="text-primary underline" href="/kvkk">KVKK Aydınlatma Metni</Link> yayımlanır.</p>}
      sections={[
        { title: 'Kapsam ve roller', content: <p>Hesap ve platform kullanım verilerinde hizmeti sunan taraf veri sorumlusu olarak hareket eder. İşletmenin kendi müşterilerine ait WhatsApp, lead, randevu ve çağrı verilerinde işletme veri sorumlusu; SvontAI ise sözleşme ve talimatlarla sınırlı hizmet sağlayıcı/veri işleyen rolündedir.</p> },
        { title: 'İşlenen bilgiler', content: <p>Hesap ve iletişim bilgileri, işletme profili, kullanıcı rolleri, entegrasyon yetkileri, konuşmalar, kişi ve lead kayıtları, randevular, medya, çağrı kayıt ve özetleri, destek talepleri, kullanım ölçümleri, cihaz/ağ bilgileri, güvenlik ve audit kayıtları işlenebilir.</p> },
        { title: 'Kullanım amaçları', content: <p>Veriler; hesabı ve tenant izolasyonunu işletmek, botları hazırlamak, mesaj ve randevu otomasyonlarını yürütmek, entegrasyonları tanılamak, destek sağlamak, kötüye kullanımı önlemek, yedek almak, hizmet kalitesini ölçmek ve yasal yükümlülükleri yerine getirmek için kullanılır.</p> },
        { title: 'Hizmet sağlayıcıları', content: <p>Barındırma, veritabanı, nesne depolama, e-posta, hata izleme, yapay zeka, WhatsApp, telefon ve otomasyon hizmetleri için yalnızca gerekli veriler ilgili sağlayıcılarla paylaşılabilir. Bağlanan her üçüncü taraf hesabı kendi koşullarına ve gizlilik kurallarına tabidir.</p> },
        { title: 'Saklama ve silme', content: <p>Veriler hizmet ilişkisi, güvenlik ihtiyacı ve yasal saklama süreleri boyunca tutulur. Süre sonunda silinir, anonimleştirilir veya erişimi kısıtlanır. Yedek kopyalar döngüsel saklama süresi sonunda güvenli şekilde kaldırılır.</p> },
        { title: 'Güvenlik', content: <p>Rol tabanlı yetkilendirme, tenant izolasyonu, güvenli oturum çerezleri, hız sınırı, şifreleme, webhook doğrulaması, audit log, yedekleme ve hata izleme önlemleri uygulanır. Hiçbir internet hizmeti mutlak güvenlik garantisi veremez.</p> },
        { title: 'Tercihler ve başvurular', content: <p>Veri erişimi, düzeltme, dışa aktarma ve silme talepleri paneldeki Destek alanından veya support@svontai.com adresinden iletilebilir. Talep sahibinin kimliği ve yetkisi doğrulanabilir.</p> },
        { title: 'Değişiklikler', content: <p>Politika önemli ürün veya mevzuat değişikliklerinde güncellenir. Esaslı değişiklikler platform veya e-posta üzerinden bildirilir; güncel sürüm ve tarihi bu sayfada yayımlanır.</p> },
      ]}
    />
  )
}
