import { isBareTarkovId } from "@/lib/tarkovItemFormat";

export const EFTARKOV_GUIDE_ORIGIN = "https://www.eftarkov.com";

/** eftarkov 任务攻略页（与 tarkov.dev / 战鸽 task id 对齐） */
export function eftarkovTaskGuideUrl(taskId: string): string | null {
  const id = taskId.trim();
  if (!isBareTarkovId(id)) return null;
  return `${EFTARKOV_GUIDE_ORIGIN}/news/id/${encodeURIComponent(id)}.html`;
}

/** 在已选任务中解析当前应展示攻略的任务 id */
export function resolveRaidPrepGuideId(
  selectedIds: readonly string[],
  guideParam: string,
): string {
  if (!selectedIds.length) return "";
  const guide = guideParam.trim();
  if (guide && selectedIds.includes(guide)) return guide;
  return selectedIds[0];
}
