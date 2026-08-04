import Link from 'next/link'
import { LegalDocument } from '@/components/legal/legal-document'
import { LegalIdentityBlock } from '@/components/legal/legal-identity-block'

export default function KvkkPage() {
  return (
    <LegalDocument
      title="KVKK Aydınlatma Metni"
      updatedAt="4 Ağustos 2026"
      introduction={(
        <div className="space-y-3">
          <p>Bu Aydınlatma Metni, SvontAI web sitesi, paneli, destek kanalları ve bağlantılı hizmetlerin kullanımı sırasında işlenen kişisel veriler hakkında 6698 sayılı Kişisel Verilerin Korunması Kanunu&apos;nun 10. maddesi uyarınca bilgi vermek amacıyla hazırlanmıştır.</p>
          <p>Bu metin bir açık rıza metni değildir. Açık rızaya ihtiyaç duyulan istisnai bir işlem olursa amaç, veri kategorisi ve aktarım bilgisi ayrıca açıklanır ve rıza ayrı bir seçimle alınır. Hizmetin kurulması veya ifası için zorunlu olmayan bir işleme faaliyeti, rıza verilmemesi nedeniyle zorunlu tutulmaz.</p>
        </div>
      )}
      notice={<p>SvontAI yalnızca işletmelere yönelik hizmet sunar. Ücretli aktivasyondan önce yasal hizmet sağlayıcı/veri sorumlusu kimliği, mali bilgiler ve tebligat adresi eksiksiz yayımlanmalı; müşteriyle imzalanan sipariş formunda aynı bilgiler yer almalıdır.</p>}
      sections={[
        { title: 'Veri sorumlusu ve başvuru kanalı', content: <LegalIdentityBlock /> },
        { title: 'Kapsam, ilgili kişi grupları ve roller', content: (
          <div className="space-y-3">
            <p>Bu metin; ziyaretçileri, hesap kullanıcılarını, müşteri işletmelerin yetkili ve çalışanlarını, destek talebi oluşturan kişileri, tedarikçi/iş ortağı yetkililerini ve SvontAI ile doğrudan ilişki kuran diğer gerçek kişileri kapsar.</p>
            <p>Hesap, güvenlik, sözleşme, destek ve platform kullanım verilerinde yasal hizmet sağlayıcı veri sorumlusudur. Müşteri işletmenin kendi WhatsApp kullanıcıları, arayanları, lead&apos;leri ve randevu sahipleri bakımından kural olarak müşteri işletme veri sorumlusudur; SvontAI ise müşterinin belgelenmiş talimatlarıyla sınırlı veri işleyen olarak hareket eder. Bu ilişki <Link href="/data-processing-agreement" className="text-primary underline">Veri İşleme Ek Protokolü</Link> ile düzenlenir.</p>
          </div>
        ) },
        { title: 'İşlenen kişisel veri kategorileri', content: (
          <ul className="list-disc space-y-2 pl-5">
            <li><strong>Kimlik ve iletişim:</strong> ad-soyad, işletme/pozisyon bilgisi, e-posta, telefon ve doğrulanmış başvuru bilgileri.</li>
            <li><strong>Hesap ve yetki:</strong> kullanıcı, tenant, rol, izin, üyelik, doğrulama, oturum ve hesap güvenliği kayıtları.</li>
            <li><strong>İşlem güvenliği:</strong> IP adresi, tarih-saat, cihaz/tarayıcı, başarısız giriş, rate-limit, webhook, audit ve sistem olayı kayıtları.</li>
            <li><strong>İşletme ve operasyon:</strong> işletme profili, hizmetler, çalışma saatleri, fiyatlar, bot ayarları, bilgi kaynakları, medya ve entegrasyon tercihleri.</li>
            <li><strong>Müşteri iletişimi:</strong> telefon numarası, görünen kişi adı, mesaj içeriği, medya, konuşma özeti, lead notu, randevu ve iletişim olayları.</li>
            <li><strong>Sesli iletişim:</strong> arama zamanı, taraf numaraları, süre, durum, transkript ve özet; yalnızca ayrıca etkinleştirildiğinde ses kaydı bağlantısı.</li>
            <li><strong>Destek ve kullanım:</strong> talep/ticket içeriği, hata bilgisi, özellik kullanımı, performans ölçümü ve müşteri başarı metrikleri.</li>
            <li><strong>Finans ve sözleşme:</strong> teklif, sipariş, plan, manuel ödeme teyidi, proforma/yasal belge referansı ve taraf bilgileri. Kart verisi SvontAI tarafından alınmaz.</li>
          </ul>
        ) },
        { title: 'İşleme amaçları ve hukuki sebepler', content: (
          <div className="space-y-3">
            <p>Hesap açma, kimlik doğrulama, tenant oluşturma, kurulum, mesaj/randevu/arama otomasyonları, destek ve sözleşme süreçleri; sözleşmenin kurulması veya ifası için gerekli olması hukuki sebebine dayanır.</p>
            <p>Fatura, kayıt, resmî talep ve mevzuata uyum işlemleri hukuki yükümlülüğün yerine getirilmesine; uyuşmazlık ve denetim kayıtları bir hakkın tesisi, kullanılması veya korunmasına dayanır.</p>
            <p>Bilgi güvenliği, kötüye kullanım önleme, kapasite planlama, hizmet kalitesi, ürün analitiği ve temel hata izleme; ilgili kişinin temel haklarına zarar vermemek kaydıyla meşru menfaate dayanır ve veri minimizasyonu uygulanır.</p>
            <p>Ticari elektronik ileti, zorunlu olmayan çerez/izleme, özel nitelikli veri veya başka bir ihtiyari işlem yalnızca uygulanabilir mevzuatın gerektirdiği ayrı izin/açık rıza alınarak yürütülür. SvontAI sağlık, biyometri, ceza mahkûmiyeti veya benzeri özel nitelikli verilerin rutin olarak yüklenmesi amacıyla tasarlanmamıştır.</p>
          </div>
        ) },
        { title: 'Toplama yöntemleri', content: <p>Veriler; kayıt ve profil formları, panel işlemleri, yüklenen dosyalar, destek kanalları, API ve imzalı webhook olayları, WhatsApp/Google/telefon entegrasyonları, tarayıcıdaki zorunlu oturum teknolojileri, sunucu logları ve müşterinin yetkili olarak sağladığı veri kaynakları üzerinden tamamen veya kısmen otomatik yöntemlerle elde edilir. Üçüncü kişiden alınan veriler bakımından müşteri işletme, gerekli aydınlatmayı uygun zamanda yapmak ve hukuki sebebi sağlamakla yükümlüdür.</p> },
        { title: 'Alıcılar, alt işleyenler ve yurt dışı aktarım', content: (
          <div className="space-y-3">
            <p>Veriler, hizmetin gerektirdiği ölçüde yetkili SvontAI personeline; müşteri tarafından yetkilendirilen kullanıcılara; hukuken yetkili kamu kurumları ve adli mercilere; ayrıca seçilen hizmete göre Railway, Vercel, Cloudflare R2, Google Gemini/Calendar, Resend, Sentry, Twilio, n8n ve WhatsApp bağlantı sağlayıcılarına aktarılabilir.</p>
            <p>Bu sağlayıcıların bir kısmı yurt dışında bulunabilir veya küresel altyapı kullanabilir. Yurt dışı aktarım için KVKK&apos;nın 9. maddesindeki yeterlilik kararı, uygun güvence/standart sözleşme veya kanunda öngörülen istisnai aktarım şartlarından uygulanabilir olanının kurulması gerekir; hukuki mekanizma yalnızca bu metinle kurulmuş sayılmaz. Açık rıza kullanılması gerekirse ayrı ve bilgilendirilmiş şekilde alınır. Müşterinin seçimine bağlı entegrasyonlar etkinleştirilmedikçe bu entegrasyonlara veri gönderilmez.</p>
          </div>
        ) },
        { title: 'Saklama ve imha', content: (
          <div className="space-y-3">
            <p>Varsayılan tenant politikası mesaj içeriğini 365 gün, ham sağlayıcı yüklerini 90 gün, ürün kullanım olaylarını 180 gün, kullanım ve sistem olaylarını 730 gün saklar. Müşteri bu süreleri panelde yasal sınırlar içinde kısaltabilir veya uzatabilir.</p>
            <p>Hesap ve sözleşme kayıtları hizmet ilişkisi ve uygulanabilir zamanaşımı/yasal saklama süreleri boyunca; güvenlik ve kabul kayıtları uyuşmazlık, denetim ve ispat ihtiyacı sürdüğü müddetçe saklanır. İşleme sebebi ortadan kalktığında veriler ilk periyodik imha işleminde silinir, yok edilir veya geri döndürülemeyecek biçimde anonimleştirilir. Hukuki muhafaza kararı bulunan kayıtlar karar kalkana kadar imha edilmez; yedekler kendi şifreli döngüsü sonunda silinir.</p>
          </div>
        ) },
        { title: 'Yapay zekâ ve otomatik işlemler', content: <p>Mesaj sınıflandırma, yanıt taslağı, lead/randevu niyeti, özet ve öneri üretiminde yapay zekâ kullanılabilir. Sistem; fiyat veya takvim gibi doğrulanması gereken bilgileri kayıtlı işletme verisi ve entegrasyon sonuçlarıyla sınırlar, riskli durumlarda insan desteğine aktarır. Kişi üzerinde hukuki veya benzer derecede önemli sonuç doğuran yalnızca otomatik karar verme amacıyla kullanılmaz.</p> },
        { title: 'Güvenlik tedbirleri', content: <p>Tenant izolasyonu, rol tabanlı erişim, çok faktörlü yönetici doğrulaması, güvenli oturum çerezleri, aktarım sırasında şifreleme, şifreli sır/token saklama, hız sınırı, imzalı webhook, audit kayıtları, özel nesne depolama, şifreli ve geri yükleme kontrollü yedekler, izleme ve olay müdahalesi uygulanır. Hiçbir çevrim içi sistem için mutlak güvenlik garantisi verilemez; ihlal şüphesinde erişim sınırlandırılır ve uygulanabilir bildirim süreçleri işletilir.</p> },
        { title: 'KVKK madde 11 kapsamındaki haklar', content: <p>İlgili kişi; verisinin işlenip işlenmediğini öğrenme, bilgi talep etme, işleme amacını ve amaca uygun kullanımı öğrenme, aktarılan tarafları bilme, eksik/yanlış veriyi düzeltme, şartları oluştuğunda silme veya yok etme, bu işlemlerin aktarılanlara bildirilmesini isteme, münhasıran otomatik sistem sonucuna itiraz etme ve kanuna aykırı işleme nedeniyle zararın giderilmesini talep etme haklarına sahiptir.</p> },
        { title: 'Başvuru usulü ve cevap süresi', content: (
          <div className="space-y-3">
            <p>Başvurular paneldeki Veri ve Gizlilik alanından, <a className="text-primary underline" href="mailto:support@svontai.com">support@svontai.com</a> adresinden veya yukarıda yayımlanan fiziksel/KEP adresinden iletilebilir. Başvuruda ad-soyad, iletişim bilgisi, talep konusu, ilgili hesap/işletme ve kimlik/yetki doğrulamasına yeterli bilgi bulunmalıdır; gereksiz kimlik belgesi kopyası istenmez.</p>
            <p>Başvuru, niteliğine göre en kısa sürede ve en geç 30 gün içinde kural olarak ücretsiz sonuçlandırılır. Talebin ek maliyet doğurması halinde Kurul tarifesi uygulanabilir. Müşteri işletmenin son kullanıcısına ait bir talep, veri sorumlusu sıfatıyla ilgili işletmeye yönlendirilir ve sözleşmedeki kapsamda teknik destek sağlanır.</p>
          </div>
        ) },
        { title: 'Güncelleme ve resmî kaynaklar', content: (
          <div className="space-y-3">
            <p>Veri işleme faaliyeti veya mevzuat değişirse metin sürümü güncellenir. Esaslı değişiklikler uygun kanaldan bildirilir; gerekiyorsa yeni bilgilendirme veya ayrı rıza süreci uygulanır.</p>
            <p>Resmî bilgi için <a className="text-primary underline" href="https://www.kvkk.gov.tr/Icerik/2033/Aydinlatma-Yukumlulugu-" target="_blank" rel="noreferrer">Aydınlatma Yükümlülüğü</a>, <a className="text-primary underline" href="https://www.kvkk.gov.tr/Icerik/2038/kisisel-verilerin-silinmesi-yok-edilmesi-veya-anonim-hale-getirilmesi" target="_blank" rel="noreferrer">Silme ve İmha</a> ve <a className="text-primary underline" href="https://www.kvkk.gov.tr/Icerik/2046/Ilgili-Kisiler-Tarafindan-Yapilan-Basvurularin-Cevaplanmasi-Yukumlulugu" target="_blank" rel="noreferrer">Başvuruların Cevaplanması</a> sayfaları incelenebilir.</p>
          </div>
        ) },
      ]}
    />
  )
}
