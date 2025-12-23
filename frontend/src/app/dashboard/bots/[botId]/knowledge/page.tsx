'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Plus, Edit, Trash2, BookOpen, Sparkles, Lightbulb, Brain, MessageSquare, HelpCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { knowledgeApi, botApi } from '@/lib/api'
import { formatDate, truncate } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'

interface KnowledgeItem {
  id: string
  title: string
  question: string
  answer: string
  created_at: string
}

const exampleItems = [
  {
    title: 'Çalışma Saatleri',
    question: 'Çalışma saatleriniz nedir?',
    answer: 'Hafta içi 09:00 - 18:00 arası hizmet vermekteyiz. Hafta sonu kapalıyız ancak online sipariş verebilirsiniz.'
  },
  {
    title: 'Kargo Bilgisi',
    question: 'Kargo ücreti ne kadar?',
    answer: '150 TL ve üzeri siparişlerde kargo ücretsizdir. Altındaki siparişlerde 29.90 TL kargo ücreti alınmaktadır. Kargo süresi 2-3 iş günüdür.'
  },
  {
    title: 'İade Politikası',
    question: 'Ürün iade edebilir miyim?',
    answer: '14 gün içinde kullanılmamış ve orijinal ambalajında olan ürünleri iade edebilirsiniz. İade için müşteri hizmetlerimizle iletişime geçmeniz yeterli.'
  }
]

