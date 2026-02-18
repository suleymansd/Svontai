import { Suspense } from 'react'
import AdminLoginPageClient from './AdminLoginPageClient'

export default function AdminLoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <AdminLoginPageClient />
    </Suspense>
  )
}

