export const LOADERS = [
  { value: "fabric", label: "Fabric" },
  { value: "quilt", label: "Quilt" },
  { value: "forge", label: "Forge" },
  { value: "neoforge", label: "NeoForge" },
];

export const MOD_LOADERS = LOADERS.map((row) => row.value);

const ICON = "/minecraft-icons";

export const MC_ICONS = {
  vanilla: `${ICON}/vanilla.svg`,
  snapshot: `${ICON}/snapshot.svg`,
  old: `${ICON}/old.svg`,
  fool: `${ICON}/fool.svg`,
  fabric: `${ICON}/fabric.svg`,
  forge: `${ICON}/forge.svg`,
  neoforge: `${ICON}/neoforge.svg`,
  quilt: `${ICON}/quilt.svg`,
  paper: `${ICON}/paper.svg`,
  purpur: `${ICON}/purpur.svg`,
  spigot: `${ICON}/spigot.svg`,
  mohist: `${ICON}/mohist.svg`,
  arclight: `${ICON}/arclight.svg`,
  youer: `${ICON}/youer.svg`,
  banner: `${ICON}/banner.svg`,
  catserver: `${ICON}/catserver.svg`,
  kindMod: `${ICON}/kind-mod.svg`,
  kindPlugin: `${ICON}/kind-plugin.svg`,
  kindHybrid: `${ICON}/kind-hybrid.svg`,
} as const;

export type ServerKind = "vanilla" | "mod" | "plugin" | "hybrid";
export type McVersionChannel = "release" | "snapshot" | "old" | "fool";

export type McGameVersion = {
  version: string;
  stable?: boolean;
  version_type?: string | null;
  release_time?: string | null;
};

export type MinecraftSetupValue = {
  mcVersion: string;
  kind: ServerKind | "";
  core: string;
};

export type ServerKindOption = {
  key: ServerKind;
  name: string;
  hint: string;
  icon: string;
};

export type ServerCoreOption = {
  key: string;
  name: string;
  hint: string;
  /** 已接入档案的模组加载器；空表示还只是选型 */
  loader: string;
  icon: string;
};

export const SERVER_KINDS: ServerKindOption[] = [
  { key: "vanilla", name: "纯净端", hint: "官方原版，无模组、无插件", icon: MC_ICONS.vanilla },
  { key: "mod", name: "模组端", hint: "Forge / NeoForge / Fabric / Quilt", icon: MC_ICONS.kindMod },
  { key: "plugin", name: "插件端", hint: "Paper / Purpur / Spigot", icon: MC_ICONS.kindPlugin },
  { key: "hybrid", name: "混合端", hint: "模组 + 插件，Mohist / Arclight 等", icon: MC_ICONS.kindHybrid },
];

export const SERVER_CORES: Record<ServerKind, ServerCoreOption[]> = {
  vanilla: [
    { key: "vanilla", name: "Vanilla", hint: "官方原版服务端", loader: "", icon: MC_ICONS.vanilla },
  ],
  mod: [
    { key: "neoforge", name: "NeoForge", hint: "可以添加", loader: "neoforge", icon: MC_ICONS.neoforge },
    { key: "forge", name: "Forge", hint: "可以添加", loader: "forge", icon: MC_ICONS.forge },
    { key: "fabric", name: "Fabric", hint: "可以添加", loader: "fabric", icon: MC_ICONS.fabric },
    { key: "quilt", name: "Quilt", hint: "可以添加", loader: "quilt", icon: MC_ICONS.quilt },
  ],
  plugin: [
    { key: "paper", name: "Paper", hint: "可以添加", loader: "", icon: MC_ICONS.paper },
    { key: "purpur", name: "Purpur", hint: "可以添加", loader: "", icon: MC_ICONS.purpur },
    { key: "spigot", name: "Spigot", hint: "可以添加", loader: "", icon: MC_ICONS.spigot },
  ],
  hybrid: [
    { key: "mohist", name: "Mohist", hint: "Forge / NeoForge + 插件", loader: "", icon: MC_ICONS.mohist },
    { key: "arclight", name: "Arclight", hint: "Forge / Fabric + 插件", loader: "", icon: MC_ICONS.arclight },
    { key: "youer", name: "Youer", hint: "Fabric + 插件", loader: "", icon: MC_ICONS.youer },
    { key: "banner", name: "Banner", hint: "Fabric + 插件", loader: "", icon: MC_ICONS.banner },
    { key: "catserver", name: "CatServer", hint: "Forge + 插件，偏老版本", loader: "", icon: MC_ICONS.catserver },
  ],
};

