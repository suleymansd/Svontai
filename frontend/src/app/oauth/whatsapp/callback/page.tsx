'use client'

import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'

export default function WhatsAppOAuthCallbackPage() {
  const [result, setResult] = useState<{ success: boolean; reason: string } | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const success = params.get('success') === '1'
    const reason = (params.get('reason') || '').slice(0, 300)
    const payload = {
      type: 'WHATSAPP_CONNECTED',
      success,
      error: success ? undefined : reason || 'WhatsApp bağlantısı tamamlanamadı.',
    }

    setResult({ success, reason })
    if (window.opener && window.opener !== window) {
      window.opener.postMessage(payload, window.location.origin)
      window.setTimeout(() => window.close(), 600)
    }
  }, [])

  const success = result?.success === true

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6">
      <section className="w-full max-w-md border border-border bg-card p-8 text-center shadow-sm">
        {result === null ? (
          <p className="text-sm text-muted-foreground">WhatsApp bağlantısı doğrulanıyor...</p>
        ) : (
          <>
            {success ? (
              <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" aria-hidden="true" />
            ) : (
              <XCircle className="mx-auto h-10 w-10 text-destructive" aria-hidden="true" />
            )}
            <h1 className="mt-4 text-xl font-semibold">
              {success ? 'WhatsApp bağlantısı tamamlandı' : 'WhatsApp bağlantısı tamamlanamadı'}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {success
                ? 'Bu pencere otomatik olarak kapanacak.'
                : result.reason || 'Lütfen WhatsApp kurulum ekranından yeniden deneyin.'}
            </p>
          </>
        )}
      </section>
    </main>
  )
}
