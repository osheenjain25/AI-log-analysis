import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/insights': 'http://localhost:3000',
      '/analytics': 'http://localhost:3000',
      '/tickets': 'http://localhost:3000',
      '/query': 'http://localhost:3000',
      '/update-config': 'http://localhost:3000',
      '/get-last-cost-analysis': 'http://localhost:3000',
      '/token': 'http://localhost:3000',
      '/users/me/': 'http://localhost:3000',
    }
  }
})
