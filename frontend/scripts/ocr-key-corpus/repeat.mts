import "./dom-shim";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { configureTarkovOcrAssets, terminateTarkovOcrWorker } from "@/lib/tarkovOcrEngine";
import { recognizeKeyboxScreenshot } from "@/lib/tarkovKeyOcrRecognize";
import type { TarkovKeyOcrCatalogKey } from "@/lib/tarkovKeyOcr";

const RUNS = Number(process.env.OCR_REPEAT || 5);
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

function rate(n: number, total: number) {
  return `${n}/${total} (${((100 * n) / total).toFixed(0)}%)`;
}

const files = (await readdir(root)).filter(
  (name) =>
    /^\d{2}-[a-z0-9-]+\.png$/.test(name) &&
    !name.includes("-row") &&
    !name.includes("-engine") &&
    !name.includes("-overlay"),
);
const samples = files
  .map((file) => file.replace(/\.png$/, ""))
  .filter((id) => expected[id]);

type SampleRun = {
  pass: boolean;
  hits: string[];
  miss: string[];
  extra: string[];
  stretchHit: string[];
};

const bySample = new Map<string, SampleRun[]>();
for (const id of samples) bySample.set(id, []);

const started = Date.now();
for (let run = 1; run <= RUNS; run += 1) {
  console.log(`\n######## run ${run}/${RUNS} ########`);
  for (const id of samples) {
    const spec = expected[id];
    const blob = new Blob([await readFile(path.join(root, `${id}.png`))], {
      type: "image/png",
    });
    const { matches } = await recognizeKeyboxScreenshot(blob, catalog);
    const got = [...new Set(matches.map((row) => row.short_name.trim()))].sort();
    const miss = spec.expect.filter((name) => !got.includes(name));
    const extra = spec.forbid.filter((name) => got.includes(name));
    const stretchHit = (spec.stretch || []).filter((name) => got.includes(name));
    const pass = miss.length === 0 && extra.length === 0;
    bySample.get(id)!.push({ pass, hits: got, miss, extra, stretchHit });
    console.log(
      `  ${id}  ${pass ? "PASS" : "GAP"}  hits=${got.length}` +
        (miss.length ? `  MISS=${miss.join(",")}` : "") +
        (extra.length ? `  FORBID=${extra.join(",")}` : "") +
        (stretchHit.length ? `  STRETCH=${stretchHit.join(",")}` : ""),
    );
  }
}

await terminateTarkovOcrWorker();

console.log(`\n========== 汇总  ${RUNS} 次  ${((Date.now() - started) / 1000).toFixed(1)}s ==========`);
console.log("(recognizeKeyboxScreenshot)");

let allPassRuns = 0;
for (let run = 0; run < RUNS; run += 1) {
  if (samples.every((id) => bySample.get(id)![run].pass)) allPassRuns += 1;
}
console.log(`全夹具 PASS: ${rate(allPassRuns, RUNS)}`);

for (const id of samples) {
  const spec = expected[id];
  const runs = bySample.get(id)!;
  const passN = runs.filter((row) => row.pass).length;
  const names = new Set<string>();
  for (const row of runs) for (const name of row.hits) names.add(name);
  const counts = [...names]
    .map((name) => ({
      name,
      n: runs.filter((row) => row.hits.includes(name)).length,
    }))
    .sort((a, b) => b.n - a.n || a.name.localeCompare(b.name, "zh"));
  const unstable = counts.filter((row) => row.n > 0 && row.n < RUNS);
  const hitLens = runs.map((row) => row.hits.length);
  const uniqueSets = new Set(runs.map((row) => row.hits.join("|")));

  console.log(`\n===== ${id}  ${spec.title} =====`);
  console.log(
    `PASS: ${rate(passN, RUNS)}  命中数 ${Math.min(...hitLens)}–${Math.max(...hitLens)}  不同结果集 ${uniqueSets.size}`,
  );
  const missCounts = spec.expect
    .map((name) => ({ name, n: runs.filter((row) => row.miss.includes(name)).length }))
    .filter((row) => row.n > 0);
  const forbidCounts = spec.forbid
    .map((name) => ({ name, n: runs.filter((row) => row.extra.includes(name)).length }))
    .filter((row) => row.n > 0);
  if (missCounts.length) {
    console.log(`漏 expect: ${missCounts.map((row) => `${row.name} ${rate(row.n, RUNS)}`).join("；")}`);
  } else {
    console.log("漏 expect: 无");
  }
  if (forbidCounts.length) {
    console.log(`误勾 forbid: ${forbidCounts.map((row) => `${row.name} ${rate(row.n, RUNS)}`).join("；")}`);
  } else {
    console.log("误勾 forbid: 无");
  }
  if (unstable.length) {
    console.log("不稳定:");
    for (const row of unstable) console.log(`  ${row.name}  ${rate(row.n, RUNS)}`);
  } else {
    console.log("不稳定: 无");
  }
}