const APRIL_FOOLS = new Set([
  "15w14a",
  "1.RV-Pre1",
  "3D Shareware v1.34",
  "20w14infinite",
  "22w13oneblockatatime",
  "23w13a_or_b",
  "24w14potato",
  "25w14craftmine",
]);

export const VERSION_CHANNELS: { key: McVersionChannel; title: string; icon: string }[] = [
  { key: "release", title: "正式版", icon: MC_ICONS.vanilla },
  { key: "snapshot", title: "预览版", icon: MC_ICONS.snapshot },
  { key: "old", title: "远古版", icon: MC_ICONS.old },
  { key: "fool", title: "愚人节版", icon: MC_ICONS.fool },
];

export function isAprilFoolsVersion(id: string) {
  const name = (id || "").trim();
  if (!name) return false;
  if (APRIL_FOOLS.has(name)) return true;
  return /infinite|potato|oneblock|shareware|craftmine|_or_b|^2\.0/i.test(name);
}

export function classifyMcVersion(row: McGameVersion): McVersionChannel {
  if (isAprilFoolsVersion(row.version)) return "fool";
  const kind = (row.version_type || "").trim().toLowerCase();
  if (kind === "old_alpha" || kind === "old_beta") return "old";
  if (kind === "snapshot") return "snapshot";
  if (kind === "release") return "release";
  return row.stable ? "release" : "snapshot";
}

export function groupMcVersions(rows: McGameVersion[]) {
  const groups: Record<McVersionChannel, McGameVersion[]> = {
    release: [],
    snapshot: [],
    old: [],
    fool: [],
  };
  for (const row of rows) {
    groups[classifyMcVersion(row)].push(row);
  }
  return {
    latestRelease: groups.release[0] || null,
    latestSnapshot: groups.snapshot[0] || null,
    groups,
  };
}

export function coresForKind(kind: ServerKind | "") {
  if (!kind) return [];
  return SERVER_CORES[kind];
}

export function findServerKind(kind: ServerKind | "") {
  return SERVER_KINDS.find((row) => row.key === kind);
}

export function findServerCore(kind: ServerKind | "", core: string) {
  return coresForKind(kind).find((row) => row.key === core);
}

export function modLoaderOfCore(core: string) {
  const key = (core || "").trim().toLowerCase();
  return MOD_LOADERS.includes(key) ? key : "";
}

export function inferSetupFromPlaybook(
  mcVersion: string,
  loader: string,
): MinecraftSetupValue {
  const version = (mcVersion || "").trim();
  const core = (loader || "").trim().toLowerCase();
  if (!core || core === "vanilla") {
    return { mcVersion: version, kind: core ? "vanilla" : "", core };
  }
  if (MOD_LOADERS.includes(core)) {
    return { mcVersion: version, kind: "mod", core };
  }
  if (["paper", "purpur", "spigot", "bukkit"].includes(core)) {
    return { mcVersion: version, kind: "plugin", core };
  }
  if (["mohist", "arclight", "youer", "banner", "catserver"].includes(core)) {
    return { mcVersion: version, kind: "hybrid", core };
  }
  return { mcVersion: version, kind: "mod", core };
}

export function setupSummary(value: MinecraftSetupValue) {
  const kind = findServerKind(value.kind);
  const core = findServerCore(value.kind, value.core);
  const parts = [value.mcVersion, kind?.name, core?.name].filter(Boolean);
  return parts.join(" · ");
}

export function versionChannelIcon(channel: McVersionChannel) {
  return VERSION_CHANNELS.find((row) => row.key === channel)?.icon || MC_ICONS.vanilla;
}

export function setupIcon(value: Pick<MinecraftSetupValue, "kind" | "core">) {
  const core = findServerCore(value.kind, value.core);
  if (core?.icon) return core.icon;
  const kind = findServerKind(value.kind);
  if (kind?.icon) return kind.icon;
  return MC_ICONS.vanilla;
}

