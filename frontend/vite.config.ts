import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * 개발 환경에서 /api를 백엔드로 프록시한다.
 * 백엔드 포트가 8001이 아니면 frontend/.env.development에서 다음 값을 설정:
 * VITE_API_PROXY_TARGET=http://localhost:8001
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY_TARGET || 'http://localhost:8001'

  return {
    base: '/app/',
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target,
          changeOrigin: true,
        },
        '/terms': {
          target,
          changeOrigin: true,
        },
        '/privacy': {
          target,
          changeOrigin: true,
        },
      },
    },
    build: {
      target: 'es2020',
      sourcemap: false,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules')) {
              if (id.includes('echarts')) return 'vendor-echarts'
              if (id.includes('framer-motion')) return 'vendor-motion'
              if (id.includes('@mui')) return 'vendor-mui'
              if (id.includes('react-dom') || id.includes('react/') || id.includes('react-router')) return 'vendor-react'
              if (id.includes('html2canvas')) return 'vendor-html2canvas'
            }
          },
        },
      },
    },
  }
})
