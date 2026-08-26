'use client'

import { FormEvent, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Bot, Check, Loader2, MessageSquarePlus, Send, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { useToast } from '@/components/ui/use-toast'
import { botApi, type AssistantTrainerProposal } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'

type Turn = {
  id: string
  role: 'user' | 'assistant'
  content: string
}

const suggestions = [
  'Kargo durumu sorulunca sipariş numarasını istesin.',
  'Fiyat soran müşteriye hizmet paketlerimizi anlatsın.',
  'İade koşullarını soran müşterilere özel bir uzman oluştur.',
]

export function ConversationalBotTrainer({ onApplied }: { onApplied: () => void }) {
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [status, setStatus] = useState<'collecting' | 'ready' | 'applied'>('collecting')
  const [proposal, setProposal] = useState<AssistantTrainerProposal | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])

  const messageMutation = useMutation({
    mutationFn: (content: string) => botApi.trainerMessage({ message: content, session_id: sessionId }),
    onSuccess: ({ data }) => {
      setSessionId(data.session_id)
      setStatus(data.status)
      setProposal(data.proposal || null)
      setTurns((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'assistant', content: data.assistant_message },
      ])
    },
    onError: (error) => toast({
      title: 'Eğitim mesajı işlenemedi',
      description: getApiErrorMessage(error, 'Lütfen kısa bir süre sonra tekrar deneyin.'),
      variant: 'destructive',
    }),
  })

  const applyMutation = useMutation({
    mutationFn: () => {
      if (!sessionId) throw new Error('Eğitim oturumu bulunamadı')
      return botApi.applyTrainerDraft(sessionId)
    },
    onSuccess: ({ data }) => {
      setStatus('applied')
      setTurns((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'assistant', content: data.assistant_message },
      ])
      onApplied()
      toast({
        title: 'Uzman bot etkinleştirildi',
        description: `${data.bot.name}, Ana Asistan ile birlikte çalışmaya başladı.`,
      })
    },
    onError: (error) => toast({
      title: 'Uzman etkinleştirilemedi',
      description: getApiErrorMessage(error, 'Taslağı kontrol edip tekrar deneyin.'),
      variant: 'destructive',
    }),
  })

  const sendMessage = (content: string) => {
    const normalized = content.trim()
    if (normalized.length < 3 || messageMutation.isPending || status === 'applied') return
    setTurns((current) => [
      ...current,
      { id: crypto.randomUUID(), role: 'user', content: normalized },
    ])
    setMessage('')
    messageMutation.mutate(normalized)
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    sendMessage(message)
  }

  const startNew = () => {
    setMessage('')
    setSessionId(null)
    setStatus('collecting')
    setProposal(null)
    setTurns([])
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <MessageSquarePlus className="mr-2 h-4 w-4" />
          Sohbetle Uzman Oluştur
        </Button>
      </DialogTrigger>
      <DialogContent className="flex max-h-[90vh] flex-col p-0 sm:max-w-3xl">
        <DialogHeader className="border-b px-6 py-5 text-left">
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            AI Eğitim Asistanı
          </DialogTitle>
          <DialogDescription>
            İstediğiniz özel davranışı anlatın. SvontAI taslağı hazırlar; siz onaylamadan yayına almaz.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-72 flex-1 space-y-4 overflow-y-auto px-6 py-5">
          {turns.length === 0 && (
            <div className="space-y-5">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Bot className="h-5 w-5 text-primary" />
                </div>
                <p className="max-w-xl text-sm leading-6 text-muted-foreground">
                  Müşterinin ne soracağını ve asistanın nasıl davranmasını istediğinizi yazın. Eksik bir ayrıntı varsa size yalnızca gerekli soruyu soracağım.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    className="rounded-md border bg-background px-3 py-2 text-left text-xs text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
                    onClick={() => sendMessage(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn) => (
            <div key={turn.id} className={`flex ${turn.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={turn.role === 'user'
                  ? 'max-w-[85%] rounded-lg bg-primary px-4 py-3 text-sm text-primary-foreground'
                  : 'max-w-[85%] rounded-lg bg-muted px-4 py-3 text-sm leading-6'}
              >
                {turn.content}
              </div>
            </div>
          ))}

          {messageMutation.isPending && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Taslak hazırlanıyor...
            </div>
          )}

          {proposal && (
            <section className="space-y-4 border-y py-4" aria-label="Uzman bot taslağı">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-medium uppercase text-muted-foreground">Hazır taslak</p>
                  <h3 className="mt-1 font-semibold">{proposal.name}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{proposal.description}</p>
                </div>
                {status === 'applied' && <Check className="h-5 w-5 shrink-0 text-emerald-600" />}
              </div>
              <div className="grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <p className="font-medium">Örnek müşteri soruları</p>
                  <ul className="mt-2 space-y-1 text-muted-foreground">
                    {proposal.example_questions.map((question) => <li key={question}>• {question}</li>)}
                  </ul>
                </div>
                <div>
                  <p className="font-medium">Doğrulanmış yanıt</p>
                  <p className="mt-2 text-muted-foreground">{proposal.answer}</p>
                </div>
              </div>
              {status === 'ready' && (
                <Button onClick={() => applyMutation.mutate()} disabled={applyMutation.isPending}>
                  {applyMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
                  Oluştur ve Etkinleştir
                </Button>
              )}
            </section>
          )}
        </div>

        <div className="border-t px-6 py-4">
          {status === 'applied' ? (
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-emerald-700">Uzman Ana Asistanınıza bağlandı.</p>
              <Button variant="outline" onClick={startNew}>Yeni Uzman Oluştur</Button>
            </div>
          ) : (
            <form className="flex items-end gap-2" onSubmit={handleSubmit}>
              <Textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Örn: Kargo nerede diye sorulursa sipariş numarasını istesin..."
                className="min-h-11 resize-none"
                maxLength={3000}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    sendMessage(message)
                  }
                }}
              />
              <Button
                type="submit"
                size="icon"
                className="h-11 w-11 shrink-0"
                disabled={message.trim().length < 3 || messageMutation.isPending}
                aria-label="Eğitim mesajını gönder"
                title="Gönder"
              >
                {messageMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </Button>
            </form>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