export type EggLoaderHint = {
  egg_id?: number | null;
  name?: string | null;
  description?: string | null;
  nest?: string | null;
  startup?: string | null;
  key?: string | null;
  loaders?: string[] | null;
};

const LOADER_EGG_RULES: Record<string, { include: string[]; exclude: string[] }> =
  {
    neoforge: { include: ["neoforge"], exclude: [] },
    fabric: { include: ["fabric"], exclude: ["quilt", "forge", "neoforge"] },
    quilt: { include: ["quilt"], exclude: [] },
    forge: { include: ["forge"], exclude: ["neoforge", "fabric"] },
  };

function eggBlob(egg: EggLoaderHint) {
  return [
    egg.name,
    egg.description,
    egg.nest,
    egg.startup,
    egg.key,
    ...(egg.loaders || []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function inferEggLoader(egg: EggLoaderHint) {
  const text = eggBlob(egg);
  if (text.includes("neoforge")) return "neoforge";
  if (text.includes("quilt")) return "quilt";
  if (text.includes("fabric")) return "fabric";
  if (text.includes("forge")) return "forge";
  return "";
}

export function eggMatchesLoader(egg: EggLoaderHint, loader: string) {
  const kind = (loader || "").trim().toLowerCase();
  if (!kind) return true;
  const preset = LOADER_EGG_RULES[kind];
  if (!preset) return true;
  const text = eggBlob(egg);
  if (preset.exclude.some((token) => text.includes(token))) return false;
  return preset.include.some((token) => text.includes(token));
}

export function eggsForLoader<T extends EggLoaderHint>(
  eggs: T[],
  loader: string,
  currentEggId?: number | null,
) {
  const matched = eggs.filter((egg) => eggMatchesLoader(egg, loader));
  const rows = matched.length ? matched : eggs;
  if (!currentEggId) return rows;
  const current = eggs.find((egg) => egg.egg_id === currentEggId);
  if (current && !rows.some((egg) => egg.egg_id === currentEggId)) {
    return [current, ...rows];
  }
  return rows;
}

export function pickSelectedEggId(opts: {
  availableIds: Array<number | null | undefined>;
  currentId?: number | null;
  recommendedId?: number | null;
  prev?: number | null;
}) {
  const ids = opts.availableIds.filter((id): id is number => Boolean(id));
  if (opts.prev != null && ids.includes(opts.prev)) return opts.prev;
  if (opts.currentId && ids.includes(opts.currentId)) return opts.currentId;
  if (opts.recommendedId && ids.includes(opts.recommendedId)) {
    return opts.recommendedId;
  }
  return ids[0] ?? null;
}

export function eggOptionLabel(
  egg: { name?: string | null; nest?: string | null },
  opts?: { current?: boolean; recommended?: boolean },
) {
  const name = (egg.name || "未命名 Egg").trim();
  const nest = (egg.nest || "").trim();
  const base = nest ? `${nest} / ${name}` : name;
  const tags: string[] = [];
  if (opts?.current) tags.push("当前");
  if (opts?.recommended) tags.push("推荐");
  return tags.length ? `${base}（${tags.join(" · ")}）` : base;
}

export const PLAYBOOK_STEPS = [
  { key: "bootstrap", title: "基础开服", description: "选版本和核心" },
  { key: "mods", title: "模组", description: "缺的再下载" },
  { key: "config", title: "配置", description: "首启后再改" },
] as const;

export type PlaybookStageKey = (typeof PLAYBOOK_STEPS)[number]["key"];

export function playbookStageColor(status?: string) {
  if (status === "applied") return "green";
  if (status === "dirty") return "gold";
  return undefined;
}

export function playbookStageLabel(status?: string) {
  if (status === "applied") return "已完成";
  if (status === "dirty") return "有改动";
  return "未执行";
}

export const PROPERTY_FIELDS: { key: string; label: string }[] = [
  { key: "motd", label: "MOTD" },
  { key: "max-players", label: "人数上限" },
  { key: "difficulty", label: "难度" },
  { key: "gamemode", label: "游戏模式" },
  { key: "white-list", label: "白名单" },
  { key: "enforce-whitelist", label: "强制白名单" },
  { key: "view-distance", label: "视距" },
  { key: "simulation-distance", label: "模拟距离" },
  { key: "pvp", label: "PvP" },
  { key: "online-mode", label: "正版验证" },
  { key: "spawn-protection", label: "出生点保护" },
  { key: "enable-command-block", label: "命令方块" },
];

const PROP_VALUE_LABELS: Record<string, Record<string, string>> = {
  difficulty: {
    peaceful: "和平",
    easy: "简单",
    normal: "普通",
    hard: "困难",
  },
  gamemode: {
    survival: "生存",
    creative: "创造",
    adventure: "冒险",
    spectator: "旁观",
  },
  "white-list": { true: "开", false: "关" },
  pvp: { true: "开", false: "关" },
  "online-mode": { true: "正版", false: "离线" },
};

export const DEFAULT_SERVER_ICON = "/platform-icons/minecraft.png";

/** 总览展示用主机名，去掉端口；优先 public_host。 */
export function displayJoinHost(opts: {
  publicHost?: string | null;
  address?: string | null;
}) {
  const host = (opts.publicHost || "").trim();
  if (host) return host;
  const address = (opts.address || "").trim();
  if (!address) return "";
  const bracket = address.match(/^\[([^\]]+)\](?::\d+)?$/);
  if (bracket) return bracket[1];
  const colon = address.lastIndexOf(":");
  if (colon > 0 && /^\d+$/.test(address.slice(colon + 1))) {
    return address.slice(0, colon);
  }
  return address;
}

export function formatPropertyValue(key: string, value: string) {
  const mapped = PROP_VALUE_LABELS[key]?.[value.trim().toLowerCase()];
  return mapped || value;
}

export function minecraftHeadUrl(player: {
  name: string;
  id?: string | null;
}) {
  const id = (player.id || "").replace(/-/g, "").toLowerCase();
  if (/^[0-9a-f]{32}$/.test(id)) {
    return `https://mc-heads.net/avatar/${id}/32`;
  }
  const name = (player.name || "").trim();
  if (!name) return undefined;
  return `https://mc-heads.net/avatar/${encodeURIComponent(name)}/32`;
}

export function displayModName(mod: {
  project_title?: string | null;
  filename: string;
}) {
  const title = (mod.project_title || "").trim();
  if (title) return title;
  const name = mod.filename || "";
  return name.toLowerCase().endsWith(".jar") ? name.slice(0, -4) : name;
}

export function joinHints(opts: {
  versionName?: string | null;
  properties?: Record<string, string> | null;
}) {
  const hints: string[] = [];
  const version = (opts.versionName || "").trim();
  if (version) hints.push(`客户端请用 ${version}`);
  const props = opts.properties || {};
  const onlineMode = (props["online-mode"] || "").trim().toLowerCase();
  if (onlineMode === "true") hints.push("需要正版账号");
  if (onlineMode === "false") hints.push("离线模式，任意用户名可进");
  if ((props["white-list"] || "").trim().toLowerCase() === "true") {
    hints.push("需在白名单内");
  }
  return hints;
}

export function overviewModTitle(mod: {
  filename: string;
  title?: string | null;
  title_zh?: string | null;
  project_title?: string | null;
}) {
  const zh = (mod.title_zh || "").trim();
  if (zh && /[\u4e00-\u9fff]/.test(zh)) return zh;
  const official = (mod.title || "").trim() || (mod.project_title || "").trim();
  if (official) return official;
  return displayModName(mod);
}

export function formatDownloads(n?: number | null) {
  if (n == null || !Number.isFinite(n) || n < 0) return "";
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1)} 亿`;
  if (n >= 10_000) return `${(n / 10_000).toFixed(n >= 100_000 ? 0 : 1)} 万`;
  return String(n);
}

export function occupancyPercent(online: number, max: number) {
  if (!max || max <= 0) return 0;
  return Math.min(100, Math.round((Math.max(0, online) / max) * 100));
}

export type PingBadgeKind = "online" | "busy" | "offline";

export function pingBadge(
  pingOnline: boolean,
  powerState?: string | null,
  rconConnected?: boolean | null,
): { kind: PingBadgeKind; text: string } {
  if (pingOnline || rconConnected) return { kind: "online", text: "在线" };
  if (powerState === "starting") return { kind: "busy", text: "启动中" };
  if (powerState === "stopping") return { kind: "busy", text: "停止中" };
  return { kind: "offline", text: "离线" };
}

export function powerLabel(state: string | null | undefined) {
  switch (state) {
    case "running":
      return { color: "green", text: "运行中" };
    case "starting":
      return { color: "gold", text: "启动中" };
    case "stopping":
      return { color: "orange", text: "停止中" };
    case "offline":
    case "stopped":
      return { color: "default", text: "已停止" };
    default:
      return { color: "default", text: state || "未知" };
  }
}

export function loaderLabel(loader: string | null | undefined) {
  const hit = LOADERS.find((row) => row.value === loader);
  return hit?.label || loader || "—";
}

export function isServerLive(state: string | null | undefined) {
  return state === "running" || state === "starting";
}

export function formatUptime(ms: number) {
  const sec = Math.max(0, Math.floor(ms / 1000));
  const d = Math.floor(sec / 86400);
  const h = Math.floor((sec % 86400) / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (d) return `${d}d ${h}h ${m}m`;
  if (h) return `${h}h ${m}m ${s}s`;
  if (m) return `${m}m ${s}s`;
  return `${s}s`;
}

export function formatBytes(n: number) {
  if (!Number.isFinite(n) || n <= 0) return "0";
  const gb = n / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(2)} GB`;
  const mb = n / 1024 ** 2;
  if (mb >= 1) return `${mb.toFixed(2)} MB`;
  const kb = n / 1024;
  if (kb >= 1) return `${kb.toFixed(0)} KB`;
  return `${Math.round(n)} B`;
}

