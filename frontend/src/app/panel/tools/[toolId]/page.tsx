'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'next/navigation'
import { Archive, ArrowLeft, Loader2, Pin, Plus, Save, Trash2 } from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { createDefaultToolWorkspaceConfig, getToolCatalogItem } from '@/components/tools/catalog'
import type { ToolWorkspaceConfig } from '@/components/tools/types'
import { notesApi } from '@/lib/api'
import { useToolStore } from '@/lib/store'
import { useToast } from '@/components/ui/use-toast'
import { cn } from '@/lib/utils'

interface WorkspaceNote {
  id: string
  title: string
  content: string
  color: string
  pinned: boolean
  archived: boolean
  updated_at: string
}

const NOTE_COLOR_MAP: Record<string, string> = {
  slate: 'border-slate-300/60 bg-slate-100/70 dark:border-slate-700/70 dark:bg-slate-900/30',
  blue: 'border-blue-300/70 bg-blue-100/60 dark:border-blue-900/70 dark:bg-blue-900/30',
  amber: 'border-amber-300/70 bg-amber-100/60 dark:border-amber-900/70 dark:bg-amber-900/30',
  emerald: 'border-emerald-300/70 bg-emerald-100/60 dark:border-emerald-900/70 dark:bg-emerald-900/30',
  rose: 'border-rose-300/70 bg-rose-100/60 dark:border-rose-900/70 dark:bg-rose-900/30',
}

