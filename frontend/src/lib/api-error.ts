export function getApiErrorMessage(error: any, fallback: string): string {
  const responseData = error?.response?.data
  if (responseData) {
    const detail = responseData?.detail
    if (typeof detail === 'string' && detail.trim()) return detail

    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0]
      if (typeof first?.msg === 'string' && first.msg.trim()) return first.msg
      if (typeof first === 'string' && first.trim()) return first
    }

    const message = responseData?.message
    if (typeof message === 'string' && message.trim()) return message
  }

  if (typeof error?.message === 'string' && error.message.trim()) return error.message
  return fallback
}

