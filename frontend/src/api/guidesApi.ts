import { client } from "./http";
import type { components } from "./generated/schema";

export type TarkovAmmoCatalog = components["schemas"]["TarkovAmmoCatalogOut"];
export type TarkovAmmoItem = components["schemas"]["TarkovAmmoItemOut"];
export type TarkovAmmoSyncResult = components["schemas"]["TarkovAmmoSyncOut"];
export type TarkovGunCatalog = components["schemas"]["TarkovGunCatalogOut"];
export type TarkovGunItem = components["schemas"]["TarkovGunItemOut"];
export type TarkovGunSyncResult = components["schemas"]["TarkovGunSyncOut"];
export type TarkovItemsSyncResult = components["schemas"]["TarkovItemsSyncOut"];
export type TarkovCatalog = components["schemas"]["TarkovCatalogOut"];
export type TarkovCatalogItem = components["schemas"]["TarkovCatalogItemOut"];
export type TarkovItemDetail = components["schemas"]["TarkovItemDetailOut"];
export type TarkovTaskCatalog = components["schemas"]["TarkovTaskCatalogOut"];
export type TarkovTaskListItem = components["schemas"]["TarkovTaskListItemOut"];
export type TarkovTaskDetail = components["schemas"]["TarkovTaskDetailOut"];
export type TarkovTasksSyncResult = components["schemas"]["TarkovTasksSyncOut"];

export async function syncTarkovItems() {
  const { data } = await client.post<TarkovItemsSyncResult>(
    "/guides/tarkov/items/sync",
    {},
    { timeout: 120_000 },
  );
  return data;
}

export type TarkovAmmoDetail = components["schemas"]["TarkovAmmoDetailOut"];

export async function fetchTarkovAmmo() {
  const { data } = await client.get<TarkovAmmoCatalog>("/guides/tarkov/ammo", {
    timeout: 120_000,
  });
  return data;
}

export async function fetchTarkovAmmoDetail(itemId: string) {
  const { data } = await client.get<TarkovAmmoDetail>(
    `/guides/tarkov/ammo/${encodeURIComponent(itemId)}`,
    { timeout: 60_000 },
  );
  return data;
}

export async function syncTarkovAmmo() {
  const { data } = await client.post<TarkovAmmoSyncResult>(
    "/guides/tarkov/ammo/sync",
    {},
    { timeout: 120_000 },
  );
  return data;
}

export async function fetchTarkovGuns() {
  const { data } = await client.get<TarkovGunCatalog>("/guides/tarkov/guns", {
    timeout: 120_000,
  });
  return data;
}

export async function syncTarkovGuns() {
  const { data } = await client.post<TarkovGunSyncResult>(
    "/guides/tarkov/guns/sync",
    {},
    { timeout: 120_000 },
  );
  return data;
}

export async function fetchTarkovItemCatalog(opts: {
  categoryIds?: string[];
  types?: string[];
  q?: string;
  page?: number;
  pageSize?: number;
}) {
  const category_ids = (opts.categoryIds || []).filter(Boolean).join(",");
  const types = (opts.types || []).filter(Boolean).join(",");
  const q = (opts.q || "").trim();
  const { data } = await client.get<TarkovCatalog>("/guides/tarkov/items", {
    params: {
      ...(category_ids ? { category_ids } : {}),
      ...(types ? { types } : {}),
      ...(q ? { q } : {}),
      page: opts.page ?? 1,
      page_size: opts.pageSize ?? 50,
    },
    timeout: 60_000,
  });
  return data;
}

export async function fetchTarkovItemDetail(itemId: string) {
  const { data } = await client.get<TarkovItemDetail>(
    `/guides/tarkov/items/${encodeURIComponent(itemId)}`,
    { timeout: 60_000 },
  );
  return data;
}

export type TarkovSiteSearch = components["schemas"]["TarkovSiteSearchOut"];

export async function fetchTarkovSiteSearch(q: string) {
  const query = (q || "").trim();
  const { data } = await client.get<TarkovSiteSearch>("/guides/tarkov/search", {
    params: { q: query },
    timeout: 60_000,
  });
  return data;
}

export async function fetchTarkovTasks(opts: {
  q?: string;
  trader?: string;
  map?: string;
  kappa?: boolean;
  progress?: boolean;
  progressStatus?: string;
  page?: number;
  pageSize?: number;
}) {
  const q = (opts.q || "").trim();
  const trader = (opts.trader || "").trim();
  const map = (opts.map || "").trim();
  const progressStatus = (opts.progressStatus || "").trim();
  const { data } = await client.get<TarkovTaskCatalog>("/guides/tarkov/tasks", {
    params: {
      ...(q ? { q } : {}),
      ...(trader ? { trader } : {}),
      ...(map ? { map } : {}),
      ...(opts.kappa === true ? { kappa: true } : {}),
      ...(opts.progress === true ? { progress: true } : {}),
      ...(opts.progress === true && progressStatus
        ? { progress_status: progressStatus }
        : {}),
      page: opts.page ?? 1,
      page_size: opts.pageSize ?? 50,
    },
    timeout: 120_000,
  });
  return data;
}

