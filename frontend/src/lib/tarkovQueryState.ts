/** 列表页 page / pageSize 从 URL 读取。 */

export function readPositiveInt(
  raw: string | null | undefined,
  fallback: number,
): number {
  const n = Number(raw || "");
  return Number.isInteger(n) && n > 0 ? n : fallback;
}

export function readAllowedInt(
  raw: string | null | undefined,
  fallback: number,
  allowed: number[],
): number {
  const n = Number(raw || "");
  return allowed.includes(n) ? n : fallback;
}

export type CatalogSortOrder = "ascend" | "descend";

export function readCatalogSort(
  sort: string | null | undefined,
  dir: string | null | undefined,
  allowed: string[],
): { key: string; order: CatalogSortOrder } | null {
  const key = (sort || "").trim();
  if (!allowed.includes(key)) return null;
  if (dir === "asc" || dir === "ascend") return { key, order: "ascend" };
  if (dir === "desc" || dir === "descend") return { key, order: "descend" };
  return null;
}

export function catalogSortQuery(
  key: string,
  order: CatalogSortOrder,
): { sort: string; dir: "asc" | "desc" } {
  return { sort: key, dir: order === "ascend" ? "asc" : "desc" };
}

export function readRigKindFilter(
  raw: string | null | undefined,
): "all" | "plain" | "armored" {
  const kind = (raw || "").trim();
  if (kind === "plain" || kind === "armored") return kind;
  return "all";
}
