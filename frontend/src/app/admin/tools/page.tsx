'use client'

import { useEffect, useMemo, useState } from 'react'
import { Plus, Pencil, Trash2, BadgeCheck } from 'lucide-react'
import { adminApi } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { EmptyState } from '@/components/shared/empty-state'
import { FilterBar } from '@/components/shared/filter-bar'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { IconButton } from '@/components/shared/icon-button'
import { ToolGuideAssistant } from '@/components/shared/tool-guide'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'

interface Tool {
  id: string
  key: string
  name: string
  description?: string | null
  category?: string | null
  icon?: string | null
  tags?: string[] | null
  required_plan?: string | null
  status: string
  is_public: boolean
  coming_soon: boolean
  created_at: string
  updated_at: string
}

interface ToolListResponse {
  items: Tool[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

const emptyToolForm = {
  key: '',
  name: '',
  description: '',
  category: '',
  icon: '',
  tags: '',
  required_plan: '',
  status: 'active',
  is_public: true,
  coming_soon: false
}

export default function ToolsAdminPage() {
  const { toast } = useToast()
  const [tools, setTools] = useState<Tool[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [activeTool, setActiveTool] = useState<Tool | null>(null)
  const [form, setForm] = useState({ ...emptyToolForm })

  const fetchTools = async () => {
    try {
      setLoading(true)
      const response = await adminApi.listTools({ page, page_size: 20, search: search || undefined })
      const data: ToolListResponse = response.data
      setTools(data.items)
      setTotal(data.total)
    } catch (error) {
      toast({
        title: 'Hata',
        description: 'Araçlar yüklenemedi',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTools()
  }, [page, search])

  const columns: DataColumn<Tool>[] = useMemo(() => [
    {
      key: 'tool',
      header: 'Araç',
      render: (row) => (
        <div className="flex items-start gap-3">
          <div className="h-9 w-9 rounded-xl bg-primary/10 text-primary flex items-center justify-center text-sm font-semibold">
            {row.icon || row.name.charAt(0).toUpperCase()}
          </div>
          <div>
            <p className="font-semibold">{row.name}</p>
            <p className="text-xs text-muted-foreground">{row.key} • {row.category || 'Genel'}</p>
          </div>
        </div>
      )
    },
    {
      key: 'status',
      header: 'Durum',
      render: (row) => (
        <div className="flex flex-wrap gap-2">
          <Badge variant={row.status === 'active' ? 'default' : 'secondary'}>
            {row.status}
          </Badge>
          {row.coming_soon && (
            <Badge variant="outline">Coming soon</Badge>
          )}
        </div>
      )
    },
    {
      key: 'plan',
      header: 'Plan',
      render: (row) => (
        <span className="text-sm text-muted-foreground">{row.required_plan || 'Tümü'}</span>
      )
    },
    {
      key: 'actions',
      header: 'İşlemler',
      render: (row) => (
        <div className="flex items-center gap-2">
          <IconButton label="Aracı düzenle" onClick={() => openEdit(row)}>
            <Pencil className="h-4 w-4" />
          </IconButton>
          <IconButton label="Aracı sil" variant="destructive" onClick={() => handleDelete(row)}>
            <Trash2 className="h-4 w-4" />
          </IconButton>
        </div>
      )
    }
  ], [])

  const openCreate = () => {
    setForm({ ...emptyToolForm })
    setCreateOpen(true)
  }

  const openEdit = (tool: Tool) => {
    setActiveTool(tool)
    setForm({
      key: tool.key,
      name: tool.name,
      description: tool.description || '',
      category: tool.category || '',
      icon: tool.icon || '',
      tags: (tool.tags || []).join(', '),
      required_plan: tool.required_plan || '',
      status: tool.status,
      is_public: tool.is_public,
      coming_soon: tool.coming_soon
    })
    setEditOpen(true)
  }

  const handleCreate = async () => {
    try {
      await adminApi.createTool({
        key: form.key,
        name: form.name,
        description: form.description || undefined,
        category: form.category || undefined,
        icon: form.icon || undefined,
        tags: form.tags ? form.tags.split(',').map((tag) => tag.trim()).filter(Boolean) : undefined,
        required_plan: form.required_plan || undefined,
        status: form.status,
        is_public: form.is_public,
        coming_soon: form.coming_soon
      })
      toast({ title: 'Başarılı', description: 'Araç oluşturuldu' })
      setCreateOpen(false)
      fetchTools()
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Araç oluşturulamadı',
        variant: 'destructive'
      })
    }
  }

  const handleUpdate = async () => {
    if (!activeTool) return

    try {
      await adminApi.updateTool(activeTool.id, {
        key: form.key,
        name: form.name,
        description: form.description || undefined,
        category: form.category || undefined,
        icon: form.icon || undefined,
        tags: form.tags ? form.tags.split(',').map((tag) => tag.trim()).filter(Boolean) : undefined,
        required_plan: form.required_plan || undefined,
        status: form.status,
        is_public: form.is_public,
        coming_soon: form.coming_soon
      })
      toast({ title: 'Başarılı', description: 'Araç güncellendi' })
      setEditOpen(false)
      setActiveTool(null)
      fetchTools()
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Araç güncellenemedi',
        variant: 'destructive'
      })
    }
  }

  const handleDelete = async (tool: Tool) => {
    if (!confirm(`${tool.name} aracını silmek istediğinize emin misiniz?`)) return

    try {
      await adminApi.deleteTool(tool.id)
      toast({ title: 'Başarılı', description: 'Araç silindi' })
      fetchTools()
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Araç silinemedi',
        variant: 'destructive'
      })
    }
  }

  return (
    <ContentContainer>
      <div className="relative space-y-6">
        <PageHeader
          title="Araç Kataloğu"
          description={`Toplam ${total} araç`}
          icon={<Icon3DBadge icon={BadgeCheck} from="from-primary" to="to-violet-500" />}
          actions={(
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Yeni Araç
            </Button>
          )}
        />

        <FilterBar
          searchPlaceholder="Araç ara..."
          onSearchChange={(value) => {
            setSearch(value)
            setPage(1)
          }}
          actions={(
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {total} sonuç
            </div>
          )}
        />

        <DataTable
          columns={columns}
          data={tools}
          loading={loading}
          emptyState={<EmptyState title="Araç yok" description="Yeni bir araç ekleyin." />}
          pagination={{
            page,
            pageSize: 20,
            total,
            onPageChange: setPage
          }}
        />

        <ToolGuideAssistant contextLabel="Araç Rehberi" storageKey="svontai_tool_guide_admin_tools" />
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Yeni Araç</DialogTitle>
            <DialogDescription>Araç bilgilerini girin ve kataloğa ekleyin.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Anahtar</Label>
              <Input value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Araç adı</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Kategori</Label>
              <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>İkon</Label>
              <Input value={form.icon} onChange={(e) => setForm({ ...form, icon: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Gerekli plan</Label>
              <Input value={form.required_plan} onChange={(e) => setForm({ ...form, required_plan: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Durum</Label>
              <Input value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label>Etiketler (virgülle ayırın)</Label>
              <Input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
            </div>
            <div className="sm:col-span-2 space-y-2">
              <Label>Açıklama</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div className="flex items-center justify-between rounded-xl border border-border/70 p-3">
              <div>
                <p className="text-sm font-medium">Public</p>
                <p className="text-xs text-muted-foreground">Müşterilere görünür</p>
              </div>
              <Switch checked={form.is_public} onCheckedChange={(value) => setForm({ ...form, is_public: value })} />
            </div>
            <div className="flex items-center justify-between rounded-xl border border-border/70 p-3">
              <div>
                <p className="text-sm font-medium">Coming soon</p>
                <p className="text-xs text-muted-foreground">Erken erişim etiketi</p>
              </div>
              <Switch checked={form.coming_soon} onCheckedChange={(value) => setForm({ ...form, coming_soon: value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>İptal</Button>
            <Button onClick={handleCreate}>
              <BadgeCheck className="h-4 w-4 mr-2" />
              Kaydet
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Araç Düzenle</DialogTitle>
            <DialogDescription>{activeTool?.name}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Anahtar</Label>
              <Input value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Araç adı</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Kategori</Label>
              <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>İkon</Label>
              <Input value={form.icon} onChange={(e) => setForm({ ...form, icon: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Gerekli plan</Label>
              <Input value={form.required_plan} onChange={(e) => setForm({ ...form, required_plan: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Durum</Label>
              <Input value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label>Etiketler (virgülle ayırın)</Label>
              <Input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
            </div>
            <div className="sm:col-span-2 space-y-2">
              <Label>Açıklama</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div className="flex items-center justify-between rounded-xl border border-border/70 p-3">
              <div>
                <p className="text-sm font-medium">Public</p>
                <p className="text-xs text-muted-foreground">Müşterilere görünür</p>
              </div>
              <Switch checked={form.is_public} onCheckedChange={(value) => setForm({ ...form, is_public: value })} />
            </div>
            <div className="flex items-center justify-between rounded-xl border border-border/70 p-3">
              <div>
                <p className="text-sm font-medium">Coming soon</p>
                <p className="text-xs text-muted-foreground">Erken erişim etiketi</p>
              </div>
              <Switch checked={form.coming_soon} onCheckedChange={(value) => setForm({ ...form, coming_soon: value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>İptal</Button>
            <Button onClick={handleUpdate}>
              <BadgeCheck className="h-4 w-4 mr-2" />
              Güncelle
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ContentContainer>
  )
}
