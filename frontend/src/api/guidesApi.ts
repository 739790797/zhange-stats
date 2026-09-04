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

export type TarkovFullSync = components["schemas"]["TarkovFullSyncOut"];

export async function syncTarkovCatalog() {
  const { data } = await client.post<TarkovFullSync>(
    "/guides/tarkov/sync",
    {},
    { timeout: 300_000 },
  );
  return data;
}

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
  page?: number;
  pageSize?: number;
  layout?: "table" | "all";
}) {
  const q = (opts.q || "").trim();
  const trader = (opts.trader || "").trim();
  const map = (opts.map || "").trim();
  const layout = opts.layout === "all" ? "all" : undefined;
  const { data } = await client.get<TarkovTaskCatalog>("/guides/tarkov/tasks", {
    params: {
      ...(q ? { q } : {}),
      ...(trader ? { trader } : {}),
      ...(map ? { map } : {}),
      ...(layout ? { layout } : {}),
      ...(layout === "all"
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
  types?: string[];
  geometry?: boolean;
  ids?: string[];
}) {
  const q = (opts.q || "").trim();
  const trader = (opts.trader || "").trim();
  const types = (opts.types || []).filter(Boolean).join(",");
  const ids = (opts.ids || []).map((id) => id.trim()).filter(Boolean).join(",");
  const { data } = await client.get<TarkovRaidPrep>("/guides/tarkov/raid-prep", {
    params: {
      map: opts.map,
      ...(q ? { q } : {}),
      ...(trader ? { trader } : {}),
      ...(types ? { types } : {}),
      ...(opts.geometry === true ? { geometry: true } : {}),
      ...(ids ? { ids } : {}),
    },
    timeout: 120_000,
  });
  return data;
}

export async function fetchTarkovTaskDetail(taskId: string) {
  const { data } = await client.get<TarkovTaskDetail>(
    `/guides/tarkov/tasks/${encodeURIComponent(taskId)}`,
    { timeout: 120_000 },
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

export type TarkovMapCatalog = components["schemas"]["TarkovMapCatalogOut"];
export type TarkovMapListItem = components["schemas"]["TarkovMapListItemOut"];
export type TarkovMapDetail = components["schemas"]["TarkovMapDetailOut"];
export type TarkovMapLoot = components["schemas"]["TarkovMapLootOut"];
export type TarkovMapExtract = components["schemas"]["TarkovMapExtractOut"];
export type TarkovMapBoss = components["schemas"]["TarkovMapBossOut"];
export type TarkovMapSpawn = components["schemas"]["TarkovMapSpawnOut"];
export type TarkovMapLock = components["schemas"]["TarkovMapLockOut"];
export type TarkovMapHazard = components["schemas"]["TarkovMapHazardOut"];
export type TarkovMapSwitch = components["schemas"]["TarkovMapSwitchOut"];
export type TarkovMapStationaryWeapon =
  components["schemas"]["TarkovMapStationaryWeaponOut"];
export type TarkovMapBtrStop = components["schemas"]["TarkovMapBtrStopOut"];
export type TarkovMapLootContainer =
  components["schemas"]["TarkovMapLootContainerOut"];
export type TarkovMapLootLoose = components["schemas"]["TarkovMapLootLooseOut"];
export type TarkovMapPlace = components["schemas"]["TarkovMapPlaceOut"];
export type TarkovMapPlaceIn = components["schemas"]["TarkovMapPlaceIn"];
export type TarkovMapPlacePatch = components["schemas"]["TarkovMapPlacePatchIn"];
export type TarkovMapPlaces = components["schemas"]["TarkovMapPlacesOut"];
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
export type TarkovKeyPacks = components["schemas"]["TarkovKeyPacksOut"];
export type TarkovKeyPackMap = components["schemas"]["TarkovKeyPackMapOut"];
export type TarkovKeyPackKey = components["schemas"]["TarkovKeyPackKeyOut"];
export type TarkovKeyOwns = components["schemas"]["TarkovKeyOwnsOut"];
export type TarkovKeyOwn = components["schemas"]["TarkovKeyOwnOut"];

export async function fetchTarkovMaps() {
  const { data } = await client.get<TarkovMapCatalog>("/guides/tarkov/maps", {
    timeout: 120_000,
  });
  return data;
}

export async function fetchTarkovMapDetail(
  slug: string,
  opts?: { lootLoose?: boolean; lootContainers?: boolean },
) {
  const { data } = await client.get<TarkovMapDetail>(
    `/guides/tarkov/maps/${encodeURIComponent(slug)}`,
    {
      timeout: 120_000,
      params: {
        loot_loose: opts?.lootLoose ?? false,
        loot_containers: opts?.lootContainers ?? false,
      },
    },
  );
  return data;
}

export async function fetchTarkovMapLoot(
  slug: string,
  opts?: { lootLoose?: boolean; lootContainers?: boolean },
) {
  const { data } = await client.get<TarkovMapLoot>(
    `/guides/tarkov/maps/${encodeURIComponent(slug)}/loot`,
    {
      timeout: 120_000,
      params: {
        loot_loose: opts?.lootLoose ?? false,
        loot_containers: opts?.lootContainers ?? false,
      },
    },
  );
  return data;
}

export async function fetchTarkovMapPlaces(slug: string) {
  const { data } = await client.get<TarkovMapPlaces>(
    `/guides/tarkov/maps/${encodeURIComponent(slug)}/places`,
    { timeout: 30_000 },
  );
  return data;
}

export async function createTarkovMapPlace(slug: string, body: TarkovMapPlaceIn) {
  const { data } = await client.post<TarkovMapPlace>(
    `/guides/tarkov/maps/${encodeURIComponent(slug)}/places`,
    body,
    { timeout: 30_000 },
  );
  return data;
}

export async function importTarkovMapPlaces(
  slug: string,
  items: TarkovMapPlaceIn[],
) {
  const { data } = await client.post<TarkovMapPlaces>(
    `/guides/tarkov/maps/${encodeURIComponent(slug)}/places/import`,
    { items },
    { timeout: 30_000 },
  );
  return data;
}

export async function patchTarkovMapPlace(
  slug: string,
  placeId: number,
  body: TarkovMapPlacePatch,
) {
  const { data } = await client.patch<TarkovMapPlace>(
    `/guides/tarkov/maps/${encodeURIComponent(slug)}/places/${placeId}`,
    body,
    { timeout: 30_000 },
  );
  return data;
}

export async function deleteTarkovMapPlace(slug: string, placeId: number) {
  const { data } = await client.delete<TarkovMapPlaces>(
    `/guides/tarkov/maps/${encodeURIComponent(slug)}/places/${placeId}`,
    { timeout: 30_000 },
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

export async function fetchTarkovKeyPacks() {
  const { data } = await client.get<TarkovKeyPacks>("/guides/tarkov/key-packs", {
    timeout: 120_000,
  });
  return data;
}

export async function fetchTarkovKeyOwns() {
  const { data } = await client.get<TarkovKeyOwns>("/guides/tarkov/key-owns", {
    timeout: 30_000,
  });
  return data;
}

export async function mergeTarkovKeyOwns(itemIds: string[]) {
  const { data } = await client.put<TarkovKeyOwns>(
    "/guides/tarkov/key-owns",
    { item_ids: itemIds },
    { timeout: 30_000 },
  );
  return data;
}

export async function addTarkovKeyOwn(itemId: string) {
  const { data } = await client.put<TarkovKeyOwns>(
    `/guides/tarkov/key-owns/${encodeURIComponent(itemId)}`,
    {},
    { timeout: 30_000 },
  );
  return data;
}

export async function removeTarkovKeyOwn(itemId: string) {
  const { data } = await client.delete<TarkovKeyOwns>(
    `/guides/tarkov/key-owns/${encodeURIComponent(itemId)}`,
    { timeout: 30_000 },
  );
  return data;
}

export type TarkovTaskDones = components["schemas"]["TarkovTaskDonesOut"];

export async function fetchTarkovTaskDones() {
  const { data } = await client.get<TarkovTaskDones>("/guides/tarkov/task-dones", {
    timeout: 30_000,
  });
  return data;
}

/** 默认 merge：只补账号里没有的完成/进行中/小步骤，不会整表清空。replace 仅测试或显式快照。 */
export async function writeTarkovTaskDones(
  taskIds: string[],
  opts?: {
    replace?: boolean;
    startedIds?: string[];
    objectiveDones?: Array<{ task_id: string; objective_id: string }>;
  },
) {
  const { data } = await client.put<TarkovTaskDones>(
    "/guides/tarkov/task-dones",
    {
      task_ids: taskIds,
      replace: Boolean(opts?.replace),
      ...(opts?.startedIds !== undefined
        ? { started_ids: opts.startedIds }
        : {}),
      ...(opts?.objectiveDones !== undefined
        ? { objective_dones: opts.objectiveDones }
        : {}),
    },
    { timeout: 30_000 },
  );
  return data;
}

export async function addTarkovTaskObjectiveDone(
  taskId: string,
  objectiveId: string,
) {
  const { data } = await client.put<TarkovTaskDones>(
    `/guides/tarkov/task-dones/${encodeURIComponent(taskId)}/objectives/${encodeURIComponent(objectiveId)}`,
    {},
    { timeout: 30_000 },
  );
  return data;
}

export async function removeTarkovTaskObjectiveDone(
  taskId: string,
  objectiveId: string,
) {
  const { data } = await client.delete<TarkovTaskDones>(
    `/guides/tarkov/task-dones/${encodeURIComponent(taskId)}/objectives/${encodeURIComponent(objectiveId)}`,
    { timeout: 30_000 },
  );
  return data;
}

export async function fetchTarkovRaidLogs(opts?: {
  mapId?: string;
  limit?: number;
}) {
  const { data } = await client.get<TarkovRaidLogsList>("/guides/tarkov/raid-logs", {
    params: {
      ...(opts?.mapId ? { map_id: opts.mapId } : {}),
      limit: opts?.limit ?? 30,
    },
    timeout: 30_000,
  });
  return data;
}

export type TarkovRaidLogsList = components["schemas"]["TarkovRaidLogsOut"];
export type TarkovRaidLog = components["schemas"]["TarkovRaidLogOut"];

export type TarkovRaidPrepState =
  components["schemas"]["TarkovUserRaidPrepStateOut"];

export async function fetchTarkovRaidPrepState(map: string) {
  const { data } = await client.get<TarkovRaidPrepState>(
    "/guides/tarkov/raid-prep/state",
    { params: { map }, timeout: 30_000 },
  );
  return data;
}

export async function putTarkovRaidPrepState(
  map: string,
  body: {
    selected: string[];
    objective_dones?: Array<{ task_id: string; objective_id: string }>;
    key_brings?: string[];
  },
) {
  const { data } = await client.put<TarkovRaidPrepState>(
    "/guides/tarkov/raid-prep/state",
    {
      selected: body.selected,
      objective_dones: body.objective_dones ?? [],
      key_brings: body.key_brings ?? [],
    },
    { params: { map }, timeout: 30_000 },
  );
  return data;
}

export type TarkovRaidLogImport = components["schemas"]["TarkovRaidLogIn"];
export type TarkovRaidLogsImportResult =
  components["schemas"]["TarkovRaidLogsImportOut"];

export async function importTarkovRaidLogs(raids: TarkovRaidLogImport[]) {
  const { data } = await client.post<TarkovRaidLogsImportResult>(
    "/guides/tarkov/raid-logs",
    { raids },
    { timeout: 60_000 },
  );
  return data;
}

export type TarkovRaidRoomLobby = components["schemas"]["TarkovRaidRoomLobbyOut"];
export type TarkovRaidRoomLobbyItem =
  components["schemas"]["TarkovRaidRoomLobbyItemOut"];
export type TarkovRaidRoomMine = components["schemas"]["TarkovRaidRoomMineOut"];
export type TarkovRaidRoomDetail =
  components["schemas"]["TarkovRaidRoomDetailOut"];
export type TarkovRaidRoomMark = components["schemas"]["TarkovRaidRoomMarkOut"];
export type TarkovRaidRoomClaim = components["schemas"]["TarkovRaidRoomClaimOut"];
export type TarkovRaidRoomKeyBring =
  components["schemas"]["TarkovRaidRoomKeyBringOut"];
export type TarkovRaidRoomObjectiveDone =
  components["schemas"]["TarkovRaidRoomObjectiveDoneOut"];

const RAID_ROOMS = "/guides/tarkov/raid-rooms";

export async function fetchTarkovRaidRooms(
  gameMode?: string,
  opts?: { page?: number; pageSize?: number },
) {
  const { data } = await client.get<TarkovRaidRoomLobby>(RAID_ROOMS, {
    timeout: 30_000,
    params: {
      ...(gameMode ? { game_mode: gameMode } : {}),
      ...(opts?.page ? { page: opts.page } : {}),
      ...(opts?.pageSize ? { page_size: opts.pageSize } : {}),
    },
  });
  return data;
}

export async function fetchTarkovRaidRoomMine() {
  const { data } = await client.get<TarkovRaidRoomMine>(`${RAID_ROOMS}/mine`, {
    timeout: 30_000,
  });
  return data;
}

export async function createTarkovRaidRoom(opts?: {
  title?: string;
  password?: string;
  listed?: boolean;
  gameMode?: string;
}) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    RAID_ROOMS,
    {
      title: opts?.title || undefined,
      password: opts?.password || undefined,
      listed: opts?.listed ?? true,
      game_mode: opts?.gameMode || undefined,
    },
    {
      timeout: 30_000,
      params: opts?.gameMode ? { game_mode: opts.gameMode } : undefined,
    },
  );
  return data;
}

export async function setTarkovRaidRoomGameMode(
  publicId: string,
  gameMode: string,
) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/game-mode`,
    { game_mode: gameMode },
    { timeout: 30_000 },
  );
  return data;
}

export async function setTarkovRaidRoomMap(publicId: string, map: string) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/map`,
    { map },
    { timeout: 30_000 },
  );
  return data;
}

export async function fetchTarkovRaidRoom(publicId: string) {
  const { data } = await client.get<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}`,
    { timeout: 30_000 },
  );
  return data;
}

export async function joinTarkovRaidRoom(
  publicId: string,
  opts?: { gameMode?: string; password?: string },
) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/join`,
    {
      game_mode: opts?.gameMode || undefined,
      password: opts?.password || undefined,
    },
    { timeout: 30_000 },
  );
  return data;
}

export async function setTarkovRaidRoomPassword(
  publicId: string,
  password: string | null,
) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/password`,
    { password: password ?? "" },
    { timeout: 30_000 },
  );
  return data;
}

export async function putTarkovRaidRoomTaskProgress(
  publicId: string,
  body: { started_ids: string[]; done_ids: string[] },
) {
  const { data } = await client.put<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/task-progress`,
    body,
    { timeout: 30_000 },
  );
  return data;
}

