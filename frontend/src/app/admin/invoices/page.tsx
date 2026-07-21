'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Eye, Plus, ReceiptText, Trash2 } from 'lucide-react'

import { adminApi } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { DataColumn, DataTable } from '@/components/shared/data-table'
import { EmptyState } from '@/components/shared/empty-state'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { IconButton } from '@/components/shared/icon-button'
import { PageHeader } from '@/components/shared/page-header'

type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'cancelled'

type InvoiceLine = {
  description: string
  quantity: string
  unit: string
  unit_price: string
  tax_rate: string
}

type Invoice = {
  id: string
  invoice_number: string
  status: InvoiceStatus
  issue_date: string
  due_date: string
  currency: string
  customer_name: string
  customer_email?: string | null
  total: string
  created_at: string
}

type Tenant = { id: string; name: string }

const statusLabels: Record<InvoiceStatus, string> = {
  draft: 'Taslak',
  sent: 'Gönderildi',
  paid: 'Ödendi',
  cancelled: 'İptal',
}

const formatDateInput = (value: Date) => [
  value.getFullYear(),
  String(value.getMonth() + 1).padStart(2, '0'),
  String(value.getDate()).padStart(2, '0'),
].join('-')

const today = () => formatDateInput(new Date())

const dateAfter = (days: number) => {
  const value = new Date()
  value.setDate(value.getDate() + days)
  return formatDateInput(value)
}

const emptyLine = (): InvoiceLine => ({
  description: '',
  quantity: '1',
  unit: 'adet',
  unit_price: '0',
  tax_rate: '20',
})

const emptyForm = () => ({
  tenant_id: '',
  issue_date: today(),
  due_date: dateAfter(7),
  currency: 'TRY',
  seller_name: 'SvontAI',
  seller_email: 'info@aparial.com',
  seller_phone: '',
  seller_address: '',
  seller_tax_office: '',
  seller_tax_number: '',
  customer_name: '',
  customer_email: '',
  customer_phone: '',
  customer_address: '',
  customer_tax_office: '',
  customer_tax_number: '',
  notes: '',
  items: [emptyLine()],
})

const money = (value: number, currency: string) => new Intl.NumberFormat('tr-TR', {
  style: 'currency',
  currency,
}).format(value)

