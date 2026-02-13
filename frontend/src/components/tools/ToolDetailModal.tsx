'use client'

import { useEffect, useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { Tool } from './types'

interface ToolDetailModalProps {
  tool: Tool | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onAddToWorkflow: (toolId: string) => void
  onSave: (toolId: string, updates: Partial<Tool>) => void
}

export function ToolDetailModal({ tool, open, onOpenChange, onAddToWorkflow, onSave }: ToolDetailModalProps) {
  const [tab, setTab] = useState('details')
  const [form, setForm] = useState({
    name: '',
    category: '',
    description: '',
    tags: '',
  })

  useEffect(() => {
    if (!tool) return
    setForm({
      name: tool.name,
      category: tool.category,
      description: tool.description,
      tags: tool.tags?.join(', ') || '',
    })
    setTab('details')
  }, [tool, open])

  if (!tool) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary text-lg font-semibold">
              {tool.icon}
            </span>
            {tool.name}
          </DialogTitle>
          <DialogDescription>{tool.description}</DialogDescription>
        </DialogHeader>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="details">Detaylar</TabsTrigger>
            <TabsTrigger value="settings">Ayarlar</TabsTrigger>
          </TabsList>

          <TabsContent value="details">
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Badge variant="secondary">{tool.category}</Badge>
                {tool.tags?.map((tag) => (
                  <Badge key={tag} variant="outline">
                    {tag}
                  </Badge>
                ))}
              </div>

              <div className="rounded-2xl border border-border/60 bg-muted/30 p-4">
                <p className="text-sm font-medium">Entegrasyon Adımları</p>
                <ol className="mt-2 space-y-2 text-sm text-muted-foreground">
                  <li>1. Tool yetkilerini doğrulayın ve erişim anahtarını ekleyin.</li>
                  <li>2. Kullanım senaryolarını seçin ve tetikleyici belirleyin.</li>
                  <li>3. Test mesajı gönderip sonucu doğrulayın.</li>
                </ol>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="settings">
            <div className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="tool-name">Tool adı</Label>
                <Input
                  id="tool-name"
                  value={form.name}
                  onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="tool-category">Kategori</Label>
                <Input
                  id="tool-category"
                  value={form.category}
                  onChange={(event) => setForm((prev) => ({ ...prev, category: event.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="tool-description">Açıklama</Label>
                <Textarea
                  id="tool-description"
                  value={form.description}
                  onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="tool-tags">Etiketler (virgülle)</Label>
                <Input
                  id="tool-tags"
                  value={form.tags}
                  onChange={(event) => setForm((prev) => ({ ...prev, tags: event.target.value }))}
                />
              </div>
            </div>
          </TabsContent>
        </Tabs>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Kapat
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              const tags = form.tags
                .split(',')
                .map((tag) => tag.trim())
                .filter(Boolean)
              onSave(tool.id, {
                name: form.name,
                category: form.category,
                description: form.description,
                tags,
              })
              setTab('details')
            }}
          >
            Ayarları Kaydet
          </Button>
          <Button onClick={() => onAddToWorkflow(tool.id)}>
            Workflow’a Ekle
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
