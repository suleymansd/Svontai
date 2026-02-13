import type { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://svontai.com'
  const now = new Date()

  const staticRoutes = [
    '/',
    '/pricing',
    '/features',
    '/security',
    '/contact',
    '/docs',
  ]

  const useCases = ['real-estate', 'clinics', 'restaurants']

  const routes: MetadataRoute.Sitemap = [
    ...staticRoutes.map((route) => ({
      url: `${baseUrl}${route}`,
      lastModified: now,
      changeFrequency: 'weekly' as const,
      priority: route === '/' ? 1 : 0.8,
    })),
    ...useCases.map((segment) => ({
      url: `${baseUrl}/use-cases/${segment}`,
      lastModified: now,
      changeFrequency: 'monthly' as const,
      priority: 0.6,
    })),
  ]

  return routes
}
