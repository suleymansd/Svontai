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
  UserCheck,
  UserX,
  X,
  Check
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { adminApi } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'

interface User {
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
  users: User[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export default function UsersPage() {
  const { toast } = useToast()
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
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

  const handleToggleAdmin = async (user: User) => {
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

  const handleToggleActive = async (user: User) => {
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

  const openEditModal = (user: User) => {
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Kullanıcılar</h1>
          <p className="text-slate-400 mt-1">Toplam {total} kullanıcı</p>
        </div>
        <Button 
          onClick={() => setShowCreateModal(true)}
          className="bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700"
        >
          <Plus className="w-4 h-4 mr-2" />
          Yeni Kullanıcı
        </Button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
        <Input
          placeholder="İsim veya e-posta ara..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 bg-slate-900 border-slate-800 text-white placeholder:text-slate-500"
        />
      </div>

      {/* Users Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-800">
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Kullanıcı</th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Durum</th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Rol</th>
                <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Kayıt Tarihi</th>
                <th className="text-right px-6 py-4 text-sm font-medium text-slate-400">İşlemler</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="text-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-500 mx-auto"></div>
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-slate-400">
                    Kullanıcı bulunamadı
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.id} className="border-b border-slate-800 hover:bg-slate-800/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center text-white font-semibold">
                          {user.full_name?.charAt(0)?.toUpperCase() || 'U'}
                        </div>
                        <div>
                          <p className="text-white font-medium">{user.full_name}</p>
                          <p className="text-sm text-slate-400">{user.email}</p>
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
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-violet-500/20 text-violet-400">
                          <Shield className="w-3 h-3" />
                          Admin
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-500/20 text-slate-400">
                          Kullanıcı
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-400 text-sm">
                      {new Date(user.created_at).toLocaleDateString('tr-TR')}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="relative">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setActionMenuId(actionMenuId === user.id ? null : user.id)}
                          className="text-slate-400 hover:text-white"
                        >
                          <MoreVertical className="w-4 h-4" />
                        </Button>
                        
                        {actionMenuId === user.id && (
                          <div className="absolute right-0 top-full mt-1 w-48 bg-slate-800 border border-slate-700 rounded-xl shadow-xl z-10 py-1">
                            <button
                              onClick={() => openEditModal(user)}
                              className="w-full flex items-center gap-2 px-4 py-2 text-sm text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
                            >
                              <Edit className="w-4 h-4" />
                              Düzenle
                            </button>
                            <button
                              onClick={() => handleToggleAdmin(user)}
                              className="w-full flex items-center gap-2 px-4 py-2 text-sm text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
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
                              className="w-full flex items-center gap-2 px-4 py-2 text-sm text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
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
                            <hr className="my-1 border-slate-700" />
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
          <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800">
            <p className="text-sm text-slate-400">
              Sayfa {page} / {totalPages}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="border-slate-700 text-slate-400 hover:text-white"
              >
                Önceki
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="border-slate-700 text-slate-400 hover:text-white"
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
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-6 border-b border-slate-800">
              <h2 className="text-xl font-semibold text-white">Yeni Kullanıcı</h2>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateUser} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Ad Soyad</label>
                <Input
                  value={createForm.full_name}
                  onChange={(e) => setCreateForm(f => ({ ...f, full_name: e.target.value }))}
                  className="bg-slate-800 border-slate-700 text-white"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">E-posta</label>
                <Input
                  type="email"
                  value={createForm.email}
                  onChange={(e) => setCreateForm(f => ({ ...f, email: e.target.value }))}
                  className="bg-slate-800 border-slate-700 text-white"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Şifre</label>
                <Input
                  type="password"
                  value={createForm.password}
                  onChange={(e) => setCreateForm(f => ({ ...f, password: e.target.value }))}
                  className="bg-slate-800 border-slate-700 text-white"
                  required
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_admin"
                  checked={createForm.is_admin}
                  onChange={(e) => setCreateForm(f => ({ ...f, is_admin: e.target.checked }))}
                  className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-violet-600 focus:ring-violet-500"
                />
                <label htmlFor="is_admin" className="text-sm text-slate-400">Admin yetkisi ver</label>
              </div>
              <div className="flex gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowCreateModal(false)} className="flex-1 border-slate-700 text-slate-400">
                  İptal
                </Button>
                <Button type="submit" className="flex-1 bg-gradient-to-r from-violet-600 to-purple-600">
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
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-6 border-b border-slate-800">
              <h2 className="text-xl font-semibold text-white">Kullanıcıyı Düzenle</h2>
              <button onClick={() => setShowEditModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleEditUser} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Ad Soyad</label>
                <Input
                  value={editForm.full_name}
                  onChange={(e) => setEditForm(f => ({ ...f, full_name: e.target.value }))}
                  className="bg-slate-800 border-slate-700 text-white"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">E-posta</label>
                <Input
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditForm(f => ({ ...f, email: e.target.value }))}
                  className="bg-slate-800 border-slate-700 text-white"
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
                    className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-violet-600 focus:ring-violet-500"
                  />
                  <label htmlFor="edit_is_admin" className="text-sm text-slate-400">Admin</label>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="edit_is_active"
                    checked={editForm.is_active}
                    onChange={(e) => setEditForm(f => ({ ...f, is_active: e.target.checked }))}
                    className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-violet-600 focus:ring-violet-500"
                  />
                  <label htmlFor="edit_is_active" className="text-sm text-slate-400">Aktif</label>
                </div>
              </div>
              <div className="flex gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowEditModal(false)} className="flex-1 border-slate-700 text-slate-400">
                  İptal
                </Button>
                <Button type="submit" className="flex-1 bg-gradient-to-r from-violet-600 to-purple-600">
                  Kaydet
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

