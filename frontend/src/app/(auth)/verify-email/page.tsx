import { Suspense } from 'react'

import VerifyEmailPageClient from './VerifyEmailPageClient'

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <VerifyEmailPageClient />
    </Suspense>
  )
}
