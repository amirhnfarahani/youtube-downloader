import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],

  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,

    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },

      // Fonts are served by Flask from /font/*
      // This makes the local Vite dev server load the same fonts as production.
      '/font': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
