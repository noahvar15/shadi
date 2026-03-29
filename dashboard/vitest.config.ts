import { defineConfig } from 'vitest/config'
import path from 'path'

export default defineConfig({
  test: {
    environment: 'node',
    globals: true,
    setupFiles: ['./src/__tests__/setup.ts'],
    // Expose NEXT_PUBLIC_* env vars so the api.ts client picks them up.
    env: {
      NEXT_PUBLIC_API_URL: 'http://localhost',
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
