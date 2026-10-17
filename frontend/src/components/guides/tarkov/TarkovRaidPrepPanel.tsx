import { Alert, Spin, message } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addTarkovKeyOwn,
  fetchTarkovKeyOwns,
  fetchTarkovMapDetail,
  fetchTarkovRaidLogs,
  fetchTarkovRaidPrep,
  fetchTarkovRaidPrepState,
  fetchTarkovTaskDones,
  putTarkovRaidPrepState,
  removeTarkovKeyOwn,
} from "@/api/guidesApi";
import { apiError } from "@/lib/apiError";
import { useTarkovGameMode } from "@/lib/tarkovGameMode";
import { useTarkovPmcFaction } from "@/lib/tarkovPmcFaction";
import { mergeRaidPrepGuideTasks } from "@/lib/eftarkovGuide";
import { TARKOV_HOME_PATH } from "@/lib/tarkovHomeNav";
import {
  RAID_PREP_MAX_SELECTED,
  clipRaidPrepStateObjectiveDones,
  buildRaidPrepOverlays,
  colorForTaskIndex,
  filterRaidPrepRows,
  groupRaidPrepRowsByProgress,
  hydrateRaidPrepCatalogRows,
  normalizeRaidPrepMapId,
  raidPrepAutoSwitchMapId,
  objectiveDonesToSkipMap,
  parseCsvParam,
  pinSelectedRaidPrepRows,
  planRaidPrepTaskProgressSync,
  raidPrepMapOptions,
  raidPrepObjectiveDoneScope,
  raidPrepObjectiveDoneLegacyScopes,
  raidPrepSkipMapForViewer,
  readRaidPrepObjectiveDoneWithLegacy,
  raidPrepSkippedIds,
  selectedTasksFromCatalog,
  serializeSelectedIds,
  settleRaidPrepSelection,
  skipMapToObjectiveDones,
  useRaidPrepObjectiveDone,
} from "@/lib/tarkovRaidPrep";
import { applyTarkovKeyOwnsCache } from "@/lib/tarkovKeyPacks";
import {
  mergeObjectivePairs,
  mergeSkipMapsIfChanged,
  sameRaidPrepStateBody,
  type RaidPrepStateBody,
} from "@/lib/tarkovObjectivePairs";
import { useTarkovRaidTaskActions } from "@/lib/useTarkovRaidTaskActions";
import {
  buildSoloRaidRoomDetail,
  formatRaidRoomLiveStatus,
  keyOwnsForUser,
  overlayRaidRoomLocalPhase,
  raidRoomLiveStatus,
  shouldSuppressLocalPlayerFix,
  SOLO_RAID_ROOM_PUBLIC_ID,
} from "@/lib/tarkovRaidRooms";
import {
  TARKOV_TASK_PROGRESS_EVENT,
  type TarkovTaskProgressDetail,
} from "@/lib/tarkovLiveWatch";
import { TarkovLogSyncRangeModal } from "@/components/guides/tarkov/TarkovLogSyncRangeModal";
import { useTarkovLogSyncDialog } from "@/lib/useTarkovLogSyncDialog";
import { logMapLabel } from "@/lib/tarkovGameLogs";
import {
  useTarkovLastLogMapId,
  useTarkovLastLogPhase,
} from "@/lib/useTarkovLiveWatch";
import { useTarkovRaidDockOpen } from "@/lib/tarkovRaidDockPrefs";
import { useRaidPrepGeometry } from "@/lib/useRaidPrepGeometry";
import {
  loadTaskStartedIds,
  resolveAccountTaskProgress,
} from "@/lib/tarkovTaskTree";
import { TarkovRaidPrepFilters, TarkovShotDirButton } from "@/components/guides/tarkov/TarkovRaidPrepFilters";
import { TarkovRaidPrepTaskGroups } from "@/components/guides/tarkov/TarkovRaidPrepTaskGroups";
import { TarkovRaidPrepEntryModal } from "@/components/guides/tarkov/TarkovRaidPrepEntryModal";
import { TarkovRaidPrepSummary } from "@/components/guides/tarkov/TarkovRaidPrepSummary";
import { TarkovRaidPrepGuideOverview } from "@/components/guides/tarkov/TarkovRaidPrepGuideOverview";
import { TarkovGoonSightingHint } from "@/components/guides/tarkov/TarkovGoonTrackerBanner";
import { TarkovRaidPrepTaskCard } from "@/components/guides/tarkov/TarkovRaidPrepTaskCard";
import { TarkovRaidMemberStrip } from "@/components/guides/tarkov/TarkovRaidMemberStrip";
import { TarkovRaidSessionMap } from "@/components/guides/tarkov/TarkovRaidSessionMap";
import { TarkovRaidWorkspace } from "@/components/guides/tarkov/TarkovRaidWorkspace";
import { useAuthStore } from "@/stores/authStore";
import styles from "./TarkovRaidPrepPanel.module.css";

