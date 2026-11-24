import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Radix layers add render work in jsdom; the slowest trace tests take ~3 s alone
  // and over 5 s when every file runs in parallel.
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.js'], restoreMocks: true, testTimeout: 15000 },
})