export function formatLimit(bytes: number) {
  return bytes > 0 ? formatBytes(bytes) : "∞";
}

const TEXT_EXTS = new Set([
  "txt",
  "log",
  "yml",
  "yaml",
  "toml",
  "json",
  "json5",
  "properties",
  "cfg",
  "conf",
  "config",
  "ini",
  "md",
  "xml",
  "csv",
  "sh",
  "bash",
  "bat",
  "ps1",
  "env",
  "lang",
  "mcmeta",
  "snbt",
  "js",
  "ts",
  "css",
  "html",
  "htm",
  "service",
  "ignore",
  "lock",
]);

const ARCHIVE_SUFFIXES = [
  ".zip",
  ".tar.gz",
  ".tgz",
  ".tar.xz",
  ".txz",
  ".tar.bz2",
  ".tbz2",
  ".7z",
];

export function joinMinecraftPath(directory: string, name: string) {
  const root = (directory || "/").replace(/\/+$/, "");
  const prefix = root === "" || root === "/" ? "" : root;
  return `${prefix}/${name}`;
}

export function parentMinecraftPath(directory: string) {
  if (!directory || directory === "/") return "/";
  const parts = directory.split("/").filter(Boolean);
  parts.pop();
  return parts.length ? `/${parts.join("/")}` : "/";
}

export function isMinecraftArchive(name: string) {
  const lower = name.toLowerCase();
  return ARCHIVE_SUFFIXES.some((ext) => lower.endsWith(ext));
}

export function isMinecraftTextFile(row: {
  name: string;
  is_file: boolean;
  is_symlink?: boolean;
  size: number;
  mimetype?: string | null;
}) {
  if (!row.is_file || row.is_symlink) return false;
  if (row.size > 1_048_576) return false;
  const mime = (row.mimetype || "").toLowerCase();
  if (
    mime.startsWith("text/") ||
    mime.includes("json") ||
    mime.includes("xml") ||
    mime.includes("javascript") ||
    mime === "application/x-sh" ||
    mime === "application/toml"
  ) {
    return true;
  }
  const dot = row.name.lastIndexOf(".");
  const ext = dot >= 0 ? row.name.slice(dot + 1).toLowerCase() : "";
  if (TEXT_EXTS.has(ext)) return true;
  if (!ext && row.size > 0 && row.size <= 64 * 1024) return true;
  return false;
}
