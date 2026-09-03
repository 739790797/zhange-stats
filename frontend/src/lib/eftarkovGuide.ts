import { isBareTarkovId } from "@/lib/tarkovItemFormat";

export const EFTARKOV_GUIDE_ORIGIN = "https://www.eftarkov.com";

/** eftarkov 任务攻略页（与 tarkov.dev / 战鸽 task id 对齐） */
export function eftarkovTaskGuideUrl(taskId: string): string | null {
  const id = taskId.trim();
  if (!isBareTarkovId(id)) return null;
  return `${EFTARKOV_GUIDE_ORIGIN}/news/id/${encodeURIComponent(id)}.html`;
}

/** 点任务名打开攻略时保留该 id；未指定才回落到已勾选的第一条。 */
export function resolveRaidPrepGuideId(
  selectedIds: readonly string[],
  guideParam: string,
): string {
  const guide = guideParam.trim();
  if (guide) return guide;
  return selectedIds[0] || "";
}

/** 点开的任务若尚未勾选，仍并进攻略侧栏，避免 iframe 被已选第一条顶掉。 */
export function mergeRaidPrepGuideTasks<T extends { id: string }>(
  selected: readonly T[],
  catalog: readonly T[],
  activeId: string,
): T[] {
  const id = activeId.trim();
  if (!id || selected.some((row) => row.id === id)) return [...selected];
  const extra = catalog.find((row) => row.id === id);
  return extra ? [extra, ...selected] : [...selected];
}
