self.addEventListener('push', (event) => {
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = { body: event.data ? event.data.text() : '' }
  }

  event.waitUntil(
    self.registration.showNotification(payload.title || 'SvontAI çalışıyor', {
      body: payload.body || 'Otomasyonlarınız çalışmaya devam ediyor.',
      icon: '/logo.png',
      badge: '/logo.png',
      tag: payload.tag || 'svontai-activity',
      renotify: false,
      data: {
        url: payload.url || '/dashboard',
        ...payload,
      },
    })
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const targetUrl = new URL(event.notification.data?.url || '/dashboard', self.location.origin).href
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) {
          client.navigate(targetUrl)
          return client.focus()
        }
      }
      return self.clients.openWindow ? self.clients.openWindow(targetUrl) : undefined
    })
  )
})
