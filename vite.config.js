import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Python API (backend/): `uvicorn backend.main:app --port 8000`
const API_TARGET = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000';
const pythonApi = { target: API_TARGET, changeOrigin: false };

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  server: {
    // /api/companies stays a Vercel Node function (dev falls back to local config).
    proxy: {
      '/api/health': pythonApi,
      '/api/ai': pythonApi,
      '/api/resume': pythonApi,
      '/api/jobs': pythonApi,
    },
  },
});
