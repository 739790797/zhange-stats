import "./dom-shim";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { configureTarkovOcrAssets, terminateTarkovOcrWorker } from "@/lib/tarkovOcrEngine";
import { recognizeKeyboxScreenshot } from "@/lib/tarkovKeyOcrRecognize";
import type { TarkovKeyOcrCatalogKey } from "@/lib/tarkovKeyOcr";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)));
const frontend = path.resolve(root, "..", "..");

type SampleExpect = {
  title: string;
  expect: string[];
  forbid: string[];
  stretch?: string[];
};

const expected = JSON.parse(
  await readFile(path.join(root, "expected.json"), "utf8"),
) as Record<string, SampleExpect>;

const catalog = JSON.parse(
  await readFile(path.join(frontend, "scripts", "ocr-key-catalog.json"), "utf8"),
) as TarkovKeyOcrCatalogKey[];

configureTarkovOcrAssets({
  langPath: path.join(frontend, "public", "tesseract"),
  cacheMethod: "none",
});

const files = (await readdir(root)).filter(
  (name) =>
    /^\d{2}-[a-z0-9-]+\.png$/.test(name) &&
    !name.includes("-row") &&
    !name.includes("-engine") &&
    !name.includes("-overlay"),
);
let failed = 0;

for (const file of files) {
  const id = file.replace(/\.png$/, "");
  const spec = expected[id];
  if (!spec) continue;
  const blob = new Blob([await readFile(path.join(root, file))], { type: "image/png" });
  const { matches } = await recognizeKeyboxScreenshot(blob, catalog);
  const got = new Set(matches.map((row) => row.short_name.trim()));
  const miss = spec.expect.filter((name) => !got.has(name));
  const extra = spec.forbid.filter((name) => got.has(name));
  const stretchHit = (spec.stretch || []).filter((name) => got.has(name));
  const stretchMiss = (spec.stretch || []).filter((name) => !got.has(name));
  const ok = miss.length === 0 && extra.length === 0;
  if (!ok) failed += 1;
  console.log(`\n===== ${id}  ${spec.title}  ${ok ? "PASS" : "GAP"} =====`);
  console.log(`hits ${matches.length}: ${[...got].sort().join("、")}`);
  if (miss.length) console.log(`MISS: ${miss.join("、")}`);
  if (extra.length) console.log(`FORBID: ${extra.join("、")}`);
  if (stretchHit.length) console.log(`STRETCH hit: ${stretchHit.join("、")}`);
  if (stretchMiss.length) console.log(`STRETCH still out: ${stretchMiss.join("、")}`);
}

await terminateTarkovOcrWorker();
if (failed) {
  console.log(`\n${failed} sample(s) still have gaps (product path)`);
  process.exitCode = 1;
} else {
  console.log("\nall corpus samples matched expect/forbid via recognizeKeyboxScreenshot");
}
