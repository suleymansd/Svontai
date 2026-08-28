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
  await expect(page.getByText('info@svontai.com', { exact: true })).toBeVisible()
  await expect(page.getByText('sales@svontai.com', { exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Ad Soyad')).toBeVisible()
  await expect(page.getByLabel('E-posta')).toBeVisible()
  await expect(page.getByLabel('Mesajınız')).toHaveValue(/PRO planı/)
  await expect(page.getByRole('button', { name: 'Görüşme Talebi Gönder' })).toBeEnabled()
})

test('auth screens omit the removed helper copy', async ({ page }) => {
  await page.goto('/register')
  await expect(page.getByText('Demo workspace açın, ardından kurulum tipinizi seçin', { exact: true })).toHaveCount(0)

  await page.goto('/login')
  await expect(page.getByRole('link', { name: 'E-postanı doğrulamadın mı? Kodu yeniden gönder' })).toHaveCount(0)
})

test('landing login link uses the animated brand button', async ({ page }) => {
  await page.goto('/')

  const loginLink = page.locator('a.animated-login-button[href="/login"]')
  await expect(loginLink).toHaveCount(1)
  await expect(loginLink).toHaveClass(/animated-login-button/)
  await expect(loginLink.locator('.animated-login-arrow')).toHaveCount(2)
  await expect(loginLink.locator('.animated-login-circle')).toHaveCount(1)

  if ((page.viewportSize()?.width || 0) >= 640) {
    await expect(loginLink).toBeVisible()
    await loginLink.hover()
    await expect(loginLink).toHaveCSS('border-radius', '10px')
  }
})

test('landing page shows the current monthly plan prices', async ({ page }) => {
  await page.goto('/#pricing')

  const pricingSection = page.locator('#pricing')
  await expect(pricingSection).toContainText('Başlangıç')
  await expect(pricingSection).toContainText('₺999')
  await expect(pricingSection).toContainText('Profesyonel')
  await expect(pricingSection).toContainText('₺4.999')
  await expect(pricingSection).toContainText('Kurumsal')
  await expect(pricingSection).toContainText('₺14.999')
  await expect(pricingSection).toContainText('Yıllık ödemede 2 ay ücretsiz')
  await expect(pricingSection).toContainText('Tek seferlik kurulum: ₺2.499')
  await expect(pricingSection).toContainText('Tek seferlik kurulum: ₺9.999')
  await expect(pricingSection).toContainText('50.000 AI yanıtı/ay')
  await expect(pricingSection).toContainText('WhatsApp/Meta mesaj')
  await expect(pricingSection).not.toContainText('Sınırsız mesaj')
})

test('landing footer omits the made-in slogan', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText("Türkiye'de ❤️ ile yapıldı", { exact: true })).toHaveCount(0)
  await expect(page.getByText('© 2026 SvontAI. Tüm hakları saklıdır.', { exact: true })).toBeVisible()
})

test('pricing page uses the same commercial pricing contract', async ({ page }) => {
  await page.route('**/billing/config', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ mode: 'manual', payments_enabled: false, contact_url: '/contact' }),
    })
  })
  await page.goto('/pricing')

  await expect(page.getByText(/^₺999\/ay$/)).toBeVisible()
  await expect(page.getByText(/^₺4\.999\/ay$/)).toBeVisible()
  await expect(page.getByText(/^₺14\.999\/ay$/)).toBeVisible()
  await expect(page.getByText('50.000 AI yanıtı/ay', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Yıllık (2 ay hediye)' }).click()
  await expect(page.getByText(/^₺9\.990\/yıl$/)).toBeVisible()
  await expect(page.getByText(/^₺49\.990\/yıl$/)).toBeVisible()
  await expect(page.getByText(/^₺149\.990\/yıl$/)).toBeVisible()
})

test('register enforces the password policy and safely renders API validation errors', async ({ page }) => {
  await page.route('**/auth/register', async (route) => {
    await route.fulfill({
      status: 422,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: [{ msg: 'Value error, Kayıt doğrulama mesajı güvenli gösterildi' }],
      }),
    })
  })

  await page.goto('/register')
  await page.getByLabel('Ad Soyad').fill('Kayıt Kontrol')
  await page.getByLabel('E-posta').fill('register-check@example.com')
  await page.getByLabel('Şifre').fill('Test123!')
  await page.getByRole('checkbox').nth(0).check()
  await page.getByRole('checkbox').nth(1).check()

  const submitButton = page.getByRole('button', { name: 'Ücretsiz Başla' })
  await expect(submitButton).toBeDisabled()

  await page.getByLabel('Şifre').fill('GucluParola123!')
  await expect(submitButton).toBeEnabled()
  await submitButton.click()

  await expect(page.getByText('Kayıt doğrulama mesajı güvenli gösterildi')).toBeVisible()
  await expect(page.getByRole('heading', { name: /Hesap oluşturun/i })).toBeVisible()
})

test('customer guide search opens the matching section', async ({ page }) => {
  await page.goto('/docs')
  await page.getByLabel('Kılavuzda ara').fill('randevu')
  await page.getByRole('link', { name: /Randevular/ }).first().click()
  await expect(page).toHaveURL(/#randevular$/)
  await expect(page.getByRole('heading', { name: 'Randevu uygunluğunu yapılandırın' })).toBeVisible()
})
