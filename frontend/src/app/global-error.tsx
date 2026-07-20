'use client'

import * as Sentry from '@sentry/nextjs'
import { useEffect } from 'react'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    Sentry.captureException(error)
  }, [error])

  return (
    <html lang="tr">
      <body className="flex min-h-screen items-center justify-center bg-background px-6 text-foreground">
        <main className="w-full max-w-md text-center">
          <p className="text-sm font-medium text-primary">SvontAI</p>
          <h1 className="mt-3 text-2xl font-semibold">Sayfa yüklenemedi</h1>
          <p className="mt-3 text-sm text-muted-foreground">
            Hata kaydedildi. İşleminize devam etmek için sayfayı yeniden deneyin.
          </p>
          <button
            type="button"
            onClick={reset}
            className="mt-6 inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"
          >
            Tekrar Dene
          </button>
        </main>
      </body>
    </html>
  )
}
