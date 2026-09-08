import { describe, expect, it } from "vitest";
import type { TarkovWorkbenchCommunityBuild } from "@/api/guidesApi";
import {
  communityTagLabel,
  communityTagsInList,
  compareCommunityBuilds,
  filterCommunityBuilds,
  formatCommunityEvoDelta,
  formatCommunityPublishedAt,
} from "./tarkovCommunityBuilds";

function row(
  partial: Partial<TarkovWorkbenchCommunityBuild> & { id: string; name: string },
): TarkovWorkbenchCommunityBuild {
  return {
    author: "",
    featured: false,
    load_count: 0,
    loadable: true,
    dropped_pair_count: 0,
    ...partial,
  };
}

describe("tarkovCommunityBuilds", () => {
  const builds = [
    row({ id: "1", name: "夜战 M4", author: "LianDouDou", tags: ["ergo", "meta"] }),
    row({ id: "2", name: "预算 CQB", author: "匿名", tags: ["budget", "cqb"] }),
  ];

  it("labels known tags and lists present ones in preset order", () => {
    expect(communityTagLabel("ergo")).toBe("高人机");
    expect(communityTagLabel("hybrid")).toBe("综合");
    expect(communityTagLabel("featured")).toBe("精选");
    expect(communityTagLabel("unknown")).toBe("unknown");
    expect(communityTagsInList(builds)).toEqual(["meta", "budget", "cqb", "ergo"]);
  });

  it("filters by query and all selected tags", () => {
    expect(filterCommunityBuilds(builds, "m4", []).map((row) => row.id)).toEqual(["1"]);
    expect(filterCommunityBuilds(builds, "lian", []).map((row) => row.id)).toEqual(["1"]);
    expect(filterCommunityBuilds(builds, "", ["ergo", "meta"]).map((row) => row.id)).toEqual([
      "1",
    ]);
    expect(filterCommunityBuilds(builds, "", ["ergo", "budget"])).toEqual([]);
  });

  it("formats ISO published_at to a date", () => {
    expect(formatCommunityPublishedAt("2026-09-05T08:10:15.610844")).toBe("2026-09-05");
    expect(formatCommunityPublishedAt(null)).toBe("");
  });

  it("sorts by date, loads, and preview stats", () => {
    const older = row({
      id: "1",
      name: "旧",
      published_at: "2026-01-01T00:00:00",
      load_count: 3,
      preview: { ergonomics: 50, evo_ergo_delta: -1.2, recoil_vertical: 80, overswing: true },
    });
    const newer = row({
      id: "2",
      name: "新",
      published_at: "2026-09-05T00:00:00",
      load_count: 20,
      preview: { ergonomics: 62.9, evo_ergo_delta: 48.92, recoil_vertical: 61, overswing: false },
    });
    expect(compareCommunityBuilds(older, newer, "published_at")).toBeLessThan(0);
    expect(compareCommunityBuilds(older, newer, "load_count")).toBeLessThan(0);
    expect(compareCommunityBuilds(older, newer, "ergonomics")).toBeLessThan(0);
    expect(compareCommunityBuilds(older, newer, "evo_ergo_delta")).toBeLessThan(0);
    expect(compareCommunityBuilds(older, newer, "recoil_vertical")).toBeGreaterThan(0);
    expect(compareCommunityBuilds(older, newer, "overswing")).toBeGreaterThan(0);
    expect(formatCommunityEvoDelta(48.92)).toBe("+48.9");
    expect(formatCommunityEvoDelta(-1.2)).toBe("-1.2");
  });
});
