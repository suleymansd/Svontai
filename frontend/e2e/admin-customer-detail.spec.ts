import { expect, test, type Route } from '@playwright/test'

const localBackendPattern = /^http:\/\/127\.0\.0\.1:800[01]\//
const tenantId = '209a305d-a7ae-4239-90c2-8e0d87f891be'

test('admin customer detail keeps the route tenant id and survives validation errors', async ({ page }) => {
  const requestedPaths: string[] = []
  const pageErrors: string[] = []

  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('dialog', (dialog) => dialog.accept())

  await page.route('**/api/auth/refresh', async (route) => {
    const payload = Buffer.from(JSON.stringify({ portal: 'super_admin', mfa: true })).toString('base64url')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: `header.${payload}.signature`, token_type: 'bearer' }),
    })
  })

  await page.route(localBackendPattern, async (route: Route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    requestedPaths.push(path)

    if (request.method() === 'OPTIONS') {
      await route.fulfill({ status: 204 })
      return
    }

    if (path === '/me') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'admin-1',
          email: 'admin@example.com',
          full_name: 'Test Admin',
          is_admin: true,
        }),
      })
      return
    }

    if (path === `/admin/tenants/${tenantId}` && request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tenant: { id: tenantId, name: 'Test Müşteri', is_active: true },
          owner_name: 'Müşteri Yetkilisi',
          owner_email: 'customer@example.com',
          plan_name: 'free',
          feature_flags: [],
          recent_runs: [],
          recent_incidents: [],
        }),
      })
      return
    }

    if (path === `/admin/tenants/${tenantId}/plan` && request.method() === 'PUT') {
      await route.fulfill({
        status: 422,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: [{ msg: 'Value error, Plan doğrulama bilgisi geçersiz' }],
        }),
      })
      return
    }

    await route.fulfill({ status: 404, contentType: 'application/json', body: '{}' })
  })

  await page.goto(`/admin/customers/${tenantId}`)
  await expect(page.getByRole('heading', { name: 'Test Müşteri' })).toBeVisible()

  await page.getByLabel('Tenant planı').selectOption('pro')
  await page.getByRole('button', { name: 'Planı Etkinleştir' }).click()

  await expect(page.getByText('Plan doğrulama bilgisi geçersiz')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Test Müşteri' })).toBeVisible()
  expect(requestedPaths.some((path) => path.includes('undefined'))).toBe(false)
  expect(pageErrors).toEqual([])
})
