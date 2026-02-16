'use client'

import { useEffect, useMemo, useState } from 'react'
import { Plus, Pencil, Trash2, BadgeCheck, Sparkles, Zap, Crown, Building2, type LucideIcon } from 'lucide-react'
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
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'

interface Plan {
  id: string
  name: string
  display_name: string
  description?: string | null
  plan_type: string
  price_monthly: number
  price_yearly: number
  currency: string
  message_limit: number
  bot_limit: number
  knowledge_items_limit: number
  feature_flags: Record<string, unknown>
  trial_days: number
  is_active: boolean
  is_public: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

interface PlanListResponse {
  items: Plan[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

const emptyPlanForm = {
  name: '',
  display_name: '',
  description: '',
  plan_type: 'starter',
  price_monthly: 0,
  price_yearly: 0,
  currency: 'TRY',
  message_limit: 1000,
  bot_limit: 1,
  knowledge_items_limit: 100,
  trial_days: 14,
  is_active: true,
  is_public: true,
  sort_order: 0,
  feature_flags: '{}'
}

const planTypeVisual: Record<string, { icon: LucideIcon; from: string; to: string }> = {
  free: { icon: Sparkles, from: 'from-slate-500', to: 'to-slate-700' },
  starter: { icon: Zap, from: 'from-cyan-500', to: 'to-blue-500' },
  pro: { icon: Crown, from: 'from-violet-500', to: 'to-fuchsia-500' },
  business: { icon: Building2, from: 'from-amber-500', to: 'to-orange-500' },
}

export default function PlansPage() {
  const { toast } = useToast()
  const [plans, setPlans] = useState<Plan[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)

  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [activePlan, setActivePlan] = useState<Plan | null>(null)
  const [form, setForm] = useState({ ...emptyPlanForm })

  const fetchPlans = async () => {
    try {
      setLoading(true)
      const response = await adminApi.listPlans({ page, page_size: 20, search: search || undefined })
      const data: PlanListResponse = response.data
      setPlans(data.items)
      setTotal(data.total)
    } catch (error) {
      toast({
        title: 'Hata',
        description: 'Planlar yüklenemedi',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPlans()
  }, [page, search])

  const columns: DataColumn<Plan>[] = useMemo(() => [
    {
      key: 'name',
      header: 'Plan',
      render: (row) => (
        <div className="flex items-center gap-3">
          <Icon3DBadge
            icon={(planTypeVisual[row.plan_type]?.icon || BadgeCheck)}
            size="sm"
            from={planTypeVisual[row.plan_type]?.from || 'from-primary'}
            to={planTypeVisual[row.plan_type]?.to || 'to-violet-500'}
          />
          <div className="space-y-1">
            <p className="font-semibold">{row.display_name}</p>
            <p className="text-xs text-muted-foreground">{row.name} • {row.plan_type}</p>
          </div>
        </div>
      )
    },
    {
      key: 'price',
      header: 'Fiyat',
      render: (row) => (
        <div className="space-y-1">
          <p className="text-sm">{row.price_monthly} {row.currency} / ay</p>
          <p className="text-xs text-muted-foreground">{row.price_yearly} {row.currency} / yıl</p>
        </div>
      )
    },
    {
      key: 'limits',
      header: 'Limitler',
      render: (row) => (
        <div className="text-sm text-muted-foreground">
          {row.message_limit} mesaj • {row.bot_limit} bot
        </div>
      )
    },
    {
      key: 'status',
      header: 'Durum',
      render: (row) => (
        <Badge variant={row.is_active ? 'default' : 'secondary'}>
          {row.is_active ? 'Aktif' : 'Pasif'}
        </Badge>
      )
    },
    {
      key: 'actions',
      header: 'İşlemler',
      render: (row) => (
        <div className="flex items-center gap-2">
          <IconButton
            label="Planı düzenle"
            onClick={() => openEdit(row)}
          >
            <Pencil className="h-4 w-4" />
          </IconButton>
          <IconButton
            label="Planı sil"
            variant="destructive"
            onClick={() => handleDelete(row)}
          >
            <Trash2 className="h-4 w-4" />
          </IconButton>
        </div>
      )
    }
  ], [])

  const openCreate = () => {
    setForm({ ...emptyPlanForm })
    setCreateOpen(true)
  }

  const openEdit = (plan: Plan) => {
    setActivePlan(plan)
    setForm({
      name: plan.name,
      display_name: plan.display_name,
      description: plan.description || '',
      plan_type: plan.plan_type,
      price_monthly: plan.price_monthly,
      price_yearly: plan.price_yearly,
      currency: plan.currency,
      message_limit: plan.message_limit,
      bot_limit: plan.bot_limit,
      knowledge_items_limit: plan.knowledge_items_limit,
      trial_days: plan.trial_days,
      is_active: plan.is_active,
      is_public: plan.is_public,
      sort_order: plan.sort_order,
      feature_flags: JSON.stringify(plan.feature_flags || {}, null, 2)
    })
    setEditOpen(true)
  }

  const parseFeatureFlags = () => {
    try {
      const parsed = JSON.parse(form.feature_flags)
      if (typeof parsed !== 'object' || parsed === null) {
        throw new Error('invalid')
      }
      return parsed
    } catch (error) {
      toast({
        title: 'Hata',
        description: 'Feature flags JSON formatı geçersiz',
        variant: 'destructive'
      })
      return null
    }
  }

  const handleCreate = async () => {
    const featureFlags = parseFeatureFlags()
    if (!featureFlags) return

    try {
      await adminApi.createPlan({
        name: form.name,
        display_name: form.display_name,
        description: form.description || undefined,
        plan_type: form.plan_type,
        price_monthly: Number(form.price_monthly),
        price_yearly: Number(form.price_yearly),
        currency: form.currency,
        message_limit: Number(form.message_limit),
        bot_limit: Number(form.bot_limit),
        knowledge_items_limit: Number(form.knowledge_items_limit),
        feature_flags: featureFlags,
        trial_days: Number(form.trial_days),
        is_active: form.is_active,
        is_public: form.is_public,
        sort_order: Number(form.sort_order)
      })
      toast({ title: 'Başarılı', description: 'Plan oluşturuldu' })
      setCreateOpen(false)
      fetchPlans()
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Plan oluşturulamadı',
        variant: 'destructive'
      })
    }
  }

  const handleUpdate = async () => {
    if (!activePlan) return
    const featureFlags = parseFeatureFlags()
    if (!featureFlags) return

    try {
      await adminApi.updatePlan(activePlan.id, {
        name: form.name,
        display_name: form.display_name,
        description: form.description || undefined,
        plan_type: form.plan_type,
        price_monthly: Number(form.price_monthly),
        price_yearly: Number(form.price_yearly),
        currency: form.currency,
        message_limit: Number(form.message_limit),
        bot_limit: Number(form.bot_limit),
        knowledge_items_limit: Number(form.knowledge_items_limit),
        feature_flags: featureFlags,
        trial_days: Number(form.trial_days),
        is_active: form.is_active,
        is_public: form.is_public,
        sort_order: Number(form.sort_order)
      })
      toast({ title: 'Başarılı', description: 'Plan güncellendi' })
      setEditOpen(false)
      setActivePlan(null)
      fetchPlans()
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Plan güncellenemedi',
        variant: 'destructive'
      })
    }
  }

