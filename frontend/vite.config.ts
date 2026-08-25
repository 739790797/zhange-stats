import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  cacheDir: path.resolve(__dirname, "../var/cache/vite"),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: Number(process.env.VITE_DEV_PORT || 6131),
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY || "http://127.0.0.1:6130",
        changeOrigin: true,
        ws: true,
      },
      "/uploads": {
        target: process.env.VITE_API_PROXY || "http://127.0.0.1:6130",
        changeOrigin: true,
      },
      "/health": {
        target: process.env.VITE_API_PROXY || "http://127.0.0.1:6130",
        changeOrigin: true,
      },
    },
  },
});
