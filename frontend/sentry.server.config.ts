import * as Sentry from '@sentry/nextjs'

const release = () => {
  const sha = process.env.SENTRY_RELEASE || process.env.VERCEL_GIT_COMMIT_SHA || process.env.GIT_COMMIT || process.env.NEXT_PUBLIC_SENTRY_RELEASE
  return sha ? `svontai-web@${sha}` : undefined
}

Sentry.init({
  dsn: process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_APP_ENV || process.env.NODE_ENV,
  tracesSampleRate: 0.05,
  sendDefaultPii: false,
  release: release(),
  enabled: Boolean(process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN),
})
