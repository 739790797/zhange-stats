import fs from "node:fs";
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

function readAppVersion(): string {
  try {
    const raw = fs.readFileSync(path.resolve(__dirname, "../VERSION"), "utf8");
    return raw.trim().replace(/^v/i, "") || "dev";
  } catch {
    return "dev";
  }
}

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(readAppVersion()),
  },
  cacheDir: path.resolve(__dirname, "../data/cache/vite"),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    // G2 图表块压缩后约 1.4MB，只在图表路由懒加载；阈值略抬高以免误报。
    chunkSizeWarningLimit: 1600,
    rolldownOptions: {
      output: {
        codeSplitting: {
          // 分组默认连依赖一起收进组块：给 @ant-design/plots 建组会把 React 也拽进去，首屏就得预载整份 G2。
          // 图表交给按路由的懒加载自动拆分；leaflet 没有依赖，单独成组不会牵连别的包。
          groups: [
            {
              name: "leaflet",
              test: /node_modules[\\/]leaflet/,
            },
          ],
        },
      },
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
