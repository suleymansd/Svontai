'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { 
  Plus, 
  Bot, 
  Edit, 
  Copy, 
  Check, 
  MoreHorizontal,
  Sparkles,
  MessageSquare,
  Users,
  TrendingUp,
  ExternalLink,
  BookOpen
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { botApi } from '@/lib/api'
import { formatDate, cn } from '@/lib/utils'

export default function BotsPage() {
  const queryClient = useQueryClient()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    welcome_message: 'Merhaba! 👋 Size nasıl yardımcı olabilirim?',
  })

  const { data: bots, isLoading } = useQuery({
    queryKey: ['bots'],
    queryFn: () => botApi.list().then(res => res.data),
  })

  const createMutation = useMutation({
    mutationFn: (data: typeof formData) => botApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bots'] })
      setIsCreateOpen(false)
      setFormData({
        name: '',
        description: '',
        welcome_message: 'Merhaba! 👋 Size nasıl yardımcı olabilirim?',
      })
    },
  })

  const copyPublicKey = async (key: string) => {
    await navigator.clipboard.writeText(key)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey(null), 2000)
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  const activeBots = bots?.filter((bot: any) => bot.is_active).length || 0

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Botlarım</h1>
          <p className="text-muted-foreground mt-1">AI asistanlarınızı yönetin ve performanslarını takip edin</p>
        </div>
        <Button 
          onClick={() => setIsCreateOpen(true)}
          className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 shadow-lg shadow-blue-500/25"
        >
          <Plus className="w-4 h-4 mr-2" />
          Yeni Bot Oluştur
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-blue-900/20 dark:to-cyan-900/20 border-blue-200 dark:border-blue-800">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
              <Bot className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-2xl font-bold">{bots?.length || 0}</p>
              <p className="text-sm text-muted-foreground">Toplam Bot</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-green-200 dark:border-green-800">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-2xl font-bold">{activeBots}</p>
              <p className="text-sm text-muted-foreground">Aktif Bot</p>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-violet-50 to-purple-50 dark:from-violet-900/20 dark:to-purple-900/20 border-violet-200 dark:border-violet-800">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center">
              <MessageSquare className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-2xl font-bold">{bots?.length === 0 ? '-' : '0'}</p>
              <p className="text-sm text-muted-foreground">Toplam Mesaj</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bots Grid */}
      {isLoading ? (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="flex items-center gap-4 mb-4">
                  <Skeleton className="w-14 h-14 rounded-2xl" />
                  <div className="space-y-2">
                    <Skeleton className="h-5 w-32" />
                    <Skeleton className="h-4 w-20" />
                  </div>
                </div>
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-2/3" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : bots?.length === 0 ? (
        <Card className="border-dashed border-2">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <div className="w-24 h-24 rounded-3xl bg-gradient-to-br from-blue-100 to-violet-100 dark:from-blue-900/30 dark:to-violet-900/30 flex items-center justify-center mb-6">
              <Sparkles className="w-12 h-12 text-blue-600" />
            </div>
            <h3 className="text-2xl font-bold mb-2">İlk Botunuzu Oluşturun</h3>
            <p className="text-muted-foreground text-center max-w-md mb-8">
              Yapay zeka destekli ilk asistanınızı oluşturarak müşterilerinize 
              7/24 otomatik yanıt vermeye başlayın.
            </p>
            <Button 
              size="lg"
              onClick={() => setIsCreateOpen(true)}
              className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 shadow-lg shadow-blue-500/25"
            >
              <Plus className="w-5 h-5 mr-2" />
              Bot Oluştur
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {bots?.map((bot: any, index: number) => (
            <Card 
              key={bot.id} 
              className="group hover:shadow-xl hover:shadow-primary/5 hover:-translate-y-1 transition-all duration-300 animate-fade-in-up"
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <CardContent className="p-6">
                {/* Header */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <div 
                      className="w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg transition-transform group-hover:scale-110"
                      style={{ backgroundColor: bot.primary_color + '20' }}
                    >
                      <Bot className="w-7 h-7" style={{ color: bot.primary_color }} />
                    </div>
                    <div>
                      <h3 className="font-semibold text-lg group-hover:text-primary transition-colors">
                        {bot.name}
                      </h3>
                      <Badge variant={bot.is_active ? 'success' : 'secondary'}>
                        {bot.is_active ? '● Aktif' : '○ Pasif'}
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Description */}
                {bot.description && (
                  <p className="text-sm text-muted-foreground mb-4 line-clamp-2">
                    {bot.description}
                  </p>
                )}

                {/* Widget Key */}
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 mb-4">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-muted-foreground">Widget Key</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2"
                      onClick={() => copyPublicKey(bot.public_key)}
                    >
                      {copiedKey === bot.public_key ? (
                        <Check className="w-3 h-3 text-green-600" />
                      ) : (
                        <Copy className="w-3 h-3" />
                      )}
                    </Button>
                  </div>
                  <code className="text-xs text-muted-foreground font-mono truncate block">
                    {bot.public_key}
                  </code>
                </div>

                {/* Actions */}
                <div className="flex gap-2">
                  <Link href={`/dashboard/bots/${bot.id}`} className="flex-1">
                    <Button variant="outline" className="w-full" size="sm">
                      <Edit className="w-4 h-4 mr-2" />
                      Düzenle
                    </Button>
                  </Link>
                  <Link href={`/dashboard/bots/${bot.id}/knowledge`} className="flex-1">
                    <Button variant="outline" className="w-full" size="sm">
                      <BookOpen className="w-4 h-4 mr-2" />
                      Eğit
                    </Button>
                  </Link>
                </div>

                {/* Created Date */}
                <p className="text-xs text-muted-foreground text-center mt-4">
                  Oluşturulma: {formatDate(bot.created_at)}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center mb-4">
              <Bot className="w-6 h-6 text-white" />
            </div>
            <DialogTitle className="text-2xl">Yeni Bot Oluştur</DialogTitle>
            <DialogDescription>
              Müşterilerinize otomatik yanıt verecek yeni bir AI asistanı oluşturun.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate}>
            <div className="space-y-5 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">Bot Adı *</Label>
                <Input
                  id="name"
                  placeholder="Örn: Müşteri Destek Botu"
                  className="h-11"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Açıklama</Label>
                <Textarea
                  id="description"
                  placeholder="Bu bot ne işe yarıyor? (Opsiyonel)"
                  className="min-h-[80px]"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="welcome_message">Karşılama Mesajı</Label>
                <Textarea
                  id="welcome_message"
                  placeholder="Müşterilerinizi nasıl karşılayacaksınız?"
                  className="min-h-[80px]"
                  value={formData.welcome_message}
                  onChange={(e) => setFormData({ ...formData, welcome_message: e.target.value })}
                />
              </div>
            </div>
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>
                İptal
              </Button>
              <Button 
                type="submit" 
                className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700"
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? 'Oluşturuluyor...' : 'Bot Oluştur'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
