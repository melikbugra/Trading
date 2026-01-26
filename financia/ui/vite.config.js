import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
const apiHost = process.env.VITE_API_HOST || 'localhost'

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: true,
    proxy: {
      '/strategies': {
        target: `http://${apiHost}:8000`,
        changeOrigin: true
      },
      '/ws': {
        target: `ws://${apiHost}:8000`,
        ws: true
      },
      '/health': {
        target: `http://${apiHost}:8000`,
        changeOrigin: true
      },
      '/markets': {
        target: `http://${apiHost}:8000`,
        changeOrigin: true
      }
    }
  }
})
