import {
  TARKOV_GAME_LOG_MAX_FILE_BYTES,
  classifyLogsRoot,
  formatBindPath,
  isNewerScreenshot,
  isReadableTarkovLogFileName,
  isScreenshotFileName,
  screenshotNamesToInspect,
  screenshotNamesToPrune,
  listSessionStubs,
  logWalkCandidatesFrom,
  mergeBindPath,
  screenshotWalkCandidatesFrom,
  type TarkovLogSessionStub,
} from "@/lib/tarkovGameLogs";
import { notifyTarkovLiveDirsChanged } from "@/lib/tarkovLiveWatch";

const DB_NAME = "zhange-tarkov-game-logs";
const DB_VERSION = 1;
const STORE = "kv";
const LOGS_HANDLE_KEY = "logs-dir";
const SHOTS_HANDLE_KEY = "screenshots-dir";
const LOGS_PATH_KEY = "logs-dir-path";
const SHOTS_PATH_KEY = "screenshots-dir-path";

type FsPermission = "granted" | "denied" | "prompt";
type FsMode = "read" | "readwrite";

export type ReadableDir = {
  name: string;
  queryPermission: (opts?: { mode?: FsMode }) => Promise<FsPermission>;
  requestPermission: (opts?: { mode?: FsMode }) => Promise<FsPermission>;
  values?: () => AsyncIterableIterator<ReadableEntry>;
  entries?: () => AsyncIterableIterator<[string, ReadableEntry]>;
  getDirectoryHandle: (name: string) => Promise<ReadableDir>;
  getFileHandle: (name: string) => Promise<ReadableFile>;
  removeEntry?: (name: string) => Promise<void>;
};

export type ReadableFile = {
  name: string;
  getFile: () => Promise<File>;
};

export type ReadableEntry = {
  kind: "file" | "directory";
  name: string;
  getFile?: () => Promise<File>;
  getDirectoryHandle?: ReadableDir["getDirectoryHandle"];
  getFileHandle?: ReadableDir["getFileHandle"];
  values?: ReadableDir["values"];
  entries?: ReadableDir["entries"];
  queryPermission?: ReadableDir["queryPermission"];
  requestPermission?: ReadableDir["requestPermission"];
};

export type TarkovLogFileRead = {
  name: string;
  text: string;
  lastModified: number;
  size: number;
};

export type TarkovLogSessionRead = {
  folder: string;
  files: TarkovLogFileRead[];
  fingerprint: string;
  skipped: string[];
};

type PickerWindow = Window & {
  showDirectoryPicker?: (opts?: {
    id?: string;
    mode?: FsMode;
    startIn?: "documents" | "desktop" | "downloads" | ReadableDir;
  }) => Promise<ReadableDir>;
};

type FileSystemObserverCtor = new (
  callback: (records: readonly FileSystemChangeRecord[]) => void,
) => {
  observe: (
    handle: ReadableDir,
    opts?: { recursive?: boolean },
  ) => void | Promise<void>;
  disconnect: () => void;
};

type FileSystemChangeRecord = {
  type?: string;
  relativePathComponents?: readonly string[];
  changedHandle?: { name?: string; kind?: string };
};

type ObserverWindow = Window & {
  FileSystemObserver?: FileSystemObserverCtor;
};

export type ResolvedTarkovDir = {
  dir: ReadableDir;
  walk: string[];
  pickedName: string;
};

export type TarkovScreenshotStub = {
  name: string;
  lastModified: number;
  size: number;
};

export function isFileSystemAccessSupported(): boolean {
  if (typeof window === "undefined") return false;
  return typeof (window as PickerWindow).showDirectoryPicker === "function";
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error("打开日志授权存储失败"));
  });
}

async function idbGet<T>(key: string): Promise<T | undefined> {
  const db = await openDb();
  try {
    return await new Promise((resolve, reject) => {
      const req = db.transaction(STORE, "readonly").objectStore(STORE).get(key);
      req.onsuccess = () => resolve(req.result as T | undefined);
      req.onerror = () => reject(req.error || new Error("读取授权目录失败"));
    });
  } finally {
    db.close();
  }
}

