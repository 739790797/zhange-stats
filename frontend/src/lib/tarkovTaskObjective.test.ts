import { describe, expect, it } from "vitest";
import {
  formatTaskExtractLines,
  orderObjectiveTypes,
  tarkovExitStatusLabel,
  tarkovObjectiveTypeLabel,
  tarkovObjectiveTypeTone,
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
