'use client'

import { useQuery } from '@tanstack/react-query'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, MessageSquare, User, Bot } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { conversationApi, botApi } from '@/lib/api'
import { formatDateTime, truncate } from '@/lib/utils'

interface Conversation {
  id: string
  external_user_id: string
  source: 'whatsapp' | 'web_widget'
  created_at: string
  updated_at: string
}

export default function BotConversationsPage() {
  const params = useParams()
  const botId = params.botId as string

  const { data: bot } = useQuery({
    queryKey: ['bot', botId],
    queryFn: () => botApi.get(botId).then(res => res.data),
  })

  const { data: conversations, isLoading } = useQuery({
    queryKey: ['conversations', botId],
    queryFn: () => conversationApi.listByBot(botId).then(res => res.data),
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/dashboard/conversations">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold">Konuşmalar</h1>
          <p className="text-muted-foreground">{bot?.name}</p>
        </div>
      </div>

      {/* Conversations List */}
      {isLoading ? (
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-4">
                <div className="flex items-center gap-4">
                  <Skeleton className="w-12 h-12 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-48" />
                  </div>
                  <Skeleton className="h-6 w-20 rounded-full" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : conversations?.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <MessageSquare className="w-16 h-16 text-muted-foreground mb-4" />
            <h3 className="text-xl font-semibold mb-2">Henüz konuşma yok</h3>
            <p className="text-muted-foreground text-center max-w-md">
              Bu bot ile başlatılan konuşmalar burada görünecek
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {conversations?.map((conv: Conversation) => (
            <Link key={conv.id} href={`/dashboard/conversations/${conv.id}`}>
              <Card className="hover:shadow-md transition-all cursor-pointer">
                <CardContent className="p-4">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-700 dark:to-slate-800 flex items-center justify-center">
                      <User className="w-6 h-6 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="font-medium truncate">
                          {conv.source === 'whatsapp' 
                            ? conv.external_user_id.replace(/(\d{2})(\d+)(\d{2})/, '$1***$3')
                            : truncate(conv.external_user_id, 20)}
                        </p>
                        <Badge variant={conv.source === 'whatsapp' ? 'success' : 'secondary'}>
                          {conv.source === 'whatsapp' ? 'WhatsApp' : 'Web'}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Son güncelleme: {formatDateTime(conv.updated_at)}
                      </p>
                    </div>
                    <MessageSquare className="w-5 h-5 text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

