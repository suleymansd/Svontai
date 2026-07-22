import { LegalDocument } from '@/components/legal/legal-document'

export default function KvkkPage() {
  return (
    <LegalDocument
      title="KVKK Aydınlatma Metni"
      updatedAt="22 Temmuz 2026"
      introduction={<p>Bu metin, SvontAI hesabının açılması ve platformun kullanılması sırasında 6698 sayılı Kişisel Verilerin Korunması Kanunu kapsamında yapılan veri işleme faaliyetlerine ilişkin bilgilendirmedir.</p>}
      notice={<p>SvontAI içinde çevrim içi ücret tahsilatı yapılmaz. Veri sorumlusunun/satıcı hizmet sağlayıcının tam adı veya unvanı, adresi ve vergi bilgileri ücretli aktivasyondan önce müşteriye sunulan imzalı teklif ve sipariş formunda ayrıca bildirilir. Bu bilgiler tamamlanmadan ücretli hizmet başlatılmaz.</p>}
      sections={[
        { title: 'Veri sorumlusu ve iletişim', content: <p>Platformun veri sorumlusu SvontAI hizmet sağlayıcısıdır. Veri koruma başvuruları support@svontai.com adresine veya paneldeki Destek alanına iletilir. Ticari hizmet sağlayıcının açık kimlik ve tebligat bilgileri, ücretli aktivasyon öncesi sözleşme ekinde yer alır.</p> },
        { title: 'İşlenen kişisel veriler', content: <p>Kimlik ve iletişim bilgileri, hesap/rol bilgileri, işletme profili, işlem güvenliği kayıtları, IP ve cihaz bilgileri, destek yazışmaları, entegrasyon kayıtları, kullanım verileri ve işletme tarafından platforma aktarılan müşteri iletişim verileri işlenebilir.</p> },
        { title: 'İşleme amaçları', content: <p>Üyelik ve sözleşme süreçlerini yürütmek, hizmeti kurmak ve sunmak, kullanıcı yetkilerini yönetmek, güvenliği sağlamak, talepleri yanıtlamak, hizmeti geliştirmek, yedekleme yapmak ve hukuki yükümlülükleri yerine getirmek amaçlarıyla işleme yapılır.</p> },
        { title: 'Toplama yöntemi ve hukuki sebepler', content: <p>Veriler web formları, entegrasyonlar, API/webhook olayları, destek kanalları ve sistem logları üzerinden otomatik veya kısmen otomatik yollarla toplanır. İşleme; sözleşmenin kurulması/ifası, hukuki yükümlülük, hakkın tesisi veya korunması ve temel haklara zarar vermeyen meşru menfaat sebeplerine; gereken özel durumlarda açık rızaya dayanır.</p> },
        { title: 'Aktarım', content: <p>Veriler; barındırma, e-posta, depolama, hata izleme, yapay zeka, WhatsApp, telefon ve otomasyon sağlayıcılarına hizmetin gerektirdiği ölçüde; yetkili kamu kurumlarına ise yasal zorunluluk halinde aktarılabilir. Yurt dışı aktarım gereken durumlarda yürürlükteki KVKK aktarım şartları uygulanır.</p> },
        { title: 'İlgili kişi hakları', content: <p>KVKK madde 11 kapsamındaki işlenip işlenmediğini öğrenme, bilgi isteme, amacına uygun kullanımı öğrenme, aktarılan tarafları bilme, düzeltme, silme/yok etme isteme, bu işlemlerin aktarılanlara bildirilmesini isteme, otomatik sonuçlara itiraz ve zarar halinde tazminat talep etme hakları kullanılabilir.</p> },
        { title: 'Başvuru usulü', content: <p>Başvuruda ad-soyad, talep konusu, hesap e-postası ve kimlik/yetki doğrulamasına yetecek bilgiler bulunmalıdır. Başvurular niteliğine göre yasal süre içinde ve kural olarak ücretsiz sonuçlandırılır.</p> },
      ]}
    />
  )
}
