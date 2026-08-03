/** 前端缓存 Steam 库列表小图标 URL（按 AppID）；不缓存商店图。 */

import { fetchSteamAppIcon } from "@/api/client";

const STORAGE_KEY = "zhange.steamIconUrls.v2";
const CLIENT_ICON_MARKER = "steamcommunity/public/images/apps/";

type IconMap = Record<string, string>;

const inflight = new Map<string, Promise<string | null>>();
const failedIds = new Set<string>();

export function isSteamClientIconUrl(url?: string | null): boolean {
  return Boolean(url && url.includes(CLIENT_ICON_MARKER));
}

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

/** 仅写入库列表 client icon，并预热浏览器图片缓存。 */
export function rememberSteamIcons(
  entries: Iterable<{ appId?: string | null; iconUrl?: string | null }>,
) {
  const map = readMap();
  let changed = false;
  for (const e of entries) {
    const id = (e.appId || "").trim();
    const url = (e.iconUrl || "").trim();
    if (!id || !isSteamClientIconUrl(url)) continue;
    failedIds.delete(id);
    if (map[id] !== url) {
      map[id] = url;
      changed = true;
    }
    const img = new Image();
    img.referrerPolicy = "no-referrer";
    img.src = url;
  }
  if (changed) writeMap(map);
}

export function cachedSteamIcon(appId?: string | null): string | null {
  const id = (appId || "").trim();
  if (!id) return null;
  const url = readMap()[id] || null;
  return isSteamClientIconUrl(url) ? url : null;
}

export function resolveSteamIcon(
  appId?: string | null,
  iconUrl?: string | null,
): string | null {
  if (isSteamClientIconUrl(iconUrl)) return (iconUrl || "").trim();
  return cachedSteamIcon(appId);
}

/**
 * 异步拉取库列表 client icon（同 AppID 合并进行中请求）。
 * 已有缓存则立刻返回；真请求失败返回 null。
 */
export function loadSteamClientIcon(appId: string): Promise<string | null> {
  const id = (appId || "").trim();
  if (!id) return Promise.resolve(null);

  const hit = cachedSteamIcon(id);
  if (hit) return Promise.resolve(hit);
  if (failedIds.has(id)) return Promise.resolve(null);

  let pending = inflight.get(id);
  if (!pending) {
    pending = (async () => {
      try {
        const res = await fetchSteamAppIcon(id);
        const url = (res.icon_url || "").trim();
        if (!isSteamClientIconUrl(url)) {
          failedIds.add(id);
          return null;
        }
        rememberSteamIcons([{ appId: id, iconUrl: url }]);
        return url;
      } catch {
        failedIds.add(id);
        return null;
      } finally {
        inflight.delete(id);
      }
    })();
    inflight.set(id, pending);
  }
  return pending;
}
