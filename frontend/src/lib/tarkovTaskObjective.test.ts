import { describe, expect, it } from "vitest";
import {
  formatTaskExtractLines,
  tarkovExitStatusLabel,
} from "./tarkovTaskObjective";

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
