import { expect, test, type Page, type Route } from '@playwright/test'

const localBackendPattern = /^http:\/\/127\.0\.0\.1:800[01]\//

const autopilotStatus = {
  status: 'ready',
  health_score: 94,
  safe_to_autorun: true,
  business_profile: { status: 'ready', industry: 'service', source: 'customer' },
  concierge_enrichment: null,
  required_user_actions: [],
  diagnostics: [],
  latest_verification: null,
}

const verificationResult = {
  status: 'ready',
  ready_for_launch: true,
  score: 96,
  summary: 'Sistem satış kullanımı için hazır.',
  failed_critical: [],
  warning_count: 1,
  run_id: 'verification-1',
  checks: [
    { key: 'database', label: 'Veritabanı', status: 'passed', message: 'Veritabanı bağlantısı çalışıyor.', critical: true },
    { key: 'push_notifications', label: 'Telefon bildirimleri', status: 'warning', message: 'Telefon bildirimi henüz etkinleştirilmemiş.', critical: false },
  ],
}

async function mockBackend(page: Page) {
  let aiReplyEnabled = true
  await page.addInitScript(() => {
    localStorage.setItem('ui-storage', JSON.stringify({ state: { sidebarOpen: false, theme: 'light' }, version: 0 }))
  })

  await page.route('**/api/auth/login', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'test-access-token', token_type: 'bearer' }),
    })
  })

  await page.route('**/api/auth/refresh', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'test-access-token', token_type: 'bearer' }),
    })
  })

  await page.route(localBackendPattern, async (route: Route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    let body: unknown = {}

    if (path === '/api/me') {
      body = {
        user: { id: 'user-1', email: 'customer@example.com', full_name: 'Test Müşteri', is_admin: false },
        tenant: { id: 'tenant-1', name: 'Test İşletmesi' },
        role: { id: 'role-1', name: 'owner' },
        permissions: ['tools:read', 'settings:write'],
        entitlements: {},
        feature_flags: {},
      }
    } else if (path === '/onboarding/setup/status') {
      body = { is_completed: true, dismissed: false, progress_percentage: 100 }
    } else if (path === '/subscription/usage') {
      body = { plan_name: 'Pilot', features: { operator_takeover: true } }
    } else if (path === '/setup/autopilot/status') {
      body = autopilotStatus
    } else if (path === '/setup/autopilot/verify' && request.method() === 'POST') {
      body = verificationResult
    } else if (path === '/integrations/diagnostics') {
      body = { health_score: 94, items: [] }
    } else if (path === '/analytics/customer-success') {
      body = {
        period_days: 30,
        messages_received: 42,
        ai_replies: 38,
        response_coverage: 90.5,
        conversations: 12,
        new_customers: 7,
        appointments: 4,
        successful_automations: 15,
        human_handoffs: 2,
        estimated_time_saved_minutes: 145,
        estimate_method: 'Test katsayısı',
      }
    } else if (path === '/analytics/action-center') {
      body = {
        generated_at: new Date().toISOString(),
        window_hours: 24,
        required_count: 1,
        items: [{
          id: 'handoff:conversation-1',
          kind: 'human_handoff',
          severity: 'high',
          title: 'Müşteri yanıt bekliyor',
          description: 'Ayşe Yılmaz insan desteği bekliyor.',
          href: '/dashboard/operator?conversation=conversation-1',
          cta_label: 'Konuşmayı Aç',
          occurred_at: new Date().toISOString(),
        }],
        upcoming_appointments: [{
          id: 'appointment-1',
          customer_name: 'Mehmet Kaya',
          subject: 'Tanışma görüşmesi',
          starts_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
          duration_minutes: 30,
          href: '/dashboard/appointments',
        }],
      }
    } else if (path === '/analytics/operational-report') {
      body = {
        period: 'today',
        title: 'Test İşletmesi Raporu',
        summary: '12 mesaj alındı ve 10 otomatik yanıt gönderildi.',
        text: 'Test raporu',
        generated_at: new Date().toISOString(),
        metrics: { incoming_messages: 12, ai_replies: 10, response_rate: 83.3, leads: 2, appointments: 1, failed_automations: 0 },
      }
    } else if (path === '/bots' && request.method() === 'GET') {
      body = []
    } else if (path === '/bots/assistant-profile') {
      body = {
        assistant: {
          id: 'bot-1',
          name: 'Test İşletmesi Asistanı',
          description: 'Müşteri sorularını işletme bilgileriyle yanıtlar.',
          is_active: true,
          primary_color: '#0891b2',
        },
        training: {
          goal: 'mixed',
          tone: 'professional',
          response_length: 'balanced',
          price_policy: 'known_only',
          handoff_mode: 'automatic',
          business_summary: 'Test işletmesi hafta içi 09:00-18:00 arasında hizmet verir.',
        },
        capabilities: [],
        completion_percent: 100,
      }
    } else if (path === '/bots/bot-1/simulate' && request.method() === 'POST') {
      body = {
        reply: 'Hafta içi 09:00-18:00 arasında hizmet veriyoruz.',
        safe_mode: 'simulation',
        history_count: 1,
        latency_ms: 35,
      }
    } else if (path === '/bots/assistant-profile/trainer/message' && request.method() === 'POST') {
      body = {
        session_id: 'trainer-session-1',
        status: 'ready',
        assistant_message: 'Kargo soruları için uzman taslağını hazırladım.',
        proposal: {
          name: 'Kargo Takip Uzmanı',
          description: 'Kargo sorularında sipariş numarasını alır.',
          example_questions: ['Kargom nerede?'],
          answer: 'Önce sipariş numarasını isteyin.',
          behavior_instruction: 'Durum uydurmayın ve sipariş numarasını isteyin.',
        },
      }
    } else if (path === '/bots/assistant-profile/trainer/trainer-session-1/apply' && request.method() === 'POST') {
      body = {
        session_id: 'trainer-session-1',
        status: 'applied',
        assistant_message: 'Kargo Takip Uzmanı oluşturuldu ve Ana Asistanınıza bağlandı.',
        bot: {
          id: 'specialist-1',
          name: 'Kargo Takip Uzmanı',
          description: 'Kargo sorularında sipariş numarasını alır.',
          is_active: true,
          assistant_type: 'specialist',
        },
        knowledge_items_created: 1,
      }
    } else if (path === '/conversations') {
      body = [{
        id: 'conversation-1',
        bot_id: 'bot-1',
        external_user_id: '905551112233',
        source: 'whatsapp',
        status: 'ai_active',
        ai_reply_enabled: aiReplyEnabled,
        customer_name: 'Ayşe Yılmaz',
        customer_phone: '+90 555 111 22 33',
        last_message: 'Merhaba',
        last_message_at: new Date().toISOString(),
        extra_data: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }]
    } else if (path === '/conversations/conversation-1/ai-reply' && request.method() === 'PATCH') {
      aiReplyEnabled = Boolean(request.postDataJSON()?.enabled)
      body = {
        id: 'conversation-1',
        bot_id: 'bot-1',
        external_user_id: '905551112233',
        source: 'whatsapp',
        status: 'ai_active',
        ai_reply_enabled: aiReplyEnabled,
        customer_name: 'Ayşe Yılmaz',
        customer_phone: '+90 555 111 22 33',
        last_message: 'Merhaba',
        last_message_at: new Date().toISOString(),
        messages: [{ id: 'message-1', conversation_id: 'conversation-1', sender: 'user', content: 'Merhaba', created_at: new Date().toISOString() }],
        extra_data: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
    } else if (path === '/conversations/conversation-1') {
      body = {
        id: 'conversation-1',
        bot_id: 'bot-1',
        external_user_id: '905551112233',
        source: 'whatsapp',
        status: 'ai_active',
        ai_reply_enabled: aiReplyEnabled,
        customer_name: 'Ayşe Yılmaz',
        customer_phone: '+90 555 111 22 33',
        last_message: 'Merhaba',
        last_message_at: new Date().toISOString(),
        messages: [{ id: 'message-1', conversation_id: 'conversation-1', sender: 'user', content: 'Merhaba', created_at: new Date().toISOString() }],
        extra_data: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
    } else if (path === '/leads' || path === '/calls' || path === '/voice-automation/intents' || path === '/voice-automation/jobs') {
      body = []
    } else if (path === '/voice-automation/capabilities') {
      body = { mode: 'live', live_ready: true, provider: 'twilio', supported_providers: ['twilio'] }
    } else if (path === '/voice-automation/settings') {
      body = {
        enabled: true,
        provider: 'twilio',
        from_number: '+905551112233',
        allow_appointment_booking: true,
        require_explicit_call_request: true,
        allowed_triggers_json: ['explicit_call_request'],
        max_attempts_per_lead: 2,
        cooldown_minutes: 240,
        daily_call_limit: 30,
      }
    } else if (path === '/voice-automation/test-call' && request.method() === 'POST') {
      body = { id: 'intent-1', status: 'queued' }
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: {
        'Access-Control-Allow-Origin': 'http://127.0.0.1:3100',
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Tenant-ID',
        'Access-Control-Allow-Methods': 'GET, POST, PATCH, PUT, DELETE, OPTIONS',
      },
      body: JSON.stringify(body),
    })
  })
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => {
    const width = document.documentElement.clientWidth
    const offenders = Array.from(document.querySelectorAll<HTMLElement>('body *'))
      .map((element) => ({
        element: `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ''}.${Array.from(element.classList).join('.')}`,
        left: Math.round(element.getBoundingClientRect().left),
        right: Math.round(element.getBoundingClientRect().right),
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
      }))
      .filter((item) => item.right > width + 1)
      .sort((a, b) => (b.scrollWidth - b.clientWidth) - (a.scrollWidth - a.clientWidth))
      .slice(0, 12)
    const widest = Array.from(document.querySelectorAll<HTMLElement>('body *'))
      .sort((a, b) => b.getBoundingClientRect().right - a.getBoundingClientRect().right)[0]
    const ancestors = []
    let current: HTMLElement | null = widest
    while (current && ancestors.length < 8) {
      const rect = current.getBoundingClientRect()
      ancestors.push({
        element: `${current.tagName.toLowerCase()}.${Array.from(current.classList).join('.')}`,
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        clientWidth: current.clientWidth,
        scrollWidth: current.scrollWidth,
      })
      current = current.parentElement
    }
    return { width, scrollWidth: document.documentElement.scrollWidth, offenders, ancestors }
  })
  expect(dimensions.scrollWidth, JSON.stringify({ offenders: dimensions.offenders, ancestors: dimensions.ancestors })).toBeLessThanOrEqual(dimensions.width + 1)
}

