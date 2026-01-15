import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteStaticCopy } from 'vite-plugin-static-copy'
import cesium from 'vite-plugin-cesium'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    cesium(),
    viteStaticCopy({
      targets: [
        {
          src: 'node_modules/cesium/Build/Cesium/Workers',
          dest: 'cesium'
        },
        {
          src: 'node_modules/cesium/Build/Cesium/ThirdParty',
          dest: 'cesium'
        },
        {
          src: 'node_modules/cesium/Build/Cesium/Assets',
          dest: 'cesium'
        },
        {
          src: 'node_modules/cesium/Build/Cesium/Widgets',
          dest: 'cesium'
        }
      ]
    })
  ],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  define: {
    CESIUM_BASE_URL: JSON.stringify('/cesium/')
  },
  resolve: {
    alias: {
      '@': '/src'
    }
  }
})
