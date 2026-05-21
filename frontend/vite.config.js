import { resolve } from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        dashboard: resolve(process.cwd(), 'index.html'),
        shop: resolve(process.cwd(), 'shop.html')
      }
    }
  }
});
