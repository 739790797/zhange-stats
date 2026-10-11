import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  cacheDir: path.resolve(__dirname, "../data/cache/vite"),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
