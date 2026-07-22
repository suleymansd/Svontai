import { LegalDocument } from '@/components/legal/legal-document'

export default function OpenWaConsentPage() {
  return (
    <LegalDocument
      title="WhatsApp QR Bağlantısı Risk ve Kullanım Onayı"
      updatedAt="22 Temmuz 2026"
      introduction={<p>Bu metin, QR koduyla kurulan WhatsApp bağlantısının niteliğini ve kullanıcı tarafından ayrıca kabul edilmesi gereken riskleri açıklar.</p>}
      sections={[
        { title: 'Bağlantının niteliği', content: <p>QR yöntemi resmi Meta WhatsApp Cloud API değildir; kullanıcının WhatsApp Web oturumunu teknik bir gateway üzerinden bağlar. Normal WhatsApp veya WhatsApp Business hesabıyla çalışabilir.</p> },
        { title: 'Bilinen riskler', content: <p>WhatsApp oturumu kapanabilir, QR yenileme gerekebilir, sağlayıcı değişiklikleri işlevi bozabilir ve WhatsApp hesabı geçici ya da kalıcı olarak kısıtlanabilir. Kesintisiz çalışma veya hesap kısıtlanmayacağı garanti edilmez.</p> },
        { title: 'Kullanıcı sorumlulukları', content: <p>Hesabın ve gönderilen içeriklerin hukuka, WhatsApp koşullarına ve ileti izinlerine uygun olması kullanıcı sorumluluğundadır. Spam, toplu izinsiz iletişim ve aldatıcı kullanım yasaktır.</p> },
        { title: 'İşlenen veriler', content: <p>Bağlantının çalışması için oturum kimliği, telefon bilgisi, kişi adı, mesaj içeriği, medya ve teslimat olayları işlenebilir. Oturum sırları kullanıcıya gösterilmez ve yetkisiz tenantlarla paylaşılmaz.</p> },
        { title: 'Alternatif ve bağlantıyı kesme', content: <p>Uygun işletmeler resmi Meta Cloud bağlantısını tercih edebilir. QR bağlantısı panelden veya telefondaki Bağlı Cihazlar bölümünden sonlandırılabilir; yeniden bağlantıda yeni QR gerekebilir.</p> },
        { title: 'Açık onay kaydı', content: <p>QR oluşturulmadan önce bu metin ayrıca kabul edilir. Kabul zamanı, metin sürümü, kullanıcı, tenant, IP ve tarayıcı bilgisi güvenlik/audit kaydı olarak tutulur.</p> },
      ]}
    />
  )
}
