'use client'

import Image from 'next/image'
import { useParams, useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Printer, ReceiptText } from 'lucide-react'

import { adminApi } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/components/ui/use-toast'
import { ContentContainer } from '@/components/shared/content-container'
import { Icon3DBadge } from '@/components/shared/icon-3d-badge'
import { PageHeader } from '@/components/shared/page-header'

type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'cancelled'

type InvoiceLine = {
  description: string
  quantity: string
  unit: string
  unit_price: string
  tax_rate: string
  subtotal: string
  tax: string
  total: string
}

type Invoice = {
  id: string
  invoice_number: string
  status: InvoiceStatus
  issue_date: string
  due_date: string
  currency: string
  seller_name: string
  seller_email?: string | null
  seller_phone?: string | null
  seller_address?: string | null
  seller_tax_office?: string | null
  seller_tax_number?: string | null
  customer_name: string
  customer_email?: string | null
  customer_phone?: string | null
  customer_address?: string | null
  customer_tax_office?: string | null
  customer_tax_number?: string | null
  items: InvoiceLine[]
  subtotal: string
  tax_total: string
  total: string
  notes?: string | null
  legal_notice: string
}

const statusLabels: Record<InvoiceStatus, string> = {
  draft: 'Taslak',
  sent: 'Gönderildi',
  paid: 'Ödendi',
  cancelled: 'İptal',
}

const formatMoney = (value: string, currency: string) => new Intl.NumberFormat('tr-TR', {
  style: 'currency',
  currency,
}).format(Number(value))