async function idbSet(key: string, value: unknown): Promise<void> {
  const db = await openDb();
  try {
    await new Promise<void>((resolve, reject) => {
      const req = db
        .transaction(STORE, "readwrite")
        .objectStore(STORE)
        .put(value, key);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error || new Error("保存授权目录失败"));
    });
  } finally {
    db.close();
  }
}

async function idbDelete(key: string): Promise<void> {
  const db = await openDb();
  try {
    await new Promise<void>((resolve, reject) => {
      const req = db
        .transaction(STORE, "readwrite")
        .objectStore(STORE)
        .delete(key);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error || new Error("清除授权目录失败"));
    });
  } finally {
    db.close();
  }
}

export async function loadStoredLogsDir(): Promise<ReadableDir | null> {
  try {
    const handle = await idbGet<ReadableDir>(LOGS_HANDLE_KEY);
    return handle || null;
  } catch {
    return null;
  }
}

export async function saveLogsDir(handle: ReadableDir): Promise<void> {
  await idbSet(LOGS_HANDLE_KEY, handle);
  notifyTarkovLiveDirsChanged();
}

export async function loadStoredLogsPath(): Promise<string> {
  try {
    const path = await idbGet<string>(LOGS_PATH_KEY);
    return typeof path === "string" ? path : "";
  } catch {
    return "";
  }
}

export async function saveLogsDisplayPath(path: string): Promise<void> {
  await idbSet(LOGS_PATH_KEY, path);
}

export async function clearStoredLogsDir(): Promise<void> {
  await idbDelete(LOGS_HANDLE_KEY);
  await idbDelete(LOGS_PATH_KEY);
  notifyTarkovLiveDirsChanged();
}

export async function loadStoredScreenshotsDir(): Promise<ReadableDir | null> {
  try {
    const handle = await idbGet<ReadableDir>(SHOTS_HANDLE_KEY);
    return handle || null;
  } catch {
    return null;
  }
}

export async function saveScreenshotsDir(handle: ReadableDir): Promise<void> {
  await idbSet(SHOTS_HANDLE_KEY, handle);
  notifyTarkovLiveDirsChanged();
}

export async function loadStoredScreenshotsPath(): Promise<string> {
  try {
    const path = await idbGet<string>(SHOTS_PATH_KEY);
    return typeof path === "string" ? path : "";
  } catch {
    return "";
  }
}

export async function saveScreenshotsDisplayPath(path: string): Promise<void> {
  await idbSet(SHOTS_PATH_KEY, path);
}

export async function clearStoredScreenshotsDir(): Promise<void> {
  await idbDelete(SHOTS_HANDLE_KEY);
  await idbDelete(SHOTS_PATH_KEY);
  notifyTarkovLiveDirsChanged();
}

async function queryDirPermission(
  handle: ReadableDir,
  mode: FsMode,
): Promise<FsPermission> {
  if (typeof handle.queryPermission !== "function") return "granted";
  try {
    return await handle.queryPermission({ mode });
  } catch {
    return "prompt";
  }
}

async function requestDirPermission(
  handle: ReadableDir,
  mode: FsMode,
): Promise<FsPermission> {
  if (typeof handle.requestPermission !== "function") return "granted";
  return handle.requestPermission({ mode });
}

export async function queryLogsDirPermission(
  handle: ReadableDir,
): Promise<FsPermission> {
  return queryDirPermission(handle, "read");
}

export async function requestLogsDirPermission(
  handle: ReadableDir,
): Promise<FsPermission> {
  return requestDirPermission(handle, "read");
}

/** 截图目录要能删已读文件；旧授权只有读权限时仍可定位。 */
export async function queryScreenshotsDirPermission(
  handle: ReadableDir,
): Promise<FsPermission> {
  const write = await queryDirPermission(handle, "readwrite");
  if (write === "granted") return write;
  return queryDirPermission(handle, "read");
}

export async function requestScreenshotsDirPermission(
  handle: ReadableDir,
): Promise<FsPermission> {
  const write = await requestDirPermission(handle, "readwrite");
  if (write === "granted") return write;
  return requestDirPermission(handle, "read");
}

export async function screenshotsDirCanWrite(
  handle: ReadableDir,
): Promise<boolean> {
  return (await queryDirPermission(handle, "readwrite")) === "granted";
}

