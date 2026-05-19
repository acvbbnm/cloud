import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    // Windows 환경에서 IPv4(127.0.0.1) + IPv6(::1) 둘 다 listen 하도록 강제.
    // 기본값(true 미지정 시) 은 IPv6 only 로 떠서 브라우저 localhost → IPv4 해석 시 접속 실패.
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
