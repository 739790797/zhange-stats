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
