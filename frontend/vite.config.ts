import fs from "node:fs";
import path from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/** 本机提供 Tesseract worker/core，避免浏览器去拉 jsDelivr。 */
const TESSERACT_RUNTIME_FILES = [
  { from: ["tesseract.js", "dist", "worker.min.js"], to: "tesseract/worker.min.js" },
  {
    from: ["tesseract.js-core", "tesseract-core-lstm.wasm.js"],
    to: "tesseract/core/tesseract-core-lstm.wasm.js",
  },
  {
    from: ["tesseract.js-core", "tesseract-core-lstm.wasm"],
    to: "tesseract/core/tesseract-core-lstm.wasm",
  },
  {
    from: ["tesseract.js-core", "tesseract-core-simd-lstm.wasm.js"],
    to: "tesseract/core/tesseract-core-simd-lstm.wasm.js",
  },
  {
    from: ["tesseract.js-core", "tesseract-core-simd-lstm.wasm"],
    to: "tesseract/core/tesseract-core-simd-lstm.wasm",
  },
] as const;

function tesseractSrc(root: string, from: readonly string[]): string {
  return path.join(root, "node_modules", ...from);
}

function tesseractContentType(file: string): string {
  if (file.endsWith(".wasm")) return "application/wasm";
  if (file.endsWith(".js")) return "application/javascript";
  return "application/octet-stream";
}

function tesseractAssets(): Plugin {
  const root = path.resolve(__dirname);
  return {
    name: "tesseract-assets",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url || "").split("?")[0];
        const hit = TESSERACT_RUNTIME_FILES.find((row) => url === `/${row.to}`);
        if (!hit) {
          next();
          return;
        }
        const file = tesseractSrc(root, hit.from);
        if (!fs.existsSync(file)) {
          next();
          return;
        }
        res.setHeader("Content-Type", tesseractContentType(file));
        res.setHeader("Cache-Control", "public, max-age=86400");
        fs.createReadStream(file).pipe(res);
      });
    },
    writeBundle(output) {
      const dir = output.dir;
      if (!dir) return;
      for (const row of TESSERACT_RUNTIME_FILES) {
        const src = tesseractSrc(root, row.from);
        if (!fs.existsSync(src)) continue;
        const dest = path.join(dir, row.to);
        fs.mkdirSync(path.dirname(dest), { recursive: true });
        fs.copyFileSync(src, dest);
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), tesseractAssets()],
  cacheDir: path.resolve(__dirname, "../var/cache/vite"),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
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
