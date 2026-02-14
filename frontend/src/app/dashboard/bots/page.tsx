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
import { cn, formatDate, maskSecret } from '@/lib/utils'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { KPIStat } from '@/components/shared/kpi-stat'
import { EmptyState } from '@/components/shared/empty-state'
import { ToolGuideAssistant } from '@/components/shared/tool-guide'

export default function BotsPage() {
  const queryClient = useQueryClient()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [formErrors, setFormErrors] = useState<{ name?: string }>({})
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    welcome_message: 'Merhaba! 👋 Size nasıl yardımcı olabilirim?',
  })

  const guideSteps = [
    {
      id: 'bot-create',
      title: 'Bot oluşturun',
      tooltip: 'Yeni bir bot ekleyerek ilk otomasyonunuzu başlatın.',
      pointer: { x: 78, y: 18 },
      highlight: { x: 68, y: 14, w: 22, h: 12 },
    },
    {
      id: 'bot-card',
      title: 'Bot kartı',
      tooltip: 'Bot detaylarına girip entegrasyonları yönetin.',
      pointer: { x: 30, y: 52 },
      highlight: { x: 10, y: 40, w: 35, h: 28 },
    },
    {
      id: 'whatsapp',
      title: 'WhatsApp bağlantısı',
      tooltip: 'Kurulum adımlarını tamamlayarak kanalı aktif edin.',
      pointer: { x: 62, y: 64 },
      highlight: { x: 55, y: 58, w: 30, h: 18 },
    },
  ]

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
    const trimmedName = formData.name.trim()
    if (!trimmedName) {
      setFormErrors({ name: 'Bot adı zorunludur.' })
      return
    }
    setFormErrors({})
    createMutation.mutate(formData)
  }

  const activeBots = bots?.filter((bot: any) => bot.is_active).length || 0

  return (
    <ContentContainer>
      <div className="relative space-y-8">
        <PageHeader
          title="Botlarım"
          description="AI asistanlarınızı yönetin ve performanslarını takip edin."
          actions={(
            <Button onClick={() => setIsCreateOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Yeni Bot Oluştur
            </Button>
          )}
        />

        <ToolGuideAssistant contextLabel="Bot Rehberi" steps={guideSteps} storageKey="svontai_tool_guide_bots" />

        {/* Stats */}
        <div className="grid gap-4 sm:grid-cols-3">
          <KPIStat label="Toplam Bot" value={bots?.length || 0} icon={<Bot className="h-5 w-5" />} />
          <KPIStat label="Aktif Bot" value={activeBots} icon={<TrendingUp className="h-5 w-5" />} />
          <KPIStat label="Toplam Mesaj" value={bots?.length === 0 ? '-' : '0'} icon={<MessageSquare className="h-5 w-5" />} />
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
          <EmptyState
            icon={<Sparkles className="h-8 w-8 text-primary" />}
            title="İlk Botunuzu Oluşturun"
            description="Yapay zeka destekli ilk asistanınızı oluşturarak müşterilerinize 7/24 otomatik yanıt vermeye başlayın."
            action={(
              <Button size="lg" onClick={() => setIsCreateOpen(true)}>
                <Plus className="w-5 h-5 mr-2" />
                Bot Oluştur
              </Button>
            )}
          />
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {bots?.map((bot: any, index: number) => (
              <Card
                key={bot.id}
                className="group border border-border/70 hover:shadow-glow-primary hover:-translate-y-1 transition-all duration-300 animate-fade-in-up gradient-border-animated"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <CardContent className="p-6">
                  {/* Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-4">
                      <div
                        className="w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg transition-transform group-hover:scale-110 animate-breathe"
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
                  <div className="p-3 rounded-xl glass-card mb-4">
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
                      {maskSecret(bot.public_key, 8, 6)}
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
                    className={cn('h-11', formErrors.name && 'border-destructive focus-visible:ring-destructive')}
                    value={formData.name}
                    onChange={(e) => {
                      setFormData({ ...formData, name: e.target.value })
                      if (formErrors.name) setFormErrors({})
                    }}
                  />
                  {formErrors.name && (
                    <p className="text-xs text-destructive">{formErrors.name}</p>
                  )}
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
                  disabled={createMutation.isPending || !formData.name.trim()}
                >
                  {createMutation.isPending ? 'Oluşturuluyor...' : 'Bot Oluştur'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </ContentContainer>
  )
}
