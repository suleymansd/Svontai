'use client'

import Link from 'next/link'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, Building2, Pause, Play, Plus, ShieldCheck, Ticket } from 'lucide-react'
import { agencyApi } from '@/lib/api'
import { ContentContainer } from '@/components/shared/content-container'
import { PageHeader } from '@/components/shared/page-header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { useToast } from '@/components/ui/use-toast'

export default function AgencyClientsPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [clientTenantId, setClientTenantId] = useState('')
  const [notes, setNotes] = useState('')

  const clientsQuery = useQuery({
    queryKey: ['agency-clients'],
    queryFn: () => agencyApi.listClients().then((res) => res.data.items || []),
  })

  const createClientMutation = useMutation({
    mutationFn: () => agencyApi.createClient({ client_tenant_id: clientTenantId.trim(), notes: notes.trim() || undefined }),
    onSuccess: () => {
      setClientTenantId('')
      setNotes('')
      queryClient.invalidateQueries({ queryKey: ['agency-clients'] })
      toast({ title: 'Müşteri eklendi', description: 'Ajans müşteri listesi güncellendi.' })
    },
    onError: (error: any) => {
      toast({
        title: 'Müşteri eklenemedi',
        description: error?.response?.data?.detail || 'Tenant ID ve yetkileri kontrol edin.',
        variant: 'destructive',
      })
    },
  })

  const updateClientMutation = useMutation({
    mutationFn: ({ relationshipId, status }: { relationshipId: string; status: 'active' | 'paused' | 'archived' }) =>
      agencyApi.updateClient(relationshipId, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agency-clients'] }),
    onError: () => toast({ title: 'İşlem tamamlanamadı', variant: 'destructive' }),
  })

  const archiveClientMutation = useMutation({
    mutationFn: (relationshipId: string) => agencyApi.archiveClient(relationshipId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['agency-clients'] }),
    onError: () => toast({ title: 'Müşteri arşivlenemedi', variant: 'destructive' }),
  })

  const canSubmit = clientTenantId.trim().length > 0 && !createClientMutation.isPending

  return (
    <ContentContainer>
      <div className="space-y-8">
        <PageHeader
          title="Ajans Müşterileri"
          description="Yönettiğiniz müşteri hesaplarının sağlık, kullanım ve açık destek durumlarını izleyin."
          icon={<Building2 className="h-7 w-7 text-primary" />}
        />

        <Card>
          <CardHeader>
            <CardTitle>Yeni müşteri bağla</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="grid gap-4 lg:grid-cols-[minmax(220px,1fr)_minmax(260px,1.4fr)_auto]"
              onSubmit={(event) => {
                event.preventDefault()
                if (canSubmit) createClientMutation.mutate()
              }}
            >
              <div className="space-y-2">
                <Label htmlFor="clientTenantId">Client tenant ID</Label>
                <Input
                  id="clientTenantId"
                  value={clientTenantId}
                  onChange={(event) => setClientTenantId(event.target.value)}
                  placeholder="UUID"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="clientNotes">Not</Label>
                <Textarea
                  id="clientNotes"
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  placeholder="Opsiyonel yönetim notu"
                  className="min-h-[42px]"
                />
              </div>
              <div className="flex items-end">
                <Button type="submit" disabled={!canSubmit} className="w-full lg:w-auto">
                  <Plus className="mr-2 h-4 w-4" />
                  Ekle
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {clientsQuery.isLoading ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Skeleton className="h-40" />
            <Skeleton className="h-40" />
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {clientsQuery.data?.map((client: any) => (
              <Card key={client.tenant_id}>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>{client.name}</CardTitle>
                    <p className="text-sm text-muted-foreground">{client.plan} plan</p>
                  </div>
                  <Badge variant={client.autopilot_status === 'ready' ? 'success' : 'warning'}>
                    {client.health_score}/100
                  </Badge>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div className="rounded-lg bg-muted p-3">
                      <div className="flex items-center gap-2 text-muted-foreground"><ShieldCheck className="h-4 w-4" /> Sağlık</div>
                      <p className="mt-1 font-semibold">{client.autopilot_status === 'ready' ? 'Hazır' : 'Dikkat'}</p>
                    </div>
                    <div className="rounded-lg bg-muted p-3">
                      <div className="text-muted-foreground">Run</div>
                      <p className="mt-1 font-semibold">{client.monthly_runs_used}/{client.monthly_runs_limit}</p>
                    </div>
                    <div className="rounded-lg bg-muted p-3">
                      <div className="flex items-center gap-2 text-muted-foreground"><Ticket className="h-4 w-4" /> Ticket</div>
                      <p className="mt-1 font-semibold">{client.open_tickets}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button asChild variant="outline">
                      <Link href={`/dashboard/agency/${client.tenant_id}`}>Sağlık Detayı</Link>
                    </Button>
                    {client.relationship_id ? (
                      <>
                        {client.status === 'paused' ? (
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => updateClientMutation.mutate({ relationshipId: client.relationship_id, status: 'active' })}
                          >
                            <Play className="mr-2 h-4 w-4" />
                            Aktif Et
                          </Button>
                        ) : (
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => updateClientMutation.mutate({ relationshipId: client.relationship_id, status: 'paused' })}
                          >
                            <Pause className="mr-2 h-4 w-4" />
                            Duraklat
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => archiveClientMutation.mutate(client.relationship_id)}
                        >
                          <Archive className="mr-2 h-4 w-4" />
                          Arşivle
                        </Button>
                      </>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </ContentContainer>
  )
}
