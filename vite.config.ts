import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  server: {
    proxy: {
      '/api': {
        // Use 127.0.0.1 — localhost may resolve to IPv6 where another app (e.g. Next.js) owns :3000
        target: 'http://127.0.0.1:3000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        // NLQ/FAQ queries can legitimately run for several minutes.
        timeout: 900000,
        proxyTimeout: 900000,
      },
    },
  },
});
