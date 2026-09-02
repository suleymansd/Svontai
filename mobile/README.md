# SvontAI Mobile

Native iOS and Android operations client for SvontAI. The app uses the existing FastAPI API and never connects directly to PostgreSQL, Redis, n8n, OpenWA, or third-party provider credentials.

## Requirements

- Node.js 20 or 22
- npm 10+
- Xcode for local iOS builds
- Android Studio for local Android builds

## Local development

```bash
cp .env.example .env.local
npm ci
npm run check
npm run ios
```

`EXPO_PUBLIC_API_URL` is public configuration, not a secret. Provider credentials must remain on the backend.

## Security model

- Access tokens live only in process memory.
- Rotating refresh tokens are stored with Expo SecureStore (iOS Keychain / Android Keystore).
- Refresh tokens are bound to a persistent installation ID.
- A failed refresh clears the local session and returns the user to login.
- Super-admin login is intentionally unavailable in the mobile client.

## Current first release

- Email, password, 2FA and email-verification aware login
- Daily operations dashboard
- Conversation search and AI reply policy control
- Conversation history and manual WhatsApp reply
- Appointment list
- Tenant and secure-session profile

Push notifications, biometric app lock, offline outbox and app-store signing are tracked as the next delivery phase.

## Validation

```bash
npm run check
npx expo export --platform ios --platform android --output-dir dist-check
```
