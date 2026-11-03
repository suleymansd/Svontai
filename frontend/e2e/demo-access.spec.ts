import { expect, test, type Page } from '@playwright/test'

const token = 'D'.repeat(43)
const backendPattern = /^http:\/\/127\.0\.0\.1:8000\//
const tenantId = '209a305d-a7ae-4239-90c2-8e0d87f891be'
const item = { id: 'demo-1', name: 'Optimageek', tenant_id: tenantId, created_at: '2026-09-24T12:00:00', expires_at: '2026-10-08T12:00:00', last_used_at: null, revoked_at: null, visit_count: 0, status: 'active' }

async function mockPanel(page: Page, admin = false) {
  const user = { id: admin ? 'admin-1' : 'guest-1', email: 'test@example.com', full_name: admin ? 'Admin' : 'Optimageek', is_admin: admin }
  const entitlements = admin ? {} : { plan_type: 'premium', plan_name: 'Profesyonel', demo_access: { expires_at: '2026-10-08T12:00:00Z' } }
  const claims = Buffer.from(JSON.stringify({ portal: admin ? 'super_admin' : 'tenant', mfa: admin })).toString('base64url')
  await page.route('**/api/auth/refresh', route => route.fulfill({ json: { access_token: `header.${claims}.signature` } }))
  await page.route(backendPattern, async route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() === 'OPTIONS') { await route.fulfill({ status: 204 }); return }
    let body: unknown = {}
    if (path === '/me') body = user
    else if (path === '/api/me') body = { user, tenant: admin ? null : { id: tenantId, name: 'Optimageek' }, role: { id: 'role-1', name: admin ? 'system_admin' : 'owner' }, entitlements, permissions: ['tools:read'], feature_flags: {} }
    else if (path === '/onboarding/setup/status') body = { is_completed: false, dismissed: true, progress_percentage: 14 }
    else if (path === '/subscription/usage') body = { ...entitlements, messages_used: 0, message_limit: 10000 }
    else if (path === '/analytics/action-center') body = { required_count: 0, items: [], upcoming_appointments: [] }
    else if (path === '/analytics/operational-report') body = { title: 'Rapor', summary: 'Henüz işlem yok.', text: '', metrics: {} }
    else if (path === '/conversations' || path === '/leads') body = []
    else if (path === '/realtime/events') { await route.fulfill({ status: 200, contentType: 'text/event-stream', body: ': ready\n\n' }); return }
    await route.fulfill({ json: body })
  })
}

test('one link opens Premium directly and survives reload without a form', async ({ page }, testInfo) => {
  const errors: string[] = []
  const exchanges: unknown[] = []
  page.on('pageerror', error => errors.push(error.message))
  await mockPanel(page)
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('demo-test-seeded')) {
      localStorage.setItem('svontai_admin_tenant_context_id', 'previous-tenant')
      sessionStorage.setItem('demo-test-seeded', '1')
    }
  })
  await page.route('**/api/auth/demo-login', async route => {
    exchanges.push(route.request().postDataJSON())
    await route.fulfill({ json: { access_token: 'demo.access.token' } })
  })
  await page.goto(`/demo#token=${token}`)
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 })
  await expect(page.getByRole('heading', { name: 'Premium çalışma alanı' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'AI asistanını dene' })).toBeVisible()
  expect(exchanges).toEqual([{ token }])
  expect(await page.evaluate(() => localStorage.getItem('svontai_admin_tenant_context_id'))).toBeNull()
  expect(await page.evaluate(() => localStorage.getItem('access_token'))).toBeNull()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('premium-panel.png'), fullPage: true })
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Premium çalışma alanı' })).toBeVisible()
  expect(exchanges).toHaveLength(1)
  expect(errors).toEqual([])
})

test('expired link shows a clear error without redirecting to registration', async ({ page }, testInfo) => {
  await page.route('**/api/auth/demo-login', route => route.fulfill({ status: 403, json: { detail: { code: 'DEMO_ACCESS_ENDED', message: 'Bu özel erişim bağlantısı artık aktif değil.' } } }))
  await page.goto(`/demo#token=${token}`)
  await expect(page.getByRole('main').getByRole('alert')).toHaveText('Bu özel erişim bağlantısı artık aktif değil.')
  await expect(page).toHaveURL(/\/demo$/)
  await expect(page.getByRole('link', { name: 'İletişime geç' })).toBeVisible()
  await expect(page.getByRole('textbox')).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('expired-link.png'), fullPage: true })
})

test('temporary failure can be retried without another form or a lost link', async ({ page }) => {
  await mockPanel(page)
  let attempts = 0
  await page.route('**/api/auth/demo-login', route => {
    attempts += 1
    expect(route.request().postDataJSON()).toEqual({ token })
    return route.fulfill(attempts === 1
      ? { status: 503, json: { detail: 'Geçici bağlantı sorunu.' } }
      : { json: { access_token: 'demo.access.token' } })
  })
  await page.goto(`/demo#token=${token}`)
  await page.getByRole('button', { name: 'Tekrar dene' }).click()
  await expect(page.getByRole('heading', { name: 'Premium çalışma alanı' })).toBeVisible()
  await expect(page).toHaveURL(/\/dashboard$/)
  expect(attempts).toBe(2)
})

test('admin creates and revokes a private link', async ({ page }, testInfo) => {
  await mockPanel(page, true)
  let created = false
  let revoked = false
  await page.route(/^http:\/\/127\.0\.0\.1:8000\/admin\/demo-access/, async route => {
    const request = route.request()
    if (request.method() === 'POST') {
      expect(request.postDataJSON()).toEqual({ name: 'Optimageek', days: 14 })
      created = true
      await route.fulfill({ status: 201, json: { ...item, url: `http://127.0.0.1:3106/demo#token=${token}` } })
    } else if (request.method() === 'DELETE') {
      revoked = true
      await route.fulfill({ status: 204 })
    } else {
      await route.fulfill({ json: created ? [{ ...item, status: revoked ? 'revoked' : 'active' }] : [] })
    }
  })
  await page.goto('/admin/demo-access')
  await page.getByLabel('Müşteri / firma adı').fill('Optimageek')
  await page.getByRole('button', { name: 'Link oluştur' }).click()
  await expect(page.getByLabel('Özel erişim bağlantısı')).toHaveValue(new RegExp(`#token=${token}$`))
  await expect(page.getByText('Aktif', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('admin-links.png'), fullPage: true })
  page.on('dialog', dialog => dialog.accept())
  await page.getByRole('button', { name: 'Optimageek: erişimi iptal et' }).click()
  await expect(page.getByText('İptal edildi', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Özel erişim bağlantısı')).toHaveCount(0)
})
