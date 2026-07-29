import * as Sentry from '@sentry/browser'

const isSentryInitialized = () =>
  typeof window !== 'undefined' && window.__SENTRY_INITIALIZED__ === true

export const reportError = (error, context = {}) => {
  if (!isSentryInitialized()) return
  Sentry.captureException(error, { extra: context })
}

export const reportMessage = (message, level = 'info') => {
  if (!isSentryInitialized()) return
  Sentry.captureMessage(message, level)
}