  const handleDelete = async (plan: Plan) => {
    if (!confirm(`${plan.display_name} planını silmek istediğinize emin misiniz?`)) return

    try {
      await adminApi.deletePlan(plan.id)
      toast({ title: 'Başarılı', description: 'Plan silindi' })
      fetchPlans()
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Plan silinemedi',
        variant: 'destructive'
      })
    }
  }

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Planlar"
          description={`Toplam ${total} plan`}
          icon={<Icon3DBadge icon={BadgeCheck} from="from-violet-500" to="to-fuchsia-500" />}
          actions={(
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Yeni Plan
            </Button>
          )}
        />

        <FilterBar
          searchPlaceholder="Plan ara..."
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
          data={plans}
          loading={loading}
          emptyState={<EmptyState title="Plan yok" description="Yeni bir plan ekleyin." />}
          pagination={{
            page,
            pageSize: 20,
            total,
            onPageChange: setPage
          }}
        />
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Yeni Plan</DialogTitle>
            <DialogDescription>Plan bilgilerini girin ve yayınlayın.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Plan kodu</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Plan adı</Label>
              <Input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Plan tipi</Label>
              <Input value={form.plan_type} onChange={(e) => setForm({ ...form, plan_type: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Para birimi</Label>
              <Input value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Aylık fiyat</Label>
              <Input type="number" value={form.price_monthly} onChange={(e) => setForm({ ...form, price_monthly: Number(e.target.value) })} />
            </div>
            <div className="space-y-2">
              <Label>Yıllık fiyat</Label>
              <Input type="number" value={form.price_yearly} onChange={(e) => setForm({ ...form, price_yearly: Number(e.target.value) })} />
            </div>
            <div className="space-y-2">
              <Label>Mesaj limiti</Label>
              <Input type="number" value={form.message_limit} onChange={(e) => setForm({ ...form, message_limit: Number(e.target.value) })} />
            </div>
            <div className="space-y-2">
              <Label>Bot limiti</Label>
              <Input type="number" value={form.bot_limit} onChange={(e) => setForm({ ...form, bot_limit: Number(e.target.value) })} />
            </div>
            <div className="space-y-2">
              <Label>Bilgi tabanı limiti</Label>
              <Input type="number" value={form.knowledge_items_limit} onChange={(e) => setForm({ ...form, knowledge_items_limit: Number(e.target.value) })} />
            </div>
            <div className="space-y-2">
              <Label>Deneme günü</Label>
              <Input type="number" value={form.trial_days} onChange={(e) => setForm({ ...form, trial_days: Number(e.target.value) })} />
            </div>
            <div className="space-y-2">
              <Label>Sıralama</Label>
              <Input type="number" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })} />
            </div>
            <div className="flex items-center justify-between rounded-xl border border-border/70 p-3">
              <div>
                <p className="text-sm font-medium">Aktif</p>
                <p className="text-xs text-muted-foreground">Plan satın alınabilir</p>
              </div>
              <Switch checked={form.is_active} onCheckedChange={(value) => setForm({ ...form, is_active: value })} />
            </div>
            <div className="flex items-center justify-between rounded-xl border border-border/70 p-3">
              <div>
                <p className="text-sm font-medium">Public</p>
                <p className="text-xs text-muted-foreground">Müşterilere görünür</p>
              </div>
              <Switch checked={form.is_public} onCheckedChange={(value) => setForm({ ...form, is_public: value })} />
            </div>
            <div className="sm:col-span-2 space-y-2">
              <Label>Açıklama</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div className="sm:col-span-2 space-y-2">
              <Label>Feature flags (JSON)</Label>
              <Textarea rows={6} value={form.feature_flags} onChange={(e) => setForm({ ...form, feature_flags: e.target.value })} />
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
            <DialogTitle>Planı Düzenle</DialogTitle>
            <DialogDescription>{activePlan?.display_name}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Plan kodu</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Plan adı</Label>
              <Input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Plan tipi</Label>
              <Input value={form.plan_type} onChange={(e) => setForm({ ...form, plan_type: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Para birimi</Label>
              <Input value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Aylık fiyat</Label>
              <Input type="number" value={form.price_monthly} onChange={(e) => setForm({ ...form, price_monthly: Number(e.target.value) })} />
            </div>
            <div className="space-y-2">
              <Label>Yıllık fiyat</Label>
              <Input type="number" value={form.price_yearly} onChange={(e) => setForm({ ...form, price_yearly: Number(e.target.value) })} />
            </div>
            <div className="space-y-2">
              <Label>Mesaj limiti</Label>
              <Input type="number" value={form.message_limit} onChange={(e) => setForm({ ...form, message_limit: Number(e.target.value) })} />
            </div>
            <div className="space-y-2">
              <Label>Bot limiti</Label>
              <Input type="number" value={form.bot_limit} onChange={(e) => setForm({ ...form, bot_limit: Number(e.target.value) })} />
            </div>
            <div className="space-y-2">
              <Label>Bilgi tabanı limiti</Label>
              <Input type="number" value={form.knowledge_items_limit} onChange={(e) => setForm({ ...form, knowledge_items_limit: Number(e.target.value) })} />
            </div>
            <div className="space-y-2">
              <Label>Deneme günü</Label>
              <Input type="number" value={form.trial_days} onChange={(e) => setForm({ ...form, trial_days: Number(e.target.value) })} />
            </div>
            <div className="space-y-2">
              <Label>Sıralama</Label>
              <Input type="number" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })} />
            </div>
            <div className="flex items-center justify-between rounded-xl border border-border/70 p-3">
              <div>
                <p className="text-sm font-medium">Aktif</p>
                <p className="text-xs text-muted-foreground">Plan satın alınabilir</p>
              </div>
              <Switch checked={form.is_active} onCheckedChange={(value) => setForm({ ...form, is_active: value })} />
            </div>
            <div className="flex items-center justify-between rounded-xl border border-border/70 p-3">
              <div>
                <p className="text-sm font-medium">Public</p>
                <p className="text-xs text-muted-foreground">Müşterilere görünür</p>
              </div>
              <Switch checked={form.is_public} onCheckedChange={(value) => setForm({ ...form, is_public: value })} />
            </div>
            <div className="sm:col-span-2 space-y-2">
              <Label>Açıklama</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div className="sm:col-span-2 space-y-2">
              <Label>Feature flags (JSON)</Label>
              <Textarea rows={6} value={form.feature_flags} onChange={(e) => setForm({ ...form, feature_flags: e.target.value })} />
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
