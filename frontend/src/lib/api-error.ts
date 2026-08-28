function normalizeApiErrorMessage(message: string): string {
  return message.replace(/^Value error,\s*/i, '').trim()
}

export function getErrorDetailMessage(value: unknown, fallback: string, depth = 0): string {
  if (typeof value === 'string' && value.trim()) return normalizeApiErrorMessage(value)
  if (typeof value === 'number' || typeof value === 'bigint') return String(value)
  if (depth >= 3 || value === null || value === undefined) return fallback

  if (Array.isArray(value)) {
    for (const item of value) {
      const message = getErrorDetailMessage(item, '', depth + 1)
      if (message) return message
    }
    return fallback
  }

  if (typeof value === 'object') {
    const record = value as Record<string, unknown>
    for (const key of ['message', 'msg', 'detail', 'error']) {
      const message = getErrorDetailMessage(record[key], '', depth + 1)
      if (message) return message
    }
  }

  return fallback
}

export function getApiErrorMessage(error: any, fallback: string): string {
  const responseData = error?.response?.data
  if (responseData) {
    const detailMessage = getErrorDetailMessage(responseData?.detail, '')
    if (detailMessage) return detailMessage

    const responseMessage = getErrorDetailMessage(responseData?.message, '')
    if (responseMessage) return responseMessage
  }

  if (typeof error?.message === 'string' && error.message.trim()) return error.message
  return fallback
}
