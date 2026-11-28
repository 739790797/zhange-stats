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
} from "@/features/guides/tarkov/model/tarkovGameLogs";
import { TARKOV_LIVE_DIRS_EVENT } from "@/features/guides/tarkov/model/tarkovLiveWatch";
import {
  readTarkovLogText,
  type TarkovLogTextEntry,
} from "@/features/guides/tarkov/model/tarkovLogTextCache";

const DB_NAME = "zhange-tarkov-game-logs";
const DB_VERSION = 1;
const STORE = "kv";
const BINDING_KEYS = {
  logs: { handle: "logs-dir", path: "logs-dir-path" },
  screenshots: { handle: "screenshots-dir", path: "screenshots-dir-path" },
} as const;
const DIRECTORY_TIMEOUT_MS = 5000;

export type TarkovDirectoryKind = keyof typeof BINDING_KEYS;

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
};

export type TarkovLogFileMeta = {
  name: string;
  size: number;
  lastModified: number;
};

/** 读取文件快照获得名字、大小、修改时间，正文留待按需读取。 */
export type TarkovLogSessionStat = {
  folder: string;
  files: Array<{ handle: ReadableFile; meta: TarkovLogFileMeta; file: File }>;
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

/** 文件系统的非交互操作不能让页面或轮询一直等；不限制用户处理原生授权弹窗的时间。 */
export async function withTarkovDirectoryTimeout<T>(work: () => Promise<T>): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      work(),
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => {
          reject(new Error("读取本机目录超时，请重试或重新选择目录。"));
        }, DIRECTORY_TIMEOUT_MS);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

function bindingTransaction<T>(
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => () => T,
): Promise<T> {
  return new Promise((resolve, reject) => {
    let db: IDBDatabase | undefined;
    let transaction: IDBTransaction | undefined;
    let finished = false;
    const fail = (message: string) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      try {
        transaction?.abort();
      } catch {
        // 浏览器可能已经终止事务。
      }
      db?.close();
      reject(new Error(message));
    };
    const failure = mode === "readonly" ? "无法读取浏览器保存的目录。" : "无法保存目录授权。";
    const timer = setTimeout(
      () => fail(`${failure} 浏览器存储响应超时，请重试。`),
      DIRECTORY_TIMEOUT_MS,
    );
    try {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onblocked = () => fail(`${failure} 请关闭其他战鸽数据标签页后重试。`);
      req.onerror = () => fail(failure);
      req.onupgradeneeded = () => {
        if (finished) {
          req.transaction?.abort();
          return;
        }
        if (!req.result.objectStoreNames.contains(STORE)) req.result.createObjectStore(STORE);
      };
      req.onsuccess = () => {
        const connection = req.result;
        if (finished) {
          connection.close();
          return;
        }
        db = connection;
        connection.onversionchange = () => connection.close();
        try {
          const txn = connection.transaction(STORE, mode);
          transaction = txn;
          txn.onerror = txn.onabort = () => fail(failure);
          const result = run(txn.objectStore(STORE));
          txn.oncomplete = () => {
            if (finished) return;
            try {
              const value = result();
              finished = true;
              clearTimeout(timer);
              connection.close();
              resolve(value);
            } catch {
              fail(failure);
            }
          };
        } catch {
          fail(failure);
        }
      };
    } catch {
      fail(failure);
    }
  });
}

type TarkovDirectoryBinding = { handle: ReadableDir | null; path: string };

export function loadTarkovDirectoryBinding(
  kind: TarkovDirectoryKind,
): Promise<TarkovDirectoryBinding> {
  const keys = BINDING_KEYS[kind];
  return bindingTransaction("readonly", (store) => {
    const handle = store.get(keys.handle);
    const path = store.get(keys.path);
    return () => ({
      handle: (handle.result as ReadableDir | undefined) ?? null,
      path: typeof path.result === "string" ? path.result : "",
    });
  });
}

export async function saveTarkovDirectoryBinding(
  kind: TarkovDirectoryKind,
  handle: ReadableDir,
  path: string,
): Promise<void> {
  const keys = BINDING_KEYS[kind];
  await bindingTransaction("readwrite", (store) => {
    store.put(handle, keys.handle);
    store.put(path, keys.path);
    return () => undefined;
  });
  window.dispatchEvent(
    new CustomEvent<TarkovDirectoryKind>(TARKOV_LIVE_DIRS_EVENT, { detail: kind }),
  );
}

export function saveTarkovDirectoryDisplayPath(
  kind: TarkovDirectoryKind,
  path: string,
): Promise<void> {
  return bindingTransaction("readwrite", (store) => {
    store.put(path, BINDING_KEYS[kind].path);
    return () => undefined;
  });
}

async function queryDirPermission(handle: ReadableDir, mode: FsMode): Promise<FsPermission> {
  if (typeof handle.queryPermission !== "function") return "granted";
  return withTarkovDirectoryTimeout(() => handle.queryPermission({ mode }));
}

async function requestDirPermission(handle: ReadableDir, mode: FsMode): Promise<FsPermission> {
  if (typeof handle.requestPermission !== "function") return "granted";
  return handle.requestPermission({ mode });
}

export async function queryLogsDirPermission(handle: ReadableDir): Promise<FsPermission> {
  return queryDirPermission(handle, "read");
}

