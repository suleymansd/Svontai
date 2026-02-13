'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Send, User, ShieldCheck } from 'lucide-react'
import { ticketsApi } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { SectionCard } from '@/components/shared/section-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Skeleton } from '@/components/ui/skeleton'
import { MetaRow } from '@/components/shared/meta-row'

interface TicketMessage {
  id: string
  body: string
  sender_type: string
  created_at: string
}

interface TicketDetail {
  id: string
  subject: string
  status: string
  priority: string
  tenant_id: string
  created_at: string
  last_activity_at: string
  messages: TicketMessage[]
}

export default function TicketDetailPage() {
  const params = useParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const ticketId = params.ticketId as string

  const { data: ticket, isLoading } = useQuery<TicketDetail>({
    queryKey: ['ticket', ticketId],
    queryFn: () => ticketsApi.get(ticketId).then(res => res.data),
    enabled: Boolean(ticketId),
  })

  const [reply, setReply] = useState('')

  const replyMutation = useMutation({
    mutationFn: () => ticketsApi.addMessage(ticketId, { body: reply }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ticket', ticketId] })
      queryClient.invalidateQueries({ queryKey: ['tickets'] })
      setReply('')
      toast({ title: 'Yanıt gönderildi' })
    },
    onError: (error: any) => {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Yanıt gönderilemedi',
        variant: 'destructive',
      })
    },
  })

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title={ticket?.subject || 'Ticket Detayı'}
          description="Destek ekibiyle olan görüşmenizi yönetin."
          actions={(
            <Button variant="outline" onClick={() => router.push('/dashboard/tickets')}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Listeye Dön
            </Button>
          )}
        />

        {isLoading && (
          <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
            <SectionCard title="Görüşme" description="Yükleniyor...">
              <Skeleton className="h-20 w-full" />
            </SectionCard>
            <SectionCard title="Detaylar">
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
            </SectionCard>
          </div>
        )}

        {!isLoading && ticket && (
          <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
            <SectionCard title="Görüşme" description="Ticket mesajları">
              <div className="space-y-4">
                {ticket.messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex flex-col gap-2 rounded-2xl border px-4 py-3 ${
                      message.sender_type === 'staff'
                        ? 'border-primary/30 bg-primary/5'
                        : 'border-border/70 bg-muted/30'
                    }`}
                  >
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      {message.sender_type === 'staff' ? (
                        <ShieldCheck className="h-4 w-4 text-primary" />
                      ) : (
                        <User className="h-4 w-4" />
                      )}
                      <span>{message.sender_type === 'staff' ? 'Destek' : 'Siz'}</span>
                      <span>•</span>
                      <span>{new Date(message.created_at).toLocaleString('tr-TR')}</span>
                    </div>
                    <p className="text-sm">{message.body}</p>
                  </div>
                ))}
              </div>
              <div className="mt-6 space-y-3">
                <Textarea
                  rows={4}
                  placeholder="Yanıtınızı yazın..."
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                />
                <Button onClick={() => replyMutation.mutate()} disabled={replyMutation.isPending || reply.length === 0}>
                  <Send className="h-4 w-4 mr-2" />
                  Yanıt Gönder
                </Button>
              </div>
            </SectionCard>

            <SectionCard title="Detaylar" description="Ticket bilgileri">
              <div className="space-y-3">
                <MetaRow label="Ticket" value={`#${ticket.id.slice(0, 8)}`} />
                <MetaRow label="Durum" value={(
                  <Badge variant={ticket.status === 'solved' ? 'success' : ticket.status === 'pending' ? 'warning' : 'secondary'}>
                    {ticket.status}
                  </Badge>
                )} />
                <MetaRow label="Öncelik" value={<Badge variant="outline">{ticket.priority}</Badge>} />
                <MetaRow label="Oluşturma" value={new Date(ticket.created_at).toLocaleString('tr-TR')} />
                <MetaRow label="Son aktivite" value={new Date(ticket.last_activity_at).toLocaleString('tr-TR')} />
              </div>
            </SectionCard>
          </div>
        )}
      </div>
    </ContentContainer>
  )
}
