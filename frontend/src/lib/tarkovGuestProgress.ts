/** 访客暂存里有多少能并进账号的进度：没有就不必问；有就告诉用户大概是什么。 */

import {
  TARKOV_COLLECTION_LAYOUT_STORAGE_KEY,
  TARKOV_COLLECTION_LAYOUT_V3_STORAGE_KEY,
  collectionLayoutFromStorage,
} from "@/lib/tarkovCollection";
import { TARKOV_GAME_MODES } from "@/lib/tarkovGameMode";
import { TARKOV_KEY_PACKS_STORAGE_KEY, parseOwnedState } from "@/lib/tarkovKeyPacks";
import {
  TARKOV_PMC_FACTION_STORAGE_KEY,
  parseTarkovPmcFactionMap,
} from "@/lib/tarkovPmcFaction";
import type { TarkovGuestProgress } from "@/lib/tarkovProgressOwner";
import {
  RAID_PREP_OBJ_DONE_STORAGE,
  mergeGuestRaidPrepObjectiveDone,
  parseRaidPrepObjectiveDoneStore,
} from "@/lib/tarkovRaidPrep";
import {
  TARKOV_TASK_DONES_STORAGE_KEY,
  cleanTaskProgress,
  parseTaskDonesStateRaw,
} from "@/lib/tarkovTaskTree";

export type TarkovGuestProgressSummary = {
  tasks: number;
  steps: number;
  keys: number;
  collected: number;
  factions: number;
};

export function summarizeTarkovGuestProgress(
  stash: TarkovGuestProgress,
): TarkovGuestProgressSummary {
  const taskState = parseTaskDonesStateRaw(stash[TARKOV_TASK_DONES_STORAGE_KEY]);
  const factions = parseTarkovPmcFactionMap(
    stash[TARKOV_PMC_FACTION_STORAGE_KEY] ?? null,
  );
  const steps = new Set<string>();
  let tasks = 0;
  let collected = 0;
  let factionCount = 0;
  for (const mode of TARKOV_GAME_MODES) {
    const cleaned = cleanTaskProgress(
      taskState[mode] || [],
      taskState.started?.[mode] || [],
      taskState.failed?.[mode] || [],
    );
    tasks += cleaned.done.length + cleaned.started.length + cleaned.failed.length;
    for (const pair of taskState.objectives?.[mode] || []) {
      steps.add(`${pair.task_id}\0${pair.objective_id}`);
    }
    collected +=
      collectionLayoutFromStorage(
        stash[TARKOV_COLLECTION_LAYOUT_STORAGE_KEY],
        stash[TARKOV_COLLECTION_LAYOUT_V3_STORAGE_KEY],
        mode,
      )?.placements.length || 0;
    if (factions[mode]) factionCount += 1;
  }
  const marks = mergeGuestRaidPrepObjectiveDone(
    {},
    parseRaidPrepObjectiveDoneStore(stash[RAID_PREP_OBJ_DONE_STORAGE]),
    0,
  );
  for (const rows of Object.values(marks)) {
    for (const [taskId, ids] of Object.entries(rows)) {
      for (const id of ids) steps.add(`${taskId}\0${id}`);
    }
  }
  return {
    tasks,
    steps: steps.size,
    keys: parseOwnedState(stash[TARKOV_KEY_PACKS_STORAGE_KEY]).length,
    collected,
    factions: factionCount,
  };
}

/** 提示里列出的几类进度；空数组表示没有可导入的。 */
export function tarkovGuestProgressParts(
  summary: TarkovGuestProgressSummary,
): string[] {
  const parts: string[] = [];
  if (summary.tasks) parts.push(`${summary.tasks} 个任务`);
  if (summary.steps) parts.push(`${summary.steps} 条任务步骤`);
  if (summary.keys) parts.push(`${summary.keys} 把钥匙`);
  if (summary.collected) parts.push(`${summary.collected} 件 3×4收集`);
  if (summary.factions) parts.push("PMC 阵营");
  return parts;
}
