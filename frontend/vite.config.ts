import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// 后端地址：通过环境变量 VITE_BACKEND_URL 指定远程服务器
// 本地: 默认 http://127.0.0.1:8000
// AutoDL: VITE_BACKEND_URL=http://<autodl-ip>:8000 npx vite dev
const backendUrl = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'
const wsUrl = backendUrl.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/styles/variables" as *;`,
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
      },
      '/ws': {
        target: wsUrl,
        ws: true,
      },
    },
  },
})
