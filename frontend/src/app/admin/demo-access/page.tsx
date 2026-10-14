'use client'

import { FormEvent, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, Check, Copy, Link2, Loader2, RotateCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { demoAccessApi, type DemoLink } from '@/lib/demo-access'
import { getApiErrorMessage } from '@/lib/api-error'

const stateLabels = { active: 'Aktif', expired: 'Süresi doldu', revoked: 'İptal edildi' }
const formatDate = (value: string) => new Date(value.endsWith('Z') ? value : `${value}Z`).toLocaleDateString('tr-TR')

export default function DemoAccessPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [days, setDays] = useState(14)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [link, setLink] = useState<DemoLink | null>(null)
  const [copied, setCopied] = useState(false)
  const { data = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['admin-demo-access'], queryFn: () => demoAccessApi.list().then(response => response.data),
  })

  async function create(event: FormEvent) {
    event.preventDefault()
    setBusy('create'); setError('')
    try {
      const response = await demoAccessApi.create(name.trim(), days)
      setLink(response.data); setCopied(false); setName('')
      await queryClient.invalidateQueries({ queryKey: ['admin-demo-access'] })
    } catch (cause) { setError(getApiErrorMessage(cause, 'Bağlantı oluşturulamadı.')) }
    finally { setBusy('') }
  }

  async function manage(id: string, action: 'rotate' | 'revoke') {
    const message = action === 'rotate' ? 'Eski bağlantı ve açık oturumlar kapatılarak yeni bağlantı oluşturulsun mu?' : 'Bu müşterinin bağlantısı ve açık oturumları kapatılsın mı?'
    if (!window.confirm(message)) return
    setBusy(id); setError('')
    try {
      if (action === 'rotate') { setLink((await demoAccessApi.rotate(id)).data); setCopied(false) }
      else { await demoAccessApi.revoke(id); if (link?.id === id) setLink(null) }
      await queryClient.invalidateQueries({ queryKey: ['admin-demo-access'] })
    } catch (cause) { setError(getApiErrorMessage(cause, 'İşlem tamamlanamadı.')) }
    finally { setBusy('') }
  }

  async function copy() {
    if (!link) return
    try { await navigator.clipboard.writeText(link.url); setCopied(true) }
    catch { setError('Kopyalama izni verilmedi. Bağlantı alanından seçerek kopyalayabilirsiniz.') }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-8">
      <header className="mb-8"><h1 className="text-2xl font-semibold">Özel erişim</h1><p className="mt-2 text-sm text-muted-foreground">Premium müşteri test alanları</p></header>
      <form onSubmit={create} className="grid items-end gap-4 border-b border-border pb-8 sm:grid-cols-[minmax(0,1fr)_130px_auto]">
        <div className="space-y-2"><Label htmlFor="demo-name">Müşteri / firma adı</Label><Input id="demo-name" value={name} onChange={event => setName(event.target.value)} placeholder="Örn. Optimageek" required minLength={2} maxLength={160} /></div>
        <div className="space-y-2"><Label htmlFor="demo-days">Erişim süresi</Label><select id="demo-days" value={days} onChange={event => setDays(Number(event.target.value))} className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"><option value={7}>7 gün</option><option value={14}>14 gün</option><option value={30}>30 gün</option></select></div>
        <Button disabled={Boolean(busy) || name.trim().length < 2} type="submit">{busy === 'create' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Link2 className="mr-2 h-4 w-4" />}Link oluştur</Button>
      </form>
      {error && <p role="alert" className="mt-5 text-sm text-destructive">{error}</p>}
      {link && <section aria-label="Oluşturulan bağlantı" className="border-b border-border py-6">
        <div className="mb-3 flex flex-wrap items-center gap-2"><Check className="h-4 w-4 shrink-0 text-emerald-600" /><h2 className="min-w-0 max-w-full break-words font-medium">{link.name}</h2><span className="text-sm text-muted-foreground">{formatDate(link.expires_at)} tarihine kadar</span></div>
        <div className="flex gap-2"><Input aria-label="Özel erişim bağlantısı" readOnly value={link.url} onFocus={event => event.target.select()} className="min-w-0 flex-1 font-mono text-xs" /><Button variant="outline" onClick={copy}><Copy className="mr-2 h-4 w-4" />{copied ? 'Kopyalandı' : 'Kopyala'}</Button></div>
        <p className="mt-3 text-xs text-muted-foreground">Bu bağlantıya sahip kişi test alanına erişebilir. Yalnızca ilgili müşteriyle paylaşın.</p>
      </section>}
      <section className="mt-8" aria-label="Erişim bağlantıları">
        {isLoading ? <p role="status" className="py-8 text-sm text-muted-foreground">Yükleniyor...</p> : isError ? <Button variant="outline" onClick={() => refetch()}><RotateCw className="mr-2 h-4 w-4" />Listeyi yeniden yükle</Button> : data.length === 0 ? <p className="py-8 text-sm text-muted-foreground">Henüz özel erişim oluşturulmadı.</p> : <div className="overflow-x-auto"><table className="w-full text-left text-sm">
          <thead className="border-b text-xs text-muted-foreground"><tr><th className="py-3 pr-4 font-medium">Müşteri</th><th className="px-3 py-3 font-medium">Durum</th><th className="px-3 py-3 font-medium">Son erişim</th><th className="px-3 py-3 font-medium">Bitiş</th><th className="py-3 text-right font-medium">İşlemler</th></tr></thead>
          <tbody>{data.map(demo => <tr key={demo.id} className="border-b border-border/60"><td className="min-w-36 py-4 pr-4 font-medium">{demo.name}</td><td className="whitespace-nowrap px-3 py-4"><span className={demo.status === 'active' ? 'text-emerald-700 dark:text-emerald-400' : 'text-muted-foreground'}>{stateLabels[demo.status]}</span></td><td className="whitespace-nowrap px-3 py-4 text-muted-foreground">{demo.last_used_at ? formatDate(demo.last_used_at) : 'Henüz giriş yok'}</td><td className="whitespace-nowrap px-3 py-4 text-muted-foreground">{formatDate(demo.expires_at)}</td><td className="py-4"><div className="flex justify-end gap-1"><Button variant="ghost" size="icon" title="Bağlantıyı yenile" aria-label={`${demo.name}: bağlantıyı yenile`} disabled={Boolean(busy) || demo.status !== 'active'} onClick={() => manage(demo.id, 'rotate')}><RotateCw className="h-4 w-4" /></Button><Button variant="ghost" size="icon" title="Erişimi iptal et" aria-label={`${demo.name}: erişimi iptal et`} disabled={Boolean(busy) || demo.status !== 'active'} onClick={() => manage(demo.id, 'revoke')}><Ban className="h-4 w-4" /></Button></div></td></tr>)}</tbody>
        </table></div>}
      </section>
    </div>
  )
}
