import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const frontendDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  cacheDir: path.resolve(frontendDir, "../data/cache/vite"),
  resolve: {
    alias: {
      "@": path.resolve(frontendDir, "src"),
      "@design-system": path.resolve(frontendDir, "design-system"),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
