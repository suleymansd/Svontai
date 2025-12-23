'use client'

import { useState, useEffect } from 'react'
import { 
  Users, 
  Building2, 
  Bot, 
  MessageSquare, 
  TrendingUp, 
  UserPlus,
  Activity,
  Zap,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react'
import { adminApi } from '@/lib/api'

interface AdminStats {
  total_users: number
  active_users: number
  total_tenants: number
  total_bots: number
  active_bots: number
  total_conversations: number
  total_messages: number
  total_leads: number
  new_users_today: number
  new_users_week: number
  messages_today: number
  messages_week: number
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await adminApi.getStats()
        setStats(response.data)
      } catch (error) {
        console.error('Failed to fetch stats:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-violet-500"></div>
      </div>
    )
  }

  const statCards = [
    {
      title: 'Toplam Kullanıcı',
      value: stats?.total_users || 0,
      icon: Users,
      change: stats?.new_users_week || 0,
      changeLabel: 'Bu hafta',
      color: 'from-blue-600 to-cyan-600',
      bgColor: 'bg-blue-500/10',
      textColor: 'text-blue-400'
    },
    {
      title: 'Aktif Kullanıcı',
      value: stats?.active_users || 0,
      icon: UserPlus,
      change: stats?.new_users_today || 0,
      changeLabel: 'Bugün',
      color: 'from-green-600 to-emerald-600',
      bgColor: 'bg-green-500/10',
      textColor: 'text-green-400'
    },
    {
      title: 'Toplam Tenant',
      value: stats?.total_tenants || 0,
      icon: Building2,
      change: null,
      changeLabel: null,
      color: 'from-violet-600 to-purple-600',
      bgColor: 'bg-violet-500/10',
      textColor: 'text-violet-400'
    },
    {
      title: 'Toplam Bot',
      value: stats?.total_bots || 0,
      icon: Bot,
      change: stats?.active_bots,
      changeLabel: 'Aktif',
      color: 'from-orange-600 to-amber-600',
      bgColor: 'bg-orange-500/10',
      textColor: 'text-orange-400'
    },
    {
      title: 'Konuşmalar',
      value: stats?.total_conversations || 0,
      icon: MessageSquare,
      change: null,
      changeLabel: null,
      color: 'from-pink-600 to-rose-600',
      bgColor: 'bg-pink-500/10',
      textColor: 'text-pink-400'
    },
    {
      title: 'Toplam Mesaj',
      value: stats?.total_messages || 0,
      icon: Zap,
      change: stats?.messages_today,
      changeLabel: 'Bugün',
      color: 'from-cyan-600 to-teal-600',
      bgColor: 'bg-cyan-500/10',
      textColor: 'text-cyan-400'
    },
    {
      title: 'Lead\'ler',
      value: stats?.total_leads || 0,
      icon: TrendingUp,
      change: null,
      changeLabel: null,
      color: 'from-indigo-600 to-blue-600',
      bgColor: 'bg-indigo-500/10',
      textColor: 'text-indigo-400'
    },
    {
      title: 'Mesaj (Hafta)',
      value: stats?.messages_week || 0,
      icon: Activity,
      change: stats?.messages_today,
      changeLabel: 'Bugün',
      color: 'from-fuchsia-600 to-pink-600',
      bgColor: 'bg-fuchsia-500/10',
      textColor: 'text-fuchsia-400'
    },
  ]

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white">Admin Dashboard</h1>
        <p className="text-slate-400 mt-1">Sistem istatistikleri ve genel bakış</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat, index) => (
          <div 
            key={index}
            className="relative overflow-hidden bg-slate-900 border border-slate-800 rounded-2xl p-6 hover:border-slate-700 transition-all duration-300 group"
          >
            {/* Background Gradient */}
            <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-br ${stat.color} opacity-5 rounded-full blur-2xl group-hover:opacity-10 transition-opacity`} />
            
            {/* Icon */}
            <div className={`w-12 h-12 ${stat.bgColor} rounded-xl flex items-center justify-center mb-4`}>
              <stat.icon className={`w-6 h-6 ${stat.textColor}`} />
            </div>
            
            {/* Content */}
            <div>
              <p className="text-sm text-slate-400 mb-1">{stat.title}</p>
              <p className="text-3xl font-bold text-white">
                {stat.value.toLocaleString()}
              </p>
              
              {stat.change !== null && stat.changeLabel && (
                <div className="flex items-center gap-1 mt-2">
                  {stat.change > 0 ? (
                    <ArrowUpRight className="w-4 h-4 text-green-500" />
                  ) : (
                    <ArrowDownRight className="w-4 h-4 text-slate-500" />
                  )}
                  <span className={stat.change > 0 ? 'text-green-500 text-sm' : 'text-slate-500 text-sm'}>
                    +{stat.change} {stat.changeLabel}
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <h2 className="text-xl font-semibold text-white mb-4">Hızlı İşlemler</h2>
          <div className="space-y-3">
            <a 
              href="/admin/users" 
              className="flex items-center justify-between p-4 bg-slate-800/50 rounded-xl hover:bg-slate-800 transition-colors group"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-500/20 rounded-lg flex items-center justify-center">
                  <Users className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-white font-medium">Kullanıcıları Yönet</p>
                  <p className="text-sm text-slate-400">{stats?.total_users || 0} kullanıcı</p>
                </div>
              </div>
              <ArrowUpRight className="w-5 h-5 text-slate-500 group-hover:text-white transition-colors" />
            </a>
            
            <a 
              href="/admin/tenants" 
              className="flex items-center justify-between p-4 bg-slate-800/50 rounded-xl hover:bg-slate-800 transition-colors group"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-violet-500/20 rounded-lg flex items-center justify-center">
                  <Building2 className="w-5 h-5 text-violet-400" />
                </div>
                <div>
                  <p className="text-white font-medium">Tenantları Yönet</p>
                  <p className="text-sm text-slate-400">{stats?.total_tenants || 0} tenant</p>
                </div>
              </div>
              <ArrowUpRight className="w-5 h-5 text-slate-500 group-hover:text-white transition-colors" />
            </a>
            
            <a 
              href="/admin/settings" 
              className="flex items-center justify-between p-4 bg-slate-800/50 rounded-xl hover:bg-slate-800 transition-colors group"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-orange-500/20 rounded-lg flex items-center justify-center">
                  <Activity className="w-5 h-5 text-orange-400" />
                </div>
                <div>
                  <p className="text-white font-medium">Sistem Ayarları</p>
                  <p className="text-sm text-slate-400">Konfigürasyon ve ayarlar</p>
                </div>
              </div>
              <ArrowUpRight className="w-5 h-5 text-slate-500 group-hover:text-white transition-colors" />
            </a>
          </div>
        </div>

        {/* System Status */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <h2 className="text-xl font-semibold text-white mb-4">Sistem Durumu</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-slate-800/50 rounded-xl">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
                <span className="text-white">API Sunucusu</span>
              </div>
              <span className="text-green-500 text-sm font-medium">Çalışıyor</span>
            </div>
            
            <div className="flex items-center justify-between p-4 bg-slate-800/50 rounded-xl">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
                <span className="text-white">Veritabanı</span>
              </div>
              <span className="text-green-500 text-sm font-medium">Çalışıyor</span>
            </div>
            
            <div className="flex items-center justify-between p-4 bg-slate-800/50 rounded-xl">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
                <span className="text-white">AI Servisi</span>
              </div>
              <span className="text-green-500 text-sm font-medium">Aktif</span>
            </div>
            
            <div className="flex items-center justify-between p-4 bg-slate-800/50 rounded-xl">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 bg-yellow-500 rounded-full animate-pulse" />
                <span className="text-white">WhatsApp API</span>
              </div>
              <span className="text-yellow-500 text-sm font-medium">Yapılandırılmadı</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

