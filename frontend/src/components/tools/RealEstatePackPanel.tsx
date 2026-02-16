'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, CalendarCheck2, FileDown, FileText, Plus, Save, Send, UploadCloud } from 'lucide-react'
import { realEstateApi } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'

type Persona = 'luxury' | 'pro' | 'warm'

export function RealEstatePackPanel() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [settingsDraft, setSettingsDraft] = useState<any>(null)
  const [newListing, setNewListing] = useState({
    title: '',
    sale_rent: 'sale',
    property_type: 'daire',
    location_text: '',
    price: '',
    rooms: '',
    m2: '',
    url: '',
  })
  const [newTemplate, setNewTemplate] = useState({
    name: '',
    category: 'followup',
    content_preview: '',
  })
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [leadId, setLeadId] = useState('')
  const [listingIdsCsv, setListingIdsCsv] = useState('')
  const [googleSyncConfig, setGoogleSyncConfig] = useState({
    sheet_url: '',
    gid: '',
    csv_url: '',
    deactivate_missing: false,
    save_to_settings: true,
  })
  const [remaxSyncConfig, setRemaxSyncConfig] = useState({
    endpoint_url: '',
    response_path: 'data.listings',
    auth_header: 'Authorization',
    auth_scheme: 'Bearer',
    api_key: '',
    deactivate_missing: false,
    save_to_settings: true,
  })
  const popupRef = useRef<Window | null>(null)

  const settingsQuery = useQuery({
    queryKey: ['real-estate-settings'],
    queryFn: () => realEstateApi.getSettings().then((res) => res.data),
  })
  const listingsQuery = useQuery({
    queryKey: ['real-estate-listings'],
    queryFn: () => realEstateApi.listListings({ active_only: true }).then((res) => res.data),
  })
  const templatesQuery = useQuery({
    queryKey: ['real-estate-templates'],
    queryFn: () => realEstateApi.listTemplates().then((res) => res.data),
  })
  const analyticsQuery = useQuery({
    queryKey: ['real-estate-weekly-analytics'],
    queryFn: () => realEstateApi.getWeeklyAnalytics().then((res) => res.data),
  })
  const agentsQuery = useQuery({
    queryKey: ['real-estate-agents'],
    queryFn: () => realEstateApi.listAgents().then((res) => res.data),
  })
  const googleStatusQuery = useQuery({
    queryKey: ['real-estate-google-calendar-status'],
    queryFn: () => realEstateApi.getGoogleCalendarStatus().then((res) => res.data),
  })

  const settings = useMemo(() => settingsDraft || settingsQuery.data, [settingsDraft, settingsQuery.data])
  const listingSource = useMemo(() => (settings?.listings_source || {}) as any, [settings])

  const saveSettingsMutation = useMutation({
    mutationFn: (payload: any) => realEstateApi.updateSettings(payload),
    onSuccess: ({ data }) => {
      setSettingsDraft(data)
      queryClient.invalidateQueries({ queryKey: ['real-estate-settings'] })
      toast({ title: 'Kaydedildi', description: 'Real Estate Pack ayarları güncellendi.' })
    },
    onError: () => {
      toast({ title: 'Hata', description: 'Ayarlar kaydedilemedi.', variant: 'destructive' })
    },
  })

  const createListingMutation = useMutation({
    mutationFn: (payload: any) => realEstateApi.createListing(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['real-estate-listings'] })
      setNewListing({
        title: '',
        sale_rent: 'sale',
        property_type: 'daire',
        location_text: '',
        price: '',
        rooms: '',
        m2: '',
        url: '',
      })
      toast({ title: 'İlan eklendi' })
    },
    onError: () => {
      toast({ title: 'Hata', description: 'İlan eklenemedi.', variant: 'destructive' })
    },
  })

  const importCsvMutation = useMutation({
    mutationFn: (file: File) => realEstateApi.importListingsCsv(file),
    onSuccess: ({ data }) => {
      queryClient.invalidateQueries({ queryKey: ['real-estate-listings'] })
      setCsvFile(null)
      toast({
        title: 'CSV içe aktarma tamamlandı',
        description: `${data.imported} kayıt eklendi, ${data.skipped} kayıt atlandı.`,
      })
    },
    onError: () => {
      toast({ title: 'Hata', description: 'CSV içe aktarılamadı.', variant: 'destructive' })
    },
  })

  const syncGoogleSheetsMutation = useMutation({
    mutationFn: (payload: typeof googleSyncConfig) => realEstateApi.syncListingsFromGoogleSheets(payload),
    onSuccess: ({ data }) => {
      setSettingsDraft(null)
      queryClient.invalidateQueries({ queryKey: ['real-estate-listings'] })
      queryClient.invalidateQueries({ queryKey: ['real-estate-settings'] })
      toast({
        title: 'Google Sheets senkronizasyonu tamamlandı',
        description: `Yeni: ${data?.stats?.created || 0} • Güncellenen: ${data?.stats?.updated || 0} • Pasif: ${data?.stats?.deactivated || 0}`,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Google Sheets senkronizasyonu başarısız',
        description: error.response?.data?.detail || 'Lütfen bağlantı bilgilerini kontrol edin.',
        variant: 'destructive',
      })
    },
  })

  const syncRemaxMutation = useMutation({
    mutationFn: (payload: typeof remaxSyncConfig) => realEstateApi.syncListingsFromRemax(payload),
    onSuccess: ({ data }) => {
      setSettingsDraft(null)
      queryClient.invalidateQueries({ queryKey: ['real-estate-listings'] })
      queryClient.invalidateQueries({ queryKey: ['real-estate-settings'] })
      toast({
        title: 'Remax senkronizasyonu tamamlandı',
        description: `Yeni: ${data?.stats?.created || 0} • Güncellenen: ${data?.stats?.updated || 0} • Pasif: ${data?.stats?.deactivated || 0}`,
      })
      setRemaxSyncConfig((prev) => ({ ...prev, api_key: '' }))
    },
    onError: (error: any) => {
      toast({
        title: 'Remax senkronizasyonu başarısız',
        description: error.response?.data?.detail || 'Endpoint/response path bilgilerini kontrol edin.',
        variant: 'destructive',
      })
    },
  })

  const createTemplateMutation = useMutation({
    mutationFn: (payload: any) => realEstateApi.createTemplate(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['real-estate-templates'] })
      setNewTemplate({ name: '', category: 'followup', content_preview: '' })
      toast({ title: 'Template eklendi' })
    },
    onError: () => {
      toast({ title: 'Hata', description: 'Template eklenemedi.', variant: 'destructive' })
    },
  })

  const runFollowupsMutation = useMutation({
    mutationFn: () => realEstateApi.runFollowups(),
    onSuccess: ({ data }) => {
      toast({
        title: 'Follow-up çalıştırıldı',
        description: `Sent: ${data.sent} • Skipped: ${data.skipped} • Failed: ${data.failed}`,
      })
    },
    onError: () => {
      toast({ title: 'Hata', description: 'Follow-up çalıştırılamadı.', variant: 'destructive' })
    },
  })

  const googleConnectMutation = useMutation({
    mutationFn: () => realEstateApi.startGoogleCalendarOAuth(),
    onSuccess: ({ data }) => {
      const popup = window.open(
        data.auth_url,
        'google_calendar_connect',
        'width=680,height=760,toolbar=no,menubar=no'
      )
      popupRef.current = popup
      if (!popup) {
        toast({ title: 'Pop-up engellendi', description: 'Tarayıcı pop-up engelini kapatın.', variant: 'destructive' })
      }
    },
    onError: (error: any) => {
      toast({ title: 'Google Calendar', description: error.response?.data?.detail || 'Bağlantı başlatılamadı.', variant: 'destructive' })
    },
  })

  const googleDisconnectMutation = useMutation({
    mutationFn: () => realEstateApi.disconnectGoogleCalendar(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['real-estate-google-calendar-status'] })
      toast({ title: 'Google Calendar bağlantısı kesildi' })
    },
  })

  const generatePdfMutation = useMutation({
    mutationFn: (payload: { listing_ids: string[]; lead_id?: string; send_whatsapp?: boolean }) =>
      realEstateApi.generateListingSummaryPdf(payload),
    onSuccess: ({ data }) => {
      toast({
        title: 'Listing PDF hazır',
        description: data.whatsapp_sent
          ? `WhatsApp gönderildi (media: ${data.media_id || '-'})`
          : `${data.item_count} ilan raporlandı.`,
      })
    },
    onError: (error: any) => {
      toast({ title: 'PDF üretilemedi', description: error.response?.data?.detail || 'Lütfen tekrar deneyin.', variant: 'destructive' })
    },
  })

  const downloadPdfMutation = useMutation({
    mutationFn: (payload: { listing_ids: string[]; lead_id?: string }) =>
      realEstateApi.downloadListingSummaryPdf(payload),
    onSuccess: (res) => {
      const blob = new Blob([res.data], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'listing-summary.pdf'
      link.click()
      URL.revokeObjectURL(url)
    },
    onError: () => {
      toast({ title: 'PDF indirilemedi', variant: 'destructive' })
    },
  })

  const sendSellerReportMutation = useMutation({
    mutationFn: (leadIdValue: string) => realEstateApi.sendSellerServiceReport(leadIdValue),
    onSuccess: () => {
      toast({ title: 'Satıcı servis raporu gönderildi' })
    },
    onError: (error: any) => {
      toast({ title: 'Gönderim hatası', description: error.response?.data?.detail || 'Lütfen tekrar deneyin.', variant: 'destructive' })
    },
  })

  const sendWeeklyMutation = useMutation({
    mutationFn: () => realEstateApi.sendWeeklyReportNow(),
    onSuccess: ({ data }) => {
      if (data.sent) {
        toast({ title: 'Haftalık rapor gönderildi', description: `${data.recipients || 0} alıcıya iletildi.` })
      } else {
        toast({ title: 'Haftalık rapor gönderilmedi', description: data.reason || 'Zaman penceresi dışında olabilir.' })
      }
    },
  })

  const downloadWeeklyMutation = useMutation({
    mutationFn: (weekStart: string) => realEstateApi.downloadWeeklyReport(weekStart),
    onSuccess: (res) => {
      const blob = new Blob([res.data], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'real-estate-weekly-report.pdf'
      link.click()
      URL.revokeObjectURL(url)
    },
    onError: () => {
      toast({ title: 'Haftalık PDF indirilemedi', variant: 'destructive' })
    },
  })

  useEffect(() => {
    const googleRaw = listingSource?.google_sheets
    const googleCfg = typeof googleRaw === 'object' && googleRaw !== null
      ? googleRaw
      : { enabled: Boolean(googleRaw) }
    setGoogleSyncConfig((prev) => ({
      ...prev,
      sheet_url: String(googleCfg.sheet_url || ''),
      gid: String(googleCfg.gid || ''),
      csv_url: String(googleCfg.csv_url || ''),
      deactivate_missing: Boolean(googleCfg.deactivate_missing),
    }))

    const remaxRaw = listingSource?.remax_connector
    const remaxCfg = typeof remaxRaw === 'object' && remaxRaw !== null
      ? remaxRaw
      : { enabled: Boolean(remaxRaw) }
    setRemaxSyncConfig((prev) => ({
      ...prev,
      endpoint_url: String(remaxCfg.endpoint_url || ''),
      response_path: String(remaxCfg.response_path || 'data.listings'),
      auth_header: String(remaxCfg.auth_header || 'Authorization'),
      auth_scheme: String(remaxCfg.auth_scheme || 'Bearer'),
      deactivate_missing: Boolean(remaxCfg.deactivate_missing),
      api_key: '',
    }))
  }, [listingSource])

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.type !== 'GOOGLE_CALENDAR_CONNECTED') return
      if (popupRef.current && !popupRef.current.closed) popupRef.current.close()
      popupRef.current = null
      queryClient.invalidateQueries({ queryKey: ['real-estate-google-calendar-status'] })

      if (event.data?.success) {
        toast({ title: 'Google Calendar bağlandı' })
      } else {
        toast({ title: 'Google Calendar bağlantı hatası', description: event.data?.error || '', variant: 'destructive' })
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [queryClient, toast])

  const selectedListingIds = listingIdsCsv
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  return (
    <div className="space-y-4">
      <Card className="gradient-border-animated">
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <Icon3DBadge icon={Building2} from="from-amber-500" to="to-orange-500" />
            Real Estate Pack
          </CardTitle>
          <CardDescription>Tenant bazlı sektör otomasyon ayarları ve ilan yönetimi.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!settings ? (
            <p className="text-sm text-muted-foreground">Ayarlar yükleniyor...</p>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label>Paket Aktif</Label>
                  <div className="flex h-11 items-center rounded-xl border border-border/70 bg-muted/20 px-3">
                    <Switch
                      checked={Boolean(settings.enabled)}
                      onCheckedChange={(checked) => setSettingsDraft({ ...settings, enabled: checked })}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Persona</Label>
                  <Select
                    value={(settings.persona || 'pro') as Persona}
                    onValueChange={(value) => setSettingsDraft({ ...settings, persona: value })}
                  >
                    <SelectTrigger className="h-11 border-border/70 bg-muted/20">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="luxury">Luxury</SelectItem>
                      <SelectItem value="pro">Pro</SelectItem>
                      <SelectItem value="warm">Warm</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Google Calendar E-Posta</Label>
                  <Input
                    className="h-11 border-border/70 bg-muted/20"
                    value={settings.google_calendar_email || ''}
                    onChange={(event) => setSettingsDraft({ ...settings, google_calendar_email: event.target.value })}
                    placeholder="agent@firma.com"
                  />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label>Lead limiti / ay</Label>
                  <Input
                    className="h-11 border-border/70 bg-muted/20"
                    value={settings.lead_limit_monthly || 0}
                    onChange={(event) => setSettingsDraft({ ...settings, lead_limit_monthly: Number(event.target.value || 0) })}
                    type="number"
                  />
                </div>
                <div className="space-y-2">
                  <Label>PDF limiti / ay</Label>
                  <Input
                    className="h-11 border-border/70 bg-muted/20"
                    value={settings.pdf_limit_monthly || 0}
                    onChange={(event) => setSettingsDraft({ ...settings, pdf_limit_monthly: Number(event.target.value || 0) })}
                    type="number"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Follow-up limiti / ay</Label>
                  <Input
                    className="h-11 border-border/70 bg-muted/20"
                    value={settings.followup_limit_monthly || 0}
                    onChange={(event) => setSettingsDraft({ ...settings, followup_limit_monthly: Number(event.target.value || 0) })}
                    type="number"
                  />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex items-center justify-between rounded-xl border border-border/70 bg-muted/20 px-4 py-3">
                  <div>
                    <p className="text-sm font-medium">Google Sheets kaynağı</p>
                    <p className="text-xs text-muted-foreground">Sheets üzerinden listing senkronizasyonu</p>
                  </div>
                  <Switch
                    checked={Boolean(
                      typeof listingSource?.google_sheets === 'object'
                        ? listingSource?.google_sheets?.enabled
                        : listingSource?.google_sheets
                    )}
                    onCheckedChange={(checked) =>
                      setSettingsDraft({
                        ...settings,
                        listings_source: {
                          ...listingSource,
                          google_sheets: {
                            ...(typeof listingSource?.google_sheets === 'object' ? listingSource?.google_sheets : {}),
                            enabled: checked,
                          },
                        },
                      })
                    }
                  />
                </div>
                <div className="flex items-center justify-between rounded-xl border border-border/70 bg-muted/20 px-4 py-3">
                  <div>
                    <p className="text-sm font-medium">Remax connector</p>
                    <p className="text-xs text-muted-foreground">Harici CRM listing sync</p>
                  </div>
                  <Switch
                    checked={Boolean(
                      typeof listingSource?.remax_connector === 'object'
                        ? listingSource?.remax_connector?.enabled
                        : listingSource?.remax_connector
                    )}
                    onCheckedChange={(checked) =>
                      setSettingsDraft({
                        ...settings,
                        listings_source: {
                          ...listingSource,
                          remax_connector: {
                            ...(typeof listingSource?.remax_connector === 'object' ? listingSource?.remax_connector : {}),
                            enabled: checked,
                          },
                        },
                      })
                    }
                  />
                </div>
              </div>
              <Button
                type="button"
                onClick={() => saveSettingsMutation.mutate(settings)}
                disabled={saveSettingsMutation.isPending}
              >
                <Save className="mr-2 h-4 w-4" />
                Ayarları Kaydet
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Manual Listings</CardTitle>
          <CardDescription>İlan havuzu ve CSV içe aktarma.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-4">
            <Input
              className="h-11 border-border/70 bg-muted/20"
              placeholder="İlan başlığı"
              value={newListing.title}
              onChange={(event) => setNewListing({ ...newListing, title: event.target.value })}
            />
            <Input
              className="h-11 border-border/70 bg-muted/20"
              placeholder="Bölge"
              value={newListing.location_text}
              onChange={(event) => setNewListing({ ...newListing, location_text: event.target.value })}
            />
            <Input
              className="h-11 border-border/70 bg-muted/20"
              placeholder="Fiyat"
              type="number"
              value={newListing.price}
              onChange={(event) => setNewListing({ ...newListing, price: event.target.value })}
            />
            <Button
              type="button"
              onClick={() =>
                createListingMutation.mutate({
                  ...newListing,
                  price: Number(newListing.price || 0),
                  m2: newListing.m2 ? Number(newListing.m2) : undefined,
                  rooms: newListing.rooms || undefined,
                  url: newListing.url || undefined,
                })
              }
              disabled={createListingMutation.isPending || !newListing.title || !newListing.location_text || !newListing.price}
            >
              <Plus className="mr-2 h-4 w-4" />
              Ekle
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/70 bg-muted/20 p-3">
            <Input
              type="file"
              accept=".csv"
              className="max-w-xs"
              onChange={(event) => setCsvFile(event.target.files?.[0] || null)}
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => csvFile && importCsvMutation.mutate(csvFile)}
              disabled={!csvFile || importCsvMutation.isPending}
            >
              <UploadCloud className="mr-2 h-4 w-4" />
              CSV Yükle
            </Button>
          </div>

          <div className="rounded-xl border border-border/70">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>İlan</TableHead>
                  <TableHead>Bölge</TableHead>
                  <TableHead>Tip</TableHead>
                  <TableHead>Fiyat</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(listingsQuery.data || []).slice(0, 8).map((listing: any) => (
                  <TableRow key={listing.id}>
                    <TableCell className="font-medium">{listing.title}</TableCell>
                    <TableCell>{listing.location_text}</TableCell>
                    <TableCell>{listing.sale_rent === 'sale' ? 'Satılık' : 'Kiralık'}</TableCell>
                    <TableCell>{Number(listing.price).toLocaleString('tr-TR')} {listing.currency}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Listings Connectors</CardTitle>
          <CardDescription>Google Sheets ve Remax kaynaklarından toplu listing senkronizasyonu.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-3 rounded-xl border border-border/70 p-4">
              <div className="space-y-1">
                <p className="text-sm font-semibold">Google Sheets Sync</p>
                <p className="text-xs text-muted-foreground">Public veya publish edilmiş sheet üzerinden CSV çekerek listing günceller.</p>
              </div>
              <Input
                className="h-10 border-border/70 bg-muted/20"
                placeholder="Sheet URL"
                value={googleSyncConfig.sheet_url}
                onChange={(event) => setGoogleSyncConfig({ ...googleSyncConfig, sheet_url: event.target.value })}
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  className="h-10 border-border/70 bg-muted/20"
                  placeholder="gid (opsiyonel)"
                  value={googleSyncConfig.gid}
                  onChange={(event) => setGoogleSyncConfig({ ...googleSyncConfig, gid: event.target.value })}
                />
                <Input
                  className="h-10 border-border/70 bg-muted/20"
                  placeholder="CSV URL (opsiyonel)"
                  value={googleSyncConfig.csv_url}
                  onChange={(event) => setGoogleSyncConfig({ ...googleSyncConfig, csv_url: event.target.value })}
                />
              </div>
              <div className="flex flex-wrap gap-3">
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Switch
                    checked={googleSyncConfig.deactivate_missing}
                    onCheckedChange={(checked) => setGoogleSyncConfig({ ...googleSyncConfig, deactivate_missing: checked })}
                  />
                  Eksik kayıtları pasifleştir
                </label>
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Switch
                    checked={googleSyncConfig.save_to_settings}
                    onCheckedChange={(checked) => setGoogleSyncConfig({ ...googleSyncConfig, save_to_settings: checked })}
                  />
                  Ayarları tenant profiline kaydet
                </label>
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={() => syncGoogleSheetsMutation.mutate(googleSyncConfig)}
                disabled={syncGoogleSheetsMutation.isPending || (!googleSyncConfig.sheet_url && !googleSyncConfig.csv_url)}
              >
                <UploadCloud className="mr-2 h-4 w-4" />
                Google Sheets Senkronize Et
              </Button>
              {typeof listingSource?.google_sheets === 'object' && listingSource?.google_sheets?.last_sync_at && (
                <p className="text-xs text-muted-foreground">
                  Son sync: {new Date(String(listingSource.google_sheets.last_sync_at)).toLocaleString('tr-TR')}
                </p>
              )}
            </div>

            <div className="space-y-3 rounded-xl border border-border/70 p-4">
              <div className="space-y-1">
                <p className="text-sm font-semibold">Remax Connector Sync</p>
                <p className="text-xs text-muted-foreground">JSON endpoint&apos;ten listing çekerek tenant havuzunu günceller.</p>
              </div>
              <Input
                className="h-10 border-border/70 bg-muted/20"
                placeholder="Endpoint URL"
                value={remaxSyncConfig.endpoint_url}
                onChange={(event) => setRemaxSyncConfig({ ...remaxSyncConfig, endpoint_url: event.target.value })}
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  className="h-10 border-border/70 bg-muted/20"
                  placeholder="Response Path (örn: data.listings)"
                  value={remaxSyncConfig.response_path}
                  onChange={(event) => setRemaxSyncConfig({ ...remaxSyncConfig, response_path: event.target.value })}
                />
                <Input
                  className="h-10 border-border/70 bg-muted/20"
                  placeholder="API Key (opsiyonel)"
                  value={remaxSyncConfig.api_key}
                  onChange={(event) => setRemaxSyncConfig({ ...remaxSyncConfig, api_key: event.target.value })}
                  type="password"
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Input
                  className="h-10 border-border/70 bg-muted/20"
                  placeholder="Auth Header"
                  value={remaxSyncConfig.auth_header}
                  onChange={(event) => setRemaxSyncConfig({ ...remaxSyncConfig, auth_header: event.target.value })}
                />
                <Input
                  className="h-10 border-border/70 bg-muted/20"
                  placeholder="Auth Scheme (Bearer)"
                  value={remaxSyncConfig.auth_scheme}
                  onChange={(event) => setRemaxSyncConfig({ ...remaxSyncConfig, auth_scheme: event.target.value })}
                />
              </div>
              <div className="flex flex-wrap gap-3">
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Switch
                    checked={remaxSyncConfig.deactivate_missing}
                    onCheckedChange={(checked) => setRemaxSyncConfig({ ...remaxSyncConfig, deactivate_missing: checked })}
                  />
                  Eksik kayıtları pasifleştir
                </label>
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Switch
                    checked={remaxSyncConfig.save_to_settings}
                    onCheckedChange={(checked) => setRemaxSyncConfig({ ...remaxSyncConfig, save_to_settings: checked })}
                  />
                  Ayarları tenant profiline kaydet
                </label>
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={() => syncRemaxMutation.mutate(remaxSyncConfig)}
                disabled={syncRemaxMutation.isPending || !remaxSyncConfig.endpoint_url}
              >
                <UploadCloud className="mr-2 h-4 w-4" />
                Remax Senkronize Et
              </Button>
              {typeof listingSource?.remax_connector === 'object' && listingSource?.remax_connector?.last_sync_at && (
                <p className="text-xs text-muted-foreground">
                  Son sync: {new Date(String(listingSource.remax_connector.last_sync_at)).toLocaleString('tr-TR')}
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Template Registry</CardTitle>
          <CardDescription>Onaylı şablon eşleme ve follow-up template yönetimi.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-[1fr,160px,1.5fr,auto]">
            <Input
              className="h-11 border-border/70 bg-muted/20"
              placeholder="template_name"
              value={newTemplate.name}
              onChange={(event) => setNewTemplate({ ...newTemplate, name: event.target.value })}
            />
            <Select
              value={newTemplate.category}
              onValueChange={(value) => setNewTemplate({ ...newTemplate, category: value })}
            >
              <SelectTrigger className="h-11 border-border/70 bg-muted/20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="welcome">welcome</SelectItem>
                <SelectItem value="followup">followup</SelectItem>
                <SelectItem value="appointment">appointment</SelectItem>
                <SelectItem value="listing">listing</SelectItem>
                <SelectItem value="seller">seller</SelectItem>
              </SelectContent>
            </Select>
            <Textarea
              className="min-h-[44px] border-border/70 bg-muted/20"
              placeholder="İçerik önizleme"
              value={newTemplate.content_preview}
              onChange={(event) => setNewTemplate({ ...newTemplate, content_preview: event.target.value })}
            />
            <Button
              type="button"
              onClick={() => createTemplateMutation.mutate(newTemplate)}
              disabled={!newTemplate.name || createTemplateMutation.isPending}
            >
              <Plus className="mr-2 h-4 w-4" />
              Ekle
            </Button>
          </div>

          <div className="flex flex-wrap gap-2">
            {(templatesQuery.data || []).map((template: any) => (
              <Badge key={template.id} variant={template.is_approved ? 'default' : 'outline'}>
                {template.name} • {template.category}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Haftalık Analitik & Follow-up</CardTitle>
          <CardDescription>Lead funnel görünümü ve follow-up tetikleme.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-border/70 bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Lead</p>
              <p className="text-xl font-semibold">{analyticsQuery.data?.lead_count ?? 0}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Aktif Konuşma</p>
              <p className="text-xl font-semibold">{analyticsQuery.data?.active_conversations ?? 0}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Randevu</p>
              <p className="text-xl font-semibold">{analyticsQuery.data?.appointment_count ?? 0}</p>
            </div>
            <div className="rounded-xl border border-border/70 bg-muted/20 p-3">
              <p className="text-xs text-muted-foreground">Dönüşüm %</p>
              <p className="text-xl font-semibold">{analyticsQuery.data?.conversion_rate_percent ?? 0}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => runFollowupsMutation.mutate()}
              disabled={runFollowupsMutation.isPending}
            >
              <Send className="mr-2 h-4 w-4" />
              Follow-up Çalıştır
            </Button>
            <span className="text-xs text-muted-foreground">
              Aktif ajanlar: {(agentsQuery.data || []).map((agent: any) => agent.full_name).join(', ') || 'Yok'}
            </span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Google Calendar + PDF İşlemleri</CardTitle>
          <CardDescription>Gerçek OAuth bağlantısı, listing PDF üretimi ve WhatsApp document gönderimi.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={googleStatusQuery.data?.connected ? 'default' : 'outline'}>
              {googleStatusQuery.data?.connected ? 'Google Calendar Bağlı' : 'Google Calendar Bağlı Değil'}
            </Badge>
            <Button
              type="button"
              variant="outline"
              onClick={() => googleConnectMutation.mutate()}
              disabled={googleConnectMutation.isPending}
            >
              <CalendarCheck2 className="mr-2 h-4 w-4" />
              Google Calendar Bağla
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => googleDisconnectMutation.mutate()}
              disabled={googleDisconnectMutation.isPending}
            >
              Bağlantıyı Kes
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              className="h-11 border-border/70 bg-muted/20"
              placeholder="Lead ID (PDF WhatsApp ve seller report için)"
              value={leadId}
              onChange={(event) => setLeadId(event.target.value)}
            />
            <Input
              className="h-11 border-border/70 bg-muted/20"
              placeholder="Listing ID'ler (virgül ile)"
              value={listingIdsCsv}
              onChange={(event) => setListingIdsCsv(event.target.value)}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => downloadPdfMutation.mutate({ listing_ids: selectedListingIds, lead_id: leadId || undefined })}
              disabled={selectedListingIds.length === 0 || downloadPdfMutation.isPending}
            >
              <FileDown className="mr-2 h-4 w-4" />
              PDF İndir
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => generatePdfMutation.mutate({ listing_ids: selectedListingIds, lead_id: leadId || undefined, send_whatsapp: true })}
              disabled={selectedListingIds.length === 0 || !leadId || generatePdfMutation.isPending}
            >
              <FileText className="mr-2 h-4 w-4" />
              WhatsApp'a PDF Gönder
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => leadId && sendSellerReportMutation.mutate(leadId)}
              disabled={!leadId || sendSellerReportMutation.isPending}
            >
              Satıcı Servis Raporu Gönder
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => sendWeeklyMutation.mutate()}
              disabled={sendWeeklyMutation.isPending}
            >
              Haftalık E-Posta/PDF Raporunu Gönder
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => analyticsQuery.data?.week_start && downloadWeeklyMutation.mutate(String(analyticsQuery.data.week_start))}
              disabled={!analyticsQuery.data?.week_start || downloadWeeklyMutation.isPending}
            >
              Haftalık PDF İndir
            </Button>
          </div>
          {(listingsQuery.data || []).length > 0 && (
            <p className="text-xs text-muted-foreground">
              İpucu: Listing ID örnekleri: {(listingsQuery.data || []).slice(0, 3).map((item: any) => item.id).join(', ')}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
