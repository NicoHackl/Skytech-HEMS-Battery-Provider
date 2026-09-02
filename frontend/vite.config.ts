import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-Proxy statt CORS: im Entwicklungsbetrieb dieselbe Origin wie in Produktion.
// Ports je Anwendung festlegen, nicht raten — mehrere Projekte laufen parallel.
export default defineConfig({
  // base: '/admin/',   // nur setzen, wenn die SPA nicht unter / ausgeliefert wird
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5174,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/media': { target: 'http://127.0.0.1:8080', changeOrigin: true },
    },
  },
})
