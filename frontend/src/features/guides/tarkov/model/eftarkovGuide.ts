import { isBareTarkovId } from "@/features/guides/tarkov/model/tarkovItemFormat";

export const EFTARKOV_GUIDE_ORIGIN = "https://www.eftarkov.com";

/** eftarkov 任务页上的图文指引（地图、实景、点位说明）。旧 /news/id/{id}.html 已 404。 */
export function eftarkovTaskGuideUrl(taskId: string): string | null {
  const id = taskId.trim();
  if (!isBareTarkovId(id)) return null;
  return `${EFTARKOV_GUIDE_ORIGIN}/task/${encodeURIComponent(id)}`;
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
