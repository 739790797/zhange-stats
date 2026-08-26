export const LOADERS = [
  { value: "fabric", label: "Fabric" },
  { value: "quilt", label: "Quilt" },
  { value: "forge", label: "Forge" },
  { value: "neoforge", label: "NeoForge" },
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
  if (hit) return hit.label;
  const extra: Record<string, string> = {
    paper: "Paper",
    purpur: "Purpur",
    spigot: "Spigot",
    bukkit: "Bukkit",
  };
  const key = (loader || "").trim().toLowerCase();
  return extra[key] || loader || "—";
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

export function normalizeMinecraftPath(path: string) {
  const parts = (path || "/").replace(/\\/g, "/").split("/").filter(Boolean);
  const out: string[] = [];
  for (const part of parts) {
    if (part === "." || part === "") continue;
    if (part === "..") {
      out.pop();
      continue;
    }
    out.push(part);
  }
  return out.length ? `/${out.join("/")}` : "/";
}

export function parentMinecraftPath(directory: string) {
  if (!directory || directory === "/") return "/";
  const parts = directory.split("/").filter(Boolean);
  parts.pop();
  return parts.length ? `/${parts.join("/")}` : "/";
}

export function isMinecraftPathWithin(root: string, path: string) {
  const base = normalizeMinecraftPath(root);
  const target = normalizeMinecraftPath(path);
  if (base === "/") return true;
  return target === base || target.startsWith(`${base}/`);
}

export function parentMinecraftPathWithin(root: string, directory: string) {
  const parent = parentMinecraftPath(directory);
  if (!isMinecraftPathWithin(root, parent)) return normalizeMinecraftPath(root);
  return parent;
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
