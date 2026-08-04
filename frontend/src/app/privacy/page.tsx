import Link from 'next/link'
import { LegalDocument } from '@/components/legal/legal-document'
import { LegalIdentityBlock } from '@/components/legal/legal-identity-block'

export default function PrivacyPage() {
  return (
    <LegalDocument
      title="Gizlilik ve Veri Koruma Politikası"
      updatedAt="4 Ağustos 2026"
      introduction={(
        <div className="space-y-3">
          <p>Bu politika SvontAI&apos;nin hesap, işletme ve müşteri iletişim verilerini hangi ilkelerle koruduğunu; kullanıcıların hangi kontrolleri kullanabileceğini açıklar. KVKK kapsamında faaliyet bazlı zorunlu bilgilendirme için <Link className="text-primary underline" href="/kvkk">KVKK Aydınlatma Metni</Link> geçerlidir.</p>
          <p>SvontAI kişisel verileri satmaz, reklam profili oluşturmak için üçüncü taraflara kiralamaz ve müşteri içeriklerini genel amaçlı yapay zekâ modeli eğitimi için kendi kararıyla kullanmaz.</p>
        </div>
      )}
      notice={<p>Gizlilik politikası tek başına yurt dışı aktarım veya müşteri iletişimi için hukuki sebep oluşturmaz. Gerekli izin, sözleşme ve aktarım mekanizmaları ilgili işlem başlamadan önce ayrıca kurulmalıdır.</p>}
      sections={[
        { title: 'Hizmet sağlayıcı kimliği', content: <LegalIdentityBlock /> },
        { title: 'Gizlilik ilkelerimiz', content: (
          <ul className="list-disc space-y-2 pl-5">
            <li>Belirli, açık ve meşru amaç; amaçla sınırlı veri kullanımı.</li>
            <li>Yalnızca gerekli veriyi toplama ve varsayılan olarak en az yetki.</li>
            <li>Tenantlar arasında teknik ve yetkisel izolasyon.</li>
            <li>Hatalı veriyi düzeltme, süre dolduğunda imha ve işlem kanıtını saklama.</li>
            <li>Yapay zekâ çıktılarında doğrulama, insan devri ve yüksek riskli kullanım sınırlaması.</li>
            <li>Alt işleyen seçiminde güvenlik, gizlilik ve veri işleme şartlarını değerlendirme.</li>
          </ul>
        ) },
        { title: 'Topladığımız bilgiler', content: <p>Hesap ve iletişim bilgileri, işletme profili, roller, entegrasyon yetkileri ve şifreli tokenlar, WhatsApp konuşmaları ve medya, kişi/lead/randevu kayıtları, çağrı metadatası/transkript/özet, destek talepleri, ürün kullanım olayları, ağ/cihaz bilgileri, güvenlik/audit kayıtları ve manuel satış belgeleri işlenebilir. Parolalar geri döndürülemez özetle saklanır; kart bilgileri platform tarafından alınmaz.</p> },
        { title: 'Verileri nasıl kullanıyoruz', content: <p>Verileri hesabı işletmek, ana asistanı kurmak, müşteri mesajlarına yanıt vermek, gerçek takvim uygunluğunu kontrol etmek, onaylı randevu oluşturmak, medya iletmek, izinli aramaları yürütmek, entegrasyon sağlığını izlemek, destek vermek, dolandırıcılık ve saldırıları önlemek, yedekleme/geri yükleme yapmak, gerçek kullanım metriklerini üretmek ve yasal yükümlülükleri yerine getirmek için kullanırız.</p> },
        { title: 'Müşteri içeriği ve veri sahipliği', content: <p>Müşteri; yüklediği işletme bilgisi, medya ve son kullanıcı verileri üzerindeki haklarını korur. SvontAI bu içeriği yalnızca hizmeti sunmak, güvenliğini sağlamak ve müşterinin belgelenmiş talimatını yerine getirmek için işler. Müşteri, üçüncü kişi verilerini platforma aktarmaya yetkili olduğunu, kendi aydınlatma/izin süreçlerini yürüttüğünü ve özel nitelikli verileri zorunlu olmadıkça sisteme yüklemeyeceğini taahhüt eder.</p> },
        { title: 'Yapay zekâ işlemleri', content: <p>İşletme talimatları, ilgili konuşma bağlamı ve gerekli bilgi parçaları seçili yapay zekâ sağlayıcısına yanıt/özet üretimi amacıyla iletilebilir. Gizli anahtarlar ve gereksiz tenant verileri prompta eklenmez. Çıktılar mutlak doğruluk garantisi taşımaz; doğrulanmayan fiyat, müsaitlik veya iç talimat iddiaları engellenir ya da insan desteğine aktarılır.</p> },
        { title: 'Alt işleyenler ve entegrasyonlar', content: (
          <div className="space-y-3">
            <p>Aktif yapılandırmaya göre Railway (API, veritabanı, Redis ve worker), Vercel (web arayüzü), Cloudflare R2 (özel dosya/yedek), Google (Gemini ve Calendar), Resend (işlemsel e-posta), Sentry (hata izleme), Twilio (izinli sesli arama), n8n (otomasyon) ve seçilen WhatsApp bağlantı yöntemi kullanılabilir.</p>
            <p>Her entegrasyon yalnızca gerekli veri ve yetki kapsamıyla çalıştırılır. Google gibi sağlayıcılarda en dar OAuth kapsamı tercih edilir; bağlantı panelden kaldırıldığında yeni işlem durdurulur ve saklanan tokenlar geçersizleştirme/silme prosedürüne alınır. Sağlayıcının kendi hesabında tuttuğu veriler ayrıca ilgili sağlayıcının koşullarına tabidir.</p>
          </div>
        ) },
        { title: 'Saklama, dışa aktarma ve silme', content: <p>Varsayılan saklama süreleri mesaj için 365 gün, ham sağlayıcı yükü için 90 gün, ürün analitiği için 180 gün, kullanım ve sistem olayı için 730 gündür. İşletme yöneticisi panelden izin verilen sınırlar içinde politika belirleyebilir, önizleme alabilir ve temizliği çalıştırabilir. Doğrulanmış erişim, düzeltme, dışa aktarma ve silme talepleri audit kaydıyla işlenir; yasal saklama veya hukuki muhafaza varsa silme kapsamı gerekçesiyle sınırlandırılabilir.</p> },
        { title: 'Çerezler ve tarayıcı depolaması', content: <p>Oturum güvenliği, kimlik doğrulama, tenant bağlamı ve temel arayüz işlevleri için zorunlu çerezler ile yerel/oturum depolaması kullanılabilir. Ürün analitiği yalnızca giriş yapmış kullanıcıda, içerik/e-posta/telefon gibi alanları göndermeyen sınırlı olay verileriyle çalışır. Reklam veya davranışsal pazarlama çerezi etkinleştirilirse önceden ayrı tercih mekanizması sunulur; zorunlu olmayan çerezler rıza verilmeden çalıştırılmaz.</p> },
        { title: 'Güvenlik ve olay yönetimi', content: <p>Erişim kontrolü, 2FA, token/sır şifreleme, HTTPS, rate-limit, imzalı webhook, audit log, özel depolama, şifreli yedek, restore testi ve hata alarmı gibi katmanlı tedbirler uygulanır. Personel ve tedarikçi erişimi görevle sınırlıdır. Veri ihlali şüphesinde kapsam belirlenir, erişim sınırlandırılır, kanıtlar korunur ve uygulanabilir KVKK bildirimleri gecikmeksizin yürütülür.</p> },
        { title: 'Kullanıcı kontrolleri', content: <p>Kullanıcılar entegrasyonları bağlayıp kaldırabilir, WhatsApp QR oturumunu sonlandırabilir, bot ve medya içeriğini düzenleyebilir, veri saklama sürelerini yönetebilir ve Veri ve Gizlilik alanından erişim/düzeltme/dışa aktarma/silme talebi oluşturabilir. İşletme yöneticisi ekip rollerini düzenli olarak gözden geçirmelidir.</p> },
        { title: 'Çocukların verileri ve yasaklanan kullanım', content: <p>SvontAI çocuklara doğrudan sunulmaz. Müşteri hizmeti çocuk verisi işlemeyi gerektiriyorsa ilgili sektörel kuralları, veli/temsilci süreçlerini ve ek güvenlik tedbirlerini kurmadan sistemi bu amaçla kullanmamalıdır. İzinsiz pazarlama, hassas profil çıkarma, ayrımcılık, yasa dışı gözetim ve kişilerin temel haklarını etkileyen yalnızca otomatik kararlar yasaktır.</p> },
        { title: 'Başvuru, şikâyet ve politika değişiklikleri', content: <p>Gizlilik talepleri panelden veya <a className="text-primary underline" href="mailto:support@svontai.com">support@svontai.com</a> adresinden iletilebilir. Kimlik ve yetki makul ölçüde doğrulanır. Esaslı politika değişiklikleri yürürlükten önce uygun kanaldan bildirilir; güncel sürüm ve tarih bu sayfada yayımlanır.</p> },
      ]}
    />
  )
}
