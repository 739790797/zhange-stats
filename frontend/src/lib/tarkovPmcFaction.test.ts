import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetTarkovGameModeRuntime } from "./tarkovGameMode";
import {
  TARKOV_PMC_FACTION_STORAGE_KEY,
  filterTasksByFaction,
  loadTarkovPmcFaction,
  parseTarkovPmcFaction,
  persistTarkovPmcFaction,
  resetTarkovPmcFactionRuntime,
  taskVisibleForFaction,
  tarkovPmcFactionLabel,
} from "./tarkovPmcFaction";

describe("tarkovPmcFaction parse", () => {
  it("accepts bear / usec and ignores the rest", () => {
    expect(parseTarkovPmcFaction("BEAR")).toBe("bear");
    expect(parseTarkovPmcFaction("usec")).toBe("usec");
    expect(parseTarkovPmcFaction("Any")).toBe("");
    expect(parseTarkovPmcFaction("")).toBe("");
    expect(parseTarkovPmcFaction("pmc")).toBe("");
  });

  it("labels stored keys with dump casing", () => {
    expect(tarkovPmcFactionLabel("bear")).toBe("BEAR");
    expect(tarkovPmcFactionLabel("usec")).toBe("USEC");
    expect(tarkovPmcFactionLabel("")).toBe("");
  });
});

describe("taskVisibleForFaction", () => {
  it("shows everything until a faction is chosen", () => {
    expect(taskVisibleForFaction("USEC", "")).toBe(true);
    expect(taskVisibleForFaction("BEAR", "")).toBe(true);
    expect(taskVisibleForFaction("Any", "")).toBe(true);
  });

  it("keeps Any plus the matching PMC line", () => {
    expect(taskVisibleForFaction("Any", "usec")).toBe(true);
    expect(taskVisibleForFaction("", "usec")).toBe(true);
    expect(taskVisibleForFaction("USEC", "usec")).toBe(true);
    expect(taskVisibleForFaction("BEAR", "usec")).toBe(false);
    expect(taskVisibleForFaction("bear", "bear")).toBe(true);
    expect(taskVisibleForFaction("USEC", "bear")).toBe(false);
  });

  it("filters list rows without mutating the source", () => {
    const rows = [
      { id: "a", faction_name: "Any" },
      { id: "u", faction_name: "USEC" },
      { id: "b", faction_name: "BEAR" },
    ];
    expect(filterTasksByFaction(rows, "").map((row) => row.id)).toEqual([
      "a",
      "u",
      "b",
    ]);
    expect(filterTasksByFaction(rows, "usec").map((row) => row.id)).toEqual([
      "a",
      "u",
    ]);
    expect(rows).toHaveLength(3);
  });
});

describe("tarkovPmcFaction persistence", () => {
  const mem = new Map<string, string>();

  beforeEach(() => {
    mem.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => mem.get(key) ?? null,
      setItem: (key: string, value: string) => {
        mem.set(key, value);
      },
      removeItem: (key: string) => {
        mem.delete(key);
      },
    });
    vi.stubGlobal("window", {
      localStorage: globalThis.localStorage,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => true,
    });
    resetTarkovGameModeRuntime();
    resetTarkovPmcFactionRuntime();
  });

  afterEach(() => {
    resetTarkovPmcFactionRuntime();
    resetTarkovGameModeRuntime();
    vi.unstubAllGlobals();
  });

  it("remembers pvp and pve separately", () => {
    persistTarkovPmcFaction("pvp", "usec");
    persistTarkovPmcFaction("pve", "bear");
    expect(loadTarkovPmcFaction("pvp")).toBe("usec");
    expect(loadTarkovPmcFaction("pve")).toBe("bear");
    const stored = JSON.parse(mem.get(TARKOV_PMC_FACTION_STORAGE_KEY) || "{}");
    expect(stored).toEqual({ pvp: "usec", pve: "bear" });
  });

  it("clears one mode without touching the other", () => {
    persistTarkovPmcFaction("pvp", "bear");
    persistTarkovPmcFaction("pve", "usec");
    persistTarkovPmcFaction("pvp", "");
    expect(loadTarkovPmcFaction("pvp")).toBe("");
    expect(loadTarkovPmcFaction("pve")).toBe("usec");
  });
});
