'use client'

import { useState, useEffect } from 'react'
import { 
  Users, 
  Search, 
  Plus, 
  MoreVertical,
  Shield,
  ShieldOff,
  Trash2,
  Edit,
  User,
  UserCheck,
  UserX,
  X,
  Check
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { EmptyState } from '@/components/shared/empty-state'

interface AdminUser {
  id: string
  email: string
  full_name: string
  is_admin: boolean
  is_active: boolean
  last_login: string | null
  created_at: string
  updated_at: string
}

interface UserListResponse {
  users: AdminUser[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export default function UsersPage() {
  const { toast } = useToast()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null)
  const [actionMenuId, setActionMenuId] = useState<string | null>(null)

  // Create user form
  const [createForm, setCreateForm] = useState({
    email: '',
    full_name: '',
    password: '',
    is_admin: false
  })

  // Edit user form
  const [editForm, setEditForm] = useState({
    email: '',
    full_name: '',
    is_admin: false,
    is_active: true
  })

  const fetchUsers = async () => {
    try {
      setLoading(true)
      const response = await adminApi.listUsers({ page, page_size: 20, search: search || undefined })
      const data: UserListResponse = response.data
      setUsers(data.users)
      setTotalPages(data.total_pages)
      setTotal(data.total)
    } catch (error) {
      console.error('Failed to fetch users:', error)
      toast({
        title: 'Hata',
        description: 'Kullanıcılar yüklenemedi',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
  }, [page, search])

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await adminApi.createUser(createForm)
      toast({
        title: 'Başarılı',
        description: 'Kullanıcı oluşturuldu'
      })
      setShowCreateModal(false)
      setCreateForm({ email: '', full_name: '', password: '', is_admin: false })
      fetchUsers()
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Kullanıcı oluşturulamadı',
        variant: 'destructive'
      })
    }
  }

  const handleEditUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedUser) return

    try {
      await adminApi.updateUser(selectedUser.id, editForm)
      toast({
        title: 'Başarılı',
        description: 'Kullanıcı güncellendi'
      })
      setShowEditModal(false)
      setSelectedUser(null)
      fetchUsers()
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Kullanıcı güncellenemedi',
        variant: 'destructive'
      })
    }
  }

  const handleDeleteUser = async (userId: string) => {
    if (!confirm('Bu kullanıcıyı silmek istediğinize emin misiniz?')) return

    try {
      await adminApi.deleteUser(userId)
      toast({
        title: 'Başarılı',
        description: 'Kullanıcı silindi'
      })
      fetchUsers()
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'Kullanıcı silinemedi',
        variant: 'destructive'
      })
    }
    setActionMenuId(null)
  }

  const handleToggleAdmin = async (user: AdminUser) => {
    try {
      await adminApi.updateUser(user.id, { is_admin: !user.is_admin })
      toast({
        title: 'Başarılı',
        description: user.is_admin ? 'Admin yetkisi kaldırıldı' : 'Admin yetkisi verildi'
      })
      fetchUsers()
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'İşlem başarısız',
        variant: 'destructive'
      })
    }
    setActionMenuId(null)
  }

  const handleToggleActive = async (user: AdminUser) => {
    try {
      await adminApi.updateUser(user.id, { is_active: !user.is_active })
      toast({
        title: 'Başarılı',
        description: user.is_active ? 'Kullanıcı devre dışı bırakıldı' : 'Kullanıcı aktif edildi'
      })
      fetchUsers()
    } catch (error: any) {
      toast({
        title: 'Hata',
        description: error.response?.data?.detail || 'İşlem başarısız',
        variant: 'destructive'
      })
    }
    setActionMenuId(null)
  }

  const openEditModal = (user: AdminUser) => {
    setSelectedUser(user)
    setEditForm({
      email: user.email,
      full_name: user.full_name,
      is_admin: user.is_admin,
      is_active: user.is_active
    })
    setShowEditModal(true)
    setActionMenuId(null)
  }

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Kullanıcılar"
          description={`Toplam ${total} kullanıcı`}
          icon={<Icon3DBadge icon={Users} from="from-cyan-500" to="to-blue-500" />}
          actions={(
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Yeni Kullanıcı
            </Button>
          )}
        />

      {/* Search */}
        <div className="relative rounded-2xl border border-border/70 bg-card/95 shadow-soft">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            placeholder="İsim veya e-posta ara..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 border-0 bg-transparent"
          />
        </div>

      {/* Users Table */}
      <div className="bg-card border border-border/70 rounded-2xl overflow-hidden shadow-soft gradient-border-animated">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border/70 bg-gradient-to-r from-muted/70 to-muted/30">
                <th className="text-left px-6 py-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Kullanıcı</th>
                <th className="text-left px-6 py-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Durum</th>
                <th className="text-left px-6 py-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Rol</th>
                <th className="text-left px-6 py-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Kayıt Tarihi</th>
                <th className="text-right px-6 py-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">İşlemler</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="text-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-2 border-transparent border-t-primary border-b-violet-500 mx-auto"></div>
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-10 px-6">
                    <EmptyState
                      icon={<Users className="h-6 w-6 text-primary" />}
                      title="Kullanıcı bulunamadı"
                      description="Arama kriterini değiştirin veya yeni bir kullanıcı ekleyin."
                    />
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.id} className="border-b border-border/70 hover:bg-primary/5 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <Icon3DBadge icon={User} size="sm" from="from-primary" to="to-violet-500" />
                        <div>
                          <p className="text-foreground font-medium">{user.full_name}</p>
                          <p className="text-sm text-muted-foreground">{user.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {user.is_active ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-green-500/20 text-green-400">
                          <UserCheck className="w-3 h-3" />
                          Aktif
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/20 text-red-400">
                          <UserX className="w-3 h-3" />
                          Pasif
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {user.is_admin ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary">
                          <Shield className="w-3 h-3" />
                          Admin
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-muted/60 text-muted-foreground">
                          Kullanıcı
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-muted-foreground text-sm">
                      {new Date(user.created_at).toLocaleDateString('tr-TR')}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="relative">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setActionMenuId(actionMenuId === user.id ? null : user.id)}
                          className="text-muted-foreground hover:text-foreground border border-border/60 bg-muted/30"
                        >
                          <MoreVertical className="w-4 h-4" />
                        </Button>
                        
                        {actionMenuId === user.id && (
                          <div className="absolute right-0 top-full mt-1 w-48 bg-card border border-border/70 rounded-xl shadow-xl z-10 py-1">
                            <button
                              onClick={() => openEditModal(user)}
                              className="w-full flex items-center gap-2 px-4 py-2 text-sm text-foreground hover:bg-muted/70 hover:text-foreground transition-colors"
                            >
                              <Edit className="w-4 h-4" />
                              Düzenle
                            </button>
                            <button
                              onClick={() => handleToggleAdmin(user)}
                              className="w-full flex items-center gap-2 px-4 py-2 text-sm text-foreground hover:bg-muted/70 hover:text-foreground transition-colors"
                            >
                              {user.is_admin ? (
                                <>
                                  <ShieldOff className="w-4 h-4" />
                                  Admin Kaldır
                                </>
                              ) : (
                                <>
                                  <Shield className="w-4 h-4" />
                                  Admin Yap
                                </>
                              )}
                            </button>
                            <button
                              onClick={() => handleToggleActive(user)}
                              className="w-full flex items-center gap-2 px-4 py-2 text-sm text-foreground hover:bg-muted/70 hover:text-foreground transition-colors"
                            >
                              {user.is_active ? (
                                <>
                                  <UserX className="w-4 h-4" />
                                  Devre Dışı Bırak
                                </>
                              ) : (
                                <>
                                  <UserCheck className="w-4 h-4" />
                                  Aktif Et
                                </>
                              )}
                            </button>
                            <hr className="my-1 border-border/70" />
                            <button
                              onClick={() => handleDeleteUser(user.id)}
                              className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                              Sil
                            </button>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-6 py-4 border-t border-border/70">
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

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border/70 rounded-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-6 border-b border-border/70">
              <h2 className="text-xl font-semibold text-foreground">Yeni Kullanıcı</h2>
              <button onClick={() => setShowCreateModal(false)} className="text-muted-foreground hover:text-foreground">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateUser} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">Ad Soyad</label>
                <Input
                  value={createForm.full_name}
                  onChange={(e) => setCreateForm(f => ({ ...f, full_name: e.target.value }))}
                  className="bg-muted border-border/70 text-foreground"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">E-posta</label>
                <Input
                  type="email"
                  value={createForm.email}
                  onChange={(e) => setCreateForm(f => ({ ...f, email: e.target.value }))}
                  className="bg-muted border-border/70 text-foreground"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">Şifre</label>
                <Input
                  type="password"
                  value={createForm.password}
                  onChange={(e) => setCreateForm(f => ({ ...f, password: e.target.value }))}
                  className="bg-muted border-border/70 text-foreground"
                  required
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_admin"
                  checked={createForm.is_admin}
                  onChange={(e) => setCreateForm(f => ({ ...f, is_admin: e.target.checked }))}
                  className="w-4 h-4 rounded border-border/70 bg-muted text-primary focus:ring-primary"
                />
                <label htmlFor="is_admin" className="text-sm text-muted-foreground">Admin yetkisi ver</label>
              </div>
              <div className="flex gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowCreateModal(false)} className="flex-1 border-border/70 text-muted-foreground">
                  İptal
                </Button>
                <Button type="submit" className="flex-1 bg-primary hover:bg-primary/90">
                  Oluştur
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {showEditModal && selectedUser && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border/70 rounded-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-6 border-b border-border/70">
              <h2 className="text-xl font-semibold text-foreground">Kullanıcıyı Düzenle</h2>
              <button onClick={() => setShowEditModal(false)} className="text-muted-foreground hover:text-foreground">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleEditUser} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">Ad Soyad</label>
                <Input
                  value={editForm.full_name}
                  onChange={(e) => setEditForm(f => ({ ...f, full_name: e.target.value }))}
                  className="bg-muted border-border/70 text-foreground"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground mb-2">E-posta</label>
                <Input
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditForm(f => ({ ...f, email: e.target.value }))}
                  className="bg-muted border-border/70 text-foreground"
                  required
                />
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="edit_is_admin"
                    checked={editForm.is_admin}
                    onChange={(e) => setEditForm(f => ({ ...f, is_admin: e.target.checked }))}
                    className="w-4 h-4 rounded border-border/70 bg-muted text-primary focus:ring-primary"
                  />
                  <label htmlFor="edit_is_admin" className="text-sm text-muted-foreground">Admin</label>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="edit_is_active"
                    checked={editForm.is_active}
                    onChange={(e) => setEditForm(f => ({ ...f, is_active: e.target.checked }))}
                    className="w-4 h-4 rounded border-border/70 bg-muted text-primary focus:ring-primary"
                  />
                  <label htmlFor="edit_is_active" className="text-sm text-muted-foreground">Aktif</label>
                </div>
              </div>
              <div className="flex gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowEditModal(false)} className="flex-1 border-border/70 text-muted-foreground">
                  İptal
                </Button>
                <Button type="submit" className="flex-1 bg-primary hover:bg-primary/90">
                  Kaydet
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
      </div>
    </ContentContainer>
  )
}
