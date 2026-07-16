'use client'

import { useEffect } from 'react'

export function PwaRegistrar() {
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return
    navigator.serviceWorker.register('/sw.js').catch((error) => {
      console.error('SvontAI service worker registration failed', error)
    })
  }, [])

  return null
}
