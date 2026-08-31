import { describe, expect, it } from "vitest";
import { parseTarkovRaidDockOpen } from "./tarkovRaidDockPrefs";

describe("parseTarkovRaidDockOpen", () => {
  it("defaults to open when empty or junk", () => {
    expect(parseTarkovRaidDockOpen(null)).toBe(true);
    expect(parseTarkovRaidDockOpen("")).toBe(true);
    expect(parseTarkovRaidDockOpen("nope")).toBe(true);
    expect(parseTarkovRaidDockOpen("[]")).toBe(true);
  });

  it("reads boolean, 0/1, and { open }", () => {
    expect(parseTarkovRaidDockOpen("true")).toBe(true);
    expect(parseTarkovRaidDockOpen("1")).toBe(true);
    expect(parseTarkovRaidDockOpen("false")).toBe(false);
    expect(parseTarkovRaidDockOpen("0")).toBe(false);
    expect(parseTarkovRaidDockOpen(JSON.stringify({ open: false }))).toBe(
      false,
    );
    expect(parseTarkovRaidDockOpen(JSON.stringify({ open: true }))).toBe(true);
  });
});
