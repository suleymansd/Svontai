'use client'

import { useState, useEffect } from 'react'
import { 
  Building2, 
  Search, 
  MoreVertical,
  Trash2,
  Bot,
  MessageSquare,
  User,
  Calendar
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/lib/api'
import Link from 'next/link'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { EmptyState } from '@/components/shared/empty-state'

interface TenantWithOwner {
  id: string
  name: string
  slug: string
  created_at: string
  updated_at: string
  owner_email: string
  owner_name: string
  bots_count: number
  conversations_count: number
}

interface TenantListResponse {
  tenants: TenantWithOwner[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export default function TenantsPage() {
  const { toast } = useToast()
  const [tenants, setTenants] = useState<TenantWithOwner[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [actionMenuId, setActionMenuId] = useState<string | null>(null)

  const fetchTenants = async () => {
    try {
      setLoading(true)
      const response = await adminApi.listTenants({ page, page_size: 20, search: search || undefined })
      const data: TenantListResponse = response.data
      setTenants(data.tenants)
      setTotalPages(data.total_pages)
      setTotal(data.total)
    } catch (error) {
      console.error('Failed to fetch tenants:', error)
      toast({
        title: 'Hata',
        description: 'Tenantlar yüklenemedi',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTenants()
  }, [page, search])

  const handleDeleteTenant = async (tenantId: string, tenantName: string) => {
    if (!confirm(`"${tenantName}" tenant'ını silmek istediğinize emin misiniz? Bu işlem tüm botları ve konuşmaları da silecektir.`)) return

    try {
      await adminApi.deleteTenant(tenantId)
      toast({
        title: 'Başarılı',
        description: 'Tenant silindi'
      })
      fetchTenants()
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Tenant silinemedi',
        variant: 'destructive'
      })
    }
    setActionMenuId(null)
  }

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Tenantlar"
          description={`Toplam ${total} tenant (işletme)`}
          icon={<Icon3DBadge icon={Building2} from="from-amber-500" to="to-orange-500" />}
        />

        <div className="relative rounded-2xl border border-border/70 bg-card/95 shadow-soft">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            placeholder="Tenant adı veya sahip e-postası ara..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 border-0 bg-transparent"
          />
        </div>

      {/* Tenants Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-card border border-border/70 rounded-2xl p-6 animate-pulse shadow-soft">
              <div className="h-6 w-32 bg-muted rounded mb-4"></div>
              <div className="h-4 w-48 bg-muted rounded mb-2"></div>
              <div className="h-4 w-24 bg-muted rounded"></div>
            </div>
          ))
        ) : tenants.length === 0 ? (
          <div className="col-span-full">
            <EmptyState
              icon={<Building2 className="h-6 w-6 text-primary" />}
              title="Tenant bulunamadı"
              description="Arama kriterini değiştirin veya yeni tenant oluşturun."
            />
          </div>
        ) : (
          tenants.map((tenant) => (
            <div key={tenant.id} className="bg-card border border-border/70 rounded-2xl p-6 hover:border-primary/30 transition-all duration-300 group relative shadow-soft gradient-border-animated">
              {/* Actions */}
              <div className="absolute top-4 right-4">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setActionMenuId(actionMenuId === tenant.id ? null : tenant.id)}
                  className="text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-opacity border border-border/60 bg-muted/30"
                >
                  <MoreVertical className="w-4 h-4" />
                </Button>
                
                {actionMenuId === tenant.id && (
                  <div className="absolute right-0 top-full mt-1 w-40 bg-card border border-border/70 rounded-xl shadow-xl z-10 py-1">
                    <button
                      onClick={() => handleDeleteTenant(tenant.id, tenant.name)}
                      className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                      Sil
                    </button>
                  </div>
                )}
              </div>

              {/* Header */}
              <div className="flex items-center gap-3 mb-4">
                <Icon3DBadge icon={Building2} from="from-amber-500" to="to-orange-500" />
                <div>
                  <h3 className="text-lg font-semibold text-foreground">{tenant.name}</h3>
                  <p className="text-sm text-muted-foreground">/{tenant.slug}</p>
                </div>
              </div>

              {/* Owner */}
              <div className="flex items-center gap-2 mb-4 p-3 bg-muted/50 rounded-xl">
                <User className="w-4 h-4 text-muted-foreground" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-foreground truncate">{tenant.owner_name}</p>
                  <p className="text-xs text-muted-foreground truncate">{tenant.owner_email}</p>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="flex items-center gap-2 p-2 bg-blue-500/10 rounded-lg">
                  <Bot className="w-4 h-4 text-blue-400" />
                  <span className="text-sm text-blue-400">{tenant.bots_count} Bot</span>
                </div>
                <div className="flex items-center gap-2 p-2 bg-green-500/10 rounded-lg">
                  <MessageSquare className="w-4 h-4 text-green-400" />
                  <span className="text-sm text-green-400">{tenant.conversations_count} Konuşma</span>
                </div>
              </div>

              {/* Date */}
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Calendar className="w-3 h-3" />
                <span>Oluşturulma: {new Date(tenant.created_at).toLocaleDateString('tr-TR')}</span>
              </div>
              <div className="mt-4 flex justify-end">
                <Link href={`/admin/tenants/${tenant.id}`}>
                  <Button variant="outline" size="sm">
                    Detayları Gör
                  </Button>
                </Link>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Sayfa {page} / {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="border-border/70 text-muted-foreground hover:text-foreground"
            >
              Önceki
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="border-border/70 text-muted-foreground hover:text-foreground"
            >
              Sonraki
            </Button>
          </div>
        </div>
      )}
      </div>
    </ContentContainer>
  )
}
