'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
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
import { conversationApi } from '@/lib/api'
import { formatDate, cn } from '@/lib/utils'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { KPIStat } from '@/components/shared/kpi-stat'
import { EmptyState } from '@/components/shared/empty-state'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'

export default function ConversationsPage() {
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [searchTerm, setSearchTerm] = useState('')

  const { data: conversations, isLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => conversationApi.list({ limit: 100 }).then((res) => res.data),
  })

  const { data: selectedConvData } = useQuery({
    queryKey: ['conversation', selectedConversation],
    queryFn: () => (selectedConversation ? conversationApi.get(selectedConversation).then((res) => res.data) : null),
    enabled: !!selectedConversation,
  })

  const filteredConversations = conversations?.filter((conv: any) => {
    if (!searchTerm) return true
    const search = searchTerm.toLowerCase()
    return conv.customer_name?.toLowerCase().includes(search) || conv.customer_phone?.includes(search)
  })

  const activeCount = conversations?.filter((c: any) => c.status === 'active').length || 0
  const closedCount = conversations?.filter((c: any) => c.status === 'closed').length || 0
  const totalCount = conversations?.length || 0

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Konuşmalar"
          description="Müşteri konuşmalarını görüntüleyin ve yönetin."
          icon={<Icon3DBadge icon={MessageSquare} from="from-primary" to="to-violet-500" />}
        />

        <div className="grid gap-4 sm:grid-cols-4">
          <KPIStat label="Toplam" value={totalCount} icon={<MessageSquare className="h-5 w-5" />} />
          <KPIStat label="Aktif" value={activeCount} icon={<Clock className="h-5 w-5" />} />
          <KPIStat label="Kapatılan" value={closedCount} icon={<MessageSquare className="h-5 w-5" />} />
          <KPIStat label="Bugün" value="0" icon={<MessageSquare className="h-5 w-5" />} />
        </div>

        <div className="grid lg:grid-cols-3 gap-6 h-[calc(100vh-320px)] min-h-[500px]">
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
                          <Badge variant={conv.status === 'active' ? 'success' : 'secondary'}>
                            {conv.status === 'active' ? 'Aktif' : 'Kapalı'}
                          </Badge>
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
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary/20 to-violet-500/20 text-primary flex items-center justify-center ring-2 ring-primary/10">
                      <User className="w-5 h-5" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold">
                        {selectedConvData.customer_name || selectedConvData.customer_phone}
                      </h3>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        {selectedConvData.customer_phone && (
                          <span className="flex items-center gap-1">
                            <Phone className="w-3 h-3" />
                            {selectedConvData.customer_phone}
                          </span>
                        )}
                        {selectedConvData.source && (
                          <span className="flex items-center gap-1">
                            <Globe className="w-3 h-3" />
                            {selectedConvData.source}
                          </span>
                        )}
                      </div>
                    </div>
                    <Badge variant={selectedConvData.status === 'active' ? 'success' : 'secondary'}>
                      {selectedConvData.status === 'active' ? 'Aktif' : 'Kapalı'}
                    </Badge>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                  {(selectedConvData.messages || []).map((msg: any) => (
                    <div
                      key={msg.id}
                      className={cn(
                        'flex gap-3',
                        msg.sender_type === 'bot' ? 'justify-end' : 'justify-start'
                      )}
                    >
                      <div
                        className={cn(
                          'max-w-[70%] rounded-2xl px-4 py-3 text-sm',
                          msg.sender_type === 'bot'
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
