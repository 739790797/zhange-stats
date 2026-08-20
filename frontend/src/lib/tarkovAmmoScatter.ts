import type { TarkovAmmoItem } from "@/api/guidesApi";

/** 黄金角分散色相；暗底略提亮，避免相邻口径落到近似色 */
export function distinctCaliberColor(index: number): string {
  const hue = Math.round((index * 137.508) % 360);
  const sat = index % 2 === 0 ? 72 : 64;
  const light = index % 3 === 0 ? 52 : index % 3 === 1 ? 58 : 48;
  return `hsl(${hue} ${sat}% ${light}%)`;
}

export function ammoScatterAxisMax(items: TarkovAmmoItem[]): {
  x: number;
  y: number;
} {
  const ceil10 = (n: number) => Math.max(10, Math.ceil(n / 10) * 10);
  let maxPen = 0;
  let maxDmg = 0;
  for (const row of items) {
    if (row.penetration > maxPen) maxPen = row.penetration;
    if (row.damage > maxDmg) maxDmg = row.damage;
  }
  return { x: ceil10(maxPen), y: ceil10(maxDmg) };
}

export function filterAmmoByIds(
  items: TarkovAmmoItem[],
  ids: Iterable<string>,
): TarkovAmmoItem[] {
  const set = new Set(Array.from(ids, (id) => id.trim()).filter(Boolean));
  if (!set.size) return [];
  return items.filter((row) => set.has(row.id));
}
