import Link from 'next/link'
import { LegalDocument } from '@/components/legal/legal-document'

export default function TermsPage() {
  return (
    <LegalDocument
      title="Kullanım Koşulları"
      updatedAt="22 Temmuz 2026"
      introduction={<p>Bu koşullar SvontAI hesabı, self-serve ve concierge kurulum, WhatsApp asistanı, randevu, lead, arama, medya ve operasyon özelliklerinin kullanımını düzenler. Ücretli hizmette ayrıca <Link href="/service-agreement" className="text-primary underline">Müşteri Hizmet Sözleşmesi</Link> ve imzalı sipariş formu uygulanır.</p>}
      sections={[
        { title: 'Hizmet kapsamı', content: <p>SvontAI işletmeler için yapay zeka asistanı, bot ve medya yönetimi, mesaj/lead/randevu takibi, sesli arama, entegrasyon sağlık kontrolü, raporlama ve concierge operasyon araçları sağlar. Özellikler kullanım hakkı, sağlayıcı bağlantısı ve müşteri onayına göre açılır.</p> },
        { title: 'Hesap güvenliği', content: <p>Kullanıcı doğru bilgi vermek, güçlü parola ve sunulan çok faktörlü doğrulamayı kullanmak, ekip yetkilerini sınırlamak ve şüpheli erişimi gecikmeden bildirmekle sorumludur. Hesap başkasına devredilemez.</p> },
        { title: 'Kabul edilebilir kullanım', content: <p>Spam, izinsiz pazarlama, aldatıcı iletişim, yasa dışı içerik, yetkisiz kişisel veri işleme, güvenlik önlemlerini aşma ve üçüncü taraf politikalarını ihlal etme yasaktır.</p> },
        { title: 'Yapay zeka ve otonomi', content: <p>Sistem rutin yanıt, randevu, tanılama ve toparlama işlemlerini otomatik yürütebilir. Yapay zeka çıktıları hatalı olabilir. Hukuki, tıbbi, finansal veya yüksek etkili kararlar için insan kontrolü ve gerekli profesyonel değerlendirme müşteriye aittir.</p> },
        { title: 'WhatsApp ve dış servisler', content: <p>Meta Cloud, QR tabanlı bağlantı, Google, telefon, yapay zeka ve diğer sağlayıcıların kullanılabilirliği kendi kurallarına bağlıdır. QR yöntemi için ayrıca <Link href="/openwa-consent" className="text-primary underline">WhatsApp QR Risk Metni</Link> açıkça kabul edilmeden bağlantı kurulmaz.</p> },
        { title: 'Ücret, plan ve limitler', content: <p>Uygulama içinde kartla ödeme alınmaz. Plan, fiyat, vergi, süre ve limitler yazılı teklif/sipariş formunda belirlenir. <Link href="/manual-payment" className="text-primary underline">Manuel ödeme ve faturalandırma süreci</Link> tamamlanmadan ücretli plan etkinleştirilmez.</p> },
        { title: 'Fikri haklar ve müşteri içeriği', content: <p>Platform yazılımı ve markası üzerindeki haklar hizmet sağlayıcıya aittir. Müşteri yüklediği içerik üzerindeki haklarını korur ve hizmetin çalışması için gerekli sınırlı işleme iznini verir; içeriği kullanmaya yetkili olduğunu taahhüt eder.</p> },
        { title: 'Süreklilik, askıya alma ve fesih', content: <p>Bakım, güvenlik veya sağlayıcı kesintileri geçici aksamalara neden olabilir. Kötüye kullanım, güvenlik riski, ödeme ihlali veya yasal zorunluluk halinde özellikler sınırlandırılabilir. Fesih ve veri çıkışı imzalı sözleşmeye göre yürütülür.</p> },
        { title: 'Gizlilik ve kişisel veriler', content: <p>Veri işleme ayrıntıları <Link href="/privacy" className="text-primary underline">Gizlilik Politikası</Link> ve <Link href="/kvkk" className="text-primary underline">KVKK Aydınlatma Metni</Link> içinde açıklanır. İşletme, kendi müşterilerine karşı aydınlatma ve ileti izinlerinden sorumludur.</p> },
        { title: 'Değişiklik ve iletişim', content: <p>Esaslı koşul değişiklikleri yürürlüğe girmeden önce bildirilir. Sorular ve itirazlar paneldeki Destek alanından veya support@svontai.com adresinden iletilebilir.</p> },
      ]}
    />
  )
}
