'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { 
  MessageSquare, 
  Search, 
  Filter,
  Send,
  Clock,
  User,
  Bot,
  Phone,
  Globe,
  ChevronRight,
  Inbox
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { conversationApi } from '@/lib/api'
import { formatDate, cn } from '@/lib/utils'

export default function ConversationsPage() {
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [searchTerm, setSearchTerm] = useState('')

  const { data: conversations, isLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => conversationApi.list({ limit: 100 }).then(res => res.data),
  })

  const { data: selectedConvData } = useQuery({
    queryKey: ['conversation', selectedConversation],
    queryFn: () => selectedConversation ? conversationApi.get(selectedConversation).then(res => res.data) : null,
    enabled: !!selectedConversation,
  })

  const filteredConversations = conversations?.filter((conv: any) => {
    if (!searchTerm) return true
    const search = searchTerm.toLowerCase()
    return (
      conv.customer_name?.toLowerCase().includes(search) ||
      conv.customer_phone?.includes(search)
    )
  })

  const activeCount = conversations?.filter((c: any) => c.status === 'active').length || 0
  const closedCount = conversations?.filter((c: any) => c.status === 'closed').length || 0
  const totalCount = conversations?.length || 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Konuşmalar</h1>
        <p className="text-muted-foreground mt-1">Müşteri konuşmalarını görüntüleyin ve yönetin</p>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-4">
        {[
          { label: 'Toplam', value: totalCount.toString(), color: 'bg-blue-500' },
          { label: 'Aktif', value: activeCount.toString(), color: 'bg-green-500' },
          { label: 'Kapatılan', value: closedCount.toString(), color: 'bg-slate-500' },
          { label: 'Bugün', value: '0', color: 'bg-violet-500' },
        ].map((stat, i) => (
          <Card key={i}>
            <CardContent className="p-4 flex items-center gap-3">
              <div className={cn('w-3 h-3 rounded-full', stat.color)} />
              <div>
                <p className="text-2xl font-bold">{stat.value}</p>
                <p className="text-sm text-muted-foreground">{stat.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Main Content */}
      <div className="grid lg:grid-cols-3 gap-6 h-[calc(100vh-320px)] min-h-[500px]">
        {/* Conversations List */}
        <Card className="lg:col-span-1 flex flex-col">
          {/* Search */}
          <div className="p-4 border-b">
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

          {/* List */}
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
              <div className="flex flex-col items-center justify-center h-full p-8 text-center">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-100 to-violet-100 dark:from-blue-900/30 dark:to-violet-900/30 flex items-center justify-center mb-4">
                  <Inbox className="w-8 h-8 text-blue-600" />
                </div>
                <h3 className="font-semibold mb-2">
                  {searchTerm ? 'Sonuç bulunamadı' : 'Henüz konuşma yok'}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {searchTerm 
                    ? 'Arama kriterlerinize uygun konuşma bulunamadı.' 
                    : 'Müşteriler botunuzla iletişime geçtiğinde konuşmalar burada görünecek.'
                  }
                </p>
              </div>
            ) : (
              filteredConversations.map((conv: any) => (
                <button
                  key={conv.id}
                  onClick={() => setSelectedConversation(conv.id)}
                  className={cn(
                    'w-full p-4 flex items-start gap-3 border-b transition-colors text-left',
                    selectedConversation === conv.id 
                      ? 'bg-blue-50 dark:bg-blue-900/20 border-l-2 border-l-blue-500' 
                      : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'
                  )}
                >
                  <div className="relative">
                    <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white font-semibold">
                      {conv.customer_name?.charAt(0).toUpperCase() || '?'}
                    </div>
                    {conv.status === 'active' && (
                      <div className="absolute bottom-0 right-0 w-3.5 h-3.5 bg-green-500 rounded-full border-2 border-white dark:border-slate-900" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium truncate">{conv.customer_name || 'Anonim'}</span>
                      <span className="text-xs text-muted-foreground">{formatDate(conv.last_message_at || conv.created_at)}</span>
                    </div>
                    <p className="text-sm text-muted-foreground truncate mb-2">
                      {conv.customer_phone || 'Telefon yok'}
                    </p>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs py-0 px-1.5 gap-1">
                        {conv.source === 'whatsapp' ? (
                          <Phone className="w-3 h-3" />
                        ) : (
                          <Globe className="w-3 h-3" />
                        )}
                        {conv.source === 'whatsapp' ? 'WA' : 'Web'}
                      </Badge>
                      <Badge variant={conv.status === 'active' ? 'success' : 'secondary'} className="text-xs">
                        {conv.status === 'active' ? 'Aktif' : 'Kapalı'}
                      </Badge>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </Card>

        {/* Chat Window */}
        <Card className="lg:col-span-2 flex flex-col">
          {selectedConvData ? (
            <>
              {/* Chat Header */}
              <div className="p-4 border-b flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white font-semibold">
                    {selectedConvData.customer_name?.charAt(0).toUpperCase() || '?'}
                  </div>
                  <div>
                    <h3 className="font-medium">{selectedConvData.customer_name || 'Anonim'}</h3>
                    <p className="text-sm text-muted-foreground flex items-center gap-1">
                      <div className={cn(
                        'w-2 h-2 rounded-full',
                        selectedConvData.status === 'active' ? 'bg-green-500' : 'bg-slate-400'
                      )} />
                      {selectedConvData.status === 'active' ? 'Aktif' : 'Kapalı'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{selectedConvData.source === 'whatsapp' ? 'WhatsApp' : 'Web Widget'}</Badge>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {selectedConvData.messages && selectedConvData.messages.length > 0 ? (
                  selectedConvData.messages.map((msg: any) => (
                    <div 
                      key={msg.id}
                      className={cn(
                        'flex gap-3',
                        msg.role === 'user' ? 'justify-start' : 'justify-end'
                      )}
                    >
                      {msg.role === 'user' && (
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0">
                          <User className="w-4 h-4 text-white" />
                        </div>
                      )}
                      <div className={cn(
                        'max-w-[70%] rounded-2xl p-4',
                        msg.role === 'user' 
                          ? 'bg-slate-100 dark:bg-slate-800 rounded-tl-sm' 
                          : 'bg-gradient-to-r from-blue-500 to-violet-600 text-white rounded-tr-sm'
                      )}>
                        <p className="text-sm">{msg.content}</p>
                        <p className={cn(
                          'text-xs mt-1',
                          msg.role === 'user' ? 'text-muted-foreground' : 'text-blue-100'
                        )}>
                          {formatDate(msg.created_at)}
                        </p>
                      </div>
                      {msg.role === 'assistant' && (
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center flex-shrink-0">
                          <Bot className="w-4 h-4 text-white" />
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-center">
                    <MessageSquare className="w-12 h-12 text-muted-foreground mb-4" />
                    <p className="text-muted-foreground">Bu konuşmada henüz mesaj yok.</p>
                  </div>
                )}
              </div>

              {/* Input */}
              <div className="p-4 border-t">
                <div className="flex gap-2">
                  <Input 
                    placeholder="Bot yanıtlarını görüntülüyorsunuz..." 
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    className="flex-1"
                    disabled
                  />
                  <Button 
                    className="bg-gradient-to-r from-blue-600 to-violet-600"
                    disabled
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground mt-2 text-center">
                  Konuşmalar bot tarafından otomatik yönetilmektedir.
                </p>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-100 to-violet-100 dark:from-blue-900/30 dark:to-violet-900/30 flex items-center justify-center mb-4">
                <MessageSquare className="w-10 h-10 text-blue-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Konuşma Seçin</h3>
              <p className="text-muted-foreground max-w-sm">
                {conversations && conversations.length > 0 
                  ? 'Detayları görüntülemek için sol taraftan bir konuşma seçin.'
                  : 'Müşteriler botunuzla iletişime geçtiğinde konuşmalar burada görünecek.'
                }
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
