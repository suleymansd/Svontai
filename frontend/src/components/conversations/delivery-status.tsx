'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, X } from 'lucide-react'
import { operatorApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { useToast } from '@/components/ui/use-toast'

type Delivery = { message_id: string; kind: 'operator' | 'ai'; content: string; delivery_status: string; note: string }

export function DeliveryStatus({ conversationId }: { conversationId: string }) {
  const client = useQueryClient()
  const { toast } = useToast()
  const deliveries = useQuery({
    queryKey: ['deliveries', conversationId],
    queryFn: () => operatorApi.deliveries(conversationId).then((res) => res.data as Delivery[]),
    refetchInterval: (query) => query.state.data?.some((item) => ['queued', 'dispatching'].includes(item.delivery_status)) ? 10_000 : 60_000,
  })
  const resolve = useMutation({
    mutationFn: ({ id, outcome, kind }: { id: string; outcome: 'sent' | 'not_sent'; kind: 'operator' | 'ai' }) => operatorApi.resolveDelivery(id, outcome, kind),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['deliveries', conversationId] })
      void client.invalidateQueries({ queryKey: ['conversation', conversationId] })
      void client.invalidateQueries({ queryKey: ['conversations'] })
    },
    onError: () => toast({ title: 'Durum kaydedilemedi', description: 'Gönderim durumu değişmiş olabilir. Listeyi yenileyin.', variant: 'destructive' }),
  })
  if (!deliveries.data?.length) return null
  return <section aria-label="Gönderim durumu" className="border-t border-border/70 px-4 py-3 space-y-3 text-sm">
    {deliveries.data.slice(0, 5).map((item) => <div key={item.message_id} className="space-y-1">
      <p className="line-clamp-2 break-words font-medium">{item.content}</p>
      <p className="text-xs text-muted-foreground">{item.note}</p>
      {item.delivery_status === 'uncertain' && <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" disabled={resolve.isPending} onClick={() => {
          if (window.confirm('WhatsApp konuşmasını kontrol ettiniz ve mesajın iletildiğini doğruladınız mı?')) resolve.mutate({ id: item.message_id, outcome: 'sent', kind: item.kind })
        }}><Check className="mr-1 h-4 w-4" />İletildi</Button>
        <Button size="sm" variant="outline" disabled={resolve.isPending} onClick={() => {
          if (window.confirm('WhatsApp konuşmasını kontrol ettiniz ve mesajın iletilmediğini doğruladınız mı? Bu işlem mesajı tekrar göndermez; AI yanıtıysa konuşma manuel yönetime alınır.')) resolve.mutate({ id: item.message_id, outcome: 'not_sent', kind: item.kind })
        }}><X className="mr-1 h-4 w-4" />İletilmedi</Button>
      </div>}
    </div>)}
  </section>
}
