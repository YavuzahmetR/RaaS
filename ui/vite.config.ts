import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev-time proxy mirrors the nginx config used in the container: the app
// always talks to relative /api/* so no CORS and no per-env base URLs.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
