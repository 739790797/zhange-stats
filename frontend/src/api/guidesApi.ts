import { client } from "./http";
import type { components } from "./generated/schema";

export type TarkovAmmoCatalog = components["schemas"]["TarkovAmmoCatalogOut"];
export type TarkovAmmoItem = components["schemas"]["TarkovAmmoItemOut"];
export type TarkovGunCatalog = components["schemas"]["TarkovGunCatalogOut"];
export type TarkovGunItem = components["schemas"]["TarkovGunItemOut"];
export type TarkovCatalog = components["schemas"]["TarkovCatalogOut"];
export type TarkovCatalogItem = components["schemas"]["TarkovCatalogItemOut"];
export type TarkovItemDetail = components["schemas"]["TarkovItemDetailOut"];
export type TarkovTaskCatalog = components["schemas"]["TarkovTaskCatalogOut"];
export type TarkovTaskListItem = components["schemas"]["TarkovTaskListItemOut"];
export type TarkovTaskDetail = components["schemas"]["TarkovTaskDetailOut"];

export async function fetchTarkovAmmo() {
  const { data } = await client.get<TarkovAmmoCatalog>("/guides/tarkov/ammo", {
    timeout: 120_000,
  });
  return data;
}

export async function fetchTarkovGuns() {
  const { data } = await client.get<TarkovGunCatalog>("/guides/tarkov/guns", {
    timeout: 120_000,
  });
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
  layout?: "table" | "chain";
}) {
  const q = (opts.q || "").trim();
  const trader = (opts.trader || "").trim();
  const map = (opts.map || "").trim();
  const progressStatus = (opts.progressStatus || "").trim();
  const layout = opts.layout === "chain" ? "chain" : undefined;
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
      ...(layout ? { layout } : {}),
      ...(layout === "chain"
        ? {}
        : {
            page: opts.page ?? 1,
            page_size: opts.pageSize ?? 50,
          }),
    },
    timeout: 120_000,
  });
  return data;
}

export type TarkovRaidPrep = components["schemas"]["TarkovRaidPrepOut"];
export type TarkovRaidPrepTask = components["schemas"]["TarkovRaidPrepTaskOut"];

