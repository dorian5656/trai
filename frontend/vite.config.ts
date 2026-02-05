// 文件名：frontend/vite.config.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：Vite 构建配置

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      dts: 'src/auto-imports.d.ts',
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    open: true,
    proxy: {
      '/api_trai': {
        target: 'http://192.168.100.119:5777',
        changeOrigin: true,
        // rewrite: (path) => path.replace(/^\/api_trai/, '/api_trai'), // 如果后端路径包含 /api_trai 则不需要 rewrite
      }
    }
  }
})
