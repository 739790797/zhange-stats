import { describe, expect, it } from "vitest";
import type {
  StrongholdMatch,
  StrongholdOwn,
  StrongholdRecordDetail,
} from "@/features/platforms/skland/api/strongholdApi";
import { boundRoleNames, preferredRoleName, withOwnRoleNames } from "./strongholdLabels";
import {
  bondLayerScale,
  groupReportPlayers,
  initialReportView,
  pickedChessIds,
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

  it("matches canonical and exact chess IDs, not shared names, phases, or guessed suffixes", () => {
    const keys = pickedChessIds([
      { id: "signal_piece", normal_chess_id: "known", is_elite: true },
      { id: "other_piece_gold", char_id: "char_002_amiya", merge_level: 3, phase: 2 },
      { id: "normal" },
      { id: "known" },
    ]);
    expect(keys).toEqual(new Set(["known", "other_piece_gold", "normal"]));
    expect(keys.has("other_piece")).toBe(false);
    expect(pickedChessIds(null).size).toBe(0);
  });
});

describe("Stronghold bond axis", () => {
  it.each([0, 397, 999, 1000])("keeps the same zero-based scale at %d layers", (peak) => {
    expect(bondLayerScale(peak)).toEqual({ ceiling: 1000, ticks: [1000, 750, 500, 250, 0] });
  });

  it.each([1001, 5326, 2_147_483_647])(
    "expands to readable equal intervals for %d layers",
    (peak) => {
      const { ceiling, ticks } = bondLayerScale(peak);
      expect(ceiling).toBeGreaterThanOrEqual(peak);
      expect(ticks).toEqual([1, 0.75, 0.5, 0.25, 0].map((fraction) => ceiling * fraction));
    },
  );
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