export async function fetchTarkovTaskDetail(
  taskId: string,
  opts?: { progress?: boolean },
) {
  const { data } = await client.get<TarkovTaskDetail>(
    `/guides/tarkov/tasks/${encodeURIComponent(taskId)}`,
    {
      params: opts?.progress === true ? { progress: true } : {},
      timeout: 120_000,
    },
  );
  return data;
}

export async function syncTarkovTasks() {
  const { data } = await client.post<TarkovTasksSyncResult>(
    "/guides/tarkov/tasks/sync",
    {},
    { timeout: 180_000 },
  );
  return data;
}

export type TarkovTraderCatalog = components["schemas"]["TarkovTraderCatalogOut"];
export type TarkovTraderListItem = components["schemas"]["TarkovTraderListItemOut"];
export type TarkovTraderDetail = components["schemas"]["TarkovTraderDetailOut"];
export type TarkovTraderOffer = components["schemas"]["TarkovTraderOfferOut"];
export type TarkovTradersSyncResult = components["schemas"]["TarkovTradersSyncOut"];

export async function fetchTarkovTraders() {
  const { data } = await client.get<TarkovTraderCatalog>("/guides/tarkov/traders", {
    timeout: 180_000,
  });
  return data;
}

export async function fetchTarkovTraderDetail(
  slug: string,
  opts: {
    level?: number;
    q?: string;
    page?: number;
    pageSize?: number;
  } = {},
) {
  const q = (opts.q || "").trim();
  const { data } = await client.get<TarkovTraderDetail>(
    `/guides/tarkov/traders/${encodeURIComponent(slug)}`,
    {
      params: {
        ...(opts.level ? { level: opts.level } : {}),
        ...(q ? { q } : {}),
        page: opts.page ?? 1,
        page_size: opts.pageSize ?? 50,
      },
      timeout: 180_000,
    },
  );
  return data;
}

export async function syncTarkovTraders() {
  const { data } = await client.post<TarkovTradersSyncResult>(
    "/guides/tarkov/traders/sync",
    {},
    { timeout: 180_000 },
  );
  return data;
}

export type TarkovBossCatalog = components["schemas"]["TarkovBossCatalogOut"];
export type TarkovBossListItem = components["schemas"]["TarkovBossListItemOut"];
export type TarkovBossDetail = components["schemas"]["TarkovBossDetailOut"];
export type TarkovBossLoot = components["schemas"]["TarkovBossLootOut"];
export type TarkovBossesSyncResult = components["schemas"]["TarkovBossesSyncOut"];

export async function fetchTarkovBosses() {
  const { data } = await client.get<TarkovBossCatalog>("/guides/tarkov/bosses", {
    timeout: 180_000,
  });
  return data;
}

export async function fetchTarkovBossDetail(slug: string) {
  const { data } = await client.get<TarkovBossDetail>(
    `/guides/tarkov/bosses/${encodeURIComponent(slug)}`,
    { timeout: 180_000 },
  );
  return data;
}

export async function syncTarkovBosses() {
  const { data } = await client.post<TarkovBossesSyncResult>(
    "/guides/tarkov/bosses/sync",
    {},
    { timeout: 180_000 },
  );
  return data;
}

export type TarkovTrackerStatus = components["schemas"]["TarkovTrackerStatusOut"];

export async function fetchTarkovProgress() {
  const { data } = await client.get<TarkovTrackerStatus>("/guides/tarkov/progress", {
    timeout: 30_000,
  });
  return data;
}

export async function bindTarkovTrackerToken(token: string) {
  const { data } = await client.put<TarkovTrackerStatus>(
    "/guides/tarkov/progress/tracker-token",
    { token },
    { timeout: 30_000 },
  );
  return data;
}

export async function unbindTarkovTrackerToken() {
  const { data } = await client.delete<TarkovTrackerStatus>(
    "/guides/tarkov/progress/tracker-token",
    { timeout: 30_000 },
  );
  return data;
}

export async function syncTarkovProgress() {
  const { data } = await client.post<TarkovTrackerStatus>(
    "/guides/tarkov/progress/sync",
    {},
    { timeout: 30_000 },
  );
  return data;
}
