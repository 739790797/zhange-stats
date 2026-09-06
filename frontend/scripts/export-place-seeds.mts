import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import rawMaps from "../src/data/tarkov-dev-maps.json";
import { findInteractiveMap, type TarkovDevMapGroup } from "../src/lib/tarkovMapImages";
import { snapshotUpstreamPlaces } from "../src/lib/tarkovMapPlaceLabels";

const SKIP = new Set([
  "shoreline",
  "streets-of-tarkov",
  "transits",
  "openworld",
]);

const NAME_MAX = 64;

const groups = rawMaps as TarkovDevMapGroup[];
const seed: Record<string, Array<Record<string, unknown>>> = {};
const report: string[] = [];

for (const group of groups) {
  const key = group.normalizedName;
  if (SKIP.has(key)) {
    report.push(`${key}: skip (already seeded or hub)`);
    continue;
  }
  const layer = findInteractiveMap(key);
  if (!layer) {
    report.push(`${key}: no interactive layer`);
    continue;
  }
  const places = snapshotUpstreamPlaces(layer);
  const items: Array<Record<string, unknown>> = [];
  let height = 0;
  let long = 0;
  for (const row of places) {
    const name = row.text;
    if (name.length > NAME_MAX) {
      long += 1;
      report.push(`  LONG ${key}: ${name.length} ${JSON.stringify(name)}`);
    }
    const item: Record<string, unknown> = {
      name,
      x: row.x ?? row.position[0],
      z: row.z ?? row.position[1],
    };
    if (row.size != null) item.size = row.size;
    if ((row.floor || "").trim()) item.floor = row.floor;
    if (Number.isFinite(row.top)) {
      item.top = row.top;
      height += 1;
    }
    if (Number.isFinite(row.bottom)) item.bottom = row.bottom;
    items.push(item);
  }
  if (!items.length) {
    report.push(`${key}: 0 places`);
    continue;
  }
  seed[key] = items;
  report.push(`${key}: ${items.length} places, ${height} with height, ${long} over ${NAME_MAX}`);
}

const here = dirname(fileURLToPath(import.meta.url));
const out = resolve(here, "../../backend/app/services/tarkov/place_upstream_seed.json");
writeFileSync(out, `${JSON.stringify(seed, null, 2)}\n`, "utf8");
console.log(report.join("\n"));
console.log(`wrote ${out}`);
