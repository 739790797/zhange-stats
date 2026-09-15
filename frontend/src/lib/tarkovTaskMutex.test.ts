import { describe, expect, it } from "vitest";
import { applyMutexLedger, mutexIndexFromTasks } from "./tarkovTaskMutex";

const chem = mutexIndexFromTasks([
  { id: "chem", mutex_ids: ["curio", "big"] },
  { id: "curio", mutex_ids: ["chem", "big"] },
  { id: "big", mutex_ids: ["chem", "curio"] },
]);

describe("applyMutexLedger", () => {
  it("fails started mutex neighbors of a completed task", () => {
    expect(applyMutexLedger(["chem"], ["curio"], [], chem)).toEqual({
      done: ["chem"],
      started: [],
      failed: ["curio"],
    });
  });

  it("does not allow the chemical-4 trio to stay completed together", () => {
    const next = applyMutexLedger(["chem", "curio", "big"], [], [], chem);
    expect(next.done).toEqual(["big"]);
    expect(next.failed.sort()).toEqual(["chem", "curio"]);
  });

  it("prefers the later log completion in a mutex group", () => {
    const next = applyMutexLedger(
      ["chem", "curio", "big"],
      [],
      [],
      chem,
      ["chem", "big"],
    );
    expect(next.done).toEqual(["big"]);
    expect(next.failed.sort()).toEqual(["chem", "curio"]);
  });
});
