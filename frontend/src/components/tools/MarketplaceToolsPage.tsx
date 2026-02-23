'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, History, PlayCircle, Puzzle, RefreshCcw, Wrench } from 'lucide-react'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { useToast } from '@/components/ui/use-toast'
import { getApiErrorMessage } from '@/lib/api-error'
import { integrationsApi, toolMarketplaceApi } from '@/lib/api'
import { PLAN_LABELS, normalizePlanCode, planMeetsRequirement } from '@/lib/plans'
import { useAuthStore } from '@/lib/store'

type ToolItem = {
  slug: string
  name: string
  description?: string
  category?: string
  status?: string
  enabled: boolean
  isPremium?: boolean
  requiredPlan?: string
  requiredIntegrations: string[]
  rateLimitPerMinute?: number | null
}

type ToolArtifact = {
  id?: string
  type: string
  name: string
  url?: string
  storageProvider?: string
  meta?: Record<string, unknown>
}

type ToolRunSummary = {
  requestId: string
  toolSlug: string
  status: string
  success: boolean
  createdAt: string
  finishedAt?: string | null
  artifactsCount?: number
}

type ToolRunDetail = {
  requestId: string
  toolSlug: string
  status: string
  success: boolean
  data: Record<string, unknown>
  error?: { message?: string; code?: string | null } | null
  usage?: { timeMs?: number; tokens?: number | null; cost?: number | null } | null
  artifacts: ToolArtifact[]
  createdAt?: string
}

type IntegrationStatusItem = {
  status: 'connected' | 'missing' | 'expired'
  required_scopes?: string[]
  granted_scopes?: string[]
  expires_at?: string | null
}

type IntegrationStatusMap = Record<string, IntegrationStatusItem>

const TOOL_FORM_DEFAULTS: Record<string, Record<string, string>> = {
  pdf_summary: {
    pdf_url: '',
    base64_pdf: '',
    language: 'tr',
  },
  pdf_to_word: {
    pdf_url: '',
    base64_pdf: '',
    output_name: '',
  },
  drive_save_file: {
    file_url: '',
    base64_content: '',
    file_name: '',
    folder_id: '',
  },
  gmail_summary: {
    query: '',
    max_messages: '10',
    label_ids: '',
  },
}

function toDateLabel(value?: string | null): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('tr-TR')
}

function normalizeTool(item: any): ToolItem {
  return {
    slug: item.slug,
    name: item.name,
    description: item.description || '',
    category: item.category || 'uncategorized',
    status: item.status || 'unknown',
    enabled: Boolean(item.enabled),
    isPremium: Boolean(item.isPremium ?? item.is_premium),
    requiredPlan: item.requiredPlan ?? item.required_plan ?? 'free',
    requiredIntegrations: Array.isArray(item.requiredIntegrations)
      ? item.requiredIntegrations
      : Array.isArray(item.required_integrations)
        ? item.required_integrations
        : [],
    rateLimitPerMinute: item.rateLimitPerMinute ?? item.rate_limit_per_minute ?? null,
  }
}

function normalizeRunSummary(item: any): ToolRunSummary {
  return {
    requestId: item.requestId ?? item.request_id,
    toolSlug: item.toolSlug ?? item.tool_slug,
    status: item.status ?? 'unknown',
    success: Boolean(item.success),
    createdAt: item.createdAt ?? item.created_at,
    finishedAt: item.finishedAt ?? item.finished_at,
    artifactsCount: item.artifactsCount ?? item.artifacts_count ?? 0,
  }
}

function normalizeRunDetail(item: any): ToolRunDetail {
  return {
    requestId: item.requestId ?? item.request_id,
    toolSlug: item.toolSlug ?? item.tool_slug,
    status: item.status ?? 'unknown',
    success: Boolean(item.success),
    data: item.data || {},
    error: item.error || null,
    usage: item.usage || null,
    artifacts: Array.isArray(item.artifacts) ? item.artifacts : [],
    createdAt: item.createdAt ?? item.created_at,
  }
}