export default function AdminInvoiceDetailPage() {
  const params = useParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const invoiceId = params.id as string

  const invoiceQuery = useQuery<Invoice>({
    queryKey: ['admin-invoice', invoiceId],
    queryFn: () => adminApi.getInvoice(invoiceId).then((response) => response.data),
    enabled: Boolean(invoiceId),
  })
  const statusMutation = useMutation({
    mutationFn: (status: InvoiceStatus) => adminApi.updateInvoiceStatus(invoiceId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-invoice', invoiceId] })
      queryClient.invalidateQueries({ queryKey: ['admin-invoices'] })
      toast({ title: 'Proforma durumu güncellendi' })
    },
  })

  if (invoiceQuery.isLoading) {
    return <ContentContainer><Skeleton className="h-[700px] w-full" /></ContentContainer>
  }
  const invoice = invoiceQuery.data
  if (!invoice) {
    return <ContentContainer><p className="text-sm text-muted-foreground">Proforma bulunamadı.</p></ContentContainer>
  }

  const partyLines = (values: Array<string | null | undefined>) => values.filter(Boolean) as string[]

  return (
    <ContentContainer className="print:max-w-none print:p-0">
      <div className="space-y-6 print:space-y-0">
        <div className="print:hidden">
          <PageHeader
            title={invoice.invoice_number}
            description="Proformayı görüntüleyin, durumunu yönetin veya PDF olarak kaydedin."
            icon={<Icon3DBadge icon={ReceiptText} from="from-cyan-500" to="to-emerald-500" />}
            actions={(
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => router.push('/admin/invoices')}><ArrowLeft className="mr-2 h-4 w-4" />Liste</Button>
                <Button onClick={() => window.print()}><Printer className="mr-2 h-4 w-4" />PDF / Yazdır</Button>
              </div>
            )}
          />
          <div className="mt-4 flex items-center gap-3">
            <Badge variant={invoice.status === 'paid' ? 'success' : invoice.status === 'cancelled' ? 'destructive' : invoice.status === 'sent' ? 'warning' : 'secondary'}>{statusLabels[invoice.status]}</Badge>
            <select
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              value={invoice.status}
              onChange={(event) => statusMutation.mutate(event.target.value as InvoiceStatus)}
              disabled={statusMutation.isPending}
              aria-label="Proforma durumu"
            >
              {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
        </div>

        <article className="mx-auto min-h-[1120px] w-full max-w-[794px] bg-white p-8 text-slate-950 shadow-sm sm:p-12 print:min-h-0 print:max-w-none print:p-10 print:shadow-none">
          <header className="flex items-start justify-between gap-6 border-b border-slate-200 pb-8">
            <div className="flex items-center gap-4">
              <Image src="/logo.png" alt="SvontAI" width={62} height={72} className="h-[62px] w-auto object-contain" priority />
              <div>
                <p className="text-2xl font-bold">SvontAI</p>
                <p className="text-sm text-slate-500">Otonom müşteri iletişimi</p>
              </div>
            </div>
            <div className="text-right">
              <h1 className="text-2xl font-bold">PROFORMA FATURA</h1>
              <p className="mt-2 font-mono text-sm text-slate-600">{invoice.invoice_number}</p>
              <Badge className="mt-3 print:border print:border-slate-300 print:bg-white print:text-slate-900" variant="secondary">{statusLabels[invoice.status]}</Badge>
            </div>
          </header>

          <section className="grid gap-8 py-8 sm:grid-cols-2">
            <div>
              <p className="mb-3 text-xs font-semibold uppercase text-slate-500">Düzenleyen</p>
              <p className="font-semibold">{invoice.seller_name}</p>
              {partyLines([invoice.seller_address, invoice.seller_email, invoice.seller_phone]).map((line) => <p key={line} className="mt-1 whitespace-pre-line text-sm text-slate-600">{line}</p>)}
              {(invoice.seller_tax_office || invoice.seller_tax_number) && <p className="mt-2 text-sm text-slate-600">{[invoice.seller_tax_office, invoice.seller_tax_number].filter(Boolean).join(' / ')}</p>}
            </div>
            <div className="sm:text-right">
              <p className="mb-3 text-xs font-semibold uppercase text-slate-500">Müşteri</p>
              <p className="font-semibold">{invoice.customer_name}</p>
              {partyLines([invoice.customer_address, invoice.customer_email, invoice.customer_phone]).map((line) => <p key={line} className="mt-1 whitespace-pre-line text-sm text-slate-600">{line}</p>)}
              {(invoice.customer_tax_office || invoice.customer_tax_number) && <p className="mt-2 text-sm text-slate-600">{[invoice.customer_tax_office, invoice.customer_tax_number].filter(Boolean).join(' / ')}</p>}
            </div>
          </section>

          <section className="mb-8 grid grid-cols-2 gap-4 border-y border-slate-200 py-4 text-sm sm:grid-cols-4">
            <div><p className="text-slate-500">Düzenleme</p><p className="mt-1 font-medium">{new Date(invoice.issue_date).toLocaleDateString('tr-TR')}</p></div>
            <div><p className="text-slate-500">Son ödeme</p><p className="mt-1 font-medium">{new Date(invoice.due_date).toLocaleDateString('tr-TR')}</p></div>
            <div><p className="text-slate-500">Para birimi</p><p className="mt-1 font-medium">{invoice.currency}</p></div>
            <div><p className="text-slate-500">Belge türü</p><p className="mt-1 font-medium">Proforma</p></div>
          </section>

          <div className="overflow-hidden border border-slate-200">
            <table className="w-full table-fixed text-left text-sm">
              <thead className="bg-slate-100 text-xs uppercase text-slate-600">
                <tr><th className="w-[38%] px-3 py-3">Açıklama</th><th className="px-2 py-3 text-right">Miktar</th><th className="px-2 py-3 text-right">Birim fiyat</th><th className="px-2 py-3 text-right">Vergi</th><th className="px-3 py-3 text-right">Toplam</th></tr>
              </thead>
              <tbody>
                {invoice.items.map((line, index) => (
                  <tr key={`${line.description}-${index}`} className="border-t border-slate-200">
                    <td className="break-words px-3 py-3 font-medium">{line.description}</td>
                    <td className="px-2 py-3 text-right">{line.quantity} {line.unit}</td>
                    <td className="px-2 py-3 text-right">{formatMoney(line.unit_price, invoice.currency)}</td>
                    <td className="px-2 py-3 text-right">%{line.tax_rate}</td>
                    <td className="px-3 py-3 text-right font-medium">{formatMoney(line.total, invoice.currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <section className="ml-auto mt-6 grid max-w-sm grid-cols-2 gap-x-8 gap-y-3 text-sm">
            <span className="text-slate-500">Ara toplam</span><span className="text-right">{formatMoney(invoice.subtotal, invoice.currency)}</span>
            <span className="text-slate-500">Vergi toplamı</span><span className="text-right">{formatMoney(invoice.tax_total, invoice.currency)}</span>
            <span className="border-t border-slate-300 pt-3 text-base font-bold">Genel toplam</span><span className="border-t border-slate-300 pt-3 text-right text-base font-bold">{formatMoney(invoice.total, invoice.currency)}</span>
          </section>

          {invoice.notes && <section className="mt-10 border-t border-slate-200 pt-5"><p className="text-xs font-semibold uppercase text-slate-500">Notlar</p><p className="mt-2 whitespace-pre-line text-sm text-slate-700">{invoice.notes}</p></section>}

          <footer className="mt-12 border-t border-slate-200 pt-5 text-center text-xs text-slate-500">
            <p>{invoice.legal_notice}</p>
            <p className="mt-2">SvontAI ile güvenli otonom işletim</p>
          </footer>
        </article>
      </div>
    </ContentContainer>
  )
}
