'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import {
  Activity,
  ArrowRight,
  BellRing,
  Bot,
  BookOpen,
  CalendarCheck,
  Check,
  ChevronRight,
  CircleHelp,
  FileText,
  Images,
  LifeBuoy,
  LockKeyhole,
  MessageSquareText,
  PhoneCall,
  Printer,
  Search,
  Settings2,
  Smartphone,
  Sparkles,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const guideSections = [
  { id: 'genel-bakis', label: 'SvontAI nasıl çalışır', summary: 'Otonom müşteri operasyonunun genel akışı', icon: Sparkles },
  { id: 'ilk-kurulum', label: 'İlk kurulum', summary: 'Kayıttan çalışan sisteme geçiş', icon: Settings2 },
  { id: 'whatsapp', label: 'WhatsApp bağlantısı', summary: 'QR ile telefonunuzu güvenli biçimde bağlama', icon: Smartphone },
  { id: 'ai-asistan', label: 'AI Asistanım', summary: 'Ana asistanı eğitme ve özelleştirme', icon: Bot },
  { id: 'medya', label: 'Medya kütüphanesi', summary: 'Görsel, video ve katalog paylaşımı', icon: Images },
  { id: 'mesajlar', label: 'Mesajlar ve müşteriler', summary: 'Konuşma ve müşteri kayıtlarını izleme', icon: MessageSquareText },
  { id: 'randevular', label: 'Randevular', summary: 'Hizmet, çalışma saati ve uygunluk yönetimi', icon: CalendarCheck },
  { id: 'aramalar', label: 'AI aramalar', summary: 'Otomatik arama ve görüşme kayıtları', icon: PhoneCall },
  { id: 'sistem-durumu', label: 'Sistem durumu', summary: 'Bağlantı ve otomasyon sağlığını izleme', icon: Activity },
  { id: 'raporlar', label: 'Raporlar ve bildirimler', summary: 'Günlük ve haftalık operasyon özeti', icon: BellRing },
  { id: 'guvenlik', label: 'Güvenli kullanım', summary: 'Hesap ve müşteri verilerini koruma', icon: LockKeyhole },
  { id: 'sorun-giderme', label: 'Sorun giderme', summary: 'En sık karşılaşılan durumların çözümü', icon: CircleHelp },
]

const setupSteps: Array<[string, string]> = [
  ['Hesabınızı doğrulayın', 'Kayıt sonrasında e-postanıza gelen altı haneli kodu girin.'],
  ['İşletmenizi tanıtın', 'Sektör, hizmetler, iletişim dili ve temel işletme bilgilerini yanıtlayın.'],
  ['WhatsApp\'ı bağlayın', 'QR kodu telefonunuzdaki Bağlı Cihazlar ekranından tarayın.'],
  ['Çalışma planını girin', 'Hizmet sürelerini, açık günleri ve randevu saatlerini belirleyin.'],
  ['Kontrol mesajı gönderin', 'Farklı bir numaradan WhatsApp hesabınıza mesaj atarak yanıtı doğrulayın.'],
]

const troubleshooting = [
  ['WhatsApp bağlantısı koptu', 'WhatsApp Bağlantısı ekranını açın. Sistem otomatik toparlayamadıysa “Yeni QR Oluştur” seçeneğini kullanıp telefonunuzdan yeniden tarayın.'],
  ['AI gelen mesaja cevap vermedi', 'Sistem Durumu ekranında WhatsApp ve Yapay Zeka satırlarının bağlı olduğunu kontrol edin. Ana asistanın aktif olduğundan emin olun; devam ederse Destek ekranından talep oluşturun.'],
  ['AI yanlış veya eksik bilgi verdi', 'AI Asistanım bölümünde “Ana Asistanı Eğit” veya “İşletme Bilgilerini Yenile” adımını kullanın. Fiyat, hizmet ve politika gibi değişen bilgileri güncel tutun.'],
  ['Randevu için uygun saat bulunamadı', 'Randevular > Çalışma Planı bölümünde en az bir aktif hizmet, çalışma günü ve saat aralığı bulunduğunu kontrol edip ayarları kaydedin.'],
  ['Görsel veya katalog gönderilmedi', 'Medya bölümünde dosyanın aktif olduğunu, açıklamasının ve müşteri talebiyle eşleşen anahtar kelimelerinin bulunduğunu kontrol edin.'],
  ['Test araması gelmedi', 'Aramalar sayfasında canlı aramanın aktif olduğunu, numaranın ülke koduyla yazıldığını ve günlük arama limitinin dolmadığını kontrol edin.'],
]

