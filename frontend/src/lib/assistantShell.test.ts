import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ASSISTANT_EMBED_STORAGE_KEY,
  ASSISTANT_PANE_STORAGE_KEY,
  assistantBodyPaneFromLocation,
  assistantEmbedFromLocation,
  assistantSearchPaneFromLocation,
} from "./assistantShell";
import { assistantBoundToDir, assistantDirWatch } from "./assistantTarkovDir";
import type { AssistantBoundDir } from "./assistantShell";
import type { ReadableDir } from "./tarkovGameLogAccess";

describe("assistantEmbedFromLocation", () => {
  it("accepts the host flag, the query, or a stored mark", () => {
    expect(assistantEmbedFromLocation("", { embed: true }, null)).toBe(true);
    expect(assistantEmbedFromLocation("?embed=assistant", null, null)).toBe(true);
    expect(assistantEmbedFromLocation("", null, "1")).toBe(true);
    expect(assistantEmbedFromLocation("?embed=1", null, null)).toBe(false);
    expect(assistantEmbedFromLocation("", { embed: false }, null)).toBe(false);
  });
});

describe("assistantBodyPaneFromLocation", () => {
  it("accepts the host flag, the query, or a stored mark", () => {
    expect(assistantBodyPaneFromLocation("", { pane: "body" }, null)).toBe(true);
    expect(assistantBodyPaneFromLocation("", { pane: true }, null)).toBe(true);
    expect(assistantBodyPaneFromLocation("?pane=body", null, null)).toBe(true);
    expect(assistantBodyPaneFromLocation("", null, "body")).toBe(true);
    expect(assistantBodyPaneFromLocation("?pane=1", null, null)).toBe(false);
    expect(assistantBodyPaneFromLocation("", { pane: false }, null)).toBe(false);
  });
});

describe("assistantSearchPaneFromLocation", () => {
  it("only accepts pane=search on the current address", () => {
    expect(assistantSearchPaneFromLocation("?pane=search")).toBe(true);
    expect(assistantSearchPaneFromLocation("?embed=assistant&pane=search")).toBe(true);
    expect(assistantSearchPaneFromLocation("?pane=body")).toBe(false);
    expect(assistantSearchPaneFromLocation("")).toBe(false);
  });
});

describe("isAssistantEmbed / isAssistantBodyPane storage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  function stubWindow(search: string, storage: "ok" | "blocked" | "full") {
    const marks = new Map<string, string>();
    const writes: string[] = [];
    const sessionStorage = {
      getItem: (key: string) => marks.get(key) ?? null,
      setItem: (key: string, value: string) => {
        if (storage === "full") {
          throw new DOMException("quota", "QuotaExceededError");
        }
        writes.push(key);
        marks.set(key, value);
      },
    };
    const win = {
      location: { search },
      get sessionStorage() {
        if (storage === "blocked") {
          throw new DOMException("denied", "SecurityError");
        }
        return sessionStorage;
      },
    };
    vi.stubGlobal("window", win);
    return { win, writes };
  }

  it("does not throw when site storage is blocked, and keeps the mark in memory", async () => {
    const { win } = stubWindow("?embed=assistant&pane=body", "blocked");
    const shell = await import("./assistantShell");
    expect(shell.isAssistantEmbed()).toBe(true);
    expect(shell.isAssistantBodyPane()).toBe(true);

    win.location.search = "";
    expect(shell.isAssistantEmbed()).toBe(true);
    expect(shell.isAssistantBodyPane()).toBe(true);
  });

  it("reports a plain visit as not embedded when storage is blocked", async () => {
    stubWindow("", "blocked");
    const shell = await import("./assistantShell");
    expect(shell.isAssistantEmbed()).toBe(false);
    expect(shell.isAssistantBodyPane()).toBe(false);
  });

  it("survives a full storage quota", async () => {
    stubWindow("?embed=assistant", "full");
    const shell = await import("./assistantShell");
    expect(() => shell.rememberAssistantEmbed()).not.toThrow();
    expect(shell.isAssistantEmbed()).toBe(true);
  });

  it("writes each session mark once instead of on every call", async () => {
    const { writes } = stubWindow("?embed=assistant&pane=body", "ok");
    const shell = await import("./assistantShell");
    for (let i = 0; i < 3; i += 1) {
      expect(shell.isAssistantEmbed()).toBe(true);
      expect(shell.isAssistantBodyPane()).toBe(true);
    }
    expect(writes).toEqual([
      ASSISTANT_EMBED_STORAGE_KEY,
      ASSISTANT_PANE_STORAGE_KEY,
    ]);
  });
});

describe("assistantBoundToDir", () => {
  function binding(): AssistantBoundDir & { removed: string[] } {
    const tree: Record<string, { kind: "file" | "directory"; name: string; text?: string; lastModified?: number }[]> = {
      "": [
        { kind: "directory", name: "Logs" },
        { kind: "file", name: "shot.png", lastModified: 5 },
      ],
      Logs: [{ kind: "file", name: "log.txt", text: "hello", lastModified: 9 }],
    };
    const removed: string[] = [];
    return {
      path: "D:\\Escape from Tarkov\\Screenshots",
      removed,
      list: async (relativeDir = "") => tree[relativeDir] || [],
      readText: async (relativePath) => {
        const folder = relativePath.includes("/")
          ? relativePath.slice(0, relativePath.lastIndexOf("/"))
          : "";
        const name = relativePath.slice(folder.length ? folder.length + 1 : 0);
        const hit = (tree[folder] || []).find((row) => row.name === name);
        return { text: hit?.text || "", lastModified: hit?.lastModified || 0, size: 5 };
      },
      readBytes: async () => new Uint8Array([1, 2, 3]).buffer,
      remove: async (paths) => {
        removed.push(...paths);
        return paths;
      },
      watch: () => () => undefined,
    };
  }

  it("lists children, reads text, and deletes by relative path", async () => {
    const bound = binding();
    const dir = assistantBoundToDir(bound) as ReadableDir & { path: string };
    expect(dir.path).toBe("D:\\Escape from Tarkov\\Screenshots");
    expect(dir.name).toBe("Screenshots");
    const logs = await dir.getDirectoryHandle("Logs");
    const file = await logs.getFileHandle("log.txt");
    expect(await (await file.getFile()).text()).toBe("hello");
    await dir.removeEntry?.("shot.png");
    expect(bound.removed).toEqual(["shot.png"]);
    expect(assistantDirWatch(dir)).toBeTypeOf("function");
    expect(assistantDirWatch(logs)).toBeNull();
  });
});
