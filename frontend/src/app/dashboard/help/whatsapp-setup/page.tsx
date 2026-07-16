'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import {
  ArrowLeft,
  Check,
  Circle,
  Smartphone,
  Building2,
  Shield,
  Globe,
  MessageSquare,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Loader2,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Zap
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

interface OnboardingStatus {
  steps: any[]
  current_step: string | null
  is_complete: boolean
  whatsapp_connected: boolean
  phone_number: string | null
}

// FAQ Items
const faqs = [
  {
    question: 'WhatsApp Business hesabım yok, ne yapmalıyım?',
    answer: `Normal WhatsApp hesabınızı QR kodla doğrudan bağlayabilirsiniz.

1. SmartWA'da "QR ile WhatsApp Bağla" seçeneğine basın
2. Telefonunuzda WhatsApp > Ayarlar > Bağlı Cihazlar bölümünü açın
3. QR kodu tarayın

Meta Business hesabı yalnızca resmi Meta Cloud yöntemini seçerseniz gerekir.`
  },
  {
    question: 'İşletme doğrulaması ne kadar sürer?',
    answer: `Meta işletme doğrulaması genellikle 1-3 iş günü sürer. Bazı durumlarda daha uzun sürebilir.

Doğrulama için gereken belgeler:
• Vergi levhası
• Ticaret sicil belgesi
• Faaliyet belgesi

Herhangi biri yeterlidir.`
  },
  {
    question: '24 saat kuralı nedir?',
    answer: `Meta WhatsApp Cloud API'de "24 saat kuralı" vardır:

• Müşteri size mesaj attığında 24 saatlik bir "pencere" açılır
• Bu süre içinde serbest mesaj gönderebilirsiniz
• 24 saat geçtikten sonra sadece onaylanmış şablonlar kullanabilirsiniz

SvontAi otomatik olarak bu kurala uyar ve müşterilerinize zamanında yanıt verir.`
  },
  {
    question: 'Mevcut WhatsApp numaramı kullanabilir miyim?',
    answer: `Evet. QR bağlantısında mevcut numaranız telefonunuzdaki WhatsApp uygulamasında çalışmaya devam eder.

Meta Cloud yöntemine geçerseniz numara taşıma ve Meta'nın numara kullanım koşulları uygulanır.`
  },
  {
    question: 'Kurulum sırasında hata alırsam ne yapmalıyım?',
    answer: `Kurulum hatası aldığınızda:

1. "Tekrar Dene" butonuna tıklayın
2. Meta hesabınızın izinlerini kontrol edin
3. İşletme doğrulamasının tamamlandığından emin olun

Sorun devam ederse:
• Kurulumu sıfırlayın ve baştan başlayın
• support@svontai.com adresinden destek alın`
  },
  {
    question: 'WhatsApp mesajlarının maliyeti nedir?',
    answer: `QR bağlantısında Meta konuşma ücreti yoktur; yalnızca SmartWA planı ve gateway sunucu maliyeti bulunur.

Meta WhatsApp Cloud API kullandığınızda Meta konuşma ücretleri uygulanabilir:

Konuşma Başına Ücret (Yaklaşık):
• Kullanıcı başlattı: İlk 1000/ay ücretsiz, sonra ~$0.005
• İşletme başlattı: ~$0.03

Ülkeye göre fiyatlar değişir. Detaylı bilgi için:
developers.facebook.com/docs/whatsapp/pricing`
  }
]

// Checklist items
const checklist = [
  {
    id: 'whatsapp_app',
    label: 'WhatsApp uygulaması',
    description: 'Normal WhatsApp veya WhatsApp Business yeterlidir'
  },
  {
    id: 'linked_devices',
    label: 'Bağlı Cihazlar erişimi',
    description: 'Telefonunuzdan QR kodu tarayabilmelisiniz'
  },
  {
    id: 'phone_number',
    label: 'Telefon numarası',
    description: 'WhatsApp hesabınız telefonda aktif olmalı'
  },
  {
    id: 'svontai_bot',
    label: 'SvontAi bot',
    description: 'En az bir aktif bot oluşturulmuş olmalı'
  }
]

