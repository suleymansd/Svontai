import { expect, test } from '@playwright/test'

const publicRoutes = [
  { path: '/', heading: /SvontAI/i },
  { path: '/login', heading: /Tekrar hoş geldiniz/i },
  { path: '/register', heading: /Hesap|Kayıt/i },
  { path: '/contact', heading: /demo ve kurulum görüşmesi/i },
  { path: '/docs', heading: /SvontAI kullanım kılavuzu/i },
]

for (const route of publicRoutes) {
  test(`${route.path} renders without console errors or horizontal overflow`, async ({ page }) => {
    const errors: string[] = []
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(message.text())
    })
    page.on('pageerror', (error) => errors.push(error.message))

    await page.goto(route.path)
    await expect(page.getByRole('heading', { name: route.heading }).first()).toBeVisible()
    const dimensions = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }))
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1)
    expect(errors).toEqual([])
  })
}

test('contact page exposes a real sales request form', async ({ page }) => {
  await page.goto('/contact?plan=pro&interval=monthly')
  await expect(page.getByLabel('Ad Soyad')).toBeVisible()
  await expect(page.getByLabel('E-posta')).toBeVisible()
  await expect(page.getByLabel('Mesajınız')).toHaveValue(/PRO planı/)
  await expect(page.getByRole('button', { name: 'Görüşme Talebi Gönder' })).toBeEnabled()
})

test('customer guide search opens the matching section', async ({ page }) => {
  await page.goto('/docs')
  await page.getByLabel('Kılavuzda ara').fill('randevu')
  await page.getByRole('link', { name: /Randevular/ }).first().click()
  await expect(page).toHaveURL(/#randevular$/)
  await expect(page.getByRole('heading', { name: 'Randevu uygunluğunu yapılandırın' })).toBeVisible()
})
