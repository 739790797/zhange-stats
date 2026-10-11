import { describe, expect, it } from "vitest";
import {
  createTarkovLogReadCache,
  peekSessionFingerprint,
  readLogsIndex,
  readSessionLogs,
  readStattedSessionLogs,
  retainTarkovLogFolders,
  statSessionLogs,
  type ReadableDir,
  type ReadableEntry,
} from "./tarkovGameLogAccess";

type FileNode = { kind: "file"; bytes: Uint8Array<ArrayBuffer>; lastModified: number };
type DirNode = { kind: "directory"; children: Map<string, FileNode | DirNode> };

type Counters = { lists: number; wholeReads: number; slicedFrom: number[] };

const encoder = new TextEncoder();

function dirNode(children: Record<string, FileNode | DirNode>): DirNode {
  return { kind: "directory", children: new Map(Object.entries(children)) };
}

function fileNode(text: string, lastModified: number): FileNode {
  return { kind: "file", bytes: encoder.encode(text), lastModified };
}

function appendTo(node: FileNode, text: string, lastModified: number) {
  const extra = encoder.encode(text);
  const bytes = new Uint8Array(node.bytes.length + extra.length);
  bytes.set(node.bytes);
  bytes.set(extra, node.bytes.length);
  node.bytes = bytes;
  node.lastModified = lastModified;
}

function snapshot(name: string, node: FileNode, counters: Counters): File {
  const file = new File([node.bytes], name, { lastModified: node.lastModified });
  return {
    name,
    size: file.size,
    lastModified: file.lastModified,
    text: () => {
      counters.wholeReads += 1;
      return file.text();
    },
    arrayBuffer: () => {
      counters.wholeReads += 1;
      return file.arrayBuffer();
    },
    slice: (start?: number) => {
      counters.slicedFrom.push(start ?? 0);
      return file.slice(start);
    },
  } as unknown as File;
}

function memoryDir(name: string, node: DirNode, counters: Counters): ReadableDir & ReadableEntry {
  const fileEntry = (fileName: string, child: FileNode): ReadableEntry => ({
    kind: "file",
    name: fileName,
    getFile: async () => snapshot(fileName, child, counters),
  });
  return {
    kind: "directory",
    name,
    queryPermission: async () => "granted",
    requestPermission: async () => "granted",
    values: async function* values() {
      counters.lists += 1;
      for (const [childName, child] of node.children) {
        yield child.kind === "directory"
          ? memoryDir(childName, child, counters)
          : fileEntry(childName, child);
      }
    },
    getDirectoryHandle: async (childName: string) => {
      const child = node.children.get(childName);
      if (child?.kind !== "directory") throw new Error(`NotFound ${childName}`);
      return memoryDir(childName, child, counters);
    },
    getFileHandle: async (childName: string) => {
      const child = node.children.get(childName);
      if (child?.kind !== "file") throw new Error(`NotFound ${childName}`);
      return { name: childName, getFile: async () => snapshot(childName, child, counters) };
    },
  };
}

const SESSION = "log_2024.02.05_19-00-00_0.14.0.0.28375";
const NEXT_SESSION = "log_2024.02.05_21-00-00_0.14.0.0.28375";

function appLines(from: number, count: number): string {
  return Array.from(
    { length: count },
    (_, i) => `2024-02-05 19:${String(from + i).padStart(2, "0")}:00.000|x|Info|application|LocationLoaded:1.00\n`,
  ).join("");
}

async function liveRead(handle: ReadableDir, folder: string, cache = createTarkovLogReadCache()) {
  await readLogsIndex(handle, cache);
  const stat = await statSessionLogs(handle, folder, cache);
  return { stat, read: await readStattedSessionLogs(stat, cache), cache };
}

describe("cached live log reads", () => {
  it("match readSessionLogs while skipping unchanged files and re-reading only appended bytes", async () => {
    const counters: Counters = { lists: 0, wholeReads: 0, slicedFrom: [] };
    const app = fileNode(appLines(0, 40), 100);
    const notifications = fileNode("2024-02-05 19:00:01.000|x|Info|push-notifications|hello\n", 90);
    const tree = dirNode({
      build: dirNode({
        Logs: dirNode({
          [SESSION]: dirNode({ "application.log": app, "notifications.log": notifications }),
        }),
      }),
    });
    const picked = memoryDir("EscapeFromTarkov", tree, counters);
    const cache = createTarkovLogReadCache();

    const first = await liveRead(picked, SESSION, cache);
    expect(cache.root?.walk).toEqual(["build", "Logs"]);
    expect(first.read).toEqual(await readSessionLogs(picked, SESSION));
    expect(first.stat.fingerprint).toBe(await peekSessionFingerprint(picked, SESSION));

    appendTo(app, appLines(40, 2), 200);
    counters.lists = 0;
    counters.wholeReads = 0;
    counters.slicedFrom = [];
    const second = await liveRead(picked, SESSION, cache);
    expect(counters.lists).toBe(2);
    expect(counters.wholeReads).toBe(0);
    expect(counters.slicedFrom).toHaveLength(1);
    expect(counters.slicedFrom[0]).toBeGreaterThan(0);
    const fresh = await readSessionLogs(picked, SESSION);
    expect(second.read).toEqual(fresh);
    expect(second.stat.fingerprint).toBe(fresh.fingerprint);
    const notificationsRead = (read: typeof first.read) =>
      read.files.find((file) => file.name === "notifications.log");
    expect(notificationsRead(second.read)).toBe(notificationsRead(first.read));
  });

  it("keeps working when a session folder itself was picked and drops folders it no longer reads", async () => {
    const counters: Counters = { lists: 0, wholeReads: 0, slicedFrom: [] };
    const app = fileNode(appLines(0, 3), 100);
    const sessionPicked = memoryDir(SESSION, dirNode({ "application.log": app }), counters);
    const own = await liveRead(sessionPicked, SESSION);
    expect(own.cache.rootIsSession).toBe(true);
    expect(own.read).toEqual(await readSessionLogs(sessionPicked, SESSION));

    const logs = memoryDir(
      "Logs",
      dirNode({
        [SESSION]: dirNode({ "application.log": fileNode(appLines(0, 2), 1) }),
        [NEXT_SESSION]: dirNode({ "application.log": fileNode(appLines(10, 2), 2) }),
      }),
      counters,
    );
    const cache = createTarkovLogReadCache();
    const index = await readLogsIndex(logs, cache);
    expect(index.sessions.map((row) => row.folder)).toEqual([NEXT_SESSION, SESSION]);
    for (const folder of [SESSION, NEXT_SESSION]) {
      await readStattedSessionLogs(await statSessionLogs(logs, folder, cache), cache);
    }
    retainTarkovLogFolders(cache, [NEXT_SESSION]);
    expect([...cache.texts.keys()]).toEqual([NEXT_SESSION]);
    expect([...cache.sessionDirs.keys()]).toEqual([NEXT_SESSION]);

    await readLogsIndex(memoryDir("Logs", dirNode({}), counters), cache).catch(() => null);
    expect(cache.texts.size).toBe(0);
  });
});
