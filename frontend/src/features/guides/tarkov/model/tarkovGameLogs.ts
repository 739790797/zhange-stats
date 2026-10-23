import { MAPS_HREF, TARKOV_MAPS, tarkovMapHref } from "@/features/guides/tarkov/model/tarkovHomeNav";
import { logTextGrownFrom } from "@/features/guides/tarkov/model/tarkovLogTextCache";
import { parseTarkovScreenshotTime } from "@/features/guides/tarkov/model/tarkovScreenshotPos";

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
  /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})(?:\s*([+-])(\d{2}):(\d{2}))?\|/;
const CLOCK_PARTS_RE = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3})$/;
const BEIJING_OFFSET_MIN = 8 * 60;

function pad(n: number, width = 2): string {
  return String(n).padStart(width, "0");
}

/**
 * 日志行时间 → 北京墙钟（保留毫秒）。游戏按玩家本机时区写，并带上 `+01:00` 这类偏移；
 * 回放下限、清空时刻、账号上的时间都按北京墙钟比，所以带偏移的一律换算。
 * 不带偏移的老格式原样当北京墙钟（与以前一致）。纯算术，不依赖运行环境的时区。
 */
export function logClockToBeijing(
  clock: string,
  sign?: string,
  hh?: string,
  mm?: string,
): string {
  if (!sign || hh == null || mm == null) return clock;
  const offsetMin = (sign === "-" ? -1 : 1) * (Number(hh) * 60 + Number(mm));
  if (offsetMin === BEIJING_OFFSET_MIN) return clock;
  const m = CLOCK_PARTS_RE.exec(clock);
  if (!m) return clock;
  const utcMs =
    Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6], +m[7]) - offsetMin * 60_000;
  const d = new Date(utcMs + BEIJING_OFFSET_MIN * 60_000);
  return (
    `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ` +
    `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}.` +
    pad(d.getUTCMilliseconds(), 3)
  );
}

const FOLDER_TS_RE =
  /(?:^|log_)(\d{4})\.(\d{2})\.(\d{2})_(\d{1,2})-(\d{2})-(\d{2})/i;
const LOCATION_RE = /Location:\s*([^,]+)/i;
const SHORT_ID_RE = /shortId:\s*([A-Z0-9]{6})/;
const RAID_MODE_RE = /RaidMode:\s*(\w+)/i;
const SCENE_RE = /scene preset path:\s*(maps\/[a-zA-Z0-9_]+\.bundle)/i;
const SESSION_MODE_RE = /Session mode:\s*([^\s|]+)/i;
const SELECT_PROFILE_RE =
  /(?:Select(?:ed)?Profile|PrepareSelectedProfileLocally|CompleteSelectedProfile) ProfileId:([A-Za-z0-9]+) AccountId:(\d+)/;

export type TarkovLogEventKind =
  | "session_mode"
  | "profile"
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
  profileId?: string;
  accountId?: string;
  version?: string;
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
  /** 带时间戳的通知首行，供同步结果表展示。 */
  line?: string;
  /** 该事件时刻 application.log 里的 Session mode；空则回放时丢弃。 */
  sessionMode?: string;
  profileId?: string;
};

export type TarkovLogQuestDropReason =
  | "json_bad"
  | "no_session_mode"
  | "unknown_mode"
  | "seasonal"
  | "profile";

export type TarkovLogQuestDrop = {
  at: string;
  reason: TarkovLogQuestDropReason;
  line?: string;
  sessionMode?: string;
  profileId?: string;
};

export type TarkovLogSessionKind = "pvp" | "pve" | "seasonal" | "unknown";

export type TarkovLogIdentity = {
  at: string;
  sessionMode: string;
  profileId: string;
  accountId: string;
  version: string;
  folder?: string;
};

export type TarkovLogParseResult = {
  events: TarkovLogEvent[];
  raids: TarkovLogRaid[];
  sessionMode?: string;
  quests?: TarkovLogQuestEvent[];
  drops?: TarkovLogQuestDrop[];
  /** 本份日志首条带偏移行的时区偏移（如 `+01:00`）；启动文件夹名可按它换算成北京时间。 */
  clockOffset?: string;
};

/** 打开同步弹窗时从 application.log 抽出的一局，结束时间可能要等通知日志补上。 */
export type TarkovLogPreviewRaid = {
  key: string;
  mapId: string;
  mapLabel: string;
  startedAt: string;
  endedAt: string;
  raidId: string;
  sessionMode: string;
};

export type TarkovLogSessionStub = {
  folder: string;
  startedAt: string | null;
  identities?: TarkovLogIdentity[];
  raids?: TarkovLogPreviewRaid[];
};

export type TarkovLogRootKind = "logs" | "install" | "session" | "unknown";

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

const APPLICATION_LOG_RE = /(?:^|[\\/ ])application(?:_\d+)?\.log$/i;
const NOTIFICATIONS_LOG_RE = /(?:^|[\\/ ])(?:push-)?notifications(?:_\d+)?\.log$/i;
const OUTPUT_LOG_RE = /(?:^|[\\/ ])output(?:_\d+)?\.log$/i;
const LOG_VERSION_RE = /\|(\d+\.\d+\.\d+\.\d+)(?:\.\d+)?\|/;
const GAME_STOPPING_MARKER = "EFT.NetworkGame`1:GameStopping()";

export function isApplicationLogFileName(name: string): boolean {
  return APPLICATION_LOG_RE.test((name || "").trim());
}

export function isNotificationsLogFileName(name: string): boolean {
  return NOTIFICATIONS_LOG_RE.test((name || "").trim());
}

export function isOutputLogFileName(name: string): boolean {
  return OUTPUT_LOG_RE.test((name || "").trim());
}

export function isReadableTarkovLogFileName(name: string): boolean {
  return (
    isApplicationLogFileName(name) ||
    isNotificationsLogFileName(name) ||
    isOutputLogFileName(name)
  );
}

export function classifyLogSessionMode(
  raw: string | undefined,
): TarkovLogSessionKind | "" {
  const key = (raw || "").trim().toLowerCase();
  if (!key) return "";
  if (key === "pve") return "pve";
  if (key === "pvp" || key === "regular") return "pvp";
  if (
    key === "seasonal" ||
    key === "pvp-season" ||
    key === "pvpseason" ||
    key === "szn"
  ) {
    return "seasonal";
  }
  return "unknown";
}

export function versionFromLogLine(line: string, fallback = ""): string {
  return LOG_VERSION_RE.exec(line)?.[1] || fallback;
}

export function isSessionFolderName(name: string): boolean {
  return FOLDER_TS_RE.test(name || "");
}

/**
 * 启动文件夹名里的时刻是**游戏本机墙钟**：文件夹名不带时区偏移，而回下来全按北京墙钟比
 * （日期范围、断点、排序）。带上从该次启动的日志里读到的偏移就能换算成北京时间。
 */
export function parseSessionFolderTime(name: string): string | null {
  const match = FOLDER_TS_RE.exec(name || "");
  if (!match) return null;
  const [, year, month, day, hour, minute, second] = match;
  const hh = String(hour).padStart(2, "0");
  return `${year}-${month}-${day} ${hh}:${minute}:${second}`;
}

const FOLDER_CLOCK_RE = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\.\d{1,3})?$/;

/** 文件夹名时刻 → 北京墙钟（`+01:00` 这类偏移来自同一份启动记录里的日志行）。 */
export function folderTimeToBeijing(
  folderTime: string | null | undefined,
  clockOffset: string | null | undefined,
): string | null {
  const clock = (folderTime || "").trim();
  if (!clock) return null;
  const parts = FOLDER_CLOCK_RE.exec(clock);
  if (!parts) return clock;
  const offset = /^([+-])(\d{2}):(\d{2})$/.exec((clockOffset || "").trim());
  if (!offset) return clock;
  return logClockToBeijing(`${parts[1]}.000`, offset[1], offset[2], offset[3]).replace(
    /\.\d{3}$/,
    "",
  );
}

/**
 * 读过这次启动的日志后，把 stub 的 startedAt 换成北京墙钟（偏移取自该次日志 `parsed.clockOffset`）。
 * 日志里没有带偏移的行（老格式）就原样保留。
 * 遗留：还没读日志、只列了目录的 stub 仍是本机墙钟。列目录阶段的排序只在同一台机器的文件夹之间比，
 * 通常偏移相同、先后不变（只有改过时区或夏令时切换前后那一小时可能颠倒）；按北京日期筛选要用换算后的。
 */
export function sessionStubInBeijing(
  stub: TarkovLogSessionStub,
  parsed: Pick<TarkovLogParseResult, "clockOffset"> | null | undefined,
): TarkovLogSessionStub {
  const startedAt = folderTimeToBeijing(stub.startedAt, parsed?.clockOffset);
  return startedAt === stub.startedAt ? stub : { ...stub, startedAt };
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

/** 写不进存储时记在内存里，本页照常生效，刷新后不保留。 */
let unsavedScreenshotPrunePref: TarkovScreenshotPrunePref | null = null;

/** 存储被禁用（隐私模式、站点数据被拦）时 localStorage 访问会抛错，按默认偏好处理。 */
export function loadScreenshotPrunePref(): TarkovScreenshotPrunePref {
  if (typeof window === "undefined") return { ...DEFAULT_SCREENSHOT_PRUNE_PREF };
  if (unsavedScreenshotPrunePref) return { ...unsavedScreenshotPrunePref };
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(TARKOV_SCREENSHOT_PRUNE_STORAGE_KEY);
  } catch {
    raw = null;
  }
  return parseScreenshotPrunePref(raw);
}

export function saveScreenshotPrunePref(
  pref: TarkovScreenshotPrunePref,
): TarkovScreenshotPrunePref {
  const next = {
    enabled: pref.enabled === true,
    keepMax: clampScreenshotPruneKeep(pref.keepMax),
  };
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(
        TARKOV_SCREENSHOT_PRUNE_STORAGE_KEY,
        JSON.stringify(next),
      );
      unsavedScreenshotPrunePref = null;
    } catch {
      unsavedScreenshotPrunePref = { ...next };
    }
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

/** 只有名字时 lastModified 记 0，比较退回文件名。 */
export type TarkovScreenshotListing = string | { name: string; lastModified?: number };

function listingStamp(row: TarkovScreenshotListing): TarkovScreenshotStamp {
  return typeof row === "string"
    ? { name: row, lastModified: 0 }
    : { name: row.name, lastModified: Number(row.lastModified) || 0 };
}

/**
 * 截图新旧：先比文件名里的日期时刻（只到分钟，小时可能是一位数，不能按字符串比），
 * 同一分钟再比修改时间（有的话），最后比文件名（数字按数值比）。不带日期的名字算最旧。
 */
export function compareScreenshotAge(
  a: TarkovScreenshotStamp,
  b: TarkovScreenshotStamp,
): number {
  const ta = parseTarkovScreenshotTime(a.name) || "";
  const tb = parseTarkovScreenshotTime(b.name) || "";
  if (ta !== tb) return ta < tb ? -1 : 1;
  if (a.lastModified !== b.lastModified) return a.lastModified - b.lastModified;
  return a.name.localeCompare(b.name, undefined, { numeric: true });
}

/** 有游戏截图时只看带日期的；返回从旧到新。 */
function screenshotPool(rows: readonly TarkovScreenshotListing[]): TarkovScreenshotStamp[] {
  const images = rows.map(listingStamp).filter((row) => isScreenshotFileName(row.name));
  const dated = images.filter((row) => TARKOV_SCREENSHOT_STAMP_RE.test(row.name));
  return (dated.length ? dated : images).sort(compareScreenshotAge);
}

/** 最新一张：按文件名里的拍摄时刻，同一分钟再看修改时间。 */
export function latestScreenshotName(
  rows: readonly TarkovScreenshotListing[],
): string | null {
  const pool = screenshotPool(rows);
  return pool[pool.length - 1]?.name ?? null;
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

/** 首次列目录时最多看这么多张没见过的，免得逐张读完整个旧目录。 */
export const TARKOV_SCREENSHOT_INSPECT_MAX = 20;

/**
 * 没读过的截图都要看（从旧到新，最新在最后）：同一分钟连拍两张时，文件名排序可能把新的排在前面，
 * 调用方又会把整目录记为已读，只看「最新」一张会漏掉另一张。
 */
export function screenshotNamesToInspect(
  rows: readonly TarkovScreenshotListing[],
  seen: ReadonlySet<string>,
  limit = TARKOV_SCREENSHOT_INSPECT_MAX,
): string[] {
  const fresh = screenshotPool(rows).filter((row) => !seen.has(row.name));
  return fresh.slice(Math.max(0, fresh.length - Math.max(1, limit))).map((row) => row.name);
}

/** 游戏截图多于 keepMax 时，从最旧的开始删；最新一张始终留着。必须传入整目录文件名，不能只传新出现的几张。 */
export function screenshotNamesToPrune(
  rows: readonly TarkovScreenshotListing[],
  keepLatest: string | null,
  keepMax: number,
  batch = TARKOV_SCREENSHOT_PRUNE_BATCH,
): string[] {
  const dated = rows
    .map(listingStamp)
    .filter((row) => isTarkovGameScreenshotName(row.name));
  const cap = clampScreenshotPruneKeep(keepMax);
  if (dated.length <= cap) return [];
  const newestFirst = dated.sort(compareScreenshotAge).reverse().map((row) => row.name);
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
  // startedAt 是文件夹名里的游戏本机墙钟：这时还没读日志、拿不到偏移。读过日志后用 sessionStubInBeijing 换算。
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
  if (
    key === "seasonal" ||
    key === "pvp-season" ||
    key === "pvpseason" ||
    key === "szn"
  ) {
    return "赛季";
  }
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
  return event.kind !== "session_mode" && event.kind !== "profile";
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
    if (event.kind === "session_mode" || event.kind === "profile") continue;
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
  line: string,
): { quest: TarkovLogQuestEvent | null; drop: TarkovLogQuestDrop | null } {
  const until = nextLogLineIndex(text, lineStart + 1);
  const block = text.slice(lineStart, until);
  const jsonText = extractJsonObject(block, 0, 512_000);
  if (!jsonText) {
    return {
      quest: null,
      drop: { at, reason: "json_bad", line: line.trim() || undefined },
    };
  }
  try {
    return { quest: questEventFromMessage(JSON.parse(jsonText), at), drop: null };
  } catch {
    return {
      quest: null,
      drop: { at, reason: "json_bad", line: line.trim() || undefined },
    };
  }
}

type LogSessionIdentity = {
  at: string;
  sessionMode: string;
  profileId: string;
  accountId: string;
  version: string;
};

function logSessionIdentityTimeline(
  events: readonly TarkovLogEvent[],
): LogSessionIdentity[] {
  const timeline: LogSessionIdentity[] = [];
  let sessionMode = "";
  let profileId = "";
  let accountId = "";
  let version = "";
  for (const event of events) {
    if (event.kind === "session_mode") {
      sessionMode = (event.sessionMode || "").trim();
      profileId = "";
      accountId = "";
      if (event.version) version = event.version;
      timeline.push({
        at: event.at || "",
        sessionMode,
        profileId,
        accountId,
        version,
      });
      continue;
    }
    if (event.kind === "profile") {
      profileId = (event.profileId || "").trim();
      accountId = (event.accountId || "").trim();
      if (event.version) version = event.version;
      timeline.push({
        at: event.at || "",
        sessionMode,
        profileId,
        accountId,
        version,
      });
    }
  }
  return timeline;
}

export function identitiesFromEvents(
  events: readonly TarkovLogEvent[],
  folder = "",
): TarkovLogIdentity[] {
  const out: TarkovLogIdentity[] = [];
  for (const row of logSessionIdentityTimeline(events)) {
    if (!row.profileId) continue;
    const kind = classifyLogSessionMode(row.sessionMode);
    if (!kind || kind === "unknown") continue;
    out.push({
      at: row.at,
      sessionMode: row.sessionMode,
      profileId: row.profileId,
      accountId: row.accountId,
      version: row.version,
      folder,
    });
  }
  return out;
}

export function identitiesFromParsed(
  parsed: Pick<TarkovLogParseResult, "events"> | null | undefined,
  folder = "",
): TarkovLogIdentity[] {
  return identitiesFromEvents(parsed?.events || [], folder);
}

function identityAt(
  timeline: readonly LogSessionIdentity[],
  at: string,
): LogSessionIdentity | undefined {
  const clock = at || "";
  let found: LogSessionIdentity | undefined;
  for (const row of timeline) {
    if ((row.at || "") <= clock) found = row;
  }
  return found;
}

function stampQuestsWithSession(
  quests: readonly TarkovLogQuestEvent[],
  events: readonly TarkovLogEvent[],
): TarkovLogQuestEvent[] {
  const timeline = logSessionIdentityTimeline(events);
  if (!timeline.length) return [...quests];
  return quests.map((quest) => {
    const ident = identityAt(timeline, quest.at || "");
    if (!ident) return quest;
    return {
      ...quest,
      sessionMode: ident.sessionMode || undefined,
      profileId: ident.profileId || undefined,
    };
  });
}

function lastSessionModeFromEvents(events: readonly TarkovLogEvent[]): string {
  let sessionMode = "";
  for (const event of events) {
    if (event.kind === "session_mode" && event.sessionMode) {
      sessionMode = event.sessionMode;
    }
  }
  return sessionMode;
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

/** 逐行扫描的累积状态；实时轮询接着上次的状态只扫新追加的行。 */
type LogScanState = {
  events: TarkovLogEvent[];
  /** 还没按 Session mode 盖章的任务事件。 */
  quests: TarkovLogQuestEvent[];
  drops: TarkovLogQuestDrop[];
  sessionMode: string;
  version: string;
  /** 首条带偏移行的偏移，如 `+01:00`。 */
  clockOffset: string;
};

function emptyScanState(): LogScanState {
  return { events: [], quests: [], drops: [], sessionMode: "", version: "", clockOffset: "" };
}

/** 扫 text（已换成 \n）里的每一行，结果追加进 st。块（通知 JSON）往后看到下一条带时间戳的行为止。 */
function scanLogLines(st: LogScanState, text: string, outputOnly: boolean): void {
  const lines = text.split("\n");
  let offset = 0;
  for (const line of lines) {
    const lineStart = offset;
    offset += line.length + 1;
    const ts = TS_RE.exec(line);
    if (ts?.[2] && !st.clockOffset) st.clockOffset = `${ts[2]}${ts[3]}:${ts[4]}`;
    const clock = ts ? logClockToBeijing(ts[1]!, ts[2], ts[3], ts[4]) : "";
    if (outputOnly) {
      if (!line.includes(GAME_STOPPING_MARKER)) continue;
      st.events.push({ kind: "raid_exited", at: clock || st.events[st.events.length - 1]?.at || "" });
      continue;
    }
    const at =
      clock ||
      st.events[st.events.length - 1]?.at ||
      st.quests[st.quests.length - 1]?.at ||
      "";
    st.version = versionFromLogLine(line, st.version);
    if (line.includes(GAME_STOPPING_MARKER)) {
      st.events.push({ kind: "raid_exited", at });
      continue;
    }
    if (SESSION_MODE_RE.test(line)) {
      st.sessionMode = (SESSION_MODE_RE.exec(line)?.[1] || "").trim();
      st.events.push({ kind: "session_mode", at, sessionMode: st.sessionMode, version: st.version || undefined });
      continue;
    }
    const profileMatch = SELECT_PROFILE_RE.exec(line);
    if (profileMatch) {
      st.events.push({
        kind: "profile",
        at,
        profileId: profileMatch[1],
        accountId: profileMatch[2],
        version: st.version || undefined,
      });
      if (line.includes("PrepareSelectedProfileLocally")) {
        st.events.push({ kind: "raid_exited", at });
      }
      continue;
    }
    if (line.includes("Got notification | ChatMessageReceived")) {
      const parsed = parseChatQuest(text, lineStart, at, line);
      if (parsed.quest) {
        const stamped = line.trim();
        st.quests.push(stamped ? { ...parsed.quest, line: stamped } : parsed.quest);
      } else if (parsed.drop) {
        st.drops.push(parsed.drop);
      }
      continue;
    }
    if (line.includes("Got notification | UserMatchOver")) {
      const exited = parseUserMatchOver(text, lineStart, at);
      if (exited) st.events.push(exited);
      continue;
    }
    if (line.includes("application|scene preset path:") || line.includes("|scene preset path:")) {
      const scene = SCENE_RE.exec(line)?.[1] || "";
      const mapId = mapLogSceneToMapId(scene);
      st.events.push(attachMap({ kind: "map_loading", at }, "", mapId));
      continue;
    }
    if (line.includes("application|LocationLoaded") || line.includes("|LocationLoaded")) {
      st.events.push({ kind: "matching", at });
      continue;
    }
    if (
      line.includes("application|TRACE-NetworkGameCreate profileStatus") ||
      line.includes("TRACE-NetworkGameCreate profileStatus")
    ) {
      const location = (LOCATION_RE.exec(line)?.[1] || "").trim();
      const raidId = (SHORT_ID_RE.exec(line)?.[1] || "").trim();
      const raidMode = parseLogRaidMode(RAID_MODE_RE.exec(line)?.[1] || "");
      st.events.push(
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
      st.events.push({ kind: "raid_starting", at });
      continue;
    }
    if (line.includes("application|GameStarted") || /\|GameStarted(?:\||$)/.test(line)) {
      st.events.push({ kind: "raid_started", at });
      continue;
    }
    if (
      line.includes("Network game matching aborted") ||
      line.includes("Network game matching cancelled")
    ) {
      st.events.push({ kind: "matching_aborted", at });
    }
  }
}

/** 由扫描状态出结果；数组都是新的，之后续扫往 st 里追加不会改到已交出去的结果。 */
function finishScan(st: LogScanState, outputOnly: boolean): TarkovLogParseResult {
  const extra = st.clockOffset ? { clockOffset: st.clockOffset } : {};
  if (outputOnly) return { events: [...st.events], raids: [], ...extra };
  const events = [...st.events];
  return {
    events,
    raids: buildRaidsFromEvents(events),
    sessionMode: lastSessionModeFromEvents(events) || st.sessionMode || undefined,
    quests: stampQuestsWithSession(st.quests, events),
    drops: [...st.drops],
    ...extra,
  };
}

export function parseTarkovLogText(text: string): TarkovLogParseResult {
  const st = emptyScanState();
  scanLogLines(st, (text || "").replace(/\r\n/g, "\n"), false);
  return finishScan(st, false);
}

const DATED_LINE_RE = /^\d{4}-\d{2}-\d{2} /;

/**
 * 实时轮询能安全续扫到哪里（text 已换成 \n）：最后一条带时间戳的行的行首。
 * 通知块（JSON）一直延续到下一条带时间戳的行，所以这一行之前的块都已封口，解析结果不会再变；
 * 这一行和它后面的续行（含没写完的半行）每轮单独补扫。
 */
export function safeLogParseEnd(text: string): number {
  let pos = text.length;
  for (;;) {
    const lineStart = pos > 0 ? text.lastIndexOf("\n", pos - 1) + 1 : 0;
    if (DATED_LINE_RE.test(text.slice(lineStart, lineStart + 11))) return lineStart;
    if (lineStart === 0) return 0;
    pos = lineStart - 1;
  }
}

type TarkovLogPart = { name: string; text: string };

type LogPartMemo = {
  name: string;
  /** 已扫过的前缀（已换成 \n），续扫前先确认新文本以它开头。 */
  prefix: string;
  state: LogScanState;
  text: string;
  parsed: TarkovLogParseResult;
};

/**
 * 实时轮询按文件对象（键）记住上次的扫描：文本没变直接复用；只是往后追加了内容，就接着上次的状态
 * 只扫新增的、已写完整的行（见 safeLogParseEnd），结果与整份重扫一致。没写完的半行 / 半块每轮在副本上补扫，不进累积状态。
 */
export type TarkovLogBundleMemo = WeakMap<object, LogPartMemo>;

function parseLogPart(
  part: TarkovLogPart,
  memo?: TarkovLogBundleMemo,
): TarkovLogParseResult {
  const outputOnly = isOutputLogFileName(part.name);
  let hit = memo?.get(part);
  if (hit && hit.name === part.name && hit.text === part.text) return hit.parsed;
  // 实时读盘在文件变长时交来的是新对象（tarkovLogTextCache 续读），顺着它找到上一轮的对象接着扫。
  const grownFrom = hit ? undefined : logTextGrownFrom(part);
  if (memo && grownFrom) {
    hit = memo.get(grownFrom);
    // 下面会往 hit.state 里追加；旧对象的记录随即作废，免得它日后拿已经扫远了的状态续扫。
    memo.delete(grownFrom);
  }
  const source = (part.text || "").replace(/\r\n/g, "\n");
  const safeEnd = safeLogParseEnd(source);
  const resumeFrom =
    hit && hit.name === part.name && safeEnd >= hit.prefix.length && source.startsWith(hit.prefix)
      ? hit
      : null;
  const state = resumeFrom ? resumeFrom.state : emptyScanState();
  scanLogLines(state, source.slice(resumeFrom ? resumeFrom.prefix.length : 0, safeEnd), outputOnly);
  let parsed: TarkovLogParseResult;
  if (safeEnd < source.length) {
    const tail: LogScanState = {
      ...state,
      events: [...state.events],
      quests: [...state.quests],
      drops: [...state.drops],
    };
    scanLogLines(tail, source.slice(safeEnd), outputOnly);
    parsed = finishScan(tail, outputOnly);
  } else {
    parsed = finishScan(state, outputOnly);
  }
  memo?.set(part, { name: part.name, prefix: source.slice(0, safeEnd), state, text: part.text, parsed });
  return parsed;
}

export function parseTarkovLogBundle(
  parts: TarkovLogPart[],
  memo?: TarkovLogBundleMemo,
): TarkovLogParseResult {
  const events: TarkovLogEvent[] = [];
  const quests: TarkovLogQuestEvent[] = [];
  const drops: TarkovLogQuestDrop[] = [];
  const ordered = [...parts].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true }),
  );
  /* 会话目录名是本机墙钟：沿用第一个带时区的分片，sessionStubInBeijing 才换得动。 */
  let clockOffset = "";
  for (const part of ordered) {
    const parsed = parseLogPart(part, memo);
    if (!clockOffset && parsed.clockOffset) clockOffset = parsed.clockOffset;
    events.push(...parsed.events);
    quests.push(...(parsed.quests ?? []));
    drops.push(...(parsed.drops ?? []));
  }
  events.sort((a, b) => {
    const cmp = (a.at || "").localeCompare(b.at || "");
    if (cmp !== 0) return cmp;
    return eventOrder(a.kind) - eventOrder(b.kind);
  });
  quests.sort((a, b) => (a.at || "").localeCompare(b.at || ""));
  const stamped = stampQuestsWithSession(quests, events);
  return {
    events,
    raids: buildRaidsFromEvents(events),
    sessionMode: lastSessionModeFromEvents(events) || undefined,
    quests: stamped,
    drops,
    ...(clockOffset ? { clockOffset } : {}),
  };
}

function eventOrder(kind: TarkovLogEventKind): number {
  switch (kind) {
    case "session_mode":
      return 0;
    case "profile":
      return 1;
    case "map_loading":
      return 2;
    case "matching":
      return 3;
    case "match_found":
      return 4;
    case "raid_starting":
      return 5;
    case "raid_started":
      return 6;
    case "matching_aborted":
      return 7;
    case "raid_exited":
      return 8;
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
  const parsedByFolder = new Map(
    sessions.map((session) => [session.folder, session.parsed]),
  );
  return historyRaidsFromSessions(sessions).map((raid) => {
    const parsed = parsedByFolder.get(raid.folder);
    const timeline = parsed ? logSessionIdentityTimeline(parsed.events || []) : [];
    const ident = identityAt(timeline, raid.startedAt || raid.endedAt || "");
    return {
      folder: raid.folder,
      raid_id: raid.raidId || "",
      location: raid.location || "",
      map_id: raid.mapId || "",
      map_label: raid.mapLabel || "",
      raid_mode: raid.raidMode,
      session_mode: ident?.sessionMode || parsed?.sessionMode || "",
      started_at: raid.startedAt || "",
      ended_at: raid.endedAt || "",
      reconnected: Boolean(raid.reconnected),
      aborted: Boolean(raid.aborted),
    };
  });
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
  raidMode?: TarkovLogRaidMode;
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
      raidMode: raid.raidMode,
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
    raidMode: event.raidMode,
  };
}

/** 当前有意义战局的地图；空图不回落到上一场，方便离线手选。 */
export function latestLogMapId(
  parsed: TarkovLogParseResult | null | undefined,
): string {
  const raid = latestMeaningfulRaid(parsed?.raids || []);
  if (raid) return (raid.mapId || "").trim();
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
  return sessionStubInBeijing(stub, parsed).startedAt || stub.folder;
}
