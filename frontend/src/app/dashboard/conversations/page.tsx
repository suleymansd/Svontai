'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Bot,
  BotOff,
  MessageSquare,
  Search,
  Send,
  Clock,
  User,
  Phone,
  Globe,
  Inbox,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/components/ui/use-toast'
import { conversationApi } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'
import { formatDate, cn } from '@/lib/utils'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { KPIStat } from '@/components/shared/kpi-stat'
import { EmptyState } from '@/components/shared/empty-state'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { useRealtimeEvents } from '@/lib/use-realtime-events'

export default function ConversationsPage() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const { connected: realtimeConnected } = useRealtimeEvents((event) => {
    if (!event.type.startsWith('message.') && !event.type.startsWith('conversation.')) return
    queryClient.invalidateQueries({ queryKey: ['conversations'] })
    if (selectedConversation && event.conversation_id === selectedConversation) {
      queryClient.invalidateQueries({ queryKey: ['conversation', selectedConversation] })
    }
  })

  const { data: conversations, isLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => conversationApi.list({ limit: 100 }).then((res) => res.data),
  })

  const { data: selectedConvData } = useQuery({
    queryKey: ['conversation', selectedConversation],
    queryFn: () => (selectedConversation ? conversationApi.get(selectedConversation).then((res) => res.data) : null),
    enabled: !!selectedConversation,
  })

  const aiReplyMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      conversationApi.updateAIReplyPolicy(id, enabled),
    onSuccess: (response) => {
      queryClient.setQueryData(['conversation', response.data.id], response.data)
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      toast({
        title: response.data.ai_reply_enabled ? 'AI yanıtları açıldı' : 'Kişi AI yanıtlarından hariç tutuldu',
        description: response.data.ai_reply_enabled
          ? 'Yeni mesajlar otomatik olarak yanıtlanacak.'
          : 'Mesajları görünmeye devam edecek, ancak otomatik yanıt gönderilmeyecek.',
      })
    },
    onError: (error) => toast({
      title: 'AI yanıt ayarı değiştirilemedi',
      description: getApiErrorMessage(error, 'Lütfen tekrar deneyin.'),
      variant: 'destructive',
    }),
  })

  const filteredConversations = conversations?.filter((conv: any) => {
    if (!searchTerm) return true
    const search = searchTerm.toLowerCase()
    return conv.customer_name?.toLowerCase().includes(search) || conv.customer_phone?.includes(search)
  })

  const activeCount = conversations?.filter((c: any) => c.status !== 'closed').length || 0
  const totalCount = conversations?.length || 0
  const aiExcludedCount = conversations?.filter((c: any) => c.ai_reply_enabled === false).length || 0
  const today = new Date().toDateString()
  const todayCount = conversations?.filter(
    (c: any) => new Date(c.created_at).toDateString() === today
  ).length || 0

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Konuşmalar"
          description="Müşteri konuşmalarını görüntüleyin ve yönetin."
          icon={<Icon3DBadge icon={MessageSquare} from="from-primary" to="to-violet-500" />}
          actions={(
            <Badge variant={realtimeConnected ? 'success' : 'secondary'}>
              {realtimeConnected ? 'Canlı' : 'Bağlanıyor'}
            </Badge>
          )}
        />

        <div className="grid gap-4 sm:grid-cols-4">
          <KPIStat label="Toplam" value={totalCount} icon={<MessageSquare className="h-5 w-5" />} />
          <KPIStat label="Aktif" value={activeCount} icon={<Clock className="h-5 w-5" />} />
          <KPIStat label="AI Hariç" value={aiExcludedCount} icon={<BotOff className="h-5 w-5" />} />
          <KPIStat label="Bugün" value={todayCount} icon={<MessageSquare className="h-5 w-5" />} />
        </div>

        <div className="grid min-h-[500px] gap-6 lg:h-[calc(100vh-320px)] lg:grid-cols-3">
          <Card className="lg:col-span-1 flex flex-col border border-border/70 shadow-soft">
            <div className="p-4 border-b border-border/70">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Konuşma ara..."
                  className="pl-9"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto">
              {isLoading ? (
                <div className="p-4 space-y-4">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <Skeleton className="w-12 h-12 rounded-full" />
                      <div className="space-y-2 flex-1">
                        <Skeleton className="h-4 w-24" />
                        <Skeleton className="h-3 w-full" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : !filteredConversations || filteredConversations.length === 0 ? (
                <div className="p-6">
                  <EmptyState
                    icon={<Inbox className="h-6 w-6 text-primary" />}
                    title={searchTerm ? 'Sonuç bulunamadı' : 'Henüz konuşma yok'}
                    description={searchTerm ? 'Farklı bir arama deneyin.' : 'Yeni mesajlar burada görünecek.'}
                  />
                </div>
              ) : (
                <div className="divide-y divide-border/70">
                  {filteredConversations.map((conv: any) => (
                    <button
                      key={conv.id}
                      className={cn(
                        'w-full text-left p-4 transition-all duration-200',
                        selectedConversation === conv.id ? 'conv-active' : 'conv-hover'
                      )}
                      onClick={() => setSelectedConversation(conv.id)}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-medium">
                            {conv.customer_name || conv.customer_phone || 'Bilinmeyen'}
                          </h4>
                          <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
                            {conv.last_message || 'Mesaj yok'}
                          </p>
                        </div>
                        <div className="flex flex-col items-end gap-2">
                          {conv.ai_reply_enabled === false ? (
                            <Badge variant="secondary" className="gap-1">
                              <BotOff className="h-3 w-3" /> AI kapalı
                            </Badge>
                          ) : (
                            <Badge variant={conv.status !== 'closed' ? 'success' : 'secondary'}>
                              {conv.status !== 'closed' ? 'Aktif' : 'Kapalı'}
                            </Badge>
                          )}
                          <span className="text-xs text-muted-foreground">
                            {formatDate(conv.last_message_at || conv.created_at)}
                          </span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <Card className="lg:col-span-2 flex flex-col border border-border/70 shadow-soft">
            {isLoading ? (
              <div className="p-6 space-y-4">
                <Skeleton className="h-8 w-1/3" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            ) : !selectedConvData ? (
              <div className="p-6">
                <EmptyState
                  icon={<MessageSquare className="h-7 w-7 text-primary" />}
                  title="Konuşma seçin"
                  description="Detayları görüntülemek için listeden bir konuşma seçin."
                />
              </div>
            ) : (
              <div className="flex flex-col h-full">
                <div className="p-4 border-b border-border/70">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                    <div className="flex min-w-0 flex-1 items-center gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary/20 to-violet-500/20 text-primary ring-2 ring-primary/10">
                        <User className="w-5 h-5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="truncate font-semibold">
                          {selectedConvData.customer_name || selectedConvData.customer_phone || 'Bilinmeyen'}
                        </h3>
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                          {selectedConvData.customer_phone && (
                            <span className="flex items-center gap-1 whitespace-nowrap">
                              <Phone className="w-3 h-3" />
                              {selectedConvData.customer_phone}
                            </span>
                          )}
                          {selectedConvData.source && (
                            <span className="flex items-center gap-1 whitespace-nowrap">
                              <Globe className="w-3 h-3" />
                              {selectedConvData.source}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex w-full items-center gap-3 rounded-md border border-border/70 px-3 py-2 sm:w-auto sm:shrink-0">
                      {selectedConvData.ai_reply_enabled === false ? (
                        <BotOff className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <Bot className="h-4 w-4 text-primary" />
                      )}
                      <div className="min-w-0">
                        <p className="text-xs font-medium">AI otomatik yanıt</p>
                        <p className="text-[11px] text-muted-foreground">
                          {selectedConvData.ai_reply_enabled === false ? 'Bu kişi hariç tutuldu' : 'Bu kişi için aktif'}
                        </p>
                      </div>
                      <Switch
                        className="ml-auto data-[state=unchecked]:bg-slate-300 sm:ml-0"
                        checked={selectedConvData.ai_reply_enabled !== false}
                        disabled={aiReplyMutation.isPending}
                        onCheckedChange={(enabled) => aiReplyMutation.mutate({
                          id: selectedConvData.id,
                          enabled,
                        })}
                        aria-label="Bu kişi için AI otomatik yanıt"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                  {(selectedConvData.messages || []).map((msg: any) => (
                    <div
                      key={msg.id}
                      className={cn(
                        'flex gap-3',
                        msg.sender === 'bot' ? 'justify-end' : 'justify-start'
                      )}
                    >
                      <div
                        className={cn(
                          'max-w-[70%] rounded-2xl px-4 py-3 text-sm',
                          msg.sender === 'bot'
                            ? 'bubble-bot text-primary-foreground'
                            : 'bg-muted'
                        )}
                      >
                        {msg.content}
                        <div className="mt-2 text-[10px] opacity-70">
                          {formatDate(msg.created_at)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="border-t border-border/70 p-4">
                  <div className="flex items-center gap-2 input-glow rounded-lg transition-all duration-300">
                    <Input
                      placeholder="Mesaj yazın..."
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                    />
                    <Button size="icon">
                      <Send className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </ContentContainer>
  )
}
