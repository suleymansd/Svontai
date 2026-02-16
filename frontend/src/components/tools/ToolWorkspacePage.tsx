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
import { ToolIcon3D } from '@/components/tools/ToolIcon3D'
import { RealEstatePackPanel } from '@/components/tools/RealEstatePackPanel'

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
  const isRealEstateTool = toolId === 'tool-real-estate-pack'

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
            <Link href="/dashboard/tools">
              <Button type="button" variant="outline">
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
          icon={<ToolIcon3D toolId={toolId} size="md" active />}
          actions={(
            <>
              <Link href="/dashboard/tools">
                <Button type="button" variant="outline">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Kataloğa dön
                </Button>
              </Link>
              <Button type="button" onClick={persistDraft}>
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
                type="button"
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
            {isRealEstateTool && <TabsTrigger value="real-estate">Real Estate Pack</TabsTrigger>}
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
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="integration">
            <Card>
              <CardHeader>
                <CardTitle>Entegrasyon</CardTitle>
                <CardDescription>Bu tool dış servislerle bağlanıyorsa burada yönetilir.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="integration-provider">Provider</Label>
                  <Input
                    id="integration-provider"
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
                  <Label htmlFor="integration-base-url">Base URL</Label>
                  <Input
                    id="integration-base-url"
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
                <div className="grid gap-2 sm:col-span-2">
                  <Label htmlFor="integration-webhook">Webhook URL</Label>
                  <Input
                    id="integration-webhook"
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
                <div className="grid gap-2 sm:col-span-2">
                  <Label htmlFor="integration-api-key">API Key</Label>
                  <Input
                    id="integration-api-key"
                    type="password"
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
                <div className="flex items-center justify-between gap-3 rounded-xl border border-border/70 bg-muted/30 p-3 sm:col-span-2">
                  <div>
                    <p className="text-sm font-medium">Entegrasyonu aktif et</p>
                    <p className="text-xs text-muted-foreground">Tool dış servislerle iletişime geçer.</p>
                  </div>
                  <Switch
                    checked={draft.integration.enabled}
                    onCheckedChange={(value) => setDraft((prev) => (
                      prev
                        ? { ...prev, integration: { ...prev.integration, enabled: value } }
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
                <CardTitle>İç Operasyon</CardTitle>
                <CardDescription>Tool’un iç çalışma notları ve runbook bilgileri.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="internal-owner">Sorumlu</Label>
                  <Input
                    id="internal-owner"
                    value={draft.internal.owner}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? { ...prev, internal: { ...prev.internal, owner: event.target.value } }
                        : prev
                    ))}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="internal-env">Ortam</Label>
                  <Select
                    value={draft.internal.environment}
                    onValueChange={(value) => setDraft((prev) => (
                      prev
                        ? { ...prev, internal: { ...prev.internal, environment: value as any } }
                        : prev
                    ))}
                  >
                    <SelectTrigger id="internal-env">
                      <SelectValue placeholder="Ortam seçin" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="test">Test</SelectItem>
                      <SelectItem value="prod">Prod</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2 sm:col-span-2">
                  <Label htmlFor="internal-notes">Notlar</Label>
                  <Textarea
                    id="internal-notes"
                    value={draft.internal.notes}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? { ...prev, internal: { ...prev.internal, notes: event.target.value } }
                        : prev
                    ))}
                  />
                </div>
                <div className="grid gap-2 sm:col-span-2">
                  <Label htmlFor="internal-runbook">Runbook</Label>
                  <Textarea
                    id="internal-runbook"
                    value={draft.internal.runbook}
                    onChange={(event) => setDraft((prev) => (
                      prev
                        ? { ...prev, internal: { ...prev.internal, runbook: event.target.value } }
                        : prev
                    ))}
                  />
                </div>
              </CardContent>
            </Card>

            {isNoteTool && (
              <div className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Notlar</CardTitle>
                    <CardDescription>Bu tool için ekip notları.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="grid gap-2">
                        <Label>Başlık</Label>
                        <Input
                          value={noteForm.title}
                          onChange={(event) => setNoteForm((prev) => ({ ...prev, title: event.target.value }))}
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label>Renk</Label>
                        <Select
                          value={noteForm.color}
                          onValueChange={(value) => setNoteForm((prev) => ({ ...prev, color: value }))}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Renk seçin" />
                          </SelectTrigger>
                          <SelectContent>
                            {Object.keys(NOTE_COLOR_MAP).map((color) => (
                              <SelectItem key={color} value={color}>
                                {color}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="grid gap-2 sm:col-span-2">
                        <Label>İçerik</Label>
                        <Textarea
                          rows={4}
                          value={noteForm.content}
                          onChange={(event) => setNoteForm((prev) => ({ ...prev, content: event.target.value }))}
                        />
                      </div>
                    </div>
                    <Button type="button" onClick={createNote} disabled={notesSaving}>
                      {notesSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                      Not oluştur
                    </Button>
                  </CardContent>
                </Card>

                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {notesLoading ? (
                    <Card>
                      <CardContent className="p-6 text-sm text-muted-foreground">
                        Notlar yükleniyor...
                      </CardContent>
                    </Card>
                  ) : notes.length === 0 ? (
                    <Card>
                      <CardContent className="p-6 text-sm text-muted-foreground">
                        Henüz not yok.
                      </CardContent>
                    </Card>
                  ) : (
                    notes.map((note) => (
                      <Card
                        key={note.id}
                        className={cn('relative border shadow-soft transition-all', NOTE_COLOR_MAP[note.color] || NOTE_COLOR_MAP.slate)}
                      >
                        <CardHeader className="space-y-1 pb-3">
                          <div className="flex items-start justify-between gap-2">
                            <CardTitle className="text-base">{note.title}</CardTitle>
                            <div className="flex items-center gap-1">
                              <Button type="button" variant="ghost" size="icon" onClick={() => togglePin(note)}>
                                <Pin className={cn('h-4 w-4', note.pinned && 'text-primary')} />
                              </Button>
                              <Button type="button" variant="ghost" size="icon" onClick={() => archiveNote(note.id)}>
                                <Archive className="h-4 w-4" />
                              </Button>
                              <Button type="button" variant="ghost" size="icon" onClick={() => deleteNote(note.id)}>
                                <Trash2 className="h-4 w-4 text-destructive" />
                              </Button>
                            </div>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {new Date(note.updated_at).toLocaleString('tr-TR')}
                          </p>
                        </CardHeader>
                        <CardContent>
                          <p className="whitespace-pre-wrap text-sm">{note.content}</p>
                        </CardContent>
                      </Card>
                    ))
                  )}
                </div>
              </div>
            )}
          </TabsContent>

          {isRealEstateTool && (
            <TabsContent value="real-estate">
              <RealEstatePackPanel />
            </TabsContent>
          )}
        </Tabs>
      </div>
    </ContentContainer>
  )
}
