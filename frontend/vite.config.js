import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { resolveApiUrl } from './api-url.js'

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, '.', 'VITE_')
  if (command === 'build') resolveApiUrl(env.VITE_API_URL, mode === 'development')
  return { plugins: [react()] }
})
