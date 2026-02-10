import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const SERVER_URL = env.VITE_APP_SERVER_URL || 'http://localhost:5777'
  const API_BASE_URL = (env.VITE_APP_BASE_URL || '/api_trai/v1').startsWith('/')
    ? env.VITE_APP_BASE_URL || '/api_trai/v1'
    : `/${env.VITE_APP_BASE_URL || 'api_trai/v1'}`

  const proxyKey = API_BASE_URL

  return {
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
        [proxyKey]: {
          target: SERVER_URL,
          changeOrigin: true,
        }
      }
    }
  }
})
