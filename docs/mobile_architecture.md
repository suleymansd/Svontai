# SvontAI Mobile Architecture

## Decision

SvontAI Mobile is a separate Expo/React Native client in `mobile/`. It shares the production FastAPI backend, database, workers and tenant authorization model with the Next.js panel. It is not a WebView and does not duplicate backend business logic.

## Boundaries

```text
Next.js web ─┐
             ├─ HTTPS/SSE ─ FastAPI ─ PostgreSQL / Redis ─ workers
Expo mobile ─┘
```

The app may call tenant-scoped APIs only. Gemini, WhatsApp, OpenWA, Twilio, n8n, storage and database credentials are server-only.

## Authentication

Web sessions continue to use an HttpOnly refresh cookie. A native login sends `client=mobile`, an installation ID and platform metadata. The same `/auth/login` endpoint then returns a rotating refresh token for SecureStore. `/auth/refresh` accepts a native refresh body only when the JWT is marked as a mobile token and its installation ID matches.

The access token is never persisted. Refresh rotation includes a unique `jti`, so an older token cannot be replayed after a successful rotation.

## Mobile scope

The app is optimized for daily operator work:

- action center and health summary
- conversations and manual takeover
- per-conversation AI reply policy
- appointments
- notification and account settings

Heavy configuration remains in the web panel: onboarding, bot training, integrations, n8n, invoicing and super-admin operations.

## Realtime and notifications

Foreground message updates will use the existing authenticated SSE stream. Background delivery will use APNs/FCM through a separate mobile-device registry. Opening a notification deep-links to the relevant conversation, appointment or incident. Every foreground transition performs a cursor-based REST reconciliation so push delivery is never treated as the source of truth.

## Release gates

1. Mobile auth and rotation tests pass.
2. Expo lint, TypeScript and iOS/Android bundle exports pass.
3. Physical iOS and Android device acceptance tests pass.
4. Push token rotation and revocation are verified.
5. App icon, screenshots, privacy declarations and reviewer account are complete.
6. TestFlight and Google Play closed testing complete before production rollout.
