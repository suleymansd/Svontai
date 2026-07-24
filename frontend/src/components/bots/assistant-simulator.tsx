'use client'

import { FormEvent, useState } from 'react'
import { Bot, Loader2, Play, RotateCcw, Send, ShieldCheck, User } from 'lucide-react'

import { botApi } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'
import { trackProductEvent } from '@/lib/product-analytics'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { useToast } from '@/components/ui/use-toast'

type Turn = {
  role: 'customer' | 'assistant'
  content: string
}

const suggestions = ['Çalışma saatleriniz nedir?', 'Randevu almak istiyorum', 'Hizmetleriniz hakkında bilgi verir misiniz?']

export function AssistantSimulator({ botId }: { botId: string }) {
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [sending, setSending] = useState(false)

  const updateOpen = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (nextOpen) trackProductEvent('assistant_simulator_opened', {}, 'funnel')
  }

  const send = async (event?: FormEvent) => {
    event?.preventDefault()
    const content = message.trim()
    if (!content || sending) return
    const history = turns.slice(-20)
    setTurns((current) => [...current, { role: 'customer', content }])
    setMessage('')
    setSending(true)
    trackProductEvent('assistant_simulator_message', { turn: history.length + 1 }, 'funnel')
    try {
      const response = await botApi.simulate(botId, { message: content, history })
      setTurns((current) => [...current, { role: 'assistant', content: response.data.reply }])
    } catch (error) {
      trackProductEvent('simulator_error', {}, 'error')
      toast({
        title: 'Yanıt üretilemedi',
        description: getApiErrorMessage(error, 'Yapay zeka bağlantısını kontrol edip tekrar deneyin.'),
        variant: 'destructive',
      })
    } finally {
      setSending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={updateOpen}>
      <DialogTrigger asChild>
        <Button data-analytics="assistant_simulator_open">
          <Play className="mr-2 h-4 w-4" />
          Yanıtı Dene
        </Button>
      </DialogTrigger>
      <DialogContent className="flex h-[min(760px,90vh)] max-w-2xl flex-col overflow-hidden p-0">
        <DialogHeader className="border-b px-6 py-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <DialogTitle>Yayın Öncesi Mesaj Simülatörü</DialogTitle>
              <DialogDescription className="mt-1">
                Müşteriniz gibi yazın ve asistanın gerçek işletme bilgileriyle vereceği yanıtı görün.
              </DialogDescription>
            </div>
            <Badge variant="success" className="gap-1">
              <ShieldCheck className="h-3.5 w-3.5" />
              Güvenli önizleme
            </Badge>
          </div>
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col bg-muted/20">
          <div className="border-b bg-background px-5 py-3 text-xs text-muted-foreground">
            Bu ekran WhatsApp mesajı, müşteri veya randevu kaydı oluşturmaz.
          </div>
          <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5" aria-live="polite">
            {turns.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                  <Bot className="h-6 w-6 text-primary" />
                </div>
                <p className="mt-4 font-medium">Bir müşteri sorusuyla başlayın</p>
                <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                  Bilgi, fiyat, randevu ve insan desteğine geçiş senaryolarını deneyebilirsiniz.
                </p>
                <div className="mt-5 flex flex-wrap justify-center gap-2">
                  {suggestions.map((suggestion) => (
                    <Button
                      key={suggestion}
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => setMessage(suggestion)}
                    >
                      {suggestion}
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              turns.map((turn, index) => (
                <div key={`${turn.role}-${index}`} className={`flex gap-3 ${turn.role === 'customer' ? 'justify-start' : 'justify-end'}`}>
                  {turn.role === 'customer' && (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                      <User className="h-4 w-4" />
                    </div>
                  )}
                  <div className={`max-w-[78%] px-4 py-3 text-sm ${turn.role === 'assistant' ? 'rounded-lg bg-primary text-primary-foreground' : 'rounded-lg border bg-background'}`}>
                    {turn.content}
                  </div>
                  {turn.role === 'assistant' && (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
                      <Bot className="h-4 w-4 text-primary" />
                    </div>
                  )}
                </div>
              ))
            )}
            {sending && (
              <div className="flex justify-end gap-3">
                <div className="flex items-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm text-primary-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Yanıt hazırlanıyor
                </div>
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
              </div>
            )}
          </div>

          <form onSubmit={send} className="border-t bg-background p-4">
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="icon"
                variant="ghost"
                title="Konuşmayı temizle"
                aria-label="Konuşmayı temizle"
                onClick={() => setTurns([])}
                disabled={turns.length === 0 || sending}
              >
                <RotateCcw className="h-4 w-4" />
              </Button>
              <Input
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Müşterinin yazacağı mesaj..."
                maxLength={2000}
                disabled={sending}
                autoFocus
              />
              <Button type="submit" size="icon" aria-label="Mesajı dene" disabled={!message.trim() || sending}>
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </Button>
            </div>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  )
}
