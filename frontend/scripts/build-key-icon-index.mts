/**
 * 从目录钥匙图标生成 NCC 指纹。
 * 本地缓存优先，再试 EfTIcons / tarkov.dev。
 */
import { createCanvas, loadImage } from "@napi-rs/canvas";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  encodeIconGray,
  KEY_ICON_TEMPLATE_SIZE,
  sampleIconFromRgba,
  type TarkovKeyIconIndexFile,
} from "../src/lib/tarkovKeyIconMatch";
import type { TarkovKeyOcrCatalogKey } from "../src/lib/tarkovKeyOcr";

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const catalogPath = path.join(frontend, "scripts", "ocr-key-catalog.json");
const cacheDir = path.join(frontend, "scripts", "ocr-key-icons");
const legacyCache = path.join(frontend, "scripts", "ocr-keybox-samples", "icons");
const outPath = path.join(frontend, "src", "lib", "tarkovKeyIconIndex.json");
const SLOT = 64;

const catalog = JSON.parse(await readFile(catalogPath, "utf8")) as TarkovKeyOcrCatalogKey[];

await mkdir(cacheDir, { recursive: true });

function iconUrls(id: string, iconLink: string): string[] {
  const out: string[] = [];
  const link = (iconLink || "").trim();
  if (link) out.push(link);
  out.push(`https://assets.tarkov.dev/${id}-icon.webp`);
  out.push(`https://raw.githubusercontent.com/RatScanner/EfTIcons/master/uid/${id}.png`);
  return [...new Set(out)];
}

async function readCached(id: string): Promise<Buffer | null> {
  for (const dir of [cacheDir, legacyCache]) {
    for (const ext of [".png", ".webp", ".jpg"]) {
      try {
        return await readFile(path.join(dir, `${id}${ext}`));
      } catch {
        /* try next */
      }
    }
  }
  return null;
}

async function downloadIcon(id: string, iconLink: string): Promise<Buffer | null> {
  const cached = await readCached(id);
  if (cached && cached.length > 80) return cached;
  for (const url of iconUrls(id, iconLink)) {
    try {
      const resp = await fetch(url, {
        headers: { "User-Agent": "zhange-stats-key-icon-index" },
      });
      if (!resp.ok) continue;
      const buf = Buffer.from(await resp.arrayBuffer());
      if (buf.length < 80) continue;
      const ext = url.includes(".webp") ? ".webp" : ".png";
      await writeFile(path.join(cacheDir, `${id}${ext}`), buf);
      return buf;
    } catch {
      /* try next */
    }
  }
  return null;
}

function sampleFromIconBuffer(buf: Buffer) {
  return loadImage(buf).then((image) => {
    const canvas = createCanvas(SLOT, SLOT);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#161616";
    ctx.fillRect(0, 0, SLOT, SLOT);
    const scale = Math.min(SLOT / image.width, SLOT / image.height) * 0.9;
    const w = Math.max(1, image.width * scale);
    const h = Math.max(1, image.height * scale);
    ctx.drawImage(image, (SLOT - w) / 2, (SLOT - h) / 2, w, h);
    const pixels = ctx.getImageData(0, 0, SLOT, SLOT);
    return sampleIconFromRgba(pixels.data, SLOT, SLOT, {
      x: 4,
      y: 4,
      width: SLOT - 8,
      height: SLOT - 8,
    }, KEY_ICON_TEMPLATE_SIZE);
  });
}

const items: TarkovKeyIconIndexFile["items"] = [];
let missing = 0;
const keys = catalog.filter((key) => (key.id || "").trim());
const CONCURRENCY = 8;
for (let i = 0; i < keys.length; i += CONCURRENCY) {
  const chunk = keys.slice(i, i + CONCURRENCY);
  const rows = await Promise.all(
    chunk.map(async (key) => {
      const id = key.id.trim();
      const buf = await downloadIcon(id, key.icon_link || "");
      if (!buf) return { id, short: key.short_name, item: null as TarkovKeyIconIndexFile["items"][number] | null };
      const sample = await sampleFromIconBuffer(buf);
      if (!sample) return { id, short: key.short_name, item: null };
      return {
        id,
        short: key.short_name,
        item: {
          id,
          gray: encodeIconGray(sample.gray),
          r: Math.round(sample.r),
          g: Math.round(sample.g),
          b: Math.round(sample.b),
          chromaRatio: Number(sample.chromaRatio.toFixed(3)),
        },
      };
    }),
  );
  for (const row of rows) {
    if (!row.item) {
      missing += 1;
      console.warn(`missing icon ${row.id} ${row.short}`);
      continue;
    }
    items.push(row.item);
  }
  console.log(`indexed ${Math.min(i + CONCURRENCY, keys.length)}/${keys.length}`);
}

const file: TarkovKeyIconIndexFile = { size: KEY_ICON_TEMPLATE_SIZE, items };
await writeFile(outPath, `${JSON.stringify(file)}\n`, "utf8");
console.log(`wrote ${items.length} templates to ${path.relative(frontend, outPath)}`);
if (missing) console.log(`missing ${missing}`);
