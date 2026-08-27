/** 列表页 page / pageSize / 展示模式从 URL 读取。 */

export function readPositiveInt(
  raw: string | null | undefined,
  fallback: number,
): number {
  const n = Number(raw || "");
  return Number.isInteger(n) && n > 0 ? n : fallback;
}

/** 任务页默认查找（表格）；仅 `view=chain` 进入任务线。 */
export function readTarkovTaskView(
  raw: string | null | undefined,
): "chain" | "table" {
  return raw === "chain" ? "chain" : "table";
}

export function readAllowedInt(
  raw: string | null | undefined,
  fallback: number,
  allowed: number[],
): number {
  const n = Number(raw || "");
  return allowed.includes(n) ? n : fallback;
}
