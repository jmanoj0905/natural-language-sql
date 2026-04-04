export function extractApiErrorMessage(error, fallback = 'Something went wrong') {
  if (!error) return fallback
  if (typeof error === 'string') return error

  const detail = error.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (detail?.message) return detail.message

  if (error.response?.data?.message) return error.response.data.message
  if (error.message) return error.message

  return fallback
}
