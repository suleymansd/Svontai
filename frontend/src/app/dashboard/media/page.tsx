'use client'

import Image from 'next/image'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  FileText,
  Image as ImageIcon,
  Images,
  Loader2,
  Play,
  Plus,
  Send,
  Trash2,
  UploadCloud,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
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
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { PageHeader } from '@/components/shared/page-header'
import { AssistantMediaAsset, mediaApi } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'

function formatBytes(value: number) {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function MediaPreview({ asset }: { asset: AssistantMediaAsset }) {
  if (asset.media_type === 'image') {
    return (
      <Image
        src={asset.preview_url}
        alt={asset.title}
        fill
        unoptimized
        className="object-cover"
        sizes="(max-width: 768px) 100vw, 33vw"
      />
    )
  }
  if (asset.media_type === 'video') {
    return (
      <video className="h-full w-full object-cover" controls preload="metadata">
        <source src={asset.preview_url} type={asset.mime_type} />
      </video>
    )
  }
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 bg-muted/60 text-muted-foreground">
      <FileText className="h-12 w-12" />
      <span className="text-sm font-medium">PDF Katalog</span>
    </div>
  )
}

export default function MediaLibraryPage() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [uploadOpen, setUploadOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [keywords, setKeywords] = useState('')
  const [progress, setProgress] = useState(0)

  const { data: assets = [], isLoading } = useQuery({
    queryKey: ['assistant-media'],
    queryFn: () => mediaApi.list().then((response) => response.data),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['assistant-media'] })
    queryClient.invalidateQueries({ queryKey: ['assistant-profile'] })
  }

  const uploadMutation = useMutation({
    mutationFn: (payload: FormData) => mediaApi.upload(payload, setProgress),
    onSuccess: () => {
      refresh()
      setUploadOpen(false)
      setFile(null)
      setTitle('')
      setDescription('')
      setKeywords('')
      setProgress(0)
      toast({ title: 'Medya hazır', description: 'Ana asistan artık bu içeriği doğru müşteri talebinde kullanabilir.' })
    },
    onError: (error) => toast({
      title: 'Dosya yüklenemedi',
      description: getApiErrorMessage(error, 'Dosya türünü ve boyutunu kontrol edin.'),
      variant: 'destructive',
    }),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => mediaApi.update(id, { is_active: active }),
    onSuccess: refresh,
    onError: (error) => toast({
      title: 'Durum güncellenemedi',
      description: getApiErrorMessage(error, 'Lütfen tekrar deneyin.'),
      variant: 'destructive',
    }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => mediaApi.delete(id),
    onSuccess: () => {
      refresh()
      toast({ title: 'Medya silindi' })
    },
    onError: (error) => toast({
      title: 'Medya silinemedi',
      description: getApiErrorMessage(error, 'Lütfen tekrar deneyin.'),
      variant: 'destructive',
    }),
  })

  const submitUpload = () => {
    if (!file || !title.trim()) {
      toast({ title: 'Dosya ve ad gerekli', variant: 'destructive' })
      return
    }
    const form = new FormData()
    form.append('file', file)
    form.append('title', title.trim())
    form.append('description', description.trim())
    form.append('keywords', keywords)
    uploadMutation.mutate(form)
  }

  const activeCount = assets.filter((asset) => asset.is_active).length
  const sentCount = assets.reduce((total, asset) => total + asset.send_count, 0)

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Medya Kütüphanesi"
          description="Görsel, ürün videosu ve PDF kataloglarınızı yükleyin. Ana asistan müşteri talebine göre doğru içeriği seçer."
          icon={<Icon3DBadge icon={Images} from="from-cyan-500" to="to-emerald-500" />}
          actions={(
            <Button onClick={() => setUploadOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Medya Yükle
            </Button>
          )}
        />

        <section className="grid gap-4 border-y border-border/70 py-5 sm:grid-cols-3">
          <div><p className="text-2xl font-semibold">{assets.length}</p><p className="text-sm text-muted-foreground">Toplam içerik</p></div>
          <div><p className="text-2xl font-semibold">{activeCount}</p><p className="text-sm text-muted-foreground">AI kullanımına açık</p></div>
          <div><p className="text-2xl font-semibold">{sentCount}</p><p className="text-sm text-muted-foreground">Otomatik gönderim</p></div>
        </section>

        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {[0, 1, 2].map((item) => <Skeleton key={item} className="h-80" />)}
          </div>
        ) : assets.length === 0 ? (
          <section className="flex min-h-72 flex-col items-center justify-center gap-4 border-y border-dashed border-border py-12 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-primary/10"><UploadCloud className="h-7 w-7 text-primary" /></div>
            <div><h2 className="font-semibold">Henüz medya yüklenmedi</h2><p className="mt-1 max-w-md text-sm text-muted-foreground">İlk dosyayı yüklediğinizde görsel ve katalog paylaşma yeteneği otomatik olarak açılır.</p></div>
            <Button onClick={() => setUploadOpen(true)}><Plus className="mr-2 h-4 w-4" />İlk Medyayı Yükle</Button>
          </section>
        ) : (
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {assets.map((asset) => (
              <Card key={asset.id} className="overflow-hidden border-border/70">
                <div className="relative aspect-video overflow-hidden bg-muted">
                  <MediaPreview asset={asset} />
                  <Badge className="absolute left-3 top-3" variant={asset.is_active ? 'success' : 'secondary'}>
                    {asset.is_active ? 'AI kullanımına açık' : 'Pasif'}
                  </Badge>
                </div>
                <CardContent className="space-y-4 pt-5">
                  <div className="min-w-0">
                    <h2 className="truncate font-semibold">{asset.title}</h2>
                    <p className="mt-1 line-clamp-2 min-h-10 text-sm text-muted-foreground">{asset.description || 'Açıklama eklenmedi'}</p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {asset.keywords.length ? asset.keywords.map((keyword) => <Badge key={keyword} variant="outline">{keyword}</Badge>) : <span className="text-xs text-muted-foreground">Anahtar kelime yok</span>}
                  </div>
                  <div className="flex items-center justify-between border-t border-border/70 pt-3 text-xs text-muted-foreground">
                    <span>{formatBytes(asset.file_size_bytes)}</span>
                    <span className="flex items-center gap-1"><Send className="h-3.5 w-3.5" />{asset.send_count} gönderim</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2"><Switch checked={asset.is_active} disabled={updateMutation.isPending} onCheckedChange={(active) => updateMutation.mutate({ id: asset.id, active })} aria-label={`${asset.title} AI kullanım durumu`} /><span className="text-sm">Aktif</span></div>
                    <Button variant="ghost" size="icon" onClick={() => deleteMutation.mutate(asset.id)} disabled={deleteMutation.isPending} title="Medyayı sil"><Trash2 className="h-4 w-4" /></Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </section>
        )}
      </div>

      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Medya Yükle</DialogTitle>
            <DialogDescription>JPEG, PNG, WebP, MP4 veya PDF. Dosya özel depolamada saklanır ve AI içeriği otomatik tanımlar.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="media-file">Dosya</Label>
              <Input id="media-file" type="file" accept="image/jpeg,image/png,image/webp,video/mp4,application/pdf" onChange={(event) => { const selected = event.target.files?.[0] || null; setFile(selected); if (selected && !title) setTitle(selected.name.replace(/\.[^.]+$/, '')) }} />
            </div>
            <div className="space-y-2"><Label htmlFor="media-title">İçerik adı</Label><Input id="media-title" value={title} maxLength={160} onChange={(event) => setTitle(event.target.value)} placeholder="2026 ürün kataloğu" /></div>
            <div className="space-y-2"><Label htmlFor="media-description">AI için açıklama</Label><Textarea id="media-description" value={description} maxLength={1200} onChange={(event) => setDescription(event.target.value)} placeholder="Yeni sezon ürünleri, model ve renk seçenekleri" /></div>
            <div className="space-y-2"><Label htmlFor="media-keywords">Anahtar kelimeler</Label><Input id="media-keywords" value={keywords} maxLength={800} onChange={(event) => setKeywords(event.target.value)} placeholder="katalog, yeni sezon, ürünler" /><p className="text-xs text-muted-foreground">Virgülle ayırın. AI doğru talebi bu kelimelerle eşleştirir.</p></div>
            {uploadMutation.isPending && <div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} /></div>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUploadOpen(false)} disabled={uploadMutation.isPending}>İptal</Button>
            <Button onClick={submitUpload} disabled={uploadMutation.isPending || !file || !title.trim()}>
              {uploadMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : file?.type === 'video/mp4' ? <Play className="mr-2 h-4 w-4" /> : file?.type === 'application/pdf' ? <FileText className="mr-2 h-4 w-4" /> : <ImageIcon className="mr-2 h-4 w-4" />}
              {uploadMutation.isPending ? `Yükleniyor %${progress}` : 'Yükle ve AI’a Tanıt'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ContentContainer>
  )
}
