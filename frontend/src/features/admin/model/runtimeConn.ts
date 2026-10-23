/** 运行环境页把库 / Redis 连接串拆成字段，保存时再拼回 URL。 */

export type MysqlConn = {
  host: string;
  port: number;
  user: string;
  password: string;
  database: string;
};

export type RedisConn = {
  host: string;
  port: number;
  user: string;
  password: string;
  db: number;
  tls: boolean;
};

export const MYSQL_CONN_DEFAULTS: MysqlConn = {
  host: "127.0.0.1",
  port: 3306,
  user: "",
  password: "",
  database: "",
};

export const REDIS_CONN_DEFAULTS: RedisConn = {
  host: "",
  port: 6379,
  user: "",
  password: "",
  db: 0,
  tls: false,
};

function decodePart(value: string): string {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function stripHostBrackets(host: string): string {
  const h = host.trim();
  if (h.startsWith("[") && h.endsWith("]")) return h.slice(1, -1);
  return h;
}

function formatHostForUrl(host: string): string {
  const h = stripHostBrackets(host);
  if (!h) return "127.0.0.1";
  if (h.includes(":")) return `[${h}]`;
  return h;
}

function parsePort(raw: string, fallback: number): number {
  const n = Number(raw);
  if (!Number.isInteger(n) || n < 1 || n > 65535) return fallback;
  return n;
}

function asUrl(text: string): URL | null {
  try {
    return new URL(text);
  } catch {
    return null;
  }
}

export function parseMysqlUrl(url: string): MysqlConn {
  const text = url.trim();
  if (!text) return { ...MYSQL_CONN_DEFAULTS };
  const normalized = text.replace(/^mysql\+pymysql:\/\//i, "mysql://");
  const parsed = asUrl(normalized);
  if (!parsed) return { ...MYSQL_CONN_DEFAULTS };
  const database = decodePart(
    (parsed.pathname || "").replace(/^\/+/, "").split("/")[0] || "",
  );
  return {
    host: stripHostBrackets(parsed.hostname || MYSQL_CONN_DEFAULTS.host),
    port: parsePort(parsed.port, MYSQL_CONN_DEFAULTS.port),
    user: decodePart(parsed.username),
    password: decodePart(parsed.password),
    database,
  };
}

export function composeMysqlUrl(conn: MysqlConn): string {
  const user = encodeURIComponent(conn.user.trim());
  const password = encodeURIComponent(conn.password);
  const host = formatHostForUrl(conn.host || MYSQL_CONN_DEFAULTS.host);
  const port = parsePort(String(conn.port || ""), MYSQL_CONN_DEFAULTS.port);
  const database = conn.database.trim().replace(/^\/+/, "");
  return `mysql+pymysql://${user}:${password}@${host}:${port}/${database}`;
}

export function parseRedisUrl(url: string): RedisConn {
  const text = url.trim();
  if (!text) return { ...REDIS_CONN_DEFAULTS };
  const parsed = asUrl(text);
  if (!parsed) return { ...REDIS_CONN_DEFAULTS };
  const scheme = parsed.protocol.replace(/:$/, "").toLowerCase();
  if (scheme !== "redis" && scheme !== "rediss") return { ...REDIS_CONN_DEFAULTS };
  const dbRaw = (parsed.pathname || "").replace(/^\/+/, "").split("/")[0] || "";
  const dbNum = dbRaw === "" ? 0 : Number(dbRaw);
  return {
    host: stripHostBrackets(parsed.hostname || ""),
    port: parsePort(parsed.port, REDIS_CONN_DEFAULTS.port),
    user: decodePart(parsed.username),
    password: decodePart(parsed.password),
    db: Number.isInteger(dbNum) && dbNum >= 0 ? dbNum : 0,
    tls: scheme === "rediss",
  };
}

function redisAuthPrefix(user: string, password: string): string {
  const u = user.trim();
  if (!u && !password) return "";
  if (!u) return `:${encodeURIComponent(password)}@`;
  if (!password) return `${encodeURIComponent(u)}@`;
  return `${encodeURIComponent(u)}:${encodeURIComponent(password)}@`;
}

export function composeRedisUrl(conn: RedisConn): string {
  const host = conn.host.trim();
  if (!host) return "";
  const scheme = conn.tls ? "rediss" : "redis";
  const port = parsePort(String(conn.port || ""), REDIS_CONN_DEFAULTS.port);
  const db = Number.isInteger(conn.db) && conn.db >= 0 ? conn.db : 0;
  return `${scheme}://${redisAuthPrefix(conn.user, conn.password)}${formatHostForUrl(host)}:${port}/${db}`;
}
