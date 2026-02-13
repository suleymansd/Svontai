'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Users,
  Download,
  Mail,
  Phone,
  MoreHorizontal,
  UserPlus,
  Filter,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { leadApi } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { KPIStat } from '@/components/shared/kpi-stat'
import { FilterBar } from '@/components/shared/filter-bar'
import { DataTable, DataColumn } from '@/components/shared/data-table'
import { EmptyState } from '@/components/shared/empty-state'

export default function LeadsPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    notes: '',
    source: 'manual',
  })

  const { data: leads, isLoading } = useQuery({
    queryKey: ['leads'],
    queryFn: () => leadApi.list({ limit: 100 }).then((res) => res.data),
  })

  const createMutation = useMutation({
    mutationFn: (data: typeof formData) => leadApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      setIsCreateOpen(false)
      setFormData({ name: '', email: '', phone: '', notes: '', source: 'manual' })
      toast({
        title: 'Lead eklendi',
        description: 'Yeni lead başarıyla oluşturuldu.',
      })
    },
    onError: () => {
      toast({
        title: 'Hata',
        description: 'Lead eklenirken bir hata oluştu.',
        variant: 'destructive',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => leadApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
      toast({
        title: 'Lead silindi',
        description: 'Lead başarıyla silindi.',
      })
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name) return
    createMutation.mutate(formData)
  }

  const handleExport = () => {
    if (!leads || leads.length === 0) {
      toast({
        title: 'Dışa aktarılacak veri yok',
        description: 'Henüz lead bulunmuyor.',
        variant: 'destructive',
      })
      return
    }

    const csv = [
      ['İsim', 'E-posta', 'Telefon', 'Kaynak', 'Durum', 'Not', 'Tarih'].join(','),
      ...leads.map((lead: any) =>
        [
          lead.name || '',
          lead.email || '',
          lead.phone || '',
          lead.source || '',
          lead.status || '',
          (lead.notes || '').replace(/,/g, ';'),
          formatDate(lead.created_at),
        ].join(',')
      ),
    ].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `leads-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)

    toast({
      title: 'Dışa aktarıldı',
      description: 'Leadler CSV olarak indirildi.',
    })
  }

  const filteredLeads = leads?.filter((lead: any) => {
    if (!searchTerm) return true
    const search = searchTerm.toLowerCase()
    return (
      lead.name?.toLowerCase().includes(search) ||
      lead.email?.toLowerCase().includes(search) ||
      lead.phone?.includes(search)
    )
  })

  const totalLeads = leads?.length || 0
  const newLeads = leads?.filter((l: any) => l.status === 'new').length || 0
  const contactedLeads = leads?.filter((l: any) => l.status === 'contacted').length || 0

  const columns: DataColumn<any>[] = [
    {
      key: 'name',
      header: 'Lead',
      render: (lead) => (
        <div className="space-y-1">
          <p className="font-medium">{lead.name || 'İsimsiz'}</p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {lead.email && (
              <span className="inline-flex items-center gap-1">
                <Mail className="h-3.5 w-3.5" />
                {lead.email}
              </span>
            )}
            {lead.phone && (
              <span className="inline-flex items-center gap-1">
                <Phone className="h-3.5 w-3.5" />
                {lead.phone}
              </span>
            )}
          </div>
        </div>
      ),
    },
    {
      key: 'source',
      header: 'Kaynak',
      render: (lead) => <Badge variant="outline">{lead.source || 'manual'}</Badge>,
    },
    {
      key: 'status',
      header: 'Durum',
      render: (lead) => (
        <Badge variant={lead.status === 'qualified' ? 'success' : 'secondary'}>
          {lead.status || 'new'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Tarih',
      render: (lead) => (
        <span className="text-sm text-muted-foreground">{formatDate(lead.created_at)}</span>
      ),
    },
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (lead) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => deleteMutation.mutate(lead.id)}>Sil</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ]

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Leadler"
          description="Potansiyel müşterilerinizi yönetin ve takip edin."
          actions={
            <div className="flex gap-2">
              <Button variant="outline" onClick={handleExport}>
                <Download className="w-4 h-4 mr-2" />
                Dışa Aktar
              </Button>
              <Button onClick={() => setIsCreateOpen(true)}>
                <UserPlus className="w-4 h-4 mr-2" />
                Lead Ekle
              </Button>
            </div>
          }
        />

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KPIStat label="Toplam Lead" value={totalLeads} icon={<Users className="h-5 w-5" />} />
          <KPIStat label="Yeni" value={newLeads} icon={<Users className="h-5 w-5" />} />
          <KPIStat label="İletişim Kuruldu" value={contactedLeads} icon={<Users className="h-5 w-5" />} />
          <KPIStat label="Ortalama Yanıt" value="2.5h" icon={<Users className="h-5 w-5" />} />
        </div>

        <FilterBar
          searchPlaceholder="Lead ara..."
          onSearchChange={setSearchTerm}
          actions={
            <Button variant="outline" size="sm">
              <Filter className="mr-2 h-4 w-4" />
              Filtre
            </Button>
          }
        />

        <DataTable
          columns={columns}
          data={filteredLeads || []}
          loading={isLoading}
          emptyState={
            <EmptyState
              icon={<Users className="h-8 w-8 text-primary" />}
              title="Henüz lead yok"
              description="İlk lead’inizi ekleyerek müşteri takibini başlatın."
              action={
                <Button onClick={() => setIsCreateOpen(true)}>
                  <UserPlus className="w-4 h-4 mr-2" />
                  Lead Ekle
                </Button>
              }
            />
          }
        />
      </div>

      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent className="sm:max-w-[520px]">
          <DialogHeader>
            <DialogTitle>Yeni Lead Ekle</DialogTitle>
            <DialogDescription>Müşteri bilgilerini girerek lead oluşturun.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid gap-3">
              <div className="space-y-2">
                <Label htmlFor="name">İsim</Label>
                <Input
                  id="name"
                  placeholder="Müşteri adı"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">E-posta</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="email@ornek.com"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">Telefon</Label>
                <Input
                  id="phone"
                  placeholder="+90 555 555 55 55"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="notes">Not</Label>
                <Textarea
                  id="notes"
                  placeholder="Lead hakkında notlar"
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                />
              </div>
            </div>
            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>
                İptal
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Kaydediliyor...' : 'Lead Ekle'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </ContentContainer>
  )
}
