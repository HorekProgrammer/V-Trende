import react from '@vitejs/plugin-react'
import { defineConfig, configDefaults } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/sitemap.xml': 'http://127.0.0.1:8000',
      '/media': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.js',
    exclude: [
      ...configDefaults.exclude, 
      '**/e2e/**'                
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
    },
  },
})