import {
  TARKOV_GAME_LOG_MAX_FILE_BYTES,
  classifyLogsRoot,
  formatBindPath,
  isNewerScreenshot,
  isReadableTarkovLogFileName,
  isScreenshotFileName,
  screenshotNamesToInspect,
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

export type ReadableDir = {
  name: string;
  queryPermission: (opts?: { mode?: "read" }) => Promise<FsPermission>;
  requestPermission: (opts?: { mode?: "read" }) => Promise<FsPermission>;
  values?: () => AsyncIterableIterator<ReadableEntry>;
  entries?: () => AsyncIterableIterator<[string, ReadableEntry]>;
  getDirectoryHandle: (name: string) => Promise<ReadableDir>;
  getFileHandle: (name: string) => Promise<ReadableFile>;
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
    mode?: "read";
    startIn?: "documents" | "desktop" | "downloads" | ReadableDir;
  }) => Promise<ReadableDir>;
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

export async function queryLogsDirPermission(
  handle: ReadableDir,
): Promise<FsPermission> {
  if (typeof handle.queryPermission !== "function") return "granted";
  try {
    return await handle.queryPermission({ mode: "read" });
  } catch {
    return "prompt";
  }
}

export async function requestLogsDirPermission(
  handle: ReadableDir,
): Promise<FsPermission> {
  if (typeof handle.requestPermission !== "function") return "granted";
  return handle.requestPermission({ mode: "read" });
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
    mode: "read",
    startIn: startIn || "documents",
  });
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

export async function pollLatestScreenshot(
  handle: ReadableDir,
  seenNames: ReadonlySet<string>,
): Promise<{
  names: string[];
  latest: TarkovScreenshotRead | null;
}> {
  const { dir } = await resolveScreenshotsDirDetailed(handle);
  const entries = await listDirEntries(dir);
  const files = entries.filter(
    (entry) => entry.kind === "file" && isScreenshotFileName(entry.name),
  );
  const names = files.map((entry) => entry.name);
  const inspect = new Set(screenshotNamesToInspect(names, seenNames));
  let latest: TarkovScreenshotRead | null = null;
  for (const entry of files) {
    if (!inspect.has(entry.name)) continue;
    const fileHandle =
      entry.getFile != null
        ? (entry as ReadableFile)
        : await dir.getFileHandle(entry.name);
    const file = await fileHandle.getFile();
    const row: TarkovScreenshotRead = {
      name: file.name,
      lastModified: file.lastModified,
      size: file.size,
      file,
    };
    if (!latest || isNewerScreenshot(latest, row)) latest = row;
  }
  return { names, latest };
}