async function openAuthenticated(page: Page, path: string) {
  const authState = {
    state: {
      user: { id: 'user-1', email: 'customer@example.com', full_name: 'Test Müşteri', is_admin: false },
      tenant: { id: 'tenant-1', name: 'Test İşletmesi' },
      role: { id: 'role-1', name: 'owner' },
      permissions: ['tools:read', 'settings:write'],
      entitlements: {},
      featureFlags: {},
      isAuthenticated: true,
    },
    version: 0,
  }

  if (path !== '/dashboard') {
    await page.addInitScript(({ state }) => {
      localStorage.setItem('auth-storage', JSON.stringify(state))
    }, { state: authState })
    await page.goto(path)
    await expect(page).toHaveURL(path)
    return
  }

  await page.goto('/login')
  await page.getByLabel('E-posta').fill('customer@example.com')
  await page.getByLabel('Şifre').fill('Password123!')
  await page.getByRole('button', { name: 'Giriş Yap' }).click()
  await expect(page).toHaveURL(/\/dashboard/)
  if (path !== '/dashboard') await page.goto(path)
}

test.beforeEach(async ({ page }) => {
  await mockBackend(page)
})

test('customer dashboard shows real outcomes without overflow', async ({ page }) => {
  await openAuthenticated(page, '/dashboard')
  await expect(page.getByRole('heading', { name: 'Bugün' })).toBeVisible()
  await expect(page.getByText('Müdahaleniz gereken 1 işlem var')).toBeVisible()
  await expect(page.getByText('Ayşe Yılmaz insan desteği bekliyor.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Konuşmayı Aç' })).toHaveAttribute(
    'href',
    '/dashboard/operator?conversation=conversation-1',
  )
  await expect(page.getByRole('heading', { name: 'Önümüzdeki 24 saat' })).toBeVisible()
  await expect(page.getByText('Mehmet Kaya')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Son 30 gün' })).toBeVisible()
  await expect(page.getByText('2.4 saat')).toBeVisible()

  if ((page.viewportSize()?.width || 0) < 1024) {
    await page.getByRole('button', { name: 'Ana menüyü aç' }).click()
  }
  await expect(page.getByRole('link', { name: 'Bugün' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'WhatsApp Bağlantısı' })).toBeHidden()
  await page.getByText('Yönetim ve Ayarlar').click()
  await expect(page.getByRole('link', { name: 'WhatsApp Bağlantısı' })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('assistant simulator previews a reply without creating customer data', async ({ page }) => {
  const mutatingPaths: string[] = []
  page.on('request', (request) => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) {
      mutatingPaths.push(new URL(request.url()).pathname)
    }
  })

  await openAuthenticated(page, '/dashboard/bots')
  await page.getByRole('button', { name: 'Yanıtı Dene' }).click()
  await expect(page.getByRole('heading', { name: 'Yayın Öncesi Mesaj Simülatörü' })).toBeVisible()
  await expect(page.getByText('Bu ekran WhatsApp mesajı, müşteri veya randevu kaydı oluşturmaz.')).toBeVisible()

  await page.getByPlaceholder('Müşterinin yazacağı mesaj...').fill('Çalışma saatleriniz nedir?')
  await page.getByRole('button', { name: 'Mesajı dene' }).click()
  await expect(page.getByText('Hafta içi 09:00-18:00 arasında hizmet veriyoruz.')).toBeVisible()

  expect(
    mutatingPaths.filter(
      (path) => !path.startsWith('/product-analytics/') && path !== '/api/auth/refresh',
    ),
  ).toEqual(['/bots/bot-1/simulate'])
  await expectNoHorizontalOverflow(page)
})

test('contact can be excluded from AI replies in conversations', async ({ page }) => {
  await openAuthenticated(page, '/dashboard/conversations')
  await page.getByRole('button', { name: /Ayşe Yılmaz/ }).click()

  const aiSwitch = page.getByRole('switch', { name: 'Bu kişi için AI otomatik yanıt' })
  await expect(aiSwitch).toBeChecked()
  await aiSwitch.click()

  await expect(aiSwitch).not.toBeChecked()
  await expect(page.getByText('Kişi AI yanıtlarından hariç tutuldu', { exact: true })).toBeVisible()
  await expect(page.getByText('Bu kişi hariç tutuldu')).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('assistant can create a reviewed specialist through conversation', async ({ page }) => {
  const mutatingPaths: string[] = []
  page.on('request', (request) => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) {
      mutatingPaths.push(new URL(request.url()).pathname)
    }
  })

  await openAuthenticated(page, '/dashboard/bots')
  await page.getByRole('button', { name: 'Sohbetle Uzman Oluştur' }).click()
  await expect(page.getByRole('heading', { name: 'AI Eğitim Asistanı' })).toBeVisible()
  await page.getByPlaceholder(/Kargo nerede/).fill('Kargom nerede diye sorulursa sipariş numarasını istesin.')
  await page.getByRole('button', { name: 'Eğitim mesajını gönder' }).click()

  await expect(page.getByRole('heading', { name: 'Kargo Takip Uzmanı' })).toBeVisible()
  await expect(page.getByText('Önce sipariş numarasını isteyin.')).toBeVisible()
  await page.getByRole('button', { name: 'Oluştur ve Etkinleştir' }).click()
  await expect(page.getByText('Uzman Ana Asistanınıza bağlandı.')).toBeVisible()

  expect(
    mutatingPaths.filter(
      (path) => !path.startsWith('/product-analytics/') && path !== '/api/auth/refresh',
    ),
  ).toEqual([
    '/bots/assistant-profile/trainer/message',
    '/bots/assistant-profile/trainer/trainer-session-1/apply',
  ])
  await expectNoHorizontalOverflow(page)
})

test('one-click system verification renders actionable checks', async ({ page }) => {
  await openAuthenticated(page, '/dashboard/autopilot')
  await page.getByRole('button', { name: 'Sistemi Test Et' }).click()
  await expect(page.getByText('Sistem satış kullanımı için hazır.', { exact: true })).toBeVisible()
  await expect(page.getByText('Veritabanı bağlantısı çalışıyor.', { exact: true })).toBeVisible()
  await expectNoHorizontalOverflow(page)
})

test('live test call requires explicit consent', async ({ page }) => {
  await openAuthenticated(page, '/dashboard/calls')
  await page.getByLabel('Telefon', { exact: true }).fill('+905551112233')
  const createButton = page.getByRole('button', { name: 'Test Oluştur' })
  await expect(createButton).toBeDisabled()
  await page.getByRole('checkbox', { name: 'Aranacak kişinin bu test aramasına izin verdiğini onaylıyorum.' }).check()
  await expect(createButton).toBeEnabled()
  await expectNoHorizontalOverflow(page)
})
