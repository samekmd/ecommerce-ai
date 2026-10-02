import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// As duas APIs têm /health na raiz, então cada uma ganha um prefixo próprio no proxy.
// O query-agent não tem CORS; o proxy também resolve isso em dev (em produção, o nginx).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ops': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (caminho) => caminho.replace(/^\/ops/, ''),
      },
      '/query': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (caminho) => caminho.replace(/^\/query/, ''),
      },
    },
  },
})
