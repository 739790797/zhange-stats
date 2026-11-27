import { describe, expect, it } from "vitest";
import type {
  StrongholdMatch,
  StrongholdOwn,
  StrongholdRecordDetail,
} from "@/features/platforms/skland/api/strongholdApi";
import { boundRoleNames, preferredRoleName, withOwnRoleNames } from "./strongholdLabels";
import {
  belongsToBond,
  bondStatus,
  chessKey,
  groupReportPlayers,
  initialReportView,
  reportBondBars,
  reportDuration,
  reportPortraits,
} from "./strongholdReportModel";

const scope = {
  season_id: "s1",
  season_label: "规程",
  difficulty_id: "abyss",
  difficulty_label: "终极模拟",
};
const ended_at = "2026-11-24T20:00:00+08:00";

function view(id: string, group?: string, own = false): StrongholdRecordDetail {
  return {
    ...scope,
    id,
    match_id: "same-match",
    player_group_id: group,
    role_name: "同名角色",
    is_own: own,
    ended_at,
    completed: null,
    pass_round: null,
    strategy_id: null,
    strategy_name: null,
    roster: null,
    bonds: null,
    battle: {},
  };
}

function match(views: StrongholdRecordDetail[], my_record_id?: string): StrongholdMatch {
  return {
    ...scope,
    id: "same-match",
    ended_at,
    success: null,
    participants: [],
    views,
    my_record_id,
  };
}

describe("Stronghold report perspectives", () => {
  it("groups only on the server-supplied identity, keeping duplicate views and own marker", () => {
    const first = view("a", "first");
    const own = view("b", "first", true);
    const sameName = view("c", "second");
    const legacy = view("d");
    expect(groupReportPlayers(match([first, own, sameName, legacy]))).toEqual([
      { id: "first", own: true, records: [first, own] },
      { id: "second", own: false, records: [sameName] },
      { id: "d", own: false, records: [legacy] },
    ]);
  });

  it("honors the exact list entry, falls back to own or first available view", () => {
    const first = view("a");
    const own1 = view("b", "duplicate", true);
    const own2 = view("c", "other", true);
    const report = match([first, own1, own2], own1.id);
    expect(initialReportView(report, own2.id)).toBe(own2);
    expect(initialReportView(report, "does-not-exist")).toBe(own1);
    expect(initialReportView(match([first, own2]))).toBe(own2);
    expect(initialReportView(match([first]))).toBe(first);
    expect(initialReportView(match([]))).toBeUndefined();
  });
});

describe("Stronghold report combat data", () => {
  it("matches canonical or exact chess IDs and evaluates golden rules independently of evolve phase", () => {
    const ordinaryBond = {
      bond_id: "known_bond",
      operators: [{ id: "known", char_id: "char_original" }],
    };
    const goldenBond = { bond_id: "gold_bond", activation_rule: "golden" as const };
    const substitute = {
      id: "signal_piece",
      normal_chess_id: "known",
      char_id: "char_backup",
      is_elite: true,
      phase: 0,
    };
    const unknown = { id: "known_gold", char_id: "char_original", phase: 2 };
    expect(chessKey(substitute)).toBe("known");
    expect(belongsToBond(substitute, ordinaryBond)).toBe(true);
    expect(belongsToBond(substitute, goldenBond)).toBe(true);
    expect(belongsToBond({ id: "known" }, ordinaryBond)).toBe(true);
    expect(belongsToBond(unknown, ordinaryBond)).toBe(false);
    expect(belongsToBond(unknown, goldenBond)).toBe(false);
    expect([true, false, null].map(bondStatus)).toEqual([
      "本局已点亮",
      "本局未点亮",
      "点亮状态未知",
    ]);
  });

  it("sorts relative bars by recorded layers and retains zero and missing values", () => {
    const bonds = [
      { bond_id: "missing", layer: null },
      { bond_id: "zero", layer: 0 },
      { bond_id: "peak", layer: 124 },
      { bond_id: "half", layer: 62 },
    ];
    expect(reportBondBars(bonds).map(({ bond, fill }) => [bond.layer, fill])).toEqual([
      [124, 1],
      [62, 0.5],
      [0, 0],
      [null, 0],
    ]);
    expect(reportBondBars(bonds.slice(0, 2)).map(({ fill }) => fill)).toEqual([0, 0]);
  });

  it("uses the same Beijing clock for naive and offset dates, including at midnight", () => {
    expect(reportDuration("2026-11-26T23:43:01", "2026-11-26T16:33:41Z")).toEqual({
      minutes: 50,
      seconds: 40,
    });
    expect(reportDuration(ended_at, ended_at)).toEqual({ minutes: 0, seconds: 0 });
    expect(reportDuration(ended_at, "2026-11-24T19:00:00+08:00")).toBeNull();
    expect(reportDuration(null, ended_at)).toBeNull();
    expect(reportDuration("invalid", ended_at)).toBeNull();
  });

  it("uses only roster portraits and falls back from elite phase 2 to the base portrait", () => {
    for (const phase of [0, 1, 3, null, undefined]) {
      expect(reportPortraits("char_example", phase)).toEqual([
        "/api/skland/arknights/assets/portrait/char_example_1.png",
      ]);
    }
    expect(reportPortraits("char_example", 2)).toEqual([
      "/api/skland/arknights/assets/portrait/char_example_2.png",
      "/api/skland/arknights/assets/portrait/char_example_1.png",
    ]);
    expect(reportPortraits(null, 2)).toEqual([]);
  });
});

describe("Stronghold binding names", () => {
  it("fills an old own view by its exact server and UID, never by the selected role or a peer's view", () => {
    const official = {
      game_code: "arknights",
      game_name: "明日方舟",
      uid: "101",
      channel_master_id: "1",
      channel_name: "官服",
      role_name: "官服博士#0197",
    };
    const bili = {
      ...official,
      channel_master_id: "2",
      channel_name: "B 服",
      role_name: "渠道服博士#1259",
    };
    const endfield = { ...bili, game_code: "endfield", role_name: "终末地角色" };
    const roles: StrongholdOwn["roles"] = [
      { id: 1, channel_id: "1", uid: "101", role_name: "官服博士", synced_at: ended_at },
      { id: 2, channel_id: "2", uid: "101", role_name: "未知角色", synced_at: ended_at },
    ];
    const own = { ...view("a", undefined, true), own_role_id: 2, role_name: null };
    const peer = { ...view("b"), own_role_id: 2, role_name: null };
    const missing = { ...view("c", undefined, true), own_role_id: 9, role_name: null };
    const report = withOwnRoleNames(
      match([own, peer, missing]),
      roles,
      boundRoleNames([official, bili, endfield]),
    );
    expect(report.views?.map(({ role_name }) => role_name)).toEqual([
      "渠道服博士#1259",
      null,
      null,
    ]);
  });

  it("adds a known tag to the same nickname, not to a rename, and rejects missing names and numeric UIDs", () => {
    expect(preferredRoleName("博士", "博士#1259", "101")).toBe("博士#1259");
    expect(preferredRoleName("改名博士", "博士#1259", "101")).toBe("改名博士");
    expect(preferredRoleName("101", "未知角色", "101")).toBeUndefined();
  });
});
