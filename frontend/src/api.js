import { resolveApiUrl } from '../api-url.js'
const API_URL = resolveApiUrl(import.meta.env.VITE_API_URL, import.meta.env.MODE === 'development')

export default API_URL
