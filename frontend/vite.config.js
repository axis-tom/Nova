import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path';

export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd());

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      open: true,
      proxy: {
        // 代理 API 请求到后端
        '/api': {
          // target: env.VITE_API_BASE_URL || 'http://localhost:8000',
          target: 'http://localhost:8000',
          changeOrigin: true,
        //   rewrite: (path) => path?.replace(/^\/api/, '') || ''
        },
        // WebSocket 代理（如果需要）
        '/ws': {
          target: env.VITE_WS_BASE_URL || 'ws://localhost:8000',
          ws: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: mode === 'development',
      rollupOptions: {
        output: {
          manualChunks: {
            'element-plus': ['element-plus'],
            'vue-vendor': ['vue', 'vue-router', 'pinia'],
          },
        },
      },
    },
    css: {
      preprocessorOptions: {
        // 如果需要使用 SCSS，可以在此配置
      },
    },
  };
});