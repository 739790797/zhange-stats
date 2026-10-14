import { getTarkovGameMode } from "@/lib/tarkovGameMode";
import {
  ledgerIdsToClear,
  loadTabQuestEpoch,
  notifyTaskLedgerStale,
} from "@/lib/tarkovTaskTree";
import type { TarkovGameMode } from "@/lib/tarkovGameMode";
import { client } from "./http";
import type { components } from "./generated/schema";

export type TarkovAmmoCatalog = components["schemas"]["TarkovAmmoCatalogOut"];
export type TarkovAmmoItem = components["schemas"]["TarkovAmmoItemOut"];
export type TarkovGunCatalog = components["schemas"]["TarkovGunCatalogOut"];
export type TarkovGunItem = components["schemas"]["TarkovGunItemOut"];
export type TarkovWorkbenchGun = components["schemas"]["TarkovWorkbenchGunOut"];
export type TarkovWorkbenchCalculate = components["schemas"]["TarkovWorkbenchCalculateOut"];
export type TarkovWorkbenchAllowed = components["schemas"]["TarkovWorkbenchAllowedOut"];
export type TarkovWorkbenchPair = components["schemas"]["TarkovWorkbenchPairOut"];
export type TarkovWorkbenchSlotNode = components["schemas"]["TarkovWorkbenchSlotNodeOut"];
export type TarkovWorkbenchPart = components["schemas"]["TarkovWorkbenchPartOut"];
export type TarkovWorkbenchStats = components["schemas"]["TarkovWorkbenchStatsOut"];
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

export async function fetchTarkovWorkbenchGun(gunId: string) {
  const { data } = await client.get<TarkovWorkbenchGun>(
    `/guides/tarkov/workbench/guns/${encodeURIComponent(gunId)}`,
    { timeout: 120_000 },
  );
  return data;
}

export async function fetchTarkovWorkbenchAllowed(slotIds: string[]) {
  const { data } = await client.post<TarkovWorkbenchAllowed>(
    "/guides/tarkov/workbench/slots/allowed-items",
    { slot_ids: slotIds },
    { timeout: 60_000 },
  );
  return data;
}

export async function fetchTarkovWorkbenchCalculate(opts: {
  gunId: string;
  pairs: TarkovWorkbenchPair[];
  ammoId?: string | null;
}) {
  const { data } = await client.post<TarkovWorkbenchCalculate>(
    "/guides/tarkov/workbench/calculate",
    {
      gun_id: opts.gunId,
      pairs: opts.pairs,
      ammo_id: opts.ammoId || null,
    },
    { timeout: 60_000 },
  );
  return data;
}

export type TarkovWorkbenchCommunityBuild =
  components["schemas"]["TarkovWorkbenchCommunityBuildOut"];
export type TarkovWorkbenchCommunityBuilds =
  components["schemas"]["TarkovWorkbenchCommunityBuildsOut"];
export type TarkovWorkbenchGunsmithTasks =
  components["schemas"]["TarkovWorkbenchGunsmithTasksOut"];
export type TarkovWorkbenchGunsmithTask =
  components["schemas"]["TarkovWorkbenchGunsmithTaskOut"];
export type TarkovWorkbenchGunsmithSolve =
  components["schemas"]["TarkovWorkbenchGunsmithSolveOut"];

export async function fetchTarkovWorkbenchCommunityBuilds(gunId: string) {
  const { data } = await client.get<TarkovWorkbenchCommunityBuilds>(
    "/guides/tarkov/workbench/community-builds",
    { params: { gun_id: gunId }, timeout: 30_000 },
  );
  return data;
}

export async function fetchTarkovWorkbenchGunsmithTasks() {
  const { data } = await client.get<TarkovWorkbenchGunsmithTasks>(
    "/guides/tarkov/workbench/gunsmith-tasks",
    { timeout: 60_000 },
  );
  return data;
}

