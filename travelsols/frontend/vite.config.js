import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.replace(/\\/g, '/');
          if (!normalized.includes('/node_modules/')) return;
          if (/\/node_modules\/(react|react-dom|scheduler)\//.test(normalized)) return 'react-vendor';
          return 'chart-vendor';
        }
      }
    }
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000'
    }
  }
})