function StepList({ items }: { items: Array<[string, string]> }) {
  return (
    <ol className="mt-6 divide-y divide-border border-y border-border">
      {items.map(([title, description], index) => (
        <li key={title} className="grid gap-3 py-5 sm:grid-cols-[40px_1fr]">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-sm font-semibold text-primary-foreground">{index + 1}</span>
          <div>
            <h3 className="font-semibold">{title}</h3>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}

function GuideSection({ id, eyebrow, title, description, children }: {
  id: string
  eyebrow: string
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-24 border-b border-border py-12 first:pt-0">
      <p className="text-xs font-semibold uppercase text-primary">{eyebrow}</p>
      <h2 className="mt-2 text-2xl font-semibold sm:text-3xl">{title}</h2>
      <p className="mt-3 max-w-3xl leading-7 text-muted-foreground">{description}</p>
      {children}
    </section>
  )
}

export function CustomerGuide() {
  const [query, setQuery] = useState('')
  const searchResults = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('tr-TR')
    if (!normalized) return []
    return guideSections.filter((item) => `${item.label} ${item.summary}`.toLocaleLowerCase('tr-TR').includes(normalized))
  }, [query])

  return (
    <div className="bg-background">
      <section className="border-b border-border bg-muted/30">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8 lg:py-16">
          <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
            <div className="max-w-3xl">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="gap-1.5"><BookOpen className="h-3.5 w-3.5" />Müşteri Rehberi</Badge>
                <span className="text-xs text-muted-foreground">Son güncelleme: Temmuz 2026</span>
              </div>
              <h1 className="mt-5 text-4xl font-semibold sm:text-5xl">SvontAI kullanım kılavuzu</h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
                Kurulumdan günlük operasyona kadar SvontAI&apos;yi kullanmak için gereken tüm adımlar. Teknik bilgi gerekmez.
              </p>
            </div>
            <div className="flex gap-2 print:hidden">
              <Button variant="outline" onClick={() => window.print()}><Printer className="mr-2 h-4 w-4" />Yazdır</Button>
              <Button asChild><Link href="/login">Panele Git<ArrowRight className="ml-2 h-4 w-4" /></Link></Button>
            </div>
          </div>

          <div className="relative mt-8 max-w-2xl print:hidden">
            <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
            <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Örn. WhatsApp, randevu veya medya ara" className="h-12 bg-background pl-12" aria-label="Kılavuzda ara" />
            {query && (
              <div className="absolute left-0 right-0 top-14 z-20 border border-border bg-background p-2 shadow-xl">
                {searchResults.length ? searchResults.map((item) => {
                  const Icon = item.icon
                  return (
                    <a key={item.id} href={`#${item.id}`} onClick={() => setQuery('')} className="flex items-center gap-3 px-3 py-3 hover:bg-muted">
                      <Icon className="h-4 w-4 text-primary" />
                      <span className="flex-1"><span className="block text-sm font-medium">{item.label}</span><span className="block text-xs text-muted-foreground">{item.summary}</span></span>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </a>
                  )
                }) : <p className="px-3 py-4 text-sm text-muted-foreground">Bu ifadeyle eşleşen bölüm bulunamadı.</p>}
              </div>
            )}
          </div>
        </div>
      </section>

      <div className="mx-auto grid max-w-7xl gap-12 px-4 py-12 sm:px-6 lg:grid-cols-[240px_minmax(0,1fr)] lg:px-8">
        <aside className="hidden lg:block print:hidden">
          <nav className="sticky top-24 space-y-1" aria-label="Kılavuz bölümleri">
            <p className="mb-3 px-3 text-xs font-semibold uppercase text-muted-foreground">Bu sayfada</p>
            {guideSections.map((item) => {
              const Icon = item.icon
              return <a key={item.id} href={`#${item.id}`} className="flex items-center gap-2.5 px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"><Icon className="h-4 w-4" />{item.label}</a>
            })}
          </nav>
        </aside>

        <article className="min-w-0 max-w-4xl">
          <GuideSection id="genel-bakis" eyebrow="Genel bakış" title="SvontAI işletmeniz için ne yapar?" description="SvontAI, WhatsApp üzerinden gelen müşteri taleplerini karşılar; işletme bilginizi kullanarak yanıt verir ve gerekli operasyon kayıtlarını kendisi oluşturur.">
            <div className="mt-7 grid gap-px overflow-hidden border border-border bg-border sm:grid-cols-2 lg:grid-cols-4">
              {[
                { icon: MessageSquareText, title: 'Mesajı anlar', text: 'Müşterinin ne istediğini ve konuşma geçmişini değerlendirir.' },
                { icon: Bot, title: 'Doğru yanıtı üretir', text: 'İşletme profili, bilgi tabanı ve kuralları kullanır.' },
                { icon: CalendarCheck, title: 'Aksiyonu tamamlar', text: 'Müşteri, randevu veya destek kaydı oluşturabilir.' },
                { icon: BellRing, title: 'Size raporlar', text: 'Önemli hareketleri panel ve e-posta özetlerine işler.' },
              ].map((item) => <div key={item.title} className="bg-background p-5"><item.icon className="h-5 w-5 text-primary" /><h3 className="mt-4 font-semibold">{item.title}</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">{item.text}</p></div>)}
            </div>
            <div className="mt-6 flex items-start gap-3 border-l-4 border-primary bg-primary/5 p-4">
              <Check className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <p className="text-sm leading-6"><strong>Günlük kullanım:</strong> Sistemi sürekli yönetmeniz gerekmez. Sistem Durumu ve raporları kontrol etmeniz; yalnızca değişen fiyat, hizmet ve çalışma saatlerini güncellemeniz yeterlidir.</p>
            </div>
          </GuideSection>

          <GuideSection id="ilk-kurulum" eyebrow="Başlangıç" title="İlk kurulumu tamamlayın" description="Kurulum sihirbazı verdiğiniz cevaplardan ana asistanı ve işletme profilini otomatik hazırlar. Bilgi kaynağı yüklemek isteğe bağlıdır.">
            <StepList items={setupSteps} />
            <div className="mt-6 flex flex-wrap gap-3 print:hidden"><Button asChild><Link href="/register">Hesap Oluştur</Link></Button><Button variant="outline" asChild><Link href="/dashboard/onboarding">Kurulumu Aç</Link></Button></div>
          </GuideSection>

          <GuideSection id="whatsapp" eyebrow="Bağlantı" title="WhatsApp hesabınızı bağlayın" description="Mevcut WhatsApp veya WhatsApp Business hesabınızı QR koduyla bağlayabilirsiniz. Telefon numaranızı değiştirmeniz gerekmez.">
            <StepList items={[
              ['QR kodunu oluşturun', 'Panelde WhatsApp Bağlantısı sayfasına gidin ve bağlantı başlatın.'],
              ['Telefonda Bağlı Cihazlar\'ı açın', 'WhatsApp > Ayarlar > Bağlı Cihazlar > Cihaz Bağla yolunu izleyin.'],
              ['QR kodunu tarayın', 'Paneldeki kodu telefon kameranızla okutun ve bağlantı durumunun “Bağlı” olmasını bekleyin.'],
              ['Test mesajı gönderin', 'Bağlanan hesaba farklı bir numaradan mesaj gönderin; konuşmanın Mesajlar ekranına düştüğünü kontrol edin.'],
            ]} />
            <div className="mt-6 border border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">Telefonunuz internete bağlı kalmalıdır. WhatsApp oturumu kapanırsa SvontAI yeniden bağlanmayı dener; yeni QR istenirse bağlantı ekranındaki yönlendirmeyi izleyin.</div>
          </GuideSection>

          <GuideSection id="ai-asistan" eyebrow="Yapay zeka" title="Ana asistanınızı eğitin" description="Her işletme için bir Ana Asistan otomatik oluşturulur. Bu asistan tüm müşteri konuşmalarının ortak zekâsıdır; ek botlar özel görevler için kullanılabilir.">
            <div className="mt-6 grid gap-6 sm:grid-cols-2">
              <div className="border-l-2 border-primary pl-5"><h3 className="font-semibold">Ana Asistan</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">İşletmenin tonu, hizmetleri, politikaları ve temel yanıt kurallarını yönetir. “Ana Asistanı Eğit” ile seçenekli soruları yanıtlamanız yeterlidir.</p></div>
              <div className="border-l-2 border-border pl-5"><h3 className="font-semibold">Özel botlar</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">Katalog gönderme, teklif toplama veya belirli bir departman gibi dar görevleri üstlenir; ana asistanla birlikte çalışır.</p></div>
            </div>
            <h3 className="mt-8 font-semibold">Ne zaman güncellemelisiniz?</h3>
            <ul className="mt-3 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">{['Fiyat veya kampanya değiştiğinde', 'Yeni hizmet eklediğinizde', 'Çalışma saatleri değiştiğinde', 'İade, teslimat veya rezervasyon kuralı değiştiğinde'].map((item) => <li key={item} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 text-emerald-600" />{item}</li>)}</ul>
          </GuideSection>

          <GuideSection id="medya" eyebrow="İçerik" title="Görsel, video ve katalogları tanıtın" description="Medya Kütüphanesi'ne yüklediğiniz içerikleri AI, müşterinin talebine göre seçip WhatsApp üzerinden paylaşabilir.">
            <StepList items={[
              ['Dosyayı yükleyin', 'JPEG, PNG, WebP, MP4 veya PDF dosyanızı seçin.'],
              ['Açıklayıcı bir ad yazın', '“2026 Gelinlik Kataloğu” gibi müşterinin talebiyle eşleşen bir ad kullanın.'],
              ['Anahtar kelimeleri ekleyin', 'gelinlik, beyaz, katalog, fiyat gibi doğal arama ifadeleri yazın.'],
              ['AI kullanımını açın', 'İçeriği aktif tutun ve gönderim sayısını Medya ekranından izleyin.'],
            ]} />
          </GuideSection>

          <GuideSection id="mesajlar" eyebrow="Günlük operasyon" title="Mesajları ve müşteri kayıtlarını izleyin" description="Mesajlar ekranı konuşma geçmişini; Müşteriler ekranı ise AI tarafından yakalanan iletişim bilgilerini ve talepleri gösterir.">
            <div className="mt-6 grid gap-px overflow-hidden border border-border bg-border sm:grid-cols-3">{[
              ['Mesajlar', 'Kim yazdı, ne konuşuldu ve AI ne yanıtladı bilgisini inceleyin.'],
              ['AI hariç tutma', 'Aile, ekip veya özel kişilerde konuşmayı açıp “AI otomatik yanıt” anahtarını kapatın. Mesaj görünür kalır; AI, n8n ve otomatik arama bu kişiye yanıt üretmez.'],
              ['Müşteriler', 'Telefon, isim, ilgi alanı ve müşteri durumunu takip edin.'],
              ['İnsan desteği', 'AI çözemediğinde oluşan destek kaydını Destek bölümünden yönetin.'],
            ].map(([title, text]) => <div key={title} className="bg-background p-5"><h3 className="font-semibold">{title}</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">{text}</p></div>)}</div>
          </GuideSection>

          <GuideSection id="randevular" eyebrow="Takvim" title="Randevu uygunluğunu yapılandırın" description="AI yalnızca tanımladığınız hizmetleri ve boş saatleri sunar. Müşteri onayladığında randevu otomatik olarak SvontAI'ye, bağlıysa Google Calendar'a kaydedilir.">
            <StepList items={[
              ['Hizmetleri ekleyin', 'Hizmet adını, görüşme süresini ve aktiflik durumunu belirleyin.'],
              ['Çalışma saatlerini seçin', 'Her gün için açık/kapalı durumunu ve saat aralığını girin.'],
              ['Saat dilimini kontrol edin', 'İşletmenizin bulunduğu saat dilimini kullanın.'],
              ['Planı kaydedin', 'Uygun saatlerin oluştuğunu kontrol edin ve bir deneme randevusu alın.'],
            ]} />
          </GuideSection>

          <GuideSection id="aramalar" eyebrow="Sesli asistan" title="AI aramalarını güvenli biçimde yönetin" description="Canlı arama hizmeti hesabınızda etkinse SvontAI arama talebi, randevu ve takip senaryolarında müşteriyi Türkçe arayabilir.">
            <div className="mt-6 grid gap-4 sm:grid-cols-2">{[
              ['Tetikleyiciler', 'Müşteri arama istedi, randevu niyeti veya sizin oluşturduğunuz test araması.'],
              ['Güvenlik sınırları', 'Günlük limit, tekrar deneme sayısı ve aynı müşteriyi yeniden arama süresi.'],
              ['Randevu işlemi', 'Asistan uygun saatleri kontrol eder ve müşteri onayıyla kaydı oluşturur.'],
              ['Görüşme kaydı', 'Durum, süre, özet ve oluşan aksiyonlar Aramalar ekranına işlenir.'],
            ].map(([title, text]) => <div key={title} className="border-t border-border pt-4"><h3 className="font-semibold">{title}</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">{text}</p></div>)}</div>
          </GuideSection>

          <GuideSection id="sistem-durumu" eyebrow="Sağlık" title="Sistemin çalıştığını doğrulayın" description="Sistem Durumu ekranı WhatsApp, yapay zekâ, otomasyon ve bağlı servislerin sağlık bilgisini tek yerde gösterir.">
            <div className="mt-6 divide-y divide-border border-y border-border">{[
              ['Bağlı', 'Entegrasyon çalışıyor ve işlem yapmaya hazır.', 'bg-emerald-500'],
              ['İşlem gerekli', 'Kullanıcı izni, QR taraması veya eksik bilgi gerekiyor.', 'bg-amber-500'],
              ['Bağlantı kesildi', 'Sistem yeniden bağlanmayı dener; gerekirse yeni QR üretir.', 'bg-red-500'],
            ].map(([label, text, color]) => <div key={label} className="flex items-start gap-3 py-4"><span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${color}`} /><div><h3 className="font-medium">{label}</h3><p className="mt-1 text-sm text-muted-foreground">{text}</p></div></div>)}</div>
          </GuideSection>

          <GuideSection id="raporlar" eyebrow="Takip" title="Rapor ve çalışma bildirimlerini kullanın" description="SvontAI, etkinliğe göre günlük veya haftalık özetler gönderir. Raporlarda gelen mesaj, AI yanıtı, yeni müşteri, randevu ve otomasyon sonuçlarını görürsünüz.">
            <div className="mt-6 flex items-start gap-4 bg-muted/50 p-5"><FileText className="mt-0.5 h-6 w-6 shrink-0 text-primary" /><div><h3 className="font-semibold">Dikkat gerektiren durum</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">Raporda bu ifade görünürse başarısız otomasyon veya düşük yanıt oranı algılanmıştır. Sistem Durumu ve Destek ekranını kontrol edin; başarısızlık ayrıntısını görmeden aynı işlemi tekrar tekrar başlatmayın.</p></div></div>
          </GuideSection>

          <GuideSection id="guvenlik" eyebrow="Güvenlik" title="Hesabınızı ve müşteri verilerini koruyun" description="SvontAI yalnızca işletme operasyonu için gereken verilere erişmelidir. Hesap erişimlerini kişisel cihazlarınız gibi koruyun.">
            <ul className="mt-6 space-y-3 text-sm leading-6">{[
              'Şifrenizi başka hizmetlerde kullanmayın ve doğrulama kodunu kimseyle paylaşmayın.',
              'WhatsApp QR kodunu yalnızca kendi panelinizde ve kendi telefonunuzla tarayın.',
              'Ortak bilgisayarda oturumu açık bırakmayın; ekipten ayrılan kişilerin erişimini kaldırın.',
              'Müşteriden gerekli olmayan özel veya hassas bilgileri istemeyin.',
              'Şüpheli mesaj, arama veya veri hareketini Destek ekranından hemen bildirin.',
            ].map((item) => <li key={item} className="flex gap-3"><LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-primary" />{item}</li>)}</ul>
          </GuideSection>

          <GuideSection id="sorun-giderme" eyebrow="Yardım" title="Sık karşılaşılan durumlar" description="Aşağıdaki kontroller sorunun büyük bölümünü birkaç dakika içinde çözmenize yardımcı olur.">
            <div className="mt-6 divide-y divide-border border-y border-border">{troubleshooting.map(([title, answer]) => <div key={title} className="py-5"><h3 className="font-semibold">{title}</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">{answer}</p></div>)}</div>
          </GuideSection>

          <section className="mt-12 bg-foreground p-6 text-background sm:p-8 print:hidden">
            <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-center">
              <div><LifeBuoy className="h-6 w-6" /><h2 className="mt-4 text-2xl font-semibold">Yardıma mı ihtiyacınız var?</h2><p className="mt-2 max-w-xl text-sm opacity-70">Sorununuzu ve gördüğünüz hata mesajını Destek ekibine iletin.</p></div>
              <Button variant="secondary" asChild><Link href="/dashboard/tickets">Destek Talebi Oluştur<ArrowRight className="ml-2 h-4 w-4" /></Link></Button>
            </div>
          </section>
        </article>
      </div>
    </div>
  )
}
