'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  MessageSquare, 
  User,
  Bot,
  Clock,
  ArrowRight,
  Send,
  RefreshCw,
  Loader2,
  Phone,
  Globe,
  Lock,
  Unlock,
  AlertCircle
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { operatorApi, subscriptionApi } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'
import Link from 'next/link'

interface ConversationWithStatus {
  id: string
  external_user_id: string
  source: string
  status: string
  is_ai_paused: boolean
  has_lead: boolean
  lead_score: number
  summary: string | null
  tags: string[]
  created_at: string
  updated_at: string
  last_message: string | null
  message_count: number
}

interface Message {
  id: string
  sender: string
  content: string
  created_at: string
}

const statusLabels: Record<string, string> = {
  ai_active: 'AI Aktif',
  human_takeover: 'Operatör',
  closed: 'Kapalı',
  waiting: 'Bekliyor',
}

const statusColors: Record<string, string> = {
  ai_active: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  human_takeover: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  closed: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-400',
  waiting: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
}

export default function OperatorPage() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null)
  const [newMessage, setNewMessage] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)

  // Check feature access
  const { data: usageStats, isLoading: usageLoading } = useQuery({
    queryKey: ['usage-stats'],
    queryFn: () => subscriptionApi.getUsageStats().then(res => res.data),
  })

  const hasFeature = usageStats?.features?.operator_takeover !== false

  // Fetch conversations
  const { data: conversations, isLoading: conversationsLoading, refetch } = useQuery<ConversationWithStatus[]>({
    queryKey: ['operator-conversations', statusFilter],
    queryFn: () => operatorApi.listConversations(statusFilter).then(res => res.data),
    enabled: hasFeature,
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  // Fetch messages for selected conversation
  const { data: messages, isLoading: messagesLoading } = useQuery<Message[]>({
    queryKey: ['operator-messages', selectedConversation],
    queryFn: () => selectedConversation 
      ? operatorApi.getConversationMessages(selectedConversation).then(res => res.data)
      : Promise.resolve([]),
    enabled: !!selectedConversation && hasFeature,
    refetchInterval: 5000,
  })

  // Takeover mutation
  const takeoverMutation = useMutation({
    mutationFn: (conversationId: string) => operatorApi.takeoverConversation(conversationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['operator-conversations'] })
      toast({ title: 'Başarılı', description: 'Konuşma devralındı' })
    },
    onError: (error: any) => {
      toast({ 
        title: 'Hata', 
        description: error.response?.data?.detail || 'Bir hata oluştu',
        variant: 'destructive'
      })
    },
  })

  // Release mutation
  const releaseMutation = useMutation({
    mutationFn: (conversationId: string) => operatorApi.releaseConversation(conversationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['operator-conversations'] })
      toast({ title: 'Başarılı', description: 'Konuşma AI\'ya devredildi' })
    },
    onError: (error: any) => {
      toast({ 
        title: 'Hata', 
        description: error.response?.data?.detail || 'Bir hata oluştu',
        variant: 'destructive'
      })
    },
  })

  // Send message mutation
  const sendMutation = useMutation({
    mutationFn: ({ conversationId, content }: { conversationId: string, content: string }) => 
      operatorApi.sendMessage(conversationId, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['operator-messages', selectedConversation] })
      setNewMessage('')
      toast({ title: 'Mesaj gönderildi' })
    },
    onError: (error: any) => {
      toast({ 
        title: 'Hata', 
        description: error.response?.data?.detail || 'Mesaj gönderilemedi',
        variant: 'destructive'
      })
    },
  })

  const selectedConv = conversations?.find(c => c.id === selectedConversation)

  if (usageLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (!hasFeature) {
    return (
      <div className="max-w-2xl mx-auto">
        <Card className="border-amber-200 dark:border-amber-800">
          <CardContent className="p-12 text-center">
            <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
              <Lock className="w-10 h-10 text-amber-600" />
            </div>
            <h2 className="text-2xl font-bold mb-2">Operatör Devralma Özelliği</h2>
            <p className="text-muted-foreground mb-6">
              Konuşmalara manuel müdahale ve canlı destek için planınızı yükseltin.
            </p>
            <Link href="/dashboard/billing">
              <Button className="bg-gradient-to-r from-amber-600 to-orange-600">
                Planları Görüntüle
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Operatör Paneli 🎧</h1>
          <p className="text-muted-foreground mt-1">
            Konuşmalara manuel müdahale edin
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Yenile
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <Button 
          variant={!statusFilter ? 'default' : 'outline'} 
          size="sm"
          onClick={() => setStatusFilter(undefined)}
        >
          Tümü
        </Button>
        <Button 
          variant={statusFilter === 'human_takeover' ? 'default' : 'outline'} 
          size="sm"
          onClick={() => setStatusFilter('human_takeover')}
        >
          Devralınmış
        </Button>
        <Button 
          variant={statusFilter === 'ai_active' ? 'default' : 'outline'} 
          size="sm"
          onClick={() => setStatusFilter('ai_active')}
        >
          AI Aktif
        </Button>
      </div>

      {/* Main Layout */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Conversations List */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-lg">Konuşmalar</CardTitle>
            <CardDescription>{conversations?.length || 0} aktif konuşma</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {conversationsLoading ? (
              <div className="p-4 space-y-3">
                {[...Array(5)].map((_, i) => (
                  <Skeleton key={i} className="h-20 w-full" />
                ))}
              </div>
            ) : conversations?.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                <MessageSquare className="w-10 h-10 mx-auto mb-3 opacity-50" />
                <p>Henüz konuşma yok</p>
              </div>
            ) : (
              <div className="divide-y dark:divide-slate-800 max-h-[600px] overflow-y-auto">
                {conversations?.map(conv => (
                  <div
                    key={conv.id}
                    onClick={() => setSelectedConversation(conv.id)}
                    className={cn(
                      'p-4 cursor-pointer transition-colors',
                      selectedConversation === conv.id 
                        ? 'bg-blue-50 dark:bg-blue-900/20' 
                        : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'
                    )}
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        {conv.source === 'whatsapp' ? (
                          <Phone className="w-4 h-4 text-green-600" />
                        ) : (
                          <Globe className="w-4 h-4 text-blue-600" />
                        )}
                        <span className="font-medium text-sm truncate max-w-[120px]">
                          {conv.external_user_id}
                        </span>
                      </div>
                      <Badge className={cn('text-xs', statusColors[conv.status])}>
                        {statusLabels[conv.status]}
                      </Badge>
                    </div>
                    {conv.last_message && (
                      <p className="text-sm text-muted-foreground line-clamp-2">
                        {conv.last_message}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                      <span>{conv.message_count} mesaj</span>
                      {conv.has_lead && (
                        <Badge variant="success" className="text-xs">Lead</Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Chat View */}
        <Card className="lg:col-span-2">
          {selectedConversation && selectedConv ? (
            <>
              <CardHeader className="border-b dark:border-slate-800">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      {selectedConv.source === 'whatsapp' ? (
                        <Phone className="w-5 h-5 text-green-600" />
                      ) : (
                        <Globe className="w-5 h-5 text-blue-600" />
                      )}
                      {selectedConv.external_user_id}
                    </CardTitle>
                    <CardDescription>
                      {selectedConv.message_count} mesaj • {selectedConv.source === 'whatsapp' ? 'WhatsApp' : 'Widget'}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedConv.is_ai_paused ? (
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => releaseMutation.mutate(selectedConversation)}
                        disabled={releaseMutation.isPending}
                      >
                        <Unlock className="w-4 h-4 mr-2" />
                        AI'ya Devret
                      </Button>
                    ) : (
                      <Button 
                        size="sm"
                        onClick={() => takeoverMutation.mutate(selectedConversation)}
                        disabled={takeoverMutation.isPending}
                      >
                        <Lock className="w-4 h-4 mr-2" />
                        Devral
                      </Button>
                    )}
                  </div>
                </div>
              </CardHeader>
              
              <CardContent className="p-0">
                {/* Messages */}
                <div className="h-[400px] overflow-y-auto p-4 space-y-4">
                  {messagesLoading ? (
                    <div className="space-y-4">
                      {[...Array(5)].map((_, i) => (
                        <Skeleton key={i} className="h-16 w-3/4" />
                      ))}
                    </div>
                  ) : messages?.length === 0 ? (
                    <div className="flex items-center justify-center h-full text-muted-foreground">
                      <p>Henüz mesaj yok</p>
                    </div>
                  ) : (
                    messages?.map(msg => (
                      <div
                        key={msg.id}
                        className={cn(
                          'flex',
                          msg.sender === 'user' ? 'justify-start' : 'justify-end'
                        )}
                      >
                        <div className={cn(
                          'max-w-[70%] rounded-2xl px-4 py-2',
                          msg.sender === 'user' 
                            ? 'bg-slate-100 dark:bg-slate-800' 
                            : msg.sender === 'operator'
                              ? 'bg-blue-500 text-white'
                              : 'bg-green-500 text-white'
                        )}>
                          <p className="text-sm">{msg.content}</p>
                          <div className={cn(
                            'flex items-center gap-1 mt-1 text-xs',
                            msg.sender === 'user' ? 'text-muted-foreground' : 'text-white/70'
                          )}>
                            {msg.sender === 'bot' && <Bot className="w-3 h-3" />}
                            {msg.sender === 'operator' && <User className="w-3 h-3" />}
                            <span>
                              {new Date(msg.created_at).toLocaleTimeString('tr-TR', { 
                                hour: '2-digit', 
                                minute: '2-digit' 
                              })}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* Input */}
                {selectedConv.is_ai_paused && (
                  <div className="p-4 border-t dark:border-slate-800">
                    <form 
                      onSubmit={(e) => {
                        e.preventDefault()
                        if (newMessage.trim() && selectedConversation) {
                          sendMutation.mutate({ 
                            conversationId: selectedConversation, 
                            content: newMessage 
                          })
                        }
                      }}
                      className="flex gap-2"
                    >
                      <Input
                        value={newMessage}
                        onChange={(e) => setNewMessage(e.target.value)}
                        placeholder="Mesajınızı yazın..."
                        className="flex-1"
                      />
                      <Button type="submit" disabled={!newMessage.trim() || sendMutation.isPending}>
                        {sendMutation.isPending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Send className="w-4 h-4" />
                        )}
                      </Button>
                    </form>
                    <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" />
                      WhatsApp mesajları için gerçek gönderim entegrasyonu gerekli
                    </p>
                  </div>
                )}
              </CardContent>
            </>
          ) : (
            <CardContent className="flex items-center justify-center h-[500px] text-muted-foreground">
              <div className="text-center">
                <MessageSquare className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Görüntülemek için bir konuşma seçin</p>
              </div>
            </CardContent>
          )}
        </Card>
      </div>
    </div>
  )
}

