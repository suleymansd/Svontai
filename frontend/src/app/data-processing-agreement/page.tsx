import Link from 'next/link'
import { LegalDocument } from '@/components/legal/legal-document'
import { LegalIdentityBlock } from '@/components/legal/legal-identity-block'

export default function DataProcessingAgreementPage() {
  return (
    <LegalDocument
      title="Kişisel Veri İşleme Ek Protokolü"
      updatedAt="4 Ağustos 2026"
      introduction={(
        <div className="space-y-3">
          <p>Bu Ek Protokol, müşteri işletmenin SvontAI hizmetine aktardığı veya hizmet aracılığıyla işlenen son kullanıcı kişisel verileri bakımından tarafların veri koruma sorumluluklarını düzenler. Müşteri sipariş formunun bu sürüme atıf yapmasıyla ana hizmet sözleşmesinin ayrılmaz parçası olur.</p>
          <p>Platform hesap, güvenlik ve sözleşme verilerinde SvontAI hizmet sağlayıcısının veri sorumlusu olduğu faaliyetler bu protokolün değil, <Link href="/kvkk" className="text-primary underline">KVKK Aydınlatma Metni</Link>&apos;nin kapsamındadır.</p>
        </div>
      )}
      notice={<p>Bu protokolde “Müşteri” veri sorumlusu, aşağıda kimliği bulunan SvontAI hizmet sağlayıcısı ise müşterinin talimatıyla hareket eden veri işleyendir. Müşterinin işleme amaç ve vasıtalarını SvontAI ile birlikte belirlediği özel bir özellik varsa roller ayrıca yazılı olarak değerlendirilir.</p>}
      sections={[
        { title: 'Veri işleyen kimliği ve sözleşme belgeleri', content: (
          <div className="space-y-4">
            <LegalIdentityBlock />
            <p>Tarafların gerçek kimlikleri, tebligat adresleri, hizmet süresi, planı ve varsa özel veri işleme talimatları imzalı sipariş formunda belirtilir. Çelişki halinde emredici mevzuat, bu Ek Protokolün veri koruma hükümleri, sipariş formu ve ana hizmet sözleşmesi sırasıyla uygulanır.</p>
          </div>
        ) },
        { title: 'Konu, süre ve işleme niteliği', content: <p>İşlemenin konusu; WhatsApp müşteri iletişimi, yapay zekâ destekli yanıt/özet, lead ve randevu yönetimi, izinli sesli arama, medya paylaşımı, entegrasyon, raporlama, destek, güvenlik ve yedekleme hizmetlerinin sunulmasıdır. İşleme, hizmet ilişkisi ve sözleşmede belirlenen çıkış/saklama dönemi boyunca; toplama, kaydetme, düzenleme, sorgulama, iletme, erişimi sınırlama, yedekleme ve imha faaliyetlerini kapsar.</p> },
        { title: 'Müşterinin talimatları', content: <p>SvontAI yalnızca ana sözleşme, sipariş formu, panel ayarları, yetkili API çağrıları ve destek kanalı üzerinden belgelenmiş müşteri talimatları doğrultusunda işlem yapar. Talimatın mevzuata aykırı olduğu kanaati oluşursa müşteri bilgilendirilir ve işlem, güvenlik/yasal zorunluluk ölçüsünde askıya alınabilir. Kanunen zorunlu bir işleme talimat dışı yapılacaksa, açıklanması hukuken yasak değilse müşteri önceden bilgilendirilir.</p> },
        { title: 'Müşterinin yükümlülükleri', content: (
          <ul className="list-disc space-y-2 pl-5">
            <li>Her veri kategorisi için geçerli işleme ve iletişim hukuki sebebini belirlemek, ispatlamak ve ilgili kişiyi zamanında aydınlatmak.</li>
            <li>Yalnızca gerekli veriyi aktarmak; özel nitelikli veri veya çocuk verisi gerekiyorsa önceden yazılı risk değerlendirmesi ve ek tedbirleri tamamlamak.</li>
            <li>WhatsApp, Google, telefon ve diğer üçüncü taraf hesaplarını kullanmaya yetkili olmak; spam ve izinsiz iletişimi önlemek.</li>
            <li>Rol ve yetkileri düzenli gözden geçirmek, hesap güvenliğini sağlamak, olay veya hatalı veri şüphesini gecikmeden bildirmek.</li>
            <li>Otomatik yanıt, fiyat, randevu, arama ve yüksek etkili süreçler için uygun insan gözetimi ve iş kurallarını kurmak.</li>
          </ul>
        ) },
        { title: 'SvontAI veri işleyen yükümlülükleri', content: (
          <ul className="list-disc space-y-2 pl-5">
            <li>Yetkili kişileri gizlilik yükümlülüğüne tabi tutmak ve erişimi görevle sınırlamak.</li>
            <li>Riskle orantılı teknik/idari güvenlik tedbirlerini sürdürmek ve erişimleri kaydetmek.</li>
            <li>İlgili kişi talepleri, etki değerlendirmesi, denetim ve ihlal yönetiminde müşteriye makul teknik destek sağlamak.</li>
            <li>Alt işleyenleri yazılı veri koruma ve gizlilik şartlarına tabi tutmak; alt işleyenin ediminden mevzuat ve ana sözleşme kapsamında sorumlu olmak.</li>
            <li>Talimat ve yasal saklama kapsamı dışında veriyi kendi bağımsız pazarlama amacıyla kullanmamak veya satmamak.</li>
          </ul>
        ) },
        { title: 'Teknik ve idari tedbirler', content: <p>Asgari tedbirler; tenant izolasyonu, rol tabanlı en az yetki, güçlü kimlik doğrulama ve yönetici 2FA, güvenli oturum yönetimi, aktarım şifrelemesi, sır/token şifreleme, hız sınırı, imzalı webhook, audit/system event, güvenlik güncellemeleri, bağımlılık taraması, özel nesne depolama, AES-256-GCM şifreli veritabanı yedekleri, geri yükleme doğrulaması, olay izleme, iş sürekliliği ve personel erişim prosedürleridir. Tedbirler risk, teknoloji ve hizmet değiştikçe eşdeğer veya daha güçlü koruma sağlayacak şekilde güncellenebilir.</p> },
        { title: 'Alt işleyenler', content: (
          <div className="space-y-3">
            <p>Hizmet yapılandırmasına göre Railway, Vercel, Cloudflare R2, Google Gemini/Calendar, Resend, Sentry, Twilio, n8n altyapısı ve seçilen WhatsApp bağlantı sağlayıcısı alt işleyen veya bağımsız veri sorumlusu rolünde yer alabilir. Yalnızca etkin özelliğin gerektirdiği sağlayıcı kullanılır.</p>
            <p>Esaslı yeni alt işleyen değişikliği uygun kanaldan bildirilir. Müşteri, somut veri koruma gerekçesiyle bildirilen süre içinde itiraz edebilir. Taraflar makul alternatif arar; güvenli/yasal alternatif bulunamazsa etkilenen özellik veya hizmet ana sözleşmeye göre sonlandırılabilir.</p>
          </div>
        ) },
        { title: 'Yurt dışına aktarım', content: <p>Yurt dışı aktarım gerekiyorsa taraflar veri akışındaki rollerine uygun KVKK madde 9 mekanizmasını aktarım başlamadan önce kurar. Uygun güvence olarak standart sözleşme kullanıldığında Kurulun ilan ettiği metin değiştirilmeden imzalanır ve yasal bildirim süresi gözetilir. Müşteri tarafından eklenen kendi entegrasyonunun alıcısı ve aktarım ayarlarından müşteri sorumludur; SvontAI kendi alt işleyenleri için gerekli sözleşmesel tedbirleri yürütür.</p> },
        { title: 'İlgili kişi talepleri', content: <p>SvontAI&apos;ye doğrudan ulaşan ve müşteri son kullanıcısına ilişkin olduğu anlaşılan talep, hukuken doğrudan cevap verilmesi gerekmedikçe müşteriye yönlendirilir. Müşteri; paneldeki dışa aktarma, düzeltme, saklama ve silme araçlarını kullanır. Ek teknik çalışma makul ölçüde sağlanır; kimlik/yetki doğrulanmadan veri açıklanmaz veya silinmez.</p> },
        { title: 'Veri ihlali ve olay bildirimi', content: <p>SvontAI, müşteri verilerini etkileyen doğrulanmış bir kişisel veri ihlalini öğrendiğinde gereksiz gecikme olmaksızın müşterinin belirlediği güvenlik irtibatına mevcut bilgileri iletir. Bildirim; olayın niteliği, etkilenen veri/kişi kategorileri, muhtemel sonuçlar, alınan/önerilen tedbirler ve güncelleme planını mevcut olduğu ölçüde içerir. Kuruma ve ilgili kişilere yapılacak yasal bildirim kararından veri sorumlusu müşteri sorumludur; SvontAI gerekli kanıt ve teknik desteği sağlar.</p> },
        { title: 'Saklama, iade ve imha', content: <p>Aktif hizmette müşteri panelindeki saklama politikası uygulanır. Hizmet sona erdiğinde müşteri verileri sipariş formundaki çıkış süresi boyunca dışa aktarmaya hazır tutulur; ardından yasal saklama/hukuki muhafaza zorunluluğu bulunmayan aktif kopyalar silinir veya anonimleştirilir. Şifreli yedekler olağan döngüsü içinde üzerine yazılarak imha edilir ve bu sürede yalnızca felaket kurtarma amacıyla erişilebilir. İmha işlemleri audit/system event ile kayıt altına alınır.</p> },
        { title: 'Denetim ve kanıt', content: <p>SvontAI, güvenlik ve veri koruma yükümlülüklerinin yerine getirildiğini göstermek için ilgili politika, test ve denetim özetlerini makul ölçüde sunar. Yerinde veya özel denetim; yılda bir kez, makul ön bildirimle, diğer müşterilerin sırlarını ve sistem güvenliğini tehlikeye atmadan, tarafların maliyet/gizlilik kurallarını yazılı belirlemesiyle yapılır. İhlal şüphesi veya yetkili makam talebi halinde bu sınırlamalar somut duruma göre uyarlanır.</p> },
        { title: 'Sorumluluk, yürürlük ve değişiklik', content: <p>Tarafların sorumluluğu emredici KVKK hükümleri ve ana sözleşmedeki geçerli sorumluluk düzenine tabidir. Bu protokol hizmet süresince yürürlükte kalır; gizlilik, denetim kanıtı ve yasal saklama hükümleri niteliği gereği sona ermeden sonra da devam eder. Esaslı değişiklik yeni sürüm olarak bildirilir ve sipariş/sözleşme sürecinde kayıt altına alınır.</p> },
        { title: 'Ek A — veri işleme kapsamı', content: (
          <div className="space-y-3">
            <p><strong>İlgili kişiler:</strong> müşterinin çalışan/yetkilileri; WhatsApp kullanıcıları; arayan/aranan kişiler; potansiyel ve mevcut müşteriler; lead ve randevu sahipleri.</p>
            <p><strong>Veriler:</strong> ad, telefon, görünen WhatsApp adı, iletişim içeriği ve medya, tercih/ilgi, lead ve randevu bilgisi, çağrı metadatası/transkript/özet, destek ve işlem kayıtları. Özel nitelikli veri varsayılan kapsamda değildir.</p>
            <p><strong>Amaç:</strong> müşteri iletişimi, destek, lead/randevu yönetimi, izinli arama, raporlama, güvenlik, yedekleme ve müşterinin etkinleştirdiği otomasyonlar.</p>
            <p><strong>Sıklık:</strong> hizmet kullanımı ve gelen olaylarla sürekli/olay bazlı. <strong>Süre:</strong> hizmet süresi ve müşteri saklama politikası.</p>
          </div>
        ) },
      ]}
    />
  )
}
