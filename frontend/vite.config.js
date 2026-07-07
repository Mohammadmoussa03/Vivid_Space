import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ['extinct-symmetrical-jayce.ngrok-free.dev'],
    // Proxy API + uploaded media to the Django backend so the whole app is
    // reachable through a single (ngrok) origin — no CORS / mixed-content.
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/media': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
