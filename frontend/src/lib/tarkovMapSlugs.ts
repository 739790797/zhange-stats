/** 地图 slug 等价 / 规范化与备战地图选项：轻模块，塔科夫外壳常驻，不拖整份 tarkovRaidPrep。 */

import { TARKOV_MAPS } from "@/lib/tarkovHomeNav";

/** 与后端 MAP_SLUG_EQUIV_GROUPS 对齐。 */
export const MAP_SLUG_EQUIV_GROUPS: readonly (readonly string[])[] = [
  ["streets", "streets-of-tarkov"],
  ["lab", "the-lab"],
  ["labyrinth", "the-labyrinth"],
  ["night-factory", "factory-night"],
  ["ground-zero", "ground-zero-21", "ground-zero-tutorial"],
  ["customs", "bigmap"],
];

export type RaidPrepMapOption = {
  id: string;
  label: string;
  english: string;
  icon: string;
};

export function mapSlugKeys(mapSlug: string): Set<string> {
  const key = (mapSlug || "").trim().toLowerCase();
  if (!key) return new Set();
  const keys = new Set<string>([key]);
  for (const group of MAP_SLUG_EQUIV_GROUPS) {
    if (group.includes(key)) {
      for (const item of group) keys.add(item);
      break;
    }
  }
  return keys;
}

export function raidPrepMapOptions(): RaidPrepMapOption[] {
  const ready = TARKOV_MAPS.filter(
    (item) => item.status === "ready" && !item.comingSoon,
  );
  const factory = ready.find((item) => item.id === "factory");
  const out: RaidPrepMapOption[] = [];
  for (const item of ready) {
    out.push({
      id: item.id,
      label: item.label,
      english: item.english,
      icon: item.icon,
    });
    if (item.id === "factory" && factory) {
      out.push({
        id: "night-factory",
        label: "夜间工厂",
        english: "Factory (Night)",
        icon: factory.icon,
      });
    }
  }
  return out;
}

export function normalizeRaidPrepMapId(raw: string): string {
  const keys = mapSlugKeys(raw);
  if (!keys.size) return "";
  for (const option of raidPrepMapOptions()) {
    const optionKeys = mapSlugKeys(option.id);
    for (const key of keys) {
      if (optionKeys.has(key)) return option.id;
    }
  }
  return "";
}

/** 载入地图 / 匹配中 / 匹配成功 / 倒计时 / 开战：认定「正在进这张图」。 */
export const RAID_PREP_AUTO_MAP_KINDS = [
  "map_loading",
  "matching",
  "match_found",
  "raid_starting",
  "raid_started",
] as const;

export function isRaidPrepAutoMapKind(kind: string | null | undefined): boolean {
  const key = (kind || "").trim();
  return (RAID_PREP_AUTO_MAP_KINDS as readonly string[]).includes(key);
}
