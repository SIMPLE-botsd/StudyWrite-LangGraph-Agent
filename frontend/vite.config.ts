import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/writeapi': {
        target: 'http://127.0.0.1:8030',
        changeOrigin: true,
      },
    },
  },
});