export async function seedTarkovRaidRoomClaimsFromProgress(publicId: string) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/claims/from-progress`,
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

export async function resetTarkovRaidRoom(publicId: string) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/reset`,
    {},
    { timeout: 30_000 },
  );
  return data;
}

export async function removeTarkovRaidRoomMember(
  publicId: string,
  userId: number,
) {
  const { data } = await client.delete<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/members/${userId}`,
    { timeout: 30_000 },
  );
  return data;
}

export async function transferTarkovRaidRoomHost(
  publicId: string,
  userId: number,
) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/host`,
    { user_id: userId },
    { timeout: 30_000 },
  );
  return data;
}

export async function claimTarkovRaidRoomTask(
  publicId: string,
  taskId: string,
) {
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

export async function bringTarkovRaidRoomKey(publicId: string, itemId: string) {
  const { data } = await client.put<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/key-brings/${encodeURIComponent(itemId)}`,
    {},
    { timeout: 30_000 },
  );
  return data;
}

export async function unbringTarkovRaidRoomKey(publicId: string, itemId: string) {
  const { data } = await client.delete<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/key-brings/${encodeURIComponent(itemId)}`,
    { timeout: 30_000 },
  );
  return data;
}

export async function markTarkovRaidRoomObjectivesDone(
  publicId: string,
  items: { task_id: string; objective_id: string }[],
) {
  const { data } = await client.put<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/objective-dones`,
    { items },
    { timeout: 30_000 },
  );
  return data;
}

export async function markTarkovRaidRoomObjectiveDone(
  publicId: string,
  taskId: string,
  objectiveId: string,
) {
  const { data } = await client.put<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/objective-dones/${encodeURIComponent(taskId)}/${encodeURIComponent(objectiveId)}`,
    {},
    { timeout: 30_000 },
  );
  return data;
}

export async function unmarkTarkovRaidRoomObjectiveDone(
  publicId: string,
  taskId: string,
  objectiveId: string,
) {
  const { data } = await client.delete<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/objective-dones/${encodeURIComponent(taskId)}/${encodeURIComponent(objectiveId)}`,
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

export type TarkovGoonTracker = components["schemas"]["TarkovGoonTrackerOut"];

export async function fetchTarkovGoons() {
  const { data } = await client.get<TarkovGoonTracker>("/guides/tarkov/goons", {
    timeout: 20_000,
  });
  return data;
}

export function tarkovGoonsWsUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/guides/tarkov/goons/ws`;
}
