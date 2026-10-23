import {
  mergeRaidPrepSkipMaps,
  objectivePairsToSkipMap,
  raidPrepSkipMapsEqual,
  type RaidPrepSkipMap,
} from "@/features/guides/tarkov/model/tarkovRaidPrep";

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

/** 用户这一下勾选的键。空 id 返回空串，调用方不要写进钉住表。 */
export function objectivePinKey(taskId: string, objectiveId: string): string {
  const task = taskId.trim();
  const objective = objectiveId.trim();
  if (!task || !objective) return "";
  return `${task}\0${objective}`;
}

function copySkipMap(
  current: RaidPrepSkipMap | null | undefined,
): Map<string, Set<string>> {
  const next = new Map<string, Set<string>>();
  for (const [taskId, ids] of current || []) {
    const task = String(taskId || "").trim();
    if (!task) continue;
    const bucket = new Set<string>();
    for (const id of ids || []) {
      const objectiveId = String(id || "").trim();
      if (objectiveId) bucket.add(objectiveId);
    }
    if (bucket.size) next.set(task, bucket);
  }
  return next;
}

/**
 * 把用户刚刚的勾选/取消钉在并集上面。
 * 旧存档、房间记录再并回来时，取消的步骤不会被加回，刚勾上的也不会被丢掉。
 * 没有变化返回 null。
 */
export function applyObjectivePins(
  current: RaidPrepSkipMap | null | undefined,
  pins: ReadonlyMap<string, boolean> | null | undefined,
): Map<string, Set<string>> | null {
  if (!pins?.size) return null;
  const next = copySkipMap(current);
  let changed = false;
  for (const [key, checked] of pins) {
    const splitAt = key.indexOf("\0");
    if (splitAt <= 0 || splitAt >= key.length - 1) continue;
    const taskId = key.slice(0, splitAt);
    const objectiveId = key.slice(splitAt + 1);
    const bucket = new Set(next.get(taskId) || []);
    const has = bucket.has(objectiveId);
    if (checked === has) continue;
    changed = true;
    if (checked) {
      bucket.add(objectiveId);
      next.set(taskId, bucket);
    } else if (bucket.size) {
      bucket.delete(objectiveId);
      if (bucket.size) next.set(taskId, bucket);
      else next.delete(taskId);
    }
  }
  return changed ? next : null;
}

/**
 * 并集之后再钉住用户这一下。
 * 钉完若和当前本机一致，返回 null：调用方不用重写状态，但持久化仍要按「没有这步」来写。
 */
export function adoptMergedObjectiveSkip(
  current: RaidPrepSkipMap | null | undefined,
  merged: RaidPrepSkipMap | null | undefined,
  pins: ReadonlyMap<string, boolean> | null | undefined,
): RaidPrepSkipMap | null {
  const base = merged ?? current;
  const sealed = applyObjectivePins(base, pins);
  if (!sealed) return merged ?? null;
  return raidPrepSkipMapsEqual(sealed, current) ? null : sealed;
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
