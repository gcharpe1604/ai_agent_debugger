import { defineConfig, loadEnv } from 'vite'
import process from 'node:process'
import react from '@vitejs/plugin-react'

// index.html's link-preview tags use __SITE_URL__: the deployed origin from
// VITE_SITE_URL (e.g. https://example.com), or '' for a root-relative URL.
function siteUrl(mode) {
  const url = (loadEnv(mode, process.cwd(), 'VITE_').VITE_SITE_URL || '').trim().replace(/\/+$/, '')
  if (url && !/^https?:\/\/[^/]+$/.test(url)) throw new Error(`VITE_SITE_URL must be an origin like https://example.com, got ${url}`)
  return { name: 'site-url', transformIndexHtml: html => html.replaceAll('__SITE_URL__', url) }
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), siteUrl(mode)],
  server: {
    host: '127.0.0.1', port: 5175, strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8008' } },
  },
}))
