/** 离线 / 本地 PVE 没有 Location 时，手选地图挂截图坐标。 */

import {
  isRaidPrepAutoMapKind,
  normalizeRaidPrepMapId,
} from "@/lib/tarkovRaidPrep";

export const TARKOV_OFFLINE_MAP_STORAGE_KEY =
  "zhange.guides.tarkov.offlineMap.v1";
export const TARKOV_OFFLINE_MAP_EVENT = "zhange-tarkov-offline-map";

export function parseOfflineMapId(raw: unknown): string {
  return normalizeRaidPrepMapId(String(raw || "").trim());
}

export function loadOfflineMapId(): string {
  if (typeof window === "undefined") return "";
  try {
    return parseOfflineMapId(
      window.localStorage.getItem(TARKOV_OFFLINE_MAP_STORAGE_KEY),
    );
  } catch {
    return "";
  }
}

export function saveOfflineMapId(raw: string): string {
  const next = parseOfflineMapId(raw);
  if (typeof window === "undefined") return next;
  try {
    if (next) window.localStorage.setItem(TARKOV_OFFLINE_MAP_STORAGE_KEY, next);
    else window.localStorage.removeItem(TARKOV_OFFLINE_MAP_STORAGE_KEY);
    window.dispatchEvent(new Event(TARKOV_OFFLINE_MAP_EVENT));
  } catch {
    /* ignore quota / private mode */
  }
  return next;
}

/** 日志没地图、且正在离线战局 / 进图相位时，用用户手选的图。 */
export function resolveOfflineLogMapId(opts: {
  logMapId?: string | null;
  offlineMapId?: string | null;
  raidMode?: string | null;
  phaseKind?: string | null;
}): string {
  const log = parseOfflineMapId(opts.logMapId);
  if (log) return log;
  const offline = parseOfflineMapId(opts.offlineMapId);
  if (!offline) return "";
  const kind = String(opts.phaseKind || "").trim();
  if (kind === "raid_exited" || kind === "matching_aborted") return "";
  const raidMode = String(opts.raidMode || "").trim().toLowerCase();
  if (raidMode === "offline" || raidMode === "local") return offline;
  if (isRaidPrepAutoMapKind(kind)) return offline;
  return "";
}
