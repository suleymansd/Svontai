import * as Sentry from '@sentry/nextjs'

const release = () => {
  // Only NEXT_PUBLIC_* variables are inlined into the browser bundle.
  const sha = process.env.NEXT_PUBLIC_SENTRY_RELEASE || process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA
  return sha ? `svontai-web@${sha}` : undefined
}

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NEXT_PUBLIC_APP_ENV || process.env.NODE_ENV,
  tracesSampleRate: 0.05,
  sendDefaultPii: false,
  release: release(),
  enabled: Boolean(process.env.NEXT_PUBLIC_SENTRY_DSN),
})

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart
