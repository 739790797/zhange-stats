import { MAPS_HREF, TARKOV_MAPS, tarkovMapHref } from "@/lib/tarkovHomeNav";

/** 日志 Location / nameId / 场景包名 → 本站地图 id。 */
const LOCATION_TO_MAP: Record<string, string> = {
  factory: "factory",
  factory4_day: "factory",
  "factory4_day_preset": "factory",
  factory4_night: "night-factory",
  "factory (night)": "night-factory",
  bigmap: "customs",
  customs: "customs",
  woods: "woods",
  shoreline: "shoreline",
  interchange: "interchange",
  rezervbase: "reserve",
  reserve: "reserve",
  laboratory: "lab",
  lab: "lab",
  "the lab": "lab",
  lighthouse: "lighthouse",
  tarkovstreets: "streets",
  streets: "streets",
  "streets of tarkov": "streets",
  sandbox: "ground-zero",
  sandbox_high: "ground-zero",
  "ground zero": "ground-zero",
  labyrinth: "labyrinth",
  "the labyrinth": "labyrinth",
  terminal: "terminal",
  icebreaker: "icebreaker",
};

const SCENE_TO_MAP: Record<string, string> = {
  factory4_day: "factory",
  factory4_night: "night-factory",
  bigmap: "customs",
  woods: "woods",
  shoreline: "shoreline",
  interchange: "interchange",
  rezervbase: "reserve",
  laboratory: "lab",
  lighthouse: "lighthouse",
  tarkovstreets: "streets",
  sandbox: "ground-zero",
  sandbox_high: "ground-zero",
  labyrinth: "labyrinth",
  terminal: "terminal",
  icebreaker: "icebreaker",
};

const TS_RE =
  /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})(?:\s*[+-]\d{2}:\d{2})?\|/;
const FOLDER_TS_RE =
  /(?:^|log_)(\d{4})\.(\d{2})\.(\d{2})_(\d{1,2})-(\d{2})-(\d{2})/i;
const LOCATION_RE = /Location:\s*([^,]+)/i;
const SHORT_ID_RE = /shortId:\s*([A-Z0-9]{6})/;
const RAID_MODE_RE = /RaidMode:\s*(\w+)/i;
const SCENE_RE = /scene preset path:\s*(maps\/[a-zA-Z0-9_]+\.bundle)/i;
const SESSION_MODE_RE = /Session mode:\s*([^\s|]+)/i;

export const TARKOV_GAME_LOG_MAX_FILE_BYTES = 32 * 1024 * 1024;

/** 任务事件在 notifications.log； flea 多的号很容易超过 32MB。 */
export const TARKOV_GAME_LOG_NOTIFICATIONS_MAX_BYTES = 96 * 1024 * 1024;

/** 超大通知日志只读尾部，避免整文件拖死标签页。 */
export const TARKOV_GAME_LOG_NOTIFICATIONS_TAIL_BYTES = 48 * 1024 * 1024;

export function logFileByteBudget(name: string): number {
  return isNotificationsLogFileName(name)
    ? TARKOV_GAME_LOG_NOTIFICATIONS_MAX_BYTES
    : TARKOV_GAME_LOG_MAX_FILE_BYTES;
}

/** 普通日志超限跳过；通知日志超限改读尾部，避免任务事件整份丢掉。 */
export function planLogFileRead(
  name: string,
  size: number,
): { skip: boolean; offset: number } {
  const n = Number(size) || 0;
  if (n <= 0) return { skip: true, offset: 0 };
  const budget = logFileByteBudget(name);
  if (n <= budget) return { skip: false, offset: 0 };
  if (isNotificationsLogFileName(name)) {
    return {
      skip: false,
      offset: Math.max(0, n - TARKOV_GAME_LOG_NOTIFICATIONS_TAIL_BYTES),
    };
  }
  return { skip: true, offset: 0 };
}

export const TARKOV_GAME_LOG_SCAN_LIMITS = [40, 120, 0] as const;

export type TarkovGameLogScanLimit = (typeof TARKOV_GAME_LOG_SCAN_LIMITS)[number];

export type TarkovLogEventKind =
  | "session_mode"
  | "map_loading"
  | "matching"
  | "match_found"
  | "raid_starting"
  | "raid_started"
  | "matching_aborted"
  | "raid_exited";

export type TarkovLogRaidMode = "online" | "offline" | "unknown";

export type TarkovLogEvent = {
  kind: TarkovLogEventKind;
  at: string;
  mapId?: string;
  mapLabel?: string;
  location?: string;
  raidId?: string;
  raidMode?: TarkovLogRaidMode;
  sessionMode?: string;
};

export type TarkovLogRaid = {
  raidId: string;
  location: string;
  mapId: string;
  mapLabel: string;
  raidMode: TarkovLogRaidMode;
  startedAt?: string;
  endedAt?: string;
  reconnected?: boolean;
  aborted?: boolean;
};

export type TarkovLogQuestKind = "started" | "failed" | "completed";

export type TarkovLogQuestEvent = {
  kind: TarkovLogQuestKind;
  at: string;
  taskId: string;
};

export type TarkovLogParseResult = {
  events: TarkovLogEvent[];
  raids: TarkovLogRaid[];
  sessionMode?: string;
  quests?: TarkovLogQuestEvent[];
};

export type TarkovLogSessionStub = {
  folder: string;
  startedAt: string | null;
};

export type TarkovLogRootKind = "logs" | "install" | "session" | "unknown";

export type TarkovScreenshotRootKind = "screenshots" | "ancestor" | "unknown";

export type TarkovLogHistoryRaid = TarkovLogRaid & {
  folder: string;
};

export function normalizeLogLocationKey(raw: string): string {
  return (raw || "")
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ");
}

export function mapLogLocationToMapId(raw: string): string {
  const compact = (raw || "").trim().toLowerCase().replace(/\s+/g, "");
  if (LOCATION_TO_MAP[compact]) return LOCATION_TO_MAP[compact];
  const spaced = normalizeLogLocationKey(raw).replace(/ /g, "_");
  if (LOCATION_TO_MAP[spaced]) return LOCATION_TO_MAP[spaced];
  const spacedKey = normalizeLogLocationKey(raw);
  return LOCATION_TO_MAP[spacedKey] || LOCATION_TO_MAP[compact] || "";
}

export function mapLogSceneToMapId(scenePath: string): string {
  const base = (scenePath || "")
    .replace(/^maps\//i, "")
    .replace(/\.bundle$/i, "")
    .trim()
    .toLowerCase();
  return SCENE_TO_MAP[base] || mapLogLocationToMapId(base);
}

export function logMapLabel(mapId: string, location = ""): string {
  if (mapId === "night-factory") return "夜间工厂";
  const row = TARKOV_MAPS.find((item) => item.id === mapId);
  if (row) return row.label;
  return (location || "").trim() || "未知地图";
}

export function logMapHref(mapId: string): string {
  if (mapId === "night-factory") return tarkovMapHref("factory");
  const row = TARKOV_MAPS.find((item) => item.id === mapId);
  if (row && row.status === "ready" && !row.comingSoon) {
    return tarkovMapHref(mapId);
  }
  return MAPS_HREF;
}

export function isApplicationLogFileName(name: string): boolean {
  const n = (name || "").toLowerCase();
  return n.endsWith("application.log") || n.endsWith("application_000.log");
}

export function isNotificationsLogFileName(name: string): boolean {
  const n = (name || "").toLowerCase();
  return (
    n.endsWith("notifications.log") ||
    n.endsWith("notifications_000.log") ||
    n.endsWith("push-notifications.log") ||
    n.endsWith("push-notifications_000.log")
  );
}

export function isReadableTarkovLogFileName(name: string): boolean {
  return isApplicationLogFileName(name) || isNotificationsLogFileName(name);
}

export function isSessionFolderName(name: string): boolean {
  return FOLDER_TS_RE.test(name || "");
}

export function parseSessionFolderTime(name: string): string | null {
  const match = FOLDER_TS_RE.exec(name || "");
  if (!match) return null;
  const [, year, month, day, hour, minute, second] = match;
  const hh = String(hour).padStart(2, "0");
  return `${year}-${month}-${day} ${hh}:${minute}:${second}`;
}

export function matchNamedDir(
  names: readonly string[],
  wanted: string,
): string | null {
  const key = (wanted || "").toLowerCase();
  if (!key) return null;
  return names.find((name) => name.toLowerCase() === key) ?? null;
}

/** Steam / BSG 安装目录常见文件夹名。 */
export function matchTarkovGameDir(names: readonly string[]): string | null {
  return (
    matchNamedDir(names, "Escape from Tarkov") ||
    matchNamedDir(names, "EscapeFromTarkov")
  );
}

export function isScreenshotFileName(name: string): boolean {
  return /\.(png|jpe?g|bmp|webp)$/i.test(name || "");
}

const TARKOV_SCREENSHOT_STAMP_RE = /^\d{4}-\d{2}-\d{2}/;

/** 日志路径页打开时，检查截图目录的间隔。 */
export const TARKOV_SCREENSHOT_POLL_MS = 2000;

/** 一次轮询最多删多少张已读游戏截图，避免卡死主线程。 */
export const TARKOV_SCREENSHOT_PRUNE_BATCH = 40;

export const TARKOV_SCREENSHOT_PRUNE_EVENT = "zhange-tarkov-screenshot-prune";
export const TARKOV_SCREENSHOT_PRUNE_STORAGE_KEY =
  "zhange.guides.tarkov.screenshotPrune.v1";
export const TARKOV_SCREENSHOT_PRUNE_KEEP_DEFAULT = 20;
export const TARKOV_SCREENSHOT_PRUNE_KEEP_MIN = 1;
export const TARKOV_SCREENSHOT_PRUNE_KEEP_MAX = 200;

export type TarkovScreenshotPrunePref = {
  enabled: boolean;
  keepMax: number;
};

const DEFAULT_SCREENSHOT_PRUNE_PREF: TarkovScreenshotPrunePref = {
  enabled: false,
  keepMax: TARKOV_SCREENSHOT_PRUNE_KEEP_DEFAULT,
};

export function clampScreenshotPruneKeep(value: unknown): number {
  const n = Math.floor(Number(value));
  if (!Number.isFinite(n)) return TARKOV_SCREENSHOT_PRUNE_KEEP_DEFAULT;
  return Math.min(
    TARKOV_SCREENSHOT_PRUNE_KEEP_MAX,
    Math.max(TARKOV_SCREENSHOT_PRUNE_KEEP_MIN, n),
  );
}

export function parseScreenshotPrunePref(
  raw: string | null | undefined,
): TarkovScreenshotPrunePref {
  if (!raw) return { ...DEFAULT_SCREENSHOT_PRUNE_PREF };
  try {
    const row = JSON.parse(raw) as { enabled?: unknown; keepMax?: unknown };
    return {
      enabled: row.enabled === true,
      keepMax: clampScreenshotPruneKeep(row.keepMax),
    };
  } catch {
    return { ...DEFAULT_SCREENSHOT_PRUNE_PREF };
  }
}

export function loadScreenshotPrunePref(): TarkovScreenshotPrunePref {
  if (typeof window === "undefined") return { ...DEFAULT_SCREENSHOT_PRUNE_PREF };
  return parseScreenshotPrunePref(
    window.localStorage.getItem(TARKOV_SCREENSHOT_PRUNE_STORAGE_KEY),
  );
}

export function saveScreenshotPrunePref(
  pref: TarkovScreenshotPrunePref,
): TarkovScreenshotPrunePref {
  const next = {
    enabled: pref.enabled === true,
    keepMax: clampScreenshotPruneKeep(pref.keepMax),
  };
  if (typeof window !== "undefined") {
    window.localStorage.setItem(
      TARKOV_SCREENSHOT_PRUNE_STORAGE_KEY,
      JSON.stringify(next),
    );
    window.dispatchEvent(new Event(TARKOV_SCREENSHOT_PRUNE_EVENT));
  }
  return next;
}

export function screenshotPruneVerifyResult(opts: {
  pruneEnabled: boolean;
  canWrite: boolean;
}): { ok: boolean; text: string } {
  if (!opts.pruneEnabled) {
    return { ok: true, text: "截图目录校验通过" };
  }
  if (!opts.canWrite) {
    return {
      ok: false,
      text: "自动删截图需要写入授权。请点「更换」重新选择 Screenshots 文件夹，并在弹窗里允许查看并编辑。",
    };
  }
  return { ok: true, text: "截图目录校验通过，已具备删除授权" };
}

export type TarkovScreenshotStamp = {
  name: string;
  lastModified: number;
};

export function isTarkovGameScreenshotName(name: string): boolean {
  return (
    isScreenshotFileName(name) && TARKOV_SCREENSHOT_STAMP_RE.test(name || "")
  );
}

/** 游戏截图文件名带日期前缀，字典序最新的就是最新一张。 */
export function latestScreenshotName(names: readonly string[]): string | null {
  const images = names.filter((name) => isScreenshotFileName(name));
  const dated = images.filter((name) => TARKOV_SCREENSHOT_STAMP_RE.test(name));
  const pool = dated.length ? dated : images;
  if (!pool.length) return null;
  return [...pool].sort((a, b) => b.localeCompare(a))[0] || null;
}

export function isNewerScreenshot(
  current: TarkovScreenshotStamp | null | undefined,
  next: TarkovScreenshotStamp,
): boolean {
  if (!current) return true;
  if (next.lastModified !== current.lastModified) {
    return next.lastModified > current.lastModified;
  }
  return next.name.localeCompare(current.name) > 0;
}

/** 只碰最新一张；已读过就跳过。 */
export function screenshotNamesToInspect(
  names: readonly string[],
  seen: ReadonlySet<string>,
): string[] {
  const latest = latestScreenshotName(names);
  if (!latest || seen.has(latest)) return [];
  return [latest];
}

/** 游戏截图多于 keepMax 时，从最旧的开始删；最新一张始终留着。必须传入整目录文件名，不能只传新出现的几张。 */
export function screenshotNamesToPrune(
  names: readonly string[],
  keepLatest: string | null,
  keepMax: number,
  batch = TARKOV_SCREENSHOT_PRUNE_BATCH,
): string[] {
  const dated = names.filter((name) => isTarkovGameScreenshotName(name));
  const cap = clampScreenshotPruneKeep(keepMax);
  if (dated.length <= cap) return [];
  const newestFirst = [...dated].sort((a, b) => b.localeCompare(a));
  const keep = new Set(newestFirst.slice(0, cap));
  if (keepLatest) keep.add(keepLatest);
  const out: string[] = [];
  for (const name of newestFirst) {
    if (out.length >= Math.max(0, batch)) break;
    if (keep.has(name)) continue;
    out.push(name);
  }
  return out;
}

export function screenshotPollHint(ms = TARKOV_SCREENSHOT_POLL_MS): string {
  const sec = Math.max(1, Math.round(ms / 1000));
  return `每 ${sec} 秒检查新截图`;
}

function uniqueWalks(walks: string[][]): string[][] {
  const seen = new Set<string>();
  const out: string[][] = [];
  for (const walk of walks) {
    const key = walk.map((part) => part.toLowerCase()).join("/");
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(walk);
  }
  return out;
}

/**
 * 从当前目录往下找 Logs。优先 Steam 的 `build/Logs`。
 * `[]` 表示当前目录已经是 Logs。
 */
export function logWalkCandidatesFrom(
  childNames: readonly string[],
): string[][] {
  if (childNames.some((name) => isSessionFolderName(name))) return [[]];
  const lower = new Set(childNames.map((name) => name.toLowerCase()));
  const game = matchTarkovGameDir(childNames);
  const walks: string[][] = [];
  if (lower.has("build")) walks.push(["build", "Logs"]);
  if (lower.has("logs")) walks.push(["Logs"]);
  if (game) {
    walks.push([game, "build", "Logs"]);
    walks.push([game, "Logs"]);
  }
  if (lower.has("common")) {
    walks.push(["common", "Escape from Tarkov", "build", "Logs"]);
    walks.push(["common", "Escape from Tarkov", "Logs"]);
  }
  if (lower.has("steamapps")) {
    walks.push(["steamapps", "common", "Escape from Tarkov", "build", "Logs"]);
    walks.push(["steamapps", "common", "Escape from Tarkov", "Logs"]);
  }
  return uniqueWalks(walks);
}

/**
 * 从当前目录往下找截图。常见是「文档 / Escape from Tarkov / Screenshots」。
 */
export function screenshotWalkCandidatesFrom(
  childNames: readonly string[],
): string[][] {
  const lower = new Set(childNames.map((name) => name.toLowerCase()));
  const game = matchTarkovGameDir(childNames);
  const walks: string[][] = [];
  if (childNames.some((name) => isScreenshotFileName(name))) walks.push([]);
  if (lower.has("screenshots")) walks.push(["Screenshots"]);
  if (game) walks.push([game, "Screenshots"]);
  return uniqueWalks(walks);
}

export function classifyLogsRoot(childNames: readonly string[]): TarkovLogRootKind {
  const names = childNames.map((name) => name.toLowerCase());
  if (childNames.some((name) => isSessionFolderName(name))) return "logs";
  if (childNames.some((name) => isReadableTarkovLogFileName(name))) {
    return "session";
  }
  if (logWalkCandidatesFrom(childNames).some((walk) => walk.length > 0)) {
    return "install";
  }
  if (names.includes("logs") || names.includes("build")) return "install";
  return "unknown";
}

export function classifyScreenshotsRoot(
  childNames: readonly string[],
): TarkovScreenshotRootKind {
  if (screenshotWalkCandidatesFrom(childNames).some((walk) => walk.length === 0)) {
    return "screenshots";
  }
  if (screenshotWalkCandidatesFrom(childNames).length) return "ancestor";
  return "unknown";
}

export function formatResolvedWalk(pickedName: string, walk: readonly string[]): string {
  const root = (pickedName || "").trim() || "已选目录";
  if (!walk.length) return root;
  return `${root} / ${walk.join(" / ")}`;
}

export const TARKOV_SCREENSHOTS_PATH_HINT =
  "C:\\Users\\...\\Documents\\Escape from Tarkov\\Screenshots";

export const TARKOV_LOGS_PATH_HINT =
  "D:\\Steam\\steamapps\\common\\Escape from Tarkov\\build\\Logs";

/** 目录绑定输入框：用反斜杠拼出接近本机路径的展示名。 */
export function formatBindPath(pickedName: string, walk: readonly string[]): string {
  return joinBindPath([
    ...splitBindPath(pickedName),
    ...walk.flatMap((part) => splitBindPath(part)),
  ]);
}

export function splitBindPath(path: string): string[] {
  return (path || "")
    .replace(/\//g, "\\")
    .split("\\")
    .map((part) => part.trim())
    .filter(Boolean);
}

export function hasDriveLetter(path: string): boolean {
  return /^[a-zA-Z]:/.test((path || "").trim());
}

export function joinBindPath(parts: readonly string[]): string {
  const cleaned = parts.flatMap((part) => splitBindPath(part));
  if (!cleaned.length) return "";
  const [head, ...rest] = cleaned;
  if (/^[a-zA-Z]:$/.test(head)) {
    return rest.length ? `${head}\\${rest.join("\\")}` : `${head}\\`;
  }
  return cleaned.join("\\");
}

function bindPartsEqual(a: string, b: string): boolean {
  return a.toLowerCase() === b.toLowerCase();
}

function bindPartsEndWith(all: readonly string[], suffix: readonly string[]): boolean {
  if (!suffix.length || suffix.length > all.length) return false;
  const tail = all.slice(all.length - suffix.length);
  return tail.every((part, index) => bindPartsEqual(part, suffix[index]));
}

function bindLeadingOverlap(prev: readonly string[], next: readonly string[]): number {
  let best = 0;
  const max = Math.min(prev.length, next.length);
  for (let count = 1; count <= max; count += 1) {
    const left = prev.slice(prev.length - count);
    const right = next.slice(0, count);
    if (left.every((part, index) => bindPartsEqual(part, right[index]))) {
      best = count;
    }
  }
  return best;
}

/**
 * 网页选目录拿不到盘符。若上次已补全 `D:\...`，校验/往下走时尽量保住盘符。
 */
export function mergeBindPath(previous: string, next: string): string {
  const nextParts = splitBindPath(next);
  const prevParts = splitBindPath(previous);
  if (!nextParts.length) return joinBindPath(prevParts);
  if (hasDriveLetter(nextParts[0] || "")) return joinBindPath(nextParts);
  if (!prevParts.length) return joinBindPath(nextParts);
  if (bindPartsEndWith(prevParts, nextParts)) return joinBindPath(prevParts);
  const overlap = bindLeadingOverlap(prevParts, nextParts);
  if (overlap > 0) {
    return joinBindPath([
      ...prevParts.slice(0, prevParts.length - overlap),
      ...nextParts,
    ]);
  }
  const index = prevParts.findIndex((part) => bindPartsEqual(part, nextParts[0]));
  if (index >= 0) {
    return joinBindPath([...prevParts.slice(0, index), ...nextParts]);
  }
  return joinBindPath(nextParts);
}

export function listSessionStubs(
  childNames: readonly string[],
  opts?: { selfFolder?: string },
): TarkovLogSessionStub[] {
  const kind = classifyLogsRoot(childNames);
  if (kind === "session" && opts?.selfFolder) {
    return [
      {
        folder: opts.selfFolder,
        startedAt: parseSessionFolderTime(opts.selfFolder),
      },
    ];
  }
  const stubs = childNames
    .filter((name) => isSessionFolderName(name))
    .map((folder) => ({
      folder,
      startedAt: parseSessionFolderTime(folder),
    }));
  stubs.sort((a, b) => {
    const ta = a.startedAt || a.folder;
    const tb = b.startedAt || b.folder;
    return tb.localeCompare(ta);
  });
  return stubs;
}

export function takeSessionStubs(
  stubs: readonly TarkovLogSessionStub[],
  limit: number,
): TarkovLogSessionStub[] {
  if (!limit) return [...stubs];
  return stubs.slice(0, limit);
}

export function parseLogRaidMode(raw: string): TarkovLogRaidMode {
  const key = (raw || "").trim().toLowerCase();
  if (key === "online") return "online";
  if (key === "offline" || key === "local") return "offline";
  return "unknown";
}

export function raidModeLabel(mode: TarkovLogRaidMode): string {
  if (mode === "online") return "在线";
  if (mode === "offline") return "离线";
  return "未知";
}

export function sessionModeLabel(mode: string): string {
  const key = (mode || "").trim().toLowerCase();
  if (key === "pve") return "PvE";
  if (key === "regular" || key === "pvp") return "正式";
  return mode.trim();
}

export function logEventLabel(kind: string): string {
  switch (kind) {
    case "map_loading":
      return "载入地图";
    case "matching":
      return "匹配中";
    case "match_found":
      return "匹配成功";
    case "raid_starting":
      return "倒计时";
    case "raid_started":
      return "开战";
    case "matching_aborted":
      return "取消匹配";
    case "raid_exited":
      return "战局结束";
    default:
      return "会话";
  }
}

export function isRaidFacingEvent(event: TarkovLogEvent): boolean {
  return event.kind !== "session_mode";
}

function attachMap(
  event: TarkovLogEvent,
  location: string,
  mapId = mapLogLocationToMapId(location),
): TarkovLogEvent {
  if (!location && !mapId) return event;
  return {
    ...event,
    location: location || event.location,
    mapId: mapId || event.mapId,
    mapLabel: logMapLabel(mapId || event.mapId || "", location),
  };
}

function emptyRaid(): TarkovLogRaid {
  return {
    raidId: "",
    location: "",
    mapId: "",
    mapLabel: "未知地图",
    raidMode: "unknown",
  };
}

function applyRaidFields(raid: TarkovLogRaid, event: TarkovLogEvent) {
  if (event.raidId && !raid.raidId) raid.raidId = event.raidId;
  if (event.location) raid.location = event.location;
  if (event.mapId) raid.mapId = event.mapId;
  if (event.mapLabel) raid.mapLabel = event.mapLabel;
  else if (raid.mapId || raid.location) {
    raid.mapLabel = logMapLabel(raid.mapId, raid.location);
  }
  if (event.raidMode && event.raidMode !== "unknown") {
    raid.raidMode = event.raidMode;
  }
}

export function buildRaidsFromEvents(
  events: readonly TarkovLogEvent[],
): TarkovLogRaid[] {
  const raids: TarkovLogRaid[] = [];
  let current: TarkovLogRaid | null = null;
  /** UserMatchOver / 取消匹配之后，回菜单的 GameStarted 不算新一局。 */
  let awaitNewMatch = false;

  const flush = () => {
    if (!current) return;
    if (current.raidId || current.startedAt || current.location || current.aborted) {
      if (!current.mapLabel || current.mapLabel === "未知地图") {
        current.mapLabel = logMapLabel(current.mapId, current.location);
      }
      raids.push(current);
    }
    current = null;
  };

  for (const event of events) {
    if (event.kind === "session_mode") continue;
    if (event.kind === "match_found") {
      awaitNewMatch = false;
      if (
        current?.raidId &&
        event.raidId &&
        current.raidId === event.raidId
      ) {
        current.reconnected = true;
        applyRaidFields(current, event);
        continue;
      }
      if (current && (current.raidId || current.startedAt)) {
        flush();
        current = emptyRaid();
      } else if (!current) {
        current = emptyRaid();
      }
      applyRaidFields(current, event);
      continue;
    }
    if (event.kind === "matching_aborted") {
      if (current && !current.startedAt) {
        current.aborted = true;
        applyRaidFields(current, event);
        flush();
        awaitNewMatch = true;
      }
      continue;
    }
    if (event.kind === "raid_started") {
      if (awaitNewMatch && !current) continue;
      if (!current) current = emptyRaid();
      current.startedAt = event.at;
      applyRaidFields(current, event);
      continue;
    }
    if (event.kind === "raid_starting" || event.kind === "map_loading" || event.kind === "matching") {
      if (awaitNewMatch && !current) {
        // 战后 hideout 的 LocationLoaded / GameStarted 仍跳过；
        // 选了新图的 scene preset 要开下一局，否则离线/无 match_found 永远不切图。
        if (event.kind === "map_loading" && event.mapId) {
          awaitNewMatch = false;
          current = emptyRaid();
          applyRaidFields(current, event);
        }
        continue;
      }
      if (!current) current = emptyRaid();
      applyRaidFields(current, event);
      continue;
    }
    if (event.kind === "raid_exited") {
      if (
        current?.raidId &&
        event.raidId &&
        current.raidId !== event.raidId
      ) {
        flush();
      }
      if (!current) current = emptyRaid();
      current.endedAt = event.at;
      applyRaidFields(current, event);
      flush();
      awaitNewMatch = true;
    }
  }
  flush();
  return raids;
}

function extractJsonObject(
  text: string,
  from: number,
  maxLen = 8000,
): string | null {
  const start = text.indexOf("{", from);
  if (start < 0 || start - from > 240) return null;
  let depth = 0;
  let inStr = false;
  let escape = false;
  for (let i = start; i < text.length && i < start + maxLen; i += 1) {
    const ch = text[i];
    if (inStr) {
      if (escape) {
        escape = false;
        continue;
      }
      if (ch === "\\") {
        escape = true;
        continue;
      }
      if (ch === "\"") inStr = false;
      continue;
    }
    if (ch === "\"") {
      inStr = true;
      continue;
    }
    if (ch === "{") depth += 1;
    else if (ch === "}") {
      depth -= 1;
      if (depth === 0) return text.slice(start, i + 1);
    }
  }
  return null;
}

const QUEST_MESSAGE_TYPE: Record<number, TarkovLogQuestKind> = {
  10: "started",
  11: "failed",
  12: "completed",
};

const QUEST_STATUS_WORD: Record<string, TarkovLogQuestKind> = {
  started: "started",
  start: "started",
  failed: "failed",
  fail: "failed",
  completed: "completed",
  complete: "completed",
  finished: "completed",
  success: "completed",
};

export function taskIdFromQuestTemplate(templateId: string): string {
  const token = (templateId || "").trim().split(/\s+/)[0] || "";
  return /^[a-fA-F0-9]{20,32}$/.test(token) ? token.toLowerCase() : "";
}

function asRecord(raw: unknown): Record<string, unknown> | null {
  return raw && typeof raw === "object" && !Array.isArray(raw)
    ? (raw as Record<string, unknown>)
    : null;
}

function pickUnknown(
  rec: Record<string, unknown> | null,
  keys: readonly string[],
): unknown {
  if (!rec) return undefined;
  for (const key of keys) {
    if (rec[key] !== undefined) return rec[key];
  }
  return undefined;
}

function questKindFromMessageType(raw: unknown): TarkovLogQuestKind | "" {
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return QUEST_MESSAGE_TYPE[raw] || "";
  }
  const text = String(raw ?? "").trim();
  if (!text) return "";
  const asNum = Number.parseInt(text, 10);
  if (Number.isFinite(asNum) && QUEST_MESSAGE_TYPE[asNum]) {
    return QUEST_MESSAGE_TYPE[asNum];
  }
  return QUEST_STATUS_WORD[text.toLowerCase()] || "";
}

function questEventFromMessage(raw: unknown, at: string): TarkovLogQuestEvent | null {
  const root = asRecord(raw);
  const message = asRecord(pickUnknown(root, ["message", "Message"])) || root;
  const kind = questKindFromMessageType(
    pickUnknown(message, ["type", "Type", "status", "Status"]),
  );
  if (!kind) return null;
  const taskId = taskIdFromQuestTemplate(
    String(
      pickUnknown(message, [
        "templateId",
        "TemplateId",
        "questId",
        "QuestId",
        "tid",
      ]) || "",
    ),
  );
  if (!taskId) return null;
  return { kind, at, taskId };
}

function parseChatQuest(
  text: string,
  lineStart: number,
  at: string,
): TarkovLogQuestEvent | null {
  const until = nextLogLineIndex(text, lineStart + 1);
  const block = text.slice(lineStart, until);
  const jsonText = extractJsonObject(block, 0, 512_000);
  if (!jsonText) return null;
  try {
    return questEventFromMessage(JSON.parse(jsonText), at);
  } catch {
    return null;
  }
}

function nextLogLineIndex(text: string, from: number): number {
  const rest = text.slice(from);
  const match = rest.search(/\n\d{4}-\d{2}-\d{2} /);
  return match < 0 ? text.length : from + match;
}

function parseUserMatchOver(
  text: string,
  lineStart: number,
  at: string,
): TarkovLogEvent | null {
  const until = nextLogLineIndex(text, lineStart + 1);
  const block = text.slice(lineStart, until);
  const jsonText = extractJsonObject(block, 0);
  let location = "";
  let raidId = "";
  if (jsonText) {
    try {
      const parsed = JSON.parse(jsonText) as {
        location?: unknown;
        shortId?: unknown;
      };
      if (typeof parsed.location === "string") location = parsed.location;
      if (typeof parsed.shortId === "string") raidId = parsed.shortId;
    } catch {
      /* 通知块偶发截断，退回行内字段 */
    }
  }
  if (!location) {
    location = (LOCATION_RE.exec(block)?.[1] || "").trim();
  }
  if (!raidId) {
    raidId = (SHORT_ID_RE.exec(block)?.[1] || "").trim();
  }
  return attachMap(
    {
      kind: "raid_exited",
      at,
      raidId: raidId || undefined,
    },
    location,
  );
}

export function parseTarkovLogText(text: string): TarkovLogParseResult {
  const source = (text || "").replace(/\r\n/g, "\n");
  const events: TarkovLogEvent[] = [];
  const quests: TarkovLogQuestEvent[] = [];
  let sessionMode = "";
  const lines = source.split("\n");
  let offset = 0;

  for (const line of lines) {
    const lineStart = offset;
    offset += line.length + 1;
    const tsMatch = TS_RE.exec(line);
    const at = tsMatch?.[1] || events[events.length - 1]?.at || quests[quests.length - 1]?.at || "";
    if (SESSION_MODE_RE.test(line)) {
      sessionMode = (SESSION_MODE_RE.exec(line)?.[1] || "").trim();
      events.push({ kind: "session_mode", at, sessionMode });
      continue;
    }
    if (line.includes("Got notification | ChatMessageReceived")) {
      const quest = parseChatQuest(source, lineStart, at);
      if (quest) quests.push(quest);
      continue;
    }
    if (line.includes("Got notification | UserMatchOver")) {
      const exited = parseUserMatchOver(source, lineStart, at);
      if (exited) events.push(exited);
      continue;
    }
    if (line.includes("application|scene preset path:") || line.includes("|scene preset path:")) {
      const scene = SCENE_RE.exec(line)?.[1] || "";
      const mapId = mapLogSceneToMapId(scene);
      events.push(attachMap({ kind: "map_loading", at }, "", mapId));
      continue;
    }
    if (line.includes("application|LocationLoaded") || line.includes("|LocationLoaded")) {
      events.push({ kind: "matching", at });
      continue;
    }
    if (
      line.includes("application|TRACE-NetworkGameCreate profileStatus") ||
      line.includes("TRACE-NetworkGameCreate profileStatus")
    ) {
      const location = (LOCATION_RE.exec(line)?.[1] || "").trim();
      const raidId = (SHORT_ID_RE.exec(line)?.[1] || "").trim();
      const raidMode = parseLogRaidMode(RAID_MODE_RE.exec(line)?.[1] || "");
      events.push(
        attachMap(
          {
            kind: "match_found",
            at,
            raidId: raidId || undefined,
            raidMode,
          },
          location,
        ),
      );
      continue;
    }
    if (line.includes("application|GameStarting") || /\|GameStarting(?:\||$)/.test(line)) {
      events.push({ kind: "raid_starting", at });
      continue;
    }
    if (line.includes("application|GameStarted") || /\|GameStarted(?:\||$)/.test(line)) {
      events.push({ kind: "raid_started", at });
      continue;
    }
    if (line.includes("PrepareSelectedProfileLocally")) {
      events.push({ kind: "raid_exited", at });
      continue;
    }
    if (
      line.includes("Network game matching aborted") ||
      line.includes("Network game matching cancelled")
    ) {
      events.push({ kind: "matching_aborted", at });
    }
  }

  return {
    events,
    raids: buildRaidsFromEvents(events),
    sessionMode: sessionMode || undefined,
    quests,
  };
}

export function parseTarkovLogBundle(
  parts: Array<{ name: string; text: string }>,
): TarkovLogParseResult {
  const events: TarkovLogEvent[] = [];
  const quests: TarkovLogQuestEvent[] = [];
  let sessionMode = "";
  const ordered = [...parts].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true }),
  );
  for (const part of ordered) {
    const parsed = parseTarkovLogText(part.text);
    if (parsed.sessionMode) sessionMode = parsed.sessionMode;
    events.push(...parsed.events);
    quests.push(...(parsed.quests ?? []));
  }
  events.sort((a, b) => {
    const cmp = (a.at || "").localeCompare(b.at || "");
    if (cmp !== 0) return cmp;
    return eventOrder(a.kind) - eventOrder(b.kind);
  });
  quests.sort((a, b) => (a.at || "").localeCompare(b.at || ""));
  return {
    events,
    raids: buildRaidsFromEvents(events),
    sessionMode: sessionMode || undefined,
    quests,
  };
}

function eventOrder(kind: TarkovLogEventKind): number {
  switch (kind) {
    case "session_mode":
      return 0;
    case "map_loading":
      return 1;
    case "matching":
      return 2;
    case "match_found":
      return 3;
    case "raid_starting":
      return 4;
    case "raid_started":
      return 5;
    case "matching_aborted":
      return 6;
    case "raid_exited":
      return 7;
    default:
      return 8;
  }
}

export function historyRaidsFromSessions(
  sessions: Array<{ folder: string; parsed: TarkovLogParseResult }>,
): TarkovLogHistoryRaid[] {
  const rows: TarkovLogHistoryRaid[] = [];
  for (const session of sessions) {
    for (const raid of session.parsed.raids) {
      if (raid.aborted && !raid.startedAt && !raid.raidId) continue;
      rows.push({ ...raid, folder: session.folder });
    }
  }
  rows.sort((a, b) => {
    const ta = a.startedAt || a.endedAt || "";
    const tb = b.startedAt || b.endedAt || "";
    return tb.localeCompare(ta);
  });
  return rows;
}

export type TarkovRaidLogImportRow = {
  folder: string;
  raid_id: string;
  location: string;
  map_id: string;
  map_label: string;
  raid_mode: string;
  session_mode: string;
  started_at: string;
  ended_at: string;
  reconnected: boolean;
  aborted: boolean;
};

export function raidLogEndedKey(row: {
  folder?: string;
  raid_id?: string;
  raidId?: string;
  started_at?: string;
  startedAt?: string;
  map_id?: string;
  mapId?: string;
}): string {
  const folder = (row.folder || "").trim();
  const raidId = (row.raid_id || row.raidId || "").trim();
  if (raidId) return `${folder}|${raidId}`;
  const started = (row.started_at || row.startedAt || "").trim();
  const mapId = (row.map_id || row.mapId || "").trim();
  return `${folder}|${started}|${mapId}`;
}

export function toRaidLogImportRows(
  sessions: Array<{ folder: string; parsed: TarkovLogParseResult }>,
): TarkovRaidLogImportRow[] {
  const modeByFolder = new Map(
    sessions.map((session) => [session.folder, session.parsed.sessionMode || ""]),
  );
  return historyRaidsFromSessions(sessions).map((raid) => ({
    folder: raid.folder,
    raid_id: raid.raidId || "",
    location: raid.location || "",
    map_id: raid.mapId || "",
    map_label: raid.mapLabel || "",
    raid_mode: raid.raidMode,
    session_mode: modeByFolder.get(raid.folder) || "",
    started_at: raid.startedAt || "",
    ended_at: raid.endedAt || "",
    reconnected: Boolean(raid.reconnected),
    aborted: Boolean(raid.aborted),
  }));
}

export function formatLogClock(raw: string): string {
  const text = (raw || "").trim();
  if (!text) return "—";
  return text.replace(/\.\d{3}$/, "");
}

export function latestLogEvent(
  parsed: TarkovLogParseResult | null | undefined,
): TarkovLogEvent | null {
  const events = parsed?.events;
  if (!events?.length) return null;
  return events[events.length - 1];
}

export type TarkovLogPhasePayload = {
  kind: TarkovLogEventKind;
  mapId: string;
  mapLabel: string;
  raidId: string;
  at: string;
};

function lastRaidFacingEvent(
  parsed: TarkovLogParseResult,
): TarkovLogEvent | null {
  const events = parsed.events || [];
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (event && isRaidFacingEvent(event)) return event;
  }
  return null;
}

/** 回菜单空壳：登录/战后重载档案，没有 shortId 和地图。 */
function isPostRaidShell(raid: TarkovLogRaid): boolean {
  return !raid.raidId && !raid.location && !raid.mapId && !raid.aborted;
}

function latestMeaningfulRaid(
  raids: readonly TarkovLogRaid[],
): TarkovLogRaid | null {
  for (let i = raids.length - 1; i >= 0; i -= 1) {
    const raid = raids[i];
    if (raid && !isPostRaidShell(raid)) return raid;
  }
  return raids[raids.length - 1] || null;
}

/** 最近一场战局对应的房间同步相位：开战 / 结束优先于匹配中。 */
export function logPhaseFromParsed(
  parsed: TarkovLogParseResult | null | undefined,
): TarkovLogPhasePayload | null {
  if (!parsed) return null;
  const raids = parsed.raids || [];
  const raid = latestMeaningfulRaid(raids);
  if (raid) {
    let kind: TarkovLogEventKind = "matching";
    if (raid.endedAt) kind = "raid_exited";
    else if (raid.startedAt) kind = "raid_started";
    else if (raid.aborted) kind = "matching_aborted";
    else {
      const event = lastRaidFacingEvent(parsed);
      if (event) kind = event.kind;
    }
    return {
      kind,
      mapId: raid.mapId || "",
      mapLabel: raid.mapLabel || "",
      raidId: raid.raidId || "",
      at: raid.endedAt || raid.startedAt || lastRaidFacingEvent(parsed)?.at || "",
    };
  }
  const event = lastRaidFacingEvent(parsed);
  if (!event) return null;
  return {
    kind: event.kind,
    mapId: event.mapId || "",
    mapLabel: event.mapLabel || "",
    raidId: event.raidId || "",
    at: event.at || "",
  };
}

/** 最近一场或最近一条带地图的事件。 */
export function latestLogMapId(
  parsed: TarkovLogParseResult | null | undefined,
): string {
  const raids = parsed?.raids || [];
  for (let i = raids.length - 1; i >= 0; i -= 1) {
    const id = (raids[i]?.mapId || "").trim();
    if (id) return id;
  }
  const events = parsed?.events || [];
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const id = (events[i]?.mapId || "").trim();
    if (id) return id;
  }
  return "";
}

/** 最新一条战局事件或任务事件的时间，用于顶栏「最近日志」。 */
export function latestLogActivityAt(
  parsed: TarkovLogParseResult | null | undefined,
): string {
  const eventAt = latestLogEvent(parsed)?.at || "";
  const quests = parsed?.quests || [];
  const questAt = quests.length ? quests[quests.length - 1]?.at || "" : "";
  if (!eventAt) return questAt;
  if (!questAt) return eventAt;
  return eventAt.localeCompare(questAt) >= 0 ? eventAt : questAt;
}

/** 日志目录校验预览：最新一条事件，没有则退回启动文件夹名。 */
export function formatLatestLogPreview(
  stub: TarkovLogSessionStub | null | undefined,
  parsed?: TarkovLogParseResult | null,
): string {
  const event = latestLogEvent(parsed);
  if (event) {
    const clock = formatLogClock(event.at);
    const label = logEventLabel(event.kind);
    const map = event.mapLabel ? ` · ${event.mapLabel}` : "";
    return `${clock} ${label}${map}`.trim();
  }
  if (!stub) return "";
  return stub.startedAt || stub.folder;
}

export function scanLimitLabel(limit: TarkovGameLogScanLimit): string {
  if (limit === 0) return "全部";
  return `最近 ${limit}`;
}
