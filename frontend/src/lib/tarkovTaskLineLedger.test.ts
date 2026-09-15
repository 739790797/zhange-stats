import { describe, expect, it } from "vitest";
import {
  applyTaskLineLedger,
  dropBlockedProgress,
  setTaskLineStatus,
  taskLineIndexFromTasks,
} from "./tarkovTaskLineLedger";

const line = taskLineIndexFromTasks([
  { id: "pre" },
  { id: "child", prereq_ids: ["pre"] },
  { id: "grand", prereq_ids: ["child"] },
  { id: "chem", mutex_ids: ["curio", "big"] },
  { id: "curio", mutex_ids: ["chem", "big"] },
  { id: "big", mutex_ids: ["chem", "curio"] },
  { id: "bat1" },
  { id: "price2", blocked_by: ["bat1"], prereq_ids: ["pre"] },
]);

describe("setTaskLineStatus", () => {
  it("completes a task and walks its prereqs", () => {
    expect(setTaskLineStatus([], ["child"], "grand", "done", [], line)).toEqual({
      done: ["grand", "child", "pre"],
      started: [],
      failed: [],
    });
  });

  it("starts a task after completing prereqs", () => {
    expect(setTaskLineStatus([], [], "child", "active", [], line)).toEqual({
      done: ["pre"],
      started: ["child"],
      failed: [],
    });
  });

  it("drops descendants from done/started when failing or clearing", () => {
    expect(
      setTaskLineStatus(
        ["pre", "child", "grand"],
        ["side"],
        "child",
        "failed",
        [],
        line,
      ),
    ).toEqual({
      done: ["pre"],
      started: ["side"],
      failed: ["child"],
    });
    expect(
      setTaskLineStatus(
        ["pre", "child", "grand"],
        ["child"],
        "pre",
        "todo",
        ["unrelated"],
        line,
      ),
    ).toEqual({
      done: [],
      started: [],
      failed: ["unrelated"],
    });
  });

  it("keeps only one mutex winner and drops blocked follow-ups", () => {
    expect(
      setTaskLineStatus(["chem", "curio", "big"], [], "chem", "done", [], line),
    ).toEqual({
      done: ["chem"],
      started: [],
      failed: ["curio", "big"],
    });
    expect(
      setTaskLineStatus(["price2"], ["bat1"], "bat1", "done", [], line),
    ).toEqual({
      done: ["bat1"],
      started: [],
      failed: [],
    });
  });
});

describe("dropBlockedProgress", () => {
  it("removes tasks whose blockers are done or started", () => {
    expect(
      dropBlockedProgress(["price2", "keep"], [], ["price2"], line.blockedById),
    ).toEqual({
      done: ["price2", "keep"],
      started: [],
      failed: ["price2"],
    });
    expect(
      dropBlockedProgress(
        ["bat1", "price2", "keep"],
        [],
        ["price2"],
        line.blockedById,
      ),
    ).toEqual({
      done: ["bat1", "keep"],
      started: [],
      failed: [],
    });
    expect(
      applyTaskLineLedger(["bat1", "price2"], ["price2"], ["price2"], line),
    ).toEqual({
      done: ["bat1"],
      started: [],
      failed: [],
    });
  });
});
