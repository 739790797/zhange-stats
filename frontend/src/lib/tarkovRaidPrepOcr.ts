import { RAID_PREP_MAX_SELECTED } from "@/lib/tarkovRaidPrep";
import { mergeOcrSelection, newOcrIds } from "@/lib/tarkovOcr";

/** 合并进已有勾选，去重并截断上限。 */
export function mergeRaidPrepOcrSelection(
  existingIds: string[],
  confirmedIds: string[],
  max = RAID_PREP_MAX_SELECTED,
): string[] {
  return mergeOcrSelection(existingIds, confirmedIds, max);
}

/** 本次确认里真正新增的 id（已存在的不算）。 */
export function newRaidPrepOcrIds(
  existingIds: string[],
  confirmedIds: string[],
): string[] {
  return newOcrIds(existingIds, confirmedIds);
}
