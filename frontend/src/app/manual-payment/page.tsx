import { LegalDocument } from '@/components/legal/legal-document'

export default function ManualPaymentPage() {
  return (
    <LegalDocument
      title="Manuel Satış, Ödeme ve Faturalandırma Süreci"
      updatedAt="22 Temmuz 2026"
      introduction={<p>SvontAI şu anda uygulama içinde kart veya otomatik ödeme almaz. Tüm ücretli aktivasyonlar aşağıdaki doğrulanabilir süreçle yürütülür.</p>}
      sections={[
        { title: 'Talep ve teklif', content: <p>Müşteri iletişim formu veya destek kanalı üzerinden talep oluşturur. İhtiyaç görüşmesinden sonra plan kapsamı, toplam bedel, vergiler, süre ve teslim koşulları yazılı teklif/sipariş formunda sunulur.</p> },
        { title: 'Satıcı bilgilerinin bildirimi', content: <p>Ödemeden önce hizmet sağlayıcının gerçek adı veya unvanı, adresi, iletişim bilgileri, vergi bilgileri ve varsa sicil bilgileri müşteriye kalıcı veri saklayıcısıyla iletilir. Bu bilgiler eksikse ödeme istenmez ve ücretli aktivasyon yapılmaz.</p> },
        { title: 'Sözleşme onayı', content: <p>Müşteri teklif, hizmet sözleşmesi, iptal/iade şartları ve gerekli entegrasyon risklerini yazılı olarak kabul eder. Kabul kaydı siparişe bağlanır.</p> },
        { title: 'Ödeme teyidi', content: <p>Ödeme yalnızca teklifte bildirilen hesaba yapılır. Dekont veya banka kaydı siparişle eşleştirilir. Tek başına sözlü bildirim “ödendi” durumu oluşturmaz.</p> },
        { title: 'Yasal belge ve aktivasyon', content: <p>Ödemeyi alan gerçek hizmet sağlayıcı, kendi vergi statüsüne uygun fatura, serbest meslek makbuzu veya diğer zorunlu mali belgeyi mevzuattaki sürede düzenler. Plan, ödeme ve belge süreci teyit edildikten sonra admin tarafından etkinleştirilir.</p> },
        { title: 'İptal, iade ve kayıtlar', content: <p>İptal/iade, imzalı teklif ve emredici mevzuata göre yürütülür. Teklif, kabul, ödeme kanıtı, belge numarası, aktivasyon ve iade kararları audit kaydıyla saklanır.</p> },
      ]}
      notice={<p>SvontAI bir mali müşavirlik veya e-fatura hizmeti değildir. Kullanılacak belge türü ve vergi yükümlülüğü, ödeme alan gerçek hizmet sağlayıcının mali müşaviri tarafından doğrulanmalıdır.</p>}
    />
  )
}
