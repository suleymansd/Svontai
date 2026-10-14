import type { Metadata } from 'next'
import DemoEntry from './DemoEntry'

export const metadata: Metadata = {
  title: 'Özel Erişim',
  robots: { index: false, follow: false },
  referrer: 'no-referrer',
}

export default function DemoPage() {
  return <DemoEntry />
}