export default function AdminInvoicesPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | ''>('')
  const [form, setForm] = useState(emptyForm)

  const invoicesQuery = useQuery<{ items: Invoice[]; total: number }>({
    queryKey: ['admin-invoices', search, statusFilter],
    queryFn: () => adminApi.listInvoices({
      search: search || undefined,
      status: statusFilter || undefined,
    }).then((response) => response.data),
  })
  const tenantsQuery = useQuery<{ tenants: Tenant[] }>({
    queryKey: ['admin-invoice-tenants'],
    queryFn: () => adminApi.listTenants({ page: 1, page_size: 100 }).then((response) => response.data),
  })

  const createMutation = useMutation({
    mutationFn: () => adminApi.createInvoice({
      ...form,
      tenant_id: form.tenant_id || null,
      seller_email: form.seller_email || null,
      customer_email: form.customer_email || null,
    }),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['admin-invoices'] })
      setDialogOpen(false)
      setForm(emptyForm())
      toast({ title: 'Proforma oluşturuldu' })
      router.push(`/admin/invoices/${response.data.id}`)
    },
    onError: () => toast({
      title: 'Proforma oluşturulamadı',
      description: 'Alanları kontrol edip tekrar deneyin.',
      variant: 'destructive',
    }),
  })

  const totals = useMemo(() => form.items.reduce((result, line) => {
    const subtotal = Math.max(0, Number(line.quantity) || 0) * Math.max(0, Number(line.unit_price) || 0)
    const tax = subtotal * Math.max(0, Number(line.tax_rate) || 0) / 100
    return { subtotal: result.subtotal + subtotal, tax: result.tax + tax, total: result.total + subtotal + tax }
  }, { subtotal: 0, tax: 0, total: 0 }), [form.items])

  const updateLine = (index: number, key: keyof InvoiceLine, value: string) => {
    setForm((current) => ({
      ...current,
      items: current.items.map((line, lineIndex) => lineIndex === index ? { ...line, [key]: value } : line),
    }))
  }

  const columns: DataColumn<Invoice>[] = [
    {
      key: 'invoice_number',
      header: 'Belge',
      render: (row) => (
        <div className="space-y-1">
          <p className="font-semibold">{row.invoice_number}</p>
          <p className="text-xs text-muted-foreground">{new Date(row.issue_date).toLocaleDateString('tr-TR')}</p>
        </div>
      ),
    },
    {
      key: 'customer',
      header: 'Müşteri',
      render: (row) => (
        <div className="space-y-1">
          <p className="font-medium">{row.customer_name}</p>
          <p className="text-xs text-muted-foreground">{row.customer_email || '-'}</p>
        </div>
      ),
    },
    {
      key: 'total',
      header: 'Toplam',
      render: (row) => <span className="font-semibold">{money(Number(row.total), row.currency)}</span>,
    },
    {
      key: 'status',
      header: 'Durum',
      render: (row) => (
        <Badge variant={row.status === 'paid' ? 'success' : row.status === 'cancelled' ? 'destructive' : row.status === 'sent' ? 'warning' : 'secondary'}>
          {statusLabels[row.status]}
        </Badge>
      ),
    },
    {
      key: 'actions',
      header: 'İşlem',
      render: (row) => (
        <IconButton label="Proformayı aç" onClick={() => router.push(`/admin/invoices/${row.id}`)}>
          <Eye className="h-4 w-4" />
        </IconButton>
      ),
    },
  ]

  const canCreate = Boolean(
    form.seller_name.trim()
    && form.customer_name.trim()
    && form.issue_date
    && form.due_date
    && form.items.length
    && form.items.every((line) => line.description.trim() && Number(line.quantity) > 0 && Number(line.unit_price) >= 0)
  )

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Proforma Faturalar"
          description="Manuel satışlar için fiyat ve tahsilat belgelerini oluşturun."
          icon={<Icon3DBadge icon={ReceiptText} from="from-cyan-500" to="to-emerald-500" />}
          actions={<Button onClick={() => setDialogOpen(true)}><Plus className="mr-2 h-4 w-4" />Yeni Proforma</Button>}
        />

        <div className="flex flex-col gap-3 sm:flex-row">
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Belge no veya müşteri ara..." className="sm:max-w-md" />
          <select
            className="h-10 rounded-md border border-input bg-background px-3 text-sm sm:w-48"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as InvoiceStatus | '')}
            aria-label="Proforma durumu"
          >
            <option value="">Tüm durumlar</option>
            {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </div>

        <DataTable
          columns={columns}
          data={invoicesQuery.data?.items || []}
          loading={invoicesQuery.isLoading}
          emptyState={<EmptyState icon={<ReceiptText className="h-6 w-6 text-primary" />} title="Henüz proforma oluşturulmadı" />}
        />
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[92vh] max-w-5xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Yeni Proforma Fatura</DialogTitle>
            <DialogDescription>Tutarlar sunucuda yeniden hesaplanır ve belge sonradan değiştirilemez.</DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            <section className="space-y-3">
              <h3 className="text-sm font-semibold">Belge bilgileri</h3>
              <div className="grid gap-3 sm:grid-cols-4">
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="invoice-tenant">Müşteri tenantı</Label>
                  <select
                    id="invoice-tenant"
                    className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                    value={form.tenant_id}
                    onChange={(event) => {
                      const tenant = tenantsQuery.data?.tenants?.find((item) => item.id === event.target.value)
                      setForm((current) => ({ ...current, tenant_id: event.target.value, customer_name: tenant?.name || current.customer_name }))
                    }}
                  >
                    <option value="">Tenant seçmeden oluştur</option>
                    {(tenantsQuery.data?.tenants || []).map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name}</option>)}
                  </select>
                </div>
                <div className="space-y-2"><Label htmlFor="issue-date">Düzenleme</Label><Input id="issue-date" type="date" value={form.issue_date} onChange={(event) => setForm({ ...form, issue_date: event.target.value })} /></div>
                <div className="space-y-2"><Label htmlFor="due-date">Son ödeme</Label><Input id="due-date" type="date" min={form.issue_date} value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} /></div>
              </div>
            </section>

            <section className="grid gap-5 lg:grid-cols-2">
              <div className="space-y-3">
                <h3 className="text-sm font-semibold">Düzenleyen</h3>
                <Input value={form.seller_name} onChange={(event) => setForm({ ...form, seller_name: event.target.value })} placeholder="İsim / unvan" />
                <div className="grid gap-3 sm:grid-cols-2"><Input type="email" value={form.seller_email} onChange={(event) => setForm({ ...form, seller_email: event.target.value })} placeholder="E-posta" /><Input value={form.seller_phone} onChange={(event) => setForm({ ...form, seller_phone: event.target.value })} placeholder="Telefon" /></div>
                <Textarea value={form.seller_address} onChange={(event) => setForm({ ...form, seller_address: event.target.value })} placeholder="Adres" rows={3} />
                <div className="grid gap-3 sm:grid-cols-2"><Input value={form.seller_tax_office} onChange={(event) => setForm({ ...form, seller_tax_office: event.target.value })} placeholder="Vergi dairesi" /><Input value={form.seller_tax_number} onChange={(event) => setForm({ ...form, seller_tax_number: event.target.value })} placeholder="VKN / TCKN" /></div>
              </div>
              <div className="space-y-3">
                <h3 className="text-sm font-semibold">Müşteri</h3>
                <Input value={form.customer_name} onChange={(event) => setForm({ ...form, customer_name: event.target.value })} placeholder="İsim / işletme" />
                <div className="grid gap-3 sm:grid-cols-2"><Input type="email" value={form.customer_email} onChange={(event) => setForm({ ...form, customer_email: event.target.value })} placeholder="E-posta" /><Input value={form.customer_phone} onChange={(event) => setForm({ ...form, customer_phone: event.target.value })} placeholder="Telefon" /></div>
                <Textarea value={form.customer_address} onChange={(event) => setForm({ ...form, customer_address: event.target.value })} placeholder="Adres" rows={3} />
                <div className="grid gap-3 sm:grid-cols-2"><Input value={form.customer_tax_office} onChange={(event) => setForm({ ...form, customer_tax_office: event.target.value })} placeholder="Vergi dairesi" /><Input value={form.customer_tax_number} onChange={(event) => setForm({ ...form, customer_tax_number: event.target.value })} placeholder="VKN / TCKN" /></div>
              </div>
            </section>

            <section className="space-y-3">
              <div className="flex items-center justify-between"><h3 className="text-sm font-semibold">Kalemler</h3><Button type="button" size="sm" variant="outline" onClick={() => setForm((current) => ({ ...current, items: [...current.items, emptyLine()] }))}><Plus className="mr-2 h-4 w-4" />Kalem ekle</Button></div>
              <div className="space-y-3">
                {form.items.map((line, index) => (
                  <div key={index} className="grid gap-3 border-b border-border/70 pb-3 sm:grid-cols-[minmax(180px,2fr)_80px_90px_120px_90px_40px]">
                    <Input value={line.description} onChange={(event) => updateLine(index, 'description', event.target.value)} placeholder="Hizmet açıklaması" />
                    <Input type="number" min="0.01" step="0.01" value={line.quantity} onChange={(event) => updateLine(index, 'quantity', event.target.value)} aria-label="Miktar" />
                    <Input value={line.unit} onChange={(event) => updateLine(index, 'unit', event.target.value)} aria-label="Birim" />
                    <Input type="number" min="0" step="0.01" value={line.unit_price} onChange={(event) => updateLine(index, 'unit_price', event.target.value)} aria-label="Birim fiyat" />
                    <Input type="number" min="0" max="100" step="0.01" value={line.tax_rate} onChange={(event) => updateLine(index, 'tax_rate', event.target.value)} aria-label="Vergi oranı" />
                    <IconButton label="Kalemi sil" variant="ghost" disabled={form.items.length === 1} onClick={() => setForm((current) => ({ ...current, items: current.items.filter((_, lineIndex) => lineIndex !== index) }))}><Trash2 className="h-4 w-4" /></IconButton>
                  </div>
                ))}
              </div>
              <div className="ml-auto grid max-w-sm grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <span className="text-muted-foreground">Ara toplam</span><span className="text-right">{money(totals.subtotal, form.currency)}</span>
                <span className="text-muted-foreground">Vergi</span><span className="text-right">{money(totals.tax, form.currency)}</span>
                <span className="font-semibold">Genel toplam</span><span className="text-right font-semibold">{money(totals.total, form.currency)}</span>
              </div>
            </section>

            <div className="space-y-2"><Label htmlFor="invoice-notes">Notlar</Label><Textarea id="invoice-notes" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} placeholder="Ödeme bilgisi veya açıklama" rows={3} /></div>
            <p className="text-xs text-amber-700">Bu belge proformadır; e-Fatura veya e-Arşiv fatura yerine geçmez.</p>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Vazgeç</Button>
            <Button onClick={() => createMutation.mutate()} disabled={!canCreate || createMutation.isPending}>{createMutation.isPending ? 'Oluşturuluyor...' : 'Proforma oluştur'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ContentContainer>
  )
}