export default function ToolWorkspacePage() {
  const params = useParams<{ toolId: string }>()
  const toolId = Array.isArray(params.toolId) ? params.toolId[0] : params.toolId
  const catalogTool = useMemo(() => (
    toolId ? getToolCatalogItem(toolId) : undefined
  ), [toolId])

  const { installedToolIds, toolConfigs, installTool, setToolConfig } = useToolStore()
  const { toast } = useToast()
  const [draft, setDraft] = useState<ToolWorkspaceConfig | null>(null)
  const [saved, setSaved] = useState(false)
  const [notes, setNotes] = useState<WorkspaceNote[]>([])
  const [notesLoading, setNotesLoading] = useState(false)
  const [notesSaving, setNotesSaving] = useState(false)
  const [noteForm, setNoteForm] = useState({
    title: '',
    content: '',
    color: 'slate',
  })

  const storedConfig = toolId ? toolConfigs[toolId] : undefined
  const isInstalled = toolId ? installedToolIds.includes(toolId) : false
  const isNoteTool = toolId === 'tool-note'

  useEffect(() => {
    if (!catalogTool) {
      setDraft(null)
      return
    }
    setDraft(storedConfig ?? createDefaultToolWorkspaceConfig(catalogTool))
  }, [catalogTool, storedConfig])

  const loadNotes = async () => {
    if (!isNoteTool) return
    setNotesLoading(true)
    try {
      const response = await notesApi.list({ archived: false })
      setNotes(response.data || [])
    } catch (error: any) {
      toast({
        title: 'Notlar alınamadı',
        description: error.response?.data?.detail || 'Lütfen tekrar deneyin.',
        variant: 'destructive',
      })
    } finally {
      setNotesLoading(false)
    }
  }

  useEffect(() => {
    if (isNoteTool) {
      loadNotes()
    }
  }, [isNoteTool])

  const persistDraft = () => {
    if (!toolId || !catalogTool || !draft) return

    setToolConfig(toolId, draft)
    if (!isInstalled) {
      installTool(toolId)
    }

    setSaved(true)
    window.setTimeout(() => setSaved(false), 1500)
  }

  const createNote = async () => {
    if (!noteForm.title.trim() || !noteForm.content.trim()) return
    setNotesSaving(true)
    try {
      await notesApi.create({
        title: noteForm.title.trim(),
        content: noteForm.content.trim(),
        color: noteForm.color,
      })
      setNoteForm({ title: '', content: '', color: 'slate' })
      await loadNotes()
    } catch (error: any) {
      toast({
        title: 'Not oluşturulamadı',
        description: error.response?.data?.detail || 'Lütfen tekrar deneyin.',
        variant: 'destructive',
      })
    } finally {
      setNotesSaving(false)
    }
  }

  const togglePin = async (note: WorkspaceNote) => {
    try {
      await notesApi.update(note.id, { pinned: !note.pinned })
      await loadNotes()
    } catch {
      toast({ title: 'Not güncellenemedi', variant: 'destructive' })
    }
  }

  const archiveNote = async (noteId: string) => {
    try {
      await notesApi.update(noteId, { archived: true })
      await loadNotes()
    } catch {
      toast({ title: 'Not arşivlenemedi', variant: 'destructive' })
    }
  }

  const deleteNote = async (noteId: string) => {
    try {
      await notesApi.delete(noteId)
      await loadNotes()
    } catch {
      toast({ title: 'Not silinemedi', variant: 'destructive' })
    }
  }

  if (!toolId || !catalogTool) {
    return (
      <ContentContainer>
        <Card>
          <CardHeader>
            <CardTitle>Tool bulunamadı</CardTitle>
            <CardDescription>Seçilen tool kataloğa kayıtlı değil.</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/panel/tools">
              <Button variant="outline">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Tool kataloğuna dön
              </Button>
            </Link>
          </CardContent>
        </Card>
      </ContentContainer>
    )
  }

  if (!draft) {
    return null
  }

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title={`${draft.customization.name || catalogTool.name} Yönetimi`}
          description="Tool entegrasyonu, özelleştirme ve iç operasyon ayarlarını buradan yönetin."
          actions={(
            <>
              <Link href="/panel/tools">
                <Button variant="outline">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Kataloğa dön
                </Button>
              </Link>
              <Button onClick={persistDraft}>
                <Save className="mr-2 h-4 w-4" />
                {saved ? 'Kaydedildi' : 'Kaydet'}
              </Button>
            </>
          )}
        />

        <Card>
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="flex items-center gap-2">
              <Badge variant={isInstalled ? 'default' : 'outline'}>
                {isInstalled ? 'Tool Sayfaları menüsünde aktif' : 'Henüz aktif değil'}
              </Badge>
              <span className="text-sm text-muted-foreground">{catalogTool.category}</span>
            </div>
            {!isInstalled && (
              <Button
                variant="secondary"
                onClick={() => {
                  setToolConfig(toolId, draft)
                  installTool(toolId)
                }}
              >
                Tool Sayfaları menüsüne ekle
              </Button>
            )}
          </CardContent>
        </Card>

        <Tabs defaultValue="customization">
          <TabsList>
            <TabsTrigger value="customization">Genel</TabsTrigger>
            <TabsTrigger value="integration">Entegrasyon</TabsTrigger>
            <TabsTrigger value="internal">İç Düzenleme</TabsTrigger>
          </TabsList>

          <TabsContent value="customization">
            <Card>
              <CardHeader>
                <CardTitle>Tool Özelleştirme</CardTitle>
                <CardDescription>Menü adı ve tool görünüm bilgileri.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="tool-name">Tool adı</Label>
                  <Input
                    id="tool-name"
                    value={draft.customization.name}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          customization: { ...prev.customization, name: event.target.value },
                        }
                        : prev
                    ))}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="tool-category">Kategori</Label>
                  <Input
                    id="tool-category"
                    value={draft.customization.category}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          customization: { ...prev.customization, category: event.target.value },
                        }
                        : prev
                    ))}
                  />
                </div>
                <div className="grid gap-2 sm:col-span-2">
                  <Label htmlFor="tool-description">Açıklama</Label>
                  <Textarea
                    id="tool-description"
                    value={draft.customization.description}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          customization: { ...prev.customization, description: event.target.value },
                        }
                        : prev
                    ))}
                  />
                </div>
                <div className="grid gap-2 sm:col-span-2">
                  <Label htmlFor="tool-tags">Etiketler (virgülle)</Label>
                  <Input
                    id="tool-tags"
                    value={draft.customization.tags.join(', ')}
                    onChange={(event) => {
                      const tags = event.target.value
                        .split(',')
                        .map((tag) => tag.trim())
                        .filter(Boolean)
                      setDraft((prev) => (
                        prev
                          ? {
                            ...prev,
                            customization: { ...prev.customization, tags },
                          }
                          : prev
                      ))
                    }}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="integration">
            <Card>
              <CardHeader>
                <CardTitle>Entegrasyon Ayarları</CardTitle>
                <CardDescription>API, webhook ve senkronizasyon yönetimi.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="provider">Sağlayıcı</Label>
                  <Input
                    id="provider"
                    placeholder="Meta, WordPress, n8n..."
                    value={draft.integration.provider}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          integration: { ...prev.integration, provider: event.target.value },
                        }
                        : prev
                    ))}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="api-key">API Key</Label>
                  <Input
                    id="api-key"
                    placeholder="******"
                    value={draft.integration.apiKey}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          integration: { ...prev.integration, apiKey: event.target.value },
                        }
                        : prev
                    ))}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="base-url">Base URL</Label>
                  <Input
                    id="base-url"
                    placeholder="https://api.example.com"
                    value={draft.integration.baseUrl}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          integration: { ...prev.integration, baseUrl: event.target.value },
                        }
                        : prev
                    ))}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="webhook-url">Webhook URL</Label>
                  <Input
                    id="webhook-url"
                    placeholder="https://app.svontai.com/webhook/..."
                    value={draft.integration.webhookUrl}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          integration: { ...prev.integration, webhookUrl: event.target.value },
                        }
                        : prev
                    ))}
                  />
                </div>
                <div className="flex items-center justify-between rounded-xl border border-border/70 p-3">
                  <div>
                    <p className="text-sm font-medium">Entegrasyon aktif</p>
                    <p className="text-xs text-muted-foreground">Dış servis çağrıları açılsın</p>
                  </div>
                  <Switch
                    checked={draft.integration.enabled}
                    onCheckedChange={(value) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          integration: { ...prev.integration, enabled: value },
                        }
                        : prev
                    ))}
                  />
                </div>
                <div className="flex items-center justify-between rounded-xl border border-border/70 p-3">
                  <div>
                    <p className="text-sm font-medium">Auto Sync</p>
                    <p className="text-xs text-muted-foreground">Arka planda otomatik senkron çalıştır</p>
                  </div>
                  <Switch
                    checked={draft.integration.autoSync}
                    onCheckedChange={(value) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          integration: { ...prev.integration, autoSync: value },
                        }
                        : prev
                    ))}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="internal">
            <Card>
              <CardHeader>
                <CardTitle>İç Düzenleme</CardTitle>
                <CardDescription>Operasyon, sahibi ve runbook notları.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="owner">Sorumlu kişi</Label>
                  <Input
                    id="owner"
                    placeholder="team@svontai.com"
                    value={draft.internal.owner}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          internal: { ...prev.internal, owner: event.target.value },
                        }
                        : prev
                    ))}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="environment">Ortam</Label>
                  <Select
                    value={draft.internal.environment}
                    onValueChange={(value) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          internal: { ...prev.internal, environment: value as 'test' | 'prod' },
                        }
                        : prev
                    ))}
                  >
                    <SelectTrigger id="environment">
                      <SelectValue placeholder="Ortam seçin" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="test">Test</SelectItem>
                      <SelectItem value="prod">Prod</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2 sm:col-span-2">
                  <Label htmlFor="internal-notes">İç notlar</Label>
                  <Textarea
                    id="internal-notes"
                    placeholder="Ekip içi teknik notlar..."
                    value={draft.internal.notes}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          internal: { ...prev.internal, notes: event.target.value },
                        }
                        : prev
                    ))}
                  />
                </div>
                <div className="grid gap-2 sm:col-span-2">
                  <Label htmlFor="runbook">Runbook / SOP</Label>
                  <Textarea
                    id="runbook"
                    placeholder="Adım adım operasyon prosedürü..."
                    value={draft.internal.runbook}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? {
                          ...prev,
                          internal: { ...prev.internal, runbook: event.target.value },
                        }
                        : prev
                    ))}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {isNoteTool && (
          <Card>
            <CardHeader>
              <CardTitle>Profesyonel Notlar Panosu</CardTitle>
              <CardDescription>Modern post-it mantığıyla sınırsız not, pin ve arşiv yönetimi.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-[1fr,2fr,180px,120px]">
                <Input
                  placeholder="Not başlığı"
                  value={noteForm.title}
                  onChange={(event) => setNoteForm((prev) => ({ ...prev, title: event.target.value }))}
                />
                <Textarea
                  placeholder="Not içeriği"
                  value={noteForm.content}
                  onChange={(event) => setNoteForm((prev) => ({ ...prev, content: event.target.value }))}
                />
                <Select
                  value={noteForm.color}
                  onValueChange={(value) => setNoteForm((prev) => ({ ...prev, color: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Renk" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="slate">Slate</SelectItem>
                    <SelectItem value="blue">Blue</SelectItem>
                    <SelectItem value="amber">Amber</SelectItem>
                    <SelectItem value="emerald">Emerald</SelectItem>
                    <SelectItem value="rose">Rose</SelectItem>
                  </SelectContent>
                </Select>
                <Button onClick={createNote} disabled={notesSaving}>
                  {notesSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                </Button>
              </div>

              {notesLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Notlar yükleniyor...
                </div>
              ) : (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {notes.map((note) => (
                    <div
                      key={note.id}
                      className={cn(
                        'rounded-xl border p-4 shadow-soft space-y-3',
                        NOTE_COLOR_MAP[note.color] || NOTE_COLOR_MAP.slate
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-semibold">{note.title}</p>
                          <p className="text-xs text-muted-foreground">{new Date(note.updated_at).toLocaleString('tr-TR')}</p>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button size="icon" variant={note.pinned ? 'default' : 'ghost'} onClick={() => togglePin(note)}>
                            <Pin className="h-4 w-4" />
                          </Button>
                          <Button size="icon" variant="ghost" onClick={() => archiveNote(note.id)}>
                            <Archive className="h-4 w-4" />
                          </Button>
                          <Button size="icon" variant="ghost" onClick={() => deleteNote(note.id)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                      <p className="text-sm whitespace-pre-wrap">{note.content}</p>
                    </div>
                  ))}
                  {notes.length === 0 && (
                    <div className="rounded-xl border border-dashed border-border/70 p-6 text-sm text-muted-foreground">
                      Henüz not yok. İlk profesyonel notunuzu oluşturun.
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </ContentContainer>
  )
}