export async function fetchTarkovWorkbenchGunsmithSolve(opts: {
  taskId: string;
  objectiveId?: string | null;
  ammoId?: string | null;
}) {
  const { data } = await client.post<TarkovWorkbenchGunsmithSolve>(
    "/guides/tarkov/workbench/gunsmith-solve",
    {
      task_id: opts.taskId,
      objective_id: opts.objectiveId || null,
      ammo_id: opts.ammoId ?? null,
    },
    { timeout: 60_000 },
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

export async function fetchTarkovItemCatalogAll(opts: {
  categoryIds?: string[];
  types?: string[];
  q?: string;
}) {
  const { data } = await client.get<TarkovCatalog>("/guides/tarkov/items", {
    params: {
      ...((opts.categoryIds || []).filter(Boolean).length
        ? { category_ids: (opts.categoryIds || []).filter(Boolean).join(",") }
        : {}),
      ...((opts.types || []).filter(Boolean).length
        ? { types: (opts.types || []).filter(Boolean).join(",") }
        : {}),
      ...((opts.q || "").trim() ? { q: (opts.q || "").trim() } : {}),
      // 本地排序用：服务端一次给全量，不再并发拉几十页。
      layout: "all",
    },
    timeout: 120_000,
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

export async function fetchTarkovSiteSearch(
  q: string,
  opts?: { faction?: string },
) {
  const query = (q || "").trim();
  const faction = (opts?.faction || "").trim();
  const { data } = await client.get<TarkovSiteSearch>("/guides/tarkov/search", {
    params: {
      q: query,
      ...(faction ? { faction } : {}),
    },
    timeout: 60_000,
  });
  return data;
}

export async function fetchTarkovTasks(opts: {
  q?: string;
  trader?: string;
  map?: string;
  faction?: string;
  page?: number;
  pageSize?: number;
  layout?: "table" | "all";
}) {
  const q = (opts.q || "").trim();
  const trader = (opts.trader || "").trim();
  const map = (opts.map || "").trim();
  const faction = (opts.faction || "").trim();
  const layout = opts.layout === "all" ? "all" : undefined;
  const { data } = await client.get<TarkovTaskCatalog>("/guides/tarkov/tasks", {
    params: {
      ...(q ? { q } : {}),
      ...(trader ? { trader } : {}),
      ...(map ? { map } : {}),
      ...(faction ? { faction } : {}),
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
export type TarkovBossGearSlot = components["schemas"]["TarkovBossGearSlotOut"];
export type TarkovBossGearItem = components["schemas"]["TarkovBossGearItemOut"];

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
export type TarkovHideoutLevels = components["schemas"]["TarkovHideoutLevelsOut"];
export type TarkovProfile = components["schemas"]["TarkovProfileOut"];
export type TarkovProfileIn = components["schemas"]["TarkovProfileIn"];
export type TarkovBarter = components["schemas"]["TarkovBarterOut"];
export type TarkovCraft = components["schemas"]["TarkovCraftOut"];
export type TarkovCraftCatalog = components["schemas"]["TarkovCraftCatalogOut"];
export type TarkovKeyPacks = components["schemas"]["TarkovKeyPacksOut"];
export type TarkovKeyPackMap = components["schemas"]["TarkovKeyPackMapOut"];
export type TarkovKeyPackKey = components["schemas"]["TarkovKeyPackKeyOut"];
export type TarkovKeyOwns = components["schemas"]["TarkovKeyOwnsOut"];
export type TarkovKeyOwn = components["schemas"]["TarkovKeyOwnOut"];
export type TarkovCollection = components["schemas"]["TarkovCollectionOut"];
export type TarkovCollectionLayout = components["schemas"]["TarkovCollectionLayoutOut"];
export type TarkovCollectionLayoutIn = components["schemas"]["TarkovCollectionLayoutIn"];

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

export async function createTarkovMapPlace(slug: string, body: TarkovMapPlaceIn) {
  const { data } = await client.post<TarkovMapPlace>(
    `/guides/tarkov/maps/${encodeURIComponent(slug)}/places`,
    body,
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

export async function fetchTarkovHideoutLevels() {
  const { data } = await client.get<TarkovHideoutLevels>(
    "/guides/tarkov/hideout-levels",
    { timeout: 30_000 },
  );
  return data;
}

export async function setTarkovHideoutLevel(stationId: string, level: number) {
  const { data } = await client.put<TarkovHideoutLevels>(
    "/guides/tarkov/hideout-levels",
    { station_id: stationId, level },
    { timeout: 30_000 },
  );
  return data;
}

export async function fetchTarkovProfile() {
  const { data } = await client.get<TarkovProfile>("/guides/tarkov/profile", {
    timeout: 30_000,
  });
  return data;
}

export async function updateTarkovProfile(body: TarkovProfileIn) {
  const { data } = await client.put<TarkovProfile>(
    "/guides/tarkov/profile",
    body,
    { timeout: 30_000 },
  );
  return data;
}

export type TarkovMapFilters = {
  saved: boolean;
  prefs: Record<string, unknown> | null;
  updated_at?: string | null;
};

export async function fetchTarkovMapFilters() {
  const { data } = await client.get<TarkovMapFilters>(
    "/guides/tarkov/map-filters",
    { timeout: 30_000 },
  );
  return data;
}

export async function saveTarkovMapFilters(prefs: object) {
  const { data } = await client.put<TarkovMapFilters>(
    "/guides/tarkov/map-filters",
    { prefs },
    { timeout: 30_000 },
  );
  return data;
}

export async function fetchTarkovCrafts(opts?: {
  station?: string;
  q?: string;
  page?: number;
  pageSize?: number;
}) {
  const { data } = await client.get<TarkovCraftCatalog>("/guides/tarkov/crafts", {
    params: {
      station: opts?.station,
      q: opts?.q,
      page: opts?.page ?? 1,
      page_size: opts?.pageSize ?? 100,
    },
    timeout: 180_000,
  });
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

export async function fetchTarkovCollection() {
  const { data } = await client.get<TarkovCollection>(
    "/guides/tarkov/collection",
    { timeout: 120_000 },
  );
  return data;
}

export async function fetchTarkovCollectionLayout() {
  const { data } = await client.get<TarkovCollectionLayout>(
    "/guides/tarkov/collection-layout",
    { timeout: 30_000 },
  );
  return data;
}

export async function saveTarkovCollectionLayout(body: TarkovCollectionLayoutIn) {
  const { data } = await client.put<TarkovCollectionLayout>(
    "/guides/tarkov/collection-layout",
    body,
    { timeout: 30_000 },
  );
  return data;
}

export type TarkovTaskDones = components["schemas"]["TarkovTaskDonesOut"];
export type TarkovTaskResetIn = components["schemas"]["TarkovTaskResetIn"];

export async function fetchTarkovTaskDones() {
  const { data } = await client.get<TarkovTaskDones>("/guides/tarkov/task-dones", {
    timeout: 30_000,
  });
  return data;
}

/** 指定模式读账号进度账（同步中途切了 PVP/PVE 也读同步开始时那个模式）。 */
export async function fetchTarkovTaskDonesFor(gameMode: TarkovGameMode) {
  const { data } = await client.get<TarkovTaskDones>("/guides/tarkov/task-dones", {
    timeout: 30_000,
    params: { game_mode: gameMode },
  });
  return data;
}

/**
 * 批量写入带上本标签页内存账基于的 reset_epoch：清空 / 转生之后，
 * 别的标签页或设备还拿着旧账的写入会被服务端 409 拒掉，不会把旧进度并回来。
 * 本页还没和账号对过就不带；账号记过边界时服务端也会 409，促使本页先拉一遍账号。
 */
function currentLedgerEpoch(): number | undefined {
  return loadTabQuestEpoch(getTarkovGameMode());
}

/** 单任务 / 小步骤写入也带本页 epoch：清空之前的旧页面发来的勾选、取消同样被服务端 409 挡住。 */
function ledgerEpochParams(): { expect_epoch?: number } {
  const epoch = currentLedgerEpoch();
  return epoch !== undefined ? { expect_epoch: epoch } : {};
}

async function guardStaleLedger<T>(request: Promise<T>): Promise<T> {
  try {
    return await request;
  } catch (error) {
    if (isStaleLedgerError(error)) notifyTaskLedgerStale();
    throw error;
  }
}

function isStaleLedgerError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    (error as { response?: { status?: number } }).response?.status === 409
  );
}

/** 默认 merge：只补账号里没有的完成/进行中/小步骤，不会整表清空。replace 仅测试或显式快照。 */
async function writeTarkovTaskDones(
  taskIds: string[],
  opts?: {
    replace?: boolean;
    startedIds?: string[];
    failedIds?: string[];
    objectiveDones?: Array<{ task_id: string; objective_id: string }>;
  },
) {
  const epoch = currentLedgerEpoch();
  try {
    const { data } = await client.put<TarkovTaskDones>(
      "/guides/tarkov/task-dones",
      {
        task_ids: taskIds,
        replace: Boolean(opts?.replace),
        ...(epoch !== undefined ? { expect_epoch: epoch } : {}),
        ...(opts?.startedIds !== undefined
          ? { started_ids: opts.startedIds }
          : {}),
        ...(opts?.failedIds !== undefined ? { failed_ids: opts.failedIds } : {}),
        ...(opts?.objectiveDones !== undefined
          ? { objective_dones: opts.objectiveDones }
          : {}),
      },
      { timeout: 30_000 },
    );
    return data;
  } catch (error) {
    if (isStaleLedgerError(error)) notifyTaskLedgerStale();
    throw error;
  }
}

/** 清空进度：服务端清掉本模式任务账并记下清空时刻，之后任何设备同步都不会把清空前的任务写回。 */
export async function clearTarkovTaskProgress() {
  const { data } = await client.post<TarkovTaskDones>(
    "/guides/tarkov/task-dones/clear",
    {},
    { timeout: 30_000 },
  );
  return data;
}

/** 记下日志里当前模式的游戏 ProfileId（不动下限、不加 epoch）。 */
export async function recordTarkovTaskProfile(profileId: string, gameMode: TarkovGameMode) {
  const { data } = await client.put<TarkovTaskDones>(
    "/guides/tarkov/task-dones/profile",
    { profile_id: profileId },
    { timeout: 30_000, params: { game_mode: gameMode } },
  );
  return data;
}

/** 带日志的同步定下回放下限（只增不减），并整表替换该模式进度账。409 = 别处已清空 / 重置，要重拉账号。 */
export async function resetTarkovTaskProgress(
  body: TarkovTaskResetIn,
  gameMode: TarkovGameMode,
) {
  try {
    const { data } = await client.post<TarkovTaskDones>(
      "/guides/tarkov/task-dones/reset",
      body,
      // 模式随同步开始时定死：同步途中切了 PVP/PVE 也不能写到另一个模式
      { timeout: 30_000, params: { game_mode: gameMode } },
    );
    return data;
  } catch (error) {
    if (isStaleLedgerError(error)) notifyTaskLedgerStale();
    throw error;
  }
}

export async function writeTaskProgressLedger(
  next: {
    done: readonly string[];
    started: readonly string[];
    failed: readonly string[];
    objectives?: Array<{ task_id: string; objective_id: string }>;
  },
  prev?: {
    done?: readonly string[];
    started?: readonly string[];
    failed?: readonly string[];
  },
  opts?: { replace?: boolean },
) {
  if (opts?.replace) {
    return writeTarkovTaskDones([...next.done], {
      replace: true,
      startedIds: [...next.started],
      failedIds: [...next.failed],
      objectiveDones: next.objectives ?? [],
    });
  }
  for (const id of ledgerIdsToClear(prev || {}, next)) {
    await removeTarkovTaskDone(id);
  }
  return writeTarkovTaskDones([...next.done], {
    startedIds: [...next.started],
    failedIds: [...next.failed],
    ...(next.objectives !== undefined
      ? { objectiveDones: next.objectives }
      : {}),
  });
}

export async function removeTarkovTaskDone(taskId: string) {
  const { data } = await guardStaleLedger(
    client.delete<TarkovTaskDones>(
      `/guides/tarkov/task-dones/${encodeURIComponent(taskId)}`,
      { timeout: 30_000, params: ledgerEpochParams() },
    ),
  );
  return data;
}

export async function addTarkovTaskObjectiveDone(
  taskId: string,
  objectiveId: string,
) {
  const { data } = await guardStaleLedger(
    client.put<TarkovTaskDones>(
      `/guides/tarkov/task-dones/${encodeURIComponent(taskId)}/objectives/${encodeURIComponent(objectiveId)}`,
      {},
      { timeout: 30_000, params: ledgerEpochParams() },
    ),
  );
  return data;
}

export async function removeTarkovTaskObjectiveDone(
  taskId: string,
  objectiveId: string,
) {
  const { data } = await guardStaleLedger(
    client.delete<TarkovTaskDones>(
      `/guides/tarkov/task-dones/${encodeURIComponent(taskId)}/objectives/${encodeURIComponent(objectiveId)}`,
      { timeout: 30_000, params: ledgerEpochParams() },
    ),
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
type RaidRoomPresenceRow = { clients?: readonly string[] | null };

/** 在线端只走房间 WebSocket，HTTP 快照没有这个字段。 */
export type TarkovRaidRoomDetail = Omit<
  components["schemas"]["TarkovRaidRoomDetailOut"],
  "occupants" | "members"
> & {
  occupants?: (components["schemas"]["TarkovRaidRoomOccupantOut"] &
    RaidRoomPresenceRow)[];
  members?: (components["schemas"]["TarkovRaidRoomMemberOut"] &
    RaidRoomPresenceRow)[];
};
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

export async function addTarkovRaidRoomMark(
  publicId: string,
  body: {
    kind: "pin" | "line" | "stroke" | "text";
    floor?: string;
    x: number;
    z: number;
    x2?: number;
    z2?: number;
    points?: number[][];
    label?: string;
  },
) {
  const { data } = await client.post<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/marks`,
    body,
    { timeout: 30_000 },
  );
  return data;
}

export async function moveTarkovRaidRoomMark(
  publicId: string,
  markId: number,
  body: { x: number; z: number },
) {
  const { data } = await client.patch<TarkovRaidRoomDetail>(
    `${RAID_ROOMS}/${encodeURIComponent(publicId)}/marks/${markId}`,
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
