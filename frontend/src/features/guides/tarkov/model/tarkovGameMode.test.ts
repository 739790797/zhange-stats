import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  TARKOV_GAME_MODE_STORAGE_KEY,
  getTarkovGameMode,
  loadTarkovGameMode,
  parseTarkovGameMode,
  persistTarkovGameMode,
  resetTarkovGameModeRuntime,
} from "./tarkovGameMode";

describe("tarkovGameMode", () => {
  it("parses pve and falls back to pvp", () => {
    expect(parseTarkovGameMode("pve")).toBe("pve");
    expect(parseTarkovGameMode("PVE")).toBe("pve");
    expect(parseTarkovGameMode("pvp")).toBe("pvp");
    expect(parseTarkovGameMode("regular")).toBe("pvp");
    expect(parseTarkovGameMode("")).toBe("pvp");
  });
});

describe("tarkovGameMode persistence", () => {
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
    });
    resetTarkovGameModeRuntime();
  });

  afterEach(() => {
    resetTarkovGameModeRuntime();
    vi.unstubAllGlobals();
  });

  it("remembers pve after a fresh runtime hydrate", () => {
    persistTarkovGameMode("pve");
    expect(mem.get(TARKOV_GAME_MODE_STORAGE_KEY)).toBe("pve");
    resetTarkovGameModeRuntime();
    expect(getTarkovGameMode()).toBe("pve");
    expect(loadTarkovGameMode()).toBe("pve");
  });

  it("defaults to pvp when nothing is stored", () => {
    expect(getTarkovGameMode()).toBe("pvp");
  });
});