export async function fetchTarkovRaidPrep(opts: {
  map: string;
  q?: string;
  trader?: string;
  kappa?: boolean;
  types?: string[];
  progress?: boolean;
  progressStatus?: string;
  geometry?: boolean;
  ids?: string[];
}) {
  const q = (opts.q || "").trim();
  const trader = (opts.trader || "").trim();
  const types = (opts.types || []).filter(Boolean).join(",");
  const progressStatus = (opts.progressStatus || "").trim();
  const ids = (opts.ids || []).map((id) => id.trim()).filter(Boolean).join(",");
  const { data } = await client.get<TarkovRaidPrep>("/guides/tarkov/raid-prep", {
    params: {
      map: opts.map,
      ...(q ? { q } : {}),
      ...(trader ? { trader } : {}),
      ...(opts.kappa === true ? { kappa: true } : {}),
      ...(types ? { types } : {}),
      ...(opts.progress === true ? { progress: true } : {}),
      ...(opts.progress === true && progressStatus
        ? { progress_status: progressStatus }
        : {}),
      ...(opts.geometry === true ? { geometry: true } : {}),
      ...(ids ? { ids } : {}),
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

export type TarkovTraderCatalog = components["schemas"]["TarkovTraderCatalogOut"];
export type TarkovTraderListItem = components["schemas"]["TarkovTraderListItemOut"];
export type TarkovTraderDetail = components["schemas"]["TarkovTraderDetailOut"];
export type TarkovTraderOffer = components["schemas"]["TarkovTraderOfferOut"];

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

export type TarkovBossCatalog = components["schemas"]["TarkovBossCatalogOut"];
export type TarkovBossListItem = components["schemas"]["TarkovBossListItemOut"];
export type TarkovBossDetail = components["schemas"]["TarkovBossDetailOut"];
export type TarkovBossLoot = components["schemas"]["TarkovBossLootOut"];

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

export type TarkovMapCatalog = components["schemas"]["TarkovMapCatalogOut"];
export type TarkovMapListItem = components["schemas"]["TarkovMapListItemOut"];
export type TarkovMapDetail = components["schemas"]["TarkovMapDetailOut"];
export type TarkovMapExtract = components["schemas"]["TarkovMapExtractOut"];
export type TarkovMapBoss = components["schemas"]["TarkovMapBossOut"];
export type TarkovMapSpawn = components["schemas"]["TarkovMapSpawnOut"];
export type TarkovHideoutCatalog = components["schemas"]["TarkovHideoutCatalogOut"];
export type TarkovHideoutStation = components["schemas"]["TarkovHideoutStationOut"];
export type TarkovHideoutLevel = components["schemas"]["TarkovHideoutLevelOut"];
export type TarkovHideoutDetail = components["schemas"]["TarkovHideoutDetailOut"];
export type TarkovBarterCatalog = components["schemas"]["TarkovBarterCatalogOut"];
export type TarkovBarter = components["schemas"]["TarkovBarterOut"];
export type TarkovCraftCatalog = components["schemas"]["TarkovCraftCatalogOut"];
export type TarkovCraft = components["schemas"]["TarkovCraftOut"];
export type TarkovLootTierCatalog = components["schemas"]["TarkovLootTierCatalogOut"];
export type TarkovLootTierItem = components["schemas"]["TarkovLootTierItemOut"];

export async function fetchTarkovMaps() {
  const { data } = await client.get<TarkovMapCatalog>("/guides/tarkov/maps", {
    timeout: 120_000,
  });
  return data;
}

export async function fetchTarkovMapDetail(slug: string) {
  const { data } = await client.get<TarkovMapDetail>(
    `/guides/tarkov/maps/${encodeURIComponent(slug)}`,
    { timeout: 120_000 },
  );
  return data;
}

export async function fetchTarkovHideout() {
  const { data } = await client.get<TarkovHideoutCatalog>(
    "/guides/tarkov/hideout",
    { timeout: 180_000 },
  );
  return data;
}

export async function fetchTarkovHideoutStation(slug: string) {
  const { data } = await client.get<TarkovHideoutDetail>(
    `/guides/tarkov/hideout/${encodeURIComponent(slug)}`,
    { timeout: 180_000 },
  );
  return data;
}

export async function fetchTarkovBarters(opts: {
  q?: string;
  trader?: string;
  page?: number;
  pageSize?: number;
} = {}) {
  const q = (opts.q || "").trim();
  const trader = (opts.trader || "").trim();
  const { data } = await client.get<TarkovBarterCatalog>("/guides/tarkov/barters", {
    params: {
      ...(q ? { q } : {}),
      ...(trader ? { trader } : {}),
      page: opts.page ?? 1,
      page_size: opts.pageSize ?? 50,
    },
    timeout: 180_000,
  });
  return data;
}

export async function fetchTarkovCrafts(opts: {
  q?: string;
  station?: string;
  page?: number;
  pageSize?: number;
} = {}) {
  const q = (opts.q || "").trim();
  const station = (opts.station || "").trim();
  const { data } = await client.get<TarkovCraftCatalog>("/guides/tarkov/crafts", {
    params: {
      ...(q ? { q } : {}),
      ...(station ? { station } : {}),
      page: opts.page ?? 1,
      page_size: opts.pageSize ?? 50,
    },
    timeout: 180_000,
  });
  return data;
}

export async function fetchTarkovLootTiers(opts: {
  q?: string;
  tier?: string;
  page?: number;
  pageSize?: number;
} = {}) {
  const q = (opts.q || "").trim();
  const tier = (opts.tier || "").trim();
  const { data } = await client.get<TarkovLootTierCatalog>(
    "/guides/tarkov/loot-tiers",
    {
      params: {
        ...(q ? { q } : {}),
        ...(tier ? { tier } : {}),
        page: opts.page ?? 1,
        page_size: opts.pageSize ?? 100,
      },
      timeout: 180_000,
    },
  );
  return data;
}

export type TarkovRaidRoomLobby = components["schemas"]["TarkovRaidRoomLobbyOut"];
export type TarkovRaidRoomLobbyItem =
  components["schemas"]["TarkovRaidRoomLobbyItemOut"];
export type TarkovRaidRoomDetail =
  components["schemas"]["TarkovRaidRoomDetailOut"];
export type TarkovRaidRoomMark = components["schemas"]["TarkovRaidRoomMarkOut"];
export type TarkovRaidRoomClaim = components["schemas"]["TarkovRaidRoomClaimOut"];

const RAID_ROOMS = "/guides/tarkov/raid-rooms";

export async function fetchTarkovRaidRooms(map?: string, mine = true) {
  const slug = (map || "").trim();
  const { data } = await client.get<TarkovRaidRoomLobby>(RAID_ROOMS, {
    params: { ...(slug ? { map: slug } : {}), mine },
    timeout: 30_000,
  });
  return data;
}

export async function createTarkovRaidRoom(body: {
  map: string;
  title?: string;
}) {
  const { data } = await client.post<TarkovRaidRoomDetail>(RAID_ROOMS, body, {
    timeout: 30_000,
  });
  return data;
}

export async function fetchTarkovRaidRoom(publicId: string) {
  const { data } = await client.get<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}`,
    { timeout: 30_000 },
  );
  return data;
}

export async function joinTarkovRaidRoom(publicId: string) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/join`,
    {},
    { timeout: 30_000 },
  );
  return data;
}

export async function leaveTarkovRaidRoom(publicId: string) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/leave`,
    {},
    { timeout: 30_000 },
  );
  return data;
}

export async function closeTarkovRaidRoom(publicId: string) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/close`,
    {},
    { timeout: 30_000 },
  );
  return data;
}

export async function claimTarkovRaidRoomTask(publicId: string, taskId: string) {
  const { data } = await client.put<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/claims/${encodeURIComponent(taskId)}`,
    {},
    { timeout: 30_000 },
  );
  return data;
}

export async function claimTarkovRaidRoomTasks(
  publicId: string,
  taskIds: string[],
) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/claims`,
    { task_ids: taskIds },
    { timeout: 30_000 },
  );
  return data;
}

export async function unclaimTarkovRaidRoomTask(
  publicId: string,
  taskId: string,
) {
  const { data } = await client.delete<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/claims/${encodeURIComponent(taskId)}`,
    { timeout: 30_000 },
  );
  return data;
}

export async function addTarkovRaidRoomMark(
  publicId: string,
  body: {
    kind: "pin" | "line" | "stroke";
    floor?: string;
    x: number;
    z: number;
    x2?: number;
    z2?: number;
    points?: number[][];
  },
) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/marks`,
    body,
    { timeout: 30_000 },
  );
  return data;
}

export async function removeTarkovRaidRoomMark(publicId: string, markId: number) {
  const { data } = await client.delete<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/marks/${markId}`,
    { timeout: 30_000 },
  );
  return data;
}

export async function undoTarkovRaidRoomMark(publicId: string) {
  const { data } = await client.delete<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/marks/undo`,
    { timeout: 30_000 },
  );
  return data;
}

export async function clearTarkovRaidRoomMarks(publicId: string) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/marks/clear`,
    {},
    { timeout: 30_000 },
  );
  return data;
}

export function tarkovRaidRoomWsUrl(publicId: string) {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/guides/tarkov/raid-rooms/${encodeURIComponent(publicId)}/ws`;
}