export function TarkovRaidPrepPanel() {
  const gameMode = useTarkovGameMode();
  const { faction } = useTarkovPmcFaction();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const me = useAuthStore((s) => s.user);
  const [searchParams, setSearchParams] = useSearchParams();
  const searchParamsRef = useRef(searchParams);
  searchParamsRef.current = searchParams;
  const mapId = normalizeRaidPrepMapId(searchParams.get("map") || "");
  const q = (searchParams.get("q") || "").trim();
  // 依赖原始串：每次渲染都新建数组会让下面 700ms 落盘定时器整轮重启（游戏写日志时 2~3s 一次 PUT）。
  const selParam = searchParams.get("sel");
  const selected = useMemo(() => parseCsvParam(selParam), [selParam]);
  const [keyword, setKeyword] = useState(q);
  const [changeMapOpen, setChangeMapOpen] = useState(false);
  const [dockOpen, setDockOpen] = useTarkovRaidDockOpen();
  const objDoneScope = raidPrepObjectiveDoneScope(mapId, gameMode, me?.id);
  const objDoneLegacy = useMemo(
    () => raidPrepObjectiveDoneLegacyScopes(mapId),
    [mapId],
  );
  const [objDone, toggleObjDoneLocal, replaceObjDone] = useRaidPrepObjectiveDone(
    objDoneScope,
    objDoneLegacy,
  );
  const [keyBringIds, setKeyBringIds] = useState<string[]>([]);
  const lastLogMapId = useTarkovLastLogMapId();
  const lastLogPhase = useTarkovLastLogPhase();
  const logSync = useTarkovLogSyncDialog();
  const autoMapSigRef = useRef("");
  const [progressTick, setProgressTick] = useState(0);
  const hydratedKeyRef = useRef("");
  const onUserObjectiveToggleRef = useRef<
    (taskId: string, objectiveId: string, checked: boolean) => void
  >(() => {});
  /** 用户刚改过步骤时加一，让还没发出的 700ms 存档不要把旧勾选写回去。 */
  const objectiveSaveGenRef = useRef(0);
  const persistReadyRef = useRef(false);
  // 每张图最后一次写成功的负载：来回切图时同样的内容不再重写。
  const lastSavedRef = useRef(new Map<string, RaidPrepStateBody>());
  const [persistTick, setPersistTick] = useState(0);
  const ownsQuery = useQuery({
    queryKey: ["guides-tarkov-key-owns"],
    queryFn: fetchTarkovKeyOwns,
    staleTime: 60_000,
    enabled: Boolean(me),
  });
  const taskDonesQuery = useQuery({
    queryKey: ["guides-tarkov-task-dones", gameMode],
    queryFn: fetchTarkovTaskDones,
    staleTime: 30_000,
    enabled: Boolean(me),
  });
  const stateQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep-state", gameMode, mapId],
    queryFn: () => fetchTarkovRaidPrepState(mapId),
    enabled: Boolean(mapId && me),
    staleTime: 30_000,
  });
  const logsQuery = useQuery({
    queryKey: ["guides-tarkov-raid-logs", mapId],
    queryFn: () => fetchTarkovRaidLogs({ mapId, limit: 8 }),
    enabled: Boolean(mapId && me),
    staleTime: 30_000,
  });
  // 每次变化只解析一次账号进度账（内部要读 6 遍 localStorage）；下面都从这一份派生。
  const accountProgress = useMemo(() => {
    void progressTick;
    return resolveAccountTaskProgress(taskDonesQuery.data, gameMode);
  }, [gameMode, progressTick, taskDonesQuery.data]);
  const doneTaskIds = accountProgress.done;
  const startedTaskIds = accountProgress.started;
  const doneTaskSet = useMemo(() => new Set(doneTaskIds), [doneTaskIds]);
  const startedTaskSet = useMemo(() => new Set(startedTaskIds), [startedTaskIds]);
  const objDoneView = useMemo(
    () => raidPrepSkipMapForViewer(objDone, accountProgress.objectives),
    [accountProgress.objectives, objDone],
  );
  const myName = (me?.display_name || me?.username || "").trim() || (me ? `用户${me.id}` : "");
  const keyOwns = useMemo(
    () =>
      keyOwnsForUser(ownsQuery.data?.item_ids, me ? { userId: me.id, name: myName } : null),
    [ownsQuery.data?.item_ids, me, myName],
  );
  const qRef = useRef(q);

  useEffect(() => {
    setKeyword(q);
    qRef.current = q;
  }, [q]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const next = keyword.trim();
      if (qRef.current === next) return;
      qRef.current = next;
      const params = new URLSearchParams(searchParamsRef.current);
      if (next) params.set("q", next);
      else params.delete("q");
      setSearchParams(params, { replace: true });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [keyword, setSearchParams]);

  useEffect(() => {
    if (!searchParams.get("types")) return;
    const next = new URLSearchParams(searchParams);
    next.delete("types");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const patchParams = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      const next = new URLSearchParams(searchParamsRef.current);
      mutate(next);
      setSearchParams(next, { replace: true });
    },
    [setSearchParams],
  );

  const setMap = useCallback((id: string) => {
    patchParams((params) => {
      if (id) params.set("map", id);
      else params.delete("map");
      params.delete("sel");
      params.delete("q");
      params.delete("trader");
    });
    setKeyword("");
  }, [patchParams]);

  const autoMapId = raidPrepAutoSwitchMapId({
    currentMapId: mapId,
    logMapId: lastLogPhase?.mapId || lastLogMapId,
    phaseKind: lastLogPhase?.kind,
    fillEmpty: false,
  });
  useEffect(() => {
    if (!autoMapId) return;
    const sig = `${autoMapId}:${lastLogPhase?.raidId || ""}:${lastLogPhase?.kind || "idle"}`;
    if (autoMapSigRef.current === sig) return;
    autoMapSigRef.current = sig;
    setMap(autoMapId);
    message.info(`已按游戏日志切换到${logMapLabel(autoMapId)}`);
  }, [autoMapId, lastLogPhase?.kind, lastLogPhase?.raidId, setMap]);

  /** 目录不含区轮廓；筛选在前端。 */
  const prepQuery = useQuery({
    queryKey: ["guides-tarkov-raid-prep", gameMode, mapId],
    queryFn: () => fetchTarkovRaidPrep({ map: mapId }),
    enabled: Boolean(mapId),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const mapQuery = useQuery({
    queryKey: ["guides-tarkov-map", gameMode, mapId],
    queryFn: () => fetchTarkovMapDetail(mapId),
    enabled: Boolean(mapId),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const geometry = useRaidPrepGeometry(mapId, selected);

  const catalog = useMemo(
    () => prepQuery.data?.items ?? [],
    [prepQuery.data],
  );
  const catalogRich = useMemo(
    () => hydrateRaidPrepCatalogRows(catalog, geometry.byId),
    [catalog, geometry.byId],
  );
  const overlayTasks = geometry.items;
  const onUserObjectiveToggle = useCallback(
    (taskId: string, objectiveId: string, checked: boolean) => {
      onUserObjectiveToggleRef.current(taskId, objectiveId, checked);
    },
    [],
  );
  const {
    taskStatusOf,
    toggleObjDone,
    adoptObjectiveSkip,
    changeTaskStatus,
    locateTask,
    guideOpen,
    setGuideOpen,
    guideTaskId,
    setGuideTaskId,
    openGuide,
    onQuestLabelClick,
    highlightTaskId,
    setHighlightTaskId,
    focusRequest,
  } = useTarkovRaidTaskActions({
    enabled: true,
    gameMode,
    mapId,
    catalog: catalogRich,
    doneSet: doneTaskSet,
    startedSet: startedTaskSet,
    objDone,
    objDoneView,
    replaceObjDone,
    toggleObjDoneLocal,
    onUserObjectiveToggle,
    overlayTasks,
    ensureGeometry: geometry.ensure,
    locateResetKey: mapId,
  });
  onUserObjectiveToggleRef.current = () => {
    objectiveSaveGenRef.current += 1;
    if (!persistReadyRef.current || !mapId || !me || !stateQuery.isSuccess) return;
    const stored = readRaidPrepObjectiveDoneWithLegacy(objDoneScope, objDoneLegacy);
    const fromServer = objectiveDonesToSkipMap(
      (stateQuery.data?.objective_dones || []).map((row) => ({
        task_id: row.task_id,
        objective_id: row.objective_id,
        user_id: me.id,
      })),
      me.id,
    );
    const next =
      adoptObjectiveSkip(stored, mergeSkipMapsIfChanged(stored, fromServer)) ??
      stored;
    if (next !== stored) replaceObjDone(next);
    const body: RaidPrepStateBody = {
      selected,
      objective_dones: clipRaidPrepStateObjectiveDones(
        skipMapToObjectiveDones(next, { userId: me.id, name: myName }).map(
          (row) => ({
            task_id: row.task_id,
            objective_id: row.objective_id,
          }),
        ),
        catalog.map((row) => row.id),
      ),
      key_brings: keyBringIds,
    };
    if (sameRaidPrepStateBody(lastSavedRef.current.get(mapId), body)) return;
    queryClient.setQueryData(
      ["guides-tarkov-raid-prep-state", gameMode, mapId],
      (prev: { objective_dones?: RaidPrepStateBody["objective_dones"] } | undefined) =>
        prev ? { ...prev, objective_dones: [...body.objective_dones] } : prev,
    );
    void putTarkovRaidPrepState(mapId, {
      selected: [...body.selected],
      objective_dones: [...body.objective_dones],
      key_brings: [...body.key_brings],
    })
      .then(() => {
        lastSavedRef.current.set(mapId, body);
      })
      .catch(() => {});
  };

  useEffect(() => {
    if (!prepQuery.isSuccess || !catalog.length) return;
    const valid = new Set(catalog.map((row) => row.id));
    const next = selected.filter((id) => valid.has(id));
    if (next.join(",") === selected.join(",")) return;
    patchParams((params) => {
      const serialized = serializeSelectedIds(next);
      if (serialized) params.set("sel", serialized);
      else params.delete("sel");
    });
  }, [patchParams, prepQuery.isSuccess, catalog, selected]);

  const applySelected = useCallback(
    (next: string[]) => {
      const serialized = serializeSelectedIds(next);
      patchParams((params) => {
        if (serialized) params.set("sel", serialized);
        else params.delete("sel");
      });
    },
    [patchParams],
  );

  useEffect(() => {
    if (!mapId) {
      hydratedKeyRef.current = "";
      persistReadyRef.current = false;
      setKeyBringIds([]);
    }
  }, [mapId]);

  useEffect(() => {
    if (!mapId || !prepQuery.isSuccess) return;
    if (me && stateQuery.isLoading) return;
    const key = `${gameMode}:${mapId}:${stateQuery.dataUpdatedAt}:${taskDonesQuery.dataUpdatedAt}`;
    if (hydratedKeyRef.current === key) return;
    hydratedKeyRef.current = key;
    const urlSel = parseCsvParam(searchParamsRef.current.get("sel"));
    const fromState = stateQuery.data?.selected ?? [];
    let next = urlSel.length ? urlSel : fromState;
    const plan = planRaidPrepTaskProgressSync({
      catalogIds: catalog.map((row) => row.id),
      selectedIds: next,
      startedIds: loadTaskStartedIds(gameMode),
      doneIds: doneTaskIds,
    });
    next = settleRaidPrepSelection({
      selectedIds: plan.nextIds,
      completedIds: doneTaskIds,
    }).nextIds;
    if (next.join(",") !== selected.join(",")) applySelected(next);
    if (stateQuery.data) {
      setKeyBringIds(stateQuery.data.key_brings || []);
    }
    const fromServer =
      me && stateQuery.data
        ? objectiveDonesToSkipMap(
            (stateQuery.data.objective_dones || []).map((row) => ({
              task_id: row.task_id,
              objective_id: row.objective_id,
              user_id: me.id,
            })),
            me.id,
          )
        : undefined;
    const stored = readRaidPrepObjectiveDoneWithLegacy(objDoneScope, objDoneLegacy);
    const merged = mergeSkipMapsIfChanged(stored, fromServer);
    const sealed = adoptObjectiveSkip(stored, merged);
    if (sealed) replaceObjDone(sealed);
    persistReadyRef.current = true;
    setPersistTick((n) => n + 1);
  }, [
    applySelected,
    catalog,
    doneTaskIds,
    gameMode,
    mapId,
    me,
    adoptObjectiveSkip,
    objDoneLegacy,
    objDoneScope,
    prepQuery.isSuccess,
    replaceObjDone,
    selected,
    stateQuery.data,
    stateQuery.dataUpdatedAt,
    stateQuery.isLoading,
    taskDonesQuery.data,
    taskDonesQuery.dataUpdatedAt,
  ]);

  useEffect(() => {
    if (!mapId || !me || !persistReadyRef.current) return;
    const body = {
      selected,
      objective_dones: clipRaidPrepStateObjectiveDones(
        skipMapToObjectiveDones(objDone, {
          userId: me.id,
          name: myName,
        }).map((row) => ({
          task_id: row.task_id,
          objective_id: row.objective_id,
        })),
        catalog.map((row) => row.id),
      ),
      key_brings: keyBringIds,
    };
    // 负载没变就别 PUT（接口整行覆盖）：切图回来的首次挂载、每 2~3s 的日志 tick 都不该重写。
    if (sameRaidPrepStateBody(lastSavedRef.current.get(mapId), body)) return;
    const scheduledGen = objectiveSaveGenRef.current;
    const handle = window.setTimeout(() => {
      if (objectiveSaveGenRef.current !== scheduledGen) return;
      void putTarkovRaidPrepState(mapId, body)
        .then(() => {
          lastSavedRef.current.set(mapId, body);
        })
        .catch(() => {
          /* 未登录或网络失败时本机勾选仍可用；失败不记账，下一次负载变化再写 */
        });
    }, 700);
    return () => window.clearTimeout(handle);
  }, [catalog, keyBringIds, mapId, me, myName, objDone, persistTick, selected]);

  useEffect(() => {
    const onProgress = (event: Event) => {
      const detail = (event as CustomEvent<TarkovTaskProgressDetail>).detail;
      if (!detail || detail.mode !== gameMode) return;
      const plan = planRaidPrepTaskProgressSync({
        catalogIds: catalog.map((row) => row.id),
        selectedIds: selected,
        startedIds: detail.started,
        doneIds: detail.done,
      });
      const settled = settleRaidPrepSelection({
        selectedIds: plan.nextIds,
        completedIds: detail.completedIds?.length ? detail.completedIds : detail.done,
      });
      if (settled.nextIds.join(",") !== selected.join(",")) {
        applySelected(settled.nextIds);
      }
      const stored = readRaidPrepObjectiveDoneWithLegacy(
        objDoneScope,
        objDoneLegacy,
      );
      const merged = mergeObjectivePairs(stored, detail.objectives);
      const next = adoptObjectiveSkip(stored, merged);
      if (next) replaceObjDone(next);
      setProgressTick((n) => n + 1);
    };
    window.addEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
    return () =>
      window.removeEventListener(TARKOV_TASK_PROGRESS_EVENT, onProgress);
  }, [
    adoptObjectiveSkip,
    applySelected,
    catalog,
    gameMode,
    objDoneLegacy,
    objDoneScope,
    replaceObjDone,
    selected,
  ]);

  useEffect(() => {
    const latest = logsQuery.data?.items?.[0];
    if (!latest || latest.aborted || !latest.ended_at) return;
    const settled = settleRaidPrepSelection({
      selectedIds: selected,
      completedIds: doneTaskIds,
      aborted: latest.aborted,
    });
    if (settled.removedIds.length) applySelected(settled.nextIds);
  }, [applySelected, doneTaskIds, logsQuery.data, selected]);

  const rows = useMemo(
    () => filterRaidPrepRows(catalogRich, { q, faction }),
    [catalogRich, faction, q],
  );

  const selectedTasks = useMemo(
    () =>
      filterRaidPrepRows(selectedTasksFromCatalog(catalogRich, selected), {
        faction,
      }),
    [catalogRich, faction, selected],
  );
  const guideTasks = useMemo(
    () => mergeRaidPrepGuideTasks(selectedTasks, catalogRich, guideTaskId),
    [catalogRich, guideTaskId, selectedTasks],
  );
  const objectiveDones = useMemo(
    () =>
      me
        ? skipMapToObjectiveDones(objDoneView, {
            userId: me.id,
            name: myName,
          })
        : undefined,
    [me, myName, objDoneView],
  );
  const selectedIdSet = useMemo(() => new Set(selected), [selected]);
  const statusGroups = useMemo(() => {
    const grouped = groupRaidPrepRowsByProgress(
      rows,
      doneTaskSet,
      startedTaskSet,
    );
    return {
      active: pinSelectedRaidPrepRows(grouped.active, selectedIdSet),
      todo: pinSelectedRaidPrepRows(grouped.todo, selectedIdSet),
      done: pinSelectedRaidPrepRows(grouped.done, selectedIdSet),
    };
  }, [doneTaskSet, rows, selectedIdSet, startedTaskSet]);
  const participantsByTask = useMemo(() => {
    const name = (me?.display_name || me?.username || "").trim() || "?";
    const map = new Map<string, Array<{ name: string; userId?: number }>>();
    for (const task of selectedTasks) {
      map.set(task.id, [{ name, userId: me?.id }]);
    }
    return map;
  }, [selectedTasks, me?.id, me?.display_name, me?.username]);
  const keyBrings = useMemo(
    () =>
      me
        ? keyBringIds.map((itemId) => ({
            item_id: itemId,
            user_id: me.id,
            display_name: myName,
          }))
        : [],
    [keyBringIds, me, myName],
  );
  const soloRoom = useMemo(
    () =>
      buildSoloRaidRoomDetail({
        gameMode,
        mapSlug: mapId,
        user: me ? { id: me.id, displayName: myName } : null,
        selectedIds: selected,
        keyBringIds,
        keyOwnIds: ownsQuery.data?.item_ids,
        objectiveDones: objectiveDones?.map((row) => ({
          task_id: row.task_id,
          objective_id: row.objective_id,
        })),
      }),
    [
      gameMode,
      keyBringIds,
      mapId,
      me,
      myName,
      objectiveDones,
      ownsQuery.data?.item_ids,
      selected,
    ],
  );
  const displayLogPhases = useMemo(
    () => overlayRaidRoomLocalPhase([], me?.id, lastLogPhase),
    [lastLogPhase, me?.id],
  );
  const phaseByUser = useMemo(() => {
    const map = new Map<number, (typeof displayLogPhases)[number]>();
    for (const row of displayLogPhases) map.set(row.userId, row);
    return map;
  }, [displayLogPhases]);
  const roomLiveStatus =
    lastLogPhase?.kind === "raid_started"
      ? "in_raid"
      : raidRoomLiveStatus(
          me?.id ? [me.id] : [],
          displayLogPhases,
        );
  const overlays = useMemo(
    () => buildRaidPrepOverlays(overlayTasks, mapId),
    [overlayTasks, mapId],
  );
  const hideLocalFix = shouldSuppressLocalPlayerFix({
    viewMapId: mapId,
    logMapId: lastLogPhase?.mapId || lastLogMapId,
    phaseKind: lastLogPhase?.kind,
  });
  const toggleKeyBring = (itemId: string) => {
    setKeyBringIds((current) =>
      current.includes(itemId)
        ? current.filter((id) => id !== itemId)
        : [...current, itemId],
    );
  };
  const toggleKeyOwn = useCallback(
    async (itemId: string) => {
      if (!me) return;
      const current = ownsQuery.data?.item_ids || [];
      const have = current.includes(itemId);
      const next = have
        ? current.filter((id) => id !== itemId)
        : [...current, itemId];
      applyTarkovKeyOwnsCache(queryClient, next);
      try {
        const data = have
          ? await removeTarkovKeyOwn(itemId)
          : await addTarkovKeyOwn(itemId);
        applyTarkovKeyOwnsCache(queryClient, data.item_ids || []);
      } catch (exc) {
        applyTarkovKeyOwnsCache(queryClient, current);
        message.error(apiError(exc, "更新钥匙拥有失败"));
      }
    },
    [me, ownsQuery.data?.item_ids, queryClient],
  );
  const colorByTask = useMemo(() => {
    const map = new Map<string, string>();
    selected.forEach((id, index) => {
      map.set(id, colorForTaskIndex(index));
    });
    return map;
  }, [selected]);
  const mapLabel =
    raidPrepMapOptions().find((item) => item.id === mapId)?.label || mapId;

  const toggleSelected = useCallback(
    (id: string) => {
      patchParams((params) => {
        const current = parseCsvParam(params.get("sel"));
        if (
          !current.includes(id) &&
          doneTaskSet.has(id)
        ) {
          return;
        }
        const next = current.includes(id)
          ? current.filter((item) => item !== id)
          : [...current, id].slice(0, RAID_PREP_MAX_SELECTED);
        const serialized = serializeSelectedIds(next);
        if (serialized) params.set("sel", serialized);
        else params.delete("sel");
      });
    },
    [doneTaskSet, patchParams],
  );

  useEffect(() => {
    if (!mapId) navigate(TARKOV_HOME_PATH, { replace: true });
  }, [mapId, navigate]);

  if (!mapId) return null;

  return (
    <TarkovRaidWorkspace
      dockOpen={dockOpen}
      onToggleDock={() => setDockOpen((open) => !open)}
      alerts={
        prepQuery.isError ? (
          <Alert
            type="error"
            showIcon
            message="任务点位加载失败"
            description={apiError(prepQuery.error, "任务点位加载失败")}
          />
        ) : null
      }
      title={soloRoom.title}
      meta={
        <>
          {mapLabel}
          {mapId ? (
            <TarkovGoonSightingHint mapId={mapId} variant="inline" />
          ) : null}
          {" · "}
          {soloRoom.member_count}/{soloRoom.max_members}
          {" · "}
          <span
            className={styles.roomLive}
            data-in-raid={roomLiveStatus === "in_raid" ? "true" : "false"}
          >
            {formatRaidRoomLiveStatus(roomLiveStatus)}
          </span>
        </>
      }
      members={
        <TarkovRaidMemberStrip
          members={soloRoom.occupants}
          phaseByUser={phaseByUser}
        />
      }
      topActions={
        <>
          <button
            type="button"
            className={styles.dockChip}
            onClick={() => setChangeMapOpen(true)}
          >
            更换地图
          </button>
        </>
      }
      goonMapId={mapId}
      map={
        <TarkovRaidSessionMap
          publicId={SOLO_RAID_ROOM_PUBLIC_ID}
          mapId={mapId}
          detail={mapQuery.data}
          loading={mapQuery.isLoading}
          error={mapQuery.isError ? mapQuery.error : undefined}
          questOverlays={overlays}
          questObjectiveDones={objectiveDones}
          questSkippedByTask={objDoneView}
          focusRequest={focusRequest}
          highlightTaskId={highlightTaskId}
          suppressLocalFix={hideLocalFix}
          authorUserId={me?.id || 0}
          authorDisplayName={myName}
          members={soloRoom.occupants}
          onQuestLabelClick={onQuestLabelClick}
          onQuestCompleteObjective={toggleObjDone}
          questParticipantsByTask={participantsByTask}
          lockKeyMode="solo"
          lockKeyOwns={keyOwns}
          lockKeyBrings={keyBrings}
        />
      }
      dock={
        <>
          <TarkovRaidPrepFilters
            keyword={keyword}
            onKeyword={setKeyword}
            leading={
              <div className={styles.dockLeadActions}>
                <TarkovShotDirButton />
                <TarkovRaidPrepSummary
                  variant="dock"
                  tasks={selectedTasks}
                  mapId={mapId}
                  participantsByTask={participantsByTask}
                  keyOwns={keyOwns}
                  keyBrings={keyBrings}
                  canToggleKeyBring={Boolean(me)}
                  onToggleKeyBring={me ? toggleKeyBring : undefined}
                  canToggleKeyOwn={Boolean(me)}
                  onToggleKeyOwn={me ? toggleKeyOwn : undefined}
                  skippedByTask={objDoneView}
                  doneTaskIds={doneTaskIds}
                  objectiveDones={objectiveDones}
                  currentUserId={me?.id}
                  currentUser={
                    me
                      ? {
                          userId: me.id,
                          name: myName,
                        }
                      : null
                  }
                  onToggleObjective={toggleObjDone}
                  onTitle={openGuide}
                />
                <button
                  type="button"
                  className={styles.changeMapBtn}
                  disabled={logSync.listing}
                  title={logSync.title}
                  onClick={() => void logSync.openDialog()}
                >
                  {logSync.label}
                </button>
                <TarkovRaidPrepGuideOverview
                  open={guideOpen}
                  onOpenChange={setGuideOpen}
                  tasks={guideTasks}
                  mapId={mapId}
                  activeId={guideTaskId}
                  onActiveIdChange={setGuideTaskId}
                  participantsByTask={participantsByTask}
                  skippedByTask={objDoneView}
                  doneTaskIds={doneTaskIds}
                  onToggleObjective={toggleObjDone}
                />
              </div>
            }
          />
          {/* oxlint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions -- 点列表空白处清高亮只是鼠标便捷操作，行内控件各自可键盘操作 */}
          <div
            className={styles.taskList}
            onClick={() => setHighlightTaskId("")}
          >
            {prepQuery.isLoading && !prepQuery.data && !rows.length ? (
              <div className={styles.empty}>
                <Spin />
              </div>
            ) : (
              <TarkovRaidPrepTaskGroups
                groups={statusGroups}
                empty={<div className={styles.empty}>当前搜索下无任务</div>}
                renderRow={(row) => (
                  <TarkovRaidPrepTaskCard
                    key={row.id}
                    row={row}
                    mapSlug={mapId}
                    compact
                    checked={selectedIdSet.has(row.id)}
                    highlighted={selectedIdSet.has(row.id)}
                    status={taskStatusOf(row.id)}
                    done={taskStatusOf(row.id) === "done"}
                    active={highlightTaskId === row.id}
                    color={
                      selectedIdSet.has(row.id)
                        ? colorByTask.get(row.id) || colorForTaskIndex(0)
                        : undefined
                    }
                    skipped={raidPrepSkippedIds(objDoneView, row.id)}
                    onToggleObjective={toggleObjDone}
                    onToggle={toggleSelected}
                    onNeedDetail={geometry.ensure}
                    onLocate={locateTask}
                    onTitle={openGuide}
                    onSetStatus={changeTaskStatus}
                  />
                )}
              />
            )}
          </div>
        </>
      }
    >
      <TarkovRaidPrepEntryModal
        open={changeMapOpen}
        step="solo"
        currentMapId={mapId}
        onClose={() => setChangeMapOpen(false)}
        onSoloMap={setMap}
      />
      <TarkovLogSyncRangeModal
        open={logSync.open}
        sessions={logSync.sessions}
        onCancel={logSync.closeDialog}
        onConfirm={logSync.confirm}
      />
    </TarkovRaidWorkspace>
  );
}
