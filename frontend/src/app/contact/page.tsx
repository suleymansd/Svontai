'use client'

import { useEffect, useState } from 'react'
import { Loader2, Mail, ShieldCheck } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { MarketingShell } from '@/components/marketing/marketing-shell'
import { Reveal } from '@/components/marketing/reveal'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { contactApi } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { getApiErrorMessage } from '@/lib/api-error'

export default function ContactPage() {
  const { toast } = useToast()
  const [form, setForm] = useState({
    name: '',
    email: '',
    company: '',
    phone: '',
    message: '',
    website: '',
  })
  const [requestedPlan, setRequestedPlan] = useState('')
  const [requestedInterval, setRequestedInterval] = useState('')

  useEffect(() => {
    const params = new URL(window.location.href).searchParams
    const plan = params.get('plan')
    const interval = params.get('interval')
    if (!plan) return
    setRequestedPlan(plan)
    setRequestedInterval(interval || '')
    setForm((current) => ({
      ...current,
      message: current.message || `${plan.toUpperCase()} planı${interval ? ` (${interval})` : ''} için görüşmek istiyorum.`,
    }))
  }, [])

  const inquiryMutation = useMutation({
    mutationFn: () => contactApi.createInquiry({
      ...form,
      plan: requestedPlan || undefined,
      interval: requestedInterval || undefined,
    }),
    onSuccess: (response) => {
      toast({
        title: 'Talebiniz alındı',
        description: response.data?.message || 'Ekibimiz sizinle iletişime geçecek.',
      })
      setForm({ name: '', email: '', company: '', phone: '', message: '', website: '' })
    },
    onError: (error) => {
      toast({
        title: 'Talep gönderilemedi',
        description: getApiErrorMessage(error, 'Lütfen bilgileri kontrol edip tekrar deneyin.'),
        variant: 'destructive',
      })
    },
  })

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    inquiryMutation.mutate()
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
                    <Label htmlFor="contact-name">Ad Soyad</Label>
                    <Input id="contact-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="contact-company">İşletme / Marka</Label>
                    <Input id="contact-company" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="contact-email">E-posta</Label>
                  <Input id="contact-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="contact-phone">Telefon</Label>
                  <Input id="contact-phone" type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="contact-message">Mesajınız</Label>
                  <Textarea id="contact-message" rows={6} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} placeholder="Sektör, WhatsApp numarası durumu, günlük mesaj yoğunluğu ve beklediğiniz otomasyon akışını yazabilirsiniz." required />
                </div>
                <div className="hidden" aria-hidden="true">
                  <Label htmlFor="website">Website</Label>
                  <Input id="website" tabIndex={-1} autoComplete="off" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} />
                </div>
                <Button type="submit" className="w-full" disabled={inquiryMutation.isPending}>
                  {inquiryMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Görüşme Talebi Gönder
                </Button>
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
                    <p className="mt-1 text-sm text-muted-foreground">WhatsApp bağlantısı, bilgi formasyonu, bot tonu, arama otomasyonu, plan ve canlıya alma adımları.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="p-6 text-sm text-muted-foreground">
                Talebinizi aldıktan sonra sizinle doğrudan iletişime geçer, uygun planı hesabınıza manuel olarak tanımlarız.
              </CardContent>
            </Card>
          </div>
        </div>
      </section>
    </MarketingShell>
  )
}
