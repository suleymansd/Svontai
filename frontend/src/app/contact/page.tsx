'use client'

import { useState } from 'react'
import { Mail, ShieldCheck } from 'lucide-react'
import { MarketingShell } from '@/components/marketing/marketing-shell'
import { Reveal } from '@/components/marketing/reveal'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'

export default function ContactPage() {
  const [form, setForm] = useState({
    name: '',
    email: '',
    company: '',
    message: '',
  })

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    const subject = encodeURIComponent('SmartWA Demo ve Concierge Kurulum Talebi')
    const body = encodeURIComponent(
      `Ad Soyad: ${form.name}\nE-posta: ${form.email}\nŞirket: ${form.company}\n\nMesaj:\n${form.message}`
    )
    window.location.href = `mailto:sales@svontai.com?subject=${subject}&body=${body}`
  }

  return (
    <MarketingShell>
      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:px-8">
        <Reveal className="space-y-5 text-center">
          <Badge variant="outline">İletişim</Badge>
          <h1 className="text-4xl font-semibold">SmartWA demo ve kurulum görüşmesi</h1>
          <p className="text-muted-foreground">İşletmenizin WhatsApp, bot, arama ve concierge kurulum ihtiyacını birlikte netleştirelim.</p>
        </Reveal>

        <div className="mt-12 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <Card className="border-border/60">
            <CardContent className="p-6">
              <form className="space-y-4" onSubmit={handleSubmit}>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Ad Soyad</Label>
                    <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
                  </div>
                  <div className="space-y-2">
                    <Label>Şirket</Label>
                    <Input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} required />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>E-posta</Label>
                  <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
                </div>
                <div className="space-y-2">
                  <Label>Mesajınız</Label>
                  <Textarea rows={6} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} placeholder="Sektör, WhatsApp numarası durumu, günlük mesaj yoğunluğu ve beklediğiniz otomasyon akışını yazabilirsiniz." required />
                </div>
                <Button type="submit" className="w-full">Görüşme Talebi Gönder</Button>
              </form>
            </CardContent>
          </Card>

          <div className="space-y-4">
            <Card className="border-border/60">
              <CardContent className="p-6">
                <div className="flex items-center gap-3">
                  <Mail className="h-5 w-5 text-primary" />
                  <div>
                    <p className="text-sm text-muted-foreground">Satış ve kurulum</p>
                    <p className="font-medium">sales@svontai.com</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="p-6">
                <div className="flex items-start gap-3">
                  <ShieldCheck className="mt-0.5 h-5 w-5 text-primary" />
                  <div>
                    <p className="font-medium">Görüşmede netleştirdiklerimiz</p>
                    <p className="mt-1 text-sm text-muted-foreground">WhatsApp bağlantısı, bilgi formasyonu, bot tonu, arama otomasyonu, ödeme/plan ve canlıya alma adımları.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="p-6 text-sm text-muted-foreground">
                Talebinizi aldıktan sonra işletme bilgilerinize göre self-serve veya concierge kurulum akışını öneririz.
              </CardContent>
            </Card>
          </div>
        </div>
      </section>
    </MarketingShell>
  )
}
