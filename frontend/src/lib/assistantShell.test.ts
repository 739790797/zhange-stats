import { describe, expect, it } from "vitest";
import {
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
