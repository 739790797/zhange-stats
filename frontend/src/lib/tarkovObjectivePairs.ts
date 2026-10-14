import {
  mergeRaidPrepSkipMaps,
  objectivePairsToSkipMap,
  raidPrepSkipMapsEqual,
  type RaidPrepSkipMap,
} from "@/lib/tarkovRaidPrep";

export type RaidPrepObjectivePair = { task_id: string; objective_id: string };

/** 本机步骤勾选 ∪ 这些步骤；内容没变返回 null，调用方就不必重写本机状态。 */
export function mergeObjectivePairs(
  current: RaidPrepSkipMap | null | undefined,
  pairs: readonly RaidPrepObjectivePair[] | null | undefined,
): Map<string, Set<string>> | null {
  if (!pairs?.length) return null;
  return mergeSkipMapsIfChanged(current, objectivePairsToSkipMap([...pairs]));
}

/** 同上，但并入的是已经成形的 skip。 */
export function mergeSkipMapsIfChanged(
  current: RaidPrepSkipMap | null | undefined,
  ...extra: Array<RaidPrepSkipMap | null | undefined>
): Map<string, Set<string>> | null {
  const next = mergeRaidPrepSkipMaps(current, ...extra);
  return raidPrepSkipMapsEqual(current, next) ? null : next;
}

export type RaidPrepStateBody = {
  selected: readonly string[];
  objective_dones: readonly RaidPrepObjectivePair[];
  key_brings: readonly string[];
};

function sameIdList(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((id, index) => id === b[index]);
}

/** 步骤顺序由展示层决定，接口只存集合：比对时按 id 排序。 */
function samePairList(
  a: readonly RaidPrepObjectivePair[],
  b: readonly RaidPrepObjectivePair[],
): boolean {
  if (a.length !== b.length) return false;
  const key = (row: RaidPrepObjectivePair) =>
    `${String(row.task_id || "").trim()}\t${String(row.objective_id || "").trim()}`;
  const left = a.map(key).sort();
  const right = b.map(key).sort();
  return left.every((item, index) => item === right[index]);
}

/** 单人准备落盘：三份内容都一样就不用再 PUT（接口是整行覆盖）。 */
export function sameRaidPrepStateBody(
  a: RaidPrepStateBody | null | undefined,
  b: RaidPrepStateBody | null | undefined,
): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  return (
    sameIdList(a.selected, b.selected) &&
    sameIdList(a.key_brings, b.key_brings) &&
    samePairList(a.objective_dones, b.objective_dones)
  );
}
