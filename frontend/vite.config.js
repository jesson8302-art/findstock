import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// 백엔드(FastAPI) 기본 포트: 8000
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
