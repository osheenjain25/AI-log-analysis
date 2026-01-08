import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/insights': 'http://localhost:5000',
      '/analytics': 'http://localhost:5000',
      '/tickets': 'http://localhost:5000',
      '/query': 'http://localhost:5000',
      '/config': 'http://localhost:5000',
    }
  }
})
