import { describe, expect, it } from "vitest";
import { TARKOV_COLLECTION_LAYOUT_STORAGE_KEY } from "./tarkovCollection";
import {
  summarizeTarkovGuestProgress,
  tarkovGuestProgressParts,
} from "./tarkovGuestProgress";
import { TARKOV_KEY_PACKS_STORAGE_KEY } from "./tarkovKeyPacks";
import { TARKOV_PMC_FACTION_STORAGE_KEY } from "./tarkovPmcFaction";
import { RAID_PREP_OBJ_DONE_STORAGE } from "./tarkovRaidPrep";
import { TARKOV_TASK_DONES_STORAGE_KEY } from "./tarkovTaskTree";

describe("summarizeTarkovGuestProgress", () => {
  it("counts what an import would bring over", () => {
    const summary = summarizeTarkovGuestProgress({
      [TARKOV_TASK_DONES_STORAGE_KEY]: JSON.stringify({
        v: 1,
        pvp: ["t1"],
        pve: ["t2"],
        started: { pvp: ["t1", "t3"] },
        objectives: { pvp: [{ task_id: "t3", objective_id: "o1" }] },
      }),
      [RAID_PREP_OBJ_DONE_STORAGE]: JSON.stringify({
        "user:guest:pvp:customs": { t3: ["o1", "o2"] },
        "solo:woods": { t4: ["o9"] },
        "user:9:pvp:customs": { t5: ["o5"] },
      }),
      [TARKOV_KEY_PACKS_STORAGE_KEY]: JSON.stringify({ v: 1, owned: ["k1", "k2"] }),
      [TARKOV_COLLECTION_LAYOUT_STORAGE_KEY]: JSON.stringify({
        v: 2,
        pve: { v: 2, placements: [{ itemId: "c1", col: 0, row: 0 }] },
      }),
      [TARKOV_PMC_FACTION_STORAGE_KEY]: JSON.stringify({ pvp: "bear" }),
    });
    expect(summary).toEqual({
      tasks: 3,
      steps: 3,
      keys: 2,
      collected: 1,
      factions: 1,
    });
    expect(tarkovGuestProgressParts(summary)).toEqual([
      "3 个任务",
      "3 条任务步骤",
      "2 把钥匙",
      "1 件 3×4收集",
      "PMC 阵营",
    ]);
  });

  it("finds nothing to ask about in empty leftovers", () => {
    const summary = summarizeTarkovGuestProgress({
      [TARKOV_TASK_DONES_STORAGE_KEY]: JSON.stringify({ v: 1, pvp: [], pve: [] }),
      [TARKOV_KEY_PACKS_STORAGE_KEY]: JSON.stringify({ v: 1, owned: [] }),
      [RAID_PREP_OBJ_DONE_STORAGE]: JSON.stringify({ "user:4:pvp:customs": { t: ["o"] } }),
    });
    expect(tarkovGuestProgressParts(summary)).toEqual([]);
  });
});
