import {
  classifyLogsRoot,
  formatBindPath,
  isNewerScreenshot,
  isApplicationLogFileName,
  isReadableTarkovLogFileName,
  isScreenshotFileName,
  screenshotNamesToInspect,
  listSessionStubs,
  logWalkCandidatesFrom,
  mergeBindPath,
  screenshotWalkCandidatesFrom,
  type TarkovLogSessionStub,
} from "@/lib/tarkovGameLogs";
import {
  assistantLogsBinding,
  assistantScreenshotsBinding,
  hasAssistantTarkovFiles,
  rebindAssistantLogs,
  rebindAssistantScreenshots,
  type AssistantBoundDir,
} from "@/lib/assistantShell";
import {
  assistantBoundToDir,
  assistantDirWatch,
  isAssistantDir,
} from "@/lib/assistantTarkovDir";
import { notifyTarkovLiveDirsChanged } from "@/lib/tarkovLiveWatch";
import { readTarkovLogText, type TarkovLogTextEntry } from "@/lib/tarkovLogTextCache";

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

/** 列目录时就知道的大小与修改时间（战鸽助手的 list 会给）；浏览器句柄没有，要 getFile 取快照。 */
export type ListedFileMeta = {
  size?: number;
  lastModified?: number;
};

export type ReadableFile = {
  name: string;
  getFile: () => Promise<File>;
  listed?: ListedFileMeta;
};

export type ReadableEntry = {
  kind: "file" | "directory";
  name: string;
  listed?: ListedFileMeta;
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
};

export type TarkovLogFileMeta = {
  name: string;
  size: number;
  lastModified: number;
};

/**
 * 只取了名字、大小、修改时间，还没读正文。浏览器句柄带着 getFile 的快照 `file`；
 * 战鸽助手列目录已给大小与时间，`file` 为空，要读时再经桥取正文。
 */
export type TarkovLogSessionStat = {
  folder: string;
  files: Array<{ handle: ReadableFile; meta: TarkovLogFileMeta; file: File | null }>;
  fingerprint: string;
};

/** 某个文件上次读到的文本，`seen` 是当时取到的大小与修改时间；下一轮一样就不读。 */
export type TarkovLogCachedText = {
  entry: TarkovLogTextEntry;
  seen: string;
};

