/** 前端缓存 Steam 图标 URL（按 AppID），避免重复依赖接口字段。 */

const STORAGE_KEY = "zhange.steamIconUrls.v1";

type IconMap = Record<string, string>;

function readMap(): IconMap {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    return parsed && typeof parsed === "object" ? (parsed as IconMap) : {};
  } catch {
    return {};
  }
}

function writeMap(map: IconMap) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    // quota / private mode
  }
}

/** 写入接口返回的图标 URL，并预热浏览器图片缓存。 */
export function rememberSteamIcons(
  entries: Iterable<{ appId?: string | null; iconUrl?: string | null }>,
) {
  const map = readMap();
  let changed = false;
  for (const e of entries) {
    const id = (e.appId || "").trim();
    const url = (e.iconUrl || "").trim();
    if (!id || !url) continue;
    if (map[id] !== url) {
      map[id] = url;
      changed = true;
    }
    // 预热 HTTP 缓存
    const img = new Image();
    img.referrerPolicy = "no-referrer";
    img.src = url;
  }
  if (changed) writeMap(map);
}

export function cachedSteamIcon(appId?: string | null): string | null {
  const id = (appId || "").trim();
  if (!id) return null;
  return readMap()[id] || null;
}

export function resolveSteamIcon(
  appId?: string | null,
  iconUrl?: string | null,
): string | null {
  const fromApi = (iconUrl || "").trim();
  if (fromApi) return fromApi;
  return cachedSteamIcon(appId);
}
