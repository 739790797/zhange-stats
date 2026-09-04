import { describe, expect, it } from "vitest";
import {
  collectTaskMutexRows,
  formatTaskCompare,
  formatTaskDelay,
  formatTaskExtractLines,
  formatTaskObjectiveExtraLines,
  orderObjectiveTypes,
  tarkovExitStatusLabel,
  tarkovObjectiveTypeLabel,
  tarkovObjectiveTypeTone,
  taskRequirementStatusLabel,
  taskUnlockStatusLabel,
} from "./tarkovTaskObjective";

describe("objective type chips", () => {
  it("translates known types and keeps unknown as-is", () => {
    expect(tarkovObjectiveTypeLabel("shoot")).toBe("击杀");
    expect(tarkovObjectiveTypeLabel("giveQuestItem")).toBe("上交任务物");
    expect(tarkovObjectiveTypeLabel("mysteryType")).toBe("mysteryType");
    expect(tarkovObjectiveTypeTone("visit")).toBe("visit");
    expect(tarkovObjectiveTypeTone("mysteryType")).toBe("unknown");
  });

  it("dedupes and orders types for the table", () => {
    expect(
      orderObjectiveTypes(["visit", "shoot", "visit", "giveItem", ""]),
    ).toEqual(["shoot", "giveItem", "visit"]);
    expect(orderObjectiveTypes(["zzz", "shoot", "aaa"])).toEqual([
      "shoot",
      "aaa",
      "zzz",
    ]);
  });
});


describe("formatTaskExtractLines", () => {
  it("matches tarkov.dev extract wording and ignores ExpBonus names", () => {
    expect(
      formatTaskExtractLines({
        exit_status: ["Survived"],
        exit_name: "ExpBonusSurvived&ExpBonusRunner",
        count: 1,
      }),
    ).toEqual(["以状态撤离：幸存或匆匆逃离"]);
    expect(tarkovExitStatusLabel("Runner")).toBe("匆匆逃离");
    expect(
      formatTaskExtractLines({
        exit_status: ["Survived"],
        exit_name: "EXFIL_Train",
      }),
    ).toEqual(["以状态撤离：幸存", "使用撤离点：EXFIL_Train"]);
  });
});

describe("task detail extras", () => {
  it("formats delay, compare, and objective extra lines", () => {
    expect(formatTaskDelay(3600, 7200)).toBe("完成后等待 1 小时–2 小时");
    expect(formatTaskDelay(0, 0)).toBe("");
    expect(formatTaskCompare(">=", 40)).toBe("≥40");
    expect(taskRequirementStatusLabel("complete")).toBe("需完成");
    expect(taskUnlockStatusLabel("complete")).toBe("完成后可接");
    expect(
      formatTaskObjectiveExtraLines({
        count: 10,
        target_names: ["Scavs"],
        body_parts: ["Head"],
        shot_type: "Kill",
        distance: { compare_method: ">=", value: 40 },
        time_from_hour: 22,
        time_until_hour: 6,
        dog_tag_level: 4,
        min_durability: 0,
        max_durability: 50,
        skill_name: "Endurance",
        skill_level: 2,
        zone_names: ["Dorms"],
        attributes: [{ name: "ergonomics", compare_method: ">=", value: 30 }],
        enemy_health_effect: { body_parts: ["Head"], effects: ["Pain"] },
        contains_category: [{ id: "cat1", name: "瞄具" }],
      }),
    ).toEqual([
      "数量 ×10",
      "目标：Scavs",
      "部位：头部",
      "方式：击杀",
      "距离 ≥40 m",
      "游戏内时段 22:00–06:00",
      "狗牌等级 ≥4",
      "耐久 0–50%",
      "技能 Endurance 2 级",
      "区域：Dorms",
      "人机 ≥30",
      "目标状态：头部 · 疼痛",
      "配件分类：瞄具",
    ]);
  });
});

describe("collectTaskMutexRows", () => {
  it("keeps unique taskStatus fail conditions as mutex links", () => {
    expect(
      collectTaskMutexRows([
        {
          type: "extract",
          tasks: [{ id: "x", name: "X" }],
        },
        {
          type: "taskStatus",
          status: ["complete"],
          tasks: [
            { id: "curio", name: "好奇心", trader_slug: "skier" },
            { id: "curio", name: "重复" },
          ],
        },
        {
          type: "taskStatus",
          status: ["complete"],
          tasks: [{ id: "big", name: "大客户", trader_name: "Prapor" }],
        },
      ]),
    ).toEqual([
      {
        id: "curio",
        name: "好奇心",
        trader_slug: "skier",
        trader_name: "",
        status: ["complete"],
      },
      {
        id: "big",
        name: "大客户",
        trader_slug: "",
        trader_name: "Prapor",
        status: ["complete"],
      },
    ]);
  });
});
