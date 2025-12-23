'use client'

import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Logo, LogoIcon } from '@/components/Logo'
import { 
  Users, 
  Brain, 
  Globe, 
  ArrowRight,
  Check,
  Sparkles,
  Clock,
  BarChart3,
  Shield,
  Zap,
  ChevronRight,
  Play,
  Star,
  MessageSquare
} from 'lucide-react'

export default function HomePage() {
  return (
    <div className="min-h-screen bg-background overflow-hidden">
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 glass">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link href="/" className="flex items-center gap-2">
              <Logo size="md" showText={true} animated={true} />
            </Link>
            
            <div className="hidden md:flex items-center gap-8">
              <Link href="#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Özellikler
              </Link>
              <Link href="#how-it-works" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Nasıl Çalışır
              </Link>
              <Link href="#pricing" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Fiyatlar
              </Link>
              <Link href="#faq" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                SSS
              </Link>
            </div>
            
            <div className="flex items-center gap-3">
              <Link href="/login">
                <Button variant="ghost" size="sm" className="hidden sm:flex">
                  Giriş Yap
                </Button>
              </Link>
              <Link href="/register">
                <Button size="sm" className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 shadow-lg shadow-blue-500/25 btn-shine">
                  Ücretsiz Başla
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-24 px-4 sm:px-6 lg:px-8">
        {/* Background Effects */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-20 left-1/4 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl animate-float" />
          <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-violet-500/20 rounded-full blur-3xl animate-float" style={{ animationDelay: '2s' }} />
          <div className="absolute inset-0 dot-pattern opacity-50" />
        </div>

        <div className="max-w-7xl mx-auto">
          <div className="text-center max-w-4xl mx-auto">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass mb-8 animate-fade-in-up">
              <Sparkles className="w-4 h-4 text-yellow-500" />
              <span className="text-sm font-medium">Yapay Zeka ile Müşteri Desteğinde Devrim</span>
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            </div>
            
            {/* Headline */}
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-8 animate-fade-in-up stagger-1">
              WhatsApp Müşteri Desteğinizi{' '}
              <span className="gradient-text">Otomatikleştirin</span>
            </h1>
            
            {/* Subheadline */}
            <p className="text-xl text-muted-foreground mb-10 max-w-2xl mx-auto leading-relaxed animate-fade-in-up stagger-2">
              SvontAi ile müşterilerinize 7/24 anında yanıt verin. 
              Yapay zeka destekli asistanınız hiç uyumaz, tatile çıkmaz 
              ve her zaman mükemmel hizmet sunar.
            </p>
            
            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center animate-fade-in-up stagger-3">
              <Link href="/register">
                <Button size="lg" className="w-full sm:w-auto bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 text-lg px-8 h-14 rounded-2xl shadow-2xl shadow-blue-500/30 btn-shine">
                  14 Gün Ücretsiz Dene
                  <ArrowRight className="ml-2 w-5 h-5" />
                </Button>
              </Link>
              <Button 
                size="lg" 
                variant="outline" 
                className="w-full sm:w-auto text-lg px-8 h-14 rounded-2xl glass"
                onClick={() => window.open('https://youtu.be/demo', '_blank')}
              >
                <Play className="mr-2 w-5 h-5" />
                Demo İzle
              </Button>
            </div>

            {/* Trust Badges */}
            <div className="flex flex-wrap items-center justify-center gap-6 mt-12 animate-fade-in-up stagger-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Shield className="w-4 h-4 text-green-500" />
                <span>KVKK Uyumlu</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Zap className="w-4 h-4 text-yellow-500" />
                <span>3 Saniyede Yanıt</span>
              </div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Star className="w-4 h-4 text-orange-500" />
                <span>4.9/5 Müşteri Puanı</span>
              </div>
            </div>
          </div>

          {/* Hero Image / Dashboard Preview */}
          <div className="mt-20 relative animate-fade-in-up stagger-5">
            <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-transparent z-10 pointer-events-none" />
            <div className="relative mx-auto max-w-5xl">
              <div className="rounded-3xl overflow-hidden shadow-2xl shadow-black/20 border border-white/10 glass">
                <div className="bg-gradient-to-br from-slate-900 to-slate-800 p-1">
                  {/* Browser Chrome */}
                  <div className="flex items-center gap-2 px-4 py-3 border-b border-white/10">
                    <div className="flex gap-1.5">
                      <div className="w-3 h-3 rounded-full bg-red-500" />
                      <div className="w-3 h-3 rounded-full bg-yellow-500" />
                      <div className="w-3 h-3 rounded-full bg-green-500" />
                    </div>
                    <div className="flex-1 flex justify-center">
                      <div className="px-4 py-1 rounded-lg bg-white/5 text-xs text-white/60">
                        app.svontai.com/dashboard
                      </div>
                    </div>
                  </div>
                  {/* Dashboard Preview */}
                  <div className="aspect-[16/9] bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-8">
                    <div className="grid grid-cols-4 gap-4 h-full">
                      {/* Sidebar */}
                      <div className="col-span-1 bg-white dark:bg-slate-800 rounded-2xl p-4 shadow-lg">
                        <div className="flex items-center gap-2 mb-6">
                          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600" />
                          <div className="h-4 w-20 bg-slate-200 dark:bg-slate-700 rounded" />
                        </div>
                        {[1, 2, 3, 4, 5].map((i) => (
                          <div key={i} className={`flex items-center gap-2 p-2 rounded-lg mb-2 ${i === 1 ? 'bg-blue-50 dark:bg-blue-900/30' : ''}`}>
                            <div className="w-5 h-5 bg-slate-200 dark:bg-slate-700 rounded" />
                            <div className="h-3 w-16 bg-slate-200 dark:bg-slate-700 rounded" />
                          </div>
                        ))}
                      </div>
                      {/* Main Content */}
                      <div className="col-span-3 space-y-4">
                        {/* Stats */}
                        <div className="grid grid-cols-3 gap-4">
                          {[
                            { color: 'from-blue-500 to-cyan-500', value: '2,847' },
                            { color: 'from-violet-500 to-purple-500', value: '156' },
                            { color: 'from-green-500 to-emerald-500', value: '%98' }
                          ].map((stat, i) => (
                            <div key={i} className="bg-white dark:bg-slate-800 rounded-2xl p-4 shadow-lg">
                              <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} mb-3`} />
                              <div className="text-2xl font-bold text-slate-900 dark:text-white">{stat.value}</div>
                              <div className="h-2 w-20 bg-slate-200 dark:bg-slate-700 rounded mt-1" />
                            </div>
                          ))}
                        </div>
                        {/* Chart Area */}
                        <div className="bg-white dark:bg-slate-800 rounded-2xl p-4 shadow-lg flex-1">
                          <div className="h-3 w-32 bg-slate-200 dark:bg-slate-700 rounded mb-4" />
                          <div className="flex items-end gap-2 h-32">
                            {[40, 65, 45, 80, 55, 90, 70, 85, 60, 75, 95, 80].map((h, i) => (
                              <div 
                                key={i} 
                                className="flex-1 bg-gradient-to-t from-blue-500 to-violet-500 rounded-t-lg"
                                style={{ height: `${h}%` }}
                              />
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 relative">
        <div className="absolute inset-0 grid-pattern" />
        <div className="max-w-7xl mx-auto relative">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { value: '10K+', label: 'Aktif Kullanıcı', icon: Users },
              { value: '5M+', label: 'Mesaj Yanıtlandı', icon: MessageSquare },
              { value: '%99.9', label: 'Uptime', icon: Zap },
              { value: '<2s', label: 'Ort. Yanıt Süresi', icon: Clock },
            ].map((stat, i) => (
              <div key={i} className="text-center group">
                <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500/10 to-violet-500/10 mb-4 group-hover:scale-110 transition-transform">
                  <stat.icon className="w-6 h-6 text-blue-600" />
                </div>
                <div className="text-4xl font-bold gradient-text mb-2">{stat.value}</div>
                <div className="text-muted-foreground">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 text-sm font-medium mb-4">
              <Sparkles className="w-4 h-4" />
              Özellikler
            </div>
            <h2 className="text-4xl sm:text-5xl font-bold mb-4">
              Neden <span className="font-bold">Svont<span className="rainbow-text">Ai</span></span>?
            </h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              İşletmenizi 7/24 açık tutun, hiçbir müşteri mesajını kaçırmayın
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[
              {
                icon: Clock,
                title: '7/24 Kesintisiz Hizmet',
                description: 'Müşterilerinize gece gündüz demeden anında yanıt verin. Tatil, hafta sonu yok.',
                color: 'from-blue-500 to-cyan-500'
              },
              {
                icon: Brain,
                title: 'Akıllı AI Yanıtları',
                description: 'GPT-4 tabanlı yapay zeka, müşterilerinize doğal ve bağlama uygun yanıtlar verir.',
                color: 'from-violet-500 to-purple-500'
              },
              {
                icon: Users,
                title: 'Otomatik Lead Toplama',
                description: 'Potansiyel müşteri bilgilerini otomatik olarak toplayın ve CRM\'e aktarın.',
                color: 'from-pink-500 to-rose-500'
              },
              {
                icon: Globe,
                title: 'Çoklu Kanal Desteği',
                description: 'WhatsApp ve web widget ile tüm platformlarda aynı kalitede hizmet.',
                color: 'from-green-500 to-emerald-500'
              },
              {
                icon: BarChart3,
                title: 'Detaylı Analizler',
                description: 'Konuşma istatistikleri, müşteri memnuniyeti ve performans metrikleri.',
                color: 'from-orange-500 to-amber-500'
              },
              {
                icon: Shield,
                title: 'Güvenli & KVKK Uyumlu',
                description: 'Verileriniz şifreli, güvenli sunucularda saklanır. Tam KVKK uyumluluğu.',
                color: 'from-teal-500 to-cyan-500'
              },
            ].map((feature, i) => (
              <div 
                key={i} 
                className="group relative p-8 rounded-3xl bg-white dark:bg-slate-900 border border-slate-200/50 dark:border-slate-800 card-hover"
              >
                <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${feature.color} flex items-center justify-center mb-6 shadow-lg group-hover:scale-110 transition-transform`}>
                  <feature.icon className="w-7 h-7 text-white" />
                </div>
                <h3 className="text-xl font-semibold mb-3">{feature.title}</h3>
                <p className="text-muted-foreground leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-24 px-4 sm:px-6 lg:px-8 bg-slate-50 dark:bg-slate-900/50">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-violet-50 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400 text-sm font-medium mb-4">
              <Zap className="w-4 h-4" />
              Nasıl Çalışır
            </div>
            <h2 className="text-4xl sm:text-5xl font-bold mb-4">
              3 Adımda <span className="gradient-text">Başlayın</span>
            </h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              Dakikalar içinde kendi AI asistanınızı oluşturun
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                step: '01',
                title: 'Hesap Oluşturun',
                description: 'Ücretsiz hesabınızı açın ve işletme bilgilerinizi girin.',
                icon: Users
              },
              {
                step: '02',
                title: 'Botu Eğitin',
                description: 'Bilgi tabanınızı ekleyin. SSS, ürün bilgileri, iletişim detayları.',
                icon: Brain
              },
              {
                step: '03',
                title: 'Yayına Alın',
                description: 'WhatsApp\'ı bağlayın veya web sitenize widget ekleyin. Hepsi bu!',
                icon: Zap
              },
            ].map((item, i) => (
              <div key={i} className="relative">
                {i < 2 && (
                  <div className="hidden md:block absolute top-20 left-full w-full h-0.5 bg-gradient-to-r from-blue-500 to-transparent -translate-x-1/2" />
                )}
                <div className="text-center p-8">
                  <div className="relative inline-block mb-6">
                    <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-xl shadow-blue-500/30">
                      <item.icon className="w-10 h-10 text-white" />
                    </div>
                    <div className="absolute -top-2 -right-2 w-8 h-8 rounded-full bg-white dark:bg-slate-800 shadow-lg flex items-center justify-center text-sm font-bold gradient-text">
                      {item.step}
                    </div>
                  </div>
                  <h3 className="text-xl font-semibold mb-3">{item.title}</h3>
                  <p className="text-muted-foreground">{item.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400 text-sm font-medium mb-4">
              <Star className="w-4 h-4" />
              Fiyatlandırma
            </div>
            <h2 className="text-4xl sm:text-5xl font-bold mb-4">
              Şeffaf <span className="gradient-text">Fiyatlar</span>
            </h2>
            <p className="text-xl text-muted-foreground">
              İhtiyacınıza uygun planı seçin, gizli ücret yok
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            {[
              {
                name: 'Başlangıç',
                price: '₺299',
                description: 'Küçük işletmeler için',
                features: ['1 Bot', '1,000 mesaj/ay', 'Web Widget', 'E-posta desteği', 'Temel analizler'],
                popular: false,
                cta: 'Başla'
              },
              {
                name: 'Profesyonel',
                price: '₺699',
                description: 'Büyüyen işletmeler için',
                features: ['5 Bot', '10,000 mesaj/ay', 'WhatsApp entegrasyonu', 'Öncelikli destek', 'Gelişmiş analizler', 'API erişimi'],
                popular: true,
                cta: 'Popüler Plan'
              },
              {
                name: 'Kurumsal',
                price: '₺1,999',
                description: 'Büyük ölçekli operasyonlar',
                features: ['Sınırsız bot', 'Sınırsız mesaj', 'Özel entegrasyonlar', '7/24 destek', 'SLA garantisi', 'Özel eğitim'],
                popular: false,
                cta: 'İletişime Geç'
              },
            ].map((plan, i) => (
              <div 
                key={i}
                className={`relative p-8 rounded-3xl ${
                  plan.popular 
                    ? 'bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-2xl shadow-blue-500/30 scale-105 z-10' 
                    : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800'
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1.5 bg-gradient-to-r from-yellow-400 to-orange-500 text-slate-900 text-sm font-bold rounded-full shadow-lg">
                    En Popüler
                  </div>
                )}
                <div className="text-center mb-8">
                  <h3 className={`text-xl font-semibold mb-2 ${plan.popular ? 'text-white' : ''}`}>
                    {plan.name}
                  </h3>
                  <p className={`text-sm mb-4 ${plan.popular ? 'text-blue-100' : 'text-muted-foreground'}`}>
                    {plan.description}
                  </p>
                  <div className="flex items-baseline justify-center gap-1">
                    <span className={`text-5xl font-bold ${plan.popular ? 'text-white' : 'gradient-text'}`}>
                      {plan.price}
                    </span>
                    <span className={plan.popular ? 'text-blue-100' : 'text-muted-foreground'}>/ay</span>
                  </div>
                </div>
                <ul className="space-y-4 mb-8">
                  {plan.features.map((feature, j) => (
                    <li key={j} className="flex items-center gap-3">
                      <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
                        plan.popular ? 'bg-white/20' : 'bg-green-100 dark:bg-green-900/30'
                      }`}>
                        <Check className={`w-3 h-3 ${plan.popular ? 'text-white' : 'text-green-600'}`} />
                      </div>
                      <span className={plan.popular ? 'text-blue-50' : 'text-muted-foreground'}>
                        {feature}
                      </span>
                    </li>
                  ))}
                </ul>
                <Link href="/register">
                  <Button 
                    className={`w-full h-12 rounded-xl font-semibold ${
                      plan.popular 
                        ? 'bg-white text-blue-600 hover:bg-blue-50' 
                        : 'bg-gradient-to-r from-blue-600 to-violet-600 text-white hover:from-blue-700 hover:to-violet-700'
                    }`}
                  >
                    {plan.cta}
                  </Button>
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section id="faq" className="py-24 px-4 sm:px-6 lg:px-8 bg-slate-50 dark:bg-slate-900/50">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">
              Sık Sorulan <span className="gradient-text">Sorular</span>
            </h2>
          </div>

          <div className="space-y-4">
            {[
              {
                q: 'SvontAi nasıl çalışır?',
                a: 'SvontAi, WhatsApp Business API ve gelişmiş yapay zeka modellerini kullanarak müşteri mesajlarınıza otomatik yanıt verir. Bilgi tabanınızı ekleyerek AI\'ı işletmenize özel eğitebilirsiniz.'
              },
              {
                q: 'WhatsApp Business hesabım olması gerekiyor mu?',
                a: 'Evet, WhatsApp entegrasyonu için Meta Business Suite üzerinden WhatsApp Business API erişiminiz olması gerekmektedir. Kurulum sürecinde size yardımcı oluyoruz.'
              },
              {
                q: 'Deneme süresi var mı?',
                a: 'Evet! Tüm planlarımız için 14 günlük ücretsiz deneme süresi sunuyoruz. Kredi kartı bilgisi gerekmez, istediğiniz zaman iptal edebilirsiniz.'
              },
              {
                q: 'Verilerim güvende mi?',
                a: 'Kesinlikle. Tüm verileriniz 256-bit SSL şifreleme ile korunur ve Türkiye\'deki KVKK uyumlu veri merkezlerinde saklanır.'
              },
              {
                q: 'Mevcut sistemlerimle entegre olabilir mi?',
                a: 'Evet, REST API\'miz sayesinde CRM, e-ticaret platformları ve diğer iş uygulamalarınızla kolayca entegre olabilirsiniz.'
              },
            ].map((faq, i) => (
              <div 
                key={i}
                className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 card-hover"
              >
                <h3 className="text-lg font-semibold mb-3 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white text-sm font-bold">
                    {i + 1}
                  </div>
                  {faq.q}
                </h3>
                <p className="text-muted-foreground pl-11">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto">
          <div className="relative p-12 md:p-16 rounded-3xl overflow-hidden">
            {/* Background */}
            <div className="absolute inset-0 bg-gradient-to-br from-blue-600 via-violet-600 to-purple-600" />
            <div className="absolute inset-0 dot-pattern opacity-20" />
            
            {/* Content */}
            <div className="relative text-center text-white">
              <h2 className="text-4xl md:text-5xl font-bold mb-6">
                Müşteri desteğinizi<br />dönüştürmeye hazır mısınız?
              </h2>
              <p className="text-xl text-blue-100 mb-10 max-w-2xl mx-auto">
                14 günlük ücretsiz deneme ile SvontAi'nın gücünü keşfedin.
                Kredi kartı gerekmez.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link href="/register">
                  <Button size="lg" className="w-full sm:w-auto bg-white text-blue-600 hover:bg-blue-50 text-lg px-8 h-14 rounded-2xl font-semibold shadow-xl">
                    Ücretsiz Başla
                    <ArrowRight className="ml-2 w-5 h-5" />
                  </Button>
                </Link>
                <Link href="mailto:sales@svontai.com">
                  <Button size="lg" variant="outline" className="w-full sm:w-auto border-white/30 text-white hover:bg-white/10 text-lg px-8 h-14 rounded-2xl">
                    Satış Ekibiyle Konuş
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-16 px-4 sm:px-6 lg:px-8 border-t border-slate-200 dark:border-slate-800">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-4 gap-12 mb-12">
            <div>
              <Link href="/" className="flex items-center gap-2 mb-4">
                <Logo size="md" showText={true} animated={false} />
              </Link>
              <p className="text-muted-foreground">
                Yapay zeka destekli WhatsApp asistanı ile müşteri hizmetlerinizi otomatikleştirin.
              </p>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Ürün</h4>
              <ul className="space-y-2 text-muted-foreground">
                <li><Link href="#features" className="hover:text-foreground transition-colors">Özellikler</Link></li>
                <li><Link href="#pricing" className="hover:text-foreground transition-colors">Fiyatlar</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">API</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Entegrasyonlar</Link></li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Şirket</h4>
              <ul className="space-y-2 text-muted-foreground">
                <li><Link href="#" className="hover:text-foreground transition-colors">Hakkımızda</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Blog</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Kariyer</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">İletişim</Link></li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Yasal</h4>
              <ul className="space-y-2 text-muted-foreground">
                <li><Link href="#" className="hover:text-foreground transition-colors">Gizlilik Politikası</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">Kullanım Koşulları</Link></li>
                <li><Link href="#" className="hover:text-foreground transition-colors">KVKK</Link></li>
              </ul>
            </div>
          </div>
          
          <div className="pt-8 border-t border-slate-200 dark:border-slate-800 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm text-muted-foreground">
              © 2024 SvontAi. Tüm hakları saklıdır.
            </p>
            <div className="flex items-center gap-4">
              <span className="text-sm text-muted-foreground">Türkiye'de ❤️ ile yapıldı</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