/** 实时轮询跨轮复用：解析出的日志根、启动记录目录句柄、各文件上次读到的文本。历史扫描只用到目录部分。 */
export type TarkovLogReadCache = {
  picked: ReadableDir | null;
  root: ResolvedTarkovDir | null;
  rootIsSession: boolean;
  sessionDirs: Map<string, ReadableDir>;
  texts: Map<string, Map<string, TarkovLogCachedText>>;
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
  return (
    typeof (window as PickerWindow).showDirectoryPicker === "function" ||
    hasAssistantTarkovFiles()
  );
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

export async function loadStoredLogsDir(): Promise<ReadableDir | null> {
  const bound = assistantLogsBinding();
  if (bound) return assistantBoundToDir(bound);
  try {
    const handle = await idbGet<ReadableDir>(LOGS_HANDLE_KEY);
    return handle || null;
  } catch {
    return null;
  }
}

/**
 * 只有浏览器授权的目录句柄才落 IndexedDB。战鸽助手绑定的目录由助手记着，页面拿到的是带函数的对象，
 * 存进去会抛 DataCloneError；绑定在时只通知页面重读即可（读取一侧本来就先看绑定）。
 */
export function shouldStoreDirHandle(
  handle: ReadableDir,
  binding: AssistantBoundDir | null,
): boolean {
  return !binding && !isAssistantDir(handle);
}

async function saveDirHandle(
  key: string,
  handle: ReadableDir,
  binding: AssistantBoundDir | null,
): Promise<void> {
  if (shouldStoreDirHandle(handle, binding)) await idbSet(key, handle);
  notifyTarkovLiveDirsChanged();
}

export async function saveLogsDir(handle: ReadableDir): Promise<void> {
  await saveDirHandle(LOGS_HANDLE_KEY, handle, assistantLogsBinding());
}

export async function loadStoredLogsPath(): Promise<string> {
  const bound = assistantLogsBinding();
  if (bound?.path) return bound.path;
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

export async function loadStoredScreenshotsDir(): Promise<ReadableDir | null> {
  const bound = assistantScreenshotsBinding();
  if (bound) return assistantBoundToDir(bound);
  try {
    const handle = await idbGet<ReadableDir>(SHOTS_HANDLE_KEY);
    return handle || null;
  } catch {
    return null;
  }
}

export async function saveScreenshotsDir(handle: ReadableDir): Promise<void> {
  await saveDirHandle(SHOTS_HANDLE_KEY, handle, assistantScreenshotsBinding());
}

export async function loadStoredScreenshotsPath(): Promise<string> {
  const bound = assistantScreenshotsBinding();
  if (bound?.path) return bound.path;
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
  if (assistantLogsBinding()) {
    if (!(await rebindAssistantLogs())) {
      throw new Error("请在战鸽助手里更换日志目录。");
    }
    const bound = assistantLogsBinding();
    if (!bound) throw new Error("请在战鸽助手里更换日志目录。");
    return assistantBoundToDir(bound);
  }
  return requirePicker()({
    id: "zhange-tarkov-logs",
    mode: "read",
    startIn: startIn || undefined,
  });
}

export async function pickScreenshotsDirectory(
  startIn?: ReadableDir | null,
): Promise<ReadableDir> {
  if (assistantScreenshotsBinding()) {
    if (!(await rebindAssistantScreenshots())) {
      throw new Error("请在战鸽助手里更换截图目录。");
    }
    const bound = assistantScreenshotsBinding();
    if (!bound) throw new Error("请在战鸽助手里更换截图目录。");
    return assistantBoundToDir(bound);
  }
  return requirePicker()({
    id: "zhange-tarkov-screenshots",
    mode: "readwrite",
    startIn: startIn || "documents",
  });
}

export async function observeDirectory(
  handle: ReadableDir,
  onChange: (appeared: string[]) => void,
): Promise<(() => void) | null> {
  const watch = assistantDirWatch(handle);
  if (watch) return watch(() => onChange([]));
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

export function createTarkovLogReadCache(): TarkovLogReadCache {
  return {
    picked: null,
    root: null,
    rootIsSession: false,
    sessionDirs: new Map(),
    texts: new Map(),
  };
}

/** 目录句柄失效（被删、改名、授权变了）时只丢目录；文本缓存按大小与修改时间自校验。 */
export function forgetTarkovLogDirs(cache: TarkovLogReadCache): void {
  cache.root = null;
  cache.sessionDirs.clear();
}

/** 只留这几个启动记录的句柄与文本，其余放掉。 */
export function retainTarkovLogFolders(
  cache: TarkovLogReadCache,
  folders: readonly string[],
): void {
  for (const folder of [...cache.sessionDirs.keys()]) {
    if (!folders.includes(folder)) cache.sessionDirs.delete(folder);
  }
  for (const folder of [...cache.texts.keys()]) {
    if (!folders.includes(folder)) cache.texts.delete(folder);
  }
}

async function listChildNames(dir: ReadableDir): Promise<string[]> {
  return (await listDirEntries(dir)).map((child) => child.name);
}

function isLogsRootKind(names: readonly string[]): boolean {
  const kind = classifyLogsRoot(names);
  return kind === "logs" || kind === "session";
}

/** 带缓存时沿用上轮解析出的日志根，它列不出启动记录了再从授权目录重新往下找。 */
async function logsRootWithNames(
  handle: ReadableDir,
  cache?: TarkovLogReadCache,
): Promise<{ resolved: ResolvedTarkovDir; names: string[] }> {
  if (cache && cache.picked !== handle) {
    cache.picked = handle;
    cache.texts.clear();
    forgetTarkovLogDirs(cache);
  }
  if (cache?.root) {
    const names = await listChildNames(cache.root.dir).catch(() => null);
    if (names && isLogsRootKind(names)) return { resolved: cache.root, names };
    forgetTarkovLogDirs(cache);
  }
  const resolved = await resolveLogsDirDetailed(handle);
  const names = await listChildNames(resolved.dir);
  if (cache) cache.root = resolved;
  return { resolved, names };
}

export async function readLogsIndex(
  handle: ReadableDir,
  cache?: TarkovLogReadCache,
): Promise<{
  resolved: ResolvedTarkovDir;
  sessions: TarkovLogSessionStub[];
}> {
  const { resolved, names } = await logsRootWithNames(handle, cache);
  const kind = classifyLogsRoot(names);
  if (cache) cache.rootIsSession = kind === "session";
  const sessions =
    kind === "session"
      ? listSessionStubs(names, { selfFolder: resolved.dir.name })
      : listSessionStubs(names);
  return { resolved, sessions };
}

/**
 * 启动记录目录。带缓存时日志根只解析一次（缓存还空着就先解析并记下），各文件夹句柄也记住；
 * 历史扫描一次走几十个文件夹，不带缓存就是每个文件夹都从授权目录往下找、整层列一遍根。
 */
async function sessionDirFor(
  handle: ReadableDir,
  folder: string,
  cache?: TarkovLogReadCache,
): Promise<ReadableDir> {
  if (cache) {
    let root = cache.picked === handle ? cache.root : null;
    if (!root) {
      const { resolved, names } = await logsRootWithNames(handle, cache);
      cache.rootIsSession = classifyLogsRoot(names) === "session";
      root = resolved;
    }
    if (cache.rootIsSession) return root.dir;
    const hit = cache.sessionDirs.get(folder);
    if (hit) return hit;
    const dir = await root.dir.getDirectoryHandle(folder);
    cache.sessionDirs.set(folder, dir);
    return dir;
  }
  const root = await resolveLogsDir(handle);
  const rootKind = classifyLogsRoot(await listChildNames(root));
  return rootKind === "session" ? root : root.getDirectoryHandle(folder);
}

async function sessionFiles(
  handle: ReadableDir,
  folder: string,
  cache?: TarkovLogReadCache,
): Promise<Array<{ handle: ReadableFile; listed?: ListedFileMeta }>> {
  const sessionDir = await sessionDirFor(handle, folder, cache);
  const entries = await listDirEntries(sessionDir);
  const out: Array<{ handle: ReadableFile; listed?: ListedFileMeta }> = [];
  for (const entry of entries) {
    if (entry.kind !== "file" || !isReadableTarkovLogFileName(entry.name)) {
      continue;
    }
    out.push(
      entry.getFile != null
        ? { handle: entry as ReadableFile, listed: entry.listed }
        : { handle: await sessionDir.getFileHandle(entry.name) },
    );
  }
  return out;
}

function fileFingerprint(file: TarkovLogFileMeta): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function joinFingerprint(parts: string[]): string {
  return [...parts].sort().join("|");
}

/**
 * 一轮的快照：浏览器授权目录要 getFile 取 size/lastModified；战鸽助手的 list 已经给了这两项，
 * 就不再经桥读整份正文（2 秒一次轮询时读的正是整份日志）。
 */
async function statSessionFile(
  row: { handle: ReadableFile; listed?: ListedFileMeta },
): Promise<TarkovLogSessionStat["files"][number]> {
  const { handle, listed } = row;
  if (listed?.size != null && listed.lastModified != null) {
    return {
      handle,
      meta: { name: handle.name, size: listed.size, lastModified: listed.lastModified },
      file: null,
    };
  }
  const file = await handle.getFile();
  return {
    handle,
    meta: { name: handle.name, size: file.size, lastModified: file.lastModified },
    file,
  };
}

export async function statSessionLogs(
  handle: ReadableDir,
  folder: string,
  cache?: TarkovLogReadCache,
): Promise<TarkovLogSessionStat> {
  const rows = await sessionFiles(handle, folder, cache);
  const files: TarkovLogSessionStat["files"] = [];
  for (const row of rows) files.push(await statSessionFile(row));
  const fingerprint = joinFingerprint(files.map((row) => fileFingerprint(row.meta)));
  return { folder, files, fingerprint };
}

export async function peekSessionFingerprint(
  handle: ReadableDir,
  folder: string,
  cache?: TarkovLogReadCache,
): Promise<string> {
  return (await statSessionLogs(handle, folder, cache)).fingerprint;
}

/**
 * 读这一轮的快照。上一轮读过、大小与修改时间都没变就沿用上次的文本（战鸽助手只给了这两项时，
 * 比上一轮变没变同样看它）；变长时交给 readTarkovLogText 只读新追加的字节。
 */
async function readStattedFile(
  row: TarkovLogSessionStat["files"][number],
  prev: TarkovLogCachedText | undefined,
): Promise<TarkovLogCachedText> {
  const seen = fileFingerprint(row.meta);
  if (prev && prev.seen === seen) return prev;
  const file = row.file ?? (await row.handle.getFile());
  let entry: TarkovLogTextEntry;
  try {
    entry = await readTarkovLogText(row.meta.name, file, prev?.entry);
  } catch {
    // 取快照之后游戏又写了文件，浏览器会拒读旧快照；重取一次。
    entry = await readTarkovLogText(row.meta.name, await row.handle.getFile(), prev?.entry);
  }
  return { entry, seen };
}

/** 与 readSessionLogs 结果相同；带缓存时没变的文件不读，变长的只读新字节。 */
export async function readStattedSessionLogs(
  stat: TarkovLogSessionStat,
  cache?: TarkovLogReadCache,
): Promise<TarkovLogSessionRead> {
  const prevTexts = cache?.texts.get(stat.folder);
  const nextTexts = new Map<string, TarkovLogCachedText>();
  const files: TarkovLogFileRead[] = [];
  for (const row of stat.files) {
    const cached = await readStattedFile(row, prevTexts?.get(row.meta.name));
    nextTexts.set(row.meta.name, cached);
    files.push(cached.entry.read);
  }
  cache?.texts.set(stat.folder, nextTexts);
  files.sort((a, b) => a.lastModified - b.lastModified || a.name.localeCompare(b.name));
  const fingerprint = joinFingerprint(files.map((file) => fileFingerprint(file)));
  return { folder: stat.folder, files, fingerprint };
}

/**
 * 整份读一次启动记录。带上同一份 cache 时，历史扫描（一次几十个文件夹）只解析一次日志根、
 * 每个文件夹的句柄也只取一次；不给 cache 就每次自己往下找。
 */
export async function readSessionLogs(
  handle: ReadableDir,
  folder: string,
  opts?: { fileName?: (name: string) => boolean; cache?: TarkovLogReadCache },
): Promise<TarkovLogSessionRead> {
  const rows = await sessionFiles(handle, folder, opts?.cache);
  const files: TarkovLogFileRead[] = [];
  for (const row of rows) {
    if (opts?.fileName && !opts.fileName(row.handle.name)) continue;
    const file = await row.handle.getFile();
    files.push({
      name: row.handle.name,
      text: await file.text(),
      lastModified: file.lastModified,
      size: file.size,
    });
  }
  files.sort((a, b) => a.lastModified - b.lastModified || a.name.localeCompare(b.name));
  const fingerprint = joinFingerprint(files.map((file) => fileFingerprint(file)));
  return { folder, files, fingerprint };
}

export async function readSessionApplicationLogs(
  handle: ReadableDir,
  folder: string,
  cache?: TarkovLogReadCache,
): Promise<TarkovLogSessionRead> {
  return readSessionLogs(handle, folder, {
    fileName: isApplicationLogFileName,
    cache,
  });
}

export type TarkovScreenshotRead = TarkovScreenshotStub;

/**
 * 截图只按名字取元数据：调用方要的是「这一张是新的吗」与「多大」，不看像素，所以不读图片字节。
 * 战鸽助手列过一次目录就把大小与修改时间带进来（`listed`）；浏览器句柄没有这些，退回 getFileHandle
 * （这是直接取一个句柄，不用整层列目录）。
 */
export async function readScreenshotByName(
  dir: ReadableDir,
  name: string,
  listed?: ListedFileMeta | null,
): Promise<TarkovScreenshotRead | null> {
  if (!isScreenshotFileName(name)) return null;
  const known = listed ?? (isAssistantDir(dir) ? await listedFileMeta(dir, name) : null);
  if (known?.size != null && known.lastModified != null) {
    return { name, size: known.size, lastModified: known.lastModified };
  }
  try {
    const file = await (await dir.getFileHandle(name)).getFile();
    return { name: file.name, lastModified: file.lastModified, size: file.size };
  } catch {
    return null;
  }
}

async function listedFileMeta(
  dir: ReadableDir,
  name: string,
): Promise<ListedFileMeta | null> {
  try {
    const entries = await listDirEntries(dir);
    const hit = entries.find((entry) => entry.kind === "file" && entry.name === name);
    return hit?.listed ?? null;
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

export async function listScreenshotFiles(
  dir: ReadableDir,
): Promise<Array<{ name: string; listed?: ListedFileMeta }>> {
  const entries = await listDirEntries(dir);
  return entries
    .filter((entry) => entry.kind === "file" && isScreenshotFileName(entry.name))
    .map((entry) => ({ name: entry.name, listed: entry.listed }));
}

export async function listScreenshotFileNames(
  dir: ReadableDir,
): Promise<string[]> {
  return (await listScreenshotFiles(dir)).map((row) => row.name);
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
  // 一整层只列一次；助手列目录已带回大小与修改时间，逐张看时不再重列、也不读图片字节。
  const rows = await listScreenshotFiles(dir);
  const names = rows.map((row) => row.name);
  const listing = new Map(rows.map((row) => [row.name, row.listed]));
  const inspect = screenshotNamesToInspect(
    rows.map((row) => ({
      name: row.name,
      lastModified: row.listed?.lastModified,
    })),
    seenNames,
  );
  let latest: TarkovScreenshotRead | null = null;
  for (const name of inspect) {
    const row = await readScreenshotByName(dir, name, listing.get(name));
    if (!row) continue;
    if (!latest || isNewerScreenshot(latest, row)) latest = row;
  }
  return { names, latest, dir };
}
