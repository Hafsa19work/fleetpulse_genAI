import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies the API and the WebSocket to the FastAPI process, so the
// browser sees a single origin and CORS never enters the picture during the demo.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
})