function generateRequestId(slug: string) {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `run-${slug}-${crypto.randomUUID()}`
  }
  return `run-${slug}-${Date.now()}`
}

export default function MarketplaceToolsPage() {
  const { toast } = useToast()
  const { entitlements } = useAuthStore()
  const queryClient = useQueryClient()
  const [activeToolSlug, setActiveToolSlug] = useState<string>('pdf_summary')
  const [formState, setFormState] = useState<Record<string, Record<string, string>>>({
    ...TOOL_FORM_DEFAULTS,
  })
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [lastRunResult, setLastRunResult] = useState<ToolRunDetail | null>(null)
  const [planLimitMessage, setPlanLimitMessage] = useState<string | null>(null)
  const [upgradeModal, setUpgradeModal] = useState<{ toolName: string; requiredPlan: string } | null>(null)

  const tenantPlan = useMemo(
    () => normalizePlanCode((entitlements?.plan_type as string) || 'free'),
    [entitlements]
  )

  const { data: tools = [], isLoading: toolsLoading } = useQuery<ToolItem[]>({
    queryKey: ['marketplace-tools'],
    queryFn: async () => {
      const response = await toolMarketplaceApi.listTools()
      return (response.data || []).map(normalizeTool)
    },
  })

  const { data: runHistory = [], isLoading: runsLoading } = useQuery<ToolRunSummary[]>({
    queryKey: ['marketplace-tool-runs'],
    queryFn: async () => {
      const response = await toolMarketplaceApi.listRuns({ limit: 20, offset: 0 })
      return (response.data || []).map(normalizeRunSummary)
    },
  })

  const { data: integrationStatus = {}, isLoading: integrationsLoading } = useQuery<IntegrationStatusMap>({
    queryKey: ['integrations-status'],
    queryFn: async () => {
      const response = await integrationsApi.getStatus()
      return response.data || {}
    },
  })

  const { data: selectedRunDetail, isLoading: runDetailLoading } = useQuery<ToolRunDetail | null>({
    queryKey: ['marketplace-tool-run-detail', selectedRunId],
    queryFn: async () => {
      if (!selectedRunId) return null
      const response = await toolMarketplaceApi.getRun(selectedRunId)
      return normalizeRunDetail(response.data)
    },
    enabled: Boolean(selectedRunId),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ slug, enabled, rateLimitPerMinute }: { slug: string; enabled: boolean; rateLimitPerMinute?: number | null }) =>
      toolMarketplaceApi.updateToolSettings(slug, {
        enabled,
        rateLimitPerMinute,
        config: {},
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace-tools'] })
      toast({ title: 'Tool ayarı güncellendi' })
    },
    onError: (error: any) => {
      toast({
        title: 'Ayar güncellenemedi',
        description: getApiErrorMessage(error, 'Tool ayarı güncellenirken hata oluştu.'),
        variant: 'destructive',
      })
    },
  })

  const runMutation = useMutation({
    mutationFn: async () => {
      const runtime = toolRuntimeBySlug[activeToolSlug]
      if (!runtime?.canRun) {
        if (runtime?.planLocked) {
          if (runtime.requiredPlan === 'enterprise') {
            throw new Error('Bu tool için Kurumsal plan gerekli.')
          }
          if (runtime.requiredPlan === 'premium') {
            throw new Error('Bu tool için Premium plan gerekli.')
          }
          if (runtime.requiredPlan === 'pro') {
            throw new Error('Bu tool için Pro plan gerekli.')
          }
          throw new Error('Bu tool mevcut planınızda kullanılamıyor.')
        }
        if ((runtime?.missingIntegrations || []).length > 0) {
          throw new Error(`Eksik entegrasyonlar: ${runtime?.missingIntegrations.join(', ')}`)
        }
        throw new Error('Tool çalıştırma şu anda uygun değil.')
      }
      const toolInput = buildToolInput(activeToolSlug, formState[activeToolSlug] || {})
      const requestId = generateRequestId(activeToolSlug)
      const response = await toolMarketplaceApi.runTool({
        requestId,
        toolSlug: activeToolSlug,
        toolInput,
        context: {
          locale: 'tr-TR',
          timezone: 'Europe/Istanbul',
          channel: 'web',
          memory: {},
        },
      })
      return normalizeRunDetail(response.data)
    },
    onSuccess: (result) => {
      setPlanLimitMessage(null)
      setLastRunResult(result)
      setSelectedRunId(result.requestId)
      queryClient.invalidateQueries({ queryKey: ['marketplace-tool-runs'] })
      toast({
        title: result.success ? 'Tool çalıştı' : 'Tool başarısız',
        description: result.success
          ? `Request ID: ${result.requestId}`
          : result.error?.message || 'Tool çalıştırma başarısız.',
        variant: result.success ? 'success' : 'destructive',
      })
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail
      if (detail && typeof detail === 'object' && detail.code === 'PLAN_LIMIT_EXCEEDED') {
        setPlanLimitMessage(detail.message || 'Aylık plan limitinize ulaştınız.')
      }
      toast({
        title: 'Tool çalıştırılamadı',
        description: getApiErrorMessage(error, 'Tool run isteği başarısız oldu.'),
        variant: 'destructive',
      })
    },
  })

  const groupedTools = useMemo(() => {
    const groups = new Map<string, ToolItem[]>()
    for (const tool of tools) {
      const key = tool.category || 'other'
      const current = groups.get(key) || []
      current.push(tool)
      groups.set(key, current)
    }
    return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]))
  }, [tools])

  const toolRuntimeBySlug = useMemo(() => {
    const map: Record<string, { missingIntegrations: string[]; planLocked: boolean; requiredPlan: string; canRun: boolean }> = {}
    for (const tool of tools) {
      const missingIntegrations = (tool.requiredIntegrations || []).filter(
        (key) => integrationStatus[key]?.status !== 'connected'
      )
      const requiredPlan = String(tool.requiredPlan || (tool.isPremium ? 'premium' : 'free')).toLowerCase()
      const planLocked = !planMeetsRequirement(tenantPlan, requiredPlan)
      const canRun = Boolean(tool.enabled && missingIntegrations.length === 0 && !planLocked)
      map[tool.slug] = { missingIntegrations, planLocked, requiredPlan, canRun }
    }
    return map
  }, [tools, integrationStatus, tenantPlan])

  const activeToolRuntime = toolRuntimeBySlug[activeToolSlug] || {
    missingIntegrations: [],
    planLocked: false,
    requiredPlan: 'free',
    canRun: false,
  }

  const detailToShow = selectedRunDetail || lastRunResult

  return (
    <ContentContainer>
      <div className="space-y-6">
        <PageHeader
          title="Marketplace Tools"
          description="Tool’ları aktif et, çalıştır ve artifact çıktılarını indir."
          icon={<Icon3DBadge icon={Puzzle} from="from-primary" to="to-violet-500" />}
          actions={(
            <Button
              variant="outline"
              onClick={() => {
                queryClient.invalidateQueries({ queryKey: ['marketplace-tools'] })
                queryClient.invalidateQueries({ queryKey: ['marketplace-tool-runs'] })
                queryClient.invalidateQueries({ queryKey: ['integrations-status'] })
              }}
            >
              <RefreshCcw className="mr-2 h-4 w-4" />
              Yenile
            </Button>
          )}
        />
        {planLimitMessage && (
          <Card className="border-warning/40 bg-warning-subtle/40">
            <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div className="flex items-center gap-2 text-sm">
                <AlertTriangle className="h-4 w-4 text-warning" />
                <span>{planLimitMessage}</span>
              </div>
              <Link href="/dashboard/billing">
                <Button size="sm">Planı Yükselt</Button>
              </Link>
            </CardContent>
          </Card>
        )}

        <div className="grid gap-6 xl:grid-cols-[1.3fr,0.7fr]">
          <Card>
            <CardHeader>
              <CardTitle>Tool Listesi</CardTitle>
              <CardDescription>Kategori bazlı marketplace araçları</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {toolsLoading && <p className="text-sm text-muted-foreground">Tool listesi yükleniyor...</p>}
              {!toolsLoading && groupedTools.length === 0 && (
                <p className="text-sm text-muted-foreground">Tool bulunamadı.</p>
              )}

              {groupedTools.map(([category, items]) => (
                <div key={category} className="space-y-3">
                  <div className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{category}</div>
                  <div className="grid gap-3">
                    {items.map((tool) => {
                      const runtime = toolRuntimeBySlug[tool.slug] || {
                        missingIntegrations: [],
                        planLocked: false,
                        requiredPlan: 'free',
                        canRun: false,
                      }
                      return (
                        <div key={tool.slug} className="rounded-xl border border-border/70 bg-card/60 p-4">
                          <div className="flex flex-wrap items-start justify-between gap-4">
                            <div className="min-w-0 space-y-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="text-sm font-semibold">{tool.name}</p>
                                {tool.requiredPlan && tool.requiredPlan !== 'free' && (
                                  <Badge variant="warning">{PLAN_LABELS[normalizePlanCode(tool.requiredPlan)]}</Badge>
                                )}
                                {runtime.planLocked && <Badge variant="destructive">Plan Kilidi</Badge>}
                                <Badge variant="outline">{tool.status || 'active'}</Badge>
                              </div>
                              <p className="text-sm text-muted-foreground">{tool.description || '-'}</p>
                              <div className="flex flex-wrap gap-2">
                                {tool.requiredIntegrations.length === 0 && (
                                  <Badge variant="secondary">integration yok</Badge>
                                )}
                                {tool.requiredIntegrations.map((integration) => (
                                  <Badge
                                    key={`${tool.slug}-${integration}`}
                                    variant={integrationStatus[integration]?.status === 'connected' ? 'success' : 'destructive'}
                                  >
                                    {integration}: {integrationStatus[integration]?.status || 'missing'}
                                  </Badge>
                                ))}
                              </div>
                              {runtime.missingIntegrations.length > 0 && (
                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                  <span>Eksik entegrasyon var.</span>
                                  <Link href="/dashboard/integrations" className="text-primary hover:underline">
                                    Connect
                                  </Link>
                                </div>
                              )}
                              {runtime.planLocked && (
                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                  <span>Bu tool {PLAN_LABELS[normalizePlanCode(runtime.requiredPlan)]} plan gerektirir.</span>
                                  {runtime.requiredPlan === 'enterprise' ? (
                                    <a href="mailto:sales@svontai.com" className="text-primary hover:underline">
                                      Contact Sales
                                    </a>
                                  ) : (
                                    <Link href="/dashboard/billing" className="text-primary hover:underline">
                                      {normalizePlanCode(runtime.requiredPlan) === 'pro' ? "Pro'ya Yükselt" : "Premium'a Yükselt"}
                                    </Link>
                                  )}
                                </div>
                              )}
                            </div>
                            <div className="flex items-center gap-3">
                              <div className="flex items-center gap-2">
                                <Label className="text-xs">Enabled</Label>
                                <Switch
                                  checked={tool.enabled}
                                  disabled={toggleMutation.isPending || runtime.planLocked}
                                  onCheckedChange={(checked) =>
                                    toggleMutation.mutate({
                                      slug: tool.slug,
                                      enabled: checked,
                                      rateLimitPerMinute: tool.rateLimitPerMinute,
                                    })
                                  }
                                />
                              </div>
                              <Button
                                size="sm"
                                disabled={!tool.enabled || runtime.missingIntegrations.length > 0}
                                onClick={() => {
                                  if (runtime.planLocked) {
                                    setUpgradeModal({
                                      toolName: tool.name,
                                      requiredPlan: runtime.requiredPlan,
                                    })
                                    return
                                  }
                                  setActiveToolSlug(tool.slug)
                                  setLastRunResult(null)
                                }}
                              >
                                <PlayCircle className="mr-2 h-4 w-4" />
                                Run
                              </Button>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Tool Çalıştır</CardTitle>
              <CardDescription>{activeToolSlug}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {integrationsLoading && (
                <p className="text-xs text-muted-foreground">Integrasyon durumu yükleniyor...</p>
              )}
              {activeToolRuntime.planLocked && (
                <div className="rounded-lg border border-warning/40 bg-warning-subtle/40 p-3 text-sm">
                  Bu tool {PLAN_LABELS[normalizePlanCode(activeToolRuntime.requiredPlan)]} planda kullanılabilir.{' '}
                  {activeToolRuntime.requiredPlan === 'enterprise' ? (
                    <a href="mailto:sales@svontai.com" className="font-medium text-primary hover:underline">
                      Satış ekibiyle iletişime geç
                    </a>
                  ) : (
                    <Link href="/dashboard/billing" className="font-medium text-primary hover:underline">
                      {normalizePlanCode(activeToolRuntime.requiredPlan) === 'pro' ? "Pro'ya yükselt" : "Premium'a yükselt"}
                    </Link>
                  )}
                </div>
              )}
              {activeToolRuntime.missingIntegrations.length > 0 && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                  Eksik entegrasyonlar: {activeToolRuntime.missingIntegrations.join(', ')}.{' '}
                  <Link href="/dashboard/integrations" className="font-medium hover:underline">
                    Connect
                  </Link>
                </div>
              )}
              <ToolInputFields
                toolSlug={activeToolSlug}
                values={formState[activeToolSlug] || {}}
                onChange={(key, value) =>
                  setFormState((prev) => ({
                    ...prev,
                    [activeToolSlug]: {
                      ...(prev[activeToolSlug] || {}),
                      [key]: value,
                    },
                  }))
                }
              />

              <Button
                className="w-full"
                onClick={() => runMutation.mutate()}
                disabled={runMutation.isPending || !activeToolRuntime.canRun}
              >
                <Wrench className="mr-2 h-4 w-4" />
                {runMutation.isPending ? 'Çalıştırılıyor...' : 'Tool Çalıştır'}
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1fr,1fr]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5" />
                Run Geçmişi
              </CardTitle>
              <CardDescription>Son 20 çalıştırma</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Request ID</TableHead>
                    <TableHead>Tool</TableHead>
                    <TableHead>Durum</TableHead>
                    <TableHead>Tarih</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runsLoading && (
                    <TableRow>
                      <TableCell colSpan={4} className="text-muted-foreground">
                        Geçmiş yükleniyor...
                      </TableCell>
                    </TableRow>
                  )}
                  {!runsLoading && runHistory.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} className="text-muted-foreground">
                        Henüz run kaydı yok.
                      </TableCell>
                    </TableRow>
                  )}
                  {runHistory.map((run) => (
                    <TableRow
                      key={run.requestId}
                      className="cursor-pointer"
                      onClick={() => setSelectedRunId(run.requestId)}
                    >
                      <TableCell className="font-mono text-xs">{run.requestId}</TableCell>
                      <TableCell>{run.toolSlug}</TableCell>
                      <TableCell>
                        <Badge variant={run.success ? 'success' : run.status === 'running' ? 'info' : 'destructive'}>
                          {run.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{toDateLabel(run.createdAt)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Run Detayı</CardTitle>
              <CardDescription>
                {detailToShow?.requestId || 'Henüz seçim yok'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {runDetailLoading && <p className="text-sm text-muted-foreground">Detay yükleniyor...</p>}
              {!runDetailLoading && !detailToShow && (
                <p className="text-sm text-muted-foreground">Bir run satırına tıklayarak detayları görüntüleyin.</p>
              )}

              {detailToShow && (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={detailToShow.success ? 'success' : 'destructive'}>
                      {detailToShow.success ? 'success' : 'failed'}
                    </Badge>
                    <Badge variant="outline">{detailToShow.toolSlug}</Badge>
                    <span className="text-xs text-muted-foreground">{toDateLabel(detailToShow.createdAt)}</span>
                  </div>

                  {detailToShow.error?.message && (
                    <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                      {detailToShow.error.message}
                    </div>
                  )}

                  <div className="space-y-2">
                    <p className="text-sm font-medium">Data</p>
                    <pre className="max-h-48 overflow-auto rounded-lg bg-muted p-3 text-xs">
                      {JSON.stringify(detailToShow.data, null, 2)}
                    </pre>
                  </div>

                  <div className="space-y-2">
                    <p className="text-sm font-medium">Artifacts</p>
                    {detailToShow.artifacts.length === 0 && (
                      <p className="text-sm text-muted-foreground">Artifact yok.</p>
                    )}
                    <div className="space-y-2">
                      {detailToShow.artifacts.map((artifact, index) => (
                        <div
                          key={`${artifact.id || artifact.name}-${index}`}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/70 p-3"
                        >
                          <div>
                            <p className="text-sm font-medium">{artifact.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {artifact.type}
                              {artifact.storageProvider ? ` • ${artifact.storageProvider}` : ''}
                            </p>
                          </div>
                          {artifact.url ? (
                            <a href={artifact.url} target="_blank" rel="noreferrer">
                              <Button size="sm" variant="outline">İndir</Button>
                            </a>
                          ) : (
                            <span className="text-xs text-muted-foreground">Link yok</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
        <Dialog open={Boolean(upgradeModal)} onOpenChange={(open) => !open && setUpgradeModal(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Bu araç için plan yükseltmesi gerekli</DialogTitle>
              <DialogDescription>
                {upgradeModal?.toolName} aracını kullanmak için {upgradeModal ? PLAN_LABELS[normalizePlanCode(upgradeModal.requiredPlan)] : ''} planına geçmelisiniz.
              </DialogDescription>
            </DialogHeader>
            <div className="flex items-center justify-end gap-2">
              <Button variant="outline" onClick={() => setUpgradeModal(null)}>Kapat</Button>
              {upgradeModal && normalizePlanCode(upgradeModal.requiredPlan) === 'enterprise' ? (
                <a href="mailto:sales@svontai.com?subject=SvontAI%20Kurumsal%20Plan">
                  <Button>Satışla İletişime Geç</Button>
                </a>
              ) : (
                <Link href="/dashboard/billing">
                  <Button>Yükselt</Button>
                </Link>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </ContentContainer>
  )
}

function buildToolInput(toolSlug: string, values: Record<string, string>) {
  if (toolSlug === 'pdf_summary') {
    const payload: Record<string, unknown> = {
      language: values.language || 'tr',
    }
    if (values.pdf_url?.trim()) payload.pdf_url = values.pdf_url.trim()
    if (values.base64_pdf?.trim()) payload.base64_pdf = values.base64_pdf.trim()
    return payload
  }

  if (toolSlug === 'pdf_to_word') {
    const payload: Record<string, unknown> = {}
    if (values.pdf_url?.trim()) payload.pdf_url = values.pdf_url.trim()
    if (values.base64_pdf?.trim()) payload.base64_pdf = values.base64_pdf.trim()
    if (values.output_name?.trim()) payload.output_name = values.output_name.trim()
    return payload
  }

  if (toolSlug === 'drive_save_file') {
    const payload: Record<string, unknown> = {}
    if (values.file_url?.trim()) payload.file_url = values.file_url.trim()
    if (values.base64_content?.trim()) payload.base64_content = values.base64_content.trim()
    if (values.file_name?.trim()) payload.file_name = values.file_name.trim()
    if (values.folder_id?.trim()) payload.folder_id = values.folder_id.trim()
    return payload
  }

  if (toolSlug === 'gmail_summary') {
    const payload: Record<string, unknown> = {}
    if (values.query?.trim()) payload.query = values.query.trim()
    if (values.max_messages?.trim()) payload.max_messages = Number(values.max_messages)
    if (values.label_ids?.trim()) {
      payload.label_ids = values.label_ids
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
    }
    return payload
  }

  return {}
}

function ToolInputFields({
  toolSlug,
  values,
  onChange,
}: {
  toolSlug: string
  values: Record<string, string>
  onChange: (key: string, value: string) => void
}) {
  if (toolSlug === 'pdf_summary') {
    return (
      <div className="space-y-3">
        <div className="space-y-2">
          <Label>PDF URL</Label>
          <Input value={values.pdf_url || ''} onChange={(e) => onChange('pdf_url', e.target.value)} placeholder="https://..." />
        </div>
        <div className="space-y-2">
          <Label>Base64 PDF (opsiyonel)</Label>
          <Textarea value={values.base64_pdf || ''} onChange={(e) => onChange('base64_pdf', e.target.value)} placeholder="JVBER..." />
        </div>
        <div className="space-y-2">
          <Label>Dil</Label>
          <Input value={values.language || 'tr'} onChange={(e) => onChange('language', e.target.value)} placeholder="tr" />
        </div>
      </div>
    )
  }

  if (toolSlug === 'pdf_to_word') {
    return (
      <div className="space-y-3">
        <div className="space-y-2">
          <Label>PDF URL</Label>
          <Input value={values.pdf_url || ''} onChange={(e) => onChange('pdf_url', e.target.value)} placeholder="https://..." />
        </div>
        <div className="space-y-2">
          <Label>Base64 PDF (opsiyonel)</Label>
          <Textarea value={values.base64_pdf || ''} onChange={(e) => onChange('base64_pdf', e.target.value)} placeholder="JVBER..." />
        </div>
        <div className="space-y-2">
          <Label>Çıkış Dosya Adı</Label>
          <Input value={values.output_name || ''} onChange={(e) => onChange('output_name', e.target.value)} placeholder="teklif-dokumani" />
        </div>
      </div>
    )
  }

  if (toolSlug === 'drive_save_file') {
    return (
      <div className="space-y-3">
        <div className="space-y-2">
          <Label>Dosya URL</Label>
          <Input value={values.file_url || ''} onChange={(e) => onChange('file_url', e.target.value)} placeholder="https://..." />
        </div>
        <div className="space-y-2">
          <Label>Base64 İçerik (opsiyonel)</Label>
          <Textarea value={values.base64_content || ''} onChange={(e) => onChange('base64_content', e.target.value)} placeholder="JVBER..." />
        </div>
        <div className="space-y-2">
          <Label>Dosya Adı</Label>
          <Input value={values.file_name || ''} onChange={(e) => onChange('file_name', e.target.value)} placeholder="dosya.pdf" />
        </div>
        <div className="space-y-2">
          <Label>Drive Klasör ID (opsiyonel)</Label>
          <Input value={values.folder_id || ''} onChange={(e) => onChange('folder_id', e.target.value)} placeholder="1AbCd..." />
        </div>
      </div>
    )
  }

  if (toolSlug === 'gmail_summary') {
    return (
      <div className="space-y-3">
        <div className="space-y-2">
          <Label>Query</Label>
          <Input value={values.query || ''} onChange={(e) => onChange('query', e.target.value)} placeholder="from:client@example.com" />
        </div>
        <div className="space-y-2">
          <Label>Max Messages</Label>
          <Input type="number" min={1} max={50} value={values.max_messages || '10'} onChange={(e) => onChange('max_messages', e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label>Label IDs (virgülle)</Label>
          <Input value={values.label_ids || ''} onChange={(e) => onChange('label_ids', e.target.value)} placeholder="INBOX,IMPORTANT" />
        </div>
      </div>
    )
  }

  return (
    <p className="text-sm text-muted-foreground">
      Bu tool için özel form tanımlı değil. Sadece ilk 4 tool destekleniyor.
    </p>
  )
}