export async function requestLogsDirPermission(handle: ReadableDir): Promise<FsPermission> {
  return requestDirPermission(handle, "read");
}

export async function queryScreenshotsDirPermission(handle: ReadableDir): Promise<FsPermission> {
  return queryDirPermission(handle, "read");
}

export async function requestScreenshotsDirPermission(
  handle: ReadableDir,
  mode: FsMode = "read",
): Promise<FsPermission> {
  const permission = await requestDirPermission(handle, mode);
  if (mode === "readwrite" && permission !== "granted")
    return queryScreenshotsDirPermission(handle);
  return permission;
}

export async function screenshotsDirCanWrite(handle: ReadableDir): Promise<boolean> {
  return (await queryDirPermission(handle, "readwrite").catch(() => "denied")) === "granted";
}

function requirePicker() {
  const picker = (window as PickerWindow).showDirectoryPicker;
  if (!picker) {
    throw new Error("当前浏览器不支持授权本地目录，请用 Chrome 或 Edge。");
  }
  return picker.bind(window);
}

export async function pickLogsDirectory(startIn?: ReadableDir | null): Promise<ReadableDir> {
  return requirePicker()({
    id: "zhange-tarkov-logs",
    mode: "read",
    startIn: startIn || undefined,
  });
}

export async function pickScreenshotsDirectory(
  startIn?: ReadableDir | null,
  mode: FsMode = "read",
): Promise<ReadableDir> {
  return requirePicker()({
    id: "zhange-tarkov-screenshots",
    mode,
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
      (child) => child.kind === "directory" && child.name.toLowerCase() === wanted.toLowerCase(),
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

export async function resolveLogsDirDetailed(handle: ReadableDir): Promise<ResolvedTarkovDir> {
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
  if (handle.name.toLowerCase() === "screenshots") {
    return { dir: handle, walk: [], pickedName: handle.name };
  }
  const dirNames = children
    .filter((child) => child.kind === "directory")
    .map((child) => child.name);
  const walks = screenshotWalkCandidatesFrom(dirNames).filter((walk) => walk.length > 0);
  const found = await resolveByWalks(handle, walks, () => true);
  if (found) return found;
  if (children.some((child) => child.kind === "file" && isScreenshotFileName(child.name))) {
    return { dir: handle, walk: [], pickedName: handle.name };
  }
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
): Promise<ReadableFile[]> {
  const sessionDir = await sessionDirFor(handle, folder, cache);
  const entries = await listDirEntries(sessionDir);
  const out: ReadableFile[] = [];
  for (const entry of entries) {
    if (entry.kind !== "file" || !isReadableTarkovLogFileName(entry.name)) {
      continue;
    }
    out.push(
      entry.getFile != null ? (entry as ReadableFile) : await sessionDir.getFileHandle(entry.name),
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

async function statSessionFile(
  handle: ReadableFile,
): Promise<TarkovLogSessionStat["files"][number]> {
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
 * 读这一轮的快照。大小与修改时间都没变就沿用上一轮的文本。
 * 变长时交给 readTarkovLogText 只读新追加的字节。
 */
async function readStattedFile(
  row: TarkovLogSessionStat["files"][number],
  prev: TarkovLogCachedText | undefined,
): Promise<TarkovLogCachedText> {
  const seen = fileFingerprint(row.meta);
  if (prev && prev.seen === seen) return prev;
  let entry: TarkovLogTextEntry;
  try {
    entry = await readTarkovLogText(row.meta.name, row.file, prev?.entry);
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
  for (const fileHandle of rows) {
    if (opts?.fileName && !opts.fileName(fileHandle.name)) continue;
    const file = await fileHandle.getFile();
    files.push({
      name: fileHandle.name,
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

/** 按名字获取截图大小与修改时间，无需读取像素。 */
export async function readScreenshotByName(
  dir: ReadableDir,
  name: string,
): Promise<TarkovScreenshotRead | null> {
  if (!isScreenshotFileName(name)) return null;
  try {
    const file = await (await dir.getFileHandle(name)).getFile();
    return { name: file.name, lastModified: file.lastModified, size: file.size };
  } catch {
    return null;
  }
}

export async function removeScreenshotFiles(
  dir: ReadableDir,
  names: readonly string[],
  canRemove: () => boolean,
): Promise<void> {
  if (typeof dir.removeEntry !== "function") return;
  for (const name of names) {
    if (!canRemove()) return;
    try {
      await dir.removeEntry(name);
    } catch {
      /* 游戏可能还占着文件 */
    }
  }
}

export async function listScreenshotFileNames(dir: ReadableDir): Promise<string[]> {
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
  seen: Set<string>;
  dir: ReadableDir;
}> {
  const dir = cachedDir || (await resolveScreenshotsDirDetailed(handle)).dir;
  const names = await listScreenshotFileNames(dir);
  const inspect = screenshotNamesToInspect(names, seenNames);
  const pending = new Set(inspect);
  const seen = new Set(names.filter((name) => !pending.has(name)));
  let latest: TarkovScreenshotRead | null = null;
  for (const name of inspect) {
    const row = await readScreenshotByName(dir, name);
    if (!row) continue;
    seen.add(name);
    if (!latest || isNewerScreenshot(latest, row)) latest = row;
  }
  return { names, latest, seen, dir };
}
