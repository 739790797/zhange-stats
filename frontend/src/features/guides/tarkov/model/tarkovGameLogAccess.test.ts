import { describe, expect, it } from "vitest";
import { assistantBoundToDir, isAssistantDir } from "./assistantTarkovDir";
import type { AssistantBoundDir, AssistantDirEntry } from "./assistantHostFiles";
import {
  createTarkovLogReadCache,
  peekSessionFingerprint,
  pollLatestScreenshot,
  readLogsIndex,
  readScreenshotByName,
  readSessionApplicationLogs,
  readSessionLogs,
  readStattedSessionLogs,
  retainTarkovLogFolders,
  shouldStoreDirHandle,
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

/** 战鸽助手：list 回名字+大小+修改时间，读正文 / 读图片字节各自过一次桥。 */
function assistantFixture() {
  const files = new Map<string, { text: string; lastModified: number }>();
  const counters = { lists: 0, readText: 0, readBytes: 0 };
  const sizeOf = (text: string) => encoder.encode(text).length;

  function set(rel: string, text: string, lastModified: number) {
    files.set(rel, { text, lastModified });
  }

  function entries(rel: string): AssistantDirEntry[] {
    counters.lists += 1;
    const prefix = rel ? `${rel}/` : "";
    const seen = new Map<string, AssistantDirEntry>();
    for (const [path, value] of files) {
      if (!path.startsWith(prefix)) continue;
      const rest = path.slice(prefix.length);
      const slash = rest.indexOf("/");
      const name = slash < 0 ? rest : rest.slice(0, slash);
      seen.set(
        name,
        slash < 0
          ? { kind: "file", name, lastModified: value.lastModified, size: sizeOf(value.text) }
          : { kind: "directory", name },
      );
    }
    return [...seen.values()];
  }

  const bound: AssistantBoundDir = {
    path: "D:\\Games\\Escape from Tarkov\\build\\Logs",
    list: async (rel = "") => entries(rel),
    readText: async (rel) => {
      counters.readText += 1;
      const hit = files.get(rel);
      return {
        text: hit?.text || "",
        lastModified: hit?.lastModified || 0,
        size: sizeOf(hit?.text || ""),
      };
    },
    readBytes: async () => {
      counters.readBytes += 1;
      return new Uint8Array([1, 2, 3]).buffer;
    },
  };
  return { bound, counters, set, sizeOf, dir: assistantBoundToDir(bound) };
}

describe("assistant-bound directories", () => {
  it("never asks the bridge for log text while only fingerprints are needed", async () => {
    const fixture = assistantFixture();
    const notify = "2024-02-05 19:00:01.000|x|Info|push-notifications|hi\n";
    fixture.set(`${SESSION}/application.log`, appLines(0, 40), 100);
    fixture.set(`${SESSION}/notifications.log`, notify, 90);
    const cache = createTarkovLogReadCache();

    const index = await readLogsIndex(fixture.dir, cache);
    expect(index.sessions.map((row) => row.folder)).toEqual([SESSION]);
    const stat = await statSessionLogs(fixture.dir, SESSION, cache);
    expect(fixture.counters.readText).toBe(0);
    expect(stat.files.every((row) => row.file === null)).toBe(true);
    expect(stat.fingerprint).toBe(
      `application.log:${fixture.sizeOf(appLines(0, 40))}:100|notifications.log:${fixture.sizeOf(notify)}:90`,
    );

    const first = await readStattedSessionLogs(stat, cache);
    expect(fixture.counters.readText).toBe(2);
    expect(first.files.map((file) => file.name)).toEqual([
      "notifications.log",
      "application.log",
    ]);
    expect(first).toEqual(await readSessionLogs(fixture.dir, SESSION));
    expect(first.fingerprint).toBe(stat.fingerprint);
    const textReads = fixture.counters.readText;

    // 下一轮什么都没变：只列目录，不再过桥读正文。
    const idle = await statSessionLogs(fixture.dir, SESSION, cache);
    expect(idle.fingerprint).toBe(stat.fingerprint);
    const again = await readStattedSessionLogs(idle, cache);
    expect(fixture.counters.readText).toBe(textReads);
    expect(again.files).toEqual(first.files);

    fixture.set(`${SESSION}/application.log`, appLines(0, 41), 200);
    const next = await statSessionLogs(fixture.dir, SESSION, cache);
    expect(next.fingerprint).not.toBe(stat.fingerprint);
    const grown = await readStattedSessionLogs(next, cache);
    // 只有变了的那一份过桥。
    expect(fixture.counters.readText).toBe(textReads + 1);
    expect(grown).toEqual(await readSessionLogs(fixture.dir, SESSION));
  });

  it("resolves the logs root once when one cache serves User whole history scan", async () => {
    const build = () => {
      const fixture = assistantFixture();
      fixture.set(`${SESSION}/application.log`, appLines(0, 2), 1);
      fixture.set(`${SESSION}/notifications.log`, "notify\n", 1);
      fixture.set(`${NEXT_SESSION}/application.log`, appLines(10, 2), 2);
      return fixture;
    };
    const folders = [SESSION, NEXT_SESSION];

    const cached = build();
    const cache = createTarkovLogReadCache();
    const withCache = [];
    for (const folder of folders) {
      withCache.push(await readSessionApplicationLogs(cached.dir, folder, cache));
    }
    expect(withCache[0]?.files.map((file) => file.name)).toEqual(["application.log"]);

    const plain = build();
    const without = [];
    for (const folder of folders) {
      without.push(await readSessionApplicationLogs(plain.dir, folder));
    }
    expect(withCache).toEqual(without);
    // 不带缓存：每个文件夹都重新解析日志根（列两次根）再列自己；带缓存：根只解析一次。
    expect(plain.counters.lists).toBe(3 * folders.length);
    expect(cached.counters.lists).toBe(2 + folders.length);
    expect(cached.counters.readText).toBe(plain.counters.readText);

    const full = await readSessionLogs(cached.dir, SESSION, { cache });
    expect(full).toEqual(await readSessionLogs(plain.dir, SESSION));
  });

  it("takes screenshot metadata from the listing instead of pulling image bytes", async () => {
    const fixture = assistantFixture();
    const older = "2026-10-13[21-35]_19.91 (0).png";
    const newer = "2026-10-13[21-36]_20.10 (0).png";
    fixture.set(older, "fake-png-bytes", 500);
    fixture.set(newer, "fake-png-bytes-2", 900);

    expect(await readScreenshotByName(fixture.dir, older)).toEqual({
      name: older,
      size: fixture.sizeOf("fake-png-bytes"),
      lastModified: 500,
    });
    expect(await readScreenshotByName(fixture.dir, "missing.png")).toBeNull();
    expect(fixture.counters.readBytes).toBe(0);
    expect(fixture.counters.readText).toBe(0);

    const listsBefore = fixture.counters.lists;
    const poll = await pollLatestScreenshot(fixture.dir, new Set(), fixture.dir);
    // 整轮只列一次目录，逐张看时不重列、不读字节。
    expect(fixture.counters.lists - listsBefore).toBe(1);
    expect(fixture.counters.readBytes).toBe(0);
    expect(poll.names).toEqual([older, newer]);
    expect(poll.latest).toEqual({
      name: newer,
      size: fixture.sizeOf("fake-png-bytes-2"),
      lastModified: 900,
    });
  });

  it("still reads metadata through file handles for browser-granted folders", async () => {
    const counters: Counters = { lists: 0, wholeReads: 0, slicedFrom: [] };
    const shot = "2026-10-13[21-35]_19.91 (0).png";
    const dir = memoryDir("Screenshots", dirNode({ [shot]: fileNode("png", 700) }), counters);
    expect(await readScreenshotByName(dir, shot)).toEqual({ name: shot, size: 3, lastModified: 700 });
    expect(counters.wholeReads).toBe(0);
    expect(counters.lists).toBe(0);
    expect(await readScreenshotByName(dir, "missing.png")).toBeNull();
  });

  it("never tries to store User bound handle in IndexedDB", () => {
    const fixture = assistantFixture();
    expect(isAssistantDir(fixture.dir)).toBe(true);
    const plain = memoryDir("Logs", dirNode({}), { lists: 0, wholeReads: 0, slicedFrom: [] });
    expect(isAssistantDir(plain)).toBe(false);
    expect(shouldStoreDirHandle(fixture.dir, fixture.bound)).toBe(false);
    // 助手绑定在时一律不存（读取一侧也先看绑定）。
    expect(shouldStoreDirHandle(plain, fixture.bound)).toBe(false);
    expect(shouldStoreDirHandle(fixture.dir, null)).toBe(false);
    expect(shouldStoreDirHandle(plain, null)).toBe(true);
  });
});
