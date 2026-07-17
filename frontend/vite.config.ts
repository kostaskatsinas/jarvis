import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev the Vite server proxies API/WS calls to the backend container
// (compose network) or a locally running uvicorn.
const backend = process.env.BACKEND_URL ?? "http://backend:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
      "/ws": { target: backend, ws: true },
    },
  },
});
