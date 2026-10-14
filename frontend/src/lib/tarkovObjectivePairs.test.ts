import { describe, expect, it } from "vitest";
import {
  mergeObjectivePairs,
  mergeSkipMapsIfChanged,
  sameRaidPrepStateBody,
} from "@/lib/tarkovObjectivePairs";
import { raidPrepSkipMapForViewer } from "@/lib/tarkovRaidPrep";

const skip = (rows: Record<string, string[]>): Map<string, Set<string>> =>
  new Map(Object.entries(rows).map(([taskId, ids]) => [taskId, new Set(ids)]));

describe("mergeObjectivePairs", () => {
  it("returns the merged map when the pairs add something new", () => {
    const merged = mergeObjectivePairs(skip({ t1: ["o1"] }), [
      { task_id: "t1", objective_id: "o2" },
    ]);
    expect(merged).not.toBeNull();
    expect([...(merged!.get("t1") || [])].sort()).toEqual(["o1", "o2"]);
  });

  it("returns null when nothing changes, so the caller skips the rewrite", () => {
    const current = skip({ t1: ["o1", "o2"] });
    expect(
      mergeObjectivePairs(current, [
        { task_id: "t1", objective_id: "o1" },
        { task_id: "t1", objective_id: "o2" },
      ]),
    ).toBeNull();
    // 顺序不同也算没变
    expect(
      mergeObjectivePairs(current, [
        { task_id: "t1", objective_id: "o2" },
        { task_id: "t1", objective_id: "o1" },
      ]),
    ).toBeNull();
  });

  it("returns null for no pairs at all", () => {
    expect(mergeObjectivePairs(skip({ t1: ["o1"] }), [])).toBeNull();
    expect(mergeObjectivePairs(skip({ t1: ["o1"] }), undefined)).toBeNull();
  });

  it("drops blank ids the way the skip map does", () => {
    expect(
      mergeObjectivePairs(new Map(), [
        { task_id: "", objective_id: "o1" },
        { task_id: "t1", objective_id: "" },
      ]),
    ).toBeNull();
  });
});

describe("mergeSkipMapsIfChanged", () => {
  it("returns null when every extra map is already covered", () => {
    const current = skip({ t1: ["o1"] });
    expect(mergeSkipMapsIfChanged(current, skip({ t1: ["o1"] }))).toBeNull();
    expect(mergeSkipMapsIfChanged(current, null, undefined)).toBeNull();
  });

  it("merges new steps from several maps", () => {
    const merged = mergeSkipMapsIfChanged(
      skip({ t1: ["o1"] }),
      skip({ t1: ["o2"] }),
      skip({ t2: ["o1"] }),
    );
    expect(merged).not.toBeNull();
    expect([...(merged!.get("t1") || [])].sort()).toEqual(["o1", "o2"]);
    expect([...(merged!.get("t2") || [])]).toEqual(["o1"]);
  });

  it("matches the viewer merge used for strikethrough", () => {
    const local = skip({ t1: ["o1"] });
    const account = [{ task_id: "t2", objective_id: "o1" }];
    expect(mergeSkipMapsIfChanged(local, null)).toBeNull();
    expect(
      mergeSkipMapsIfChanged(local, undefined),
    ).toBeNull();
    expect(
      [...(mergeObjectivePairs(local, account)!.get("t2") || [])],
    ).toEqual(["o1"]);
    expect(
      [...(raidPrepSkipMapForViewer(local, account).get("t2") || [])],
    ).toEqual(["o1"]);
  });
});

describe("sameRaidPrepStateBody", () => {
  type Body = Parameters<typeof sameRaidPrepStateBody>[0] & object;
  const body = (over: Partial<Body> = {}): Body => ({
    selected: ["a", "b"],
    objective_dones: [{ task_id: "t1", objective_id: "o1" }],
    key_brings: ["k1"],
    ...over,
  });

  it("skips the PUT when the payload is unchanged", () => {
    expect(sameRaidPrepStateBody(body(), body())).toBe(true);
    expect(sameRaidPrepStateBody(null, null)).toBe(true);
    expect(sameRaidPrepStateBody(undefined, undefined)).toBe(true);
  });

  it("sees the same objective set in another order as unchanged", () => {
    expect(
      sameRaidPrepStateBody(
        body({
          objective_dones: [
            { task_id: "t1", objective_id: "o1" },
            { task_id: "t2", objective_id: "o9" },
          ],
        }),
        body({
          objective_dones: [
            { task_id: "t2", objective_id: "o9" },
            { task_id: "t1", objective_id: "o1" },
          ],
        }),
      ),
    ).toBe(true);
  });

  it("sees a changed selection, key list or step set as a new payload", () => {
    expect(sameRaidPrepStateBody(body(), body({ selected: ["a"] }))).toBe(false);
    expect(sameRaidPrepStateBody(body(), body({ selected: ["b", "a"] }))).toBe(false);
    expect(sameRaidPrepStateBody(body(), body({ key_brings: ["k2"] }))).toBe(false);
    expect(
      sameRaidPrepStateBody(
        body(),
        body({ objective_dones: [{ task_id: "t1", objective_id: "o2" }] }),
      ),
    ).toBe(false);
    expect(sameRaidPrepStateBody(body(), body({ objective_dones: [] }))).toBe(false);
  });

  it("never treats a missing payload as equal to a present one", () => {
    expect(sameRaidPrepStateBody(body(), null)).toBe(false);
    expect(sameRaidPrepStateBody(undefined, body())).toBe(false);
  });
});
