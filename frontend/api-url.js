export function resolveApiUrl(configured, development) {
  const value = (configured?.trim() || (development ? 'http://localhost:8001' : '')).replace(/\/+$/, '')
  if (!value) throw new Error('VITE_API_URL is required for production builds')
  const url = new URL(value)
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
  if ((url.protocol !== 'https:' && !(development && local && url.protocol === 'http:')) || url.username || url.password || url.search || url.hash) {
    throw new Error('VITE_API_URL must use HTTPS, except for local development')
  }
  return value
}
