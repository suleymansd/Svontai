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

  await expect(page.getByText('Plan doğrulama bilgisi geçersiz', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Test Müşteri' })).toBeVisible()
  expect(requestedPaths.some((path) => path.includes('undefined'))).toBe(false)
  expect(pageErrors).toEqual([])
})

test('super admin opens and exits the selected customer panel without forbidden requests', async ({ page }) => {
  const tenantScopedRequests: Array<{ path: string; tenantId?: string }> = []
  const pageErrors: string[] = []

  page.on('pageerror', (error) => pageErrors.push(error.message))

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
    const selectedTenantId = request.headers()['x-tenant-id']

    if (request.method() === 'OPTIONS') {
      await route.fulfill({ status: 204 })
      return
    }

    if (selectedTenantId) tenantScopedRequests.push({ path, tenantId: selectedTenantId })

    let body: unknown = {}
    if (path === '/me') {
      body = { id: 'admin-1', email: 'admin@example.com', full_name: 'Test Admin', is_admin: true }
    } else if (path === '/api/me') {
      body = {
        user: { id: 'admin-1', email: 'admin@example.com', full_name: 'Test Admin', is_admin: true },
        tenant: selectedTenantId ? { id: tenantId, name: 'Test Müşteri' } : null,
        role: { id: 'system-admin', name: 'system_admin' },
        permissions: [],
        entitlements: selectedTenantId ? { plan_name: 'Pilot', plan_type: 'pro' } : {},
        feature_flags: {},
      }
    } else if (path === `/admin/tenants/${tenantId}`) {
      body = {
        tenant: { id: tenantId, name: 'Test Müşteri', is_active: true },
        owner_name: 'Müşteri Yetkilisi',
        owner_email: 'customer@example.com',
        plan_name: 'pro',
        feature_flags: [],
        recent_runs: [],
        recent_incidents: [],
      }
    } else if (path === `/admin/tenants/${tenantId}/preview` && request.method() === 'POST') {
      body = { id: tenantId, name: 'Test Müşteri', is_active: true }
    } else if (path === '/onboarding/setup/status') {
      body = { is_completed: true, dismissed: false, progress_percentage: 100 }
    } else if (path === '/subscription/usage') {
      body = { plan_name: 'Pilot', plan_type: 'pro', status: 'active' }
    } else if (path === '/setup/autopilot/status') {
      body = { status: 'ready', health_score: 100, safe_to_autorun: true, required_user_actions: [], diagnostics: [] }
    } else if (path === '/analytics/customer-success') {
      body = { period_days: 30, messages_received: 0, ai_replies: 0, response_coverage: 0, conversations: 0, new_customers: 0, appointments: 0, successful_automations: 0, human_handoffs: 0, estimated_time_saved_minutes: 0, estimate_method: 'test' }
    } else if (path === '/analytics/action-center') {
      body = { generated_at: new Date().toISOString(), window_hours: 24, required_count: 0, items: [], upcoming_appointments: [] }
    } else if (path === '/analytics/operational-report') {
      body = { period: 'today', title: 'Rapor', summary: 'İşlem yok.', text: '', generated_at: new Date().toISOString(), metrics: {} }
    } else if (path === '/conversations' || path === '/leads') {
      body = []
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })

  await page.goto(`/admin/customers/${tenantId}`)
  await expect(page.getByRole('heading', { name: 'Test Müşteri' })).toBeVisible()
  await page.getByRole('button', { name: 'Müşteri Paneline Geç' }).click()

  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByRole('heading', { name: 'Bugün' })).toBeVisible()
  await expect(page.getByText('Test Müşteri').first()).toBeVisible()
  expect(tenantScopedRequests.length).toBeGreaterThan(0)
  expect(tenantScopedRequests.every((request) => request.tenantId === tenantId)).toBe(true)
  expect(pageErrors).toEqual([])

  await page.getByRole('button', { name: "Admin'a Dön" }).click()
  await expect(page).toHaveURL(/\/admin$/)
})