function requirePicker() {
  const picker = (window as PickerWindow).showDirectoryPicker;
  if (!picker) {
    throw new Error("当前浏览器不支持授权本地目录，请用 Chrome 或 Edge。");
  }
  return picker;
}

export async function pickLogsDirectory(
  startIn?: ReadableDir | null,
): Promise<ReadableDir> {
  return requirePicker()({
    id: "zhange-tarkov-logs",
    mode: "read",
    startIn: startIn || undefined,
  });
}

export async function pickScreenshotsDirectory(
  startIn?: ReadableDir | null,
): Promise<ReadableDir> {
  return requirePicker()({
    id: "zhange-tarkov-screenshots",
    mode: "readwrite",
    startIn: startIn || "documents",
  });
}

export function isFileSystemObserverSupported(): boolean {
  if (typeof window === "undefined") return false;
  return typeof (window as ObserverWindow).FileSystemObserver === "function";
}

export async function observeDirectory(
  handle: ReadableDir,
  onChange: (appeared: string[]) => void,
): Promise<(() => void) | null> {
  const Ctor = (window as ObserverWindow).FileSystemObserver;
  if (!Ctor) return null;
  let dead = false;
  const observer = new Ctor((records) => {
    if (dead) return;
    const appeared: string[] = [];
    for (const record of records) {
      const type = String(record.type || "");
      if (type && type !== "appeared" && type !== "modified") continue;
      const name =
        record.relativePathComponents?.[0] || record.changedHandle?.name || "";
      if (name && !isScreenshotFileName(name)) continue;
      if (name) appeared.push(name);
    }
    onChange(appeared);
  });
  try {
    await Promise.resolve(observer.observe(handle));
  } catch {
    observer.disconnect();
    return null;
  }
  return () => {
    dead = true;
    observer.disconnect();
  };
}

export function isPickerAbort(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    (error as { name: string }).name === "AbortError"
  );
}

function readHandlePathProp(handle: object, key: string): string {
  if (!(key in handle)) return "";
  const value = (handle as Record<string, unknown>)[key];
  return typeof value === "string" ? value.trim() : "";
}

type ParentableDir = ReadableDir & {
  getParent?: () => Promise<ReadableDir | null | undefined>;
};

