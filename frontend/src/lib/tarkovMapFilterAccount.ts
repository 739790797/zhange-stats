import {
  fetchTarkovMapFilters,
  saveTarkovMapFilters,
} from "@/api/guidesApi";
import {
  hasStoredTarkovMapViewerPrefs,
  loadTarkovMapViewerPrefs,
  parseTarkovMapViewerPrefs,
  type TarkovMapViewerPrefs,
} from "@/lib/tarkovMapViewerPrefs";

let pushTimer = 0;
let pending: TarkovMapViewerPrefs | null = null;

/** 账号上已有记录就用账号的；还没有、本机有，就把本机这份上传。用户已经改过则不要盖掉。 */
export async function pullAccountMapFilters(
  edited: () => boolean,
): Promise<TarkovMapViewerPrefs | null> {
  try {
    const row = await fetchTarkovMapFilters();
    if (edited()) return null;
    if (row.saved && row.prefs) {
      return parseTarkovMapViewerPrefs(JSON.stringify(row.prefs));
    }
    if (!edited() && hasStoredTarkovMapViewerPrefs()) {
      await saveTarkovMapFilters(loadTarkovMapViewerPrefs());
    }
  } catch {
    /* 未登录或网络失败时继续用本机记录 */
  }
  return null;
}

export function scheduleAccountMapFilters(prefs: TarkovMapViewerPrefs) {
  pending = prefs;
  window.clearTimeout(pushTimer);
  pushTimer = window.setTimeout(() => {
    const body = pending;
    pending = null;
    if (!body) return;
    void saveTarkovMapFilters(body).catch(() => undefined);
  }, 400);
}
