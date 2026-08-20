import { describe, expect, it } from "vitest";
import {
  averageWipeLength,
  buildWipeRows,
  type TarkovWipeStart,
} from "./tarkovWipeLength";

describe("buildWipeRows", () => {
  const starts: TarkovWipeStart[] = [
    { name: "A", start: "2024-01-01T00:00:00.000Z" },
    { name: "B", start: "2024-02-01T00:00:00.000Z" },
    { name: "C", start: "2024-04-01T00:00:00.000Z" },
  ];

  it("marks the latest wipe ongoing and lists newest first", () => {
    const now = new Date("2024-04-11T00:00:00.000Z");
    const rows = buildWipeRows(starts, now);
    expect(rows.map((r) => r.name)).toEqual(["C", "B", "A"]);
    expect(rows[0]).toMatchObject({ ongoing: true, lengthDays: 10 });
    expect(rows[1]).toMatchObject({
      ongoing: false,
      lengthDays: 60,
    });
    expect(rows[2].lengthDays).toBe(31);
  });

  it("averages the last finished wipes", () => {
    const now = new Date("2024-04-11T00:00:00.000Z");
    expect(averageWipeLength(starts, now)).toBe(Math.floor((60 + 31) / 2));
  });
});