export default function KnowledgeBasePage() {
  const params = useParams()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const botId = params.botId as string
  
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<KnowledgeItem | null>(null)
  const [formData, setFormData] = useState({
    title: '',
    question: '',
    answer: '',
  })

  const { data: bot } = useQuery({
    queryKey: ['bot', botId],
    queryFn: () => botApi.get(botId).then(res => res.data),
  })

  const { data: items, isLoading } = useQuery({
    queryKey: ['knowledge', botId],
    queryFn: () => knowledgeApi.list(botId).then(res => res.data),
  })

  const createMutation = useMutation({
    mutationFn: (data: typeof formData) => knowledgeApi.create(botId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge', botId] })
      closeDialog()
      toast({
        title: 'Bilgi eklendi',
        description: 'AI artık bu bilgiyi kullanarak yanıt verebilir.',
      })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: typeof formData }) => 
      knowledgeApi.update(botId, id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge', botId] })
      closeDialog()
      toast({
        title: 'Bilgi güncellendi',
        description: 'Değişiklikler kaydedildi.',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => knowledgeApi.delete(botId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge', botId] })
      toast({
        title: 'Bilgi silindi',
        description: 'Bilgi tabanından kaldırıldı.',
      })
    },
  })

  const openCreateDialog = () => {
    setEditingItem(null)
    setFormData({ title: '', question: '', answer: '' })
    setIsDialogOpen(true)
  }

  const openEditDialog = (item: KnowledgeItem) => {
    setEditingItem(item)
    setFormData({
      title: item.title,
      question: item.question,
      answer: item.answer,
    })
    setIsDialogOpen(true)
  }

  const useExample = (example: typeof exampleItems[0]) => {
    setFormData(example)
    setIsDialogOpen(true)
  }

  const closeDialog = () => {
    setIsDialogOpen(false)
    setEditingItem(null)
    setFormData({ title: '', question: '', answer: '' })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, data: formData })
    } else {
      createMutation.mutate(formData)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href={`/dashboard/bots/${botId}`}>
            <Button variant="ghost" size="icon">
              <ArrowLeft className="w-5 h-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Brain className="w-8 h-8 text-violet-600" />
              AI Bilgi Tabanı
            </h1>
            <p className="text-muted-foreground">{bot?.name} - AI'ın bilmesi gereken bilgileri ekleyin</p>
          </div>
        </div>
        <Button 
          onClick={openCreateDialog}
          className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700"
        >
          <Plus className="w-4 h-4 mr-2" />
          Bilgi Ekle
        </Button>
      </div>

      {/* How it works info */}
      <Card className="border-blue-200 dark:border-blue-800 bg-gradient-to-br from-blue-50 to-violet-50 dark:from-blue-900/20 dark:to-violet-900/20">
        <CardContent className="p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-semibold">AI Nasıl Çalışır?</h3>
              <p className="text-muted-foreground">
                Siz bilgi tabanına <strong>işletmeniz hakkında bilgiler</strong> eklersiniz. 
                AI bu bilgileri kullanarak müşterilerinizin <strong>herhangi bir sorusuna</strong> akıllı ve doğal yanıtlar üretir.
              </p>
              <div className="flex flex-wrap gap-4 mt-3 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                    <span className="text-green-600 font-bold">1</span>
                  </div>
                  <span>Bilgi ekleyin</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                    <span className="text-blue-600 font-bold">2</span>
                  </div>
                  <span>Müşteri soru sorar</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
                    <span className="text-violet-600 font-bold">3</span>
                  </div>
                  <span>AI akıllı yanıt üretir</span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Knowledge Items */}
      {isLoading ? (
        <div className="grid gap-4">
          {[...Array(3)].map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-5 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-2/3" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : items?.length === 0 ? (
        <div className="space-y-6">
          <Card className="border-dashed border-2">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-blue-100 to-violet-100 dark:from-blue-900/30 dark:to-violet-900/30 flex items-center justify-center mb-6">
                <BookOpen className="w-10 h-10 text-blue-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Bilgi tabanınız boş</h3>
              <p className="text-muted-foreground text-center max-w-md mb-6">
                İşletmeniz hakkında bilgiler ekleyerek AI'ınızı eğitin. 
                Ne kadar çok bilgi eklerseniz, AI o kadar doğru yanıt verir.
              </p>
              <Button 
                onClick={openCreateDialog}
                className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700"
              >
                <Plus className="w-4 h-4 mr-2" />
                İlk Bilgiyi Ekle
              </Button>
            </CardContent>
          </Card>

          {/* Example suggestions */}
          <div>
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Lightbulb className="w-5 h-5 text-yellow-500" />
              Başlangıç için öneriler
            </h3>
            <div className="grid gap-4 md:grid-cols-3">
              {exampleItems.map((example, i) => (
                <Card 
                  key={i} 
                  className="cursor-pointer hover:shadow-lg hover:border-blue-300 dark:hover:border-blue-700 transition-all group"
                  onClick={() => useExample(example)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Badge variant="outline" className="text-xs">Örnek</Badge>
                      <span className="text-sm font-medium">{example.title}</span>
                    </div>
                    <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
                      <strong>S:</strong> {example.question}
                    </p>
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      <strong>C:</strong> {truncate(example.answer, 80)}
                    </p>
                    <p className="text-xs text-blue-600 mt-3 opacity-0 group-hover:opacity-100 transition-opacity">
                      Tıklayarak kullan →
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {items?.length} bilgi öğesi • AI bu bilgileri kullanarak yanıt üretir
            </p>
          </div>
          <div className="grid gap-4">
            {items?.map((item: KnowledgeItem) => (
              <Card key={item.id} className="hover:shadow-md transition-shadow group">
                <CardHeader className="flex flex-row items-start justify-between pb-2">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
                        <BookOpen className="w-4 h-4 text-white" />
                      </div>
                      <CardTitle className="text-lg">{item.title}</CardTitle>
                    </div>
                    <CardDescription>{formatDate(item.created_at)}</CardDescription>
                  </div>
                  <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button variant="ghost" size="icon" onClick={() => openEditDialog(item)}>
                      <Edit className="w-4 h-4" />
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      onClick={() => deleteMutation.mutate(item.id)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50">
                    <p className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1">
                      <HelpCircle className="w-3 h-3" />
                      Örnek Müşteri Sorusu
                    </p>
                    <p className="text-sm">{item.question}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20">
                    <p className="text-xs font-medium text-blue-600 dark:text-blue-400 mb-1 flex items-center gap-1">
                      <MessageSquare className="w-3 h-3" />
                      AI'ın Kullanacağı Bilgi
                    </p>
                    <p className="text-sm text-muted-foreground">{item.answer}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center mb-4">
              <Brain className="w-6 h-6 text-white" />
            </div>
            <DialogTitle className="text-2xl">
              {editingItem ? 'Bilgiyi Düzenle' : 'Yeni Bilgi Ekle'}
            </DialogTitle>
            <DialogDescription>
              AI, bu bilgiyi kullanarak müşterilerin sorularına doğal ve akıllı yanıtlar üretecek.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit}>
            <div className="space-y-5 py-4">
              <div className="space-y-2">
                <Label htmlFor="title">Bilgi Başlığı *</Label>
                <Input
                  id="title"
                  placeholder="Örn: Çalışma Saatleri, Kargo Bilgisi, İade Politikası"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  required
                />
                <p className="text-xs text-muted-foreground">Bu başlık organizasyon içindir, AI'a gönderilir.</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="question">Örnek Müşteri Sorusu *</Label>
                <Textarea
                  id="question"
                  placeholder="Örn: Çalışma saatleriniz nedir? Saat kaçta açılıyorsunuz?"
                  value={formData.question}
                  onChange={(e) => setFormData({ ...formData, question: e.target.value })}
                  required
                  rows={2}
                />
                <p className="text-xs text-muted-foreground">Müşterilerin bu konuda nasıl soru sorabileceğini yazın. AI benzer soruları anlayacaktır.</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="answer">Doğru Bilgi / Cevap *</Label>
                <Textarea
                  id="answer"
                  placeholder="Örn: Mağazamız hafta içi 09:00-18:00, hafta sonu 10:00-16:00 arası açıktır. Resmi tatillerde kapalıyız."
                  value={formData.answer}
                  onChange={(e) => setFormData({ ...formData, answer: e.target.value })}
                  required
                  rows={4}
                />
                <p className="text-xs text-muted-foreground">
                  AI bu bilgiyi kullanarak <strong>kendi cümleleriyle</strong> doğal bir yanıt oluşturacak.
                </p>
              </div>
              
              {/* Preview */}
              {formData.answer && (
                <div className="p-4 rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20">
                  <p className="text-xs font-medium text-green-600 dark:text-green-400 mb-2 flex items-center gap-1">
                    <Sparkles className="w-3 h-3" />
                    AI bu bilgiyi şu şekilde kullanabilir:
                  </p>
                  <p className="text-sm text-muted-foreground italic">
                    "Merhaba! {formData.answer.slice(0, 100)}... Başka bir sorunuz var mı?"
                  </p>
                </div>
              )}
            </div>
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={closeDialog}>
                İptal
              </Button>
              <Button 
                type="submit" 
                className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700"
                disabled={createMutation.isPending || updateMutation.isPending}
              >
                {createMutation.isPending || updateMutation.isPending ? 'Kaydediliyor...' : 'Kaydet'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
