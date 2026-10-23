import { describe, expect, it } from "vitest";
import { assistantBoundToDir, assistantDirWatch } from "./assistantTarkovDir";
import type { AssistantBoundDir } from "./assistantHostFiles";
import type { ReadableDir } from "./tarkovGameLogAccess";

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
