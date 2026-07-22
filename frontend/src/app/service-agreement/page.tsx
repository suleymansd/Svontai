import { LegalDocument } from '@/components/legal/legal-document'

export default function ServiceAgreementPage() {
  return (
    <LegalDocument
      title="Müşteri Hizmet Sözleşmesi Esasları"
      updatedAt="22 Temmuz 2026"
      introduction={<p>Bu sayfa SvontAI hizmet ilişkisinin standart esaslarını açıklar. Ücretli hizmet, tarafların gerçek kimlikleri ile plan, fiyat, süre ve özel şartları içeren yazılı sipariş formunun kabulüyle başlar.</p>}
      sections={[
        { title: 'Hizmet kapsamı', content: <p>SvontAI; kurulum, WhatsApp asistanı, bot ve medya yönetimi, müşteri/lead/randevu takibi, raporlama, tanılama ve seçilen entegrasyonları sunar. Aktif özellikler sipariş formu ve kullanım haklarıyla belirlenir.</p> },
        { title: 'Kurulum ve teslim', content: <p>Müşteri self-serve veya concierge kurulum seçebilir. Dış servis izinleri ve WhatsApp QR taraması gibi yalnızca hesap sahibi tarafından yapılabilecek işlemler müşteriye aittir. Yayına alma durumu panelde kayıt altına alınır.</p> },
        { title: 'Müşteri yükümlülükleri', content: <p>Müşteri doğru işletme bilgisi vermek, yetkileri korumak, iletişim izinlerini almak, hukuka ve sağlayıcı politikalarına uymak, AI çıktılarının yüksek riskli kullanımında insan kontrolü sağlamakla yükümlüdür.</p> },
        { title: 'Ücret ve faturalandırma', content: <p>Ücret, vergi, dönem, ödeme hesabı ve yenileme koşulları sipariş formunda belirtilir. Uygulama içinde kart alınmaz. Plan yalnızca ödeme teyidi ve gerekli yasal belgenin düzenlenmesi süreciyle etkinleştirilir.</p> },
        { title: 'Veri koruma ve gizlilik', content: <p>Taraflar eriştikleri gizli bilgileri yalnızca hizmet amacıyla kullanır. Müşteri, kendi müşterilerinin verilerinde veri sorumlusudur; SvontAI sözleşme talimatlarıyla sınırlı veri işleyen olarak hareket eder.</p> },
        { title: 'Süreklilik ve üçüncü taraflar', content: <p>Planlı bakım, ağ, WhatsApp, AI, telefon veya diğer sağlayıcı kesintileri hizmeti etkileyebilir. Makul izleme ve otomatik toparlama uygulanır; mutlak kesintisizlik taahhüt edilmez.</p> },
        { title: 'Süre, askıya alma ve fesih', content: <p>Süre ve yenileme sipariş formunda belirlenir. Güvenlik riski, kötüye kullanım veya ödeme ihlalinde hizmet sınırlandırılabilir. Fesih sonrası veriler yasal saklama ve güvenli silme prosedürüne göre yönetilir.</p> },
        { title: 'Sorumluluk ve uyuşmazlık', content: <p>Özel sorumluluk sınırları, uygulanacak hukuk, yetkili merci ve bildirim adresleri gerçek taraf bilgilerini içeren imzalı sözleşmede belirlenir. Emredici tüketici ve veri koruma hükümleri saklıdır.</p> },
      ]}
    />
  )
}