export default function WhatsAppSetupHelpPage() {
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null)
  const [checkedItems, setCheckedItems] = useState<Set<string>>(new Set())

  // Fetch onboarding status for live status display
  const { data: status } = useQuery<OnboardingStatus>({
    queryKey: ['whatsapp-onboarding-status'],
    queryFn: () => api.get('/api/onboarding/whatsapp/status').then(res => res.data).catch(() => null),
  })

  const toggleFaq = (index: number) => {
    setExpandedFaq(expandedFaq === index ? null : index)
  }

  const toggleChecklist = (id: string) => {
    const newChecked = new Set(checkedItems)
    if (newChecked.has(id)) {
      newChecked.delete(id)
    } else {
      newChecked.add(id)
    }
    setCheckedItems(newChecked)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/dashboard/setup/whatsapp">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-green-500 flex items-center justify-center">
              <HelpCircle className="w-5 h-5 text-white" />
            </div>
            WhatsApp Kurulum Rehberi
          </h1>
          <p className="text-muted-foreground mt-1">
            Adım adım kurulum kılavuzu ve SSS
          </p>
        </div>
      </div>

      {/* Language Toggle */}
      <div className="flex gap-2">
        <Button variant="default" size="sm">🇹🇷 Türkçe</Button>
        <Button variant="outline" size="sm" disabled>🇬🇧 English (Soon)</Button>
      </div>

      {/* Quick Status */}
      {status && (
        <Card className={cn(
          status.whatsapp_connected 
            ? 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20'
            : 'border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20'
        )}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {status.whatsapp_connected ? (
                  <CheckCircle2 className="w-6 h-6 text-green-600" />
                ) : (
                  <AlertTriangle className="w-6 h-6 text-yellow-600" />
                )}
                <div>
                  <p className="font-medium">
                    {status.whatsapp_connected 
                      ? 'WhatsApp Bağlı' 
                      : 'WhatsApp Henüz Bağlı Değil'}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {status.whatsapp_connected 
                      ? status.phone_number 
                      : 'Kurulumu tamamlamak için aşağıdaki adımları takip edin'}
                  </p>
                </div>
              </div>
              <Link href="/dashboard/setup/whatsapp">
                <Button variant={status.whatsapp_connected ? 'outline' : 'default'} size="sm">
                  {status.whatsapp_connected ? 'Ayarlar' : 'Kuruluma Git'}
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {/* How It Works */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-violet-600" />
            Nasıl Çalışır?
          </CardTitle>
          <CardDescription>
            SvontAi WhatsApp entegrasyonu 3 basit adımda tamamlanır
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                step: 1,
                title: 'QR Bağlantısını Seçin',
                description: 'Normal WhatsApp veya WhatsApp Business hesabınızı seçin',
                icon: Shield,
                color: 'blue'
              },
              {
                step: 2,
                title: 'Kodu Tarayın',
                description: 'Telefonunuzdaki Bağlı Cihazlar menüsünden QR kodu tarayın',
                icon: Smartphone,
                color: 'green'
              },
              {
                step: 3,
                title: 'Otomatik Kurulum',
                description: 'SvontAi webhook ve API ayarlarını otomatik olarak yapar',
                icon: Zap,
                color: 'violet'
              }
            ].map((item) => (
              <div key={item.step} className="text-center">
                <div className={cn(
                  'w-16 h-16 mx-auto rounded-2xl flex items-center justify-center mb-4',
                  item.color === 'blue' && 'bg-blue-100 dark:bg-blue-900/30',
                  item.color === 'green' && 'bg-green-100 dark:bg-green-900/30',
                  item.color === 'violet' && 'bg-violet-100 dark:bg-violet-900/30'
                )}>
                  <item.icon className={cn(
                    'w-8 h-8',
                    item.color === 'blue' && 'text-blue-600',
                    item.color === 'green' && 'text-green-600',
                    item.color === 'violet' && 'text-violet-600'
                  )} />
                </div>
                <div className="text-sm font-medium text-muted-foreground mb-1">
                  Adım {item.step}
                </div>
                <h3 className="font-semibold mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Pre-Setup Checklist */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Check className="w-5 h-5 text-green-600" />
            Kurulum Öncesi Kontrol Listesi
          </CardTitle>
          <CardDescription>
            Başlamadan önce aşağıdakilerin hazır olduğundan emin olun
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {checklist.map((item) => (
              <div 
                key={item.id}
                className={cn(
                  'flex items-center gap-4 p-4 rounded-xl cursor-pointer transition-all',
                  checkedItems.has(item.id) 
                    ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                    : 'bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800'
                )}
                onClick={() => toggleChecklist(item.id)}
              >
                <div className={cn(
                  'w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 transition-all',
                  checkedItems.has(item.id) 
                    ? 'bg-green-500' 
                    : 'border-2 border-slate-300 dark:border-slate-600'
                )}>
                  {checkedItems.has(item.id) && (
                    <Check className="w-4 h-4 text-white" />
                  )}
                </div>
                <div className="flex-1">
                  <p className="font-medium">{item.label}</p>
                  <p className="text-sm text-muted-foreground">{item.description}</p>
                </div>
              </div>
            ))}
          </div>
          
          <div className="mt-6 p-4 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              <strong>💡 İpucu:</strong> Tüm maddeler tamamlandıysa, kurulum 1-3 dakika içinde tamamlanır.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* What You Do vs What We Do */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">👤 Sizin Yapacaklarınız</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {[
                'QR bağlantısını başlatın',
                'Telefonunuzda Bağlı Cihazlar menüsünü açın',
                'QR kodu tarayın',
                'Bağlantının hazır olmasını bekleyin'
              ].map((item, i) => (
                <li key={i} className="flex items-center gap-3">
                  <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-bold text-blue-600">{i + 1}</span>
                  </div>
                  <span className="text-sm">{item}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">🤖 SvontAi'ın Yapacakları</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {[
                'Tenant için özel oturum oluşturma',
                'İmzalı webhook yapılandırması',
                'Mesajları doğru tenant ve bota yönlendirme',
                'Bağlantı sağlığını takip etme',
                'Kopma durumunda hata ve aksiyon üretme'
              ].map((item, i) => (
                <li key={i} className="flex items-center gap-3">
                  <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
                  <span className="text-sm">{item}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      {/* Important Notes */}
      <Card className="border-yellow-200 dark:border-yellow-800">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-yellow-800 dark:text-yellow-200">
            <AlertTriangle className="w-5 h-5" />
            Önemli Notlar
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-4 rounded-xl bg-yellow-50 dark:bg-yellow-900/20">
            <h4 className="font-medium mb-2">📱 24 Saat Kuralı</h4>
            <p className="text-sm text-muted-foreground">
              WhatsApp Business API'de müşteri mesaj attıktan sonra 24 saat içinde 
              serbest yanıt verebilirsiniz. Bu süre geçtikten sonra yalnızca 
              önceden onaylanmış mesaj şablonları kullanılabilir.
            </p>
          </div>
          
          <div className="p-4 rounded-xl bg-yellow-50 dark:bg-yellow-900/20">
            <h4 className="font-medium mb-2">🚫 Spam Yasağı</h4>
            <p className="text-sm text-muted-foreground">
              WhatsApp'ın katı spam politikası vardır. İzinsiz toplu mesaj göndermek 
              hesabınızın askıya alınmasına neden olabilir. SvontAi yalnızca müşteri 
              başlattığı konuşmalara yanıt verir.
            </p>
          </div>
          
          <div className="p-4 rounded-xl bg-yellow-50 dark:bg-yellow-900/20">
            <h4 className="font-medium mb-2">📋 Şablon Mesajlar</h4>
            <p className="text-sm text-muted-foreground">
              24 saat dışında mesaj göndermek için Meta tarafından onaylanmış şablonlar 
              gerekir. Şablon oluşturma ve onay süreci ayrı bir işlemdir.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* FAQ */}
      <Card>
        <CardHeader>
          <CardTitle>Sık Sorulan Sorular</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {faqs.map((faq, index) => (
              <div 
                key={index}
                className="border rounded-xl overflow-hidden"
              >
                <button
                  className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                  onClick={() => toggleFaq(index)}
                >
                  <span className="font-medium pr-4">{faq.question}</span>
                  {expandedFaq === index ? (
                    <ChevronUp className="w-5 h-5 flex-shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="w-5 h-5 flex-shrink-0 text-muted-foreground" />
                  )}
                </button>
                {expandedFaq === index && (
                  <div className="px-4 pb-4">
                    <div className="pt-2 border-t">
                      <p className="text-sm text-muted-foreground whitespace-pre-line">
                        {faq.answer}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* External Links */}
      <Card>
        <CardHeader>
          <CardTitle>Faydalı Linkler</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid sm:grid-cols-2 gap-4">
            {[
              {
                title: 'Meta Business Suite',
                description: 'İşletme hesabınızı yönetin',
                url: 'https://business.facebook.com',
                icon: Building2
              },
              {
                title: 'Meta for Developers',
                description: 'WhatsApp API dokümantasyonu',
                url: 'https://developers.facebook.com/docs/whatsapp',
                icon: Globe
              },
              {
                title: 'WhatsApp Pricing',
                description: 'Konuşma ücretlendirmesi',
                url: 'https://developers.facebook.com/docs/whatsapp/pricing',
                icon: MessageSquare
              },
              {
                title: 'SvontAi Destek',
                description: 'Yardım ve destek',
                url: 'mailto:support@svontai.com',
                icon: HelpCircle
              }
            ].map((link) => (
              <a
                key={link.title}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-4 p-4 rounded-xl border hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
              >
                <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
                  <link.icon className="w-5 h-5 text-slate-600 dark:text-slate-400" />
                </div>
                <div className="flex-1">
                  <p className="font-medium">{link.title}</p>
                  <p className="text-sm text-muted-foreground">{link.description}</p>
                </div>
                <ExternalLink className="w-4 h-4 text-muted-foreground" />
              </a>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* CTA */}
      <div className="text-center py-8">
        <Link href="/dashboard/setup/whatsapp">
          <Button size="lg" className="bg-green-600 hover:bg-green-700">
            <Smartphone className="w-5 h-5 mr-2" />
            WhatsApp Kurulumuna Git
          </Button>
        </Link>
      </div>
    </div>
  )
}