/** 浏览器通常不给盘符；有非标准 path / getParent 时尽量往上拼。 */
export async function peekNativeDirPath(handle: ReadableDir): Promise<string> {
  for (const key of ["path", "fullPath"]) {
    const value = readHandlePathProp(handle, key);
    if (value) return value.replace(/\//g, "\\").replace(/\\+$/, "");
  }
  const start = handle as ParentableDir;
  if (typeof start.getParent !== "function") return "";
  const names: string[] = [];
  let current: ParentableDir = start;
  for (let depth = 0; depth < 32; depth += 1) {
    const name = (current.name || "").trim();
    if (name) names.unshift(name);
    const getParent = current.getParent;
    if (typeof getParent !== "function") break;
    let parent: ReadableDir | null | undefined;
    try {
      parent = await getParent();
    } catch {
      break;
    }
    if (!parent) break;
    if (parent === current) break;
    current = parent as ParentableDir;
  }
  return formatBindPath(names[0] || "", names.slice(1));
}

export async function displayPathForResolved(
  picked: ReadableDir,
  resolved: ResolvedTarkovDir,
  previous = "",
): Promise<string> {
  const peekedResolved = await peekNativeDirPath(resolved.dir);
  if (peekedResolved) {
    return mergeBindPath(previous, peekedResolved);
  }
  const peekedPicked = await peekNativeDirPath(picked);
  return mergeBindPath(
    previous,
    formatBindPath(peekedPicked || resolved.pickedName, resolved.walk),
  );
}

export async function listDirEntries(handle: ReadableDir): Promise<ReadableEntry[]> {
  const out: ReadableEntry[] = [];
  if (handle.values) {
    for await (const child of handle.values()) out.push(child);
    return out;
  }
  if (handle.entries) {
    for await (const [, child] of handle.entries()) out.push(child);
  }
  return out;
}

async function walkDirectory(
  handle: ReadableDir,
  segments: readonly string[],
): Promise<ReadableDir | null> {
  let current = handle;
  for (const wanted of segments) {
    const children = await listDirEntries(current);
    const hit = children.find(
      (child) =>
        child.kind === "directory" &&
        child.name.toLowerCase() === wanted.toLowerCase(),
    );
    if (!hit) return null;
    current = await current.getDirectoryHandle(hit.name);
  }
  return current;
}

async function resolveByWalks(
  handle: ReadableDir,
  walks: string[][],
  ok: (names: string[], walk: string[]) => boolean,
): Promise<ResolvedTarkovDir | null> {
  for (const walk of walks) {
    const dir = walk.length ? await walkDirectory(handle, walk) : handle;
    if (!dir) continue;
    const names = (await listDirEntries(dir)).map((child) => child.name);
    if (!ok(names, walk)) continue;
    return { dir, walk, pickedName: handle.name };
  }
  return null;
}

export async function resolveLogsDir(handle: ReadableDir): Promise<ReadableDir> {
  return (await resolveLogsDirDetailed(handle)).dir;
}

export async function resolveLogsDirDetailed(
  handle: ReadableDir,
): Promise<ResolvedTarkovDir> {
  const children = await listDirEntries(handle);
  const names = children.map((child) => child.name);
  const kind = classifyLogsRoot(names);
  if (kind === "logs" || kind === "session") {
    return { dir: handle, walk: [], pickedName: handle.name };
  }
  const found = await resolveByWalks(handle, logWalkCandidatesFrom(names), (inner) => {
    const innerKind = classifyLogsRoot(inner);
    return innerKind === "logs" || innerKind === "session";
  });
  if (found) return found;
  throw new Error(
    "这个目录里找不到塔科夫日志。常见位置是游戏目录下的 build\\Logs。也可以选 Steam 库、steamapps、common 或游戏根目录，页面会自动往下走。",
  );
}

export async function resolveScreenshotsDirDetailed(
  handle: ReadableDir,
): Promise<ResolvedTarkovDir> {
  const children = await listDirEntries(handle);
  const names = children.map((child) => child.name);
  const found = await resolveByWalks(
    handle,
    screenshotWalkCandidatesFrom(names),
    (inner, walk) => {
      if (inner.some((name) => isScreenshotFileName(name))) return true;
      return (walk[walk.length - 1] || "").toLowerCase() === "screenshots";
    },
  );
  if (found) return found;
  throw new Error(
    "这个目录里找不到截图。常见位置是「文档\\Escape from Tarkov\\Screenshots」。选择器会打开「文档」，选文档或 Escape from Tarkov 即可。",
  );
}

export async function listLogSessions(
  handle: ReadableDir,
): Promise<TarkovLogSessionStub[]> {
  return (await readLogsIndex(handle)).sessions;
}

export async function readLogsIndex(handle: ReadableDir): Promise<{
  resolved: ResolvedTarkovDir;
  sessions: TarkovLogSessionStub[];
}> {
  const resolved = await resolveLogsDirDetailed(handle);
  const names = (await listDirEntries(resolved.dir)).map((child) => child.name);
  const kind = classifyLogsRoot(names);
  const sessions =
    kind === "session"
      ? listSessionStubs(names, { selfFolder: resolved.dir.name })
      : listSessionStubs(names);
  return { resolved, sessions };
}

async function sessionFileHandles(
  handle: ReadableDir,
  folder: string,
): Promise<ReadableFile[]> {
  const root = await resolveLogsDir(handle);
  const rootChildren = await listDirEntries(root);
  const rootKind = classifyLogsRoot(rootChildren.map((child) => child.name));
  const sessionDir =
    rootKind === "session" ? root : await root.getDirectoryHandle(folder);
  const entries = await listDirEntries(sessionDir);
  const out: ReadableFile[] = [];
  for (const entry of entries) {
    if (entry.kind !== "file" || !isReadableTarkovLogFileName(entry.name)) {
      continue;
    }
    out.push(
      entry.getFile != null
        ? (entry as ReadableFile)
        : await sessionDir.getFileHandle(entry.name),
    );
  }
  return out;
}

function fileFingerprint(file: Pick<File, "name" | "size" | "lastModified">): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function joinFingerprint(parts: string[]): string {
  return [...parts].sort().join("|");
}

export async function peekSessionFingerprint(
  handle: ReadableDir,
  folder: string,
): Promise<string> {
  const handles = await sessionFileHandles(handle, folder);
  const parts: string[] = [];
  for (const fileHandle of handles) {
    const file = await fileHandle.getFile();
    if (file.size > TARKOV_GAME_LOG_MAX_FILE_BYTES) continue;
    parts.push(fileFingerprint(file));
  }
  return joinFingerprint(parts);
}

export async function readSessionLogs(
  handle: ReadableDir,
  folder: string,
): Promise<TarkovLogSessionRead> {
  const handles = await sessionFileHandles(handle, folder);
  const files: TarkovLogFileRead[] = [];
  const skipped: string[] = [];
  for (const fileHandle of handles) {
    const file = await fileHandle.getFile();
    if (file.size > TARKOV_GAME_LOG_MAX_FILE_BYTES) {
      skipped.push(fileHandle.name);
      continue;
    }
    files.push({
      name: fileHandle.name,
      text: await file.text(),
      lastModified: file.lastModified,
      size: file.size,
    });
  }
  files.sort((a, b) => a.lastModified - b.lastModified || a.name.localeCompare(b.name));
  const fingerprint = joinFingerprint(files.map((file) => fileFingerprint(file)));
  return { folder, files, fingerprint, skipped };
}

export async function listRecentScreenshots(
  handle: ReadableDir,
  limit = 12,
): Promise<TarkovScreenshotStub[]> {
  const { dir } = await resolveScreenshotsDirDetailed(handle);
  const entries = await listDirEntries(dir);
  const files: TarkovScreenshotStub[] = [];
  for (const entry of entries) {
    if (entry.kind !== "file" || !isScreenshotFileName(entry.name)) continue;
    const fileHandle =
      entry.getFile != null
        ? (entry as ReadableFile)
        : await dir.getFileHandle(entry.name);
    const file = await fileHandle.getFile();
    files.push({
      name: file.name,
      lastModified: file.lastModified,
      size: file.size,
    });
  }
  files.sort((a, b) => b.lastModified - a.lastModified);
  return files.slice(0, Math.max(0, limit));
}

export type TarkovScreenshotRead = TarkovScreenshotStub & { file: File };

export async function readScreenshotByName(
  dir: ReadableDir,
  name: string,
): Promise<TarkovScreenshotRead | null> {
  if (!isScreenshotFileName(name)) return null;
  try {
    const fileHandle = await dir.getFileHandle(name);
    const file = await fileHandle.getFile();
    return {
      name: file.name,
      lastModified: file.lastModified,
      size: file.size,
      file,
    };
  } catch {
    return null;
  }
}

export async function removeScreenshotFiles(
  dir: ReadableDir,
  names: readonly string[],
): Promise<string[]> {
  if (typeof dir.removeEntry !== "function") return [];
  const removed: string[] = [];
  for (const name of names) {
    try {
      await dir.removeEntry(name);
      removed.push(name);
    } catch {
      /* 游戏可能还占着文件 */
    }
  }
  return removed;
}

export async function pruneConsumedScreenshots(
  dir: ReadableDir,
  names: readonly string[],
  keepLatest: string | null,
  keepMax: number,
): Promise<string[]> {
  return removeScreenshotFiles(
    dir,
    screenshotNamesToPrune(names, keepLatest, keepMax),
  );
}

export async function listScreenshotFileNames(
  dir: ReadableDir,
): Promise<string[]> {
  const entries = await listDirEntries(dir);
  return entries
    .filter((entry) => entry.kind === "file" && isScreenshotFileName(entry.name))
    .map((entry) => entry.name);
}

export async function pollLatestScreenshot(
  handle: ReadableDir,
  seenNames: ReadonlySet<string>,
  cachedDir?: ReadableDir | null,
): Promise<{
  names: string[];
  latest: TarkovScreenshotRead | null;
  dir: ReadableDir;
}> {
  const dir = cachedDir || (await resolveScreenshotsDirDetailed(handle)).dir;
  const names = await listScreenshotFileNames(dir);
  const inspect = screenshotNamesToInspect(names, seenNames);
  let latest: TarkovScreenshotRead | null = null;
  for (const name of inspect) {
    const row = await readScreenshotByName(dir, name);
    if (!row) continue;
    if (!latest || isNewerScreenshot(latest, row)) latest = row;
  }
  return { names, latest, dir };
}
